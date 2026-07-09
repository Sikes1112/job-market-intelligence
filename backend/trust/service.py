"""Deterministic Layer 30A trust tier assignment."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.trust.evidence import EvidenceRequirementsEngine
from backend.trust.schemas import (
    EvidenceEvaluationResult,
    EvidenceRequirementCode,
    EvidenceRequirementStatus,
    TrustAssessmentResult,
    TrustSubjectMetadata,
    TrustTier,
    TrustWarning,
)

TRUST_TIER_PRECEDENCE: tuple[TrustTier, ...] = (
    TrustTier.BLOCKED,
    TrustTier.QUARANTINED,
    TrustTier.CONFLICTING,
    TrustTier.STALE,
    TrustTier.PARTNER_SUBMITTED,
    TrustTier.LOW_CONFIDENCE,
    TrustTier.VERIFIED,
    TrustTier.TRUSTED,
    TrustTier.UNVERIFIED_VISIBLE,
    TrustTier.RANKING_INELIGIBLE,
    TrustTier.NOT_ASSESSED,
)


class TrustAssessmentService:
    """Classify trust from existing metadata and evidence results.

    Assessment is intentionally pure: it does not persist, mutate subject rows,
    change visibility, or alter ranking flags. Persistence is available through
    ``backend.trust.repository`` for explicit callers that want an assessment
    audit row.
    """

    def __init__(
        self,
        evidence_engine: EvidenceRequirementsEngine | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._evidence_engine = evidence_engine or EvidenceRequirementsEngine()
        self._clock = clock or (lambda: datetime.now(UTC))

    def assess(self, subject: TrustSubjectMetadata) -> TrustAssessmentResult:
        evidence = self._evidence_engine.evaluate(subject)
        trust_tier, reasons = _assign_trust_tier(subject, evidence)
        warnings = _dedupe_warnings(
            (
                *evidence.warnings,
                *_trust_warnings_from_subject(subject),
                *_trust_warning_for_tier(trust_tier, subject),
            )
        )
        return TrustAssessmentResult(
            subject_type=subject.subject_type,
            subject_id=subject.subject_id,
            trust_tier=trust_tier,
            evidence_requirements_met=evidence.met,
            evidence_requirements_missing=evidence.missing,
            evidence_requirements_failed=evidence.failed,
            evidence_requirements_not_applicable=evidence.not_applicable,
            warnings=warnings,
            reasons=tuple(dict.fromkeys((*reasons, *evidence.reasons))),
            ranking_influence_allowed=subject.ranking_influence_allowed,
            assessed_at=self._clock(),
        )


def _assign_trust_tier(
    subject: TrustSubjectMetadata,
    evidence: EvidenceEvaluationResult,
) -> tuple[TrustTier, tuple[str, ...]]:
    candidates: list[tuple[TrustTier, str]] = []
    trust_label = _clean(subject.trust_label)
    review_status = _clean(subject.review_status)
    quality_label = _clean(subject.quality_label)
    verification_status = _clean(subject.verification_status)
    confidence = _clean(subject.confidence_label)
    freshness = _clean(subject.freshness_status)
    partner_verification = _clean(subject.partner_verification_status)
    partner_tier = _clean(subject.partner_trust_tier)

    if (
        subject.blocked
        or trust_label == "rejected"
        or review_status == "rejected"
        or partner_verification in {"revoked", "suspended"}
        or partner_tier == "untrusted"
    ):
        candidates.append((TrustTier.BLOCKED, "blocked_or_rejected_metadata"))
    if (
        subject.quarantined
        or review_status in {"needs_correction", "needs_review"}
        or quality_label == "blocked"
    ):
        candidates.append((TrustTier.QUARANTINED, "quarantine_like_metadata"))
    if subject.conflict_detected or _contains(subject.warnings, "conflict"):
        candidates.append((TrustTier.CONFLICTING, "conflict_detected"))
    if (
        subject.stale
        or subject.expired
        or freshness == "stale"
        or trust_label == "expired"
        or review_status == "expired"
    ):
        candidates.append((TrustTier.STALE, "stale_or_expired_metadata"))
    if subject.partner_submitted:
        candidates.append((TrustTier.PARTNER_SUBMITTED, "partner_submitted_metadata"))
    elif subject.partner_origin and not _strong_partner_trust(subject):
        candidates.append((TrustTier.PARTNER_SUBMITTED, "partner_origin_not_verified"))
    if (
        confidence in {"low", "unknown"}
        or quality_label == "low_confidence_signal"
        or _has_failed(evidence, EvidenceRequirementCode.CONFIDENCE_SUFFICIENT)
        or _has_missing(evidence, EvidenceRequirementCode.SOURCE_PRESENT)
        or _has_failed(evidence, EvidenceRequirementCode.VALID_FIELDS)
    ):
        candidates.append((TrustTier.LOW_CONFIDENCE, "low_confidence_or_weak_evidence"))
    if _verified_signal(
        trust_label=trust_label,
        review_status=review_status,
        verification_status=verification_status,
        partner_verification=partner_verification,
        partner_tier=partner_tier,
        subject=subject,
    ):
        candidates.append((TrustTier.VERIFIED, "verified_metadata"))
    if _trusted_signal(
        confidence=confidence,
        freshness=freshness,
        quality_label=quality_label,
        partner_verification=partner_verification,
        partner_tier=partner_tier,
        evidence=evidence,
    ):
        candidates.append((TrustTier.TRUSTED, "trusted_evidence_metadata"))
    if (
        _has_met(evidence, EvidenceRequirementCode.SOURCE_PRESENT)
        and not candidates
    ):
        candidates.append((TrustTier.UNVERIFIED_VISIBLE, "visible_with_source_metadata"))
    if (
        subject.ranking_influence_allowed is False
        and not candidates
        and _has_failed(evidence, EvidenceRequirementCode.RANKING_EVIDENCE_SUFFICIENT)
    ):
        candidates.append((TrustTier.RANKING_INELIGIBLE, "ranking_ineligible_metadata"))

    if not candidates:
        return TrustTier.NOT_ASSESSED, ("insufficient_metadata_for_trust_assessment",)

    for tier in TRUST_TIER_PRECEDENCE:
        reasons = tuple(reason for candidate, reason in candidates if candidate is tier)
        if reasons:
            return tier, reasons
    return TrustTier.NOT_ASSESSED, ("insufficient_metadata_for_trust_assessment",)


def _trusted_signal(
    *,
    confidence: str | None,
    freshness: str | None,
    quality_label: str | None,
    partner_verification: str | None,
    partner_tier: str | None,
    evidence: EvidenceEvaluationResult,
) -> bool:
    strong_partner = (
        partner_verification == "verified"
        and partner_tier
        in {"tier_1_verified_institutional", "tier_2_verified_regional"}
    )
    strong_quality = quality_label in {
        "audited_source_data",
        "public_source_verified",
        "verified_partner_data",
    }
    return (
        confidence == "high"
        and freshness == "fresh"
        and _has_met(evidence, EvidenceRequirementCode.SOURCE_PRESENT)
        and _has_met(evidence, EvidenceRequirementCode.NO_CONFLICT_DETECTED)
        and (strong_partner or strong_quality)
    )


def _verified_signal(
    *,
    trust_label: str | None,
    review_status: str | None,
    verification_status: str | None,
    partner_verification: str | None,
    partner_tier: str | None,
    subject: TrustSubjectMetadata,
) -> bool:
    if trust_label in {"verified", "source_checked"}:
        return True
    if review_status in {"approved", "source_checked"}:
        return True
    if verification_status in {"verified", "source_checked", "approved"}:
        return True
    if subject.independent_verification:
        return True
    return (
        partner_verification == "verified"
        and partner_tier
        in {
            "tier_1_verified_institutional",
            "tier_2_verified_regional",
            "tier_3_verified_platform",
        }
    )


def _strong_partner_trust(subject: TrustSubjectMetadata) -> bool:
    return (
        _clean(subject.partner_verification_status) == "verified"
        and _clean(subject.partner_trust_tier)
        in {
            "tier_1_verified_institutional",
            "tier_2_verified_regional",
            "tier_3_verified_platform",
        }
    )


def _has_met(
    evidence: EvidenceEvaluationResult,
    code: EvidenceRequirementCode,
) -> bool:
    return any(
        result.code is code and result.status is EvidenceRequirementStatus.MET
        for result in evidence.requirements
    )


def _has_missing(
    evidence: EvidenceEvaluationResult,
    code: EvidenceRequirementCode,
) -> bool:
    return any(
        result.code is code and result.status is EvidenceRequirementStatus.MISSING
        for result in evidence.requirements
    )


def _has_failed(
    evidence: EvidenceEvaluationResult,
    code: EvidenceRequirementCode,
) -> bool:
    return any(
        result.code is code and result.status is EvidenceRequirementStatus.FAILED
        for result in evidence.requirements
    )


def _trust_warnings_from_subject(
    subject: TrustSubjectMetadata,
) -> tuple[TrustWarning, ...]:
    warnings: list[TrustWarning] = []
    for index, warning in enumerate(subject.warnings):
        warnings.append(
            TrustWarning(
                warning_code=f"subject_warning_{index + 1}",
                severity=_warning_severity(warning),
                message=warning,
                source="subject_metadata",
            )
        )
    return tuple(warnings)


def _trust_warning_for_tier(
    trust_tier: TrustTier,
    subject: TrustSubjectMetadata,
) -> tuple[TrustWarning, ...]:
    if trust_tier in {
        TrustTier.TRUSTED,
        TrustTier.VERIFIED,
        TrustTier.NOT_ASSESSED,
        TrustTier.UNVERIFIED_VISIBLE,
    }:
        return ()
    return (
        TrustWarning(
            warning_code=f"trust_tier_{trust_tier.value}",
            severity="critical"
            if trust_tier in {TrustTier.BLOCKED, TrustTier.QUARANTINED}
            else "warning",
            message=f"Deterministic trust tier is {trust_tier.value}.",
            source=subject.subject_type.value,
        ),
    )


def _warning_severity(message: str) -> str:
    lowered = message.casefold()
    if any(token in lowered for token in ("blocked", "rejected", "revoked")):
        return "critical"
    if any(
        token in lowered
        for token in ("conflict", "stale", "low", "missing", "unverified")
    ):
        return "warning"
    return "info"


def _dedupe_warnings(warnings: tuple[TrustWarning, ...]) -> tuple[TrustWarning, ...]:
    deduped: list[TrustWarning] = []
    seen: set[tuple[str, str, str]] = set()
    for warning in warnings:
        key = (warning.warning_code, warning.message, warning.source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return tuple(deduped)


def _contains(values: tuple[str, ...], token: str) -> bool:
    lowered = token.casefold()
    return any(lowered in value.casefold() for value in values)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().casefold()
    return stripped or None
