"""Market profile generation over Layer 33 operational snapshots."""

from __future__ import annotations

from backend.imports.diagnostics import (
    coverage_gaps_from_snapshot,
    dataset_health_from_snapshot,
)
from backend.imports.operations import MarketOperationalSnapshot
from backend.market_intelligence.grounding import build_profile_grounding
from backend.market_intelligence.schemas import (
    MarketInsight,
    MarketIntelligenceProfile,
    OpportunityEnvironment,
)
from backend.market_intelligence.scoring import MarketMetrics


def build_market_profile(
    snapshot: MarketOperationalSnapshot,
    metrics: MarketMetrics,
    *,
    all_metrics: tuple[MarketMetrics, ...],
) -> MarketIntelligenceProfile:
    health = dataset_health_from_snapshot(snapshot)
    gaps = coverage_gaps_from_snapshot(snapshot)
    strengths = _strengths(metrics, all_metrics=all_metrics)
    weaknesses = _weaknesses(metrics, gaps=tuple(gaps.gaps))
    opportunity = _opportunity_environment(metrics)
    supporting_metrics = metrics.supporting_metrics()
    overview = (
        f"{metrics.market_name} has {metrics.employer_count} curated employer(s), "
        f"{_observed_label(metrics.active_posting_total, 'observed active posting')}, "
        f"and {metrics.formal_program_count} formal early-career program signal(s)."
    )
    return MarketIntelligenceProfile(
        market_key=metrics.market_key,
        market_name=metrics.market_name,
        region_id=metrics.region_id,
        overview=overview,
        strengths=strengths,
        weaknesses=weaknesses,
        hiring_summary=_hiring_summary(metrics),
        employer_summary=_employer_summary(metrics),
        internship_summary=_internship_summary(metrics),
        coop_summary=_coop_summary(metrics),
        early_career_summary=_early_career_summary(metrics),
        opportunity_environment=opportunity,
        confidence=metrics.confidence,
        confidence_score=metrics.confidence_score,
        freshness=metrics.freshness,
        coverage_summary=health.coverage_summary,
        limitations=metrics.limitations,
        supporting_metrics=supporting_metrics,
        grounding=build_profile_grounding(
            supporting_metrics=supporting_metrics,
            confidence=metrics.confidence,
            freshness=metrics.freshness,
            coverage_summary=health.coverage_summary,
            limitations=metrics.limitations,
        ),
    )


def _strengths(
    metrics: MarketMetrics,
    *,
    all_metrics: tuple[MarketMetrics, ...],
) -> tuple[MarketInsight, ...]:
    maxima = {
        "employers": max((item.employer_count for item in all_metrics), default=0),
        "hiring": max((item.active_posting_total or 0 for item in all_metrics), default=0),
        "ai_cloud": max(
            (signal for item in all_metrics if (signal := _ai_cloud_signal(item)) is not None),
            default=None,
        ),
        "internships": max((item.internship_total or 0 for item in all_metrics), default=0),
        "programs": max((item.formal_program_count for item in all_metrics), default=0),
    }
    strengths: list[MarketInsight] = []
    if metrics.employer_count and metrics.employer_count == maxima["employers"]:
        strengths.append(
            _insight(
                "strong_employer_presence",
                "Strong employer presence.",
                f"{metrics.employer_count} curated employers are present.",
                "Improves breadth for market comparison.",
            )
        )
    if (
        metrics.active_posting_total is not None
        and metrics.active_posting_total > 0
        and metrics.active_posting_total == maxima["hiring"]
    ):
        strengths.append(
            _insight(
                "strong_hiring_activity",
                "Strong observed hiring activity.",
                f"{metrics.active_posting_total} observed active postings are ranking-eligible.",
                "Improves near-term opportunity signal.",
            )
        )
    ai_cloud_signal = _ai_cloud_signal(metrics)
    if (
        ai_cloud_signal is not None
        and ai_cloud_signal > 0
        and ai_cloud_signal == maxima["ai_cloud"]
    ):
        strengths.append(
            _insight(
                "strong_ai_cloud_signal",
                "Strong AI/cloud signal.",
                (
                    f"{metrics.ai_cloud_employer_count} AI/cloud employer(s) and "
                    f"{metrics.ai_cloud_activity} observed AI/cloud posting(s)."
                ),
                "Supports AI/ML-oriented comparisons.",
            )
        )
    if (
        metrics.internship_total is not None
        and metrics.internship_total > 0
        and metrics.internship_total == maxima["internships"]
    ):
        strengths.append(
            _insight(
                "healthy_internship_ecosystem",
                "Healthy internship ecosystem.",
                f"{metrics.internship_total} observed internship opportunity count(s).",
                "Supports early-career market fit.",
            )
        )
    if metrics.formal_program_count and metrics.formal_program_count == maxima["programs"]:
        strengths.append(
            _insight(
                "formal_early_career_programs",
                "Formal early-career programs are present.",
                f"{metrics.formal_program_count} company fact(s) carry formal program signals.",
                "Improves structured entry-level support.",
            )
        )
    return tuple(strengths) or (
        _insight(
            "limited_positive_differentiators",
            "No strong positive differentiator was detected.",
            "Current canonical facts do not place this market at the top of a tracked dimension.",
            "Use with comparison context rather than as a standalone endorsement.",
        ),
    )


def _ai_cloud_signal(metrics: MarketMetrics) -> int | None:
    if metrics.ai_cloud_activity is None and metrics.ai_cloud_employer_count == 0:
        return None
    return metrics.ai_cloud_employer_count + (metrics.ai_cloud_activity or 0)


def _weaknesses(metrics: MarketMetrics, *, gaps: tuple[object, ...]) -> tuple[MarketInsight, ...]:
    weaknesses: list[MarketInsight] = []
    for gap in gaps[:3]:
        weaknesses.append(
            _insight(
                f"coverage_gap_{gap.gap_code}",
                gap.message,
                (
                    f"Coverage gap {gap.gap_code} has severity {gap.severity.value}; "
                    f"{_gap_metric_evidence(metrics, gap.gap_code)}"
                ),
                gap.estimated_impact,
            )
        )
    if metrics.coop_observed_rows == 0:
        weaknesses.append(
            _insight(
                "limited_coop_coverage",
                "Limited co-op coverage.",
                (
                    "0 ranking-eligible observed co-op count(s) are available "
                    f"across {metrics.coop_observed_rows} observed co-op fact(s)."
                ),
                "Limits internship/co-op ecosystem comparisons.",
            )
        )
    if metrics.active_posting_unknown_rows:
        weaknesses.append(
            _insight(
                "unknown_hiring_counts",
                "Some hiring counts are unknown.",
                f"{metrics.active_posting_unknown_rows} hiring fact(s) have unknown counts.",
                "Unknown values are not treated as zero.",
            )
        )
    if metrics.ranking_excluded_fact_count:
        weaknesses.append(
            _insight(
                "ranking_excluded_facts",
                "Some facts are excluded from ranking influence.",
                f"{metrics.ranking_excluded_fact_count} fact(s) are ranking-excluded.",
                "Reduces recommendation confidence.",
            )
        )
    if metrics.stale_source_count or metrics.expired_source_count:
        weaknesses.append(
            _insight(
                "stale_sources",
                "Some source references are stale or expired.",
                (
                    f"{metrics.stale_source_count} stale and "
                    f"{metrics.expired_source_count} expired source(s)."
                ),
                "Limits freshness and confidence.",
            )
        )
    return tuple(dict.fromkeys(weaknesses))


def _opportunity_environment(metrics: MarketMetrics) -> OpportunityEnvironment:
    return OpportunityEnvironment(
        hiring_activity=_hiring_summary(metrics),
        employer_diversity=_employer_summary(metrics),
        internship_ecosystem=_internship_summary(metrics),
        coop_ecosystem=_coop_summary(metrics),
        early_career_support=_early_career_summary(metrics),
        hiring_momentum=_momentum_summary(metrics),
        overall=(
            f"{metrics.market_name} has {metrics.confidence.value} confidence with "
            f"{metrics.freshness.value} source freshness."
        ),
    )


def _hiring_summary(metrics: MarketMetrics) -> str:
    observed = _observed_label(metrics.active_posting_total, "observed active posting")
    unknown = (
        f" {metrics.active_posting_unknown_rows} hiring count(s) are unknown and "
        "not treated as zero."
        if metrics.active_posting_unknown_rows
        else ""
    )
    return (
        f"{observed} across {metrics.active_posting_observed_rows} observed "
        f"hiring fact(s).{unknown}"
    )


def _employer_summary(metrics: MarketMetrics) -> str:
    return (
        f"{metrics.employer_count} curated employer(s) across {metrics.sector_count} "
        f"sector(s), including {metrics.major_tech_count} major-tech employer(s)."
    )


def _internship_summary(metrics: MarketMetrics) -> str:
    observed = _observed_label(metrics.internship_total, "observed internship count")
    return (
        f"{observed} across {metrics.internship_observed_rows} observed entry-level fact(s); "
        f"{metrics.internship_unknown_rows} internship count(s) are unknown."
    )


def _coop_summary(metrics: MarketMetrics) -> str:
    observed = _observed_label(metrics.coop_total, "observed co-op count")
    return (
        f"{observed} across {metrics.coop_observed_rows} observed entry-level fact(s); "
        f"{metrics.coop_unknown_rows} co-op count(s) are unknown or not collected."
    )


def _early_career_summary(metrics: MarketMetrics) -> str:
    full_time = _observed_label(
        metrics.entry_level_full_time_total,
        "observed entry-level full-time count",
    )
    return (
        f"{full_time}; {metrics.formal_program_count} formal early-career program "
        f"signal(s); {metrics.positive_entry_level_score_count} positive access score fact(s)."
    )


def _momentum_summary(metrics: MarketMetrics) -> str:
    if metrics.active_posting_total is None:
        return (
            "Hiring momentum is not inferred because observed short-window hiring "
            "counts are unavailable."
        )
    if metrics.active_posting_total > 0:
        return "Observed hiring activity is positive; no unsupported trend is inferred."
    return "Observed hiring activity is zero for collected rows; unknown rows remain unknown."


def _gap_metric_evidence(metrics: MarketMetrics, gap_code: str) -> str:
    if gap_code == "missing_coop_data":
        return (
            f"{metrics.coop_observed_rows} observed co-op fact(s), "
            f"{metrics.coop_unknown_rows} unknown co-op count(s), and "
            f"{metrics.ranking_eligible_fact_count} ranking-eligible fact(s)."
        )
    if gap_code in {"missing_30_day_hiring_counts", "missing_90_day_hiring_counts"}:
        return (
            f"{metrics.active_posting_observed_rows} observed hiring fact(s) and "
            f"{metrics.active_posting_unknown_rows} unknown hiring count(s)."
        )
    return f"{metrics.ranking_eligible_fact_count} ranking-eligible fact(s)."


def _observed_label(value: int | None, noun: str) -> str:
    if value is None:
        return f"No {noun} is available"
    return f"{value} {noun}{'' if value == 1 else 's'}"


def _insight(code: str, message: str, evidence: str, impact: str) -> MarketInsight:
    return MarketInsight(code=code, message=message, evidence=evidence, impact=impact)
