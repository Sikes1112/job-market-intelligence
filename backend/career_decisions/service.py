"""Layer 36A career decision lifecycle service."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.career_decisions.exceptions import (
    CareerDecisionNotFound,
    CareerDecisionTransitionError,
    CareerDecisionValidationError,
)
from backend.career_decisions.models import (
    CareerAction,
    CareerActionPlan,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    CareerOutcome,
    DecisionContextSnapshot,
    DecisionOption,
    DecisionRecommendation,
    DecisionVersion,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    ActionPlanView,
    ApplicationCreateInput,
    ApplicationStatus,
    ApplicationTransitionInput,
    ApplicationTransitionView,
    ApplicationView,
    CareerActionInput,
    CareerActionStatus,
    CareerActionType,
    CareerActionUpdateInput,
    CareerActionView,
    ChallengeCode,
    ConfidenceLevel,
    DecisionContextView,
    DecisionCreateInput,
    DecisionOptionInput,
    DecisionOptionStatus,
    DecisionOptionView,
    DecisionRecommendationStatus,
    DecisionRecommendationView,
    DecisionStatus,
    DecisionUpdateInput,
    DecisionVersionView,
    DecisionView,
    EvidenceKind,
    EvidenceSufficiency,
    FitAssessment,
    OptionSelectInput,
    OutcomeCreateInput,
    OutcomeType,
    OutcomeView,
    WeeklyReviewView,
)
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.repository import CompanyRepository
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.product_measurement.schemas import (
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
)
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.repository import UserRepository

TERMINAL_APPLICATION_STATUSES = {
    ApplicationStatus.REJECTED.value,
    ApplicationStatus.WITHDRAWN.value,
    ApplicationStatus.ACCEPTED.value,
    ApplicationStatus.DECLINED.value,
}

LEGAL_APPLICATION_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("considering", "preparing"),
        ("considering", "applied"),
        ("considering", "withdrawn"),
        ("preparing", "applied"),
        ("preparing", "withdrawn"),
        ("applied", "response"),
        ("applied", "interview"),
        ("applied", "rejected"),
        ("applied", "withdrawn"),
        ("applied", "offer"),
        ("response", "interview"),
        ("response", "rejected"),
        ("response", "withdrawn"),
        ("interview", "final_round"),
        ("interview", "rejected"),
        ("interview", "withdrawn"),
        ("interview", "offer"),
        ("final_round", "offer"),
        ("final_round", "rejected"),
        ("final_round", "withdrawn"),
        ("offer", "accepted"),
        ("offer", "declined"),
        ("offer", "withdrawn"),
    }
)


@dataclass(frozen=True, slots=True)
class FitDimension:
    name: str
    assessment: str
    evidence_kind: str
    evidence_refs: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...] = ()


class CareerDecisionService:
    def __init__(
        self,
        repository: CareerDecisionRepository,
        career_identity_repository: CareerIdentityRepository,
        user_repository: UserRepository,
        region_repository: RegionRepository,
        company_repository: CompanyRepository,
        score_repository: RegionScoreRepository,
        measurement_service: ProductMeasurementService | None = None,
    ) -> None:
        self._repo = repository
        self._identity_repo = career_identity_repository
        self._user_repo = user_repository
        self._region_repo = region_repository
        self._company_repo = company_repository
        self._score_repo = score_repository
        self._measurement = measurement_service

    def create_decision(self, user_id: str, request: DecisionCreateInput) -> DecisionView:
        self._ensure_user(user_id)
        identity = self._identity_for_context(user_id)
        context = self._create_context_snapshot(user_id, identity)
        decision = CareerDecision(
            decision_id=_new_id("decision"),
            user_id=user_id,
            career_identity_id=identity.career_identity_id,
            current_context_snapshot_id=context.context_snapshot_id,
            decision_type=request.decision_type.value,
            status=DecisionStatus.DRAFT.value,
            title=request.title,
            description=request.description,
            target_date=request.target_date,
            planned_review_at=request.planned_review_at,
            time_horizon=request.time_horizon,
            priorities=[item.model_dump(mode="json") for item in request.priorities],
            constraints=[item.model_dump(mode="json") for item in request.constraints],
            current_version=1,
        )
        self._repo.add(decision)
        self._repo.flush()
        for index, option_input in enumerate(request.options):
            self._add_option_row(user_id, decision, option_input, default_position=index)
        self._repo.flush()
        self._append_version(decision, "created")
        self._repo.flush()
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.DECISION_CREATED,
                event_source=ProductEventSource.BACKEND,
                decision_id=decision.decision_id,
                career_identity_id=identity.career_identity_id,
                career_identity_version=identity.current_version,
                product_surface="decision_workspace",
                payload={
                    "decision_type": decision.decision_type,
                    "option_count": len(request.options),
                },
            ),
        )
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.DECISION_CONSIDERED,
                event_source=ProductEventSource.BACKEND,
                decision_id=decision.decision_id,
                career_identity_id=identity.career_identity_id,
                career_identity_version=identity.current_version,
                product_surface="decision_workspace",
                payload={"decision_type": decision.decision_type},
            ),
        )
        return self.decision_view(user_id, decision.decision_id)

    def list_decisions(self, user_id: str, *, limit: int = 100) -> tuple[DecisionView, ...]:
        self._ensure_user(user_id)
        return tuple(
            self._decision_view(row, include_graph=False)
            for row in self._repo.list_decisions(user_id, limit=limit)
        )

    def decision_view(self, user_id: str, decision_id: str) -> DecisionView:
        decision = self._owned_decision(user_id, decision_id)
        return self._decision_view(decision, include_graph=True)

    def update_decision(
        self,
        user_id: str,
        decision_id: str,
        request: DecisionUpdateInput,
    ) -> DecisionView:
        decision = self._owned_decision(user_id, decision_id)
        if request.status is not None:
            decision.status = request.status.value
            if request.status is DecisionStatus.DECIDED and decision.decision_date is None:
                decision.decision_date = _now()
        for field in ("title", "description", "target_date", "planned_review_at", "time_horizon"):
            value = getattr(request, field)
            if value is not None:
                setattr(decision, field, value)
        if request.priorities is not None:
            decision.priorities = [item.model_dump(mode="json") for item in request.priorities]
        if request.constraints is not None:
            decision.constraints = [item.model_dump(mode="json") for item in request.constraints]
        decision.current_version += 1
        self._repo.flush()
        self._append_version(decision, "updated", user_note=request.user_note)
        self._repo.flush()
        return self._decision_view(decision, include_graph=True)

    def add_option(
        self,
        user_id: str,
        decision_id: str,
        request: DecisionOptionInput,
    ) -> DecisionView:
        decision = self._owned_decision(user_id, decision_id)
        self._add_option_row(
            user_id, decision, request, default_position=len(self._repo.list_options(decision_id))
        )
        decision.current_version += 1
        self._repo.flush()
        self._append_version(decision, "option_added")
        self._repo.flush()
        return self._decision_view(decision, include_graph=True)

    def compare_decision(self, user_id: str, decision_id: str) -> DecisionRecommendationView:
        decision = self._owned_decision(user_id, decision_id)
        options = self._repo.list_options(decision.decision_id)
        if not options:
            raise CareerDecisionValidationError("decision comparison requires at least one option")
        identity = self._identity_for_context(user_id)
        context = self._create_context_snapshot(user_id, identity)
        decision.current_context_snapshot_id = context.context_snapshot_id
        assessment = self._compare_options(decision, options, context)
        recommendation = DecisionRecommendation(
            recommendation_id=_new_id("decision_rec"),
            user_id=user_id,
            decision_id=decision.decision_id,
            context_snapshot_id=context.context_snapshot_id,
            recommended_option_id=assessment["recommended_option_id"],
            recommendation_status=assessment["recommendation_status"],
            evidence_sufficiency=assessment["evidence_sufficiency"],
            confidence=assessment["confidence"],
            summary=assessment["summary"],
            fit_payload=assessment["fit"],
            comparison_payload=assessment["comparison"],
            evidence_payload=assessment["evidence"],
            challenge_payload=assessment["challenges"],
            limitations=assessment["limitations"],
            generated_at=_now(),
        )
        self._repo.add(recommendation)
        self._repo.flush()
        decision.current_recommendation_id = recommendation.recommendation_id
        decision.status = DecisionStatus.EVALUATING.value
        decision.current_version += 1
        self._repo.flush()
        self._append_version(decision, "recommendation_generated")
        self._repo.flush()
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.RECOMMENDATION_GENERATED,
                event_source=ProductEventSource.BACKEND,
                decision_id=decision.decision_id,
                recommendation_id=recommendation.recommendation_id,
                career_identity_id=context.career_identity_id,
                career_identity_version=context.career_identity_version,
                confidence_bucket=recommendation.confidence,
                coverage_status=recommendation.evidence_sufficiency,
                recommendation_state=recommendation.recommendation_status,
                product_surface="decision_workspace",
                payload={
                    "recommended_option_present": recommendation.recommended_option_id is not None,
                    "option_count": len(options),
                },
            ),
        )
        return self._recommendation_view(recommendation)

    def select_option(
        self,
        user_id: str,
        decision_id: str,
        request: OptionSelectInput,
    ) -> DecisionView:
        decision = self._owned_decision(user_id, decision_id)
        option = self._owned_option(user_id, request.option_id)
        if option.decision_id != decision.decision_id:
            raise CrossUserAccessBlocked(user_id, option.user_id)
        for row in self._repo.list_options(decision.decision_id):
            row.status = (
                DecisionOptionStatus.SELECTED.value
                if row.option_id == option.option_id
                else DecisionOptionStatus.REJECTED.value
            )
        decision.selected_option_id = option.option_id
        decision.status = DecisionStatus.DECIDED.value
        decision.decision_date = _now()
        decision.current_version += 1
        self._repo.flush()
        self._append_version(decision, "option_selected", user_note=request.user_note)
        self._repo.flush()
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.DECISION_SAVED,
                event_source=ProductEventSource.BACKEND,
                decision_id=decision.decision_id,
                recommendation_id=decision.current_recommendation_id,
                product_surface="decision_workspace",
                payload={"selected_option_id": decision.selected_option_id},
            ),
        )
        return self._decision_view(decision, include_graph=True)

    def reopen_decision(
        self, user_id: str, decision_id: str, *, user_note: str | None = None
    ) -> DecisionView:
        decision = self._owned_decision(user_id, decision_id)
        decision.status = DecisionStatus.RECONSIDERING.value
        decision.current_version += 1
        self._repo.flush()
        self._append_version(decision, "reopened", user_note=user_note)
        self._repo.flush()
        return self._decision_view(decision, include_graph=True)

    def journal(self, user_id: str, decision_id: str) -> tuple[DecisionVersionView, ...]:
        decision = self._owned_decision(user_id, decision_id)
        return tuple(
            self._version_view(row) for row in self._repo.list_versions(decision.decision_id)
        )

    def create_action_plan(
        self,
        user_id: str,
        decision_id: str,
        request: ActionPlanCreateInput,
    ) -> ActionPlanView:
        decision = self._owned_decision(user_id, decision_id)
        if decision.selected_option_id is not None:
            self._ensure_option_belongs_to_decision(
                user_id, decision.selected_option_id, decision.decision_id
            )
        actions = request.actions or _default_actions_for_decision(decision)
        for action_input in actions:
            if action_input.option_id is not None:
                self._ensure_option_belongs_to_decision(
                    user_id, action_input.option_id, decision.decision_id
                )
        plan = CareerActionPlan(
            action_plan_id=_new_id("action_plan"),
            user_id=user_id,
            decision_id=decision.decision_id,
            selected_option_id=decision.selected_option_id,
            title=request.title or f"{decision.title} action plan",
            status="active",
            plan_payload={
                "basis": "decision_selection" if decision.selected_option_id else "decision",
                "decision_version": decision.current_version,
                "recommendation_id": decision.current_recommendation_id,
            },
        )
        self._repo.add(plan)
        self._repo.flush()
        for index, action_input in enumerate(actions):
            self._add_action_row(user_id, decision, plan, action_input, default_position=index)
        self._repo.flush()
        self._append_version(decision, "action_plan_created")
        self._repo.flush()
        for action in self._repo.list_actions_for_plan(plan.action_plan_id):
            self._record_event(
                user_id,
                ProductEventCreate(
                    event_type=ProductEventType.ACTION_CREATED,
                    event_source=ProductEventSource.BACKEND,
                    decision_id=decision.decision_id,
                    recommendation_id=decision.current_recommendation_id,
                    action_id=action.action_id,
                    product_surface="decision_workspace",
                    payload={"action_type": action.action_type},
                ),
            )
        return self._action_plan_view(plan)

    def list_actions(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> tuple[CareerActionView, ...]:
        self._ensure_user(user_id)
        if decision_id is not None:
            self._owned_decision(user_id, decision_id)
        return tuple(
            self._action_view(row)
            for row in self._repo.list_actions(user_id, decision_id=decision_id, limit=limit)
        )

    def update_action(
        self,
        user_id: str,
        action_id: str,
        request: CareerActionUpdateInput,
    ) -> CareerActionView:
        action = self._owned_action(user_id, action_id)
        if request.status is not None:
            action.status = request.status.value
            action.completed_at = (
                _now() if request.status is CareerActionStatus.COMPLETED else action.completed_at
            )
        for field in ("title", "description", "due_at", "priority"):
            value = getattr(request, field)
            if value is not None:
                setattr(action, field, value)
        if request.metadata is not None:
            action.metadata_json = deepcopy(request.metadata)
        self._repo.flush()
        if request.status is not None:
            event_type = (
                ProductEventType.ACTION_SUCCEEDED
                if request.status is CareerActionStatus.COMPLETED
                else ProductEventType.USER_ACTED
            )
            self._record_event(
                user_id,
                ProductEventCreate(
                    event_type=event_type,
                    event_source=ProductEventSource.BACKEND,
                    decision_id=action.decision_id,
                    action_id=action.action_id,
                    product_surface="decision_workspace",
                    payload={"action_type": action.action_type, "status": action.status},
                ),
            )
        return self._action_view(action)

    def create_application(
        self,
        user_id: str,
        request: ApplicationCreateInput,
    ) -> ApplicationView:
        self._ensure_user(user_id)
        self._validate_lifecycle_links(
            user_id,
            decision_id=request.decision_id,
            action_id=request.action_id,
            option_id=request.option_id,
        )
        canonical_region_id = None
        if request.region_id is not None:
            resolution = GeographicResolver(self._region_repo).resolve(request.region_id)
            if not resolution.resolved:
                raise CareerDecisionValidationError(
                    f"application region does not resolve canonically: {request.region_id!r}",
                    code="APPLICATION_REGION_UNRESOLVED",
                )
            canonical_region_id = resolution.region_id
        application = CareerApplication(
            application_id=_new_id("application"),
            user_id=user_id,
            decision_id=request.decision_id,
            action_id=request.action_id,
            option_id=request.option_id,
            company_id=request.company_id,
            region_id=canonical_region_id,
            role_title=request.role_title,
            status=request.status.value,
            status_started_at=_now(),
            applied_at=request.applied_at
            or (
                _now()
                if request.status.value
                in {
                    "applied",
                    "response",
                    "interview",
                    "final_round",
                    "offer",
                    "accepted",
                    "declined",
                    "rejected",
                }
                else None
            ),
            follow_up_at=request.follow_up_at,
            source_url=request.source_url,
            notes=request.notes,
            metadata_json=deepcopy(request.metadata),
        )
        self._repo.add(application)
        self._repo.flush()
        self._record_transition(
            user_id=user_id,
            application=application,
            from_status=None,
            to_status=request.status.value,
            reason="initial_state",
            metadata={},
            transitioned_at=application.status_started_at,
        )
        self._repo.flush()
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.APPLICATION_RECORDED,
                event_source=ProductEventSource.BACKEND,
                decision_id=application.decision_id,
                action_id=application.action_id,
                application_id=application.application_id,
                product_surface="decision_workspace",
                payload={
                    "status": application.status,
                    "company_id_present": application.company_id is not None,
                    "region_id_present": application.region_id is not None,
                    "role_title_present": application.role_title is not None,
                },
            ),
        )
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.USER_ACTED,
                event_source=ProductEventSource.BACKEND,
                decision_id=application.decision_id,
                action_id=application.action_id,
                application_id=application.application_id,
                product_surface="decision_workspace",
                payload={"action_kind": "application", "status": application.status},
            ),
        )
        return self._application_view(application)

    def transition_application(
        self,
        user_id: str,
        application_id: str,
        request: ApplicationTransitionInput,
    ) -> ApplicationView:
        application = self._owned_application(user_id, application_id)
        to_status = request.to_status.value
        if application.status == to_status:
            return self._application_view(application)
        if application.status in TERMINAL_APPLICATION_STATUSES:
            raise CareerDecisionTransitionError("terminal application status cannot transition")
        if (application.status, to_status) not in LEGAL_APPLICATION_TRANSITIONS:
            raise CareerDecisionTransitionError(
                f"invalid application transition: {application.status} -> {to_status}"
            )
        transitioned_at = request.transitioned_at or _now()
        previous = application.status
        application.status = to_status
        application.status_started_at = transitioned_at
        if to_status == ApplicationStatus.APPLIED.value and application.applied_at is None:
            application.applied_at = transitioned_at
        if request.follow_up_at is not None:
            application.follow_up_at = request.follow_up_at
        self._record_transition(
            user_id=user_id,
            application=application,
            from_status=previous,
            to_status=to_status,
            reason=request.reason,
            metadata=request.metadata,
            transitioned_at=transitioned_at,
        )
        self._repo.flush()
        if to_status in {"interview", "final_round", "offer", "accepted"} and application.action_id:
            self._record_event(
                user_id,
                ProductEventCreate(
                    event_type=ProductEventType.ACTION_SUCCEEDED,
                    event_source=ProductEventSource.BACKEND,
                    decision_id=application.decision_id,
                    action_id=application.action_id,
                    application_id=application.application_id,
                    product_surface="decision_workspace",
                    payload={"application_status": to_status},
                ),
            )
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.OUTCOME_UPDATED,
                event_source=ProductEventSource.BACKEND,
                decision_id=application.decision_id,
                application_id=application.application_id,
                product_surface="decision_workspace",
                payload={"from_status": previous, "to_status": to_status},
            ),
        )
        return self._application_view(application)

    def create_outcome(self, user_id: str, request: OutcomeCreateInput) -> OutcomeView:
        self._ensure_user(user_id)
        resolved = self._validate_lifecycle_links(
            user_id,
            decision_id=request.decision_id,
            action_id=request.action_id,
            application_id=request.application_id,
            option_id=request.option_id,
            recommendation_id=request.recommendation_id,
        )
        outcome = CareerOutcome(
            outcome_id=_new_id("outcome"),
            user_id=user_id,
            decision_id=request.decision_id or resolved.get("decision_id"),
            action_id=request.action_id,
            application_id=request.application_id,
            option_id=request.option_id or resolved.get("option_id"),
            recommendation_id=request.recommendation_id or resolved.get("recommendation_id"),
            outcome_type=request.outcome_type.value,
            status=request.status.value,
            title=request.title,
            description=request.description,
            occurred_at=request.occurred_at or _now(),
            reflection=request.reflection,
            evidence_payload=deepcopy(request.evidence),
            metadata_json=deepcopy(request.metadata),
        )
        self._repo.add(outcome)
        self._repo.flush()
        if outcome.decision_id is not None:
            decision = self._owned_decision(user_id, outcome.decision_id)
            self._append_version(decision, "outcome_recorded", user_note=outcome.reflection)
            self._repo.flush()
        self._record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.OUTCOME_RECORDED,
                event_source=ProductEventSource.BACKEND,
                decision_id=outcome.decision_id,
                recommendation_id=outcome.recommendation_id,
                action_id=outcome.action_id,
                application_id=outcome.application_id,
                outcome_id=outcome.outcome_id,
                product_surface="decision_workspace",
                payload={"outcome_type": outcome.outcome_type, "status": outcome.status},
            ),
        )
        if outcome.outcome_type == OutcomeType.STRATEGY_CHANGE.value:
            self._record_event(
                user_id,
                ProductEventCreate(
                    event_type=ProductEventType.STRATEGY_CHANGED,
                    event_source=ProductEventSource.BACKEND,
                    decision_id=outcome.decision_id,
                    recommendation_id=outcome.recommendation_id,
                    outcome_id=outcome.outcome_id,
                    product_surface="decision_workspace",
                    payload={"source": "career_outcome"},
                ),
            )
        return self._outcome_view(outcome)

    def _record_event(self, user_id: str, request: ProductEventCreate) -> None:
        if self._measurement is not None:
            self._measurement.best_effort_record_event(user_id, request)

    def weekly_review(
        self,
        user_id: str,
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> WeeklyReviewView:
        self._ensure_user(user_id)
        end = window_end or _now()
        start = window_start or (end - timedelta(days=7))
        decisions = self._repo.list_decisions(user_id, limit=500)
        actions = self._repo.list_actions(user_id, limit=500)
        applications = self._repo.list_applications(user_id, limit=500)
        outcomes = self._repo.list_outcomes(user_id, since=start, until=end, limit=500)
        happened = [
            {
                "type": "outcome",
                "id": row.outcome_id,
                "title": row.title,
                "occurred_at": row.occurred_at.isoformat(),
            }
            for row in outcomes
        ]
        changed = [
            {
                "type": "application",
                "id": row.application_id,
                "status": row.status,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in applications
            if start <= _aware(row.updated_at) <= end
        ]
        worked = [
            {
                "type": "outcome",
                "id": row.outcome_id,
                "outcome_type": row.outcome_type,
                "title": row.title,
            }
            for row in outcomes
            if row.outcome_type
            in {
                "offer",
                "skill_development",
                "research_completed",
                "networking",
                "decision_completed",
            }
        ]
        did_not_work = [
            {
                "type": "outcome",
                "id": row.outcome_id,
                "outcome_type": row.outcome_type,
                "title": row.title,
            }
            for row in outcomes
            if row.outcome_type in {"rejection", "withdrawal"}
        ]
        stalled = _stalled_items(actions, applications, now=end)
        invalidated = _invalidated_assumptions(outcomes)
        reconsider = [
            {
                "type": "decision",
                "id": row.decision_id,
                "title": row.title,
                "reason": "planned_review_due",
            }
            for row in decisions
            if row.planned_review_at is not None
            and _aware(row.planned_review_at) <= end
            and row.status not in {"completed", "abandoned"}
        ]
        next_actions = [
            {
                "type": "action",
                "id": row.action_id,
                "title": row.title,
                "due_at": row.due_at.isoformat() if row.due_at else None,
            }
            for row in actions
            if row.status in {"open", "in_progress"}
        ][:25]
        reminders = _reminders(decisions, actions, applications, now=end)
        return WeeklyReviewView(
            window_start=start,
            window_end=end,
            happened=tuple(happened),
            changed=tuple(changed),
            worked=tuple(worked),
            did_not_work=tuple(did_not_work),
            stalled=tuple(stalled),
            invalidated_assumptions=tuple(invalidated),
            reconsider=tuple(reconsider),
            next_actions=tuple(next_actions),
            reminders=tuple(reminders),
        )

    def _create_context_snapshot(
        self,
        user_id: str,
        identity: CareerIdentity,
    ) -> DecisionContextSnapshot:
        if identity.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, identity.user_id)
        facts = self._identity_repo.list_facts(identity.career_identity_id)
        context_payload, fact_refs = _adapt_identity_context(identity, facts)
        row = DecisionContextSnapshot(
            context_snapshot_id=_new_id("decision_context"),
            user_id=user_id,
            career_identity_id=identity.career_identity_id,
            career_identity_version=identity.current_version,
            completeness_state=identity.completeness_state,
            sufficiency_state=identity.sufficiency_state,
            privacy_scope="owner_decision_only",
            context_payload=context_payload,
            fact_refs=fact_refs,
        )
        self._repo.add(row)
        self._repo.flush()
        return row

    def _identity_for_context(self, user_id: str) -> CareerIdentity:
        identity = self._identity_repo.get_identity_for_user(user_id)
        if identity is not None:
            return identity
        identity = CareerIdentity(
            career_identity_id=_new_id("career_identity"),
            user_id=user_id,
            current_version=1,
            completeness_state="empty",
            sufficiency_state="insufficient",
            privacy_visibility="private",
        )
        self._identity_repo.add_identity(identity)
        self._identity_repo.flush()
        return identity

    def _compare_options(
        self,
        decision: CareerDecision,
        options: list[DecisionOption],
        context: DecisionContextSnapshot,
    ) -> dict[str, Any]:
        context_payload = context.context_payload
        option_results = []
        all_evidence: list[dict[str, Any]] = []
        all_challenges: list[dict[str, Any]] = []
        limitations: list[str] = []
        for option in options:
            result = self._fit_option(decision, option, context_payload)
            option_results.append(result)
            all_evidence.extend(result["evidence"])
            all_challenges.extend(result["challenges"])
            limitations.extend(result["limitations"])
        ranked = sorted(
            option_results,
            key=lambda item: (-item["rank_value"], item["position"], item["option_id"]),
        )
        eligible = [
            item
            for item in ranked
            if not item["hard_violations"] and item["assessment"] != FitAssessment.ABSTAIN.value
        ]
        recommended = eligible[0] if eligible else None
        sufficiency = _overall_sufficiency(option_results, context_payload)
        abstain = recommended is None or sufficiency in {
            EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value,
            EvidenceSufficiency.NOT_SUPPORTED.value,
        }
        confidence = _overall_confidence(option_results, sufficiency)
        if abstain:
            recommended_option_id = None
            status = DecisionRecommendationStatus.ABSTAINED.value
            summary = (
                "Decision recommendation abstained because evidence is insufficient "
                "or all viable options violate hard constraints."
            )
            all_challenges.append(
                _challenge(
                    ChallengeCode.INSUFFICIENT_EVIDENCE,
                    severity="blocking",
                    message="No strong recommendation is produced from the available evidence.",
                    scope_type="decision",
                    scope_id=decision.decision_id,
                )
            )
        else:
            recommended_option_id = recommended["option_id"]
            status = DecisionRecommendationStatus.READY.value
            summary = f"{recommended['title']} is the best-supported option from current evidence."
        return {
            "recommended_option_id": recommended_option_id,
            "recommendation_status": status,
            "evidence_sufficiency": sufficiency,
            "confidence": confidence,
            "summary": summary,
            "fit": {"options": option_results},
            "comparison": {
                "ranked_option_ids": [item["option_id"] for item in ranked],
                "recommended_option_id": recommended_option_id,
                "abstained": abstain,
            },
            "evidence": {
                "supporting": [
                    item for item in all_evidence if item["kind"] in {"direct", "proxy"}
                ],
                "contrary": [
                    item for item in all_evidence if item["kind"] in {"contrary", "conflicting"}
                ],
                "unavailable": [
                    item for item in all_evidence if item["kind"] in {"unavailable", "weak"}
                ],
            },
            "challenges": _dedupe_challenges(all_challenges),
            "limitations": list(dict.fromkeys(limitations)),
        }

    def _fit_option(
        self,
        decision: CareerDecision,
        option: DecisionOption,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        scenario = option.scenario or {}
        evidence: list[dict[str, Any]] = []
        challenges: list[dict[str, Any]] = []
        limitations: list[str] = []
        dimensions = [
            self._role_fit(option, context, evidence, limitations),
            self._market_fit(option, evidence, limitations),
            self._company_fit(option, evidence, challenges, limitations),
            self._strategy_fit(option, context, evidence, limitations),
        ]
        constraints = _constraint_results(decision.constraints or [], scenario)
        hard_violations = [item for item in constraints if item["hard"] and not item["satisfied"]]
        for violation in hard_violations:
            code = (
                ChallengeCode.COMPENSATION_MINIMUM_VIOLATION
                if violation["field"] in {"compensation_min", "minimum_compensation", "salary_min"}
                else ChallengeCode.HARD_CONSTRAINT_VIOLATION
            )
            challenges.append(
                _challenge(
                    code,
                    severity="blocking",
                    message=f"Hard constraint not satisfied: {violation['key']}",
                    scope_type="option",
                    scope_id=option.option_id,
                    details=violation,
                )
            )
        if _identity_incomplete(context):
            challenges.append(
                _challenge(
                    ChallengeCode.INCOMPLETE_IDENTITY,
                    severity="warning",
                    message=(
                        "Career Identity is incomplete for a strong personalized "
                        "recommendation."
                    ),
                    scope_type="decision",
                    scope_id=decision.decision_id,
                )
            )
            limitations.append("Career Identity completeness limits recommendation strength.")
        if context.get("inferred_fact_count", 0) > context.get("confirmed_fact_count", 0):
            challenges.append(
                _challenge(
                    ChallengeCode.INFERRED_IDENTITY_DEPENDENCY,
                    severity="warning",
                    message="Recommendation depends materially on inferred Career Identity facts.",
                    scope_type="decision",
                    scope_id=decision.decision_id,
                )
            )
        assessment, rank_value = _assessment_from_dimensions(dimensions, hard_violations)
        return {
            "option_id": option.option_id,
            "title": option.title,
            "position": option.position,
            "assessment": assessment,
            "rank_value": rank_value,
            "dimensions": [asdict(dimension) for dimension in dimensions],
            "constraints": constraints,
            "hard_violations": hard_violations,
            "advantages": _advantages(dimensions, constraints),
            "disadvantages": _disadvantages(dimensions, constraints),
            "tradeoffs": _tradeoffs(dimensions, constraints),
            "important_unknowns": [
                item for item in evidence if item["kind"] in {"unavailable", "weak"}
            ],
            "evidence": evidence,
            "challenges": challenges,
            "limitations": limitations,
        }

    def _role_fit(
        self,
        option: DecisionOption,
        context: dict[str, Any],
        evidence: list[dict[str, Any]],
        limitations: list[str],
    ) -> FitDimension:
        roles = _tokens(
            option.scenario.get("roles")
            or option.scenario.get("role_titles")
            or option.scenario.get("role")
        )
        preferred = _tokens(context.get("role_preferences"))
        skills = _tokens(context.get("skills"))
        if not roles:
            evidence.append(
                _evidence(
                    EvidenceKind.UNAVAILABLE, "role", option.option_id, "Option has no role signal."
                )
            )
            return FitDimension(
                "role_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
            )
        if preferred and roles & preferred:
            ref = _evidence(
                EvidenceKind.DIRECT,
                "role",
                option.option_id,
                "Option matches confirmed or explicit role preferences.",
            )
            evidence.append(ref)
            return FitDimension(
                "role_fit", FitAssessment.STRONG.value, EvidenceKind.DIRECT.value, (ref,)
            )
        if skills:
            ref = _evidence(
                EvidenceKind.PROXY,
                "role",
                option.option_id,
                "Skills provide proxy role-fit evidence.",
            )
            evidence.append(ref)
            limitations.append(
                "Role fit uses skills as proxy evidence where no role preference matches directly."
            )
            return FitDimension(
                "role_fit", FitAssessment.MODERATE.value, EvidenceKind.PROXY.value, (ref,)
            )
        evidence.append(
            _evidence(
                EvidenceKind.UNAVAILABLE,
                "role",
                option.option_id,
                "No role preference or skill evidence is available.",
            )
        )
        return FitDimension(
            "role_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
        )

    def _market_fit(
        self,
        option: DecisionOption,
        evidence: list[dict[str, Any]],
        limitations: list[str],
    ) -> FitDimension:
        region_ids = _string_values(
            option.scenario.get("region_ids")
            or option.scenario.get("regions")
            or option.scenario.get("location")
        )
        if not region_ids:
            evidence.append(
                _evidence(
                    EvidenceKind.UNAVAILABLE,
                    "market",
                    option.option_id,
                    "Option has no region signal.",
                )
            )
            return FitDimension(
                "market_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
            )
        score_values = []
        refs = []
        resolver = GeographicResolver(self._region_repo)
        for legacy_region_ref in region_ids:
            resolution = resolver.resolve(legacy_region_ref)
            if not resolution.resolved or resolution.region_id is None:
                limitations.append(
                    f"Market reference {legacy_region_ref!r} is {resolution.status}; "
                    "it was not mapped to canonical geography."
                )
                evidence.append(
                    _evidence(
                        EvidenceKind.UNAVAILABLE,
                        "region",
                        legacy_region_ref,
                        "Region reference did not resolve to canonical geography.",
                    )
                )
                continue
            region_id = resolution.region_id
            score = self._score_repo.get_score_by_region(region_id)
            if score is not None and score.objective_opportunity_score is not None:
                score_values.append(score.objective_opportunity_score)
                ref = _evidence(
                    EvidenceKind.DIRECT,
                    "region_market_score",
                    region_id,
                    "Region market score is available.",
                )
                evidence.append(ref)
                refs.append(ref)
            elif self._region_repo.exists(region_id):
                ref = _evidence(
                    EvidenceKind.PROXY,
                    "region",
                    region_id,
                    "Region exists, but market score is unavailable.",
                )
                evidence.append(ref)
                refs.append(ref)
                limitations.append(f"Market fit for {region_id} lacks an objective score.")
            else:
                evidence.append(
                    _evidence(
                        EvidenceKind.UNAVAILABLE,
                        "region",
                        region_id,
                        "Region is not known to canonical geography.",
                    )
                )
        if score_values:
            avg = sum(score_values) / len(score_values)
            assessment = (
                FitAssessment.STRONG
                if avg >= 0.75
                else FitAssessment.MODERATE
                if avg >= 0.50
                else FitAssessment.WEAK
            )
            return FitDimension(
                "market_fit", assessment.value, EvidenceKind.DIRECT.value, tuple(refs)
            )
        if refs:
            return FitDimension(
                "market_fit", FitAssessment.WEAK.value, EvidenceKind.PROXY.value, tuple(refs)
            )
        return FitDimension(
            "market_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
        )

    def _company_fit(
        self,
        option: DecisionOption,
        evidence: list[dict[str, Any]],
        challenges: list[dict[str, Any]],
        limitations: list[str],
    ) -> FitDimension:
        company_ids = _string_values(
            option.scenario.get("company_ids")
            or option.scenario.get("companies")
            or option.scenario.get("company_id")
        )
        if not company_ids:
            return FitDimension(
                "company_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
            )
        refs = []
        missing = []
        for company_id in company_ids:
            company = self._company_repo.get(company_id)
            if company is None:
                missing.append(company_id)
                evidence.append(
                    _evidence(
                        EvidenceKind.UNAVAILABLE,
                        "company",
                        company_id,
                        "Company evidence is unavailable.",
                    )
                )
                continue
            ref = _evidence(
                EvidenceKind.DIRECT,
                "company",
                company_id,
                "Canonical company metadata is available.",
            )
            refs.append(ref)
            evidence.append(ref)
            if company.classification_confidence in {None, "unknown"}:
                limitations.append(f"Company-specific confidence is weak for {company_id}.")
                challenges.append(
                    _challenge(
                        ChallengeCode.WEAK_COMPANY_EVIDENCE,
                        severity="warning",
                        message="Company-specific evidence is weak or missing.",
                        scope_type="company",
                        scope_id=company_id,
                    )
                )
        if refs and not missing:
            return FitDimension(
                "company_fit", FitAssessment.MODERATE.value, EvidenceKind.DIRECT.value, tuple(refs)
            )
        if refs:
            return FitDimension(
                "company_fit", FitAssessment.WEAK.value, EvidenceKind.DIRECT.value, tuple(refs)
            )
        return FitDimension(
            "company_fit", FitAssessment.UNKNOWN.value, EvidenceKind.UNAVAILABLE.value, ()
        )

    def _strategy_fit(
        self,
        option: DecisionOption,
        context: dict[str, Any],
        evidence: list[dict[str, Any]],
        limitations: list[str],
    ) -> FitDimension:
        option_industries = _tokens(
            option.scenario.get("industries") or option.scenario.get("industry")
        )
        context_industries = _tokens(context.get("industries"))
        work = _tokens(option.scenario.get("work_arrangement"))
        preferred_work = _tokens(context.get("work_arrangements"))
        if option_industries and context_industries and option_industries & context_industries:
            ref = _evidence(
                EvidenceKind.DIRECT,
                "strategy",
                option.option_id,
                "Industry preference aligns with the option.",
            )
            evidence.append(ref)
            return FitDimension(
                "strategy_fit", FitAssessment.STRONG.value, EvidenceKind.DIRECT.value, (ref,)
            )
        if work and preferred_work and work & preferred_work:
            ref = _evidence(
                EvidenceKind.DIRECT,
                "strategy",
                option.option_id,
                "Work arrangement aligns with Career Identity.",
            )
            evidence.append(ref)
            return FitDimension(
                "strategy_fit", FitAssessment.MODERATE.value, EvidenceKind.DIRECT.value, (ref,)
            )
        limitations.append("Strategy fit has limited direct preference evidence.")
        evidence.append(
            _evidence(
                EvidenceKind.WEAK,
                "strategy",
                option.option_id,
                "Strategy evidence is weak or unavailable.",
            )
        )
        return FitDimension(
            "strategy_fit", FitAssessment.UNKNOWN.value, EvidenceKind.WEAK.value, ()
        )

    def _add_option_row(
        self,
        user_id: str,
        decision: CareerDecision,
        request: DecisionOptionInput,
        *,
        default_position: int,
    ) -> DecisionOption:
        scenario = deepcopy(request.scenario)
        if "region_ids" in scenario:
            raw_region_ids = _as_list(scenario["region_ids"])
            canonical_region_ids: list[str] = []
            resolver = GeographicResolver(self._region_repo)
            for raw_region_id in raw_region_ids:
                resolution = resolver.resolve(raw_region_id)
                if not resolution.resolved or resolution.region_id is None:
                    raise CareerDecisionValidationError(
                        f"decision region does not resolve canonically: {raw_region_id!r}",
                        code="DECISION_REGION_UNRESOLVED",
                    )
                if resolution.region_id not in canonical_region_ids:
                    canonical_region_ids.append(resolution.region_id)
            scenario["region_ids"] = canonical_region_ids
        option = DecisionOption(
            option_id=_new_id("decision_option"),
            user_id=user_id,
            decision_id=decision.decision_id,
            title=request.title,
            description=request.description,
            scenario=scenario,
            status=DecisionOptionStatus.ACTIVE.value,
            position=request.position if request.position != 0 else default_position,
        )
        self._repo.add(option)
        return option

    def _add_action_row(
        self,
        user_id: str,
        decision: CareerDecision,
        plan: CareerActionPlan,
        request: CareerActionInput,
        *,
        default_position: int,
    ) -> CareerAction:
        if request.option_id is not None:
            self._ensure_option_belongs_to_decision(
                user_id, request.option_id, decision.decision_id
            )
        action = CareerAction(
            action_id=_new_id("career_action"),
            user_id=user_id,
            action_plan_id=plan.action_plan_id,
            decision_id=decision.decision_id,
            option_id=request.option_id,
            action_type=request.action_type.value,
            status=CareerActionStatus.OPEN.value,
            title=request.title,
            description=request.description,
            due_at=request.due_at,
            priority=request.priority,
            position=request.position if request.position != 0 else default_position,
            metadata_json=deepcopy(request.metadata),
        )
        self._repo.add(action)
        return action

    def _append_version(
        self,
        decision: CareerDecision,
        version_reason: str,
        *,
        user_note: str | None = None,
    ) -> DecisionVersion:
        recommendation = (
            self._repo.get_recommendation(decision.current_recommendation_id)
            if decision.current_recommendation_id
            else None
        )
        row = DecisionVersion(
            decision_version_id=_new_id("decision_version"),
            user_id=decision.user_id,
            decision_id=decision.decision_id,
            version_number=self._repo.latest_version_number(decision.decision_id) + 1,
            version_reason=version_reason,
            decision_snapshot=_decision_snapshot(decision),
            options_snapshot=[
                _option_snapshot(option) for option in self._repo.list_options(decision.decision_id)
            ],
            recommendation_snapshot=_recommendation_snapshot(recommendation)
            if recommendation
            else None,
            selected_option_id=decision.selected_option_id,
            context_snapshot_id=decision.current_context_snapshot_id,
            user_note=user_note,
        )
        self._repo.add(row)
        return row

    def _record_transition(
        self,
        *,
        user_id: str,
        application: CareerApplication,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        metadata: dict[str, Any],
        transitioned_at: datetime,
    ) -> CareerApplicationTransition:
        row = CareerApplicationTransition(
            transition_id=_new_id("application_transition"),
            user_id=user_id,
            application_id=application.application_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            metadata_json=deepcopy(metadata),
            transitioned_at=transitioned_at,
        )
        self._repo.add(row)
        return row

    def _owned_decision(self, user_id: str, decision_id: str) -> CareerDecision:
        decision = self._repo.get_decision(decision_id)
        if decision is None:
            raise CareerDecisionNotFound(decision_id)
        if decision.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, decision.user_id)
        return decision

    def _owned_option(self, user_id: str, option_id: str) -> DecisionOption:
        option = self._repo.get_option(option_id)
        if option is None:
            raise CareerDecisionNotFound(option_id)
        if option.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, option.user_id)
        return option

    def _owned_action(self, user_id: str, action_id: str) -> CareerAction:
        action = self._repo.get_action(action_id)
        if action is None:
            raise CareerDecisionNotFound(action_id)
        if action.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, action.user_id)
        return action

    def _owned_application(self, user_id: str, application_id: str) -> CareerApplication:
        application = self._repo.get_application(application_id)
        if application is None:
            raise CareerDecisionNotFound(application_id)
        if application.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, application.user_id)
        return application

    def _ensure_option_belongs_to_decision(
        self,
        user_id: str,
        option_id: str,
        decision_id: str,
    ) -> None:
        option = self._owned_option(user_id, option_id)
        if option.decision_id != decision_id:
            raise CrossUserAccessBlocked(user_id, option.user_id)

    def _validate_lifecycle_links(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        action_id: str | None = None,
        application_id: str | None = None,
        option_id: str | None = None,
        recommendation_id: str | None = None,
    ) -> dict[str, str | None]:
        resolved: dict[str, str | None] = {"decision_id": decision_id, "option_id": option_id}
        if decision_id is not None:
            self._owned_decision(user_id, decision_id)
        if action_id is not None:
            action = self._owned_action(user_id, action_id)
            resolved["decision_id"] = resolved["decision_id"] or action.decision_id
            resolved["option_id"] = resolved["option_id"] or action.option_id
        if application_id is not None:
            application = self._owned_application(user_id, application_id)
            resolved["decision_id"] = resolved["decision_id"] or application.decision_id
            resolved["option_id"] = resolved["option_id"] or application.option_id
        if option_id is not None:
            option = self._owned_option(user_id, option_id)
            linked_decision = resolved.get("decision_id")
            if linked_decision is not None and option.decision_id != linked_decision:
                raise CrossUserAccessBlocked(user_id, option.user_id)
            resolved["decision_id"] = resolved["decision_id"] or option.decision_id
        if recommendation_id is not None:
            rec = self._repo.get_recommendation(recommendation_id)
            if rec is None:
                raise CareerDecisionNotFound(recommendation_id)
            if rec.user_id != user_id:
                raise CrossUserAccessBlocked(user_id, rec.user_id)
            linked_decision = resolved.get("decision_id")
            if linked_decision is not None and rec.decision_id != linked_decision:
                raise CrossUserAccessBlocked(user_id, rec.user_id)
            resolved["decision_id"] = resolved["decision_id"] or rec.decision_id
            resolved["recommendation_id"] = rec.recommendation_id
        return resolved

    def _ensure_user(self, user_id: str) -> None:
        if self._user_repo.get_user(user_id) is None:
            raise UserNotFound(user_id)

    def _decision_view(self, decision: CareerDecision, *, include_graph: bool) -> DecisionView:
        context = (
            self._repo.get_context(decision.current_context_snapshot_id)
            if decision.current_context_snapshot_id
            else None
        )
        recommendation = (
            self._repo.get_recommendation(decision.current_recommendation_id)
            if decision.current_recommendation_id
            else None
        )
        plan = (
            self._repo.get_action_plan_for_decision(decision.decision_id) if include_graph else None
        )
        applications = (
            self._repo.list_applications(decision.user_id, decision_id=decision.decision_id)
            if include_graph
            else []
        )
        outcomes = (
            self._repo.list_outcomes(decision.user_id, decision_id=decision.decision_id)
            if include_graph
            else []
        )
        return DecisionView(
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            status=decision.status,
            title=decision.title,
            description=decision.description,
            decision_date=decision.decision_date,
            target_date=decision.target_date,
            planned_review_at=decision.planned_review_at,
            time_horizon=decision.time_horizon,
            priorities=tuple(decision.priorities or []),
            constraints=tuple(decision.constraints or []),
            selected_option_id=decision.selected_option_id,
            career_identity_id=decision.career_identity_id,
            current_context_snapshot_id=decision.current_context_snapshot_id,
            current_recommendation_id=decision.current_recommendation_id,
            current_version=decision.current_version,
            context=self._context_view(context) if context else None,
            options=tuple(
                self._option_view(row) for row in self._repo.list_options(decision.decision_id)
            ),
            recommendation=self._recommendation_view(recommendation) if recommendation else None,
            action_plan=self._action_plan_view(plan) if plan else None,
            applications=tuple(self._application_view(row) for row in applications),
            outcomes=tuple(self._outcome_view(row) for row in outcomes),
            created_at=decision.created_at,
            updated_at=decision.updated_at,
        )

    def _context_view(self, row: DecisionContextSnapshot) -> DecisionContextView:
        return DecisionContextView(
            context_snapshot_id=row.context_snapshot_id,
            career_identity_id=row.career_identity_id,
            career_identity_version=row.career_identity_version,
            completeness_state=row.completeness_state,
            sufficiency_state=row.sufficiency_state,
            privacy_scope=row.privacy_scope,
            context=deepcopy(row.context_payload),
            fact_refs=tuple(deepcopy(row.fact_refs or [])),
            created_at=row.created_at,
        )

    def _option_view(self, row: DecisionOption) -> DecisionOptionView:
        return DecisionOptionView(
            option_id=row.option_id,
            decision_id=row.decision_id,
            title=row.title,
            description=row.description,
            scenario=deepcopy(row.scenario),
            status=row.status,
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _recommendation_view(self, row: DecisionRecommendation) -> DecisionRecommendationView:
        return DecisionRecommendationView(
            recommendation_id=row.recommendation_id,
            decision_id=row.decision_id,
            context_snapshot_id=row.context_snapshot_id,
            recommended_option_id=row.recommended_option_id,
            recommendation_status=row.recommendation_status,
            evidence_sufficiency=row.evidence_sufficiency,
            confidence=row.confidence,
            summary=row.summary,
            fit=deepcopy(row.fit_payload),
            comparison=deepcopy(row.comparison_payload),
            evidence=deepcopy(row.evidence_payload),
            challenges=tuple(deepcopy(row.challenge_payload or [])),
            limitations=tuple(row.limitations or []),
            generated_at=row.generated_at,
        )

    def _version_view(self, row: DecisionVersion) -> DecisionVersionView:
        return DecisionVersionView(
            decision_version_id=row.decision_version_id,
            version_number=row.version_number,
            version_reason=row.version_reason,
            selected_option_id=row.selected_option_id,
            context_snapshot_id=row.context_snapshot_id,
            decision_snapshot=deepcopy(row.decision_snapshot),
            options_snapshot=tuple(deepcopy(row.options_snapshot or [])),
            recommendation_snapshot=deepcopy(row.recommendation_snapshot),
            user_note=row.user_note,
            created_at=row.created_at,
        )

    def _action_plan_view(self, row: CareerActionPlan) -> ActionPlanView:
        return ActionPlanView(
            action_plan_id=row.action_plan_id,
            decision_id=row.decision_id,
            selected_option_id=row.selected_option_id,
            title=row.title,
            status=row.status,
            plan=deepcopy(row.plan_payload),
            actions=tuple(
                self._action_view(action)
                for action in self._repo.list_actions_for_plan(row.action_plan_id)
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _action_view(self, row: CareerAction) -> CareerActionView:
        return CareerActionView(
            action_id=row.action_id,
            action_plan_id=row.action_plan_id,
            decision_id=row.decision_id,
            option_id=row.option_id,
            action_type=row.action_type,
            status=row.status,
            title=row.title,
            description=row.description,
            due_at=row.due_at,
            priority=row.priority,
            position=row.position,
            completed_at=row.completed_at,
            metadata=deepcopy(row.metadata_json),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _application_view(self, row: CareerApplication) -> ApplicationView:
        return ApplicationView(
            application_id=row.application_id,
            decision_id=row.decision_id,
            action_id=row.action_id,
            option_id=row.option_id,
            company_id=row.company_id,
            region_id=row.region_id,
            role_title=row.role_title,
            status=row.status,
            status_started_at=row.status_started_at,
            applied_at=row.applied_at,
            follow_up_at=row.follow_up_at,
            source_url=row.source_url,
            notes=row.notes,
            metadata=deepcopy(row.metadata_json),
            transitions=tuple(
                self._transition_view(item)
                for item in self._repo.list_transitions(row.application_id)
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _transition_view(self, row: CareerApplicationTransition) -> ApplicationTransitionView:
        return ApplicationTransitionView(
            transition_id=row.transition_id,
            application_id=row.application_id,
            from_status=row.from_status,
            to_status=row.to_status,
            reason=row.reason,
            metadata=deepcopy(row.metadata_json),
            transitioned_at=row.transitioned_at,
        )

    def _outcome_view(self, row: CareerOutcome) -> OutcomeView:
        return OutcomeView(
            outcome_id=row.outcome_id,
            decision_id=row.decision_id,
            action_id=row.action_id,
            application_id=row.application_id,
            option_id=row.option_id,
            recommendation_id=row.recommendation_id,
            outcome_type=row.outcome_type,
            status=row.status,
            title=row.title,
            description=row.description,
            occurred_at=row.occurred_at,
            reflection=row.reflection,
            evidence=deepcopy(row.evidence_payload),
            metadata=deepcopy(row.metadata_json),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _adapt_identity_context(
    identity: CareerIdentity,
    facts: list[CareerIdentityFact],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not identity.downstream_personalization_consent_granted:
        return (
            {
                "consent": {
                    "usable": False,
                    "reason": "downstream_personalization_consent_not_granted",
                },
                "completeness_state": identity.completeness_state,
                "sufficiency_state": identity.sufficiency_state,
            },
            [],
        )
    grouped: dict[str, list[dict[str, Any]]] = {}
    fact_refs: list[dict[str, Any]] = []
    for fact in facts:
        grouped.setdefault(fact.fact_type, []).append(
            {
                "fact_id": fact.career_identity_fact_id,
                "state": fact.state,
                "payload": deepcopy(fact.payload),
                "provenance": _safe_provenance(fact.provenance),
            }
        )
        fact_refs.append(
            {
                "fact_id": fact.career_identity_fact_id,
                "fact_type": fact.fact_type,
                "state": fact.state,
                "normalized_key": fact.normalized_key,
            }
        )
    payload = {
        "consent": {"usable": True},
        "career_identity_version": identity.current_version,
        "completeness_state": identity.completeness_state,
        "sufficiency_state": identity.sufficiency_state,
        "skills": [_payload_value(item, "name") for item in grouped.get("skill", [])],
        "experience": [item["payload"] for item in grouped.get("experience", [])],
        "education": [item["payload"] for item in grouped.get("education", [])],
        "projects": [item["payload"] for item in grouped.get("project", [])],
        "credentials": [item["payload"] for item in grouped.get("credential", [])],
        "goals": [item["payload"] for item in grouped.get("career_goal", [])],
        "role_preferences": [
            _first_present(
                item["payload"], "role_title", "function", "seniority", "employment_type"
            )
            for item in grouped.get("role_preference", [])
            if item["payload"].get("preference_kind") != "excluded"
        ],
        "excluded_roles": [
            _first_present(
                item["payload"], "role_title", "function", "seniority", "employment_type"
            )
            for item in grouped.get("role_preference", [])
            if item["payload"].get("preference_kind") == "excluded"
        ],
        "industries": [
            _payload_value(item, "industry") for item in grouped.get("industry_preference", [])
        ],
        "geography": [item["payload"] for item in grouped.get("geographic_constraint", [])],
        "work_arrangements": [
            _payload_value(item, "arrangement")
            for item in grouped.get("work_arrangement_preference", [])
        ],
        "compensation_constraints": [
            item["payload"] for item in grouped.get("compensation_constraint", [])
        ],
        "timing": [item["payload"] for item in grouped.get("timing_preference", [])],
        "confirmed_fact_count": sum(1 for fact in facts if fact.state == "confirmed"),
        "inferred_fact_count": sum(1 for fact in facts if fact.state == "inferred"),
    }
    return payload, fact_refs


def _constraint_results(
    constraints: list[dict[str, Any]], scenario: dict[str, Any]
) -> list[dict[str, Any]]:
    results = []
    for constraint in constraints:
        field = constraint.get("field")
        operator = constraint.get("operator", "equals")
        expected = constraint.get("value")
        actual = _scenario_value(scenario, str(field))
        satisfied = _constraint_satisfied(actual, operator, expected)
        results.append(
            {
                "key": constraint.get("key"),
                "field": field,
                "operator": operator,
                "expected": expected,
                "actual": actual,
                "hard": bool(constraint.get("hard", True)),
                "satisfied": satisfied,
            }
        )
    return results


def _constraint_satisfied(actual: Any, operator: str, expected: Any) -> bool:
    if operator in {"equals", "eq"}:
        return _normalize_scalar(actual) == _normalize_scalar(expected)
    if operator in {"in", "one_of"}:
        actual_values = {_normalize_scalar(item) for item in _as_list(actual)}
        expected_values = {_normalize_scalar(item) for item in _as_list(expected)}
        return bool(actual_values & expected_values)
    if operator in {"gte", ">="}:
        return (
            _number(actual) is not None
            and _number(expected) is not None
            and _number(actual) >= _number(expected)
        )
    if operator in {"lte", "<="}:
        return (
            _number(actual) is not None
            and _number(expected) is not None
            and _number(actual) <= _number(expected)
        )
    return False


def _scenario_value(scenario: dict[str, Any], field: str) -> Any:
    aliases = {
        "compensation_min": (
            "compensation_min",
            "salary_min",
            "target_salary_min",
            "minimum_compensation",
        ),
        "minimum_compensation": (
            "minimum_compensation",
            "compensation_min",
            "salary_min",
            "target_salary_min",
        ),
        "work_arrangement": ("work_arrangement", "arrangement"),
        "location": ("location", "regions", "region_ids"),
    }
    for key in aliases.get(field, (field,)):
        if key in scenario:
            return scenario[key]
    return None


def _assessment_from_dimensions(
    dimensions: list[FitDimension],
    hard_violations: list[dict[str, Any]],
) -> tuple[str, int]:
    if hard_violations:
        return FitAssessment.MISALIGNED.value, 0
    value = 0
    order = {
        FitAssessment.STRONG.value: 4,
        FitAssessment.MODERATE.value: 3,
        FitAssessment.WEAK.value: 2,
        FitAssessment.UNKNOWN.value: 1,
        FitAssessment.ABSTAIN.value: 0,
        FitAssessment.MISALIGNED.value: 0,
    }
    for dimension in dimensions:
        value += order[dimension.assessment]
    if value <= 3:
        return FitAssessment.ABSTAIN.value, value
    if value >= 11:
        return FitAssessment.STRONG.value, value
    if value >= 8:
        return FitAssessment.MODERATE.value, value
    return FitAssessment.WEAK.value, value


def _overall_sufficiency(results: list[dict[str, Any]], context: dict[str, Any]) -> str:
    if not context.get("consent", {}).get("usable", False):
        return EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value
    if all(item["assessment"] == FitAssessment.ABSTAIN.value for item in results):
        return EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value
    if any(item["hard_violations"] for item in results):
        return EvidenceSufficiency.LIMITED_EVIDENCE.value
    if any(item["important_unknowns"] for item in results) or _identity_incomplete(context):
        return EvidenceSufficiency.LIMITED_EVIDENCE.value
    return EvidenceSufficiency.COMPARISON_READY.value


def _overall_confidence(results: list[dict[str, Any]], sufficiency: str) -> str:
    if sufficiency == EvidenceSufficiency.COMPARISON_READY.value:
        return ConfidenceLevel.MEDIUM.value
    if sufficiency == EvidenceSufficiency.LIMITED_EVIDENCE.value:
        return ConfidenceLevel.LOW.value
    if any(item["evidence"] for item in results):
        return ConfidenceLevel.LOW.value
    return ConfidenceLevel.UNKNOWN.value


def _identity_incomplete(context: dict[str, Any]) -> bool:
    return (
        context.get("completeness_state") in {None, "empty", "minimal"}
        or context.get("sufficiency_state") == "insufficient"
    )


def _advantages(
    dimensions: list[FitDimension], constraints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    items = [
        {"code": f"{dimension.name}_supported", "detail": dimension.name}
        for dimension in dimensions
        if dimension.assessment in {FitAssessment.STRONG.value, FitAssessment.MODERATE.value}
    ]
    items.extend(
        {"code": "constraint_satisfied", "detail": item["key"]}
        for item in constraints
        if item["satisfied"]
    )
    return items


def _disadvantages(
    dimensions: list[FitDimension], constraints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    items = [
        {"code": f"{dimension.name}_weak", "detail": dimension.name}
        for dimension in dimensions
        if dimension.assessment in {FitAssessment.WEAK.value, FitAssessment.UNKNOWN.value}
    ]
    items.extend(
        {"code": "constraint_violated", "detail": item["key"]}
        for item in constraints
        if not item["satisfied"]
    )
    return items


def _tradeoffs(
    dimensions: list[FitDimension], constraints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    has_direct = any(d.evidence_kind == EvidenceKind.DIRECT.value for d in dimensions)
    has_unknown = any(
        d.evidence_kind in {EvidenceKind.UNAVAILABLE.value, EvidenceKind.WEAK.value}
        for d in dimensions
    )
    tradeoffs = []
    if has_direct and has_unknown:
        tradeoffs.append(
            {
                "code": "supported_dimensions_with_unknowns",
                "detail": "Some fit dimensions are supported while others remain unknown.",
            }
        )
    if any(not item["satisfied"] and not item["hard"] for item in constraints):
        tradeoffs.append(
            {
                "code": "soft_constraint_tradeoff",
                "detail": "One or more soft constraints are not satisfied.",
            }
        )
    return tradeoffs


def _default_actions_for_decision(decision: CareerDecision) -> tuple[CareerActionInput, ...]:
    option_id = decision.selected_option_id
    return (
        CareerActionInput(
            action_type=CareerActionType.RESEARCH,
            option_id=option_id,
            title="Verify current market and employer evidence",
            priority=1,
            position=0,
        ),
        CareerActionInput(
            action_type=CareerActionType.PREPARATION,
            option_id=option_id,
            title="Prepare decision-specific application materials",
            priority=2,
            position=1,
        ),
        CareerActionInput(
            action_type=CareerActionType.REVIEW_TASK,
            option_id=option_id,
            title="Review decision progress and assumptions",
            due_at=decision.planned_review_at,
            priority=3,
            position=2,
        ),
    )


def _stalled_items(
    actions: list[CareerAction], applications: list[CareerApplication], *, now: datetime
) -> list[dict[str, Any]]:
    stalled = []
    for action in actions:
        if (
            action.status in {"open", "in_progress"}
            and action.due_at is not None
            and _aware(action.due_at) < now
        ):
            stalled.append(
                {
                    "type": "action",
                    "id": action.action_id,
                    "title": action.title,
                    "reason": "past_due",
                }
            )
    for app in applications:
        age_days = (now - _aware(app.status_started_at)).days
        if app.status in {"applied", "response", "interview", "final_round"} and age_days >= 14:
            stalled.append(
                {
                    "type": "application",
                    "id": app.application_id,
                    "status": app.status,
                    "reason": "status_unchanged_14_days",
                }
            )
    return stalled


def _invalidated_assumptions(outcomes: list[CareerOutcome]) -> list[dict[str, Any]]:
    items = []
    for outcome in outcomes:
        invalidated = (
            outcome.metadata_json.get("invalidated_assumptions")
            if isinstance(outcome.metadata_json, dict)
            else None
        )
        if invalidated:
            items.append(
                {
                    "type": "outcome",
                    "id": outcome.outcome_id,
                    "invalidated_assumptions": invalidated,
                }
            )
    return items


def _reminders(
    decisions: list[CareerDecision],
    actions: list[CareerAction],
    applications: list[CareerApplication],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    horizon = now + timedelta(days=14)
    reminders = []
    for decision in decisions:
        if (
            decision.planned_review_at is not None
            and now <= _aware(decision.planned_review_at) <= horizon
        ):
            reminders.append(
                {
                    "type": "decision_review",
                    "id": decision.decision_id,
                    "due_at": decision.planned_review_at.isoformat(),
                    "title": decision.title,
                }
            )
    for action in actions:
        if (
            action.due_at is not None
            and action.status in {"open", "in_progress"}
            and now <= _aware(action.due_at) <= horizon
        ):
            reminders.append(
                {
                    "type": "action_due",
                    "id": action.action_id,
                    "due_at": action.due_at.isoformat(),
                    "title": action.title,
                }
            )
    for app in applications:
        if (
            app.follow_up_at is not None
            and app.status not in TERMINAL_APPLICATION_STATUSES
            and now <= _aware(app.follow_up_at) <= horizon
        ):
            reminders.append(
                {
                    "type": "application_follow_up",
                    "id": app.application_id,
                    "due_at": app.follow_up_at.isoformat(),
                    "status": app.status,
                }
            )
    return reminders


def _decision_snapshot(decision: CareerDecision) -> dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "decision_type": decision.decision_type,
        "status": decision.status,
        "title": decision.title,
        "description": decision.description,
        "decision_date": decision.decision_date.isoformat() if decision.decision_date else None,
        "target_date": decision.target_date.isoformat() if decision.target_date else None,
        "planned_review_at": decision.planned_review_at.isoformat()
        if decision.planned_review_at
        else None,
        "time_horizon": decision.time_horizon,
        "priorities": deepcopy(decision.priorities),
        "constraints": deepcopy(decision.constraints),
        "selected_option_id": decision.selected_option_id,
        "current_recommendation_id": decision.current_recommendation_id,
        "current_context_snapshot_id": decision.current_context_snapshot_id,
        "current_version": decision.current_version,
    }


def _option_snapshot(option: DecisionOption) -> dict[str, Any]:
    return {
        "option_id": option.option_id,
        "title": option.title,
        "description": option.description,
        "scenario": deepcopy(option.scenario),
        "status": option.status,
        "position": option.position,
    }


def _recommendation_snapshot(rec: DecisionRecommendation | None) -> dict[str, Any] | None:
    if rec is None:
        return None
    return {
        "recommendation_id": rec.recommendation_id,
        "context_snapshot_id": rec.context_snapshot_id,
        "recommended_option_id": rec.recommended_option_id,
        "recommendation_status": rec.recommendation_status,
        "evidence_sufficiency": rec.evidence_sufficiency,
        "confidence": rec.confidence,
        "summary": rec.summary,
        "fit": deepcopy(rec.fit_payload),
        "comparison": deepcopy(rec.comparison_payload),
        "evidence": deepcopy(rec.evidence_payload),
        "challenges": deepcopy(rec.challenge_payload),
        "limitations": deepcopy(rec.limitations),
        "generated_at": rec.generated_at.isoformat() if rec.generated_at else None,
    }


def _safe_provenance(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: deepcopy(val)
        for key, val in value.items()
        if key
        in {
            "state",
            "created_by",
            "source_type",
            "source_label",
            "observed_at",
            "extraction_method",
            "confidence",
        }
    }


def _payload_value(item: dict[str, Any], key: str) -> Any:
    return item["payload"].get(key)


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return None


def _tokens(value: Any) -> set[str]:
    return {_normalize_scalar(item) for item in _as_list(value) if _normalize_scalar(item)}


def _string_values(value: Any) -> list[str]:
    return [item for item in (_normalize_scalar(v) for v in _as_list(value)) if item]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().replace("-", " ").split())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence(
    kind: EvidenceKind, reference_type: str, reference_id: str, note: str
) -> dict[str, Any]:
    return {
        "kind": kind.value,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "note": note,
    }


def _challenge(
    code: ChallengeCode,
    *,
    severity: str,
    message: str,
    scope_type: str,
    scope_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code.value,
        "severity": severity,
        "message": message,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "details": details or {},
    }


def _dedupe_challenges(challenges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for challenge in challenges:
        key = (challenge["code"], challenge["scope_type"], challenge["scope_id"])
        deduped.setdefault(key, challenge)
    return list(deduped.values())


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"
