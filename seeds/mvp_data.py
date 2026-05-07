"""Deterministic seed dataset for the MVP demo path (Slice 18).

The constants below feed :func:`seeds.mvp_seed.run_seed`. Coverage targets
match the slice-18 prompt:

* both narrowest-MVP regions (``greater_boston``, ``greater_sf``);
* Mag 7, eligible mid-size, override-included, and ineligible companies;
* presence basis variety: full triple, office+hiring, office+ops,
  satellite-only;
* hiring records exercising ``currently_hiring`` True/False, posting
  windows, and ``role_family_summary`` across product / ai_cloud_adjacent /
  cybersecurity;
* entry-level records exercising internships, co-ops, full-time
  entry-level, formal early-career flag, and recurrence signal.

Counts are illustrative — the dataset is intentionally small. Nothing here
performs network IO, scraping, AI/NLP/ML inference, or external lookups;
the only imports are the in-process service input shapes already shipped
by Slices 5–9.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backend.companies.overrides import Override
from backend.companies.service import CompanyDefinition
from backend.companies.types import PublicOrPrivate
from backend.entry_level.service import EntryLevelDefinition, EntryLevelSnapshot
from backend.entry_level.types import StudentSeasonRecurrenceSignal
from backend.geography.service import RegionDefinition
from backend.geography.types import RegionType
from backend.hiring.service import HiringDefinition, HiringSnapshot
from backend.hiring.types import (
    AnnualizedTrendSignal,
    HiringConfidence,
    SeasonalStudentHiringSignal,
)
from backend.presence.evidence import PresenceEvidence
from backend.presence.service import PresenceDefinition

# Stable region identifiers used throughout the seed pipeline.
REGION_BOSTON = "greater_boston"
REGION_SF = "greater_sf"

# Synthetic "far-future" expiry stamped on every refresh-style snapshot so
# the demo dataset reads as ``fresh`` regardless of when the seed runs.
# This is a demo affordance — real refresh cadences live in Slice 14+.
_FAR_FUTURE_FRESHNESS = datetime(2099, 12, 31, tzinfo=UTC)

REGIONS: tuple[RegionDefinition, ...] = (
    RegionDefinition(
        region_id=REGION_BOSTON,
        region_name="greater_boston",
        display_name="Greater Boston",
        region_type=RegionType.GREATER_REGION,
        parent_region_id=None,
        labor_market_group="boston_labor_market",
        normalization_profile_id="us_metro_v1",
    ),
    RegionDefinition(
        region_id=REGION_SF,
        region_name="greater_sf",
        display_name="Greater San Francisco / Silicon Valley",
        region_type=RegionType.GREATER_REGION,
        parent_region_id=None,
        labor_market_group="bay_area_labor_market",
        normalization_profile_id="us_metro_v1",
    ),
)


COMPANIES: tuple[CompanyDefinition, ...] = (
    # Mag 7, present in both regions.
    CompanyDefinition(
        company_id="comp_alphabet",
        company_name="Alphabet",
        normalized_company_name="alphabet",
        sector_primary="ai",
        sector_secondary="cloud",
        public_or_private=PublicOrPrivate.PUBLIC,
        prestige_score=0.95,
    ),
    CompanyDefinition(
        company_id="comp_microsoft",
        company_name="Microsoft",
        normalized_company_name="microsoft",
        sector_primary="cloud",
        sector_secondary="software",
        public_or_private=PublicOrPrivate.PUBLIC,
        prestige_score=0.95,
    ),
    # Mag 7, single-region.
    CompanyDefinition(
        company_id="comp_meta",
        company_name="Meta",
        normalized_company_name="meta",
        sector_primary="internet",
        sector_secondary="ai",
        public_or_private=PublicOrPrivate.PUBLIC,
        prestige_score=0.92,
    ),
    # Eligible mid-market, single-region.
    CompanyDefinition(
        company_id="comp_hubspot",
        company_name="HubSpot",
        normalized_company_name="hubspot",
        sector_primary="software",
        sector_secondary=None,
        public_or_private=PublicOrPrivate.PUBLIC,
        prestige_score=0.65,
    ),
    # Eligible, both regions, exercises currently_hiring=False on one pair.
    CompanyDefinition(
        company_id="comp_databricks",
        company_name="Databricks",
        normalized_company_name="databricks",
        sector_primary="data",
        sector_secondary="ai",
        public_or_private=PublicOrPrivate.PRIVATE,
        prestige_score=0.78,
    ),
    # Override-included edge case: primary sector is outside the in-scope
    # set, so the default rule rejects; the override flips it to
    # ``override_included`` with ``override_edge_case`` confidence.
    CompanyDefinition(
        company_id="comp_specialized_ai",
        company_name="Specialized AI Services",
        normalized_company_name="specialized ai services",
        sector_primary="enterprise_services",
        sector_secondary="ai",
        public_or_private=PublicOrPrivate.PRIVATE,
        prestige_score=0.55,
        eligibility_override=Override(
            reason=(
                "Mid-market AI services firm whose primary sector is not "
                "in the default in-scope set; admin-included as a credible "
                "edge case for the MVP demo."
            ),
            decided_by="seed_demo",
        ),
    ),
    # Ineligible — biotech is on the documented exclusion list. Kept in the
    # universe so eligibility=ineligible is exercised.
    CompanyDefinition(
        company_id="comp_biotech_research",
        company_name="Biotech Research Co.",
        normalized_company_name="biotech research co",
        sector_primary="biotech",
        sector_secondary=None,
        public_or_private=PublicOrPrivate.PRIVATE,
        prestige_score=0.40,
    ),
)


def _presence(
    company_id: str,
    region_id: str,
    *,
    office: bool,
    ops: bool,
    hiring: bool,
) -> PresenceDefinition:
    return PresenceDefinition(
        presence_id=f"pres_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        evidence=PresenceEvidence(
            office_evidence_flag=office,
            operations_evidence_flag=ops,
            hiring_evidence_flag=hiring,
            source_refs=[
                {"type": "seed_demo", "tag": f"{company_id}@{region_id}"}
            ],
        ),
    )


PRESENCE: tuple[PresenceDefinition, ...] = (
    # Full triple → office_plus_hiring (preferred) per evaluate_presence.
    _presence("comp_alphabet", REGION_BOSTON, office=True, ops=True, hiring=True),
    _presence("comp_alphabet", REGION_SF, office=True, ops=True, hiring=True),
    # Office + hiring (no operations evidence).
    _presence("comp_microsoft", REGION_BOSTON, office=True, ops=False, hiring=True),
    _presence("comp_microsoft", REGION_SF, office=True, ops=True, hiring=True),
    _presence("comp_meta", REGION_SF, office=True, ops=True, hiring=True),
    _presence("comp_hubspot", REGION_BOSTON, office=True, ops=True, hiring=True),
    # Office + operations only → office_plus_operations basis.
    _presence("comp_databricks", REGION_BOSTON, office=True, ops=True, hiring=False),
    _presence("comp_databricks", REGION_SF, office=True, ops=False, hiring=True),
    # Satellite office only → satellite_office_only basis.
    _presence(
        "comp_specialized_ai", REGION_BOSTON, office=True, ops=False, hiring=False
    ),
)


def _hiring(
    company_id: str,
    region_id: str,
    *,
    currently_hiring: bool,
    now: int,
    d30: int,
    d90: int,
    role_family: dict[str, int],
    programs: int,
    trend: AnnualizedTrendSignal,
    seasonal: SeasonalStudentHiringSignal,
    confidence: HiringConfidence = HiringConfidence.MODERATE_CONFIDENCE,
) -> HiringDefinition:
    return HiringDefinition(
        hiring_id=f"hire_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        snapshot=HiringSnapshot(
            currently_hiring_flag=currently_hiring,
            active_posting_count_now=now,
            posting_count_30d=d30,
            posting_count_90d=d90,
            annualized_trend_signal=trend,
            seasonal_student_hiring_signal=seasonal,
            hiring_program_count=programs,
            role_family_summary=dict(role_family),
            hiring_confidence=confidence,
            freshness_expires_at=_FAR_FUTURE_FRESHNESS,
            source_refs=[
                {"type": "seed_demo", "tag": f"{company_id}@{region_id}"}
            ],
        ),
    )


HIRING: tuple[HiringDefinition, ...] = (
    _hiring(
        "comp_alphabet",
        REGION_BOSTON,
        currently_hiring=True,
        now=12,
        d30=24,
        d90=55,
        role_family={"product": 3, "ai_cloud_adjacent": 5, "cybersecurity": 2},
        programs=2,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.STRONG,
        confidence=HiringConfidence.HIGH_CONFIDENCE,
    ),
    _hiring(
        "comp_alphabet",
        REGION_SF,
        currently_hiring=True,
        now=20,
        d30=45,
        d90=120,
        role_family={"product": 6, "ai_cloud_adjacent": 10, "cybersecurity": 3},
        programs=4,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.STRONG,
        confidence=HiringConfidence.HIGH_CONFIDENCE,
    ),
    _hiring(
        "comp_microsoft",
        REGION_BOSTON,
        currently_hiring=True,
        now=8,
        d30=16,
        d90=40,
        role_family={"product": 2, "ai_cloud_adjacent": 4, "cybersecurity": 2},
        programs=2,
        trend=AnnualizedTrendSignal.NEUTRAL,
        seasonal=SeasonalStudentHiringSignal.MODERATE,
    ),
    _hiring(
        "comp_microsoft",
        REGION_SF,
        currently_hiring=True,
        now=15,
        d30=30,
        d90=85,
        role_family={"product": 4, "ai_cloud_adjacent": 7, "cybersecurity": 2},
        programs=3,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.STRONG,
    ),
    _hiring(
        "comp_meta",
        REGION_SF,
        currently_hiring=True,
        now=10,
        d30=22,
        d90=55,
        role_family={"product": 3, "ai_cloud_adjacent": 5},
        programs=2,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.MODERATE,
    ),
    _hiring(
        "comp_hubspot",
        REGION_BOSTON,
        currently_hiring=True,
        now=6,
        d30=12,
        d90=28,
        role_family={"product": 5, "ai_cloud_adjacent": 1},
        programs=1,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.MODERATE,
    ),
    # currently_hiring=False — exercises the no-current-postings path.
    _hiring(
        "comp_databricks",
        REGION_BOSTON,
        currently_hiring=False,
        now=0,
        d30=3,
        d90=12,
        role_family={"product": 1, "ai_cloud_adjacent": 1},
        programs=0,
        trend=AnnualizedTrendSignal.NEUTRAL,
        seasonal=SeasonalStudentHiringSignal.WEAK,
    ),
    _hiring(
        "comp_databricks",
        REGION_SF,
        currently_hiring=True,
        now=7,
        d30=14,
        d90=35,
        role_family={"ai_cloud_adjacent": 5, "product": 2},
        programs=1,
        trend=AnnualizedTrendSignal.POSITIVE,
        seasonal=SeasonalStudentHiringSignal.MODERATE,
    ),
    _hiring(
        "comp_specialized_ai",
        REGION_BOSTON,
        currently_hiring=True,
        now=2,
        d30=4,
        d90=9,
        role_family={"cybersecurity": 2},
        programs=0,
        trend=AnnualizedTrendSignal.NEUTRAL,
        seasonal=SeasonalStudentHiringSignal.WEAK,
        confidence=HiringConfidence.LOW_CONFIDENCE,
    ),
)


def _entry_level(
    company_id: str,
    region_id: str,
    *,
    internships: int,
    coops: int,
    ft: int,
    formal: bool,
    recurrence: StudentSeasonRecurrenceSignal,
) -> EntryLevelDefinition:
    return EntryLevelDefinition(
        entry_level_id=f"el_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        snapshot=EntryLevelSnapshot(
            internship_count=internships,
            coop_count=coops,
            entry_level_full_time_count=ft,
            formal_early_career_program_flag=formal,
            student_season_recurrence_signal=recurrence,
            freshness_expires_at=_FAR_FUTURE_FRESHNESS,
            source_refs=[
                {"type": "seed_demo", "tag": f"{company_id}@{region_id}"}
            ],
        ),
    )


ENTRY_LEVEL: tuple[EntryLevelDefinition, ...] = (
    _entry_level(
        "comp_alphabet",
        REGION_BOSTON,
        internships=10,
        coops=5,
        ft=12,
        formal=True,
        recurrence=StudentSeasonRecurrenceSignal.STRONG,
    ),
    _entry_level(
        "comp_alphabet",
        REGION_SF,
        internships=15,
        coops=2,
        ft=18,
        formal=True,
        recurrence=StudentSeasonRecurrenceSignal.STRONG,
    ),
    _entry_level(
        "comp_microsoft",
        REGION_BOSTON,
        internships=8,
        coops=4,
        ft=8,
        formal=True,
        recurrence=StudentSeasonRecurrenceSignal.MODERATE,
    ),
    _entry_level(
        "comp_microsoft",
        REGION_SF,
        internships=12,
        coops=2,
        ft=14,
        formal=True,
        recurrence=StudentSeasonRecurrenceSignal.STRONG,
    ),
    _entry_level(
        "comp_meta",
        REGION_SF,
        internships=6,
        coops=0,
        ft=10,
        formal=True,
        recurrence=StudentSeasonRecurrenceSignal.MODERATE,
    ),
    _entry_level(
        "comp_hubspot",
        REGION_BOSTON,
        internships=4,
        coops=6,
        ft=5,
        formal=False,
        recurrence=StudentSeasonRecurrenceSignal.WEAK,
    ),
    _entry_level(
        "comp_databricks",
        REGION_BOSTON,
        internships=0,
        coops=0,
        ft=2,
        formal=False,
        recurrence=StudentSeasonRecurrenceSignal.WEAK,
    ),
    _entry_level(
        "comp_databricks",
        REGION_SF,
        internships=3,
        coops=2,
        ft=4,
        formal=False,
        recurrence=StudentSeasonRecurrenceSignal.MODERATE,
    ),
    _entry_level(
        "comp_specialized_ai",
        REGION_BOSTON,
        internships=1,
        coops=0,
        ft=1,
        formal=False,
        recurrence=StudentSeasonRecurrenceSignal.WEAK,
    ),
)


COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    (REGION_BOSTON, REGION_SF),
)
