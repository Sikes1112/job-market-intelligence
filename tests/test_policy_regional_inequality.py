from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.policy.service import PolicyIntelligenceService
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence

NOW = datetime(2026, 6, 27, 12, tzinfo=UTC)
FRESH_UNTIL = NOW + timedelta(days=90)


def _seed_region(session: Session, region_id: str, *, score: bool = True) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    if score:
        session.add(
            RegionMarketScore(
                region_score_id=f"score_{region_id}",
                region_id=region_id,
                objective_opportunity_score=0.68,
                live_market_score=0.70,
                early_career_accessibility_score=0.55,
                score_ruleset_version="marketscore_v1",
            )
        )
    session.flush()


def _seed_company_signal(
    session: Session,
    *,
    region_id: str,
    index: int,
    active_postings: int = 10,
    internship_count: int | None = 2,
    sector: str = "software",
    formal_program: bool = True,
) -> None:
    company_id = f"{region_id}_comp_{index}"
    session.add(
        Company(
            company_id=company_id,
            company_name=f"{region_id} Company {index}",
            normalized_company_name=f"{region_id} company {index}",
            sector_primary=sector,
            eligibility_status="eligible",
            classification_confidence="high",
        )
    )
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id=f"presence_{region_id}_{index}",
            company_id=company_id,
            region_id=region_id,
            presence_status="present",
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
            presence_confidence="high",
            source_refs=[{"fact_source_link_id": f"presence_source_{region_id}_{index}"}],
        )
    )
    session.add(
        CompanyRegionHiring(
            hiring_id=f"hiring_{region_id}_{index}",
            company_id=company_id,
            region_id=region_id,
            currently_hiring_flag=active_postings > 0,
            active_posting_count_now=active_postings,
            posting_count_30d=active_postings * 2,
            hiring_confidence="high",
            freshness_expires_at=FRESH_UNTIL,
            source_refs=[{"fact_source_link_id": f"hiring_source_{region_id}_{index}"}],
        )
    )
    session.add(
        CompanyRegionEntryLevel(
            entry_level_id=f"entry_{region_id}_{index}",
            company_id=company_id,
            region_id=region_id,
            internship_count=internship_count,
            coop_count=0 if internship_count is not None else None,
            entry_level_full_time_count=1 if internship_count else 0,
            formal_early_career_program_flag=formal_program,
            entry_level_access_score=0.65 if internship_count else 0.0,
            entry_level_confidence="high",
            freshness_expires_at=FRESH_UNTIL,
            source_refs=[{"fact_source_link_id": f"entry_source_{region_id}_{index}"}],
        )
    )
    session.flush()


def test_regional_policy_profile_is_deterministic(session: Session) -> None:
    _seed_region(session, "deterministic_region")
    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "fintech"]):
        _seed_company_signal(
            session,
            region_id="deterministic_region",
            index=index,
            active_postings=10 + index,
            sector=sector,
        )

    service = PolicyIntelligenceService(session)

    first = service.build_regional_policy_profile("deterministic_region", now=NOW)
    second = service.build_regional_policy_profile("deterministic_region", now=NOW)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.early_career_access_score.score == second.early_career_access_score.score
    assert first.opportunity_concentration_score.score == (
        second.opportunity_concentration_score.score
    )


def test_low_data_region_emits_warnings_and_lower_confidence(session: Session) -> None:
    _seed_region(session, "thin_region", score=False)
    _seed_company_signal(
        session,
        region_id="thin_region",
        index=0,
        active_postings=1,
        internship_count=None,
        sector="software",
        formal_program=False,
    )

    profile = PolicyIntelligenceService(session).build_regional_policy_profile(
        "thin_region",
        now=NOW,
    )

    warning_codes = {warning.code for warning in profile.warnings}
    assert "low_data_region" in warning_codes
    assert "missing_region_score" in warning_codes
    assert profile.confidence.level in {Confidence.LOW, Confidence.UNKNOWN}
    assert profile.public_safe is True


def test_raw_big_city_count_bias_is_mitigated_by_normalization(session: Session) -> None:
    _seed_region(session, "small_region")
    _seed_region(session, "large_region")
    for index in range(5):
        _seed_company_signal(
            session,
            region_id="small_region",
            index=index,
            active_postings=10,
            internship_count=2,
            sector=f"sector_{index % 3}",
        )
    for index in range(50):
        _seed_company_signal(
            session,
            region_id="large_region",
            index=index,
            active_postings=10,
            internship_count=2,
            sector=f"sector_{index % 3}",
        )

    service = PolicyIntelligenceService(session)
    small = service.build_regional_policy_profile("small_region", now=NOW)
    large = service.build_regional_policy_profile("large_region", now=NOW)

    assert large.early_career_access_score.explainable_inputs[
        "present_company_count"
    ] == 50
    assert small.early_career_access_score.score == large.early_career_access_score.score
    assert small.internship_pipeline_score.score == large.internship_pipeline_score.score
    assert abs(
        small.opportunity_concentration_score.score
        - large.opportunity_concentration_score.score
    ) <= 0.05
    assert "missing_normalization_denominator" not in {
        warning.code for warning in small.warnings + large.warnings
    }


def test_policy_findings_are_generated_from_structured_metrics(session: Session) -> None:
    _seed_region(session, "concentrated_region")
    for index, postings in enumerate([90, 2, 2, 2, 2]):
        _seed_company_signal(
            session,
            region_id="concentrated_region",
            index=index,
            active_postings=postings,
            internship_count=0,
            sector="software",
            formal_program=False,
        )

    profile = PolicyIntelligenceService(session).build_regional_policy_profile(
        "concentrated_region",
        now=NOW,
    )

    finding_types = {finding.finding_type for finding in profile.policy_findings}
    assert "opportunity_concentration" in finding_types
    assert "early_career_access_gap" in finding_types
    assert all(finding.evidence_references for finding in profile.policy_findings)


def test_policy_findings_do_not_emit_unsupported_language(session: Session) -> None:
    _seed_region(session, "safe_language_region")
    for index, postings in enumerate([100, 1, 1, 1, 1]):
        _seed_company_signal(
            session,
            region_id="safe_language_region",
            index=index,
            active_postings=postings,
            internship_count=0,
            sector="software",
            formal_program=False,
        )

    profile = PolicyIntelligenceService(session).build_regional_policy_profile(
        "safe_language_region",
        now=NOW,
    )
    serialized = str(profile.model_dump(mode="json")).casefold()

    for phrase in (
        "this policy caused",
        "is failing because",
        "tax incentives",
        "will definitely",
        "guaranteed",
    ):
        assert phrase not in serialized
