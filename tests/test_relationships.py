from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _full_seed(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_101",
                company_name="Example AI",
                normalized_company_name="example ai",
                eligibility_status="eligible",
                is_major_tech=True,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="pres_a",
                company_id="comp_101",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
            ),
            CompanyRegionPresence(
                presence_id="pres_b",
                company_id="comp_101",
                region_id="greater_sf",
                presence_status="present",
                presence_basis="office_plus_operations",
            ),
            CompanyRegionHiring(
                hiring_id="hir_a",
                company_id="comp_101",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
            ),
            CompanyRegionEntryLevel(
                entry_level_id="ent_a",
                company_id="comp_101",
                region_id="greater_boston",
                internship_count=3,
                coop_count=2,
            ),
            RegionMarketScore(
                region_score_id="rms_a",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
            ),
        ]
    )
    session.flush()


def test_company_appears_in_multiple_region_presences(session: Session) -> None:
    _full_seed(session)
    rows = (
        session.execute(
            select(CompanyRegionPresence)
            .where(CompanyRegionPresence.company_id == "comp_101")
            .order_by(CompanyRegionPresence.region_id)
        )
        .scalars()
        .all()
    )
    assert [r.region_id for r in rows] == ["greater_boston", "greater_sf"]


def test_region_can_be_joined_to_hiring_and_entry_level(session: Session) -> None:
    _full_seed(session)
    hiring = (
        session.execute(
            select(CompanyRegionHiring).where(
                CompanyRegionHiring.region_id == "greater_boston"
            )
        )
        .scalars()
        .one()
    )
    entry = (
        session.execute(
            select(CompanyRegionEntryLevel).where(
                CompanyRegionEntryLevel.region_id == "greater_boston"
            )
        )
        .scalars()
        .one()
    )
    score = (
        session.execute(
            select(RegionMarketScore).where(RegionMarketScore.region_id == "greater_boston")
        )
        .scalars()
        .one()
    )
    assert hiring.currently_hiring_flag is True
    assert entry.internship_count == 3
    assert score.objective_opportunity_score == 0.74


def test_region_hierarchy_is_self_referential(session: Session) -> None:
    parent = Region(
        region_id="california",
        region_name="california",
        display_name="California",
        region_type="state",
    )
    session.add(parent)
    session.flush()
    child = Region(
        region_id="greater_la",
        region_name="greater_la",
        display_name="Greater LA",
        region_type="greater_region",
        parent_region_id="california",
    )
    session.add(child)
    session.flush()
    fetched_parent = session.get(Region, "california")
    assert fetched_parent is not None
    assert {r.region_id for r in fetched_parent.child_regions} == {"greater_la"}
