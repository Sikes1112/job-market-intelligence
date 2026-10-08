"""Layer 26B deterministic career action planning."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from backend.career_agent.memory import values_for_category
from backend.career_agent.schemas import (
    CareerActionPlan,
    CareerActionPlanRequest,
    CareerAgentEvidenceRef,
    CareerAgentEvidenceType,
    CareerAgentFreshness,
    CareerAgentFreshnessStatus,
    CareerAgentGuardrailViolation,
    CareerAgentQuestionType,
    CareerAgentRecommendation,
    CareerMemoryCategory,
    CareerMemoryProfile,
    CareerPlanEvidenceBinding,
    CareerPlanMilestone,
    CareerPlanRisk,
    CareerPlanStep,
    CareerPlanTimeWindow,
    CareerPlanType,
    CareerPlanUserActionRequirement,
    validate_career_action_plan,
)
from backend.career_agent.service import FORECAST_WARNING, CareerAgentGroundingService
from backend.shared.confidence import Confidence


class CareerActionPlanningService:
    """Create governed actions from authoritative conclusions and context."""

    _PUBLIC_CONTEXT_USER_ID = "public_career_agent_context"

    def __init__(self, session: Session) -> None:
        self._grounding_service = CareerAgentGroundingService(session)

    def generate_plan(
        self,
        request: CareerActionPlanRequest,
        *,
        user_id: str | None = None,
        memory_profile: CareerMemoryProfile | None = None,
        now: datetime | None = None,
    ) -> CareerActionPlan:
        generated_at = _aware(now or datetime.now(UTC))
        plan_request = request.career_agent_request.model_copy(
            update={
                "question_type": _question_type_for_plan(request),
                "user_goal": request.career_goal
                or request.career_agent_request.user_goal,
                "limit": min(request.limit, request.career_agent_request.limit),
                "preferred_program_types": _program_types_for_plan(request),
            }
        )
        answer = self._grounding_service.answer_for_plan(
            user_id or self._PUBLIC_CONTEXT_USER_ID,
            plan_request,
            now=generated_at,
        )
        if not answer.recommendations:
            reason = " ".join(answer.limitations) or (
                "Authoritative Decision, Explore, or current-job context is required."
            )
            raise CareerAgentGuardrailViolation(
                f"Action plan unavailable: {reason}"
            )

        memory_warnings, memory_personalization = _memory_effects(memory_profile)
        recommendations, rejected_warnings = _apply_rejected_market_memory(
            answer.recommendations,
            memory_profile,
        )
        plan_warnings = _dedupe_strings(
            (
                *answer.guardrails.warnings,
                *answer.limitations,
                *memory_warnings,
                *rejected_warnings,
                *_freshness_warnings(answer.freshness),
                *_uncertainty_warnings(answer.uncertainty),
            )
        )
        time_window = request.time_window or _default_time_window(
            request.plan_type,
            generated_at.date(),
        )
        steps = _build_steps(
            request.plan_type,
            recommendations[: request.limit],
            time_window=time_window,
            generated_at=generated_at,
        )
        evidence_refs = _dedupe_refs(
            ref for step in steps for ref in step.evidence_refs
        )
        risks = _dedupe_risks(
            (
                *(
                    risk
                    for step in steps
                    for risk in step.risks
                ),
                *_plan_level_risks(
                    evidence_refs,
                    freshness=answer.freshness,
                    confidence=answer.uncertainty.confidence_level,
                    warnings=plan_warnings,
                ),
            )
        )
        guardrails = answer.guardrails.model_copy(
            update={
                "warnings": plan_warnings,
                "evidence_requirement_met": all(
                    step.evidence_refs for step in steps if step.strategic
                ),
            }
        )
        plan = CareerActionPlan(
            plan_id=_stable_id(
                "career_action_plan",
                request.plan_type.value,
                generated_at.isoformat(),
                answer.answer_id,
            ),
            plan_type=request.plan_type,
            generated_at=generated_at,
            source_answer_id=answer.answer_id,
            summary=_plan_summary(request.plan_type, recommendations, plan_warnings),
            career_goal=request.career_goal or request.career_agent_request.user_goal,
            time_window=time_window,
            steps=steps,
            evidence_refs=evidence_refs,
            freshness=answer.freshness,
            source_freshness=answer.source_freshness,
            uncertainty=answer.uncertainty,
            risks=risks,
            warnings=plan_warnings,
            limitations=answer.limitations,
            memory_personalization=memory_personalization,
            guardrails=guardrails,
        )
        validate_career_action_plan(plan)
        return plan


def _question_type_for_plan(request: CareerActionPlanRequest) -> CareerAgentQuestionType:
    if (
        request.plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR
        or request.career_agent_request.question_type
        is CareerAgentQuestionType.WHERE_SHOULD_I_APPLY
    ):
        return CareerAgentQuestionType.WHERE_SHOULD_I_APPLY
    return CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY


def _program_types_for_plan(request: CareerActionPlanRequest) -> tuple[str, ...]:
    program_types = request.career_agent_request.preferred_program_types
    if request.plan_type is not CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return program_types
    if "internship" in program_types:
        return program_types
    return (*program_types, "internship")


def _default_time_window(plan_type: CareerPlanType, start: date) -> CareerPlanTimeWindow:
    days_by_type = {
        CareerPlanType.WEEKLY_JOB_SEARCH_PLAN: 6,
        CareerPlanType.REGIONAL_TARGETING_PLAN: 29,
        CareerPlanType.COMPANY_RESEARCH_PLAN: 13,
        CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR: 29,
        CareerPlanType.NETWORKING_PLAN: 13,
    }
    days = days_by_type[plan_type]
    return CareerPlanTimeWindow(
        label=f"{plan_type.value.replace('_', ' ')} window",
        start_date=start,
        end_date=start + timedelta(days=days),
    )


def _build_steps(
    plan_type: CareerPlanType,
    recommendations: tuple[CareerAgentRecommendation, ...],
    *,
    time_window: CareerPlanTimeWindow,
    generated_at: datetime,
) -> tuple[CareerPlanStep, ...]:
    steps: list[CareerPlanStep] = []
    first = recommendations[0]
    steps.append(
        _step_from_recommendation(
            plan_type,
            first,
            rank=1,
            action_owner=CareerPlanUserActionRequirement.SYSTEM_SUGGESTED,
            time_window=time_window,
            generated_at=generated_at,
            title=_system_step_title(plan_type, first),
            description=_system_step_description(plan_type, first),
            milestone_summary="Evidence-backed priority selected.",
            outcome="One grounded focus area is identified before user action begins.",
        )
    )
    for index, recommendation in enumerate(recommendations, start=2):
        steps.append(
            _step_from_recommendation(
                plan_type,
                recommendation,
                rank=index,
                action_owner=CareerPlanUserActionRequirement.USER_ACTION_REQUIRED,
                time_window=time_window,
                generated_at=generated_at,
                title=_user_step_title(plan_type, recommendation),
                description=_user_step_description(plan_type, recommendation),
                milestone_summary=_user_milestone_summary(plan_type),
                outcome=_user_milestone_outcome(plan_type),
            )
        )
    return tuple(steps)


def _step_from_recommendation(
    plan_type: CareerPlanType,
    recommendation: CareerAgentRecommendation,
    *,
    rank: int,
    action_owner: CareerPlanUserActionRequirement,
    time_window: CareerPlanTimeWindow,
    generated_at: datetime,
    title: str,
    description: str,
    milestone_summary: str,
    outcome: str,
) -> CareerPlanStep:
    step_id = _stable_id(
        "career_plan_step",
        plan_type.value,
        recommendation.recommendation_id,
        str(rank),
        generated_at.isoformat(),
    )
    target_date = min(
        time_window.end_date,
        time_window.start_date + timedelta(days=max(0, rank - 1)),
    )
    warnings = _dedupe_strings(
        (
            *recommendation.warnings,
            *recommendation.limitations,
            *recommendation.freshness.warnings,
            *(
                (FORECAST_WARNING,)
                if _has_forecast_evidence(recommendation.evidence_refs)
                or recommendation.uncertainty.forecast_based
                else ()
            ),
        )
    )
    risks = _plan_level_risks(
        recommendation.evidence_refs,
        freshness=recommendation.freshness,
        confidence=recommendation.uncertainty.confidence_level,
        warnings=warnings,
    )
    binding = CareerPlanEvidenceBinding(
        binding_id=_stable_id("career_plan_binding", step_id),
        step_id=step_id,
        binding_type="strategic_basis",
        evidence_refs=recommendation.evidence_refs,
        note="This step is grounded in the attached structured career-agent evidence refs.",
    )
    return CareerPlanStep(
        step_id=step_id,
        rank=rank,
        title=title,
        description=description,
        action_owner=action_owner,
        strategic=True,
        milestone=CareerPlanMilestone(
            milestone_id=_stable_id("career_plan_milestone", step_id),
            summary=milestone_summary,
            outcome=outcome,
            target_date=target_date,
        ),
        evidence_refs=recommendation.evidence_refs,
        evidence_bindings=(binding,),
        freshness=recommendation.freshness,
        uncertainty=recommendation.uncertainty,
        risks=risks,
        matched_opportunity_ids=recommendation.matched_opportunity_ids,
        warnings=warnings,
    )


def _system_step_title(
    plan_type: CareerPlanType,
    recommendation: CareerAgentRecommendation,
) -> str:
    if recommendation.recommendation_type == "explore_market_context":
        return f"Review authoritative Explore context for {recommendation.title}"
    if plan_type is CareerPlanType.REGIONAL_TARGETING_PLAN:
        return f"Set the primary regional lane around {recommendation.title}"
    if plan_type is CareerPlanType.COMPANY_RESEARCH_PLAN:
        return f"Prioritize research around {recommendation.title}"
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return f"Anchor the internship calendar on {recommendation.title}"
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return f"Focus networking research around {recommendation.title}"
    return f"Use {recommendation.title} as the first weekly priority"


def _system_step_description(
    plan_type: CareerPlanType,
    recommendation: CareerAgentRecommendation,
) -> str:
    if recommendation.recommendation_type == "explore_market_context":
        return (
            "Explore supplied this governed market context for comparison; its display "
            "order is not a separate Career Agent recommendation or market winner. "
            f"{recommendation.summary}"
        )
    base = (
        "The system suggests this action because an authoritative subsystem supplied "
        f"the conclusion and structured evidence: {recommendation.summary}"
    )
    if recommendation.action:
        base = f"{base} Authoritative next action: {recommendation.action}"
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return (
            f"{base} Treat calendar dates as planning checkpoints only; verify source "
            "timing manually before acting."
        )
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return (
            f"{base} Use official public pages and contacts you already have permission "
            "to use; no recruiter contacts are inferred."
        ).replace("recruiter contacts", "hiring contacts")
    return base


def _user_step_title(
    plan_type: CareerPlanType,
    recommendation: CareerAgentRecommendation,
) -> str:
    if plan_type is CareerPlanType.REGIONAL_TARGETING_PLAN:
        return f"Compare constraints against {recommendation.title}"
    if plan_type is CareerPlanType.COMPANY_RESEARCH_PLAN:
        return f"Complete structured company research for {recommendation.title}"
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return f"Prepare a manual application checklist for {recommendation.title}"
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return f"Create a permission-safe networking note for {recommendation.title}"
    return f"Verify and act on {recommendation.title}"


def _user_step_description(
    plan_type: CareerPlanType,
    recommendation: CareerAgentRecommendation,
) -> str:
    if plan_type is CareerPlanType.REGIONAL_TARGETING_PLAN:
        description = (
            "User action: compare relocation, commute, role, and timing constraints "
            f"against the evidence-backed market recommendation. "
            f"{recommendation.action or ''}"
        )
        return description.strip()
    if plan_type is CareerPlanType.COMPANY_RESEARCH_PLAN:
        description = (
            "User action: review the employer's official public materials and compare "
            f"any current role with the attached company evidence. "
            f"{recommendation.action or ''}"
        )
        return description.strip()
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return (
            "User action: build a checklist for eligibility, materials, location, and "
            "source timing. Do not treat this plan as proof that a new opening exists."
        )
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return (
            "User action: draft a research note or outreach idea only from public, "
            "permission-safe information. The plan does not infer private contacts."
        )
    return (
        "User action: manually verify source freshness, fit, and any official role "
        "details before spending application time."
    )


def _user_milestone_summary(plan_type: CareerPlanType) -> str:
    if plan_type is CareerPlanType.REGIONAL_TARGETING_PLAN:
        return "Market constraint check completed."
    if plan_type is CareerPlanType.COMPANY_RESEARCH_PLAN:
        return "Company research note completed."
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return "Manual application checklist completed."
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return "Permission-safe networking note completed."
    return "Weekly verification step completed."


def _user_milestone_outcome(plan_type: CareerPlanType) -> str:
    if plan_type is CareerPlanType.REGIONAL_TARGETING_PLAN:
        return "A market is kept, paused, or rejected based on user constraints."
    if plan_type is CareerPlanType.COMPANY_RESEARCH_PLAN:
        return "A company is ready for watch, deeper research, or deprioritization."
    if plan_type is CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR:
        return "The user has a source-verified checklist without invented timing claims."
    if plan_type is CareerPlanType.NETWORKING_PLAN:
        return "The user has a compliant next networking step without inferred contacts."
    return "The user has one verified next action and known evidence limitations."


def _memory_effects(
    memory_profile: CareerMemoryProfile | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if memory_profile is None:
        return (), ()
    applied_roles = values_for_category(
        memory_profile,
        CareerMemoryCategory.APPLIED_ROLES,
    )
    personalization: list[str] = []
    warnings: list[str] = []
    if applied_roles:
        personalization.append(
            "Applied roles memory was used as user context only, not source evidence."
        )
        warnings.append(
            "Career memory notes already-applied roles; avoid treating them as new targets."
        )
    if values_for_category(memory_profile, CareerMemoryCategory.REJECTED_MARKETS):
        personalization.append(
            "Rejected markets memory was used to adjust plan priority only."
        )
    return tuple(warnings), tuple(personalization)


def _apply_rejected_market_memory(
    recommendations: tuple[CareerAgentRecommendation, ...],
    memory_profile: CareerMemoryProfile | None,
) -> tuple[tuple[CareerAgentRecommendation, ...], tuple[str, ...]]:
    rejected_markets = values_for_category(
        memory_profile,
        CareerMemoryCategory.REJECTED_MARKETS,
    )
    if not rejected_markets:
        return recommendations, ()
    rejected_normalized = {_normalize(value) for value in rejected_markets}
    kept: list[CareerAgentRecommendation] = []
    removed: list[str] = []
    for recommendation in recommendations:
        haystack = " ".join(
            (
                recommendation.target_id,
                recommendation.title,
                *(ref.entity_id for ref in recommendation.evidence_refs),
                *(ref.label for ref in recommendation.evidence_refs),
            )
        )
        if any(item and item in _normalize(haystack) for item in rejected_normalized):
            removed.append(recommendation.target_id)
        else:
            kept.append(recommendation)
    if kept:
        return tuple(kept), (
            "Career memory excluded rejected markets from plan priority.",
        )
    return recommendations, (
        "All grounded recommendations matched rejected markets; review memory settings "
        "before acting.",
    )


def _plan_summary(
    plan_type: CareerPlanType,
    recommendations: tuple[CareerAgentRecommendation, ...],
    warnings: tuple[str, ...],
) -> str:
    warning_note = " Known limitations are attached." if warnings else ""
    return (
        f"Generated a {plan_type.value.replace('_', ' ')} from "
        f"{len(recommendations)} authoritative recommendation or context item(s)."
        f"{warning_note}"
    )


def _plan_level_risks(
    evidence_refs: tuple[CareerAgentEvidenceRef, ...],
    *,
    freshness: CareerAgentFreshness,
    confidence: Confidence,
    warnings: tuple[str, ...],
) -> tuple[CareerPlanRisk, ...]:
    risks: list[CareerPlanRisk] = []
    if freshness.freshness_status in {
        CareerAgentFreshnessStatus.STALE,
        CareerAgentFreshnessStatus.PARTIAL,
        CareerAgentFreshnessStatus.UNKNOWN,
    }:
        risks.append(
            CareerPlanRisk(
                risk_id=_stable_id(
                    "career_plan_risk",
                    "freshness",
                    freshness.freshness_status.value,
                ),
                severity=(
                    "high"
                    if freshness.freshness_status is CareerAgentFreshnessStatus.STALE
                    else "medium"
                ),
                summary=f"Evidence freshness is {freshness.freshness_status.value}.",
                mitigation="Verify source freshness manually before acting on this step.",
                evidence_refs=evidence_refs[:5],
            )
        )
    if confidence in {Confidence.LOW, Confidence.UNKNOWN}:
        risks.append(
            CareerPlanRisk(
                risk_id=_stable_id("career_plan_risk", "confidence", confidence.value),
                severity="high" if confidence is Confidence.UNKNOWN else "medium",
                summary=f"Evidence confidence is {confidence.value}.",
                mitigation=(
                    "Treat this as a low-support plan item until more structured "
                    "evidence exists."
                ),
                evidence_refs=evidence_refs[:5],
            )
        )
    has_forecast_warning = any(
        "forecast" in warning.casefold() for warning in warnings
    )
    if has_forecast_warning or _has_forecast_evidence(evidence_refs):
        risks.append(
            CareerPlanRisk(
                risk_id=_stable_id(
                    "career_plan_risk",
                    "forecast",
                    *(ref.ref_id for ref in evidence_refs[:3]),
                ),
                severity="medium",
                summary="Forecast-backed evidence is directional and uncertain.",
                mitigation="Use forecasts for prioritization only, not as proof of future hiring.",
                evidence_refs=tuple(
                    ref
                    for ref in evidence_refs
                    if ref.evidence_type is CareerAgentEvidenceType.FORECAST
                )[:5],
            )
        )
    return tuple(risks)


def _freshness_warnings(freshness: CareerAgentFreshness) -> tuple[str, ...]:
    warnings = list(freshness.warnings)
    if freshness.freshness_status is CareerAgentFreshnessStatus.STALE:
        warnings.append("Evidence is stale; verify current source state before acting.")
    elif freshness.freshness_status in {
        CareerAgentFreshnessStatus.PARTIAL,
        CareerAgentFreshnessStatus.UNKNOWN,
    }:
        warnings.append("Evidence coverage is incomplete or unknown.")
    return tuple(warnings)


def _uncertainty_warnings(uncertainty) -> tuple[str, ...]:  # noqa: ANN001
    warnings: list[str] = []
    if uncertainty.confidence_level in {Confidence.LOW, Confidence.UNKNOWN}:
        warnings.append("Confidence is low or unknown; treat plan priority as tentative.")
    if uncertainty.forecast_based:
        warnings.append(FORECAST_WARNING)
    return tuple(warnings)


def _has_forecast_evidence(evidence_refs: tuple[CareerAgentEvidenceRef, ...]) -> bool:
    return any(ref.evidence_type is CareerAgentEvidenceType.FORECAST for ref in evidence_refs)


def _dedupe_refs(refs) -> tuple[CareerAgentEvidenceRef, ...]:  # noqa: ANN001
    seen: set[str] = set()
    deduped: list[CareerAgentEvidenceRef] = []
    for ref in refs:
        if ref.ref_id in seen:
            continue
        seen.add(ref.ref_id)
        deduped.append(ref)
    return tuple(deduped)


def _dedupe_risks(risks: tuple[CareerPlanRisk, ...]) -> tuple[CareerPlanRisk, ...]:
    seen: set[str] = set()
    deduped: list[CareerPlanRisk] = []
    for risk in risks:
        if risk.risk_id in seen:
            continue
        seen.add(risk.risk_id)
        deduped.append(risk)
    return tuple(deduped)


def _dedupe_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in values if item))


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join((prefix, *parts))
    return f"{prefix}_{uuid5(NAMESPACE_URL, joined).hex[:24]}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())
