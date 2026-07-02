"""Aggregate institution and program mapping helpers for Layer 24B."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.institutions.decision_infrastructure import PROGRAM_DEFINITIONS
from backend.institutions.models import Organization
from backend.policy.schemas import InstitutionRegionalPipeline
from backend.policy.sector_gaps import SectorDemandSnapshot
from backend.shared.confidence import Confidence

_PUBLIC_PIPELINE_ORG_TYPES = frozenset(
    {"school", "career_center", "bootcamp", "workforce_org"}
)


def institution_pipeline_summaries(
    session: Session,
    *,
    region_id: str,
    sector_snapshots: tuple[SectorDemandSnapshot, ...],
    limit: int = 12,
) -> tuple[InstitutionRegionalPipeline, ...]:
    organizations = tuple(
        session.execute(
            select(Organization)
            .where(
                Organization.status == "active",
                Organization.organization_type.in_(_PUBLIC_PIPELINE_ORG_TYPES),
            )
            .order_by(Organization.name, Organization.organization_id)
        ).scalars()
    )
    if not organizations:
        return ()
    demand_sectors = tuple(snapshot.sector for snapshot in _top_demand_sectors(sector_snapshots))
    program_areas = _program_areas_for_sectors(demand_sectors)
    early_summary = _early_summary(sector_snapshots)
    internship_summary = _internship_summary(sector_snapshots)
    return tuple(
        InstitutionRegionalPipeline(
            institution_id=organization.organization_id,
            institution_name=organization.name,
            region_id=region_id,
            program_areas_available=(),
            related_demand_sectors=demand_sectors,
            nearby_early_career_demand_summary=early_summary,
            internship_access_summary=internship_summary,
            alignment_confidence=Confidence.LOW if not program_areas else Confidence.MEDIUM,
            limitations=(
                "Institution-program catalog data is not connected in this layer.",
                "Institution identity is listed only with aggregate regional demand context.",
            ),
        )
        for organization in organizations[:limit]
    )


def program_definitions() -> tuple:
    return tuple(PROGRAM_DEFINITIONS)


def _top_demand_sectors(
    sector_snapshots: tuple[SectorDemandSnapshot, ...],
) -> tuple[SectorDemandSnapshot, ...]:
    return tuple(
        sorted(
            sector_snapshots,
            key=lambda item: (-item.demand_score, item.sector),
        )[:5]
    )


def _program_areas_for_sectors(sectors: tuple[str, ...]) -> tuple[str, ...]:
    sector_set = {sector.casefold() for sector in sectors}
    return tuple(
        program.program_name
        for program in PROGRAM_DEFINITIONS
        if sector_set.intersection(program.sectors)
    )


def _early_summary(sector_snapshots: tuple[SectorDemandSnapshot, ...]) -> str:
    total_hiring = sum(snapshot.hiring_company_count for snapshot in sector_snapshots)
    total_access = sum(snapshot.companies_with_entry_access for snapshot in sector_snapshots)
    return (
        f"{total_access} companies with early-career signals across "
        f"{total_hiring} hiring-company sector observations."
    )


def _internship_summary(sector_snapshots: tuple[SectorDemandSnapshot, ...]) -> str:
    total_internships = sum(snapshot.internship_count for snapshot in sector_snapshots)
    return f"{total_internships} internship or co-op signals are visible in aggregate."
