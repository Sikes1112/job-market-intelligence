"""Shared metric inputs and helpers for Layer 24A policy intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence


@dataclass(frozen=True, slots=True)
class RegionalPolicyInputs:
    region: Region
    present_companies: tuple[Company, ...]
    presence_rows: tuple[CompanyRegionPresence, ...]
    hiring_rows: tuple[CompanyRegionHiring, ...]
    entry_level_rows: tuple[CompanyRegionEntryLevel, ...]
    region_market_score: RegionMarketScore | None

    @property
    def present_company_count(self) -> int:
        return len(self.present_companies)

    @property
    def hiring_record_count(self) -> int:
        return len(self.hiring_rows)

    @property
    def entry_level_record_count(self) -> int:
        return len(self.entry_level_rows)

    @property
    def present_company_ids(self) -> frozenset[str]:
        return frozenset(company.company_id for company in self.present_companies)


def bounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(1.0, value)), 4)


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return bounded(float(numerator) / float(denominator))


def positive_entry_pathway_count(row: CompanyRegionEntryLevel) -> int:
    count = 0
    for value in (row.internship_count, row.coop_count, row.entry_level_full_time_count):
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            count += value
    if row.formal_early_career_program_flag:
        count += 1
    return count


def has_entry_level_access(row: CompanyRegionEntryLevel) -> bool:
    return (
        positive_entry_pathway_count(row) > 0
        or (row.entry_level_access_score is not None and row.entry_level_access_score > 0)
    )


def internship_pathway_count(row: CompanyRegionEntryLevel) -> int | None:
    values = (row.internship_count, row.coop_count)
    if all(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def hiring_signal_value(row: CompanyRegionHiring) -> int | None:
    for value in (
        row.active_posting_count_now,
        row.posting_count_30d,
        row.posting_count_90d,
    ):
        if value is not None:
            return max(0, value)
    if row.currently_hiring_flag:
        return 1
    return None


def normalized_hhi(values: tuple[int | float, ...]) -> float | None:
    positive = tuple(float(value) for value in values if value > 0)
    if not positive:
        return None
    total = sum(positive)
    if total <= 0:
        return None
    if len(positive) == 1:
        return 1.0
    hhi = sum((value / total) ** 2 for value in positive)
    equal_share_floor = 1.0 / len(positive)
    return bounded((hhi - equal_share_floor) / (1.0 - equal_share_floor))


def normalized_entropy(counts: tuple[int, ...]) -> float | None:
    import math

    positive = tuple(count for count in counts if count > 0)
    if not positive:
        return None
    if len(positive) == 1:
        return 0.0
    total = sum(positive)
    entropy = -sum((count / total) * math.log(count / total) for count in positive)
    return bounded(entropy / math.log(len(positive)))


def average(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return bounded(sum(values) / len(values))


def confidence_value(value: str | Confidence | None) -> float | None:
    if value is None:
        return None
    normalized = value.value if isinstance(value, Confidence) else value
    normalized = normalized.casefold().strip()
    if normalized in {"high", "high_confidence"}:
        return 1.0
    if normalized in {"medium", "moderate", "moderate_confidence"}:
        return 0.7
    if normalized in {"low", "low_confidence"}:
        return 0.35
    if normalized in {"unknown", "unknown_confidence"}:
        return 0.15
    return None


def source_categories_for_inputs(inputs: RegionalPolicyInputs) -> tuple[str, ...]:
    categories = ["region_registry"]
    if inputs.region_market_score is not None:
        categories.append("region_market_scores")
    if inputs.present_companies:
        categories.append("company_classification")
    if inputs.presence_rows:
        categories.append("company_region_presence")
    if inputs.hiring_rows:
        categories.append("company_region_hiring")
    if inputs.entry_level_rows:
        categories.append("company_region_entry_level")
    return tuple(dict.fromkeys(categories))


def public_metric_inputs(**values: Any) -> dict[str, Any]:
    """Return deterministic, public-safe metric inputs without row identifiers."""

    cleaned: dict[str, Any] = {}
    for key in sorted(values):
        value = values[key]
        if isinstance(value, float):
            cleaned[key] = round(value, 4)
        elif isinstance(value, set | frozenset | tuple | list):
            cleaned[key] = len(value)
        else:
            cleaned[key] = value
    return cleaned
