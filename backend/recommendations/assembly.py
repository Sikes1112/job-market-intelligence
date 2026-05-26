"""Assembly bridge from structured app outputs to recommendation contracts.

This module does not rank targets and does not decide which recommendation is
best. It maps already-assembled read-model fields into Layer 14A explanation
objects, preserving missing/stale/weak evidence as weaknesses or manual
verification items.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationConfidenceSummary,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationFreshnessSummary,
    RecommendationGoalMode,
    RecommendationImportance,
    RecommendationManualVerificationItem,
    RecommendationProvenanceReference,
    RecommendationReason,
    RecommendationReasonCategory,
    RecommendationTarget,
    RecommendationTargetType,
    RecommendationWeakness,
    RecommendationWeaknessCategory,
)


def assemble_region_recommendation_explanation(
    region_payload: Any,
    *,
    goal_mode: RecommendationGoalMode | str | None = None,
    source_summary: Any | None = None,
) -> RecommendationExplanation:
    """Build a region recommendation explanation from structured read data.

    ``region_payload`` may be a full ``RegionOutput`` or a region-like search
    result object. The function uses attribute/dict access only so API modules
    do not become dependencies of the recommendation package.
    """

    body = _field(region_payload, "region") or region_payload
    metadata = _field(region_payload, "metadata")
    target_id = _required_string(_field(body, "region_id"), "region_id")
    display_label = _string_or_none(_field(body, "display_name") or _field(body, "name"))
    target = RecommendationTarget(
        target_type=RecommendationTargetType.REGION,
        target_id=target_id,
        display_label=display_label,
    )
    goal = RecommendationGoalMode(goal_mode) if goal_mode is not None else None

    freshness = _freshness_summary(metadata=metadata, source_summary=source_summary)
    confidence = _coverage_confidence_summary(
        _field(body, "coverage"),
        confidence_ref=f"coverage:{target_id}:confidence",
    )
    provenance_refs = _provenance_refs(source_summary)
    score_ref = _score_evidence_ref(
        target_type="region",
        target_id=target_id,
        scores=_field(body, "scores"),
        confidence=confidence,
        freshness=freshness,
        provenance=provenance_refs[0] if provenance_refs else None,
    )
    coverage_ref = _coverage_evidence_ref(
        target_type="region",
        target_id=target_id,
        coverage=_field(body, "coverage"),
        confidence=confidence,
        freshness=freshness,
    )
    region_ref = _metadata_evidence_ref(
        basis=RecommendationEvidenceBasis.REGION_METADATA,
        target_type="region",
        target_id=target_id,
        label="Region metadata",
    )
    freshness_ref = _freshness_evidence_ref(target_id=target_id, freshness=freshness)
    confidence_ref = _confidence_evidence_ref(target_id=target_id, confidence=confidence)
    provenance_ref = _provenance_evidence_ref(provenance_refs[0]) if provenance_refs else None

    evidence_refs = _dedupe_refs(
        score_ref,
        coverage_ref,
        region_ref,
        freshness_ref,
        confidence_ref,
        provenance_ref,
    )
    fit_reasons = _region_fit_reasons(
        body=body,
        score_ref=score_ref,
        coverage_ref=coverage_ref,
        region_ref=region_ref,
    )
    data_strengths = _data_strengths(
        coverage=_field(body, "coverage"),
        coverage_ref=coverage_ref,
        confidence=confidence,
        confidence_ref=confidence_ref,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_ref=provenance_ref,
    )
    weaknesses = _region_weaknesses(
        body=body,
        metadata=metadata,
        score_ref=score_ref,
        coverage_ref=coverage_ref,
        confidence=confidence,
        confidence_ref=confidence_ref,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_refs=provenance_refs,
    )
    weaknesses.extend(_goal_mode_proxy_weaknesses(goal))
    manual_verification = _region_manual_verification(
        body=body,
        metadata=metadata,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_refs=provenance_refs,
    )

    return RecommendationExplanation(
        target=target,
        goal_mode=goal,
        headline=f"{display_label or target_id} recommendation evidence",
        fit_reasons=tuple(fit_reasons),
        data_strengths=tuple(data_strengths),
        weaknesses=tuple(weaknesses),
        manual_verification=tuple(manual_verification),
        evidence_refs=evidence_refs,
        confidence_summary=confidence,
        freshness_summary=freshness,
        provenance_refs=tuple(provenance_refs),
        coverage_warnings=_coverage_warning_refs(_field(body, "coverage")),
        data_quality_warnings=_metadata_warning_codes(metadata),
    )


def assemble_company_recommendation_explanation(
    company_payload: Any,
    *,
    goal_mode: RecommendationGoalMode | str | None = None,
    source_summary: Any | None = None,
) -> RecommendationExplanation:
    """Build a company recommendation explanation from structured read data."""

    body = _field(company_payload, "company") or company_payload
    metadata = _field(company_payload, "metadata")
    target_id = _required_string(_field(body, "company_id"), "company_id")
    display_label = _string_or_none(_field(body, "company_name") or _field(body, "name"))
    target = RecommendationTarget(
        target_type=RecommendationTargetType.COMPANY,
        target_id=target_id,
        display_label=display_label,
    )
    goal = RecommendationGoalMode(goal_mode) if goal_mode is not None else None
    freshness = _freshness_summary(metadata=metadata, source_summary=source_summary)
    confidence = _company_confidence_summary(body, target_id=target_id)
    provenance_refs = _provenance_refs(source_summary)
    company_ref = _metadata_evidence_ref(
        basis=RecommendationEvidenceBasis.COMPANY_METADATA,
        target_type="company",
        target_id=target_id,
        label="Company metadata",
        confidence=confidence,
        freshness=freshness,
        provenance=provenance_refs[0] if provenance_refs else None,
    )
    freshness_ref = _freshness_evidence_ref(target_id=target_id, freshness=freshness)
    confidence_ref = _confidence_evidence_ref(target_id=target_id, confidence=confidence)
    provenance_ref = _provenance_evidence_ref(provenance_refs[0]) if provenance_refs else None
    coverage_refs = _company_region_coverage_refs(body, freshness=freshness)

    evidence_refs = _dedupe_refs(
        company_ref,
        freshness_ref,
        confidence_ref,
        provenance_ref,
        *coverage_refs,
    )
    fit_reasons = _company_fit_reasons(
        body=body,
        company_ref=company_ref,
        coverage_refs=coverage_refs,
    )
    data_strengths = _data_strengths(
        coverage=_first_company_coverage(body),
        coverage_ref=coverage_refs[0] if coverage_refs else None,
        confidence=confidence,
        confidence_ref=confidence_ref,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_ref=provenance_ref,
    )
    weaknesses = _company_weaknesses(
        body=body,
        metadata=metadata,
        company_ref=company_ref,
        confidence=confidence,
        confidence_ref=confidence_ref,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_refs=provenance_refs,
    )
    weaknesses.extend(_goal_mode_proxy_weaknesses(goal))
    manual_verification = _company_manual_verification(
        body=body,
        metadata=metadata,
        freshness=freshness,
        freshness_ref=freshness_ref,
        provenance_refs=provenance_refs,
    )

    return RecommendationExplanation(
        target=target,
        goal_mode=goal,
        headline=f"{display_label or target_id} recommendation evidence",
        fit_reasons=tuple(fit_reasons),
        data_strengths=tuple(data_strengths),
        weaknesses=tuple(weaknesses),
        manual_verification=tuple(manual_verification),
        evidence_refs=evidence_refs,
        confidence_summary=confidence,
        freshness_summary=freshness,
        provenance_refs=tuple(provenance_refs),
        coverage_warnings=tuple(
            warning
            for coverage in _company_coverages(body)
            for warning in _coverage_warning_refs(coverage)
        ),
        data_quality_warnings=_metadata_warning_codes(metadata),
    )


def _region_fit_reasons(
    *,
    body: Any,
    score_ref: RecommendationEvidenceReference | None,
    coverage_ref: RecommendationEvidenceReference | None,
    region_ref: RecommendationEvidenceReference,
) -> list[RecommendationReason]:
    reasons: list[RecommendationReason] = []
    scores = _field(body, "scores")
    score_fields = _present_score_fields(scores)
    if score_ref is not None and score_fields:
        reasons.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.REGION_FIT,
                label="Structured region scores are available",
                detail="Available score fields: " + ", ".join(score_fields),
                evidence_strength=_score_strength(scores),
                evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
                evidence_refs=(score_ref,),
            )
        )

    summary = _field(body, "summary")
    present_count = _number_or_none(_field(summary, "present_company_count"))
    if present_count is not None:
        reasons.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.REGION_FIT,
                label="Region company presence summary is available",
                detail=f"Present-company count is represented as {present_count:g}.",
                evidence_strength=RecommendationEvidenceStrength.MODERATE,
                evidence_basis=(RecommendationEvidenceBasis.REGION_METADATA,),
                evidence_refs=(region_ref,),
            )
        )

    if coverage_ref is not None and _coverage_is_confident(_field(body, "coverage")):
        reasons.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Coverage supports confident comparison",
                evidence_strength=RecommendationEvidenceStrength.STRONG,
                evidence_basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
                evidence_refs=(coverage_ref,),
            )
        )
    return reasons


def _company_fit_reasons(
    *,
    body: Any,
    company_ref: RecommendationEvidenceReference,
    coverage_refs: tuple[RecommendationEvidenceReference, ...],
) -> list[RecommendationReason]:
    reasons = [
        RecommendationReason(
            reason_category=RecommendationReasonCategory.COMPANY_FIT,
            label="Structured company metadata is available",
            detail=_company_metadata_detail(body),
            evidence_strength=RecommendationEvidenceStrength.MODERATE,
            evidence_basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
            evidence_refs=(company_ref,),
        )
    ]
    present_regions = tuple(_field(body, "regions_present") or ())
    if present_regions:
        reasons.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.COMPANY_FIT,
                label="Company has structured region-presence records",
                detail=f"Present-region count is represented as {len(present_regions)}.",
                evidence_strength=RecommendationEvidenceStrength.MODERATE,
                evidence_basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
                evidence_refs=(company_ref,),
            )
        )
    if coverage_refs:
        reasons.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Region coverage metadata is attached",
                evidence_strength=RecommendationEvidenceStrength.MODERATE,
                evidence_basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
                evidence_refs=(coverage_refs[0],),
            )
        )
    return reasons


def _data_strengths(
    *,
    coverage: Any,
    coverage_ref: RecommendationEvidenceReference | None,
    confidence: RecommendationConfidenceSummary | None,
    confidence_ref: RecommendationEvidenceReference | None,
    freshness: RecommendationFreshnessSummary | None,
    freshness_ref: RecommendationEvidenceReference | None,
    provenance_ref: RecommendationEvidenceReference | None,
) -> list[RecommendationReason]:
    strengths: list[RecommendationReason] = []
    if coverage_ref is not None and coverage is not None:
        strengths.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Market coverage metadata is attached",
                detail=_coverage_detail(coverage),
                evidence_strength=_coverage_strength(coverage),
                evidence_basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
                evidence_refs=(coverage_ref,),
            )
        )
    if confidence is not None and confidence_ref is not None:
        strengths.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Confidence context is attached",
                evidence_strength=_confidence_strength(confidence),
                evidence_basis=(RecommendationEvidenceBasis.CONFIDENCE,),
                evidence_refs=(confidence_ref,),
            )
        )
    if freshness is not None and freshness_ref is not None:
        strengths.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Freshness context is attached",
                evidence_strength=_freshness_strength(freshness),
                evidence_basis=(RecommendationEvidenceBasis.FRESHNESS,),
                evidence_refs=(freshness_ref,),
            )
        )
    if provenance_ref is not None:
        strengths.append(
            RecommendationReason(
                reason_category=RecommendationReasonCategory.DATA_STRENGTH,
                label="Source/provenance references are attached",
                evidence_strength=RecommendationEvidenceStrength.MODERATE,
                evidence_basis=(RecommendationEvidenceBasis.PROVENANCE,),
                evidence_refs=(provenance_ref,),
            )
        )
    return strengths


def _region_weaknesses(
    *,
    body: Any,
    metadata: Any,
    score_ref: RecommendationEvidenceReference | None,
    coverage_ref: RecommendationEvidenceReference | None,
    confidence: RecommendationConfidenceSummary | None,
    confidence_ref: RecommendationEvidenceReference | None,
    freshness: RecommendationFreshnessSummary | None,
    freshness_ref: RecommendationEvidenceReference | None,
    provenance_refs: tuple[RecommendationProvenanceReference, ...],
) -> list[RecommendationWeakness]:
    weaknesses: list[RecommendationWeakness] = []
    if score_ref is None:
        weaknesses.append(_missing_weakness("Region scores are missing"))
    if coverage_ref is None:
        weaknesses.append(_missing_weakness("Coverage metadata is missing"))
    elif not _coverage_is_confident(_field(body, "coverage")):
        weaknesses.append(
            RecommendationWeakness(
                weakness_category=RecommendationWeaknessCategory.COVERAGE_GAP,
                label="Coverage is not a confident recommendation basis",
                detail=_coverage_detail(_field(body, "coverage")),
                evidence_strength=_coverage_strength(_field(body, "coverage")),
                evidence_basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
                evidence_refs=(coverage_ref,),
            )
        )
    if _metadata_state(metadata) in {"partial", "stale"} and freshness_ref is not None:
        weaknesses.append(_freshness_or_partial_weakness(metadata, freshness_ref))
    if confidence is None:
        weaknesses.append(_missing_weakness("Confidence context is missing"))
    elif _confidence_is_weak(confidence) and confidence_ref is not None:
        weaknesses.append(
            RecommendationWeakness(
                weakness_category=RecommendationWeaknessCategory.LOW_CONFIDENCE,
                label="Confidence context is weak",
                evidence_strength=_confidence_strength(confidence),
                evidence_basis=(RecommendationEvidenceBasis.CONFIDENCE,),
                evidence_refs=(confidence_ref,),
            )
        )
    if freshness is None:
        weaknesses.append(_missing_weakness("Freshness context is missing"))
    elif _freshness_is_weak(freshness) and freshness_ref is not None:
        weaknesses.append(_weak_freshness_weakness(freshness, freshness_ref))
    if not provenance_refs:
        weaknesses.append(_missing_weakness("Source/provenance references are missing"))
    return weaknesses


def _company_weaknesses(
    *,
    body: Any,
    metadata: Any,
    company_ref: RecommendationEvidenceReference,
    confidence: RecommendationConfidenceSummary | None,
    confidence_ref: RecommendationEvidenceReference | None,
    freshness: RecommendationFreshnessSummary | None,
    freshness_ref: RecommendationEvidenceReference | None,
    provenance_refs: tuple[RecommendationProvenanceReference, ...],
) -> list[RecommendationWeakness]:
    weaknesses: list[RecommendationWeakness] = []
    if not tuple(_field(body, "regions_present") or ()):
        weaknesses.append(
            RecommendationWeakness(
                weakness_category=RecommendationWeaknessCategory.MISSING_DATA,
                label="No present-region records are attached",
                evidence_strength=RecommendationEvidenceStrength.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
                evidence_refs=(company_ref,),
            )
        )
    if not tuple(_field(body, "entry_level_regions") or ()):
        weaknesses.append(_missing_weakness("Company entry-level region data is missing"))
    if _metadata_state(metadata) in {"partial", "stale"} and freshness_ref is not None:
        weaknesses.append(_freshness_or_partial_weakness(metadata, freshness_ref))
    if confidence is None:
        weaknesses.append(_missing_weakness("Company confidence context is missing"))
    elif _confidence_is_weak(confidence) and confidence_ref is not None:
        weaknesses.append(
            RecommendationWeakness(
                weakness_category=RecommendationWeaknessCategory.LOW_CONFIDENCE,
                label="Company confidence context is weak",
                evidence_strength=_confidence_strength(confidence),
                evidence_basis=(RecommendationEvidenceBasis.CONFIDENCE,),
                evidence_refs=(confidence_ref,),
            )
        )
    if freshness is None:
        weaknesses.append(_missing_weakness("Freshness context is missing"))
    elif _freshness_is_weak(freshness) and freshness_ref is not None:
        weaknesses.append(_weak_freshness_weakness(freshness, freshness_ref))
    if not provenance_refs:
        weaknesses.append(_missing_weakness("Source/provenance references are missing"))
    return weaknesses


def _region_manual_verification(
    *,
    body: Any,
    metadata: Any,
    freshness: RecommendationFreshnessSummary | None,
    freshness_ref: RecommendationEvidenceReference | None,
    provenance_refs: tuple[RecommendationProvenanceReference, ...],
) -> list[RecommendationManualVerificationItem]:
    items: list[RecommendationManualVerificationItem] = []
    if _metadata_state(metadata) in {"partial", "stale"} or _freshness_is_weak(freshness):
        items.append(
            _manual_verification(
                ManualVerificationCategory.DATA_FRESHNESS_OR_CONFIDENCE,
                "Verify stale or partial data",
                "Are the score, hiring, and entry-level inputs current enough to act on?",
                freshness_ref,
            )
        )
    if _field(body, "scores") is None:
        items.append(
            _manual_verification(
                ManualVerificationCategory.SOURCE_CONFIRMATION,
                "Verify missing score inputs",
                "Is there enough structured score data before treating this as a fit?",
                None,
            )
        )
    entry_summary = _field(body, "entry_level_summary")
    if _field(entry_summary, "internship_count_total") is None:
        items.append(
            _manual_verification(
                ManualVerificationCategory.INTERNSHIP_COOP_ACCESS,
                "Verify internship/co-op availability",
                "Are internships or co-ops currently available in this region?",
                None,
            )
        )
    if not provenance_refs:
        items.append(
            _manual_verification(
                ManualVerificationCategory.SOURCE_CONFIRMATION,
                "Verify source evidence",
                "Which app-owned sources support this recommendation explanation?",
                None,
            )
        )
    return items


def _company_manual_verification(
    *,
    body: Any,
    metadata: Any,
    freshness: RecommendationFreshnessSummary | None,
    freshness_ref: RecommendationEvidenceReference | None,
    provenance_refs: tuple[RecommendationProvenanceReference, ...],
) -> list[RecommendationManualVerificationItem]:
    items: list[RecommendationManualVerificationItem] = []
    if _metadata_state(metadata) in {"partial", "stale"} or _freshness_is_weak(freshness):
        items.append(
            _manual_verification(
                ManualVerificationCategory.DATA_FRESHNESS_OR_CONFIDENCE,
                "Verify stale or partial data",
                "Are company presence, hiring, and entry-level inputs still current?",
                freshness_ref,
            )
        )
    if not tuple(_field(body, "regions_hiring") or ()):
        items.append(
            _manual_verification(
                ManualVerificationCategory.CURRENT_JOB_POSTINGS,
                "Verify current job postings",
                "Does this company currently post relevant roles in target regions?",
                None,
            )
        )
    if not tuple(_field(body, "entry_level_regions") or ()):
        items.append(
            _manual_verification(
                ManualVerificationCategory.ENTRY_LEVEL_HIRING,
                "Verify entry-level hiring",
                "Does this company currently hire entry-level candidates?",
                None,
            )
        )
    if not provenance_refs:
        items.append(
            _manual_verification(
                ManualVerificationCategory.SOURCE_CONFIRMATION,
                "Verify source evidence",
                "Which app-owned sources support this company recommendation explanation?",
                None,
            )
        )
    return items


def _goal_mode_proxy_weaknesses(
    goal_mode: RecommendationGoalMode | None,
) -> list[RecommendationWeakness]:
    if goal_mode not in {
        RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
        RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS,
        RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY,
    }:
        return []
    labels = {
        RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION: (
            "Lower competition is a heuristic proxy"
        ),
        RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS: (
            "Underrated-market fit is a heuristic proxy"
        ),
        RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY: (
            "Geographic flexibility is a heuristic proxy"
        ),
    }
    return [
        RecommendationWeakness(
            weakness_category=RecommendationWeaknessCategory.HEURISTIC_LIMITATION,
            label=labels[goal_mode],
            detail=(
                "Current structured data does not directly prove this goal-mode "
                "dimension; later ranking must keep the claim inferred."
            ),
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            support=RecommendationClaimSupport.INFERRED,
        )
    ]


def _score_evidence_ref(
    *,
    target_type: str,
    target_id: str,
    scores: Any,
    confidence: RecommendationConfidenceSummary | None,
    freshness: RecommendationFreshnessSummary | None,
    provenance: RecommendationProvenanceReference | None,
) -> RecommendationEvidenceReference | None:
    if not _present_score_fields(scores):
        return None
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.STRUCTURED_SCORE,
        strength=_score_strength(scores),
        label="Structured score fields",
        reference_type=f"{target_type}_scores",
        reference_id=f"{target_type}:{target_id}:scores",
        confidence=confidence,
        freshness=freshness,
        provenance=provenance,
    )


def _coverage_evidence_ref(
    *,
    target_type: str,
    target_id: str,
    coverage: Any,
    confidence: RecommendationConfidenceSummary | None,
    freshness: RecommendationFreshnessSummary | None,
) -> RecommendationEvidenceReference | None:
    if coverage is None:
        return None
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.MARKET_COVERAGE,
        strength=_coverage_strength(coverage),
        label="Market coverage metadata",
        reference_type="coverage",
        reference_id=f"{target_type}:{target_id}:coverage",
        confidence=confidence,
        freshness=freshness,
        coverage_warning_refs=_coverage_warning_refs(coverage),
    )


def _metadata_evidence_ref(
    *,
    basis: RecommendationEvidenceBasis,
    target_type: str,
    target_id: str,
    label: str,
    confidence: RecommendationConfidenceSummary | None = None,
    freshness: RecommendationFreshnessSummary | None = None,
    provenance: RecommendationProvenanceReference | None = None,
) -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=basis,
        strength=RecommendationEvidenceStrength.MODERATE,
        label=label,
        reference_type=target_type,
        reference_id=f"{target_type}:{target_id}:metadata",
        confidence=confidence,
        freshness=freshness,
        provenance=provenance,
    )


def _freshness_evidence_ref(
    *,
    target_id: str,
    freshness: RecommendationFreshnessSummary | None,
) -> RecommendationEvidenceReference | None:
    if freshness is None:
        return None
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.FRESHNESS,
        strength=_freshness_strength(freshness),
        label="Freshness summary",
        reference_type="freshness",
        reference_id=f"{target_id}:freshness",
        freshness=freshness,
    )


def _confidence_evidence_ref(
    *,
    target_id: str,
    confidence: RecommendationConfidenceSummary | None,
) -> RecommendationEvidenceReference | None:
    if confidence is None:
        return None
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.CONFIDENCE,
        strength=_confidence_strength(confidence),
        label="Confidence summary",
        reference_type="confidence",
        reference_id=f"{target_id}:confidence",
        confidence=confidence,
    )


def _provenance_evidence_ref(
    provenance: RecommendationProvenanceReference,
) -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.PROVENANCE,
        strength=RecommendationEvidenceStrength.MODERATE,
        label="Source/provenance reference",
        reference_type="provenance",
        reference_id=(
            provenance.fact_source_link_id
            or provenance.source_ref_id
            or provenance.provenance_ref
        ),
        provenance=provenance,
    )


def _company_region_coverage_refs(
    body: Any,
    *,
    freshness: RecommendationFreshnessSummary | None,
) -> tuple[RecommendationEvidenceReference, ...]:
    refs: list[RecommendationEvidenceReference] = []
    seen: set[str] = set()
    for collection_name in ("regions_present", "regions_hiring", "entry_level_regions"):
        for row in tuple(_field(body, collection_name) or ()):
            coverage = _field(row, "coverage")
            if coverage is None:
                continue
            region_id = _string_or_none(_field(row, "region_id")) or "unknown_region"
            ref = _coverage_evidence_ref(
                target_type="company_region",
                target_id=region_id,
                coverage=coverage,
                confidence=_coverage_confidence_summary(
                    coverage,
                    confidence_ref=f"coverage:{region_id}:confidence",
                ),
                freshness=freshness,
            )
            if ref is None or ref.reference_id in seen:
                continue
            seen.add(ref.reference_id or "")
            refs.append(ref)
    return tuple(refs)


def _company_coverages(body: Any) -> tuple[Any, ...]:
    coverages: list[Any] = []
    for collection_name in ("regions_present", "regions_hiring", "entry_level_regions"):
        for row in tuple(_field(body, collection_name) or ()):
            coverage = _field(row, "coverage")
            if coverage is None:
                continue
            coverages.append(coverage)
    return tuple(coverages)


def _first_company_coverage(body: Any) -> Any | None:
    coverages = _company_coverages(body)
    return coverages[0] if coverages else None


def _freshness_summary(
    *,
    metadata: Any,
    source_summary: Any | None,
) -> RecommendationFreshnessSummary | None:
    source_freshness = _field(source_summary, "freshness") if source_summary is not None else None
    status = _enum_or_string(_field(source_freshness, "freshness_status"))
    data_basis = _enum_or_string(_field(source_freshness, "data_basis"))
    last_updated = _field(source_freshness, "last_collected_at")
    expires = _field(metadata, "freshness_expires_at")
    source_count = _field(source_freshness, "source_count")
    warning = _string_or_none(_field(source_freshness, "low_confidence_warning"))
    metadata_state = _metadata_state(metadata)
    if status is None and metadata_state is not None:
        status = metadata_state
    if not any((status, data_basis, last_updated, expires, source_count is not None, warning)):
        return None
    return RecommendationFreshnessSummary(
        freshness_status=status,
        data_basis=data_basis,
        last_updated_at=_aware_or_none(last_updated),
        freshness_expires_at=_aware_or_none(expires),
        source_count=int(source_count) if isinstance(source_count, int) else None,
        freshness_ref="source_freshness_summary" if source_freshness is not None else None,
        warnings=(warning,) if warning else (),
    )


def _coverage_confidence_summary(
    coverage: Any,
    *,
    confidence_ref: str,
) -> RecommendationConfidenceSummary | None:
    if coverage is None:
        return None
    components = _field(coverage, "components") or _field(
        _field(coverage, "coverage_quality_score"),
        "components",
    )
    score = None
    if isinstance(components, Mapping):
        value = components.get("confidence")
        if isinstance(value, int | float) and not isinstance(value, bool):
            score = max(0.0, min(1.0, float(value) / 100.0))
    status = _enum_or_string(_field(coverage, "coverage_tier") or _field(coverage, "tier"))
    warnings = tuple(_coverage_warning_refs(coverage))
    if score is None and status is None and not warnings:
        return None
    return RecommendationConfidenceSummary(
        confidence_level=_confidence_level_from_score(score),
        confidence_score=score,
        confidence_status=status,
        confidence_ref=confidence_ref,
        warnings=warnings,
    )


def _company_confidence_summary(
    body: Any,
    *,
    target_id: str,
) -> RecommendationConfidenceSummary | None:
    confidence = _string_or_none(_field(body, "classification_confidence"))
    warnings: list[str] = []
    if not confidence:
        warnings.append("Company classification confidence is missing.")
    return RecommendationConfidenceSummary(
        confidence_level=confidence or "unknown",
        confidence_status=confidence or "unknown",
        confidence_ref=f"company:{target_id}:classification_confidence",
        warnings=tuple(warnings),
    )


def _provenance_refs(source_summary: Any | None) -> tuple[RecommendationProvenanceReference, ...]:
    if source_summary is None:
        return ()
    sources = tuple(_field(source_summary, "sources") or ())
    refs: list[RecommendationProvenanceReference] = []
    for source in sources:
        source_id = _string_or_none(_field(source, "source_id"))
        if not source_id:
            continue
        refs.append(
            RecommendationProvenanceReference(
                provenance_ref=f"source:{source_id}",
                source_ref_id=source_id,
                source_type=_string_or_none(_field(source, "source_type")),
                source_refs=(source_id,),
            )
        )
    return tuple(refs)


def _missing_weakness(label: str) -> RecommendationWeakness:
    return RecommendationWeakness(
        weakness_category=RecommendationWeaknessCategory.MISSING_DATA,
        label=label,
        evidence_strength=RecommendationEvidenceStrength.MISSING,
        evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
    )


def _freshness_or_partial_weakness(
    metadata: Any,
    freshness_ref: RecommendationEvidenceReference,
) -> RecommendationWeakness:
    state = _metadata_state(metadata) or "unknown"
    category = (
        RecommendationWeaknessCategory.STALE_DATA
        if state == "stale"
        else RecommendationWeaknessCategory.MISSING_DATA
    )
    return RecommendationWeakness(
        weakness_category=category,
        label=f"Output state is {state}",
        detail="The read model reports partial or stale upstream data.",
        evidence_strength=RecommendationEvidenceStrength.WEAK,
        evidence_basis=(RecommendationEvidenceBasis.FRESHNESS,),
        evidence_refs=(freshness_ref,),
    )


def _weak_freshness_weakness(
    freshness: RecommendationFreshnessSummary,
    freshness_ref: RecommendationEvidenceReference,
) -> RecommendationWeakness:
    return RecommendationWeakness(
        weakness_category=RecommendationWeaknessCategory.STALE_DATA,
        label="Freshness should be verified",
        detail=f"Freshness status is {freshness.freshness_status or 'unknown'}.",
        evidence_strength=_freshness_strength(freshness),
        evidence_basis=(RecommendationEvidenceBasis.FRESHNESS,),
        evidence_refs=(freshness_ref,),
    )


def _manual_verification(
    category: ManualVerificationCategory,
    label: str,
    question: str,
    evidence_ref: RecommendationEvidenceReference | None,
) -> RecommendationManualVerificationItem:
    basis = (
        (evidence_ref.basis,)
        if evidence_ref is not None
        else (RecommendationEvidenceBasis.MISSING_DATA,)
    )
    refs = (evidence_ref,) if evidence_ref is not None else ()
    return RecommendationManualVerificationItem(
        verification_category=category,
        label=label,
        question=question,
        importance=RecommendationImportance.HIGH,
        evidence_strength=(
            evidence_ref.strength
            if evidence_ref is not None
            else RecommendationEvidenceStrength.MISSING
        ),
        evidence_basis=basis,
        evidence_refs=refs,
    )


def _coverage_strength(coverage: Any) -> RecommendationEvidenceStrength:
    tier = _enum_or_string(_field(coverage, "coverage_tier") or _field(coverage, "tier"))
    if tier == "tier_1":
        return RecommendationEvidenceStrength.STRONG
    if tier == "tier_2":
        return RecommendationEvidenceStrength.MODERATE
    if tier == "tier_3":
        return RecommendationEvidenceStrength.WEAK
    return RecommendationEvidenceStrength.MISSING


def _coverage_is_confident(coverage: Any) -> bool:
    return bool(_field(coverage, "should_rank_as_confident_recommendation"))


def _coverage_warning_refs(coverage: Any) -> tuple[str, ...]:
    if coverage is None:
        return ()
    warnings: list[str] = []
    for item in tuple(_field(coverage, "coverage_limitations") or ()):
        text = _string_or_none(item)
        if text:
            warnings.append(text)
    if not _coverage_is_confident(coverage):
        warnings.append("coverage_not_confident")
    return tuple(dict.fromkeys(warnings))


def _coverage_detail(coverage: Any) -> str:
    tier = _enum_or_string(_field(coverage, "coverage_tier") or _field(coverage, "tier"))
    label = _string_or_none(_field(coverage, "coverage_label") or _field(coverage, "label"))
    score = _number_or_none(_field(coverage, "quality_score"))
    parts = []
    if tier:
        parts.append(f"tier={tier}")
    if label:
        parts.append(f"label={label}")
    if score is not None:
        parts.append(f"quality_score={score:g}")
    return "; ".join(parts) if parts else "Coverage metadata is present."


def _score_strength(scores: Any) -> RecommendationEvidenceStrength:
    count = len(_present_score_fields(scores))
    if count >= 3:
        return RecommendationEvidenceStrength.STRONG
    if count >= 1:
        return RecommendationEvidenceStrength.MODERATE
    return RecommendationEvidenceStrength.MISSING


def _present_score_fields(scores: Any) -> tuple[str, ...]:
    if scores is None:
        return ()
    names = (
        "objective_opportunity_score",
        "raw_total_score",
        "early_career_accessibility_score",
        "live_market_score",
        "structural_ecosystem_score",
        "general_density_score",
        "tech_market_density_score",
    )
    return tuple(name for name in names if _number_or_none(_field(scores, name)) is not None)


def _freshness_strength(
    freshness: RecommendationFreshnessSummary,
) -> RecommendationEvidenceStrength:
    status = (freshness.freshness_status or "unknown").casefold()
    if status == "fresh":
        return RecommendationEvidenceStrength.STRONG
    if status in {"partial", "seeded_demo"}:
        return RecommendationEvidenceStrength.WEAK
    if status == "stale":
        return RecommendationEvidenceStrength.WEAK
    return RecommendationEvidenceStrength.MISSING


def _freshness_is_weak(freshness: RecommendationFreshnessSummary | None) -> bool:
    if freshness is None:
        return True
    return _freshness_strength(freshness) in {
        RecommendationEvidenceStrength.WEAK,
        RecommendationEvidenceStrength.MISSING,
    }


def _confidence_strength(
    confidence: RecommendationConfidenceSummary,
) -> RecommendationEvidenceStrength:
    score = confidence.confidence_score
    level = (confidence.confidence_level or confidence.confidence_status or "").casefold()
    if score is not None:
        if score >= 0.75:
            return RecommendationEvidenceStrength.STRONG
        if score >= 0.4:
            return RecommendationEvidenceStrength.MODERATE
        return RecommendationEvidenceStrength.WEAK
    if "high" in level or "tier_1" in level:
        return RecommendationEvidenceStrength.STRONG
    if "moderate" in level or "medium" in level or "tier_2" in level:
        return RecommendationEvidenceStrength.MODERATE
    if "low" in level or "unknown" in level:
        return RecommendationEvidenceStrength.WEAK
    return RecommendationEvidenceStrength.MODERATE


def _confidence_is_weak(confidence: RecommendationConfidenceSummary) -> bool:
    return _confidence_strength(confidence) in {
        RecommendationEvidenceStrength.WEAK,
        RecommendationEvidenceStrength.MISSING,
    }


def _confidence_level_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _metadata_warning_codes(metadata: Any) -> tuple[str, ...]:
    warnings = tuple(_field(metadata, "warnings") or ())
    codes: list[str] = []
    for warning in warnings:
        code = _string_or_none(_field(warning, "warning_code"))
        if code:
            codes.append(code)
    return tuple(codes)


def _metadata_state(metadata: Any) -> str | None:
    value = _field(metadata, "state")
    return _enum_or_string(value)


def _company_metadata_detail(body: Any) -> str:
    pieces: list[str] = []
    for name in ("sector_primary", "sector_secondary", "eligibility_status"):
        value = _string_or_none(_field(body, name))
        if value:
            pieces.append(f"{name}={value}")
    prestige = _number_or_none(_field(body, "prestige_score"))
    if prestige is not None:
        pieces.append(f"prestige_score={prestige:g}")
    if _field(body, "is_major_tech"):
        pieces.append("is_major_tech=true")
    if _field(body, "is_mag7"):
        pieces.append("is_mag7=true")
    return "; ".join(pieces) if pieces else "Basic company identity fields are present."


def _dedupe_refs(
    *refs: RecommendationEvidenceReference | None,
) -> tuple[RecommendationEvidenceReference, ...]:
    deduped: dict[tuple[str, str | None], RecommendationEvidenceReference] = {}
    for ref in refs:
        if ref is None:
            continue
        deduped[(ref.basis.value, ref.reference_id or "")] = ref
    return tuple(deduped[key] for key in sorted(deduped))


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _required_string(value: Any, label: str) -> str:
    text = _string_or_none(value)
    if text is None:
        raise ValueError(f"{label} is required for recommendation assembly")
    return text


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _enum_or_string(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return _string_or_none(value)


def _aware_or_none(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
