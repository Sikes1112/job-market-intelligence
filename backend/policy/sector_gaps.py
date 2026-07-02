"""Sector gap analysis for Layer 24B regional strategy intelligence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from backend.companies.models import Company
from backend.policy.metrics import RegionalPolicyInputs, bounded, public_metric_inputs
from backend.policy.schemas import (
    PolicyMetric,
    RegionalPolicyProfile,
    SectorGapFinding,
    band_for_score,
)
from backend.shared.confidence import Confidence


@dataclass(frozen=True, slots=True)
class SectorDemandSnapshot:
    sector: str
    present_company_count: int
    hiring_company_count: int
    active_posting_count: int
    internship_count: int
    entry_level_full_time_count: int
    formal_program_count: int
    companies_with_entry_access: int

    @property
    def demand_score(self) -> float:
        score = (
            min(self.active_posting_count, 100) * 0.006
            + min(self.hiring_company_count, 10) * 0.04
            + min(self.present_company_count, 10) * 0.02
        )
        return bounded(score) or 0.0

    @property
    def internship_pipeline_score(self) -> float:
        if self.hiring_company_count <= 0:
            return 0.0
        company_ratio = min(1.0, self.companies_with_entry_access / self.hiring_company_count)
        density = min(1.0, self.internship_count / max(1, self.hiring_company_count * 2))
        program_ratio = min(1.0, self.formal_program_count / self.hiring_company_count)
        return bounded(0.45 * company_ratio + 0.40 * density + 0.15 * program_ratio) or 0.0

    @property
    def early_career_access_score(self) -> float:
        if self.present_company_count <= 0:
            return 0.0
        return bounded(self.companies_with_entry_access / self.present_company_count) or 0.0


def sector_demand_snapshots(inputs: RegionalPolicyInputs) -> tuple[SectorDemandSnapshot, ...]:
    companies = {
        company.company_id: company
        for company in inputs.present_companies
        if company.sector_primary is not None and company.sector_primary.strip()
    }
    present_counts = Counter(_sector(company) for company in companies.values())
    hiring_company_ids: dict[str, set[str]] = defaultdict(set)
    active_postings: Counter[str] = Counter()
    for row in inputs.hiring_rows:
        company = companies.get(row.company_id)
        if company is None:
            continue
        sector = _sector(company)
        active_count = row.active_posting_count_now or row.posting_count_30d or 0
        if row.currently_hiring_flag or active_count > 0:
            hiring_company_ids[sector].add(row.company_id)
        active_postings[sector] += max(0, active_count)

    internships: Counter[str] = Counter()
    full_time: Counter[str] = Counter()
    formal: Counter[str] = Counter()
    entry_access_companies: dict[str, set[str]] = defaultdict(set)
    for row in inputs.entry_level_rows:
        company = companies.get(row.company_id)
        if company is None:
            continue
        sector = _sector(company)
        internship_value = (row.internship_count or 0) + (row.coop_count or 0)
        internships[sector] += internship_value
        full_time[sector] += row.entry_level_full_time_count or 0
        if row.formal_early_career_program_flag:
            formal[sector] += 1
        if (
            internship_value > 0
            or (row.entry_level_full_time_count or 0) > 0
            or row.formal_early_career_program_flag
            or (row.entry_level_access_score is not None and row.entry_level_access_score > 0)
        ):
            entry_access_companies[sector].add(row.company_id)

    sectors = sorted(
        set(present_counts)
        | set(hiring_company_ids)
        | set(active_postings)
        | set(internships)
        | set(full_time)
    )
    return tuple(
        SectorDemandSnapshot(
            sector=sector,
            present_company_count=present_counts[sector],
            hiring_company_count=len(hiring_company_ids[sector]),
            active_posting_count=active_postings[sector],
            internship_count=internships[sector],
            entry_level_full_time_count=full_time[sector],
            formal_program_count=formal[sector],
            companies_with_entry_access=len(entry_access_companies[sector]),
        )
        for sector in sectors
    )


def build_sector_gap_findings(
    *,
    inputs: RegionalPolicyInputs,
    profile: RegionalPolicyProfile,
    peer_sector_demand: dict[str, float] | None = None,
) -> tuple[SectorGapFinding, ...]:
    snapshots = sector_demand_snapshots(inputs)
    findings: list[SectorGapFinding] = []
    for snapshot in snapshots:
        if snapshot.demand_score >= 0.45 and snapshot.internship_pipeline_score <= 0.35:
            findings.append(
                _sector_gap(
                    snapshot,
                    gap_type="internship_pathway_gap",
                    severity="medium",
                    interpretation=(
                        f"Available signals suggest {snapshot.sector} has employer "
                        "demand but limited internship or co-op pathway evidence."
                    ),
                    strategy=(
                        "This sector may benefit from further local validation of "
                        "student-facing employer pathways."
                    ),
                    confidence=profile.confidence.level,
                )
            )
        if (
            snapshot.entry_level_full_time_count > 0
            and snapshot.internship_count <= 0
        ):
            findings.append(
                _sector_gap(
                    snapshot,
                    gap_type="full_time_without_internship_pathway",
                    severity="medium",
                    interpretation=(
                        f"Available signals suggest {snapshot.sector} has entry-level "
                        "full-time demand but limited internship or co-op pathway evidence."
                    ),
                    strategy=(
                        "This sector may benefit from further local validation of "
                        "student-facing pathways before strategy decisions."
                    ),
                    confidence=profile.confidence.level,
                )
            )
        if snapshot.demand_score >= 0.55 and snapshot.early_career_access_score <= 0.35:
            findings.append(
                _sector_gap(
                    snapshot,
                    gap_type="early_career_access_gap",
                    severity="medium",
                    interpretation=(
                        f"Available signals suggest {snapshot.sector} demand is more "
                        "visible than entry-level access in the region."
                    ),
                    strategy=(
                        "This sector could be a candidate for employer pathway "
                        "mapping before public strategy decisions."
                    ),
                    confidence=profile.confidence.level,
                )
            )
    if (
        profile.sector_diversity_score.score is not None
        and profile.sector_diversity_score.score <= 0.40
    ):
        top_sector = _top_sector(snapshots)
        if top_sector is not None:
            findings.append(
                _sector_gap(
                    top_sector,
                    gap_type="narrow_sector_mix",
                    severity="medium",
                    interpretation=(
                        "This region shows signs of a narrow demonstrated sector mix "
                        "in the available employer base."
                    ),
                    strategy=(
                        "Adjacent sectors may be useful candidates for diversification "
                        "analysis after local validation."
                    ),
                    confidence=profile.confidence.level,
                )
            )
    if peer_sector_demand:
        target_demand = {snapshot.sector: snapshot.demand_score for snapshot in snapshots}
        for sector, peer_score in sorted(peer_sector_demand.items()):
            if peer_score >= 0.50 and target_demand.get(sector, 0.0) <= 0.25:
                findings.append(
                    SectorGapFinding(
                        sector=sector,
                        gap_type="peer_relative_sector_gap",
                        severity="low",
                        evidence_references=(
                            "peer_metro_comparison",
                            "company_region_hiring",
                        ),
                        interpretation=(
                            f"{sector} appears underdeveloped relative to available "
                            "peer-region demand signals."
                        ),
                        recommended_strategy_candidate=(
                            "This sector could be a candidate for further comparison "
                            "against peer employer and internship pathways."
                        ),
                        confidence=profile.confidence.level,
                        limitations=(
                            "Peer comparisons use available canonical region data.",
                            "This is not a causal explanation for sector differences.",
                        ),
                    )
                )
    return tuple(_dedupe_findings(findings))


def sector_metric(
    *,
    metric_id: str,
    label: str,
    score: float | None,
    interpretation_label: str,
    explainable_inputs: dict,
    limitations: tuple[str, ...],
) -> PolicyMetric:
    return PolicyMetric(
        metric_id=metric_id,
        label=label,
        score=score,
        band=band_for_score(score),
        polarity="higher_is_better",
        interpretation_label=interpretation_label,
        explainable_inputs=public_metric_inputs(**explainable_inputs),
        limitations=limitations,
        warning_codes=(),
    )


def _sector(company: Company) -> str:
    assert company.sector_primary is not None
    return company.sector_primary.strip().casefold()


def _top_sector(snapshots: tuple[SectorDemandSnapshot, ...]) -> SectorDemandSnapshot | None:
    if not snapshots:
        return None
    return sorted(
        snapshots,
        key=lambda item: (
            -item.present_company_count,
            -item.active_posting_count,
            item.sector,
        ),
    )[0]


def _sector_gap(
    snapshot: SectorDemandSnapshot,
    *,
    gap_type: str,
    severity: str,
    interpretation: str,
    strategy: str,
    confidence: Confidence,
) -> SectorGapFinding:
    return SectorGapFinding(
        sector=snapshot.sector,
        gap_type=gap_type,
        severity=severity,  # type: ignore[arg-type]
        evidence_references=(
            "company_region_hiring",
            "company_region_entry_level",
            f"sector:{snapshot.sector}",
        ),
        interpretation=interpretation,
        recommended_strategy_candidate=strategy,
        confidence=confidence,
        limitations=(
            "Sector findings use available employer and early-career signals only.",
            "Further local validation is recommended before strategy decisions.",
        ),
    )


def _dedupe_findings(findings: list[SectorGapFinding]) -> list[SectorGapFinding]:
    deduped: dict[tuple[str, str], SectorGapFinding] = {}
    for finding in findings:
        deduped.setdefault((finding.sector, finding.gap_type), finding)
    return [
        deduped[key]
        for key in sorted(
            deduped,
            key=lambda item: (item[0], item[1]),
        )
    ]
