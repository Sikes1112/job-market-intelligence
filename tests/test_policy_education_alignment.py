from __future__ import annotations

from sqlalchemy.orm import Session

from backend.policy.service import PolicyIntelligenceService
from tests.policy_strategy_helpers import (
    NOW,
    seed_active_institution,
    seed_company_region_signal,
    seed_region,
)


def _seed_education_market(session: Session) -> None:
    seed_region(session, "education_region", display_name="Education Region")
    seed_active_institution(session)
    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="education_region",
            company_id=f"education_company_{index}",
            company_name=f"Education Company {index}",
            sector=sector,
            active_postings=12 + index,
            internship_count=1 if index < 3 else 0,
            coop_count=0,
            entry_level_full_time_count=1,
            formal_program=index < 3,
        )


def test_education_alignment_profile_is_aggregate_only(session: Session) -> None:
    _seed_education_market(session)

    profile = PolicyIntelligenceService(session).build_education_alignment_profile(
        "education_region",
        now=NOW,
    )

    assert profile.region_id == "education_region"
    assert profile.institution_pipeline_summaries
    assert profile.program_alignment_findings
    assert profile.local_employer_absorption_score.metric_id == "local_employer_absorption"
    assert profile.talent_export_pressure_score.metric_id == "talent_export_risk"
    assert profile.student_interest_market_fit is not None
    assert profile.student_interest_market_fit.score is None
    assert "aggregate_only_education_alignment" in {
        warning.code for warning in profile.warnings
    }
    assert profile.public_safe is True
    assert profile.public_safety.student_level_data_exposed is False

    serialized = str(profile.model_dump(mode="json")).casefold()
    for token in (
        "student_id",
        "student email",
        "user_id",
        "private notes",
        "reviewer_id",
    ):
        assert token not in serialized
    assert "no individual student outcomes are inferred" in serialized


def test_program_alignment_uses_market_signals_without_program_quality_claims(
    session: Session,
) -> None:
    _seed_education_market(session)

    profile = PolicyIntelligenceService(session).build_education_alignment_profile(
        "education_region",
        now=NOW,
    )

    computer_science = next(
        item
        for item in profile.program_alignment_findings
        if item.program_area == "Computer Science"
    )
    assert computer_science.nearby_employer_demand.explainable_inputs[
        "matched_sector_count"
    ] > 0
    assert computer_science.alignment_band in {
        "low",
        "moderate",
        "high",
        "very_high",
    }
    assert "program-quality rating" in " ".join(
        computer_science.early_career_access.limitations
    )
    assert "No individual student outcomes are inferred." in computer_science.limitations

    serialized = str(profile.model_dump(mode="json")).casefold()
    for phrase in (
        "bad program",
        "should close this program",
        "students from this school will leave",
        "guaranteed placement",
    ):
        assert phrase not in serialized


def test_institution_pipeline_summaries_do_not_expose_private_internals(
    session: Session,
) -> None:
    _seed_education_market(session)

    profile = PolicyIntelligenceService(session).build_education_alignment_profile(
        "education_region",
        now=NOW,
    )
    pipeline = profile.institution_pipeline_summaries[0]

    assert pipeline.institution_id == "policy_state_university"
    assert pipeline.institution_name == "Policy State University"
    assert pipeline.related_demand_sectors
    assert "student-facing" not in pipeline.nearby_early_career_demand_summary.casefold()
    assert any("catalog" in item.casefold() for item in pipeline.limitations)

    serialized = str(profile.model_dump(mode="json")).casefold()
    for token in (
        "organization_membership_id",
        "institutional_audit_log_id",
        "institutional_report_id",
        "payload_json",
        "minimum_group_size",
        "private_metadata",
    ):
        assert token not in serialized
