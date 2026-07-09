"""Read-only Layer 30.1 user intelligence dashboard assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api.search import search_companies, search_regions
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.service import OpportunityService
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.predictive_exports import export_predictive_observations
from backend.predictive.reports import PredictiveReportBuilder
from backend.user_intelligence.schemas import (
    DashboardSummary,
    DashboardTrustContext,
    ForecastChange,
    MarketWarning,
    RecommendedCompany,
    RecommendedNextAction,
    RecommendedOpportunity,
    RecommendedRegion,
    SavedDashboardItem,
    UserIntelligenceDashboardResponse,
)
from backend.users.repository import UserRepository


class UserIntelligenceDashboardService:
    """Build a user-facing dashboard from existing read-only metadata.

    The service deliberately does not create trust tiers, mutate ranking flags,
    write canonical facts, or expose review internals. It copies existing
    confidence/freshness/warning/source metadata so later Layer 30 slices can
    replace the placeholder trust fields with deterministic trust assessments.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def build_dashboard(
        self,
        *,
        current_user_id: str | None = None,
        now: datetime | None = None,
        region_limit: int = 5,
        company_limit: int = 5,
        opportunity_limit: int = 5,
        forecast_limit: int = 5,
    ) -> UserIntelligenceDashboardResponse:
        generated_at = now or datetime.now(UTC)
        regions = self._recommended_regions(limit=region_limit)
        companies = self._recommended_companies(limit=company_limit)
        opportunities = self._recommended_opportunities(
            limit=opportunity_limit,
            now=generated_at,
        )
        forecast_changes = self._forecast_changes(
            regions=regions,
            companies=companies,
            limit=forecast_limit,
            now=generated_at,
        )
        saved_items = self._saved_items(current_user_id=current_user_id)
        warnings = self._market_warnings(
            regions=regions,
            companies=companies,
            opportunities=opportunities,
            forecasts=forecast_changes,
        )
        next_actions = self._next_actions(
            regions=regions,
            companies=companies,
            opportunities=opportunities,
            warnings=warnings,
            forecasts=forecast_changes,
        )
        recommendation_count = len(regions) + len(companies) + len(opportunities)
        return UserIntelligenceDashboardResponse(
            generated_at=generated_at,
            summary=DashboardSummary(
                headline="Your current market intelligence",
                description=(
                    "Personalized recommendations, warnings, and next actions "
                    "based on available data."
                ),
                warning_count=len(warnings),
                recommendation_count=recommendation_count,
            ),
            recommended_regions=regions,
            recommended_companies=companies,
            recommended_opportunities=opportunities,
            market_warnings=warnings,
            forecast_changes=forecast_changes,
            saved_items=saved_items,
            recommended_next_actions=next_actions,
            trust_context=DashboardTrustContext(
                uses_existing_metadata_only=False,
                layer_30_full_trust_engine_available=True,
                message=(
                    "This dashboard displays available confidence, freshness, "
                    "source, trust, evidence, risk, ranking, explanation, report, "
                    "recheck, and safe exception metadata from the deterministic "
                    "Layer 30 workflow."
                ),
            ),
        )

    def _recommended_regions(self, *, limit: int) -> tuple[RecommendedRegion, ...]:
        if limit <= 0:
            return ()
        if not _tables_available(self._session, _REGION_RECOMMENDATION_TABLES):
            return ()
        response = search_regions(self._session)
        scored = [
            region
            for region in response.regions
            if region.opportunity_score is not None
        ]
        ranked = sorted(
            scored,
            key=lambda region: (
                region.opportunity_score or 0.0,
                region.has_real_data,
                region.name.casefold(),
                region.region_id,
            ),
            reverse=True,
        )
        return tuple(_region_item(region) for region in ranked[:limit])

    def _recommended_companies(self, *, limit: int) -> tuple[RecommendedCompany, ...]:
        if limit <= 0:
            return ()
        if not _tables_available(self._session, _COMPANY_RECOMMENDATION_TABLES):
            return ()
        response = search_companies(self._session)
        candidates = [
            company
            for company in response.companies
            if company.current_hiring or company.has_entry_level_access
        ]
        ranked = sorted(
            candidates,
            key=lambda company: (
                company.current_hiring,
                company.has_entry_level_access,
                company.has_real_data,
                len(company.matched_region_ids),
                company.name.casefold(),
                company.company_id,
            ),
            reverse=True,
        )
        return tuple(_company_item(company) for company in ranked[:limit])

    def _recommended_opportunities(
        self,
        *,
        limit: int,
        now: datetime,
    ) -> tuple[RecommendedOpportunity, ...]:
        if limit <= 0:
            return ()
        if not _tables_available(self._session, _OPPORTUNITY_RECOMMENDATION_TABLES):
            return ()
        service = OpportunityService(OpportunityRepository(self._session))
        payload = service.list_opportunities(active=True, now=now, limit=limit)
        return tuple(_opportunity_item(opportunity) for opportunity in payload.opportunities)

    def _forecast_changes(
        self,
        *,
        regions: tuple[RecommendedRegion, ...],
        companies: tuple[RecommendedCompany, ...],
        limit: int,
        now: datetime,
    ) -> tuple[ForecastChange, ...]:
        if limit <= 0:
            return ()
        region_ids = tuple(region.region_id for region in regions)
        company_ids = tuple(company.company_id for company in companies)
        if not region_ids and not company_ids:
            return ()
        if not _history_tables_available(self._session):
            return ()
        try:
            observations = export_predictive_observations(
                HistoryRepository(self._session),
                region_ids=region_ids,
                company_ids=company_ids,
                limit_per_subject=100,
            )
        except SQLAlchemyError:
            return ()
        report = PredictiveReportBuilder().build_report(
            observations,
            generated_at=now,
            now=now.date(),
        )
        items: list[ForecastChange] = []
        for section in report.sections:
            for forecast in section.forecasts:
                items.append(
                    ForecastChange(
                        subject_type=forecast.affected_entity.entity_type.value,
                        subject_id=forecast.affected_entity.entity_id,
                        title=forecast.forecast_title,
                        summary=forecast.safe_display_summary,
                        confidence=forecast.confidence.level.value,
                        freshness=_forecast_freshness(forecast),
                        warnings=tuple(forecast.uncertainty.limitations),
                    )
                )
                if len(items) >= limit:
                    return tuple(items)
        return tuple(items)

    def _saved_items(
        self,
        *,
        current_user_id: str | None,
        limit: int = 10,
    ) -> tuple[SavedDashboardItem, ...]:
        if not current_user_id:
            return ()
        if not _tables_available(self._session, _SAVED_ITEM_TABLES):
            return ()
        rows = UserRepository(self._session).list_saved_market_artifacts(
            user_id=current_user_id,
        )
        return tuple(_saved_item(row) for row in rows[:limit])

    def _market_warnings(
        self,
        *,
        regions: tuple[RecommendedRegion, ...],
        companies: tuple[RecommendedCompany, ...],
        opportunities: tuple[RecommendedOpportunity, ...],
        forecasts: tuple[ForecastChange, ...],
    ) -> tuple[MarketWarning, ...]:
        warnings: list[MarketWarning] = []
        for region in regions:
            for index, message in enumerate(region.warnings):
                warnings.append(
                    _warning(
                        code=f"region_metadata_warning_{index + 1}",
                        title=f"{region.region_name} data warning",
                        message=message,
                        subject_type="region",
                        subject_id=region.region_id,
                        source="region_search_metadata",
                    )
                )
        for company in companies:
            for index, message in enumerate(company.warnings):
                warnings.append(
                    _warning(
                        code=f"company_metadata_warning_{index + 1}",
                        title=f"{company.company_name} data warning",
                        message=message,
                        subject_type="company",
                        subject_id=company.company_id,
                        source="company_search_metadata",
                    )
                )
        for opportunity in opportunities:
            for index, message in enumerate(opportunity.warnings):
                warnings.append(
                    _warning(
                        code=f"opportunity_metadata_warning_{index + 1}",
                        title=f"{opportunity.title} warning",
                        message=message,
                        subject_type="opportunity",
                        subject_id=opportunity.opportunity_id,
                        source="opportunity_metadata",
                    )
                )
        for forecast in forecasts:
            for index, message in enumerate(forecast.warnings):
                warnings.append(
                    _warning(
                        code=f"forecast_warning_{index + 1}",
                        title=f"{forecast.title} limitation",
                        message=message,
                        subject_type=forecast.subject_type,
                        subject_id=forecast.subject_id,
                        source="predictive_report_metadata",
                    )
                )
        return tuple(warnings[:25])

    def _next_actions(
        self,
        *,
        regions: tuple[RecommendedRegion, ...],
        companies: tuple[RecommendedCompany, ...],
        opportunities: tuple[RecommendedOpportunity, ...],
        warnings: tuple[MarketWarning, ...],
        forecasts: tuple[ForecastChange, ...],
    ) -> tuple[RecommendedNextAction, ...]:
        actions: list[RecommendedNextAction] = []
        if len(regions) >= 2:
            actions.append(
                RecommendedNextAction(
                    action_code="compare_recommended_regions",
                    label="Compare recommended regions",
                    description=(
                        "Review the top recommended regions side by side before "
                        "using either as a decision anchor."
                    ),
                    priority="high",
                    target_route=(
                        f"/markets/compare?region_a={regions[0].region_id}"
                        f"&region_b={regions[1].region_id}"
                    ),
                )
            )
        if companies:
            actions.append(
                RecommendedNextAction(
                    action_code="review_recommended_companies",
                    label="Review recommended companies",
                    description=(
                        "Inspect companies with current hiring or entry-level "
                        "signals and check freshness before relying on them."
                    ),
                    priority="medium",
                    target_route=f"/markets/company/{companies[0].company_id}",
                )
            )
        if opportunities:
            actions.append(
                RecommendedNextAction(
                    action_code="check_current_opportunities",
                    label="Check current opportunities",
                    description=(
                        "Open source links and verify eligibility, deadline, "
                        "location, and trust labels before acting."
                    ),
                    priority="medium",
                    target_route="/markets/opportunity-routes",
                )
            )
        if warnings:
            actions.append(
                RecommendedNextAction(
                    action_code="inspect_market_warnings",
                    label="Inspect market warnings",
                    description=(
                        "Review weak confidence, stale freshness, partner-submitted, "
                        "and forecast limitation warnings before relying on a result."
                    ),
                    priority="high",
                    target_route="/markets/dashboard#warnings",
                )
            )
        if forecasts:
            actions.append(
                RecommendedNextAction(
                    action_code="review_forecast_changes",
                    label="Review forecast changes",
                    description=(
                        "Use forecast movement as directional context, not certain "
                        "outcome claims."
                    ),
                    priority="low",
                    target_route="/forecasts",
                )
            )
        exception_opportunity = next(
            (
                opportunity
                for opportunity in opportunities
                if opportunity.exception_status is not None
            ),
            None,
        )
        if exception_opportunity is not None:
            actions.append(
                RecommendedNextAction(
                    action_code="avoid_exception_item",
                    label="Avoid relying on quarantined or blocked items",
                    description=(
                        "Review safe exception status and use stronger markets or "
                        "verified alternatives before relying on this item."
                    ),
                    priority="high",
                    target_route="/markets/dashboard",
                )
            )
        return tuple(actions[:6])


def _region_item(region: Any) -> RecommendedRegion:
    warnings = _metadata_warnings(region.freshness)
    coverage_warning = _coverage_warning(getattr(region, "coverage", None))
    if coverage_warning is not None:
        warnings = (*warnings, coverage_warning)
    return RecommendedRegion(
        region_id=region.region_id,
        region_name=region.name,
        score=region.opportunity_score,
        confidence=_confidence_from_source_summary(region.freshness),
        freshness=region.freshness.freshness_status.value,
        warnings=warnings,
        why_recommended=(
            "Existing region score metadata shows a comparatively strong "
            "objective opportunity score."
        ),
        ranking_influence_allowed=None,
    )


def _company_item(company: Any) -> RecommendedCompany:
    reasons: list[str] = []
    if company.current_hiring:
        reasons.append("current hiring")
    if company.has_entry_level_access:
        reasons.append("entry-level access")
    if company.matched_region_ids:
        reasons.append(f"{len(company.matched_region_ids)} matched region(s)")
    return RecommendedCompany(
        company_id=company.company_id,
        company_name=company.name,
        score=None,
        confidence=_confidence_from_source_summary(company.freshness),
        freshness=company.freshness.freshness_status.value,
        warnings=_metadata_warnings(company.freshness),
        why_recommended=(
            "Existing company metadata shows "
            f"{', '.join(reasons) if reasons else 'available market relevance'}."
        ),
        ranking_influence_allowed=None,
    )


def _opportunity_item(opportunity: Any) -> RecommendedOpportunity:
    warnings: list[str] = []
    if opportunity.partner_submitted:
        warnings.append("Partner-submitted opportunity; verify source details before acting.")
    if opportunity.ranking_influence_allowed is False:
        warnings.append("Visible opportunity is not allowed to influence rankings.")
    if str(opportunity.trust_label) in {"unverified", "partner_submitted"}:
        warnings.append("Opportunity trust label is not a verified trust label.")
    if str(opportunity.expiration_state) == "expired":
        warnings.append("Opportunity is expired.")
    for warning in getattr(opportunity, "trust_warnings", ()):
        message = getattr(warning, "message", None)
        if isinstance(message, str) and message:
            warnings.append(message)
    regions = tuple(opportunity.regions)
    trust_tier = getattr(getattr(opportunity, "trust_tier", None), "value", None)
    risk_level = _enum_value(getattr(opportunity, "risk_level", None))
    routing_outcome = _enum_value(getattr(opportunity, "routing_outcome", None))
    ranking_decision = _enum_value(
        getattr(opportunity, "ranking_influence_decision", None)
    )
    ranking_reason = getattr(opportunity, "ranking_influence_reason", None)
    ranking_reason_codes = tuple(
        value
        for value in (
            _enum_value(code)
            for code in getattr(opportunity, "ranking_influence_reason_codes", ())
        )
        if value is not None
    )
    trust_explanation = getattr(opportunity, "trust_explanation", None)
    report_recheck_status = getattr(opportunity, "report_recheck_status", None)
    exception_status = getattr(opportunity, "exception_status", None)
    if exception_status is not None:
        warnings.append(getattr(exception_status, "message", "Exception status present."))
    evidence_summary = _opportunity_evidence_summary(opportunity, trust_tier=trust_tier)
    return RecommendedOpportunity(
        opportunity_id=opportunity.id,
        title=opportunity.program_name,
        company_name=opportunity.employer_name,
        region_name=regions[0] if regions else None,
        trust_label=opportunity.trust_label.value,
        review_status=opportunity.review_status.value,
        partner_submitted=opportunity.partner_submitted,
        ranking_influence_allowed=opportunity.ranking_influence_allowed,
        expiration_state=opportunity.expiration_state.value,
        source_type=opportunity.source_type.value,
        warnings=tuple(dict.fromkeys(warnings)),
        why_recommended=(
            "Existing opportunity metadata marks this record as active and "
            "available to display."
        ),
        trust_tier=trust_tier,
        evidence_summary=evidence_summary,
        risk_level=risk_level,
        routing_outcome=routing_outcome,
        ranking_influence_decision=ranking_decision,
        ranking_influence_reason=ranking_reason,
        ranking_influence_reason_codes=ranking_reason_codes,
        trust_explanation=trust_explanation,
        report_recheck_status=report_recheck_status,
        exception_status=exception_status,
    )


def _opportunity_evidence_summary(
    opportunity: Any,
    *,
    trust_tier: str | None,
) -> dict[str, int | str] | None:
    if trust_tier is None:
        return None
    return {
        "trust_tier": trust_tier,
        "met_count": len(tuple(getattr(opportunity, "evidence_requirements_met", ()))),
        "missing_count": len(
            tuple(getattr(opportunity, "evidence_requirements_missing", ()))
        ),
        "failed_count": len(
            tuple(getattr(opportunity, "evidence_requirements_failed", ()))
        ),
        "warning_count": len(tuple(getattr(opportunity, "trust_warnings", ()))),
    }


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    if isinstance(value, str):
        return value
    return None


def _saved_item(row: Any) -> SavedDashboardItem:
    label = row.label or row.artifact_ref
    return SavedDashboardItem(
        item_id=row.saved_artifact_id,
        item_type=row.artifact_type,
        label=label,
        target_route=_saved_item_route(row.artifact_type, row.artifact_ref),
        metadata={
            "artifact_ref": row.artifact_ref,
            "notes": row.notes,
        },
    )


def _saved_item_route(artifact_type: str, artifact_ref: str) -> str | None:
    if artifact_type == "region":
        return f"/markets/region/{artifact_ref}"
    if artifact_type == "company":
        return f"/markets/company/{artifact_ref}"
    if artifact_type == "comparison":
        return "/markets/compare"
    if artifact_type == "discovery_result":
        return "/markets/discovery"
    return None


def _metadata_warnings(summary: Any) -> tuple[str, ...]:
    warning = getattr(summary, "low_confidence_warning", None)
    return (warning,) if isinstance(warning, str) and warning.strip() else ()


def _confidence_from_source_summary(summary: Any) -> str:
    if getattr(summary, "low_confidence_warning", None):
        return "warning"
    if getattr(summary, "source_count", 0) <= 0:
        return "unknown"
    freshness = getattr(getattr(summary, "freshness_status", None), "value", None)
    if freshness == "fresh":
        return "metadata_available"
    return freshness or "unknown"


def _coverage_warning(coverage: Any) -> str | None:
    if coverage is None:
        return None
    limitations = getattr(coverage, "coverage_limitations", None)
    if limitations:
        return "; ".join(str(item) for item in limitations)
    should_rank = getattr(coverage, "should_rank_as_confident_recommendation", None)
    if should_rank is False:
        return "Coverage metadata does not mark this region as a confident recommendation market."
    return None


def _forecast_freshness(forecast: Any) -> str | None:
    states = getattr(forecast.source_basis, "freshness_states", ())
    return ", ".join(states) if states else None


_REGION_RECOMMENDATION_TABLES = frozenset(
    {
        "regions",
        "region_market_scores",
        "company_region_presence",
        "company_region_hiring",
        "company_region_entry_level",
        "fact_source_links",
    }
)
_COMPANY_RECOMMENDATION_TABLES = frozenset(
    {
        "companies",
        "regions",
        "region_market_scores",
        "company_region_presence",
        "company_region_hiring",
        "company_region_entry_level",
        "fact_source_links",
    }
)
_OPPORTUNITY_RECOMMENDATION_TABLES = frozenset(
    {
        "employer_programs",
        "opportunities",
        "opportunity_sources",
        "opportunity_region_bindings",
        "opportunity_role_family_bindings",
        "employer_influence_metadata",
        "opportunity_review_actions",
    }
)
_SAVED_ITEM_TABLES = frozenset({"saved_market_artifacts"})
_HISTORY_TABLES = frozenset(
    {
        "market_snapshots",
        "sector_region_snapshots",
        "company_region_snapshots",
    }
)


def _history_tables_available(session: Session) -> bool:
    return _tables_available(session, _HISTORY_TABLES)


def _tables_available(session: Session, required: frozenset[str]) -> bool:
    inspector = inspect(session.connection())
    table_names = set(inspector.get_table_names())
    return required.issubset(table_names)


def _warning(
    *,
    code: str,
    title: str,
    message: str,
    subject_type: str,
    subject_id: str,
    source: str,
) -> MarketWarning:
    return MarketWarning(
        warning_code=code,
        severity=_warning_severity(message),
        title=title,
        message=message,
        subject_type=subject_type,
        subject_id=subject_id,
        source=source,
    )


def _warning_severity(message: str) -> str:
    text = message.casefold()
    if any(token in text for token in ("expired", "blocked", "critical")):
        return "critical"
    if any(
        token in text
        for token in ("stale", "unknown", "low confidence", "partner-submitted", "not allowed")
    ):
        return "warning"
    return "info"
