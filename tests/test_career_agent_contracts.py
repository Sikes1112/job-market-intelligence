from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog
from backend.career_agent.schemas import (
    CareerAgentAnswer,
    CareerAgentEvidenceRef,
    CareerAgentEvidenceType,
    CareerAgentFreshness,
    CareerAgentFreshnessStatus,
    CareerAgentGuardrailStatus,
    CareerAgentGuardrailViolation,
    CareerAgentPreferenceSnapshot,
    CareerAgentQuestionType,
    CareerAgentRecommendation,
    CareerAgentRequest,
    CareerAgentTargetType,
    CareerAgentUncertainty,
    validate_career_agent_answer,
)
from backend.career_agent.service import CareerAgentGroundingService
from backend.companies.models import Company
from backend.data_standards.models import (
    DataStandardCandidateFactRecord,
    DataStandardCandidateReviewRecord,
    DataStandardCanonicalMergeRecord,
    DataStandardPartnerSubmissionRecord,
)
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceCreate,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.schemas import MarketSnapshotCreate
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence

NOW = datetime(2026, 6, 24, 12, tzinfo=UTC)


def _freshness(status: CareerAgentFreshnessStatus = CareerAgentFreshnessStatus.FRESH):
    return CareerAgentFreshness(
        freshness_status=status,
        data_basis="test_fixture",
        source_count=1,
    )


def _uncertainty(forecast_based: bool = False):
    return CareerAgentUncertainty(
        confidence_level=Confidence.MEDIUM,
        confidence_score=0.67,
        uncertainty_level="medium",
        reasons=("test fixture",),
        limitations=(
            (
                "Forecast evidence is a bounded directional signal, not a certain outcome."
            ),
        )
        if forecast_based
        else (),
        forecast_based=forecast_based,
    )


def _evidence(
    evidence_type: CareerAgentEvidenceType = CareerAgentEvidenceType.REGION_SCORE,
    entity_id: str = "score_boston",
) -> CareerAgentEvidenceRef:
    return CareerAgentEvidenceRef(
        ref_id=f"{evidence_type.value}:{entity_id}",
        evidence_type=evidence_type,
        entity_type=evidence_type.value,
        entity_id=entity_id,
        label="Fixture evidence",
        summary="Structured fixture evidence.",
        data_basis="structured_fixture",
        freshness_status=CareerAgentFreshnessStatus.FRESH,
        confidence_label="medium",
        source_count=1,
    )


def test_recommendation_without_evidence_refs_fails_validation() -> None:
    with pytest.raises(ValidationError):
        CareerAgentRecommendation(
            recommendation_id="rec_missing_evidence",
            recommendation_type="city_fit",
            rank=1,
            target_type=CareerAgentTargetType.REGION,
            target_id="greater_boston",
            title="Greater Boston",
            summary="Missing evidence should fail.",
            evidence_refs=(),
            freshness=_freshness(),
            uncertainty=_uncertainty(),
        )


def test_guardrail_blocks_fabricated_opportunity_recommendation() -> None:
    recommendation = CareerAgentRecommendation(
        recommendation_id="rec_fabricated",
        recommendation_type="grounded_application_target",
        rank=1,
        target_type=CareerAgentTargetType.OPPORTUNITY,
        target_id="opp_fake",
        title="Fake opportunity",
        summary="This should be rejected because no opportunity evidence exists.",
        evidence_refs=(_evidence(),),
        freshness=_freshness(),
        uncertainty=_uncertainty(),
        matched_opportunity_ids=("opp_fake",),
    )
    answer = CareerAgentAnswer(
        answer_id="answer_fake",
        question_type=CareerAgentQuestionType.WHERE_SHOULD_I_APPLY,
        generated_at=NOW,
        summary="Fixture answer.",
        recommendations=(recommendation,),
        freshness=_freshness(),
        source_freshness=(_freshness(),),
        uncertainty=_uncertainty(),
        guardrails=CareerAgentGuardrailStatus(
            passed=True,
            evidence_requirement_met=True,
        ),
    )

    with pytest.raises(CareerAgentGuardrailViolation):
        validate_career_agent_answer(answer)


def test_no_grounded_recommendations_report_evidence_requirement_unmet(
    session: Session,
) -> None:
    answer = CareerAgentGroundingService(session).answer(
        CareerAgentRequest(
            question_type=CareerAgentQuestionType.CITY_FIT,
            target_region_ids=("missing_region",),
            include_forecasts=False,
        ),
        now=NOW,
    )

    assert answer.recommendations == ()
    assert answer.guardrails.evidence_requirement_met is False
    assert "No recommendation was returned" in " ".join(answer.limitations)


def _seed_region(
    session: Session,
    *,
    region_id: str,
    display_name: str,
    objective: float,
    early: float,
    expires_at: datetime | None = None,
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name,
            region_type="metro",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=objective,
            early_career_accessibility_score=early,
            score_ruleset_version="canonical_v1",
        )
    )
    session.flush()
    session.add(
        Company(
            company_id=f"comp_{region_id}",
            company_name=f"{display_name} Systems",
            normalized_company_name=f"{display_name} systems".casefold(),
            sector_primary="software",
            eligibility_status="eligible",
            classification_confidence="high_confidence",
        )
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id=f"presence_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high_confidence",
            ),
            CompanyRegionHiring(
                hiring_id=f"hiring_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=8,
                posting_count_30d=12,
                role_family_summary={"software_engineering": 5},
                hiring_confidence="high_confidence",
                freshness_expires_at=expires_at,
            ),
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                internship_count=3,
                coop_count=1,
                entry_level_full_time_count=4,
                formal_early_career_program_flag=True,
                entry_level_access_score=early,
                entry_level_confidence="high_confidence",
                freshness_expires_at=expires_at,
            ),
        ]
    )
    session.flush()


def _seed_opportunity(session: Session, *, internal_note: str = "Internal-only note") -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_career_agent",
            employer_id="comp_greater_boston",
            employer_name="Greater Boston Systems",
            program_name="Grounded Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students and new graduates.",
            application_url="https://example.com/apply/career-agent",
            source_url="https://example.com/source/career-agent",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=date(2099, 1, 1),
            trust_label=OpportunityTrustLabel.VERIFIED,
            review_status=OpportunityReviewStatus.APPROVED,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=True,
                paid_partner=True,
                paid_partner_label="paid partner",
                internal_review_notes=internal_note,
            ),
            sources=(
                OpportunitySourceCreate(
                    source_type=OpportunitySourceType.CAREER_CENTER,
                    source_url="https://example.edu/source/career-agent",
                    source_name="Career Center",
                    collected_at=NOW,
                    verification_note="Public source checked.",
                ),
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )


def _mark_partner_origin_ranking_ineligible(
    session: Session,
    *,
    fact_type: str,
    fact_id: str,
    suffix: str,
    record_type: str,
) -> None:
    submission_id = f"sub_ca_gate_{suffix}"
    candidate_id = f"cand_ca_gate_{suffix}"
    review_id = f"review_ca_gate_{suffix}"
    audit_id = f"audit_ca_gate_{suffix}"
    session.add(
        DataStandardPartnerSubmissionRecord(
            partner_submission_id=submission_id,
            partner_id="partner_career_platform",
            submitted_at=NOW,
            schema_version="partner_submission_v1",
            submitter_type="data_vendor",
            validation_status="validated",
            review_lifecycle_state="merged",
            review_state_history_json=[],
            records_json=[],
            source_refs_json=[],
            freshness_json={"freshness_status": "fresh"},
            confidence_json={"confidence_label": "high"},
            warnings_json=[],
            validation_errors_json=[],
            raw_submission_json={"partner_id": "partner_career_platform"},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()
    session.add(
        DataStandardCandidateFactRecord(
            candidate_fact_id=candidate_id,
            partner_submission_id=submission_id,
            partner_id="partner_career_platform",
            partner_name="Career Platform Partner",
            partner_type="career_platform",
            partner_verification_status="verified",
            partner_trust_tier="tier_3_verified_platform",
            submitter_type="data_vendor",
            submitted_at=NOW,
            record_id=f"rec_ca_gate_{suffix}",
            record_type=record_type,
            candidate_state="merged",
            canonical_target_type=fact_type,
            canonical_target_id=fact_id,
            canonical_target_key_json={"id": fact_id},
            fact_payload_json={"id": fact_id},
            source_refs_json=[],
            freshness_json={"freshness_status": "fresh"},
            confidence_json={"confidence_label": "high"},
            provenance_complete=True,
            provenance_warnings_json=[],
            raw_record_json={"record_id": f"rec_ca_gate_{suffix}"},
            ranking_influence_allowed=False,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        AdminEventLog(
            admin_event_id=audit_id,
            actor="reviewer_ca_gate",
            actor_role="data_reviewer",
            action="data_standard.review",
            object_type="data_standard_candidate_fact",
            object_id=candidate_id,
            reason="Mark partner-origin fixture as reviewed.",
            timestamp=NOW,
        )
    )
    session.flush()
    session.add(
        DataStandardCandidateReviewRecord(
            candidate_review_id=review_id,
            candidate_fact_id=candidate_id,
            partner_submission_id=submission_id,
            decision="approve_candidate",
            resulting_candidate_state="approved_for_merge",
            reviewer_id="reviewer_ca_gate",
            reviewer_name="Career Agent Gate Reviewer",
            reason="Fixture review.",
            decision_notes="Fixture source basis.",
            source_basis_json={"source_ref_ids": ["src_ca_gate"]},
            before_after_diff_json={},
            resolved_conflict_codes_json=[],
            audit_event_id=audit_id,
            provenance_complete=True,
            provenance_snapshot_json={"source_ref_ids": ["src_ca_gate"]},
            ranking_influence_allowed=False,
            reviewed_at=NOW,
            created_at=NOW,
        )
    )
    session.flush()
    session.add(
        DataStandardCanonicalMergeRecord(
            merge_record_id=f"merge_ca_gate_{suffix}",
            candidate_fact_id=candidate_id,
            partner_submission_id=submission_id,
            review_decision_id=review_id,
            canonical_target_type=fact_type,
            canonical_target_id=fact_id,
            merge_action="noop",
            merge_status="merged",
            conflict_detected=False,
            conflicts_json=[],
            canonical_before_json={"id": fact_id},
            canonical_after_json={"id": fact_id},
            provenance_binding_json={"source_ref_ids": ["src_ca_gate"]},
            invalidation_json=[],
            stale_output_ids_json=[],
            audit_event_id=audit_id,
            ranking_influence_allowed=False,
            merged_by="admin_ca_gate",
            merged_at=NOW,
            created_at=NOW,
        )
    )


def test_career_answer_includes_freshness_and_uncertainty_metadata(
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.80,
        early=0.76,
        expires_at=NOW + timedelta(days=30),
    )

    answer = CareerAgentGroundingService(session).answer(
        CareerAgentRequest(
            question_type=CareerAgentQuestionType.CITY_FIT,
            target_region_ids=("greater_boston",),
            target_role_families=("software_engineering",),
            include_forecasts=False,
        ),
        now=NOW,
    )

    assert answer.freshness.freshness_status in {
        CareerAgentFreshnessStatus.FRESH,
        CareerAgentFreshnessStatus.PARTIAL,
    }
    assert answer.source_freshness
    assert answer.uncertainty.confidence_level in Confidence
    assert answer.recommendations[0].freshness.source_count > 0
    assert answer.recommendations[0].uncertainty.bounded is True


def test_partner_origin_ranking_ineligible_facts_are_excluded_from_company_watch(
    session: Session,
) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="metro",
        )
    )
    session.add_all(
        [
            Company(
                company_id="comp_normal",
                company_name="Normal Systems",
                normalized_company_name="normal systems",
                sector_primary="software",
                eligibility_status="eligible",
            ),
            Company(
                company_id="comp_partner_origin",
                company_name="Partner Origin Systems",
                normalized_company_name="partner origin systems",
                sector_primary="software",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_partner_origin",
                company_id="comp_normal",
                region_id="greater_boston",
                presence_status="present",
                presence_confidence="high_confidence",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_partner_origin",
                company_id="comp_normal",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=50,
                role_family_summary={"software_engineering": 12},
                hiring_confidence="high_confidence",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_platform_owned",
                company_id="comp_normal",
                region_id="greater_boston",
                internship_count=2,
                entry_level_access_score=0.74,
                entry_level_confidence="high_confidence",
            ),
        ]
    )
    _mark_partner_origin_ranking_ineligible(
        session,
        fact_type="company_region_presence",
        fact_id="presence_partner_origin",
        suffix="presence",
        record_type="company_region_presence",
    )
    _mark_partner_origin_ranking_ineligible(
        session,
        fact_type="company_region_hiring",
        fact_id="hiring_partner_origin",
        suffix="hiring",
        record_type="hiring_signal",
    )
    _mark_partner_origin_ranking_ineligible(
        session,
        fact_type="company",
        fact_id="comp_partner_origin",
        suffix="company",
        record_type="company",
    )
    session.flush()

    answer = CareerAgentGroundingService(session).answer(
        CareerAgentRequest(
            question_type=CareerAgentQuestionType.COMPANIES_TO_WATCH,
            target_company_ids=("comp_normal", "comp_partner_origin"),
            target_region_ids=("greater_boston",),
            include_forecasts=False,
        ),
        now=NOW,
    )

    assert [recommendation.target_id for recommendation in answer.recommendations] == [
        "comp_normal"
    ]
    evidence_ids = {
        ref.entity_id
        for recommendation in answer.recommendations
        for ref in recommendation.evidence_refs
    }
    assert "entry_platform_owned" in evidence_ids
    assert "presence_partner_origin" not in evidence_ids
    assert "hiring_partner_origin" not in evidence_ids
    assert "comp_partner_origin" not in evidence_ids
    assert "0 presence row(s), 0 hiring row(s)" in answer.recommendations[0].summary


def test_forecast_backed_recommendation_has_confidence_and_warning(
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.80,
        early=0.76,
        expires_at=NOW + timedelta(days=30),
    )
    snapshot_service = HistoricalSnapshotService(HistoryRepository(session))
    for index, value in enumerate((0.30, 0.42, 0.55, 0.68), start=1):
        snapshot_service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"career_market_{index}",
                region_id="greater_boston",
                snapshot_date=date(2026, index, 1),
                overall_score=value,
                ai_opportunity_score=value,
                entry_level_access_score=0.70,
                confidence_score=0.82,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )

    answer = CareerAgentGroundingService(session).answer(
        CareerAgentRequest(
            question_type=CareerAgentQuestionType.CITY_FIT,
            target_region_ids=("greater_boston",),
            include_forecasts=True,
        ),
        now=NOW,
    )

    recommendation = answer.recommendations[0]
    assert any(
        ref.evidence_type is CareerAgentEvidenceType.FORECAST
        for ref in recommendation.evidence_refs
    )
    assert recommendation.uncertainty.forecast_based is True
    assert recommendation.uncertainty.confidence_level.value in {
        "high",
        "medium",
        "low",
        "unknown",
    }
    assert any("not a certain outcome" in warning for warning in recommendation.warnings)


def test_preferences_affect_ranking_but_are_not_evidence(session: Session) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.72,
        early=0.70,
        expires_at=NOW + timedelta(days=30),
    )
    _seed_region(
        session,
        region_id="greater_atlanta",
        display_name="Greater Atlanta",
        objective=0.70,
        early=0.69,
        expires_at=NOW + timedelta(days=30),
    )

    answer = CareerAgentGroundingService(session).answer(
        CareerAgentRequest(
            question_type=CareerAgentQuestionType.CITY_FIT,
            target_region_ids=("greater_boston", "greater_atlanta"),
            include_forecasts=False,
            preference_snapshot=CareerAgentPreferenceSnapshot(
                preferred_region_ids=("greater_atlanta",),
                preferred_role_families=("software_engineering",),
            ),
        ),
        now=NOW,
    )

    assert answer.recommendations[0].target_id == "greater_atlanta"
    assert answer.recommendations[0].preference_alignment
    assert all(
        "preference" not in ref.data_basis
        for recommendation in answer.recommendations
        for ref in recommendation.evidence_refs
    )
    assert answer.preference_snapshot is not None
    assert answer.preference_snapshot.counts_as_evidence is False


def test_api_route_returns_grounded_schema_and_redacts_private_fields(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.80,
        early=0.76,
        expires_at=NOW + timedelta(days=30),
    )
    _seed_opportunity(session, internal_note="Internal-only career agent note")

    response = api_client.post(
        "/career-agent/answers",
        json={
            "question_type": "where_should_i_apply",
            "target_region_ids": ["greater_boston"],
            "target_role_families": ["software_engineering"],
            "preferred_program_types": ["internship"],
            "preferred_location_modes": ["hybrid"],
            "include_forecasts": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"success", "partial"}
    data = body["data"]
    assert data["question_type"] == "where_should_i_apply"
    assert data["freshness"]
    assert data["uncertainty"]
    assert data["guardrails"]["passed"] is True
    assert data["recommendations"][0]["evidence_refs"]
    assert data["recommendations"][0]["matched_opportunity_ids"] == [
        "opp_career_agent"
    ]
    assert "Internal-only career agent note" not in response.text
    assert "internal_review_notes" not in response.text


def test_api_rejects_free_form_prompt_field(api_client: TestClient) -> None:
    response = api_client.post(
        "/career-agent/answers",
        json={
            "question_type": "city_fit",
            "prompt": "Tell me anything.",
        },
    )

    assert response.status_code == 422
