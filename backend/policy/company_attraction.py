"""Company attraction fit candidates for Layer 24B strategy analysis."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.policy.metrics import bounded
from backend.policy.schemas import CompanyAttractionFit, SectorGapFinding, band_for_score
from backend.presence.models import CompanyRegionPresence
from backend.shared.confidence import Confidence


def build_company_attraction_fits(
    session: Session,
    *,
    region_id: str,
    sector_gaps: tuple[SectorGapFinding, ...],
    limit: int = 10,
) -> tuple[CompanyAttractionFit, ...]:
    gap_sectors = {finding.sector for finding in sector_gaps}
    if not gap_sectors:
        return ()
    companies = {
        row.company_id: row
        for row in session.execute(select(Company).order_by(Company.company_id)).scalars()
    }
    present_in_target = {
        row.company_id
        for row in _eligible_presence_rows(
            session,
            select(CompanyRegionPresence)
            .where(
                CompanyRegionPresence.region_id == region_id,
                CompanyRegionPresence.presence_status == "present",
            )
            .order_by(CompanyRegionPresence.company_id)
        )
    }
    presence_by_company: dict[str, set[str]] = defaultdict(set)
    for row in _eligible_presence_rows(
        session,
        select(CompanyRegionPresence)
        .where(CompanyRegionPresence.presence_status == "present")
        .order_by(CompanyRegionPresence.company_id, CompanyRegionPresence.region_id)
    ):
        presence_by_company[row.company_id].add(row.region_id)

    entry_relevance: dict[str, int] = defaultdict(int)
    for row in _eligible_entry_level_rows(
        session,
        select(CompanyRegionEntryLevel).order_by(
            CompanyRegionEntryLevel.company_id,
            CompanyRegionEntryLevel.region_id,
        )
    ):
        if row.company_id in present_in_target:
            continue
        entry_relevance[row.company_id] += (
            (row.internship_count or 0)
            + (row.coop_count or 0)
            + (row.entry_level_full_time_count or 0)
            + int(row.formal_early_career_program_flag)
        )

    candidates: list[CompanyAttractionFit] = []
    for company_id, company in companies.items():
        sector = company.sector_primary.casefold() if company.sector_primary else None
        if company_id in present_in_target or sector not in gap_sectors:
            continue
        peer_presence_count = len(presence_by_company.get(company_id, set()) - {region_id})
        if peer_presence_count <= 0:
            continue
        relevance = entry_relevance.get(company_id, 0)
        fit_score = bounded(
            min(1.0, 0.45 + peer_presence_count * 0.10 + min(relevance, 5) * 0.06)
        )
        if fit_score is None:
            continue
        candidates.append(
            CompanyAttractionFit(
                company_id=company.company_id,
                company_name=company.company_name,
                sector=sector,
                fit_score=fit_score,
                fit_band=band_for_score(fit_score),
                fit_rationale=(
                    "This company appears directionally aligned with an identified "
                    "sector gap and has demonstrated presence in other tracked regions."
                ),
                regional_gap_addressed=f"sector:{sector}",
                early_career_or_internship_relevance=(
                    "Early-career relevance is visible in other tracked regions."
                    if relevance > 0
                    else "No early-career pathway evidence was found in tracked regions."
                ),
                diversification_impact=(
                    "This employer type may be useful for regional diversification "
                    "analysis because the sector is underrepresented locally."
                ),
                confidence=Confidence.MEDIUM if relevance > 0 else Confidence.LOW,
                limitations=(
                    "This is a strategy candidate, not an expansion prediction.",
                    "Further local employer and site validation is required.",
                ),
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (-(item.fit_score or 0.0), item.company_name, item.company_id),
        )[:limit]
    )


def _eligible_presence_rows(session: Session, stmt) -> tuple[CompanyRegionPresence, ...]:
    rows = tuple(session.execute(stmt).scalars())
    eligible_ids = ranking_eligible_fact_ids(
        session,
        "company_region_presence",
        [row.presence_id for row in rows],
    )
    eligible_company_ids = ranking_eligible_fact_ids(
        session,
        "company",
        [row.company_id for row in rows],
    )
    return tuple(
        row
        for row in rows
        if row.presence_id in eligible_ids and row.company_id in eligible_company_ids
    )


def _eligible_entry_level_rows(
    session: Session,
    stmt,
) -> tuple[CompanyRegionEntryLevel, ...]:
    rows = tuple(session.execute(stmt).scalars())
    eligible_ids = ranking_eligible_fact_ids(
        session,
        "company_region_entry_level",
        [row.entry_level_id for row in rows],
    )
    return tuple(row for row in rows if row.entry_level_id in eligible_ids)
