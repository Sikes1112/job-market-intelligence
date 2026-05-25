"""End-to-end service tests for the OutputAssemblyService.

These tests seed canonical truth via the Slice 5–10 model classes directly
(the slice plan permits direct model writes inside tests), then call the
output service and inspect both the returned payloads and the persisted
OutputMetadata rows.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingCompanyForOutput,
    MissingRegionForOutput,
)
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository

# --- helpers --------------------------------------------------------------


def _service(session: Session) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _seed_region(
    session: Session,
    *,
    region_id: str = "greater_boston",
    display_name: str | None = None,
) -> Region:
    region = Region(
        region_id=region_id,
        region_name=region_id,
        display_name=display_name or region_id.replace("_", " ").title(),
        region_type="greater_region",
    )
    session.add(region)
    session.flush()
    return region


def _seed_company(
    session: Session,
    *,
    company_id: str = "comp_a",
    eligibility_status: str = "eligible",
    is_major_tech: bool = False,
    is_mag7: bool = False,
    prestige_score: float | None = None,
) -> Company:
    company = Company(
        company_id=company_id,
        company_name=company_id,
        normalized_company_name=company_id,
        eligibility_status=eligibility_status,
        is_major_tech=is_major_tech,
        is_mag7=is_mag7,
        prestige_score=prestige_score,
    )
    session.add(company)
    session.flush()
    return company


def _seed_presence(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    presence_status: str = "present",
) -> CompanyRegionPresence:
    p = CompanyRegionPresence(
        presence_id=f"p_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        presence_status=presence_status,
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
    )
    session.add(p)
    session.flush()
    return p


def _seed_hiring(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    currently_hiring_flag: bool = True,
    active_posting_count_now: int | None = 5,
    freshness_expires_at: datetime | None = None,
) -> CompanyRegionHiring:
    h = CompanyRegionHiring(
        hiring_id=f"h_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        currently_hiring_flag=currently_hiring_flag,
        active_posting_count_now=active_posting_count_now,
        freshness_expires_at=freshness_expires_at,
    )
    session.add(h)
    session.flush()
    return h


def _seed_entry_level(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    internship_count: int | None = 3,
    coop_count: int | None = 2,
    entry_level_full_time_count: int | None = 4,
    entry_level_access_score: float | None = 0.7,
    freshness_expires_at: datetime | None = None,
) -> CompanyRegionEntryLevel:
    e = CompanyRegionEntryLevel(
        entry_level_id=f"e_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        internship_count=internship_count,
        coop_count=coop_count,
        entry_level_full_time_count=entry_level_full_time_count,
        entry_level_access_score=entry_level_access_score,
        freshness_expires_at=freshness_expires_at,
    )
    session.add(e)
    session.flush()
    return e


def _seed_score(
    session: Session,
    *,
    region_id: str,
    objective: float | None = 0.74,
    structural: float | None = 0.72,
    live: float | None = 0.68,
    early_career: float | None = 0.79,
    raw_total: float | None = 0.71,
    general_density: float | None = 0.76,
    tech_density: float | None = 0.73,
) -> RegionMarketScore:
    s = RegionMarketScore(
        region_score_id=f"rms_{region_id}",
        region_id=region_id,
        structural_ecosystem_score=structural,
        live_market_score=live,
        objective_opportunity_score=objective,
        raw_total_score=raw_total,
        general_density_score=general_density,
        tech_market_density_score=tech_density,
        early_career_accessibility_score=early_career,
        score_ruleset_version="marketscore_v1",
    )
    session.add(s)
    session.flush()
    return s


def _fixed_clock(when: datetime):
    def _now() -> datetime:
        return when

    return _now


# --- region build ---------------------------------------------------------


def test_build_region_happy_path_uses_stored_score_values_exactly(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a", is_major_tech=True, prestige_score=0.6)
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_hiring(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    result = svc.build_region("greater_boston")

    assert result.action == "created"
    assert result.metadata.state == "fresh"
    assert result.payload.region.region_id == "greater_boston"
    # Scores are exactly the stored values — no recomputation.
    assert result.payload.region.scores.objective_opportunity_score == 0.74
    assert result.payload.region.scores.early_career_accessibility_score == 0.79
    assert result.payload.region.scores.score_ruleset_version == "marketscore_v1"
    assert result.payload.region.coverage.heuristic is True
    assert result.payload.region.coverage.tier.value in {"tier_2", "tier_3"}
    assert result.payload.region.sector_coverage == {}
    # Summary aggregates reflect seeded data.
    assert result.payload.region.summary.present_company_count == 1
    assert result.payload.region.summary.major_tech_count == 1
    # Top lists populated.
    assert len(result.payload.region.top_companies_present) == 1
    assert result.payload.region.top_companies_present[0].company_id == "comp_a"
    # Entry-level summary aggregates pair-level counts.
    assert result.payload.region.entry_level_summary.internship_count_total == 3
    assert result.payload.region.entry_level_summary.coop_count_total == 2


def test_build_region_missing_score_is_partial_with_warning(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    # No RegionMarketScore.

    svc = _service(session)
    result = svc.build_region("greater_boston")

    assert result.metadata.state == "partial"
    assert result.payload.region.scores is None
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "region_score_missing" in codes


def test_build_region_no_present_companies_is_partial_with_warning(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    result = svc.build_region("greater_boston")

    assert result.metadata.state == "partial"
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "no_present_companies_for_region" in codes
    assert result.payload.region.summary.present_company_count == 0


def test_build_region_stale_inputs_marks_stale(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    expired = datetime(2026, 1, 1, tzinfo=UTC)
    _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=expired,
    )
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    # Use a clock past the expiry.
    result = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 6, 1, tzinfo=UTC))
    )
    assert result.metadata.state == "stale"
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "stale_input_rows" in codes


def test_build_region_missing_region_raises(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingRegionForOutput):
        svc.build_region("ghost")


def test_build_region_unchanged_does_not_bump_version(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    when = _fixed_clock(datetime(2026, 5, 7, 12, tzinfo=UTC))
    first = svc.build_region("greater_boston", now=when)
    second = svc.build_region("greater_boston", now=when)
    assert second.action == "unchanged"
    assert second.metadata.version == first.metadata.version
    assert second.metadata.artifact_hash == first.metadata.artifact_hash


def test_build_region_changed_bumps_version_and_keeps_fresh(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    when = _fixed_clock(datetime(2026, 5, 7, 12, tzinfo=UTC))
    first = svc.build_region("greater_boston", now=when)
    assert first.metadata.state == "fresh"
    initial_version = first.metadata.version  # capture before SQLAlchemy mutates

    # Add a new present company → top list and summary change.
    _seed_company(session, company_id="comp_b", is_major_tech=True)
    _seed_presence(session, company_id="comp_b", region_id="greater_boston")

    second = svc.build_region("greater_boston", now=when)
    assert second.action == "updated"
    assert second.metadata.version == initial_version + 1
    assert second.metadata.state == "fresh"


def test_build_region_does_not_mutate_upstream_rows(session: Session) -> None:
    region = _seed_region(session)
    company = _seed_company(session, company_id="comp_a", is_major_tech=True)
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    score = _seed_score(session, region_id="greater_boston")

    region_version_before = region.version
    company_version_before = company.version
    score_version_before = score.version
    score_state_before = score.state
    objective_before = score.objective_opportunity_score

    svc = _service(session)
    svc.build_region("greater_boston")

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    assert region.version == region_version_before
    assert company.version == company_version_before
    assert score.version == score_version_before
    assert score.state == score_state_before
    assert score.objective_opportunity_score == objective_before


def test_build_region_unknown_entry_counts_are_not_reported_as_zero(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        internship_count=None,
        coop_count=None,
        entry_level_full_time_count=None,
        entry_level_access_score=None,
    )
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    result = svc.build_region("greater_boston")

    summary = result.payload.region.entry_level_summary
    assert summary.internship_count_total is None
    assert summary.coop_count_total is None
    assert summary.entry_level_full_time_count_total is None
    assert result.metadata.state == "partial"
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "entry_level_counts_not_fully_observed" in codes


# --- company build --------------------------------------------------------


def test_build_company_happy_path(session: Session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_company(
        session,
        company_id="comp_a",
        is_major_tech=True,
        is_mag7=False,
        prestige_score=0.6,
    )
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_presence(session, company_id="comp_a", region_id="greater_sf")
    _seed_hiring(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")

    svc = _service(session)
    result = svc.build_company("comp_a")

    assert result.metadata.state == "fresh"
    assert result.payload.company.company_id == "comp_a"
    assert {r.region_id for r in result.payload.company.regions_present} == {
        "greater_boston",
        "greater_sf",
    }
    assert all(
        entry.coverage.heuristic for entry in result.payload.company.regions_present
    )
    assert all(entry.sector_coverage == {} for entry in result.payload.company.regions_present)
    assert {r.region_id for r in result.payload.company.regions_hiring} == {
        "greater_boston",
    }
    assert {r.region_id for r in result.payload.company.entry_level_regions} == {
        "greater_boston",
    }


def test_build_company_filters_non_present_pairs_from_regions_present(
    session: Session,
) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_company(session, company_id="comp_a")
    _seed_presence(
        session, company_id="comp_a", region_id="greater_boston", presence_status="present"
    )
    _seed_presence(
        session,
        company_id="comp_a",
        region_id="greater_sf",
        presence_status="uncertain",
    )

    svc = _service(session)
    result = svc.build_company("comp_a")
    region_ids = {r.region_id for r in result.payload.company.regions_present}
    assert region_ids == {"greater_boston"}


def test_build_company_no_presence_is_partial(session: Session) -> None:
    _seed_company(session, company_id="comp_a")
    svc = _service(session)
    result = svc.build_company("comp_a")
    assert result.metadata.state == "partial"
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "no_presence_for_company" in codes


def test_build_company_missing_company_raises(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingCompanyForOutput):
        svc.build_company("ghost")


def test_build_company_does_not_mutate_upstream_rows(session: Session) -> None:
    region = _seed_region(session, region_id="greater_boston")
    company = _seed_company(session, company_id="comp_a")
    presence = _seed_presence(session, company_id="comp_a", region_id="greater_boston")

    region_version_before = region.version
    company_version_before = company.version
    presence_version_before = presence.version

    svc = _service(session)
    svc.build_company("comp_a")

    session.refresh(region)
    session.refresh(company)
    session.refresh(presence)
    assert region.version == region_version_before
    assert company.version == company_version_before
    assert presence.version == presence_version_before


# --- comparison build ----------------------------------------------------


def test_build_comparison_canonical_subject_id_is_order_independent(
    session: Session,
) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.74)
    _seed_score(session, region_id="greater_sf", objective=0.70)

    svc = _service(session)
    a = svc.build_comparison("greater_boston", "greater_sf")
    b = svc.build_comparison("greater_sf", "greater_boston")
    # The second call sees the existing row → returns "unchanged".
    assert b.action == "unchanged"
    assert a.metadata.subject_id == b.metadata.subject_id == "greater_boston__greater_sf"


def test_build_comparison_category_winners_use_stored_scores_only(
    session: Session,
) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.74, early_career=0.79)
    _seed_score(session, region_id="greater_sf", objective=0.70, early_career=0.65)

    svc = _service(session)
    result = svc.build_comparison("greater_boston", "greater_sf")
    winners = result.payload.comparison.category_winners
    assert winners["objective_opportunity_score"] == "greater_boston"
    assert winners["early_career_accessibility_score"] == "greater_boston"
    assert result.payload.comparison.region_a.coverage.heuristic is True
    assert result.payload.comparison.region_b.coverage.heuristic is True
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "region_coverage_not_confident" in codes


def test_build_comparison_handles_ties_with_none(session: Session) -> None:
    _seed_region(session, region_id="a")
    _seed_region(session, region_id="b")
    _seed_score(session, region_id="a", objective=0.5)
    _seed_score(session, region_id="b", objective=0.5)

    svc = _service(session)
    result = svc.build_comparison("a", "b")
    assert result.payload.comparison.category_winners["objective_opportunity_score"] is None


def test_build_comparison_missing_one_score_is_partial(session: Session) -> None:
    _seed_region(session, region_id="a")
    _seed_region(session, region_id="b")
    _seed_score(session, region_id="a")
    # No score for "b".

    svc = _service(session)
    result = svc.build_comparison("a", "b")
    assert result.metadata.state == "partial"
    # category_winners must be empty when one side has no score.
    assert result.payload.comparison.category_winners == {}
    codes = [w.warning_code for w in result.payload.metadata.warnings]
    assert "region_score_missing" in codes


def test_build_comparison_rejects_identical_regions(session: Session) -> None:
    _seed_region(session, region_id="a")
    svc = _service(session)
    with pytest.raises(InvalidComparisonInput):
        svc.build_comparison("a", "a")


def test_build_comparison_rejects_missing_region(session: Session) -> None:
    _seed_region(session, region_id="a")
    svc = _service(session)
    with pytest.raises(MissingRegionForOutput):
        svc.build_comparison("a", "ghost")


def test_build_comparison_does_not_mutate_upstream_rows(session: Session) -> None:
    _seed_region(session, region_id="a")
    _seed_region(session, region_id="b")
    score_a = _seed_score(session, region_id="a")
    score_b = _seed_score(session, region_id="b")

    score_a_version_before = score_a.version
    score_a_objective_before = score_a.objective_opportunity_score
    score_b_objective_before = score_b.objective_opportunity_score

    svc = _service(session)
    svc.build_comparison("a", "b")

    session.refresh(score_a)
    session.refresh(score_b)
    assert score_a.version == score_a_version_before
    assert score_a.objective_opportunity_score == score_a_objective_before
    assert score_b.objective_opportunity_score == score_b_objective_before


def test_build_comparison_does_not_call_scoring_or_entry_level_formula(
    session: Session,
) -> None:
    """If Slice 11 secretly recomputed objective_opportunity_score, this test
    would catch it: we set the stored value to a number outside the formula's
    natural range and confirm the comparison passes it through unchanged."""
    _seed_region(session, region_id="a")
    _seed_region(session, region_id="b")
    _seed_score(session, region_id="a", objective=42.0)  # absurd value
    _seed_score(session, region_id="b", objective=99.0)  # absurd value

    svc = _service(session)
    result = svc.build_comparison("a", "b")
    assert result.payload.comparison.region_a.scores.objective_opportunity_score == 42.0
    assert result.payload.comparison.region_b.scores.objective_opportunity_score == 99.0
    # b > a → b wins.
    assert (
        result.payload.comparison.category_winners["objective_opportunity_score"] == "b"
    )


# --- state machine first build vs rebuild --------------------------------


def test_first_region_build_walks_to_fresh(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    result = svc.build_region("greater_boston")
    assert result.metadata.state == "fresh"
    assert result.metadata.version == 1


def test_first_region_build_partial_walks_to_partial(session: Session) -> None:
    _seed_region(session)
    # No score and no companies → partial.
    svc = _service(session)
    result = svc.build_region("greater_boston")
    assert result.metadata.state == "partial"


def test_changed_region_build_fresh_to_stale_updates_state(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    hiring = _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )
    assert first.metadata.state == "fresh"

    hiring.freshness_expires_at = datetime(2026, 4, 1, tzinfo=UTC)
    session.flush()
    second = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )

    assert second.action == "updated"
    assert second.metadata.state == "stale"
    assert second.payload.metadata.state == "stale"


def test_changed_region_build_stale_to_fresh_updates_state(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    hiring = _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )
    assert first.metadata.state == "stale"

    hiring.freshness_expires_at = datetime(2026, 6, 1, tzinfo=UTC)
    session.flush()
    second = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )

    assert second.action == "updated"
    assert second.metadata.state == "fresh"
    assert second.payload.metadata.state == "fresh"


def test_changed_region_build_partial_to_fresh_updates_state(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region("greater_boston")
    assert first.metadata.state == "partial"

    _seed_score(session, region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    second = svc.build_region("greater_boston")

    assert second.action == "updated"
    assert second.metadata.state == "fresh"
    assert second.payload.metadata.state == "fresh"


def test_changed_region_build_fresh_to_partial_updates_state(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    score = _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region("greater_boston")
    assert first.metadata.state == "fresh"

    session.delete(score)
    session.flush()
    second = svc.build_region("greater_boston")

    assert second.action == "updated"
    assert second.payload.metadata.state == "partial"
    assert second.metadata.state == "partial"


def test_changed_region_build_stale_to_partial_updates_state(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    hiring = _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    score = _seed_score(session, region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )
    assert first.metadata.state == "stale"

    hiring.freshness_expires_at = datetime(2026, 6, 1, tzinfo=UTC)
    session.delete(score)
    session.flush()
    second = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )

    assert second.action == "updated"
    assert second.metadata.state == "partial"
    assert second.payload.metadata.state == "partial"


def test_changed_region_build_partial_to_stale_updates_state(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")

    svc = _service(session)
    first = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )
    assert first.metadata.state == "partial"

    _seed_score(session, region_id="greater_boston")
    _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    second = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )

    assert second.action == "updated"
    assert second.metadata.state == "stale"
    assert second.payload.metadata.state == "stale"


def test_freshness_expires_at_is_min_across_inputs(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    later = datetime(2027, 1, 1, tzinfo=UTC)
    earlier = datetime(2026, 6, 1, tzinfo=UTC)
    _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=later,
    )
    _seed_entry_level(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        freshness_expires_at=earlier,
    )

    svc = _service(session)
    # Use a clock before either expiry so neither is stale.
    result = svc.build_region(
        "greater_boston", now=_fixed_clock(datetime(2026, 5, 1, tzinfo=UTC))
    )
    assert result.metadata.freshness_expires_at == earlier
