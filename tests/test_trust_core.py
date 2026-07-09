from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.data_standards.schemas import (
    CandidateCanonicalTargetType,
    CandidateFactPayload,
    CandidateFactState,
    CandidateProvenanceSnapshot,
    PartnerConfidence,
    PartnerFreshness,
    PartnerFreshnessStatus,
    PartnerIdentityContext,
    PartnerRecordType,
    PartnerSourceRef,
    PartnerSubmitterType,
    PartnerTrustTier,
    PartnerType,
    PartnerVerificationStatus,
)
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataPayload,
    OpportunityBindingConfidence,
    OpportunityExpirationState,
    OpportunityLocationMode,
    OpportunityPayload,
    OpportunityProgramType,
    OpportunityRegionBindingPayload,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingPayload,
    OpportunitySeniorityLevel,
    OpportunitySourcePayload,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.shared.confidence import Confidence
from backend.trust.adapters import DataStandardsTrustAdapter, OpportunityTrustAdapter
from backend.trust.evidence import EvidenceRequirementsEngine
from backend.trust.repository import TrustAssessmentRepository
from backend.trust.schemas import (
    EvidenceRequirementCode,
    EvidenceRequirementStatus,
    TrustAssessmentSubjectType,
    TrustSubjectMetadata,
    TrustTier,
)
from backend.trust.service import TrustAssessmentService

NOW = datetime(2026, 7, 3, 12, tzinfo=UTC)


def test_trust_contract_enums_are_stable() -> None:
    assert TrustTier.values() == {
        "trusted",
        "verified",
        "partner_submitted",
        "unverified_visible",
        "low_confidence",
        "conflicting",
        "stale",
        "quarantined",
        "ranking_ineligible",
        "blocked",
        "not_assessed",
    }
    assert EvidenceRequirementStatus.values() == {
        "met",
        "missing",
        "failed",
        "not_applicable",
    }
    assert {
        "valid_fields",
        "source_present",
        "source_allowed",
        "source_fresh",
        "confidence_sufficient",
        "no_conflict_detected",
        "partner_trust_sufficient",
        "ranking_evidence_sufficient",
    }.issubset(EvidenceRequirementCode.values())


def test_evidence_engine_is_deterministic_and_structured() -> None:
    subject = TrustSubjectMetadata(
        subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
        subject_id="opp_low",
        valid_fields=True,
        source_present=False,
        source_allowed=False,
        freshness_status="unknown",
        confidence_label="low",
        ranking_influence_allowed=False,
    )
    engine = EvidenceRequirementsEngine()

    first = engine.evaluate(subject)
    second = engine.evaluate(subject)

    assert first == second
    failed = {item.code for item in first.failed}
    missing = {item.code for item in first.missing}
    assert EvidenceRequirementCode.SOURCE_PRESENT in failed
    assert EvidenceRequirementCode.SOURCE_ALLOWED in failed
    assert EvidenceRequirementCode.CONFIDENCE_SUFFICIENT in failed
    assert EvidenceRequirementCode.SOURCE_FRESH in missing
    assert all(item.message for item in first.requirements)


def test_opportunity_trust_tiers_are_deterministic_and_non_mutating() -> None:
    service = TrustAssessmentService(clock=lambda: NOW)
    partner = _opportunity(
        opportunity_id="opp_partner",
        trust_label=OpportunityTrustLabel.PARTNER_SUBMITTED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
        source_type=OpportunitySourceType.PARTNER_SUBMITTED,
        partner_submitted=True,
    )
    verified = _opportunity(
        opportunity_id="opp_verified",
        trust_label=OpportunityTrustLabel.VERIFIED,
        review_status=OpportunityReviewStatus.APPROVED,
        partner_submitted=False,
    )
    stale = _opportunity(
        opportunity_id="opp_stale",
        trust_label=OpportunityTrustLabel.VERIFIED,
        review_status=OpportunityReviewStatus.APPROVED,
        expiration_state=OpportunityExpirationState.EXPIRED,
        partner_submitted=False,
    )
    blocked = _opportunity(
        opportunity_id="opp_blocked",
        trust_label=OpportunityTrustLabel.REJECTED,
        review_status=OpportunityReviewStatus.REJECTED,
        partner_submitted=False,
    )
    weak = _opportunity(
        opportunity_id="opp_weak",
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
        source_type=OpportunitySourceType.UNKNOWN,
        partner_submitted=False,
    )

    assert service.assess(
        OpportunityTrustAdapter.from_payload(partner)
    ).trust_tier is TrustTier.PARTNER_SUBMITTED
    assert service.assess(
        OpportunityTrustAdapter.from_payload(verified)
    ).trust_tier is TrustTier.VERIFIED
    assert service.assess(
        OpportunityTrustAdapter.from_payload(stale)
    ).trust_tier is TrustTier.STALE
    assert service.assess(
        OpportunityTrustAdapter.from_payload(blocked)
    ).trust_tier is TrustTier.BLOCKED
    weak_result = service.assess(OpportunityTrustAdapter.from_payload(weak))
    assert weak_result.trust_tier in {
        TrustTier.UNVERIFIED_VISIBLE,
        TrustTier.LOW_CONFIDENCE,
    }
    assert weak_result.ranking_influence_allowed is False
    assert weak.ranking_influence_allowed is False


def test_data_standard_trust_tiers_are_deterministic_and_non_ranking() -> None:
    service = TrustAssessmentService(clock=lambda: NOW)

    trusted = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(_candidate("trusted"))
    )
    stale = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(
            _candidate("stale", freshness=PartnerFreshnessStatus.STALE)
        )
    )
    conflicting = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(
            _candidate("conflict", candidate_state=CandidateFactState.CONFLICT)
        )
    )
    partner = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(
            _candidate(
                "partner",
                partner_verification=PartnerVerificationStatus.UNVERIFIED,
                partner_tier=PartnerTrustTier.TIER_4_LIMITED_PARTNER,
            )
        )
    )
    low = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(
            _candidate("low", confidence=Confidence.LOW)
        )
    )
    blocked = service.assess(
        DataStandardsTrustAdapter.from_candidate_payload(
            _candidate(
                "blocked",
                partner_verification=PartnerVerificationStatus.REVOKED,
                partner_tier=PartnerTrustTier.UNTRUSTED,
            )
        )
    )

    assert trusted.trust_tier in {TrustTier.TRUSTED, TrustTier.VERIFIED}
    assert stale.trust_tier is TrustTier.STALE
    assert conflicting.trust_tier is TrustTier.CONFLICTING
    assert partner.trust_tier is TrustTier.PARTNER_SUBMITTED
    assert low.trust_tier is TrustTier.LOW_CONFIDENCE
    assert blocked.trust_tier is TrustTier.BLOCKED
    for result in (trusted, stale, conflicting, partner, low, blocked):
        assert result.ranking_influence_allowed is False


def test_trust_assessment_persistence_round_trips_json(session: Session) -> None:
    result = TrustAssessmentService(clock=lambda: NOW).assess(
        DataStandardsTrustAdapter.from_candidate_payload(_candidate("persisted"))
    )
    repo = TrustAssessmentRepository(session)
    row = repo.add_assessment(result, trust_assessment_id="trust_assessment_test")
    session.flush()

    loaded = repo.latest_for_subject(
        subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
        subject_id="candidate_persisted",
    )

    assert row.trust_assessment_id == "trust_assessment_test"
    assert loaded is not None
    assert loaded.subject_id == "candidate_persisted"
    assert loaded.trust_tier is result.trust_tier
    assert loaded.evidence_requirements_met
    assert loaded.ranking_influence_allowed is False


def _opportunity(
    *,
    opportunity_id: str,
    trust_label: OpportunityTrustLabel,
    review_status: OpportunityReviewStatus,
    source_type: OpportunitySourceType = OpportunitySourceType.EMPLOYER_OFFICIAL,
    expiration_state: OpportunityExpirationState = OpportunityExpirationState.ACTIVE,
    partner_submitted: bool,
) -> OpportunityPayload:
    return OpportunityPayload(
        id=opportunity_id,
        employer_id="comp_alpha",
        employer_name="Alpha Systems",
        program_name="Analyst Internship",
        program_type=OpportunityProgramType.INTERNSHIP,
        role_families=("data_analytics",),
        regions=("greater_boston",),
        location_mode=OpportunityLocationMode.HYBRID,
        seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
        eligibility_summary="Students and recent graduates.",
        application_url=f"https://example.com/apply/{opportunity_id}",
        source_url=f"https://example.com/source/{opportunity_id}",
        source_type=source_type,
        expiration_state=expiration_state,
        compensation_disclosed=False,
        trust_label=trust_label,
        review_status=review_status,
        partner_submitted=partner_submitted,
        paid_partner=False,
        ranking_influence_allowed=False,
        created_at=NOW,
        updated_at=NOW,
        sources=(
            OpportunitySourcePayload(
                opportunity_source_id=f"src_{opportunity_id}",
                source_type=source_type,
                source_url=f"https://example.com/source/{opportunity_id}",
                created_at=NOW,
            ),
        ),
        region_bindings=(
            OpportunityRegionBindingPayload(
                opportunity_region_binding_id=f"orb_{opportunity_id}",
                region_id="greater_boston",
                region_label="Greater Boston",
                binding_confidence=OpportunityBindingConfidence.HIGH,
                created_at=NOW,
            ),
        ),
        role_family_bindings=(
            OpportunityRoleFamilyBindingPayload(
                opportunity_role_family_binding_id=f"orf_{opportunity_id}",
                role_family="data_analytics",
                binding_confidence=OpportunityBindingConfidence.HIGH,
                created_at=NOW,
            ),
        ),
        employer_influence=EmployerInfluenceMetadataPayload(
            employer_influence_metadata_id=f"inf_{opportunity_id}",
            partner_submitted=partner_submitted,
            paid_partner=False,
            ranking_influence_allowed=False,
            created_at=NOW,
            updated_at=NOW,
        ),
    )


def _candidate(
    suffix: str,
    *,
    candidate_state: CandidateFactState = CandidateFactState.PENDING_REVIEW,
    freshness: PartnerFreshnessStatus = PartnerFreshnessStatus.FRESH,
    confidence: Confidence = Confidence.HIGH,
    partner_verification: PartnerVerificationStatus = PartnerVerificationStatus.VERIFIED,
    partner_tier: PartnerTrustTier = PartnerTrustTier.TIER_1_VERIFIED_INSTITUTIONAL,
) -> CandidateFactPayload:
    return CandidateFactPayload(
        candidate_fact_id=f"candidate_{suffix}",
        partner_submission_id=f"submission_{suffix}",
        record_id=f"record_{suffix}",
        record_type=PartnerRecordType.COMPANY,
        candidate_state=candidate_state,
        canonical_target_type=CandidateCanonicalTargetType.COMPANY,
        canonical_target_id=f"company_{suffix}",
        canonical_target_key={"company_name": "Alpha Systems"},
        fact_payload={"company_name": "Alpha Systems"},
        raw_record={"record_id": f"record_{suffix}"},
        provenance=CandidateProvenanceSnapshot(
            partner=PartnerIdentityContext(
                partner_id=f"partner_{suffix}",
                partner_name="State University",
                partner_type=PartnerType.UNIVERSITY,
                verification_status=partner_verification,
                trust_tier=partner_tier,
                region_scope=("statewide",),
            ),
            submitter_type=PartnerSubmitterType.EDUCATION_INSTITUTION,
            submitted_at=NOW,
            source_refs=(
                PartnerSourceRef(
                    source_ref_id=f"source_{suffix}",
                    source_type="career_center",
                    url=f"https://example.com/source/{suffix}",
                ),
            ),
            freshness=PartnerFreshness(freshness_status=freshness, observed_at=NOW),
            confidence=PartnerConfidence(confidence_label=confidence),
            provenance_complete=True,
            provenance_warnings=(),
            ranking_influence_allowed=False,
        ),
        created_at=NOW,
        updated_at=NOW,
    )
