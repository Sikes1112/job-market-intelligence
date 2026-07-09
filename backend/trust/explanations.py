"""Deterministic user-facing Layer 30C trust explanations."""

from __future__ import annotations

from backend.trust.schemas import (
    EvidenceRequirementCode,
    ExceptionSubjectStatus,
    RankingInfluenceDecision,
    RankingInfluenceReasonCode,
    ReportRecheckStatus,
    RiskLevel,
    RiskRoutingDecisionResult,
    RoutingOutcome,
    TrustAssessmentResult,
    TrustAssessmentSubjectType,
    TrustExplanation,
    TrustTier,
    UserFacingTrustWarning,
)

TRUST_LABELS: dict[TrustTier, str] = {
    TrustTier.TRUSTED: "Trusted source",
    TrustTier.VERIFIED: "Verified",
    TrustTier.PARTNER_SUBMITTED: "Partner-submitted",
    TrustTier.UNVERIFIED_VISIBLE: "Not independently verified",
    TrustTier.LOW_CONFIDENCE: "Low confidence",
    TrustTier.CONFLICTING: "Conflicting source detected",
    TrustTier.STALE: "Stale source",
    TrustTier.QUARANTINED: "Quarantined",
    TrustTier.RANKING_INELIGIBLE: "Excluded from rankings",
    TrustTier.BLOCKED: "Blocked",
    TrustTier.NOT_ASSESSED: "Not assessed",
}

RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Low risk",
    RiskLevel.MEDIUM: "Use with caution",
    RiskLevel.HIGH: "Needs stronger evidence",
    RiskLevel.CRITICAL: "Blocked or quarantined",
    RiskLevel.UNKNOWN: "Not assessed",
}

ROUTING_LABELS: dict[RoutingOutcome, str] = {
    RoutingOutcome.AUTO_ACCEPT_NON_RANKING: "Visible, not used in rankings",
    RoutingOutcome.VISIBLE_WITH_WARNING: "Visible with warning",
    RoutingOutcome.NEEDS_MORE_EVIDENCE: "Needs stronger evidence",
    RoutingOutcome.AUTO_RECHECK: "Queued for recheck",
    RoutingOutcome.AUTO_REJECT: "Rejected automatically",
    RoutingOutcome.QUARANTINE: "Quarantined",
    RoutingOutcome.BLOCKED: "Blocked",
    RoutingOutcome.ESCALATE_EXCEPTION: "Requires exception handling",
    RoutingOutcome.NOT_ROUTED: "Not routed",
}

RANKING_LABELS: dict[RankingInfluenceDecision, str] = {
    RankingInfluenceDecision.ALLOWED: "Used in rankings",
    RankingInfluenceDecision.DENIED: "Excluded from rankings",
    RankingInfluenceDecision.NOT_APPLICABLE: "Not applicable",
    RankingInfluenceDecision.NOT_ASSESSED: "Not assessed",
}


class TrustExplanationService:
    """Build safe user-facing explanations from existing 30A/30B decisions."""

    def explain(
        self,
        *,
        assessment: TrustAssessmentResult | None,
        routing: RiskRoutingDecisionResult | None,
        subject_type: TrustAssessmentSubjectType,
        subject_id: str,
        report_recheck_status: ReportRecheckStatus | None = None,
        exception_status: ExceptionSubjectStatus | None = None,
    ) -> TrustExplanation:
        if assessment is None:
            return self.not_assessed(
                subject_type=subject_type,
                subject_id=subject_id,
                report_recheck_status=report_recheck_status,
                exception_status=exception_status,
            )

        tier = assessment.trust_tier
        ranking_decision = (
            routing.ranking_influence_decision
            if routing is not None
            else RankingInfluenceDecision.NOT_ASSESSED
        )
        ranking_allowed = (
            routing.ranking_influence_allowed if routing is not None else False
        )
        return TrustExplanation(
            subject_type=assessment.subject_type,
            subject_id=assessment.subject_id,
            trust_tier=tier,
            trust_label=TRUST_LABELS[tier],
            trust_summary=_trust_summary(tier),
            risk_level=routing.risk_level if routing is not None else None,
            risk_label=(
                RISK_LABELS[routing.risk_level] if routing is not None else None
            ),
            risk_summary=(
                _risk_summary(routing.risk_level) if routing is not None else None
            ),
            routing_outcome=routing.routing_outcome if routing is not None else None,
            routing_label=(
                ROUTING_LABELS[routing.routing_outcome]
                if routing is not None
                else None
            ),
            routing_summary=(
                _routing_summary(routing.routing_outcome)
                if routing is not None
                else None
            ),
            ranking_influence_allowed=ranking_allowed,
            ranking_influence_decision=ranking_decision,
            ranking_influence_label=RANKING_LABELS[ranking_decision],
            ranking_influence_reason=_ranking_reason(routing, tier=tier),
            evidence_requirements_met=assessment.evidence_requirements_met,
            evidence_requirements_missing=assessment.evidence_requirements_missing,
            evidence_requirements_failed=assessment.evidence_requirements_failed,
            trust_warnings=assessment.warnings,
            user_facing_warnings=_user_facing_warnings(assessment, routing),
            last_checked_at=assessment.assessed_at,
            decided_at=routing.decided_at if routing is not None else None,
            next_recheck_at=assessment.next_assessment_at,
            report_recheck_status=report_recheck_status,
            exception_status=exception_status,
        )

    def not_assessed(
        self,
        *,
        subject_type: TrustAssessmentSubjectType,
        subject_id: str,
        report_recheck_status: ReportRecheckStatus | None = None,
        exception_status: ExceptionSubjectStatus | None = None,
    ) -> TrustExplanation:
        return TrustExplanation(
            subject_type=subject_type,
            subject_id=subject_id,
            trust_tier=TrustTier.NOT_ASSESSED,
            trust_label=TRUST_LABELS[TrustTier.NOT_ASSESSED],
            trust_summary=(
                "No deterministic trust assessment is available for this item."
            ),
            risk_level=RiskLevel.UNKNOWN,
            risk_label=RISK_LABELS[RiskLevel.UNKNOWN],
            risk_summary="Risk has not been assessed from deterministic evidence.",
            routing_outcome=RoutingOutcome.NOT_ROUTED,
            routing_label=ROUTING_LABELS[RoutingOutcome.NOT_ROUTED],
            routing_summary="No autonomous routing decision is available.",
            ranking_influence_allowed=False,
            ranking_influence_decision=RankingInfluenceDecision.NOT_ASSESSED,
            ranking_influence_label=RANKING_LABELS[
                RankingInfluenceDecision.NOT_ASSESSED
            ],
            ranking_influence_reason=(
                "This item is not used in rankings because no deterministic "
                "ranking decision is available."
            ),
            user_facing_warnings=(
                UserFacingTrustWarning(
                    warning_code="NOT_ASSESSED",
                    severity="info",
                    title="Not assessed",
                    message="No deterministic trust assessment is available.",
                ),
            ),
            report_recheck_status=report_recheck_status,
            exception_status=exception_status,
        )


def _trust_summary(tier: TrustTier) -> str:
    return {
        TrustTier.TRUSTED: "This item has trusted, fresh, high-confidence evidence.",
        TrustTier.VERIFIED: "This item has been verified through backend evidence.",
        TrustTier.PARTNER_SUBMITTED: (
            "This item was submitted by a partner and has not been independently "
            "verified."
        ),
        TrustTier.UNVERIFIED_VISIBLE: (
            "This item is visible for awareness but has not been independently "
            "verified."
        ),
        TrustTier.LOW_CONFIDENCE: (
            "This is a low-confidence signal. It is visible for awareness, but "
            "excluded from scoring until stronger evidence is available."
        ),
        TrustTier.CONFLICTING: (
            "Conflicting source evidence was detected. This item is not currently "
            "used in rankings."
        ),
        TrustTier.STALE: (
            "The source may be outdated. This signal is not used in rankings unless "
            "refreshed and verified."
        ),
        TrustTier.QUARANTINED: (
            "This item is quarantined because deterministic checks found a serious "
            "trust issue."
        ),
        TrustTier.RANKING_INELIGIBLE: (
            "This item is excluded from rankings because it does not meet ranking "
            "evidence requirements."
        ),
        TrustTier.BLOCKED: "This item is blocked by deterministic trust checks.",
        TrustTier.NOT_ASSESSED: "No deterministic trust assessment is available.",
    }[tier]


def _risk_summary(risk: RiskLevel) -> str:
    return {
        RiskLevel.LOW: "No major risk signal was detected from available evidence.",
        RiskLevel.MEDIUM: "Use this item with caution and review its warnings.",
        RiskLevel.HIGH: "This item needs stronger evidence before relying on it.",
        RiskLevel.CRITICAL: "This item is blocked or quarantined for users.",
        RiskLevel.UNKNOWN: "Risk has not been assessed from deterministic evidence.",
    }[risk]


def _routing_summary(outcome: RoutingOutcome) -> str:
    return {
        RoutingOutcome.AUTO_ACCEPT_NON_RANKING: (
            "This item can be visible but remains separate from ranking influence."
        ),
        RoutingOutcome.VISIBLE_WITH_WARNING: (
            "This item can be visible, but warnings should be reviewed first."
        ),
        RoutingOutcome.NEEDS_MORE_EVIDENCE: (
            "This item needs stronger evidence before trust can be elevated."
        ),
        RoutingOutcome.AUTO_RECHECK: (
            "This item should be rechecked before relying on it."
        ),
        RoutingOutcome.AUTO_REJECT: "This item is rejected automatically.",
        RoutingOutcome.QUARANTINE: "This item is quarantined from normal use.",
        RoutingOutcome.BLOCKED: "This item is blocked from normal use.",
        RoutingOutcome.ESCALATE_EXCEPTION: (
            "This item requires rare exception handling, not normal approval."
        ),
        RoutingOutcome.NOT_ROUTED: "No autonomous routing decision is available.",
    }[outcome]


def _ranking_reason(
    routing: RiskRoutingDecisionResult | None,
    *,
    tier: TrustTier,
) -> str:
    if routing is None:
        return (
            "This item is not used in rankings because no deterministic ranking "
            "decision is available."
        )
    if routing.ranking_influence_allowed:
        return (
            "This item is used in rankings because deterministic trust and evidence "
            "requirements were met."
        )
    codes = set(routing.ranking_influence_reason_codes)
    if RankingInfluenceReasonCode.PARTNER_SUBMITTED_NOT_VERIFIED in codes:
        return (
            "Partner-submitted items are visible for awareness but excluded from "
            "rankings until stronger independent evidence is available."
        )
    if tier is TrustTier.LOW_CONFIDENCE or RankingInfluenceReasonCode.LOW_CONFIDENCE in codes:
        return (
            "This low-confidence signal is visible for awareness, but excluded "
            "from scoring until stronger evidence is available."
        )
    if (
        tier is TrustTier.CONFLICTING
        or RankingInfluenceReasonCode.CONFLICTING_EVIDENCE in codes
    ):
        return (
            "Conflicting source evidence was detected. This item is not currently "
            "used in rankings."
        )
    if tier is TrustTier.STALE or RankingInfluenceReasonCode.STALE_SOURCE in codes:
        return (
            "The source may be outdated. This signal is not used in rankings unless "
            "refreshed and verified."
        )
    if RankingInfluenceReasonCode.EVIDENCE_REQUIREMENTS_MISSING in codes:
        return (
            "This item is visible to users, but it is excluded from rankings because "
            "it does not meet evidence requirements."
        )
    return routing.ranking_influence_reason


def _user_facing_warnings(
    assessment: TrustAssessmentResult,
    routing: RiskRoutingDecisionResult | None,
) -> tuple[UserFacingTrustWarning, ...]:
    warnings: list[UserFacingTrustWarning] = []
    tier = assessment.trust_tier
    if tier is TrustTier.PARTNER_SUBMITTED:
        warnings.append(
            UserFacingTrustWarning(
                warning_code="PARTNER_SUBMITTED_NOT_VERIFIED",
                severity="info",
                title="Partner-submitted",
                message="This item has not been independently verified.",
            )
        )
    if tier is TrustTier.LOW_CONFIDENCE:
        warnings.append(
            UserFacingTrustWarning(
                warning_code="LOW_CONFIDENCE",
                severity="warning",
                title="Low confidence",
                message="This signal needs stronger evidence before ranking use.",
            )
        )
    if tier is TrustTier.CONFLICTING:
        warnings.append(
            UserFacingTrustWarning(
                warning_code="CONFLICTING_EVIDENCE",
                severity="warning",
                title="Conflicting source detected",
                message="This item is not currently used in rankings.",
            )
        )
    if tier is TrustTier.STALE:
        warnings.append(
            UserFacingTrustWarning(
                warning_code="STALE_SOURCE",
                severity="warning",
                title="Stale source",
                message="The source may be outdated.",
            )
        )
    if tier in {TrustTier.QUARANTINED, TrustTier.BLOCKED}:
        warnings.append(
            UserFacingTrustWarning(
                warning_code=tier.value.upper(),
                severity="critical",
                title=TRUST_LABELS[tier],
                message="This item is not available for normal ranking use.",
            )
        )
    if routing is not None and not routing.ranking_influence_allowed:
        warnings.append(
            UserFacingTrustWarning(
                warning_code="RANKING_INFLUENCE_DENIED",
                severity="info",
                title="Excluded from rankings",
                message=_ranking_reason(routing, tier=tier),
            )
        )
    for requirement in (
        *assessment.evidence_requirements_missing,
        *assessment.evidence_requirements_failed,
    ):
        warning = _requirement_warning(requirement.code)
        if warning is not None:
            warnings.append(warning)
    return tuple({warning.warning_code: warning for warning in warnings}.values())


def _requirement_warning(
    code: EvidenceRequirementCode,
) -> UserFacingTrustWarning | None:
    if code is EvidenceRequirementCode.SOURCE_PRESENT:
        return UserFacingTrustWarning(
            warning_code="SOURCE_MISSING",
            severity="warning",
            title="Source missing",
            message="Source evidence is missing or incomplete.",
        )
    if code is EvidenceRequirementCode.SOURCE_FRESH:
        return UserFacingTrustWarning(
            warning_code="SOURCE_FRESHNESS_UNCLEAR",
            severity="warning",
            title="Freshness unclear",
            message="Source freshness should be checked before relying on this item.",
        )
    if code is EvidenceRequirementCode.NO_CONFLICT_DETECTED:
        return UserFacingTrustWarning(
            warning_code="CONFLICT_CHECK_FAILED",
            severity="warning",
            title="Conflict check failed",
            message="A conflict signal was detected or could not be ruled out.",
        )
    if code is EvidenceRequirementCode.CONFIDENCE_SUFFICIENT:
        return UserFacingTrustWarning(
            warning_code="CONFIDENCE_INSUFFICIENT",
            severity="warning",
            title="Confidence insufficient",
            message="Available confidence metadata is not strong enough for ranking use.",
        )
    return None
