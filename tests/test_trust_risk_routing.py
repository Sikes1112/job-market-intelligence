from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.trust.repository import TrustAssessmentRepository
from backend.trust.risk import (
    RankingInfluencePolicy,
    RiskClassifier,
    RiskRoutingService,
)
from backend.trust.schemas import (
    RankingInfluenceDecision,
    RankingInfluenceReasonCode,
    RiskLevel,
    RiskRoutingReasonCode,
    RoutingOutcome,
    TrustAssessmentSubjectType,
    TrustSubjectMetadata,
    TrustTier,
)
from backend.trust.service import TrustAssessmentService

NOW = datetime(2026, 7, 3, 12, tzinfo=UTC)


def test_risk_and_ranking_contract_enums_are_stable() -> None:
    assert RiskLevel.values() == {"low", "medium", "high", "critical", "unknown"}
    assert RoutingOutcome.values() == {
        "auto_accept_non_ranking",
        "visible_with_warning",
        "needs_more_evidence",
        "auto_recheck",
        "auto_reject",
        "quarantine",
        "blocked",
        "escalate_exception",
        "not_routed",
    }
    assert RankingInfluenceDecision.values() == {
        "allowed",
        "denied",
        "not_applicable",
        "not_assessed",
    }
    assert "partner_submitted_not_verified" in RankingInfluenceReasonCode.values()
    assert "conflict_requires_quarantine" in RiskRoutingReasonCode.values()


def test_risk_classifier_is_deterministic_for_supported_tiers() -> None:
    service = TrustAssessmentService(clock=lambda: NOW)
    classifier = RiskClassifier()

    low = classifier.classify(service.assess(_subject("verified")))
    partner = classifier.classify(service.assess(_subject("partner", partner=True)))
    stale = classifier.classify(service.assess(_subject("stale", stale=True)))
    conflict = classifier.classify(service.assess(_subject("conflict", conflict=True)))
    blocked = classifier.classify(service.assess(_subject("blocked", blocked=True)))

    assert low.risk_level is RiskLevel.LOW
    assert partner.risk_level is RiskLevel.MEDIUM
    assert stale.risk_level is RiskLevel.HIGH
    assert conflict.risk_level is RiskLevel.HIGH
    assert blocked.risk_level is RiskLevel.CRITICAL
    assert classifier.classify(service.assess(_subject("verified"))) == low


def test_ranking_influence_policy_defaults_false_and_allows_only_strict_evidence() -> None:
    service = TrustAssessmentService(clock=lambda: NOW)
    policy = RankingInfluencePolicy()

    assert policy.decide(None).ranking_influence_allowed is False
    verified_subject = _subject("verified")
    verified = service.assess(verified_subject)
    allowed = policy.decide(verified, verified_subject)

    assert verified.trust_tier is TrustTier.VERIFIED
    assert allowed.decision is RankingInfluenceDecision.ALLOWED
    assert allowed.ranking_influence_allowed is True
    assert (
        RankingInfluenceReasonCode.VERIFIED_FRESH_NO_CONFLICT
        in allowed.reason_codes
    )

    for subject in (
        _subject("partner", partner=True),
        _subject("stale", stale=True),
        _subject("low", confidence_label="low"),
        _subject("conflict", conflict=True),
        _subject("blocked", blocked=True),
        _subject("self_promo", self_promotional=True),
    ):
        assessment = service.assess(subject)
        decision = policy.decide(assessment, subject)
        assert decision.ranking_influence_allowed is False
        assert decision.decision is RankingInfluenceDecision.DENIED


def test_risk_routing_service_is_read_only_and_defaults_non_ranking() -> None:
    subject = _subject("partner", partner=True)
    assessment = TrustAssessmentService(clock=lambda: NOW).assess(subject)
    before = subject.model_dump()

    decision = RiskRoutingService(clock=lambda: NOW).decide(assessment, subject)

    assert subject.model_dump() == before
    assert decision.risk_level is RiskLevel.MEDIUM
    assert decision.routing_outcome is RoutingOutcome.VISIBLE_WITH_WARNING
    assert decision.ranking_influence_allowed is False
    assert decision.ranking_influence_decision is RankingInfluenceDecision.DENIED
    assert (
        RiskRoutingReasonCode.PARTNER_SUBMISSION_NON_RANKING
        in decision.routing_reasons
    )


def test_routing_decision_persistence_round_trips_json(session: Session) -> None:
    subject = _subject("persisted", stale=True)
    assessment = TrustAssessmentService(clock=lambda: NOW).assess(subject)
    decision = RiskRoutingService(clock=lambda: NOW).decide(assessment, subject)
    repo = TrustAssessmentRepository(session)

    row = repo.add_routing_decision(
        decision,
        risk_routing_decision_id="risk_route_test",
    )
    session.flush()
    loaded = repo.latest_routing_for_subject(
        subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
        subject_id="subject_persisted",
    )

    assert row.risk_routing_decision_id == "risk_route_test"
    assert loaded is not None
    assert loaded.risk_level is RiskLevel.HIGH
    assert loaded.routing_outcome is RoutingOutcome.AUTO_RECHECK
    assert loaded.ranking_influence_allowed is False
    assert loaded.evidence_requirements_failed


def _subject(
    suffix: str,
    *,
    partner: bool = False,
    stale: bool = False,
    conflict: bool = False,
    blocked: bool = False,
    confidence_label: str = "high",
    self_promotional: bool = False,
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
        self_promotional=self_promotional,
        corroboration_count=2,
        claim_type_allowed=True,
        ranking_influence_allowed=False,
        blocked=blocked,
        stale=stale,
        verification_status="verified" if not partner else None,
        trust_label="verified" if not partner else "partner_submitted",
    )
