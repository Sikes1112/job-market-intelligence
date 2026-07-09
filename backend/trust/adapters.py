"""Domain adapters for Layer 30A trust assessment inputs."""

from __future__ import annotations

from typing import Any

from backend.data_standards.schemas import CandidateFactPayload
from backend.opportunities.schemas import (
    OpportunityExpirationState,
    OpportunityPayload,
    OpportunityReviewStatus,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.trust.schemas import TrustAssessmentSubjectType, TrustSubjectMetadata


class OpportunityTrustAdapter:
    @staticmethod
    def from_payload(opportunity: OpportunityPayload) -> TrustSubjectMetadata:
        source_count = len(opportunity.sources) if opportunity.sources else 0
        source_present = source_count > 0 or bool(opportunity.source_url)
        source_allowed = opportunity.source_type is not OpportunitySourceType.UNKNOWN
        verified = opportunity.trust_label in {
            OpportunityTrustLabel.VERIFIED,
            OpportunityTrustLabel.SOURCE_CHECKED,
        } or opportunity.review_status in {
            OpportunityReviewStatus.APPROVED,
            OpportunityReviewStatus.SOURCE_CHECKED,
        }
        expired = opportunity.expiration_state is OpportunityExpirationState.EXPIRED
        warnings = _opportunity_warnings(opportunity)
        return TrustSubjectMetadata(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id=opportunity.id,
            valid_fields=all(
                (
                    bool(opportunity.employer_name),
                    bool(opportunity.program_name),
                    bool(opportunity.application_url),
                    bool(opportunity.source_url),
                )
            ),
            source_count=source_count,
            source_present=source_present,
            source_allowed=source_allowed,
            freshness_status="stale" if expired else "fresh",
            observation_date_valid=True,
            confidence_label=_binding_confidence(opportunity),
            duplicate_detected=None,
            conflict_detected=_contains(warnings, "conflict"),
            independent_verification=verified,
            partner_submitted=opportunity.partner_submitted,
            partner_origin=opportunity.partner_submitted,
            self_promotional=(
                opportunity.source_type is OpportunitySourceType.PARTNER_SUBMITTED
            ),
            corroboration_count=source_count,
            claim_type_allowed=True,
            ranking_influence_allowed=opportunity.ranking_influence_allowed,
            expired=expired,
            blocked=opportunity.trust_label is OpportunityTrustLabel.REJECTED
            or opportunity.review_status is OpportunityReviewStatus.REJECTED,
            quarantined=(
                opportunity.review_status is OpportunityReviewStatus.NEEDS_CORRECTION
            ),
            trust_label=opportunity.trust_label.value,
            review_status=opportunity.review_status.value,
            warnings=warnings,
            metadata={
                "source_type": opportunity.source_type.value,
                "expiration_state": opportunity.expiration_state.value,
            },
        )


class DataStandardsTrustAdapter:
    @staticmethod
    def from_candidate_payload(candidate: CandidateFactPayload) -> TrustSubjectMetadata:
        provenance = candidate.provenance
        source_count = len(provenance.source_refs)
        freshness_status = provenance.freshness.freshness_status.value
        confidence_label = provenance.confidence.confidence_label.value
        confidence_score = provenance.confidence.confidence_score
        partner = provenance.partner
        state = candidate.candidate_state.value
        warnings = tuple(provenance.provenance_warnings)
        return TrustSubjectMetadata(
            subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
            subject_id=candidate.candidate_fact_id,
            valid_fields=bool(candidate.fact_payload and candidate.raw_record),
            source_count=source_count,
            source_present=source_count > 0,
            source_allowed=True,
            freshness_status=freshness_status,
            observation_date_valid=True,
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            duplicate_detected=state == "duplicate",
            conflict_detected=state == "conflict" or _contains(warnings, "conflict"),
            independent_verification=provenance.provenance_complete
            and partner.verification_status.value == "verified",
            partner_submitted=False,
            partner_origin=True,
            partner_verification_status=partner.verification_status.value,
            partner_trust_tier=partner.trust_tier.value,
            self_promotional=provenance.submitter_type.value == "employer",
            corroboration_count=source_count,
            claim_type_allowed=candidate.canonical_target_type.value != "unsupported",
            ranking_influence_allowed=provenance.ranking_influence_allowed,
            blocked=state == "rejected"
            or partner.verification_status.value in {"revoked", "suspended"}
            or partner.trust_tier.value == "untrusted",
            quarantined=state in {"needs_correction", "escalated"},
            stale=freshness_status == "stale",
            verification_status=partner.verification_status.value,
            quality_label="low_confidence_signal" if state == "low_confidence" else None,
            warnings=warnings,
            metadata={
                "candidate_state": state,
                "record_type": candidate.record_type.value,
                "canonical_target_type": candidate.canonical_target_type.value,
            },
        )

    @staticmethod
    def from_mapping(payload: dict[str, Any]) -> TrustSubjectMetadata:
        warnings = tuple(str(item) for item in payload.get("warnings", ()))
        source_refs = payload.get("source_refs", ()) or ()
        freshness = payload.get("freshness", {}) or {}
        confidence = payload.get("confidence", {}) or {}
        return TrustSubjectMetadata(
            subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
            subject_id=str(payload.get("subject_id") or payload.get("candidate_fact_id")),
            valid_fields=bool(payload.get("valid_fields", True)),
            source_count=len(source_refs),
            source_present=bool(source_refs),
            source_allowed=payload.get("source_allowed", True),
            freshness_status=freshness.get("freshness_status"),
            confidence_label=confidence.get("confidence_label"),
            confidence_score=confidence.get("confidence_score"),
            duplicate_detected=payload.get("duplicate_detected"),
            conflict_detected=payload.get("conflict_detected"),
            independent_verification=payload.get("independent_verification"),
            partner_origin=bool(payload.get("partner_id")),
            partner_verification_status=payload.get("partner_verification_status"),
            partner_trust_tier=payload.get("partner_trust_tier"),
            ranking_influence_allowed=payload.get("ranking_influence_allowed", False),
            warnings=warnings,
        )


def _opportunity_warnings(opportunity: OpportunityPayload) -> tuple[str, ...]:
    warnings: list[str] = []
    if opportunity.partner_submitted:
        warnings.append("Partner-submitted opportunity.")
    if opportunity.ranking_influence_allowed is False:
        warnings.append("Existing metadata does not allow ranking influence.")
    if opportunity.trust_label in {
        OpportunityTrustLabel.UNVERIFIED,
        OpportunityTrustLabel.PARTNER_SUBMITTED,
    }:
        warnings.append("Opportunity trust label is not independently verified.")
    if opportunity.expiration_state is OpportunityExpirationState.EXPIRED:
        warnings.append("Opportunity is expired.")
    if opportunity.review_status is OpportunityReviewStatus.NEEDS_CORRECTION:
        warnings.append("Opportunity needs correction before trust elevation.")
    if opportunity.trust_label is OpportunityTrustLabel.REJECTED:
        warnings.append("Opportunity is rejected.")
    return tuple(dict.fromkeys(warnings))


def _binding_confidence(opportunity: OpportunityPayload) -> str | None:
    confidences = [
        binding.binding_confidence.value
        for binding in (
            *opportunity.region_bindings,
            *opportunity.role_family_bindings,
        )
    ]
    if not confidences:
        return None
    if all(value == "high" for value in confidences):
        return "high"
    if any(value in {"high", "medium"} for value in confidences):
        return "medium"
    if any(value == "low" for value in confidences):
        return "low"
    return "unknown"


def _contains(values: tuple[str, ...], token: str) -> bool:
    lowered = token.casefold()
    return any(lowered in value.casefold() for value in values)
