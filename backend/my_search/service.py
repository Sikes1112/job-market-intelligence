"""Bounded read projection over the existing search authorities."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.career_decisions.models import (
    CareerAction,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    CareerOutcome,
    DecisionOption,
    DecisionVersion,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import ApplicationCreateInput, ApplicationStatus
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.current_opportunities.models import CurrentOpportunity, OpportunityCoverageContract
from backend.current_opportunities.pursuit_scope import (
    PursuitOpportunityScopeError,
    pursuit_opportunity_scope,
)
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.service import CurrentOpportunityService
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.my_search.schemas import (
    ActivePursuitView,
    OpportunitySummaryView,
    PursuitActionView,
    PursuitApplicationView,
    PursuitOptionView,
    SavedComparisonView,
    SavedItemView,
    SearchHistoryItemView,
    SearchWorkspaceView,
    SourceComparisonView,
    TrackOpportunityInput,
    TrackOpportunityResult,
)
from backend.product_measurement.models import ProductAnalyticsEvent
from backend.product_measurement.schemas import ProductEventType
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import UserNotFound
from backend.users.models import SavedMarketArtifact
from backend.users.repository import UserRepository

ACTIVE_DECISION_STATUSES = ("draft", "evaluating", "decided", "reconsidering")
SEARCH_DECISION_TYPES = (
    "role_choice",
    "company_choice",
    "location_choice",
    "career_strategy",
    "job_search_strategy",
    "offer_comparison",
    "career_path",
)
INCOMPLETE_ACTION_STATUSES = frozenset({"open", "in_progress", "blocked"})
ACTIVE_APPLICATION_STATUSES = frozenset(
    {"considering", "preparing", "applied", "response", "interview", "final_round", "offer"}
)


class SearchWorkspaceNotFound(LookupError):
    pass


class SearchWorkspaceValidationError(ValueError):
    pass


class MySearchService:
    """Compose current-user search state without owning any durable authority."""

    def __init__(self, session: Session, *, clock: callable | None = None) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    def workspace(self, user_id: str) -> SearchWorkspaceView:
        self._ensure_user(user_id)
        decisions = list(
            self._session.execute(
                select(CareerDecision)
                .where(
                    CareerDecision.user_id == user_id,
                    CareerDecision.decision_type.in_(SEARCH_DECISION_TYPES),
                )
                .order_by(CareerDecision.updated_at.desc(), CareerDecision.decision_id)
                .limit(100)
            ).scalars()
        )
        active = [row for row in decisions if row.status in ACTIVE_DECISION_STATUSES]
        active_ids = [row.decision_id for row in active]

        options = self._rows_for_decisions(DecisionOption, active_ids)
        actions = self._rows_for_user(CareerAction, user_id, limit=500)
        applications = self._rows_for_user(CareerApplication, user_id, limit=500)
        outcomes = self._rows_for_user(CareerOutcome, user_id, limit=200)
        versions = self._rows_for_user(DecisionVersion, user_id, limit=300)
        transitions = self._rows_for_user(CareerApplicationTransition, user_id, limit=300)
        action_completion_events = list(
            self._session.execute(
                select(ProductAnalyticsEvent)
                .where(
                    ProductAnalyticsEvent.user_id == user_id,
                    ProductAnalyticsEvent.event_type == ProductEventType.ACTION_SUCCEEDED.value,
                )
                .order_by(
                    ProductAnalyticsEvent.occurred_at.desc(),
                    ProductAnalyticsEvent.event_id.desc(),
                )
                .limit(300)
            ).scalars()
        )
        provenances = self._provenances(user_id, active_ids)
        comparison_snapshots = self._comparison_snapshots(provenances)
        saved_comparisons = self._saved_comparisons(user_id)
        saved_items = self._saved_items(user_id)

        company_names = self._company_names(applications)
        region_views = self._region_views(options, applications, saved_items)
        opportunity_rows = self._opportunities(region_views)
        coverage_rows = list(self._session.execute(select(OpportunityCoverageContract)).scalars())

        options_by_decision = _group(options, "decision_id")
        actions_by_decision = _group(actions, "decision_id")
        applications_by_decision = _group(applications, "decision_id")
        opportunity_by_market = _group(opportunity_rows, "market_id")

        pursuits = tuple(
            self._pursuit(
                row,
                options_by_decision.get(row.decision_id, []),
                actions_by_decision.get(row.decision_id, []),
                applications_by_decision.get(row.decision_id, []),
                provenances.get(row.decision_id),
                comparison_snapshots,
                company_names,
                region_views,
                opportunity_by_market,
                coverage_rows,
            )
            for row in active
            if _selected_option(row, options_by_decision.get(row.decision_id, [])) is not None
        )
        application_views = tuple(
            self._application_view(row, company_names, region_views) for row in applications
        )
        return SearchWorkspaceView(
            active_pursuits=pursuits,
            applications=application_views,
            saved_comparisons=tuple(saved_comparisons),
            saved_items=tuple(self._saved_item_view(row, region_views) for row in saved_items),
            history=self._history(
                decisions,
                actions,
                applications,
                transitions,
                outcomes,
                versions,
                action_completion_events,
            ),
            generated_at=self._clock(),
        )

    def track_opportunity(
        self, user_id: str, request: TrackOpportunityInput
    ) -> TrackOpportunityResult:
        self._ensure_user(user_id)
        decision = self._session.get(CareerDecision, request.decision_id)
        if decision is None or decision.user_id != user_id:
            raise SearchWorkspaceNotFound(request.decision_id)
        if decision.status not in ACTIVE_DECISION_STATUSES:
            raise SearchWorkspaceValidationError(
                "applications can only be added to an active pursuit"
            )

        opportunity_service = CurrentOpportunityService(CurrentOpportunityRepository(self._session))
        try:
            opportunity = opportunity_service.get_opportunity(
                request.opportunity_id, require_display=True
            )
        except LookupError as exc:
            raise SearchWorkspaceNotFound(request.opportunity_id) from exc

        try:
            scope = opportunity_service.pursuit_scope(user_id, decision.decision_id)
        except ValueError as exc:
            raise SearchWorkspaceValidationError(str(exc)) from exc
        if not scope.allows(opportunity):
            raise SearchWorkspaceValidationError(
                "opportunity is not eligible for the pursuit's selected context"
            )

        existing = self._tracked_opportunity(
            user_id, decision.decision_id, opportunity.opportunity_id
        )
        created = existing is None
        if existing is None:
            try:
                with self._session.begin_nested():
                    application = self._decision_service().create_application(
                        user_id,
                        ApplicationCreateInput(
                            decision_id=decision.decision_id,
                            option_id=decision.selected_option_id,
                            company_id=opportunity.company_id,
                            region_id=opportunity.market_id,
                            role_title=opportunity.normalized_title,
                            status=ApplicationStatus(request.initial_status.value),
                            source_url=opportunity.application_url or opportunity.source_url,
                            metadata={
                                "current_opportunity_id": opportunity.opportunity_id,
                                "company_name": opportunity.company_name,
                                "market_label": opportunity.market_label,
                                "external_application_url": opportunity.application_url,
                                "source": "layer_38_current_opportunity",
                            },
                        ),
                        current_opportunity_id=opportunity.opportunity_id,
                    )
                    existing = self._session.get(CareerApplication, application.application_id)
            except IntegrityError:
                existing = self._tracked_opportunity(
                    user_id, decision.decision_id, opportunity.opportunity_id
                )
                created = False
        if existing is None:
            raise SearchWorkspaceNotFound(request.opportunity_id)
        company_names = (
            {existing.company_id: opportunity.company_name} if existing.company_id else {}
        )
        region_views: dict[str, dict[str, str | None]] = {}
        if existing.region_id:
            region_views[existing.region_id] = {
                "region_id": existing.region_id,
                "display_name": opportunity.market_label,
                "public_slug": opportunity.market_public_slug,
            }
        return TrackOpportunityResult(
            application=self._application_view(existing, company_names, region_views),
            created=created,
            external_application_url=opportunity.application_url,
        )

    def _tracked_opportunity(
        self, user_id: str, decision_id: str, opportunity_id: str
    ) -> CareerApplication | None:
        return self._session.execute(
            select(CareerApplication)
            .where(
                CareerApplication.user_id == user_id,
                CareerApplication.decision_id == decision_id,
                CareerApplication.current_opportunity_id == opportunity_id,
            )
            .order_by(CareerApplication.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _pursuit(
        self,
        decision: CareerDecision,
        options: list[DecisionOption],
        actions: list[CareerAction],
        applications: list[CareerApplication],
        provenance: ExploreDecisionProvenance | None,
        comparison_snapshots: dict[str, ExploreComparisonSnapshot],
        company_names: dict[str, str],
        region_views: dict[str, dict[str, str | None]],
        opportunity_by_market: dict[str | None, list[CurrentOpportunity]],
        coverage_rows: list[OpportunityCoverageContract],
    ) -> ActivePursuitView:
        selected = _selected_option(decision, options)
        if selected is None:  # guarded by caller
            raise SearchWorkspaceValidationError("active pursuit has no selected option")
        selected_view = self._option_view(selected, region_views)
        incomplete = [row for row in actions if row.status in INCOMPLETE_ACTION_STATUSES]
        incomplete.sort(key=_action_sort_key)
        app_views = tuple(
            self._application_view(row, company_names, region_views) for row in applications
        )
        meaningful_times = [decision.updated_at]
        meaningful_times.extend(row.updated_at for row in actions)
        meaningful_times.extend(row.updated_at for row in applications)
        market_rows = opportunity_by_market.get(selected_view.region_id, [])
        try:
            pursuit_scope = pursuit_opportunity_scope(decision, selected)
        except PursuitOpportunityScopeError as exc:
            raise SearchWorkspaceValidationError(str(exc)) from exc
        market_rows = [row for row in market_rows if pursuit_scope.allows(row)]
        return ActivePursuitView(
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            status=decision.status,
            title=decision.title,
            selected_priority=selected_view,
            alternatives=tuple(
                self._option_view(row, region_views)
                for row in options
                if row.option_id != selected.option_id
            ),
            target_context=_target_context(decision),
            prioritized_at=decision.decision_date,
            next_action=self._action_view(incomplete[0]) if incomplete else None,
            open_action_count=len(incomplete),
            completed_action_count=sum(row.status == "completed" for row in actions),
            applications=app_views,
            active_application_count=sum(
                row.status in ACTIVE_APPLICATION_STATUSES for row in applications
            ),
            applications_needing_attention=sum(item.needs_attention for item in app_views),
            source_comparison=self._source_comparison(
                provenance, comparison_snapshots, selected, options
            ),
            current_opportunities=self._opportunity_summary(
                selected_view.region_id, market_rows, coverage_rows
            ),
            latest_meaningful_update_at=max(meaningful_times),
        )

    def _source_comparison(
        self,
        provenance: ExploreDecisionProvenance | None,
        comparison_snapshots: dict[str, ExploreComparisonSnapshot],
        selected: DecisionOption,
        options: list[DecisionOption],
    ) -> SourceComparisonView | None:
        if provenance is None:
            return None
        snapshot = comparison_snapshots.get(provenance.comparison_id)
        recommendation_summary = None
        generated_at = None
        if snapshot is not None:
            recommendation_summary = snapshot.snapshot_payload.get("recommendation_summary")
            generated_at = snapshot.generated_at
        option_by_region = {
            str(row.scenario.get("region_id")): row.title
            for row in options
            if row.scenario.get("region_id")
        }
        recommended = tuple(
            option_by_region.get(region_id, region_id)
            for region_id in (provenance.system_recommended_region_ids or [])
        )
        recommended_region_ids = tuple(provenance.system_recommended_region_ids or [])
        original_region_id = provenance.user_selected_region_id
        current_region_id = _option_region_id(selected)
        current_matches = (
            current_region_id in recommended_region_ids if recommended_region_ids else None
        )
        return SourceComparisonView(
            comparison_id=provenance.comparison_id,
            compared_markets=tuple(row.title for row in options),
            system_recommendation=recommended,
            original_user_choice=option_by_region.get(original_region_id, original_region_id),
            original_choice_matches_recommendation=provenance.choice_matches_recommendation,
            current_user_choice=selected.title,
            current_choice_matches_recommendation=current_matches,
            recommendation_state=provenance.system_recommendation_state,
            recommendation_summary=recommendation_summary,
            generated_at=generated_at,
        )

    def _opportunity_summary(
        self,
        market_id: str | None,
        rows: list[CurrentOpportunity],
        coverage_rows: list[OpportunityCoverageContract],
    ) -> OpportunitySummaryView:
        coverage = _coverage_for_market(market_id, coverage_rows)
        limitations: list[str] = []
        if coverage is None:
            coverage_status = "unsupported"
            rationale = "No explicit current-opportunity coverage contract exists for this market."
            limitations.append("Unknown coverage does not mean there are no opportunities.")
        else:
            coverage_status = coverage.operator_override_status or coverage.status
            rationale = coverage.rationale
            if coverage_status == "unsupported":
                limitations.append("Unsupported coverage does not mean there are no opportunities.")
            elif coverage_status == "limited":
                limitations.append("The observed opportunity set is partial, not exhaustive.")
            elif coverage_status == "experimental":
                limitations.append("Experimental coverage is not a complete market inventory.")
        active = [row for row in rows if row.canonical_status in {"active", "stale"}]
        active.sort(
            key=lambda row: (
                row.ranking_eligible,
                row.last_observed_at or datetime.min.replace(tzinfo=UTC),
                row.current_opportunity_id,
            ),
            reverse=True,
        )
        return OpportunitySummaryView(
            market_id=market_id,
            coverage_status=coverage_status,
            coverage_rationale=rationale,
            coverage_limitations=tuple(limitations),
            observed_active_count=len(active),
            ranking_eligible_count=sum(row.ranking_eligible for row in active),
            fresh_count=sum(row.freshness_state == "fresh" for row in active),
            latest_observed_at=max(
                (row.last_observed_at for row in active if row.last_observed_at), default=None
            ),
            top_opportunities=tuple(
                {
                    "opportunity_id": row.current_opportunity_id,
                    "company_name": row.company_name,
                    "role_title": row.normalized_title,
                    "freshness_state": row.freshness_state,
                    "ranking_eligible": row.ranking_eligible,
                    "application_url_available": bool(row.application_url),
                }
                for row in active[:3]
            ),
        )

    def _application_view(
        self,
        row: CareerApplication,
        company_names: dict[str, str],
        region_views: dict[str, dict[str, str | None]],
    ) -> PursuitApplicationView:
        metadata = row.metadata_json or {}
        company_name = company_names.get(row.company_id or "") or str(
            metadata.get("company_name") or "Company not specified"
        )
        market = region_views.get(row.region_id or "", {})
        market_name = (
            market.get("display_name")
            or metadata.get("market_label")
            or metadata.get("location_text")
        )
        now = self._clock()
        follow_up_due = bool(row.follow_up_at and _aware(row.follow_up_at) <= _aware(now))
        draft = row.status in {"considering", "preparing"}
        attention_reason = "Follow-up due" if follow_up_due else "Not submitted" if draft else None
        return PursuitApplicationView(
            application_id=row.application_id,
            decision_id=row.decision_id,
            company_id=row.company_id,
            company_name=company_name,
            region_id=row.region_id,
            market_name=str(market_name) if market_name else None,
            role_title=row.role_title or "Role not specified",
            status=row.status,
            applied_at=row.applied_at,
            follow_up_at=row.follow_up_at,
            source_url=row.source_url,
            current_opportunity_id=metadata.get("current_opportunity_id"),
            needs_attention=follow_up_due or draft,
            attention_reason=attention_reason,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _action_view(row: CareerAction) -> PursuitActionView:
        return PursuitActionView(
            action_id=row.action_id,
            action_type=row.action_type,
            status=row.status,
            title=row.title,
            description=row.description,
            due_at=row.due_at,
            priority=row.priority,
            completed_at=row.completed_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _option_view(
        row: DecisionOption, region_views: dict[str, dict[str, str | None]]
    ) -> PursuitOptionView:
        region_id = _option_region_id(row)
        region = region_views.get(str(region_id), {}) if region_id else {}
        return PursuitOptionView(
            option_id=row.option_id,
            title=row.title,
            region_id=str(region_id) if region_id else None,
            public_slug=region.get("public_slug") or row.scenario.get("public_slug"),
        )

    def _history(
        self,
        decisions: list[CareerDecision],
        actions: list[CareerAction],
        applications: list[CareerApplication],
        transitions: list[CareerApplicationTransition],
        outcomes: list[CareerOutcome],
        versions: list[DecisionVersion],
        action_completion_events: list[ProductAnalyticsEvent],
    ) -> tuple[SearchHistoryItemView, ...]:
        decision_titles = {row.decision_id: row.title for row in decisions}
        application_by_id = {row.application_id: row for row in applications}
        action_by_id = {row.action_id: row for row in actions}
        items: list[SearchHistoryItemView] = []
        for row in versions:
            if row.version_reason not in {"option_selected", "reopened"}:
                continue
            selected = next(
                (
                    item.get("title")
                    for item in row.options_snapshot or []
                    if item.get("option_id") == row.selected_option_id
                ),
                None,
            )
            verb = "Prioritized" if row.version_reason == "option_selected" else "Reopened"
            items.append(
                SearchHistoryItemView(
                    history_id=f"decision:{row.decision_version_id}",
                    kind=row.version_reason,
                    title=f"{verb} {selected or decision_titles.get(row.decision_id, 'pursuit')}",
                    detail=decision_titles.get(row.decision_id),
                    occurred_at=row.created_at,
                    decision_id=row.decision_id,
                )
            )
        event_action_ids: set[str] = set()
        for event in action_completion_events:
            if event.action_id is None or (event.payload or {}).get("status") != "completed":
                continue
            action = action_by_id.get(event.action_id)
            if action is None:
                continue
            event_action_ids.add(event.action_id)
            items.append(
                SearchHistoryItemView(
                    history_id=f"action_event:{event.event_id}",
                    kind="action_completed",
                    title=f"Completed {action.title}",
                    detail=decision_titles.get(action.decision_id or ""),
                    occurred_at=event.occurred_at,
                    decision_id=action.decision_id,
                )
            )
        for row in actions:
            if (
                row.action_id in event_action_ids
                or row.status != "completed"
                or row.completed_at is None
            ):
                continue
            items.append(
                SearchHistoryItemView(
                    history_id=f"action:{row.action_id}",
                    kind="action_completed",
                    title=f"Completed {row.title}",
                    detail=decision_titles.get(row.decision_id or ""),
                    occurred_at=row.completed_at,
                    decision_id=row.decision_id,
                )
            )
        for row in applications:
            items.append(
                SearchHistoryItemView(
                    history_id=f"application:{row.application_id}",
                    kind="application_tracking_started",
                    title=f"Started tracking {row.role_title or 'an application'}",
                    detail=str((row.metadata_json or {}).get("company_name") or "Application"),
                    occurred_at=row.created_at,
                    decision_id=row.decision_id,
                    application_id=row.application_id,
                )
            )
        for row in transitions:
            if row.from_status is None:
                continue
            application = application_by_id.get(row.application_id)
            items.append(
                SearchHistoryItemView(
                    history_id=f"transition:{row.transition_id}",
                    kind="application_status_changed",
                    title=f"Application moved to {row.to_status.replace('_', ' ')}",
                    detail=application.role_title if application else None,
                    occurred_at=row.transitioned_at,
                    decision_id=application.decision_id if application else None,
                    application_id=row.application_id,
                )
            )
        for row in outcomes:
            items.append(
                SearchHistoryItemView(
                    history_id=f"outcome:{row.outcome_id}",
                    kind="outcome_recorded",
                    title=row.title,
                    detail=row.outcome_type.replace("_", " "),
                    occurred_at=row.occurred_at,
                    decision_id=row.decision_id,
                    application_id=row.application_id,
                )
            )
        items.sort(key=lambda item: (_aware(item.occurred_at), item.history_id), reverse=True)
        return tuple(items[:30])

    def _saved_comparisons(self, user_id: str) -> list[SavedComparisonView]:
        rows = list(
            self._session.execute(
                select(ExploreComparisonSnapshot)
                .where(
                    ExploreComparisonSnapshot.user_id == user_id,
                    ExploreComparisonSnapshot.saved_at.is_not(None),
                )
                .order_by(ExploreComparisonSnapshot.saved_at.desc())
                .limit(100)
            ).scalars()
        )
        return [
            SavedComparisonView(
                comparison_id=row.comparison_id,
                market_names=tuple(
                    str(item.get("fit", {}).get("region", {}).get("display_name", "Market"))
                    for item in row.snapshot_payload.get("compared_markets", [])
                    if isinstance(item, dict)
                ),
                context_summary=_saved_context_summary(row.effective_context_summary),
                recommendation_state=row.recommendation_state,
                recommendation_summary=row.recommendation_summary,
                winner_region_ids=tuple(row.winner_region_ids or []),
                generated_at=row.generated_at,
                saved_at=row.saved_at,
            )
            for row in rows
            if row.saved_at is not None
        ]

    def _saved_items(self, user_id: str) -> list[SavedMarketArtifact]:
        return list(
            self._session.execute(
                select(SavedMarketArtifact)
                .where(SavedMarketArtifact.user_id == user_id)
                .order_by(SavedMarketArtifact.created_at.desc())
                .limit(200)
            ).scalars()
        )

    @staticmethod
    def _saved_item_view(
        row: SavedMarketArtifact, region_views: dict[str, dict[str, str | None]]
    ) -> SavedItemView:
        region = region_views.get(row.artifact_ref, {}) if row.artifact_type == "region" else {}
        return SavedItemView(
            saved_artifact_id=row.saved_artifact_id,
            artifact_type=row.artifact_type,
            artifact_ref=row.artifact_ref,
            label=row.label,
            notes=row.notes,
            region_id=region.get("region_id"),
            public_slug=region.get("public_slug"),
            display_name=region.get("display_name"),
            created_at=row.created_at,
        )

    def _provenances(
        self, user_id: str, decision_ids: list[str]
    ) -> dict[str, ExploreDecisionProvenance]:
        if not decision_ids:
            return {}
        rows = self._session.execute(
            select(ExploreDecisionProvenance).where(
                ExploreDecisionProvenance.user_id == user_id,
                ExploreDecisionProvenance.decision_id.in_(decision_ids),
            )
        ).scalars()
        return {row.decision_id: row for row in rows}

    def _comparison_snapshots(
        self, provenances: dict[str, ExploreDecisionProvenance]
    ) -> dict[str, ExploreComparisonSnapshot]:
        comparison_ids = {row.comparison_id for row in provenances.values()}
        if not comparison_ids:
            return {}
        rows = self._session.execute(
            select(ExploreComparisonSnapshot).where(
                ExploreComparisonSnapshot.comparison_id.in_(comparison_ids)
            )
        ).scalars()
        return {row.comparison_id: row for row in rows}

    def _company_names(self, applications: list[CareerApplication]) -> dict[str, str]:
        ids = {row.company_id for row in applications if row.company_id}
        if not ids:
            return {}
        rows = self._session.execute(select(Company).where(Company.company_id.in_(ids))).scalars()
        return {row.company_id: row.company_name for row in rows}

    def _region_views(
        self,
        options: list[DecisionOption],
        applications: list[CareerApplication],
        saved_items: list[SavedMarketArtifact],
    ) -> dict[str, dict[str, str | None]]:
        ids = {row.region_id for row in applications if row.region_id}
        ids.update(
            row.artifact_ref
            for row in saved_items
            if row.artifact_type == "region" and row.artifact_ref
        )
        for option in options:
            region_id = option.scenario.get("region_id")
            ids.update([str(region_id)] if region_id else [])
            ids.update(str(value) for value in (option.scenario.get("region_ids") or []))
        if not ids:
            return {}
        rows = self._session.execute(select(Region).where(Region.region_id.in_(ids))).scalars()
        return {
            row.region_id: {
                "region_id": row.region_id,
                "display_name": row.display_name,
                "public_slug": row.public_slug,
            }
            for row in rows
        }

    def _opportunities(
        self, region_views: dict[str, dict[str, str | None]]
    ) -> list[CurrentOpportunity]:
        if not region_views:
            return []
        return list(
            self._session.execute(
                select(CurrentOpportunity)
                .where(
                    CurrentOpportunity.market_id.in_(region_views),
                    CurrentOpportunity.canonical_status.in_(("active", "stale")),
                )
                .order_by(
                    CurrentOpportunity.ranking_eligible.desc(),
                    CurrentOpportunity.last_observed_at.desc(),
                )
                .limit(500)
            ).scalars()
        )

    def _decision_service(self) -> CareerDecisionService:
        return CareerDecisionService(
            CareerDecisionRepository(self._session),
            CareerIdentityRepository(self._session),
            UserRepository(self._session),
            RegionRepository(self._session),
            CompanyRepository(self._session),
            RegionScoreRepository(self._session),
            ProductMeasurementService(self._session),
        )

    def _ensure_user(self, user_id: str) -> None:
        if UserRepository(self._session).get_user(user_id) is None:
            raise UserNotFound(user_id)

    def _rows_for_decisions(self, model: type, decision_ids: list[str]) -> list[Any]:
        if not decision_ids:
            return []
        return list(
            self._session.execute(
                select(model).where(model.decision_id.in_(decision_ids)).limit(1000)
            ).scalars()
        )

    def _rows_for_user(self, model: type, user_id: str, *, limit: int) -> list[Any]:
        return list(
            self._session.execute(
                select(model)
                .where(model.user_id == user_id)
                .order_by(model.created_at.desc())
                .limit(limit)
            ).scalars()
        )


def _group(rows: list[Any], field: str) -> dict[Any, list[Any]]:
    result: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        result[getattr(row, field)].append(row)
    return dict(result)


def _selected_option(
    decision: CareerDecision, options: list[DecisionOption]
) -> DecisionOption | None:
    return next((row for row in options if row.option_id == decision.selected_option_id), None)


def _option_region_id(option: DecisionOption) -> str | None:
    region_id = option.scenario.get("region_id")
    if region_id is None:
        region_ids = option.scenario.get("region_ids") or []
        region_id = region_ids[0] if region_ids else None
    return str(region_id) if region_id else None


def _action_sort_key(row: CareerAction) -> tuple[Any, ...]:
    due = _aware(row.due_at) if row.due_at else datetime.max.replace(tzinfo=UTC)
    priority = -(row.priority or 0)
    return (
        row.status == "blocked",
        due,
        priority,
        row.position,
        _aware(row.created_at),
        row.action_id,
    )


def _target_context(decision: CareerDecision) -> str | None:
    priorities = [
        str(item.get("label") or item.get("key", "")).strip()
        for item in (decision.priorities or [])
        if isinstance(item, dict)
    ]
    return " · ".join(item for item in priorities if item) or None


def _coverage_for_market(
    market_id: str | None, rows: list[OpportunityCoverageContract]
) -> OpportunityCoverageContract | None:
    if market_id is None:
        return None
    by_scope = {(row.market_key, row.role_family, row.opportunity_type): row for row in rows}
    for row in rows:
        if row.market_id:
            by_scope.setdefault((row.market_id, row.role_family, row.opportunity_type), row)
    for scope in ((market_id, "*", "*"), ("*", "*", "*")):
        if scope in by_scope:
            return by_scope[scope]
    candidates = [row for row in rows if row.market_key == market_id or row.market_id == market_id]
    return candidates[0] if candidates else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _saved_context_summary(context: dict[str, Any]) -> str:
    goal = context.get("goal")
    if isinstance(goal, str) and goal:
        return goal.replace("_", " ").title()
    roles = context.get("role_families") or []
    if isinstance(roles, list) and roles:
        return ", ".join(str(item).replace("_", " ").title() for item in roles[:2])
    return "General market intelligence"
