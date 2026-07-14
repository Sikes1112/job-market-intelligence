"""Deterministic confidence-aware scoring for Layer 34 intelligence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from backend.imports.diagnostics import (
    coverage_gaps_from_snapshot,
    fact_health_from_snapshot,
    ranking_exclusions_from_snapshot,
    source_aging_from_snapshot,
)
from backend.imports.operations import MarketOperationalSnapshot
from backend.imports.schemas import GapSeverity
from backend.market_intelligence.contradictions import apply_ranking_contradictions
from backend.market_intelligence.explanations import build_ranking_report_explanation
from backend.market_intelligence.goals import goal_component_weights
from backend.market_intelligence.grounding import (
    build_ranking_grounding,
    grounding_for_ranking_report,
    score_margin_for_item,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    EvidenceSufficiency,
    ExplainableRankingItem,
    ExplainableRankingReport,
    IntelligenceConfidence,
    IntelligenceFreshness,
    MarketIntelligenceProfile,
    RankingDriver,
)
from backend.market_intelligence.sufficiency import (
    evaluate_ranking_sufficiency,
    sufficiency_allows_recommendation,
)
from backend.scoring.models import RegionMarketScore
from backend.shared.provenance import ObservationStatus

OBSERVED_STATUSES = {
    ObservationStatus.ZERO_OBSERVED.value,
    ObservationStatus.POSITIVE_OBSERVED.value,
}

AI_CLOUD_SECTORS = {"ai", "cloud", "artificial_intelligence"}
CYBERSECURITY_SECTORS = {"cybersecurity", "security"}


@dataclass(frozen=True, slots=True)
class MarketMetrics:
    market_key: str
    market_name: str
    region_id: str
    employer_count: int
    sector_count: int
    major_tech_count: int
    mag7_count: int
    ai_cloud_employer_count: int
    cybersecurity_employer_count: int
    active_posting_total: int | None
    active_posting_observed_rows: int
    active_posting_unknown_rows: int
    active_posting_zero_rows: int
    role_active_postings: dict[str, int]
    role_observed_rows: dict[str, int]
    role_unknown_rows: dict[str, int]
    internship_total: int | None
    internship_observed_rows: int
    internship_unknown_rows: int
    coop_total: int | None
    coop_observed_rows: int
    coop_unknown_rows: int
    entry_level_full_time_total: int | None
    formal_program_count: int
    positive_entry_level_score_count: int
    structural_score: float | None
    live_market_score: float | None
    objective_score: float | None
    tech_density_score: float | None
    early_career_score: float | None
    source_count: int
    aging_source_count: int
    stale_source_count: int
    expired_source_count: int
    unknown_fact_count: int
    observed_zero_fact_count: int
    total_fact_count: int
    ranking_eligible_fact_count: int
    ranking_excluded_fact_count: int
    high_gap_count: int
    medium_gap_count: int
    confidence_score: float
    confidence: IntelligenceConfidence
    freshness: IntelligenceFreshness
    limitations: tuple[str, ...]

    @property
    def unknown_fact_ratio(self) -> float:
        if self.total_fact_count <= 0:
            return 0.0
        return self.unknown_fact_count / self.total_fact_count

    @property
    def ranking_eligible_ratio(self) -> float:
        if self.total_fact_count <= 0:
            return 0.0
        return self.ranking_eligible_fact_count / self.total_fact_count

    @property
    def ai_cloud_activity(self) -> int | None:
        return self._role_activity("ai_cloud_adjacent")

    @property
    def product_activity(self) -> int | None:
        return self._role_activity("product")

    @property
    def cybersecurity_activity(self) -> int | None:
        return self._role_activity("cybersecurity")

    def _role_activity(self, role: str) -> int | None:
        if role in self.role_observed_rows:
            return self.role_active_postings.get(role, 0)
        return None

    def supporting_metrics(self) -> dict[str, int | float | str | None]:
        return {
            "employer_count": self.employer_count,
            "sector_count": self.sector_count,
            "major_tech_count": self.major_tech_count,
            "ai_cloud_employer_count": self.ai_cloud_employer_count,
            "cybersecurity_employer_count": self.cybersecurity_employer_count,
            "active_posting_total": self.active_posting_total,
            "active_posting_unknown_rows": self.active_posting_unknown_rows,
            "active_posting_zero_rows": self.active_posting_zero_rows,
            "product_active_postings": self.product_activity,
            "product_activity_observed_rows": self.role_observed_rows.get("product", 0),
            "product_activity_unknown_rows": self.role_unknown_rows.get("product", 0),
            "product_activity_status": _role_activity_status(self, "product"),
            "ai_cloud_active_postings": self.ai_cloud_activity,
            "ai_cloud_activity_observed_rows": self.role_observed_rows.get(
                "ai_cloud_adjacent",
                0,
            ),
            "ai_cloud_activity_unknown_rows": self.role_unknown_rows.get(
                "ai_cloud_adjacent",
                0,
            ),
            "ai_cloud_activity_status": _role_activity_status(
                self,
                "ai_cloud_adjacent",
            ),
            "cybersecurity_active_postings": self.cybersecurity_activity,
            "cybersecurity_activity_observed_rows": self.role_observed_rows.get(
                "cybersecurity",
                0,
            ),
            "cybersecurity_activity_unknown_rows": self.role_unknown_rows.get(
                "cybersecurity",
                0,
            ),
            "cybersecurity_activity_status": _role_activity_status(
                self,
                "cybersecurity",
            ),
            "role_unknown_rows": sum(self.role_unknown_rows.values()),
            "internship_total": self.internship_total,
            "internship_unknown_rows": self.internship_unknown_rows,
            "coop_total": self.coop_total,
            "coop_unknown_rows": self.coop_unknown_rows,
            "formal_program_count": self.formal_program_count,
            "unknown_fact_count": self.unknown_fact_count,
            "observed_zero_fact_count": self.observed_zero_fact_count,
            "ranking_eligible_fact_count": self.ranking_eligible_fact_count,
            "ranking_excluded_fact_count": self.ranking_excluded_fact_count,
            "source_count": self.source_count,
            "aging_source_count": self.aging_source_count,
            "stale_source_count": self.stale_source_count,
            "expired_source_count": self.expired_source_count,
            "high_gap_count": self.high_gap_count,
            "medium_gap_count": self.medium_gap_count,
            "unknown_fact_ratio": round(self.unknown_fact_ratio, 4),
            "ranking_eligible_ratio": round(self.ranking_eligible_ratio, 4),
            "confidence_score": self.confidence_score,
            "freshness": self.freshness.value,
        }


@dataclass(frozen=True, slots=True)
class ComponentScore:
    code: str
    label: str
    value: float | None
    weight: float
    weighted_value: float
    evidence: str


def metrics_from_snapshot(
    snapshot: MarketOperationalSnapshot,
    *,
    score: RegionMarketScore | None,
) -> MarketMetrics:
    source_report = source_aging_from_snapshot(snapshot)
    fact_report = fact_health_from_snapshot(snapshot)
    gap_report = coverage_gaps_from_snapshot(snapshot, fact_report=fact_report)
    ranking_report = ranking_exclusions_from_snapshot(snapshot)
    eligible_fact_ids = {
        fact.fact_id for fact in snapshot.facts if fact.ranking_eligible
    }

    observed_hiring = [
        row
        for row in snapshot.hiring_facts
        if row.hiring_id in eligible_fact_ids
        and row.active_posting_count_now_status in OBSERVED_STATUSES
    ]
    active_total = (
        sum(row.active_posting_count_now or 0 for row in observed_hiring)
        if observed_hiring
        else None
    )
    role_active: dict[str, int] = {}
    role_observed: dict[str, int] = {}
    role_unknown: dict[str, int] = {}
    for row in snapshot.hiring_facts:
        if row.hiring_id not in eligible_fact_ids:
            continue
        role = row.role_family_summary
        if row.active_posting_count_now_status in OBSERVED_STATUSES:
            if isinstance(role, dict) and role:
                for key, value in sorted(role.items()):
                    if isinstance(key, str) and isinstance(value, int) and value >= 0:
                        role_active[key] = role_active.get(key, 0) + value
                        role_observed[key] = role_observed.get(key, 0) + 1
            else:
                role_key = _role_family(row)
                role_active[role_key] = role_active.get(role_key, 0) + (
                    row.active_posting_count_now or 0
                )
                role_observed[role_key] = role_observed.get(role_key, 0) + 1
        else:
            unknown_roles = _role_family_keys(row)
            for role_key in unknown_roles:
                role_unknown[role_key] = role_unknown.get(role_key, 0) + 1

    internship_values = _observed_count_values(
        (row.internship_count, row.internship_count_status)
        for row in snapshot.entry_level_facts
        if row.entry_level_id in eligible_fact_ids
    )
    coop_values = _observed_count_values(
        (row.coop_count, row.coop_count_status)
        for row in snapshot.entry_level_facts
        if row.entry_level_id in eligible_fact_ids
    )
    full_time_values = _observed_count_values(
        (row.entry_level_full_time_count, row.entry_level_full_time_count_status)
        for row in snapshot.entry_level_facts
        if row.entry_level_id in eligible_fact_ids
    )

    sectors = {
        _normalized_sector(company.sector_primary)
        for company in snapshot.companies
        if company.sector_primary
    }
    high_gaps = sum(
        1
        for gap in gap_report.gaps
        if gap.severity in {GapSeverity.HIGH, GapSeverity.CRITICAL}
    )
    medium_gaps = sum(1 for gap in gap_report.gaps if gap.severity is GapSeverity.MEDIUM)
    confidence_score = _confidence_score(
        validation_ok=snapshot.validation.ok,
        fact_report=fact_report,
        source_report=source_report,
        high_gap_count=high_gaps,
        medium_gap_count=medium_gaps,
        ranking_limited_ratio=ranking_report.ranking_limited_ratio,
    )
    limitations = _limitations(
        snapshot=snapshot,
        fact_report=fact_report,
        source_report=source_report,
        gap_codes=tuple(gap.gap_code for gap in gap_report.gaps),
    )
    return MarketMetrics(
        market_key=snapshot.market_key,
        market_name=snapshot.display_name,
        region_id=snapshot.region_id,
        employer_count=len(snapshot.companies),
        sector_count=len(sectors),
        major_tech_count=sum(1 for company in snapshot.companies if company.is_major_tech),
        mag7_count=sum(1 for company in snapshot.companies if company.is_mag7),
        ai_cloud_employer_count=sum(
            1
            for company in snapshot.companies
            if _normalized_sector(company.sector_primary) in AI_CLOUD_SECTORS
        ),
        cybersecurity_employer_count=sum(
            1
            for company in snapshot.companies
            if _normalized_sector(company.sector_primary) in CYBERSECURITY_SECTORS
        ),
        active_posting_total=active_total,
        active_posting_observed_rows=len(observed_hiring),
        active_posting_unknown_rows=sum(
            1
            for row in snapshot.hiring_facts
            if row.hiring_id in eligible_fact_ids
            and row.active_posting_count_now_status not in OBSERVED_STATUSES
        ),
        active_posting_zero_rows=sum(
            1
            for row in snapshot.hiring_facts
            if row.hiring_id in eligible_fact_ids
            and row.active_posting_count_now_status == ObservationStatus.ZERO_OBSERVED.value
        ),
        role_active_postings=dict(sorted(role_active.items())),
        role_observed_rows=dict(sorted(role_observed.items())),
        role_unknown_rows=dict(sorted(role_unknown.items())),
        internship_total=internship_values.total,
        internship_observed_rows=internship_values.observed_rows,
        internship_unknown_rows=internship_values.unknown_rows,
        coop_total=coop_values.total,
        coop_observed_rows=coop_values.observed_rows,
        coop_unknown_rows=coop_values.unknown_rows,
        entry_level_full_time_total=full_time_values.total,
        formal_program_count=sum(
            1
            for row in snapshot.entry_level_facts
            if row.entry_level_id in eligible_fact_ids
            and row.formal_early_career_program_flag
        ),
        positive_entry_level_score_count=sum(
            1
            for row in snapshot.entry_level_facts
            if row.entry_level_id in eligible_fact_ids
            and row.entry_level_access_score is not None
            and row.entry_level_access_score > 0
        ),
        structural_score=score.structural_ecosystem_score if score else None,
        live_market_score=score.live_market_score if score else None,
        objective_score=score.objective_opportunity_score if score else None,
        tech_density_score=score.tech_market_density_score if score else None,
        early_career_score=score.early_career_accessibility_score if score else None,
        source_count=source_report.source_count,
        aging_source_count=source_report.aging_source_count,
        stale_source_count=source_report.stale_source_count,
        expired_source_count=source_report.expired_source_count,
        unknown_fact_count=fact_report.unknown_facts,
        observed_zero_fact_count=fact_report.observed_zero_facts,
        total_fact_count=fact_report.total_facts,
        ranking_eligible_fact_count=fact_report.ranking_eligible_facts,
        ranking_excluded_fact_count=fact_report.ranking_excluded_facts,
        high_gap_count=high_gaps,
        medium_gap_count=medium_gaps,
        confidence_score=confidence_score,
        confidence=_confidence_label(confidence_score),
        freshness=_freshness_label(source_report),
        limitations=limitations,
    )


def rank_profiles(
    profiles: tuple[MarketIntelligenceProfile, ...],
    metrics_by_market: dict[str, MarketMetrics],
    *,
    goal: CareerGoal,
    goal_definition: Any,
) -> ExplainableRankingReport:
    maxima = _metric_maxima(metrics_by_market.values())
    scored: list[
        tuple[MarketIntelligenceProfile, MarketMetrics, float, float, tuple[ComponentScore, ...]]
    ] = []
    for profile in profiles:
        metrics = metrics_by_market[profile.market_key]
        raw, components = _raw_goal_score(metrics, goal=goal, maxima=maxima)
        final = _confidence_adjusted_score(raw, metrics)
        scored.append((profile, metrics, final, raw, components))

    ranked = sorted(scored, key=lambda item: (-item[2], item[0].market_key))
    items: list[ExplainableRankingItem] = []
    for index, (profile, metrics, score, raw_score, components) in enumerate(
        ranked,
        start=1,
    ):
        drivers = _ranking_drivers(components)
        supporting_metrics = _ranking_metrics(metrics, components)
        limitations = (
            *profile.limitations,
            *_role_activity_limitations(components, metrics),
        )
        decision = evaluate_ranking_sufficiency(
            goal=goal,
            evidence_categories=(driver.code for driver in drivers),
            score=score,
            confidence=profile.confidence,
            freshness=profile.freshness,
            supporting_metrics=supporting_metrics,
            limitations=limitations,
        )
        classification = decision.classification
        supporting_metrics.update(
            {
                "evidence_basis": classification.evidence_basis.value,
                "evidence_sufficiency": decision.sufficiency.value,
                "direct_evidence_count": classification.direct_evidence_count,
                "proxy_evidence_count": classification.proxy_evidence_count,
                "total_evidence_count": classification.total_evidence_count,
                "minimum_direct_evidence": classification.minimum_direct_evidence,
                "minimum_total_evidence": classification.minimum_total_evidence,
                "proxy_only_confidence_cap": (
                    classification.proxy_only_confidence_cap.value
                ),
            }
        )
        items.append(
            ExplainableRankingItem(
                rank=index,
                market_key=profile.market_key,
                market_name=profile.market_name,
                goal=goal,
                score=round(score, 4),
                raw_score=round(raw_score, 4),
                confidence=decision.capped_confidence,
                freshness=profile.freshness,
                ranking_drivers=drivers,
                strengths=tuple(insight.message for insight in profile.strengths[:3]),
                weaknesses=tuple(insight.message for insight in profile.weaknesses[:3]),
                limitations=decision.limitations,
                supporting_metrics=supporting_metrics,
                evidence_sufficiency=decision.sufficiency,
                evidence_basis=classification.evidence_basis,
                is_provisional=decision.is_provisional,
                abstention_reason=decision.abstention_reason,
            )
        )
    items = list(_with_grounding(tuple(items)))
    top = items[0] if items else None
    report_sufficiency = (
        top.evidence_sufficiency if top else EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    )
    abstention_reason = top.abstention_reason if top else "no ranked markets are available"
    report_limitations = tuple(
        sorted(
            {
                *getattr(goal_definition, "limitations", ()),
                *(item for ranked_item in items for item in ranked_item.limitations),
            }
        )
    )
    report = ExplainableRankingReport(
        goal=goal,
        goal_definition=goal_definition,
        ranked_markets=tuple(items),
        top_market_key=(
            top.market_key
            if top and sufficiency_allows_recommendation(top.evidence_sufficiency)
            else None
        ),
        explanation=build_ranking_report_explanation(
            top,
            tuple(items),
            goal_definition,
        ),
        limitations=report_limitations,
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
        evidence_sufficiency=report_sufficiency,
        is_provisional=bool(top and top.is_provisional),
        abstention_reason=(
            abstention_reason
            if report_sufficiency
            in {
                EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
                EvidenceSufficiency.NOT_SUPPORTED,
            }
            else None
        ),
        grounding=grounding_for_ranking_report(tuple(items)),
    )
    return apply_ranking_contradictions(report)


def _with_grounding(
    items: tuple[ExplainableRankingItem, ...],
) -> tuple[ExplainableRankingItem, ...]:
    return tuple(
        replace(
            item,
            grounding=build_ranking_grounding(
                goal=item.goal,
                ranking_drivers=item.ranking_drivers,
                supporting_metrics=item.supporting_metrics,
                confidence=item.confidence,
                freshness=item.freshness,
                evidence_sufficiency=item.evidence_sufficiency,
                limitations=item.limitations,
                score_margin=score_margin_for_item(item, items),
            ),
        )
        for item in items
    )


def component_scores(
    metrics: MarketMetrics,
    *,
    goal: CareerGoal,
    all_metrics: dict[str, MarketMetrics],
) -> tuple[ComponentScore, ...]:
    _raw, components = _raw_goal_score(
        metrics,
        goal=goal,
        maxima=_metric_maxima(all_metrics.values()),
    )
    return components


@dataclass(frozen=True, slots=True)
class _ObservedCounts:
    total: int | None
    observed_rows: int
    unknown_rows: int


def _observed_count_values(values: Any) -> _ObservedCounts:
    total = 0
    observed = 0
    unknown = 0
    for value, status in values:
        if status in OBSERVED_STATUSES:
            observed += 1
            total += value or 0
        else:
            unknown += 1
    return _ObservedCounts(
        total=total if observed else None,
        observed_rows=observed,
        unknown_rows=unknown,
    )


def _role_component_value(value: int | None) -> float | None:
    return float(value) if value is not None else None


def _role_activity_status(metrics: MarketMetrics, role: str) -> str:
    if metrics.role_observed_rows.get(role, 0) > 0:
        if metrics.role_active_postings.get(role, 0) == 0:
            return "observed_zero"
        return "observed"
    if metrics.role_unknown_rows.get(role, 0) > 0:
        return "unknown"
    return "unavailable"


def _role_family_keys(row: Any) -> tuple[str, ...]:
    role = row.role_family_summary
    if isinstance(role, dict) and role:
        return tuple(
            sorted(
                key.strip()
                for key in role
                if isinstance(key, str) and key.strip()
            )
        ) or ("unknown",)
    return (_role_family(row),)


def _role_family(row: Any) -> str:
    if isinstance(row.role_family_summary, dict) and len(row.role_family_summary) == 1:
        key = next(iter(row.role_family_summary))
        if isinstance(key, str) and key.strip():
            return key.strip()
    # Layer 31-32 curated imports store one role family per row in source files;
    # imported rows without a JSON summary can still be inferred from the fact id
    # only through the source row, so use a stable unknown bucket.
    return "unknown"


def _role_activity_limitations(
    components: tuple[ComponentScore, ...],
    metrics: MarketMetrics,
) -> tuple[str, ...]:
    role_components = {
        "product_activity": ("product", "Product role-family activity"),
        "ai_cloud_activity": ("ai_cloud_adjacent", "AI/cloud role-family activity"),
        "cybersecurity_activity": (
            "cybersecurity",
            "Cybersecurity role-family activity",
        ),
    }
    limitations: list[str] = []
    for component in components:
        role_config = role_components.get(component.code)
        if role_config is None or component.value is not None:
            continue
        role, label = role_config
        if metrics.role_unknown_rows.get(role, 0) > 0:
            limitations.append(f"{label} is unknown and is not treated as observed zero.")
        else:
            limitations.append(
                f"{label} is unavailable; no observed-zero role evidence is present."
            )
    return tuple(dict.fromkeys(limitations))


def _normalized_sector(value: str | None) -> str:
    return (value or "").strip().lower()


def _confidence_score(
    *,
    validation_ok: bool,
    fact_report: Any,
    source_report: Any,
    high_gap_count: int,
    medium_gap_count: int,
    ranking_limited_ratio: float,
) -> float:
    score = 1.0
    if not validation_ok:
        score -= 0.50
    if source_report.stale_source_count or source_report.expired_source_count:
        score -= 0.25
    if source_report.aging_source_count:
        score -= 0.10
    unknown_ratio = (
        fact_report.unknown_facts / fact_report.total_facts
        if fact_report.total_facts
        else 0.0
    )
    if unknown_ratio >= 0.30:
        score -= 0.20
    elif unknown_ratio > 0:
        score -= 0.08
    score -= min(0.30, ranking_limited_ratio * 0.30)
    if high_gap_count:
        score -= 0.15
    if medium_gap_count:
        score -= 0.08
    if fact_report.low_confidence_facts:
        score -= 0.08
    return round(max(0.0, min(1.0, score)), 4)


def _confidence_label(score: float) -> IntelligenceConfidence:
    if score >= 0.80:
        return IntelligenceConfidence.HIGH
    if score >= 0.60:
        return IntelligenceConfidence.MODERATE
    if score >= 0.40:
        return IntelligenceConfidence.LOW
    return IntelligenceConfidence.LIMITED


def _freshness_label(source_report: Any) -> IntelligenceFreshness:
    if source_report.stale_source_count or source_report.expired_source_count:
        return IntelligenceFreshness.STALE
    if source_report.aging_source_count:
        return IntelligenceFreshness.AGING
    if source_report.source_count:
        return IntelligenceFreshness.CURRENT
    return IntelligenceFreshness.UNKNOWN


def _limitations(
    *,
    snapshot: MarketOperationalSnapshot,
    fact_report: Any,
    source_report: Any,
    gap_codes: tuple[str, ...],
) -> tuple[str, ...]:
    items: list[str] = []
    if not snapshot.validation.ok:
        items.append("Curated files have validation errors.")
    if source_report.stale_source_count:
        items.append("One or more source references are stale.")
    if fact_report.ranking_excluded_facts:
        items.append("Some facts are excluded from ranking influence.")
    if fact_report.unknown_facts:
        items.append("Some count facts are unknown and are not treated as zero.")
    if "missing_coop_data" in gap_codes:
        items.append("Co-op coverage is limited or unavailable.")
    if "missing_30_day_hiring_counts" in gap_codes:
        items.append("30-day hiring counts are not collected.")
    if "missing_90_day_hiring_counts" in gap_codes:
        items.append("90-day hiring counts are not collected.")
    return tuple(dict.fromkeys(items))


def _metric_maxima(metrics_items: Any) -> dict[str, float]:
    metrics = tuple(metrics_items)
    keys = {
        "employer_presence": lambda item: float(item.employer_count),
        "hiring_activity": lambda item: float(item.active_posting_total or 0),
        "tech_signal": lambda item: float(
            (item.tech_density_score or 0)
            + item.ai_cloud_employer_count
            + item.cybersecurity_employer_count
            + item.major_tech_count
        ),
        "early_career": lambda item: float(
            (item.early_career_score or 0)
            + (item.entry_level_full_time_total or 0)
            + item.formal_program_count
        ),
        "formal_programs": lambda item: float(item.formal_program_count),
        "internship": lambda item: float(item.internship_total or 0),
        "product_activity": lambda item: float(item.product_activity or 0),
        "ai_cloud_activity": lambda item: float(item.ai_cloud_activity or 0),
        "ai_cloud_employers": lambda item: float(item.ai_cloud_employer_count),
        "cybersecurity_activity": lambda item: float(item.cybersecurity_activity or 0),
        "cybersecurity_employers": lambda item: float(item.cybersecurity_employer_count),
    }
    return {
        key: max((resolver(item) for item in metrics), default=0.0)
        for key, resolver in keys.items()
    }


def _raw_goal_score(
    metrics: MarketMetrics,
    *,
    goal: CareerGoal,
    maxima: dict[str, float],
) -> tuple[float, tuple[ComponentScore, ...]]:
    components: list[ComponentScore] = []
    for code, weight in goal_component_weights(goal).items():
        raw = _raw_component_value(metrics, code)
        maximum = maxima.get(code, 0.0)
        value = _normalize(raw, maximum)
        weighted = value * weight if value is not None else 0.0
        components.append(
            ComponentScore(
                code=code,
                label=_component_label(code),
                value=value,
                weight=weight,
                weighted_value=weighted,
                evidence=_component_evidence(metrics, code, raw),
            )
        )
    total_weight = sum(component.weight for component in components)
    if total_weight <= 0:
        return 0.0, tuple(components)
    # Missing components keep their configured weight so unknown evidence cannot
    # improve a market by renormalizing away an absent signal.
    raw_score = sum(component.weighted_value for component in components) / total_weight
    return max(0.0, min(1.0, raw_score)), tuple(components)


def _raw_component_value(metrics: MarketMetrics, code: str) -> float | None:
    values: dict[str, float | None] = {
        "employer_presence": float(metrics.employer_count),
        "hiring_activity": (
            float(metrics.active_posting_total)
            if metrics.active_posting_total is not None
            else None
        ),
        "tech_signal": float(
            (metrics.tech_density_score or 0)
            + metrics.ai_cloud_employer_count
            + metrics.cybersecurity_employer_count
            + metrics.major_tech_count
        ),
        "early_career": float(
            (metrics.early_career_score or 0)
            + (metrics.entry_level_full_time_total or 0)
            + metrics.formal_program_count
        ),
        "formal_programs": float(metrics.formal_program_count),
        "internship": (
            float(metrics.internship_total)
            if metrics.internship_total is not None
            else None
        ),
        "product_activity": _role_component_value(metrics.product_activity),
        "ai_cloud_activity": _role_component_value(metrics.ai_cloud_activity),
        "ai_cloud_employers": float(metrics.ai_cloud_employer_count),
        "cybersecurity_activity": _role_component_value(metrics.cybersecurity_activity),
        "cybersecurity_employers": float(metrics.cybersecurity_employer_count),
    }
    return values.get(code)


def _normalize(value: float | None, maximum: float) -> float | None:
    if value is None:
        return None
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, value / maximum))


def _confidence_adjusted_score(raw_score: float, metrics: MarketMetrics) -> float:
    confidence_factor = 0.75 + 0.25 * metrics.confidence_score
    freshness_factor = {
        IntelligenceFreshness.CURRENT: 1.0,
        IntelligenceFreshness.AGING: 0.90,
        IntelligenceFreshness.STALE: 0.70,
        IntelligenceFreshness.UNKNOWN: 0.80,
    }[metrics.freshness]
    ranking_factor = metrics.ranking_eligible_ratio
    return max(0.0, min(1.0, raw_score * confidence_factor * freshness_factor * ranking_factor))


def _ranking_drivers(components: tuple[ComponentScore, ...]) -> tuple[RankingDriver, ...]:
    drivers = [
        RankingDriver(
            code=component.code,
            label=component.label,
            contribution=round(component.weighted_value, 4),
            evidence=component.evidence,
        )
        for component in components
        if component.value is not None and component.weighted_value > 0
    ]
    return tuple(
        sorted(
            drivers,
            key=lambda item: (-item.contribution, item.code),
        )[:4]
    )


def _ranking_metrics(
    metrics: MarketMetrics,
    components: tuple[ComponentScore, ...],
) -> dict[str, int | float | str | None]:
    result = metrics.supporting_metrics()
    result.update(
        {
            f"component_{component.code}": (
                round(component.value, 4) if component.value is not None else None
            )
            for component in components
        }
    )
    return result


def _component_label(code: str) -> str:
    return {
        "hiring_activity": "observed hiring activity",
        "employer_presence": "employer presence",
        "tech_signal": "technology employer signal",
        "early_career": "early-career support",
        "formal_programs": "formal early-career programs",
        "internship": "internship ecosystem",
        "product_activity": "product role activity",
        "ai_cloud_activity": "AI/cloud role activity",
        "ai_cloud_employers": "AI/cloud employer presence",
        "cybersecurity_activity": "cybersecurity role activity",
        "cybersecurity_employers": "cybersecurity employer presence",
    }[code]


def _component_evidence(
    metrics: MarketMetrics,
    code: str,
    raw: float | None,
) -> str:
    if raw is None:
        return f"{_component_label(code)} is unavailable from current canonical facts."
    return f"{_component_label(code)} is supported by canonical metric value {raw:g}."
