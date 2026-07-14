"""Market differentiation audit for Layer 34C quality checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations

from backend.market_intelligence.explanations import (
    has_public_evidence_detail,
    has_unsupported_city_stereotype,
    is_generic_market_language,
    normalize_public_text,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    CrossGoalRankCorrelation,
    DifferentiationFinding,
    DifferentiationFindingCode,
    DifferentiationSeverity,
    ExplainableRankingReport,
    MarketDifferentiationAudit,
    MarketInsight,
    MarketIntelligenceProfile,
)
from backend.market_intelligence.sufficiency import sufficiency_requires_abstention


@dataclass(frozen=True, slots=True)
class _TextAppearance:
    field: str
    market_key: str
    text: str
    context_text: str
    evidence_fingerprint: tuple[tuple[str, str], ...]


def evaluate_market_differentiation(
    *,
    profiles: tuple[MarketIntelligenceProfile, ...],
    rankings: dict[CareerGoal, ExplainableRankingReport],
) -> MarketDifferentiationAudit:
    """Audit whether profiles and rankings are meaningfully differentiated."""

    ordered_profiles = tuple(sorted(profiles, key=lambda item: item.market_key))
    ordered_rankings = {
        goal: rankings[goal] for goal in sorted(rankings, key=lambda item: item.value)
    }
    duplicated_language, true_similarity_notes = _duplicated_language_findings(
        ordered_profiles
    )
    quality_findings = _language_quality_findings(ordered_profiles)
    repeated_driver_findings = _repeated_driver_findings(ordered_rankings)
    correlations = _cross_goal_rank_correlations(ordered_rankings)
    substantive_goals = _substantive_goals(ordered_rankings)
    cross_goal_notes = _cross_goal_diagnostic_notes(
        correlations,
        substantive_goals=substantive_goals,
    )

    language_findings = tuple(
        sorted(
            {*duplicated_language, *quality_findings},
            key=_finding_sort_key,
        )
    )
    driver_findings = tuple(
        sorted(repeated_driver_findings, key=_finding_sort_key)
    )
    recommendations = _recommendations(
        language_findings=language_findings,
        driver_findings=driver_findings,
        correlations=correlations,
        substantive_goals=substantive_goals,
    )
    return MarketDifferentiationAudit(
        profile_count=len(ordered_profiles),
        goal_count=len(ordered_rankings),
        differentiation_score=_differentiation_score(
            language_findings=language_findings,
            driver_findings=driver_findings,
            correlations=correlations,
            substantive_goals=substantive_goals,
        ),
        duplicated_language_findings=language_findings,
        repeated_driver_findings=driver_findings,
        cross_goal_rank_correlation_summary=correlations,
        required_improvement_recommendations=recommendations,
        true_similarity_notes=tuple(sorted((*true_similarity_notes, *cross_goal_notes))),
    )


def _duplicated_language_findings(
    profiles: tuple[MarketIntelligenceProfile, ...],
) -> tuple[tuple[DifferentiationFinding, ...], tuple[str, ...]]:
    appearances_by_key: dict[tuple[str, str], list[_TextAppearance]] = {}
    for profile in profiles:
        for appearance in _profile_text_appearances(profile):
            normalized = _normalize(appearance.text)
            if normalized:
                appearances_by_key.setdefault(
                    (appearance.field, normalized),
                    [],
                ).append(appearance)

    findings: list[DifferentiationFinding] = []
    true_similarity_notes: list[str] = []
    for (field, _normalized), appearances in sorted(appearances_by_key.items()):
        markets = tuple(sorted({item.market_key for item in appearances}))
        if len(markets) < 2:
            continue
        text = appearances[0].text
        if _is_true_similarity(appearances):
            true_similarity_notes.append(
                f"{field} language is similar for {', '.join(markets)} because "
                "the public evidence fingerprint is also identical."
            )
            continue
        context_text = " ".join(item.context_text for item in appearances)
        findings.append(
            DifferentiationFinding(
                code=_language_code(field),
                severity=_language_severity(
                    text,
                    context_text=context_text,
                    market_count=len(markets),
                ),
                field=field,
                market_keys=markets,
                goal_keys=(),
                message=f"{field.replace('_', ' ')} language repeats across markets.",
                evidence=_truncated_evidence(text),
                recommendation=(
                    "Use existing canonical market-specific evidence in this profile "
                    "field before presenting the markets as distinct; do not invent "
                    "differences where evidence is absent."
                ),
            )
        )
    return tuple(findings), tuple(true_similarity_notes)


def _language_quality_findings(
    profiles: tuple[MarketIntelligenceProfile, ...],
) -> tuple[DifferentiationFinding, ...]:
    findings: list[DifferentiationFinding] = []
    for profile in profiles:
        texts = tuple(_quality_texts(profile))
        generic_texts = tuple(text for text in texts if _is_generic_description(text))
        stereotype_texts = tuple(
            text for text in texts if _has_unsupported_stereotype(text)
        )
        if generic_texts:
            findings.append(
                DifferentiationFinding(
                    code=DifferentiationFindingCode.GENERIC_DESCRIPTION,
                    severity=DifferentiationSeverity.NEEDS_IMPROVEMENT,
                    field="profile_language",
                    market_keys=(profile.market_key,),
                    goal_keys=(),
                    message="Profile language is too generic to support differentiation.",
                    evidence=_truncated_evidence(generic_texts[0]),
                    recommendation=(
                        "Replace generic market language with available public "
                        "canonical evidence, or mark the profile as lacking "
                        "market-specific support."
                    ),
                )
            )
        if stereotype_texts:
            findings.append(
                DifferentiationFinding(
                    code=DifferentiationFindingCode.UNSUPPORTED_STEREOTYPE,
                    severity=DifferentiationSeverity.NEEDS_IMPROVEMENT,
                    field="profile_language",
                    market_keys=(profile.market_key,),
                    goal_keys=(),
                    message="Profile language contains an unsupported market stereotype.",
                    evidence=_truncated_evidence(stereotype_texts[0]),
                    recommendation=(
                        "Remove stereotype or trend language unless it is directly "
                        "grounded in public canonical evidence."
                    ),
                )
            )
        if _missing_market_specific_evidence(profile):
            findings.append(
                DifferentiationFinding(
                    code=DifferentiationFindingCode.MISSING_MARKET_SPECIFIC_EVIDENCE,
                    severity=DifferentiationSeverity.NEEDS_IMPROVEMENT,
                    field="profile_language",
                    market_keys=(profile.market_key,),
                    goal_keys=(),
                    message="Profile text lacks market-specific public evidence.",
                    evidence=_truncated_evidence(profile.overview),
                    recommendation=(
                        "Surface observed counts, unknown-vs-zero context, or other "
                        "canonical market-specific evidence before relying on this "
                        "profile for comparison."
                    ),
                )
            )
    return tuple(findings)


def _repeated_driver_findings(
    rankings: dict[CareerGoal, ExplainableRankingReport],
) -> tuple[DifferentiationFinding, ...]:
    findings: list[DifferentiationFinding] = []
    for goal, ranking in rankings.items():
        signatures: dict[
            tuple[str, ...],
            list[tuple[str, tuple[float, ...], tuple[str, ...]]],
        ] = {}
        ranked_markets = tuple(
            sorted(ranking.ranked_markets, key=lambda item: item.market_key)
        )
        threshold = max(2, int(len(ranked_markets) * 0.75))
        for item in ranked_markets:
            signature = tuple(driver.code for driver in item.ranking_drivers[:3])
            if not signature:
                continue
            signatures.setdefault(signature, []).append(
                (
                    item.market_key,
                    tuple(driver.contribution for driver in item.ranking_drivers[:3]),
                    tuple(driver.evidence for driver in item.ranking_drivers[:3]),
                )
            )
        for signature, appearances in sorted(signatures.items()):
            markets = tuple(
                sorted(market for market, _contrib, _evidence in appearances)
            )
            if len(markets) < threshold:
                continue
            public_evidence_variants = {
                (contributions, evidence)
                for _market, contributions, evidence in appearances
            }
            severity = (
                DifferentiationSeverity.WARNING
                if len(public_evidence_variants) > 1
                else DifferentiationSeverity.NEEDS_IMPROVEMENT
            )
            findings.append(
                DifferentiationFinding(
                    code=DifferentiationFindingCode.REPEATED_DRIVER,
                    severity=severity,
                    field="ranking_drivers",
                    market_keys=markets,
                    goal_keys=(goal,),
                    message=(
                        f"{goal.value} ranking repeats the same top driver sequence "
                        "across many markets."
                    ),
                    evidence=(
                        "Top driver codes: "
                        f"{', '.join(signature)}; public evidence variants: "
                        f"{len(public_evidence_variants)}."
                    ),
                    recommendation=(
                        "Review whether the repeated drivers reflect true canonical "
                        "similarity or missing goal-specific evidence; do not add "
                        "distinctions without supporting facts."
                    ),
                )
            )
    return tuple(findings)


def _cross_goal_rank_correlations(
    rankings: dict[CareerGoal, ExplainableRankingReport],
) -> tuple[CrossGoalRankCorrelation, ...]:
    summaries: list[CrossGoalRankCorrelation] = []
    for goal_a, goal_b in combinations(sorted(rankings, key=lambda item: item.value), 2):
        ranks_a = {
            item.market_key: item.rank for item in rankings[goal_a].ranked_markets
        }
        ranks_b = {
            item.market_key: item.rank for item in rankings[goal_b].ranked_markets
        }
        common = tuple(sorted(set(ranks_a) & set(ranks_b)))
        order_a = tuple(
            item.market_key
            for item in sorted(rankings[goal_a].ranked_markets, key=lambda item: item.rank)
            if item.market_key in common
        )
        order_b = tuple(
            item.market_key
            for item in sorted(rankings[goal_b].ranked_markets, key=lambda item: item.rank)
            if item.market_key in common
        )
        correlation = _spearman_correlation(common, ranks_a, ranks_b)
        identical = bool(common) and order_a == order_b
        nearly_identical = identical or (
            correlation is not None and correlation >= 0.95
        )
        shared_top = (
            order_a[0]
            if order_a and order_b and order_a[0] == order_b[0]
            else None
        )
        summaries.append(
            CrossGoalRankCorrelation(
                goal_a=goal_a,
                goal_b=goal_b,
                common_market_count=len(common),
                spearman_correlation=correlation,
                identical_order=identical,
                nearly_identical=nearly_identical,
                shared_top_market_key=shared_top,
                rank_deltas={
                    market: ranks_a[market] - ranks_b[market] for market in common
                },
            )
        )
    return tuple(
        sorted(summaries, key=lambda item: (item.goal_a.value, item.goal_b.value))
    )


def _spearman_correlation(
    common: tuple[str, ...],
    ranks_a: dict[str, int],
    ranks_b: dict[str, int],
) -> float | None:
    count = len(common)
    if count < 2:
        return None
    squared_delta = sum((ranks_a[market] - ranks_b[market]) ** 2 for market in common)
    denominator = count * (count * count - 1)
    return round(1 - ((6 * squared_delta) / denominator), 4)


def _differentiation_score(
    *,
    language_findings: tuple[DifferentiationFinding, ...],
    driver_findings: tuple[DifferentiationFinding, ...],
    correlations: tuple[CrossGoalRankCorrelation, ...],
    substantive_goals: frozenset[CareerGoal],
) -> float:
    penalty = 0.0
    for finding in (*language_findings, *driver_findings):
        if finding.severity is DifferentiationSeverity.NEEDS_IMPROVEMENT:
            penalty += 0.10
        elif finding.severity is DifferentiationSeverity.WARNING:
            penalty += 0.01
    for correlation in correlations:
        if not _correlation_is_substantive(correlation, substantive_goals):
            continue
        if correlation.identical_order:
            penalty += 0.08
        elif correlation.nearly_identical:
            penalty += 0.04
    return round(max(0.0, min(1.0, 1.0 - penalty)), 4)


def _recommendations(
    *,
    language_findings: tuple[DifferentiationFinding, ...],
    driver_findings: tuple[DifferentiationFinding, ...],
    correlations: tuple[CrossGoalRankCorrelation, ...],
    substantive_goals: frozenset[CareerGoal],
) -> tuple[str, ...]:
    recommendations = {
        finding.recommendation
        for finding in (*language_findings, *driver_findings)
        if finding.severity is DifferentiationSeverity.NEEDS_IMPROVEMENT
    }
    if any(
        correlation.nearly_identical
        and _correlation_is_substantive(correlation, substantive_goals)
        for correlation in correlations
    ):
        recommendations.add(
            "Review goal-specific evidence definitions and ranking drivers where "
            "cross-goal ordering is nearly identical; preserve similarities that "
            "are directly supported by canonical evidence."
        )
    return tuple(sorted(recommendations))


def _substantive_goals(
    rankings: dict[CareerGoal, ExplainableRankingReport],
) -> frozenset[CareerGoal]:
    return frozenset(
        goal
        for goal, ranking in rankings.items()
        if ranking.top_market_key is not None
        and not sufficiency_requires_abstention(ranking.evidence_sufficiency)
    )


def _correlation_is_substantive(
    correlation: CrossGoalRankCorrelation,
    substantive_goals: frozenset[CareerGoal],
) -> bool:
    return (
        correlation.goal_a in substantive_goals
        and correlation.goal_b in substantive_goals
    )


def _cross_goal_diagnostic_notes(
    correlations: tuple[CrossGoalRankCorrelation, ...],
    *,
    substantive_goals: frozenset[CareerGoal],
) -> tuple[str, ...]:
    return tuple(
        (
            f"{correlation.goal_a.value} and {correlation.goal_b.value} ordering is "
            "diagnostic because at least one goal abstains or is not supported; "
            "it is not counted as substantive market superiority."
        )
        for correlation in correlations
        if not _correlation_is_substantive(correlation, substantive_goals)
    )


def _profile_text_appearances(
    profile: MarketIntelligenceProfile,
) -> tuple[_TextAppearance, ...]:
    return (
        _appearance("overview", profile.market_key, profile.overview, profile),
        *(
            _appearance(
                "strength",
                profile.market_key,
                _insight_text(insight),
                profile,
            )
            for insight in profile.strengths
        ),
        *(
            _appearance(
                "strength_message",
                profile.market_key,
                insight.message,
                profile,
                context_text=_insight_text(insight),
            )
            for insight in profile.strengths
        ),
        *(
            _appearance(
                "weakness",
                profile.market_key,
                _insight_text(insight),
                profile,
            )
            for insight in profile.weaknesses
        ),
        *(
            _appearance(
                "weakness_message",
                profile.market_key,
                insight.message,
                profile,
                context_text=_insight_text(insight),
            )
            for insight in profile.weaknesses
        ),
    )


def _appearance(
    field: str,
    market_key: str,
    text: str,
    profile: MarketIntelligenceProfile,
    context_text: str | None = None,
) -> _TextAppearance:
    return _TextAppearance(
        field=field,
        market_key=market_key,
        text=text,
        context_text=context_text or text,
        evidence_fingerprint=_evidence_fingerprint(profile),
    )


def _quality_texts(profile: MarketIntelligenceProfile) -> tuple[str, ...]:
    return (
        profile.overview,
        profile.hiring_summary,
        profile.employer_summary,
        profile.internship_summary,
        profile.coop_summary,
        profile.early_career_summary,
        profile.coverage_summary,
        profile.opportunity_environment.overall,
        *(_insight_text(insight) for insight in profile.strengths),
        *(_insight_text(insight) for insight in profile.weaknesses),
    )


def _insight_text(insight: MarketInsight) -> str:
    return f"{insight.message} {insight.evidence} {insight.impact}"


def _evidence_fingerprint(
    profile: MarketIntelligenceProfile,
) -> tuple[tuple[str, str], ...]:
    selected = {
        key: profile.supporting_metrics.get(key)
        for key in (
            "active_posting_total",
            "ai_cloud_active_postings",
            "cybersecurity_active_postings",
            "employer_count",
            "formal_program_count",
            "internship_total",
            "observed_zero_fact_count",
            "product_active_postings",
            "ranking_eligible_fact_count",
            "unknown_fact_count",
        )
        if key in profile.supporting_metrics
    }
    return tuple((key, str(value)) for key, value in sorted(selected.items()))


def _is_true_similarity(appearances: list[_TextAppearance]) -> bool:
    fingerprints = {appearance.evidence_fingerprint for appearance in appearances}
    text = " ".join(appearance.context_text for appearance in appearances)
    return len(fingerprints) == 1 and has_public_evidence_detail(text)


def _missing_market_specific_evidence(profile: MarketIntelligenceProfile) -> bool:
    overview = _normalize(profile.overview)
    if _normalize(profile.market_name) in overview and has_public_evidence_detail(
        profile.overview
    ):
        return False
    all_text = " ".join(_quality_texts(profile))
    return not has_public_evidence_detail(all_text)


def _is_generic_description(text: str) -> bool:
    return is_generic_market_language(text)


def _has_unsupported_stereotype(text: str) -> bool:
    return has_unsupported_city_stereotype(text)


def _language_code(field: str) -> DifferentiationFindingCode:
    if field == "overview":
        return DifferentiationFindingCode.REPEATED_OVERVIEW
    if field.startswith("strength"):
        return DifferentiationFindingCode.REPEATED_STRENGTH
    return DifferentiationFindingCode.REPEATED_WEAKNESS


def _language_severity(
    text: str,
    *,
    context_text: str,
    market_count: int,
) -> DifferentiationSeverity:
    if _is_generic_description(text) or not has_public_evidence_detail(context_text):
        return DifferentiationSeverity.NEEDS_IMPROVEMENT
    if market_count >= 3:
        return DifferentiationSeverity.WARNING
    return DifferentiationSeverity.INFO


def _truncated_evidence(text: str) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) <= 220:
        return compacted
    return f"{compacted[:217]}..."


def _normalize(text: str) -> str:
    return normalize_public_text(text)


def _finding_sort_key(
    finding: DifferentiationFinding,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...], str]:
    return (
        finding.code.value,
        finding.field,
        finding.market_keys,
        tuple(goal.value for goal in finding.goal_keys),
        finding.evidence,
    )
