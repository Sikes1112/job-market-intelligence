"""Deterministic regional inequality and access metric generation."""

from __future__ import annotations

from collections import Counter

from backend.policy.metrics import (
    RegionalPolicyInputs,
    average,
    bounded,
    has_entry_level_access,
    hiring_signal_value,
    internship_pathway_count,
    normalized_entropy,
    normalized_hhi,
    positive_entry_pathway_count,
    public_metric_inputs,
    safe_ratio,
)
from backend.policy.schemas import PolicyMetric, RegionalPolicyMetrics, band_for_score


def build_regional_policy_metrics(inputs: RegionalPolicyInputs) -> RegionalPolicyMetrics:
    concentration = opportunity_concentration_metric(inputs)
    early_access = early_career_access_metric(inputs)
    internship_pipeline = internship_pipeline_metric(inputs)
    dependency = employer_dependency_metric(inputs)
    diversity = sector_diversity_metric(inputs)
    export_risk = talent_export_risk_metric(
        early_access=early_access,
        internship_pipeline=internship_pipeline,
        sector_diversity=diversity,
        employer_dependency=dependency,
    )
    return RegionalPolicyMetrics(
        opportunity_concentration_score=concentration,
        early_career_access_score=early_access,
        internship_pipeline_score=internship_pipeline,
        employer_dependency_score=dependency,
        sector_diversity_score=diversity,
        talent_export_risk_score=export_risk,
    )


def opportunity_concentration_metric(inputs: RegionalPolicyInputs) -> PolicyMetric:
    values_by_company = {
        row.company_id: value
        for row in inputs.hiring_rows
        if (value := hiring_signal_value(row)) is not None
    }
    warning_codes: list[str] = []
    limitations = [
        "Uses employer-level hiring shares, not raw regional posting totals.",
        "Hiring counts may be incomplete when source coverage is partial.",
    ]
    if not values_by_company:
        warning_codes.append("missing_hiring_signal_denominator")
        return _metric(
            metric_id="opportunity_concentration",
            label="Opportunity concentration",
            score=None,
            polarity="higher_is_risk",
            interpretation_label="Concentration unknown from available data",
            explainable_inputs=public_metric_inputs(
                hiring_record_count=inputs.hiring_record_count,
                present_company_count=inputs.present_company_count,
            ),
            limitations=tuple(limitations),
            warning_codes=tuple(warning_codes),
        )

    values = tuple(values_by_company.values())
    top_share = max(values) / sum(values) if sum(values) else 0.0
    hhi_score = normalized_hhi(values) or 0.0
    score = bounded((0.75 * hhi_score) + (0.25 * top_share))
    return _metric(
        metric_id="opportunity_concentration",
        label="Opportunity concentration",
        score=score,
        polarity="higher_is_risk",
        interpretation_label=_risk_label(score, "concentration"),
        explainable_inputs=public_metric_inputs(
            employer_signal_count=len(values_by_company),
            top_employer_share=top_share,
            normalized_hhi=hhi_score,
            observed_hiring_signal_total=sum(values),
        ),
        limitations=tuple(limitations),
        warning_codes=tuple(warning_codes),
    )


def early_career_access_metric(inputs: RegionalPolicyInputs) -> PolicyMetric:
    present_count = inputs.present_company_count
    warning_codes: list[str] = []
    limitations = [
        "Normalizes by demonstrated present employers where available.",
        "Missing entry-level rows are treated as unknown rather than zero.",
    ]
    if present_count <= 0:
        warning_codes.append("missing_normalization_denominator")
        return _metric(
            metric_id="early_career_access",
            label="Early-career access",
            score=None,
            polarity="higher_is_better",
            interpretation_label="Early-career access unknown from available data",
            explainable_inputs=public_metric_inputs(
                present_company_count=present_count,
                entry_level_record_count=inputs.entry_level_record_count,
            ),
            limitations=tuple(limitations),
            warning_codes=tuple(warning_codes),
        )
    if not inputs.entry_level_rows:
        warning_codes.append("missing_entry_level_records")
        return _metric(
            metric_id="early_career_access",
            label="Early-career access",
            score=None,
            polarity="higher_is_better",
            interpretation_label="Early-career access unknown from available data",
            explainable_inputs=public_metric_inputs(
                present_company_count=present_count,
                entry_level_record_count=0,
            ),
            limitations=tuple(limitations),
            warning_codes=tuple(warning_codes),
        )

    access_company_ids = {
        row.company_id
        for row in inputs.entry_level_rows
        if row.company_id in inputs.present_company_ids and has_entry_level_access(row)
    }
    access_ratio = safe_ratio(len(access_company_ids), present_count) or 0.0
    row_scores = tuple(
        row.entry_level_access_score
        for row in inputs.entry_level_rows
        if row.entry_level_access_score is not None
    )
    average_row_score = average(row_scores)
    market_score = (
        inputs.region_market_score.early_career_accessibility_score
        if inputs.region_market_score is not None
        else None
    )
    components = [0.45 * access_ratio]
    weight = 0.45
    if average_row_score is not None:
        components.append(0.35 * average_row_score)
        weight += 0.35
    else:
        warning_codes.append("missing_entry_access_scores")
    if market_score is not None:
        components.append(0.20 * market_score)
        weight += 0.20
    else:
        warning_codes.append("missing_region_early_career_score")
    score = bounded(sum(components) / weight)
    return _metric(
        metric_id="early_career_access",
        label="Early-career access",
        score=score,
        polarity="higher_is_better",
        interpretation_label=_access_label(score, "early-career access"),
        explainable_inputs=public_metric_inputs(
            present_company_count=present_count,
            companies_with_entry_level_access=len(access_company_ids),
            access_ratio=access_ratio,
            average_entry_level_access_score=average_row_score,
            region_early_career_accessibility_score=market_score,
        ),
        limitations=tuple(limitations),
        warning_codes=tuple(dict.fromkeys(warning_codes)),
    )


def internship_pipeline_metric(inputs: RegionalPolicyInputs) -> PolicyMetric:
    present_count = inputs.present_company_count
    warning_codes: list[str] = []
    limitations = [
        "Normalizes internship and co-op signals by demonstrated present employers.",
        "Formal early-career programs are counted as pathway evidence, not placement promises.",
    ]
    if present_count <= 0:
        warning_codes.append("missing_normalization_denominator")
        return _metric(
            metric_id="internship_pipeline",
            label="Internship pipeline",
            score=None,
            polarity="higher_is_better",
            interpretation_label="Internship pipeline unknown from available data",
            explainable_inputs=public_metric_inputs(
                present_company_count=present_count,
                entry_level_record_count=inputs.entry_level_record_count,
            ),
            limitations=tuple(limitations),
            warning_codes=tuple(warning_codes),
        )
    if not inputs.entry_level_rows:
        warning_codes.append("missing_entry_level_records")
        return _metric(
            metric_id="internship_pipeline",
            label="Internship pipeline",
            score=None,
            polarity="higher_is_better",
            interpretation_label="Internship pipeline unknown from available data",
            explainable_inputs=public_metric_inputs(
                present_company_count=present_count,
                entry_level_record_count=0,
            ),
            limitations=tuple(limitations),
            warning_codes=tuple(warning_codes),
        )

    internship_counts = tuple(
        value
        for row in inputs.entry_level_rows
        if (value := internship_pathway_count(row)) is not None
    )
    if len(internship_counts) < len(inputs.entry_level_rows):
        warning_codes.append("unknown_internship_counts")
    internship_total = sum(internship_counts)
    internship_company_ids = {
        row.company_id
        for row in inputs.entry_level_rows
        if row.company_id in inputs.present_company_ids
        and (internship_pathway_count(row) or 0) > 0
    }
    program_company_ids = {
        row.company_id
        for row in inputs.entry_level_rows
        if row.company_id in inputs.present_company_ids
        and row.formal_early_career_program_flag
    }
    company_ratio = safe_ratio(len(internship_company_ids), present_count) or 0.0
    density = min(1.0, internship_total / (present_count * 2.0))
    program_ratio = safe_ratio(len(program_company_ids), present_count) or 0.0
    score = bounded((0.50 * company_ratio) + (0.35 * density) + (0.15 * program_ratio))
    return _metric(
        metric_id="internship_pipeline",
        label="Internship pipeline",
        score=score,
        polarity="higher_is_better",
        interpretation_label=_access_label(score, "internship pipeline"),
        explainable_inputs=public_metric_inputs(
            present_company_count=present_count,
            companies_with_internship_or_coop=len(internship_company_ids),
            internship_company_ratio=company_ratio,
            internship_and_coop_count_total=internship_total,
            internship_density_per_present_company=internship_total / present_count,
            formal_program_company_count=len(program_company_ids),
        ),
        limitations=tuple(limitations),
        warning_codes=tuple(dict.fromkeys(warning_codes)),
    )


def employer_dependency_metric(inputs: RegionalPolicyInputs) -> PolicyMetric:
    warning_codes: list[str] = []
    limitations = [
        "Uses aggregate employer share signals and does not identify a single employer.",
        "High dependency is a concentration signal, not a causal diagnosis.",
    ]
    hiring_values = {
        row.company_id: value
        for row in inputs.hiring_rows
        if (value := hiring_signal_value(row)) is not None
    }
    top_hiring_share = (
        max(hiring_values.values()) / sum(hiring_values.values())
        if hiring_values and sum(hiring_values.values()) > 0
        else None
    )
    entry_values = {
        row.company_id: value
        for row in inputs.entry_level_rows
        if (value := positive_entry_pathway_count(row)) > 0
    }
    top_entry_share = (
        max(entry_values.values()) / sum(entry_values.values())
        if entry_values and sum(entry_values.values()) > 0
        else None
    )
    major_tech_share = safe_ratio(
        sum(1 for company in inputs.present_companies if company.is_major_tech or company.is_mag7),
        inputs.present_company_count,
    )
    observed = tuple(
        value
        for value in (top_hiring_share, top_entry_share, major_tech_share)
        if value is not None
    )
    if not observed:
        warning_codes.append("missing_employer_dependency_inputs")
        score = None
        label = "Employer dependency unknown from available data"
    else:
        score = bounded(max(observed))
        label = _risk_label(score, "employer dependency")
    return _metric(
        metric_id="employer_dependency",
        label="Employer dependency",
        score=score,
        polarity="higher_is_risk",
        interpretation_label=label,
        explainable_inputs=public_metric_inputs(
            hiring_employer_signal_count=len(hiring_values),
            top_hiring_share=top_hiring_share,
            top_entry_pathway_share=top_entry_share,
            major_tech_or_mag7_present_share=major_tech_share,
            present_company_count=inputs.present_company_count,
        ),
        limitations=tuple(limitations),
        warning_codes=tuple(warning_codes),
    )


def sector_diversity_metric(inputs: RegionalPolicyInputs) -> PolicyMetric:
    warning_codes: list[str] = []
    limitations = [
        "Uses primary sector labels on present canonical companies.",
        "Unknown sector labels reduce interpretability but are not treated as a sector.",
    ]
    sectors = [
        company.sector_primary
        for company in inputs.present_companies
        if company.sector_primary is not None and company.sector_primary.strip()
    ]
    unknown_sector_count = inputs.present_company_count - len(sectors)
    if inputs.present_company_count <= 0:
        warning_codes.append("missing_normalization_denominator")
    if unknown_sector_count:
        warning_codes.append("missing_sector_classification")
    sector_counts = Counter(sectors)
    score = normalized_entropy(tuple(sector_counts.values()))
    label = (
        "Sector diversity unknown from available data"
        if score is None
        else _access_label(score, "sector diversity")
    )
    return _metric(
        metric_id="sector_diversity",
        label="Sector diversity",
        score=score,
        polarity="higher_is_better",
        interpretation_label=label,
        explainable_inputs=public_metric_inputs(
            present_company_count=inputs.present_company_count,
            classified_company_count=len(sectors),
            distinct_sector_count=len(sector_counts),
            unknown_sector_count=unknown_sector_count,
        ),
        limitations=tuple(limitations),
        warning_codes=tuple(dict.fromkeys(warning_codes)),
    )


def talent_export_risk_metric(
    *,
    early_access: PolicyMetric,
    internship_pipeline: PolicyMetric,
    sector_diversity: PolicyMetric,
    employer_dependency: PolicyMetric,
) -> PolicyMetric:
    warning_codes = ["talent_export_is_proxy"]
    limitations = [
        "This is a directional proxy for local pathway weakness, not migration measurement.",
        "Further local validation is recommended before program or funding decisions.",
    ]
    components: list[float] = []
    inputs: dict[str, float | None] = {
        "early_career_access_score": early_access.score,
        "internship_pipeline_score": internship_pipeline.score,
        "sector_diversity_score": sector_diversity.score,
        "employer_dependency_score": employer_dependency.score,
    }
    if early_access.score is not None:
        components.append(0.42 * (1.0 - early_access.score))
    if internship_pipeline.score is not None:
        components.append(0.32 * (1.0 - internship_pipeline.score))
    if sector_diversity.score is not None:
        components.append(0.16 * (1.0 - sector_diversity.score))
    if employer_dependency.score is not None:
        components.append(0.10 * employer_dependency.score)
    if len(components) < 2:
        warning_codes.append("insufficient_talent_export_inputs")
        score = None
        label = "Talent export risk unknown from available data"
    else:
        score = bounded(sum(components) / _component_weight_sum(inputs))
        label = _risk_label(score, "talent export risk")
    return _metric(
        metric_id="talent_export_risk",
        label="Talent export risk",
        score=score,
        polarity="higher_is_risk",
        interpretation_label=label,
        explainable_inputs=public_metric_inputs(**inputs),
        limitations=tuple(limitations),
        warning_codes=tuple(dict.fromkeys(warning_codes)),
    )


def _component_weight_sum(values: dict[str, float | None]) -> float:
    weights = {
        "early_career_access_score": 0.42,
        "internship_pipeline_score": 0.32,
        "sector_diversity_score": 0.16,
        "employer_dependency_score": 0.10,
    }
    total = sum(weight for key, weight in weights.items() if values[key] is not None)
    return total or 1.0


def _metric(
    *,
    metric_id: str,
    label: str,
    score: float | None,
    polarity: str,
    interpretation_label: str,
    explainable_inputs: dict,
    limitations: tuple[str, ...],
    warning_codes: tuple[str, ...],
) -> PolicyMetric:
    return PolicyMetric(
        metric_id=metric_id,
        label=label,
        score=score,
        band=band_for_score(score),
        polarity=polarity,  # type: ignore[arg-type]
        interpretation_label=interpretation_label,
        explainable_inputs=explainable_inputs,
        limitations=limitations,
        warning_codes=warning_codes,
    )


def _risk_label(score: float | None, subject: str) -> str:
    if score is None:
        return f"{subject.title()} unknown"
    if score >= 0.8:
        return f"Very high {subject} signal"
    if score >= 0.65:
        return f"High {subject} signal"
    if score >= 0.4:
        return f"Moderate {subject} signal"
    if score >= 0.2:
        return f"Low {subject} signal"
    return f"Very low {subject} signal"


def _access_label(score: float | None, subject: str) -> str:
    if score is None:
        return f"{subject.title()} unknown"
    if score >= 0.8:
        return f"Very high {subject} signal"
    if score >= 0.65:
        return f"High {subject} signal"
    if score >= 0.4:
        return f"Moderate {subject} signal"
    if score >= 0.2:
        return f"Low {subject} signal"
    return f"Very low {subject} signal"
