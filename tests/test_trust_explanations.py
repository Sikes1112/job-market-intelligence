from __future__ import annotations

from datetime import UTC, datetime

from backend.trust.explanations import (
    RANKING_LABELS,
    RISK_LABELS,
    ROUTING_LABELS,
    TRUST_LABELS,
    TrustExplanationService,
)
from backend.trust.risk import RiskRoutingService
from backend.trust.schemas import (
    RankingInfluenceDecision,
    RiskLevel,
    RoutingOutcome,
    TrustAssessmentSubjectType,
    TrustSubjectMetadata,
    TrustTier,
)
from backend.trust.service import TrustAssessmentService

NOW = datetime(2026, 7, 4, 12, tzinfo=UTC)


def test_explanation_label_contracts_are_stable() -> None:
    assert TRUST_LABELS[TrustTier.TRUSTED] == "Trusted source"
    assert TRUST_LABELS[TrustTier.VERIFIED] == "Verified"
    assert TRUST_LABELS[TrustTier.PARTNER_SUBMITTED] == "Partner-submitted"
    assert TRUST_LABELS[TrustTier.UNVERIFIED_VISIBLE] == "Not independently verified"
    assert TRUST_LABELS[TrustTier.LOW_CONFIDENCE] == "Low confidence"
    assert TRUST_LABELS[TrustTier.CONFLICTING] == "Conflicting source detected"
    assert TRUST_LABELS[TrustTier.STALE] == "Stale source"
    assert TRUST_LABELS[TrustTier.QUARANTINED] == "Quarantined"
    assert TRUST_LABELS[TrustTier.RANKING_INELIGIBLE] == "Excluded from rankings"
    assert TRUST_LABELS[TrustTier.BLOCKED] == "Blocked"
    assert TRUST_LABELS[TrustTier.NOT_ASSESSED] == "Not assessed"
    assert RISK_LABELS[RiskLevel.MEDIUM] == "Use with caution"
    assert ROUTING_LABELS[RoutingOutcome.VISIBLE_WITH_WARNING] == (
        "Visible with warning"
    )
    assert RANKING_LABELS[RankingInfluenceDecision.DENIED] == (
        "Excluded from rankings"
    )


def test_partner_submitted_explanation_is_visible_unverified_and_non_ranking() -> None:
    explanation = _explain(_subject("partner", partner=True))

    assert explanation.trust_tier is TrustTier.PARTNER_SUBMITTED
    assert explanation.trust_label == "Partner-submitted"
    assert "not been independently verified" in explanation.trust_summary
    assert explanation.ranking_influence_allowed is False
    assert explanation.ranking_influence_label == "Excluded from rankings"
    assert "visible for awareness" in explanation.ranking_influence_reason
    assert any(
        warning.warning_code == "PARTNER_SUBMITTED_NOT_VERIFIED"
        for warning in explanation.user_facing_warnings
    )


def test_low_confidence_conflicting_and_stale_copy_is_conservative() -> None:
    low = _explain(_subject("low", confidence_label="low"))
    conflict = _explain(_subject("conflict", conflict=True))
    stale = _explain(_subject("stale", stale=True))

    assert low.trust_tier is TrustTier.LOW_CONFIDENCE
    assert "visible for awareness" in low.trust_summary
    assert "excluded from scoring" in low.ranking_influence_reason
    assert conflict.trust_tier is TrustTier.CONFLICTING
    assert "not currently used in rankings" in conflict.ranking_influence_reason
    assert stale.trust_tier is TrustTier.STALE
    assert "outdated" in stale.ranking_influence_reason


def test_ranking_allowed_explanation_only_when_backend_decision_allows() -> None:
    allowed = _explain(_subject("verified"))
    denied = _explain(_subject("blocked", blocked=True))

    assert allowed.trust_tier is TrustTier.VERIFIED
    assert allowed.ranking_influence_allowed is True
    assert allowed.ranking_influence_decision is RankingInfluenceDecision.ALLOWED
    assert allowed.ranking_influence_label == "Used in rankings"
    assert "requirements were met" in allowed.ranking_influence_reason
    assert denied.ranking_influence_allowed is False
    assert denied.ranking_influence_label == "Excluded from rankings"


def test_missing_assessment_returns_safe_not_assessed_explanation() -> None:
    explanation = TrustExplanationService().not_assessed(
        subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
        subject_id="missing",
    )

    assert explanation.trust_tier is TrustTier.NOT_ASSESSED
    assert explanation.risk_level is RiskLevel.UNKNOWN
    assert explanation.routing_outcome is RoutingOutcome.NOT_ROUTED
    assert explanation.ranking_influence_allowed is False
    assert explanation.evidence_requirements_met == ()
    assert explanation.user_facing_warnings[0].warning_code == "NOT_ASSESSED"


def test_explanation_generation_is_deterministic_and_read_only() -> None:
    subject = _subject("partner", partner=True)
    before = subject.model_dump()

    first = _explain(subject)
    second = _explain(subject)

    assert first == second
    assert subject.model_dump() == before
    serialized = first.model_dump(mode="json")
    assert "internal_review_notes" not in str(serialized)
    assert "reviewer_identity" not in str(serialized)
    assert "admin" not in str(serialized).lower()


def _explain(subject: TrustSubjectMetadata):
    assessment = TrustAssessmentService(clock=lambda: NOW).assess(subject)
    routing = RiskRoutingService(clock=lambda: NOW).decide(assessment, subject)
    return TrustExplanationService().explain(
        assessment=assessment,
        routing=routing,
        subject_type=subject.subject_type,
        subject_id=subject.subject_id,
    )


def _subject(
    suffix: str,
    *,
    partner: bool = False,
    stale: bool = False,
    conflict: bool = False,
    blocked: bool = False,
    confidence_label: str = "high",
) -> TrustSubjectMetadata:
    return TrustSubjectMetadata(
        subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
        subject_id=f"subject_{suffix}",
        valid_fields=True,
        source_count=2,
        source_present=True,
        source_allowed=True,
        freshness_status="stale" if stale else "fresh",
        observation_date_valid=True,
        confidence_label=confidence_label,
        duplicate_detected=False,
        conflict_detected=conflict,
        independent_verification=not partner,
        partner_submitted=partner,
        partner_origin=partner,
        partner_verification_status="verified" if partner else None,
        partner_trust_tier="tier_1_verified_institutional" if partner else None,
        self_promotional=False,
        corroboration_count=2,
        claim_type_allowed=True,
        ranking_influence_allowed=False,
        blocked=blocked,
        stale=stale,
        verification_status="verified" if not partner else None,
        trust_label="verified" if not partner else "partner_submitted",
    )
