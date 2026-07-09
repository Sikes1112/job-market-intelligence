"""Deterministic Layer 30A evidence requirement evaluation."""

from __future__ import annotations

from backend.trust.schemas import (
    EvidenceEvaluationResult,
    EvidenceRequirementCode,
    EvidenceRequirementResult,
    EvidenceRequirementStatus,
    TrustSubjectMetadata,
    TrustWarning,
)


class EvidenceRequirementsEngine:
    """Evaluate evidence readiness from already-available metadata.

    The engine performs no network calls, model calls, writes, or canonical
    state transitions. It only classifies existing metadata into structured
    requirement results.
    """

    def evaluate(self, subject: TrustSubjectMetadata) -> EvidenceEvaluationResult:
        requirements = (
            _valid_fields(subject),
            _source_present(subject),
            _source_allowed(subject),
            _source_fresh(subject),
            _observation_date_valid(subject),
            _confidence_sufficient(subject),
            _no_duplicate_detected(subject),
            _no_conflict_detected(subject),
            _independent_verification(subject),
            _partner_trust_sufficient(subject),
            _not_self_promotional(subject),
            _corroboration_present(subject),
            _claim_type_allowed(subject),
            _ranking_evidence_sufficient(subject),
        )
        warnings = tuple(_warning_for_requirement(result) for result in requirements)
        warnings = tuple(warning for warning in warnings if warning is not None)
        reasons = tuple(
            result.code.value
            for result in requirements
            if result.status in {
                EvidenceRequirementStatus.MISSING,
                EvidenceRequirementStatus.FAILED,
            }
        )
        return EvidenceEvaluationResult(
            subject_type=subject.subject_type,
            subject_id=subject.subject_id,
            requirements=requirements,
            warnings=warnings,
            reasons=reasons,
        )


def _valid_fields(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _boolean_requirement(
        EvidenceRequirementCode.VALID_FIELDS,
        subject.valid_fields,
        missing_message="Required fields were not available to assess.",
        failed_message="Required fields are incomplete or invalid.",
        met_message="Required fields are present.",
        source="subject_metadata",
    )


def _source_present(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    present = subject.source_present
    if present is None and subject.source_count is not None:
        present = subject.source_count > 0
    return _boolean_requirement(
        EvidenceRequirementCode.SOURCE_PRESENT,
        present,
        missing_message="No source evidence was present.",
        failed_message="Source evidence is explicitly absent.",
        met_message="Source evidence is present.",
        source="source_metadata",
    )


def _source_allowed(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _boolean_requirement(
        EvidenceRequirementCode.SOURCE_ALLOWED,
        subject.source_allowed,
        missing_message="Source policy could not be evaluated.",
        failed_message="Source policy does not allow this source for trust elevation.",
        met_message="Source policy allows this source.",
        source="source_policy_metadata",
        none_status=EvidenceRequirementStatus.NOT_APPLICABLE,
    )


def _source_fresh(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    freshness = _clean(subject.freshness_status)
    if freshness is None:
        return _requirement(
            EvidenceRequirementCode.SOURCE_FRESH,
            EvidenceRequirementStatus.NOT_APPLICABLE,
            "Freshness metadata is not available for this subject.",
            "freshness_metadata",
        )
    if freshness == "fresh":
        return _requirement(
            EvidenceRequirementCode.SOURCE_FRESH,
            EvidenceRequirementStatus.MET,
            "Source freshness is fresh.",
            "freshness_metadata",
        )
    if freshness == "stale":
        return _requirement(
            EvidenceRequirementCode.SOURCE_FRESH,
            EvidenceRequirementStatus.FAILED,
            "Source freshness is stale.",
            "freshness_metadata",
        )
    return _requirement(
        EvidenceRequirementCode.SOURCE_FRESH,
        EvidenceRequirementStatus.MISSING,
        f"Source freshness is {freshness}.",
        "freshness_metadata",
    )


def _observation_date_valid(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _boolean_requirement(
        EvidenceRequirementCode.OBSERVATION_DATE_VALID,
        subject.observation_date_valid,
        missing_message="Observation date is missing or not validated.",
        failed_message="Observation date is invalid.",
        met_message="Observation date is valid.",
        source="observation_metadata",
        none_status=EvidenceRequirementStatus.NOT_APPLICABLE,
    )


def _confidence_sufficient(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    label = _clean(subject.confidence_label)
    score = subject.confidence_score
    if score is not None:
        if score >= 0.7:
            return _requirement(
                EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
                EvidenceRequirementStatus.MET,
                "Confidence score is sufficient.",
                "confidence_metadata",
            )
        if score < 0.5:
            return _requirement(
                EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
                EvidenceRequirementStatus.FAILED,
                "Confidence score is below the trust threshold.",
                "confidence_metadata",
            )
    if label in {"high", "medium"}:
        return _requirement(
            EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
            EvidenceRequirementStatus.MET,
            "Confidence label is sufficient.",
            "confidence_metadata",
        )
    if label == "low":
        return _requirement(
            EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
            EvidenceRequirementStatus.FAILED,
            "Confidence label is low.",
            "confidence_metadata",
        )
    if label is None:
        return _requirement(
            EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
            EvidenceRequirementStatus.NOT_APPLICABLE,
            "Confidence metadata is not available for this subject.",
            "confidence_metadata",
        )
    return _requirement(
        EvidenceRequirementCode.CONFIDENCE_SUFFICIENT,
        EvidenceRequirementStatus.MISSING,
        f"Confidence label is {label}.",
        "confidence_metadata",
    )


def _no_duplicate_detected(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _negative_boolean_requirement(
        EvidenceRequirementCode.NO_DUPLICATE_DETECTED,
        subject.duplicate_detected,
        missing_message="Duplicate detection was not available.",
        failed_message="Duplicate signal was detected.",
        met_message="No duplicate signal was detected.",
        source="duplicate_metadata",
    )


def _no_conflict_detected(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    conflict = subject.conflict_detected
    if conflict is None:
        conflict = _contains_token(subject.warnings, "conflict")
    return _negative_boolean_requirement(
        EvidenceRequirementCode.NO_CONFLICT_DETECTED,
        conflict,
        missing_message="Conflict detection was not available.",
        failed_message="Conflict signal was detected.",
        met_message="No conflict signal was detected.",
        source="conflict_metadata",
    )


def _independent_verification(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    verified = subject.independent_verification
    if verified is None:
        verified = _clean(subject.verification_status) in {
            "verified",
            "source_checked",
            "approved",
        } or _clean(subject.trust_label) in {"verified", "source_checked"}
    return _boolean_requirement(
        EvidenceRequirementCode.INDEPENDENT_VERIFICATION,
        verified,
        missing_message="Independent verification is missing.",
        failed_message="Independent verification explicitly failed.",
        met_message="Independent verification is present.",
        source="verification_metadata",
    )


def _partner_trust_sufficient(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    if not subject.partner_origin and not subject.partner_submitted:
        return _requirement(
            EvidenceRequirementCode.PARTNER_TRUST_SUFFICIENT,
            EvidenceRequirementStatus.NOT_APPLICABLE,
            "Partner trust is not applicable for this subject.",
            "partner_metadata",
        )
    verification = _clean(subject.partner_verification_status)
    tier = _clean(subject.partner_trust_tier)
    if verification in {"revoked", "suspended"} or tier == "untrusted":
        return _requirement(
            EvidenceRequirementCode.PARTNER_TRUST_SUFFICIENT,
            EvidenceRequirementStatus.FAILED,
            "Partner trust metadata is revoked, suspended, or untrusted.",
            "partner_metadata",
        )
    if verification == "verified" and tier in {
        "tier_1_verified_institutional",
        "tier_2_verified_regional",
        "tier_3_verified_platform",
    }:
        return _requirement(
            EvidenceRequirementCode.PARTNER_TRUST_SUFFICIENT,
            EvidenceRequirementStatus.MET,
            "Partner trust metadata is sufficient.",
            "partner_metadata",
        )
    return _requirement(
        EvidenceRequirementCode.PARTNER_TRUST_SUFFICIENT,
        EvidenceRequirementStatus.MISSING,
        "Partner trust metadata is limited or unverified.",
        "partner_metadata",
    )


def _not_self_promotional(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _negative_boolean_requirement(
        EvidenceRequirementCode.NOT_SELF_PROMOTIONAL,
        subject.self_promotional,
        missing_message="Self-promotional status was not available.",
        failed_message="Self-promotional signal was detected.",
        met_message="No self-promotional signal was detected.",
        source="source_metadata",
    )


def _corroboration_present(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    count = subject.corroboration_count
    if count is None:
        return _requirement(
            EvidenceRequirementCode.CORROBORATION_PRESENT,
            EvidenceRequirementStatus.NOT_APPLICABLE,
            "Corroboration metadata is not available for this subject.",
            "corroboration_metadata",
        )
    if count >= 2:
        return _requirement(
            EvidenceRequirementCode.CORROBORATION_PRESENT,
            EvidenceRequirementStatus.MET,
            "Corroborating evidence is present.",
            "corroboration_metadata",
        )
    return _requirement(
        EvidenceRequirementCode.CORROBORATION_PRESENT,
        EvidenceRequirementStatus.MISSING,
        "Corroborating evidence is missing or insufficient.",
        "corroboration_metadata",
    )


def _claim_type_allowed(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    return _boolean_requirement(
        EvidenceRequirementCode.CLAIM_TYPE_ALLOWED,
        subject.claim_type_allowed,
        missing_message="Claim type policy could not be evaluated.",
        failed_message="Claim type is not allowed for this trust assessment.",
        met_message="Claim type is allowed.",
        source="claim_type_metadata",
        none_status=EvidenceRequirementStatus.NOT_APPLICABLE,
    )


def _ranking_evidence_sufficient(subject: TrustSubjectMetadata) -> EvidenceRequirementResult:
    if subject.ranking_influence_allowed is None:
        return _requirement(
            EvidenceRequirementCode.RANKING_EVIDENCE_SUFFICIENT,
            EvidenceRequirementStatus.NOT_APPLICABLE,
            "Ranking evidence metadata is not available for this subject.",
            "ranking_metadata",
        )
    if subject.ranking_influence_allowed:
        return _requirement(
            EvidenceRequirementCode.RANKING_EVIDENCE_SUFFICIENT,
            EvidenceRequirementStatus.MET,
            "Existing metadata allows ranking influence.",
            "ranking_metadata",
        )
    return _requirement(
        EvidenceRequirementCode.RANKING_EVIDENCE_SUFFICIENT,
        EvidenceRequirementStatus.FAILED,
        "Existing metadata does not allow ranking influence.",
        "ranking_metadata",
    )


def _boolean_requirement(
    code: EvidenceRequirementCode,
    value: bool | None,
    *,
    missing_message: str,
    failed_message: str,
    met_message: str,
    source: str,
    none_status: EvidenceRequirementStatus = EvidenceRequirementStatus.MISSING,
) -> EvidenceRequirementResult:
    if value is True:
        return _requirement(code, EvidenceRequirementStatus.MET, met_message, source)
    if value is False:
        return _requirement(code, EvidenceRequirementStatus.FAILED, failed_message, source)
    return _requirement(code, none_status, missing_message, source)


def _negative_boolean_requirement(
    code: EvidenceRequirementCode,
    value: bool | None,
    *,
    missing_message: str,
    failed_message: str,
    met_message: str,
    source: str,
) -> EvidenceRequirementResult:
    if value is False:
        return _requirement(code, EvidenceRequirementStatus.MET, met_message, source)
    if value is True:
        return _requirement(code, EvidenceRequirementStatus.FAILED, failed_message, source)
    return _requirement(
        code,
        EvidenceRequirementStatus.NOT_APPLICABLE,
        missing_message,
        source,
    )


def _requirement(
    code: EvidenceRequirementCode,
    status: EvidenceRequirementStatus,
    message: str,
    source: str,
) -> EvidenceRequirementResult:
    return EvidenceRequirementResult(
        code=code,
        status=status,
        message=message,
        source=source,
    )


def _warning_for_requirement(
    result: EvidenceRequirementResult,
) -> TrustWarning | None:
    if result.status is EvidenceRequirementStatus.MET:
        return None
    if result.status is EvidenceRequirementStatus.NOT_APPLICABLE:
        return None
    severity = "critical" if result.status is EvidenceRequirementStatus.FAILED else "warning"
    return TrustWarning(
        warning_code=f"evidence_{result.code.value}_{result.status.value}",
        severity=severity,
        message=result.message,
        source=result.source,
        evidence_requirement_code=result.code,
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().casefold()
    return stripped or None


def _contains_token(values: tuple[str, ...], token: str) -> bool | None:
    if not values:
        return None
    lowered = token.casefold()
    return any(lowered in value.casefold() for value in values)
