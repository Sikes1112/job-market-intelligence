"""Deterministic Layer 30B risk routing and ranking influence policy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.trust.schemas import (
    EvidenceRequirementCode,
    RankingInfluenceDecision,
    RankingInfluencePolicyResult,
    RankingInfluenceReasonCode,
    RiskClassificationResult,
    RiskLevel,
    RiskRoutingDecisionResult,
    RiskRoutingReasonCode,
    RoutingOutcome,
    TrustAssessmentResult,
    TrustSubjectMetadata,
    TrustTier,
)

_RANKING_DENIED_TIERS: frozenset[TrustTier] = frozenset(
    {
        TrustTier.PARTNER_SUBMITTED,
        TrustTier.LOW_CONFIDENCE,
        TrustTier.CONFLICTING,
        TrustTier.STALE,
        TrustTier.QUARANTINED,
        TrustTier.BLOCKED,
        TrustTier.RANKING_INELIGIBLE,
        TrustTier.NOT_ASSESSED,
        TrustTier.UNVERIFIED_VISIBLE,
    }
)

_RANKING_IGNORED_FAILED_REQUIREMENTS: frozenset[EvidenceRequirementCode] = frozenset(
    {
        # Existing metadata is frequently false because 30B is the first
        # deterministic allow/deny authority. The policy may allow only after
        # all other ranking-sensitive evidence passes.
        EvidenceRequirementCode.RANKING_EVIDENCE_SUFFICIENT,
    }
)


class RiskClassifier:
    """Classify risk from 30A trust and evidence results only."""

    def classify(
        self,
        assessment: TrustAssessmentResult,
        subject: TrustSubjectMetadata | None = None,
    ) -> RiskClassificationResult:
        tier = assessment.trust_tier
        reasons: list[str] = []
        codes: list[RiskRoutingReasonCode] = []

        if tier is TrustTier.BLOCKED or (subject is not None and subject.blocked):
            return _risk_result(
                assessment,
                RiskLevel.CRITICAL,
                RiskRoutingReasonCode.BLOCKED_POLICY_SIGNAL,
                "blocked_or_policy_signal",
            )
        if tier is TrustTier.QUARANTINED or (
            subject is not None and subject.quarantined
        ):
            return _risk_result(
                assessment,
                RiskLevel.CRITICAL,
                RiskRoutingReasonCode.CRITICAL_RISK_BLOCKED,
                "quarantine_signal",
            )
        if tier is TrustTier.CONFLICTING or _has_failed(
            assessment,
            EvidenceRequirementCode.NO_CONFLICT_DETECTED,
        ):
            return _risk_result(
                assessment,
                RiskLevel.HIGH,
                RiskRoutingReasonCode.CONFLICT_REQUIRES_QUARANTINE,
                "conflict_detected",
            )
        if tier is TrustTier.STALE or _has_failed(
            assessment,
            EvidenceRequirementCode.SOURCE_FRESH,
        ):
            return _risk_result(
                assessment,
                RiskLevel.HIGH,
                RiskRoutingReasonCode.STALE_RECHECK_REQUIRED,
                "stale_source_or_expired_metadata",
            )
        if _has_failed(assessment, EvidenceRequirementCode.NO_DUPLICATE_DETECTED):
            return _risk_result(
                assessment,
                RiskLevel.HIGH,
                RiskRoutingReasonCode.HIGH_RISK_MORE_EVIDENCE_REQUIRED,
                "duplicate_risk_detected",
            )
        if _has_failed(assessment, EvidenceRequirementCode.SOURCE_PRESENT):
            return _risk_result(
                assessment,
                RiskLevel.HIGH,
                RiskRoutingReasonCode.MISSING_EVIDENCE_NON_RANKING,
                "missing_required_source",
            )
        if _has_failed(assessment, EvidenceRequirementCode.SOURCE_ALLOWED):
            return _risk_result(
                assessment,
                RiskLevel.CRITICAL,
                RiskRoutingReasonCode.BLOCKED_POLICY_SIGNAL,
                "source_not_allowed",
            )
        if tier is TrustTier.NOT_ASSESSED:
            return _risk_result(
                assessment,
                RiskLevel.UNKNOWN,
                RiskRoutingReasonCode.MISSING_EVIDENCE_NON_RANKING,
                "insufficient_metadata_for_risk_classification",
            )
        if tier in {TrustTier.LOW_CONFIDENCE, TrustTier.RANKING_INELIGIBLE}:
            codes.append(RiskRoutingReasonCode.MEDIUM_RISK_WARNING_REQUIRED)
            reasons.append("low_confidence_or_ranking_ineligible_metadata")
        if _has_missing_or_failed_evidence(assessment):
            codes.append(RiskRoutingReasonCode.MISSING_EVIDENCE_NON_RANKING)
            reasons.append("evidence_requirements_missing_or_failed")
        if tier is TrustTier.PARTNER_SUBMITTED or (
            subject is not None and subject.partner_submitted
        ):
            codes.append(RiskRoutingReasonCode.PARTNER_SUBMISSION_NON_RANKING)
            reasons.append("partner_submission_visible_but_non_ranking")

        if codes:
            return RiskClassificationResult(
                subject_type=assessment.subject_type,
                subject_id=assessment.subject_id,
                trust_tier=tier,
                risk_level=RiskLevel.MEDIUM,
                reason_codes=tuple(dict.fromkeys(codes)),
                reasons=tuple(dict.fromkeys(reasons)),
            )
        return _risk_result(
            assessment,
            RiskLevel.LOW,
            RiskRoutingReasonCode.LOW_RISK_VISIBLE_NON_RANKING,
            "low_risk_deterministic_trust_metadata",
        )


class RankingInfluencePolicy:
    """Default-deny deterministic ranking influence policy."""

    def decide(
        self,
        assessment: TrustAssessmentResult | None,
        subject: TrustSubjectMetadata | None = None,
        *,
        public_demo_restricted: bool = False,
    ) -> RankingInfluencePolicyResult:
        if public_demo_restricted:
            return _ranking_denied(
                "Public-demo restrictions prevent ranking influence.",
                RankingInfluenceReasonCode.PUBLIC_DEMO_RESTRICTED,
            )
        if assessment is None:
            return _ranking_denied(
                "No deterministic Layer 30 assessment is available.",
                RankingInfluenceReasonCode.ASSESSMENT_MISSING,
            )

        tier = assessment.trust_tier
        if tier in _RANKING_DENIED_TIERS:
            return _ranking_denied(
                f"Trust tier {tier.value} is not eligible for ranking influence.",
                _denied_code_for_tier(tier),
            )
        if subject is not None and (subject.partner_submitted or subject.partner_origin):
            return _ranking_denied(
                "Partner-submitted or partner-origin evidence is not independently "
                "ranking-eligible by default.",
                RankingInfluenceReasonCode.PARTNER_SUBMITTED_NOT_VERIFIED,
            )
        if _has_failed(assessment, EvidenceRequirementCode.SOURCE_PRESENT):
            return _ranking_denied(
                "Ranking influence requires a present source.",
                RankingInfluenceReasonCode.MISSING_SOURCE,
            )
        if _has_failed(assessment, EvidenceRequirementCode.SOURCE_ALLOWED):
            return _ranking_denied(
                "Ranking influence requires an allowed source.",
                RankingInfluenceReasonCode.SOURCE_NOT_ALLOWED,
            )
        if _has_failed(assessment, EvidenceRequirementCode.SOURCE_FRESH):
            return _ranking_denied(
                "Ranking influence requires fresh source evidence.",
                RankingInfluenceReasonCode.STALE_SOURCE,
            )
        if _has_failed(assessment, EvidenceRequirementCode.CONFIDENCE_SUFFICIENT):
            return _ranking_denied(
                "Ranking influence requires sufficient confidence.",
                RankingInfluenceReasonCode.LOW_CONFIDENCE,
            )
        if _has_failed(assessment, EvidenceRequirementCode.NO_CONFLICT_DETECTED):
            return _ranking_denied(
                "Ranking influence requires no unresolved conflict signal.",
                RankingInfluenceReasonCode.CONFLICTING_EVIDENCE,
            )
        if _has_failed(assessment, EvidenceRequirementCode.NO_DUPLICATE_DETECTED):
            return _ranking_denied(
                "Ranking influence requires no duplicate-risk signal.",
                RankingInfluenceReasonCode.DUPLICATE_RISK,
            )
        if _has_failed(assessment, EvidenceRequirementCode.NOT_SELF_PROMOTIONAL):
            return _ranking_denied(
                "Self-promotional source metadata cannot influence rankings.",
                RankingInfluenceReasonCode.SELF_PROMOTIONAL_SOURCE,
            )
        if _has_failed(assessment, EvidenceRequirementCode.CORROBORATION_PRESENT):
            return _ranking_denied(
                "Ranking influence requires corroborating evidence.",
                RankingInfluenceReasonCode.CORROBORATION_MISSING,
            )
        if _has_failed(assessment, EvidenceRequirementCode.CLAIM_TYPE_ALLOWED):
            return _ranking_denied(
                "Ranking influence requires an allowed claim type.",
                RankingInfluenceReasonCode.CLAIM_TYPE_NOT_ALLOWED,
            )
        remaining_failures = tuple(
            result
            for result in assessment.evidence_requirements_failed
            if result.code not in _RANKING_IGNORED_FAILED_REQUIREMENTS
        )
        if remaining_failures or assessment.evidence_requirements_missing:
            return _ranking_denied(
                "Ranking influence requires all required deterministic evidence to be present.",
                RankingInfluenceReasonCode.EVIDENCE_REQUIREMENTS_MISSING,
            )
        if tier is TrustTier.TRUSTED:
            return RankingInfluencePolicyResult(
                decision=RankingInfluenceDecision.ALLOWED,
                ranking_influence_allowed=True,
                reason=(
                    "Trusted, fresh, high-confidence evidence passed deterministic "
                    "ranking requirements."
                ),
                reason_codes=(
                    RankingInfluenceReasonCode.TRUSTED_FRESH_HIGH_CONFIDENCE,
                ),
            )
        if tier is TrustTier.VERIFIED:
            return RankingInfluencePolicyResult(
                decision=RankingInfluenceDecision.ALLOWED,
                ranking_influence_allowed=True,
                reason=(
                    "Verified, fresh, non-conflicting evidence passed deterministic "
                    "ranking requirements."
                ),
                reason_codes=(RankingInfluenceReasonCode.VERIFIED_FRESH_NO_CONFLICT,),
            )
        return _ranking_denied(
            "Ranking influence is denied by default without a deterministic allow rule.",
            RankingInfluenceReasonCode.RANKING_DEFAULT_DENIED,
        )


class RiskRoutingService:
    """Assign autonomous routing and ranking outcomes from trust evidence."""

    def __init__(
        self,
        classifier: RiskClassifier | None = None,
        ranking_policy: RankingInfluencePolicy | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._classifier = classifier or RiskClassifier()
        self._ranking_policy = ranking_policy or RankingInfluencePolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def decide(
        self,
        assessment: TrustAssessmentResult,
        subject: TrustSubjectMetadata | None = None,
        *,
        public_demo_restricted: bool = False,
    ) -> RiskRoutingDecisionResult:
        classification = self._classifier.classify(assessment, subject)
        ranking = self._ranking_policy.decide(
            assessment,
            subject,
            public_demo_restricted=public_demo_restricted,
        )
        outcome = _routing_outcome(classification)
        return RiskRoutingDecisionResult(
            subject_type=assessment.subject_type,
            subject_id=assessment.subject_id,
            trust_tier=assessment.trust_tier,
            risk_level=classification.risk_level,
            routing_outcome=outcome,
            routing_reasons=classification.reason_codes,
            ranking_influence_decision=ranking.decision,
            ranking_influence_allowed=ranking.ranking_influence_allowed,
            ranking_influence_reason=ranking.reason,
            ranking_influence_reason_codes=ranking.reason_codes,
            evidence_requirements_met=assessment.evidence_requirements_met,
            evidence_requirements_missing=assessment.evidence_requirements_missing,
            evidence_requirements_failed=assessment.evidence_requirements_failed,
            warnings=assessment.warnings,
            decided_at=self._clock(),
        )


def _risk_result(
    assessment: TrustAssessmentResult,
    risk_level: RiskLevel,
    code: RiskRoutingReasonCode,
    reason: str,
) -> RiskClassificationResult:
    return RiskClassificationResult(
        subject_type=assessment.subject_type,
        subject_id=assessment.subject_id,
        trust_tier=assessment.trust_tier,
        risk_level=risk_level,
        reason_codes=(code,),
        reasons=(reason,),
    )


def _routing_outcome(classification: RiskClassificationResult) -> RoutingOutcome:
    if classification.risk_level is RiskLevel.CRITICAL:
        if RiskRoutingReasonCode.BLOCKED_POLICY_SIGNAL in classification.reason_codes:
            return RoutingOutcome.BLOCKED
        return RoutingOutcome.QUARANTINE
    if classification.risk_level is RiskLevel.HIGH:
        if (
            RiskRoutingReasonCode.CONFLICT_REQUIRES_QUARANTINE
            in classification.reason_codes
        ):
            return RoutingOutcome.QUARANTINE
        if RiskRoutingReasonCode.STALE_RECHECK_REQUIRED in classification.reason_codes:
            return RoutingOutcome.AUTO_RECHECK
        return RoutingOutcome.NEEDS_MORE_EVIDENCE
    if classification.risk_level is RiskLevel.MEDIUM:
        return RoutingOutcome.VISIBLE_WITH_WARNING
    if classification.risk_level is RiskLevel.LOW:
        return RoutingOutcome.AUTO_ACCEPT_NON_RANKING
    return RoutingOutcome.NOT_ROUTED


def _ranking_denied(
    reason: str,
    *codes: RankingInfluenceReasonCode,
) -> RankingInfluencePolicyResult:
    return RankingInfluencePolicyResult(
        decision=RankingInfluenceDecision.DENIED,
        ranking_influence_allowed=False,
        reason=reason,
        reason_codes=tuple(
            dict.fromkeys((*codes, RankingInfluenceReasonCode.RANKING_DEFAULT_DENIED))
        ),
    )


def _denied_code_for_tier(tier: TrustTier) -> RankingInfluenceReasonCode:
    if tier is TrustTier.PARTNER_SUBMITTED:
        return RankingInfluenceReasonCode.PARTNER_SUBMITTED_NOT_VERIFIED
    if tier is TrustTier.STALE:
        return RankingInfluenceReasonCode.STALE_SOURCE
    if tier is TrustTier.LOW_CONFIDENCE:
        return RankingInfluenceReasonCode.LOW_CONFIDENCE
    if tier is TrustTier.CONFLICTING:
        return RankingInfluenceReasonCode.CONFLICTING_EVIDENCE
    if tier in {TrustTier.QUARANTINED, TrustTier.BLOCKED}:
        return RankingInfluenceReasonCode.BLOCKED_OR_QUARANTINED
    if tier is TrustTier.NOT_ASSESSED:
        return RankingInfluenceReasonCode.LEGACY_UNASSESSED
    return RankingInfluenceReasonCode.RANKING_DEFAULT_DENIED


def _has_failed(
    assessment: TrustAssessmentResult,
    code: EvidenceRequirementCode,
) -> bool:
    return any(result.code is code for result in assessment.evidence_requirements_failed)


def _has_missing_or_failed_evidence(assessment: TrustAssessmentResult) -> bool:
    failures = tuple(
        result
        for result in assessment.evidence_requirements_failed
        if result.code not in _RANKING_IGNORED_FAILED_REQUIREMENTS
    )
    return bool(assessment.evidence_requirements_missing or failures)
