"""Confidence scoring for Layer 24A policy intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from backend.policy.schemas import (
    PolicyConfidenceFactor,
    PolicyConfidenceMetadata,
    PolicyMetric,
    PolicyWarning,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus


@dataclass(frozen=True, slots=True)
class PolicyConfidenceInput:
    present_company_count: int
    hiring_record_count: int
    entry_level_record_count: int
    source_count: int
    freshness_status: FreshnessStatus
    metrics: tuple[PolicyMetric, ...]
    warnings: tuple[PolicyWarning, ...]


def build_policy_confidence(profile: PolicyConfidenceInput) -> PolicyConfidenceMetadata:
    score = 0.86
    factors: list[PolicyConfidenceFactor] = []

    if profile.present_company_count == 0:
        score -= 0.42
        factors.append(
            _factor(
                "missing_normalization_denominator",
                "high",
                "No present-company denominator is available.",
            )
        )
    elif profile.present_company_count < 5:
        score -= 0.30
        factors.append(
            _factor(
                "low_employer_coverage",
                "high",
                "The demonstrated employer base is small.",
            )
        )
    elif profile.present_company_count < 10:
        score -= 0.15
        factors.append(
            _factor(
                "limited_employer_coverage",
                "medium",
                "The demonstrated employer base is limited.",
            )
        )

    if profile.hiring_record_count < 3:
        score -= 0.14
        factors.append(
            _factor(
                "thin_hiring_signal_coverage",
                "medium",
                "Few employer hiring signal rows were available.",
            )
        )
    if profile.entry_level_record_count < 3:
        score -= 0.18
        factors.append(
            _factor(
                "thin_entry_level_signal_coverage",
                "medium",
                "Few employer early-career signal rows were available.",
            )
        )
    if profile.source_count == 0:
        score -= 0.10
        factors.append(
            _factor(
                "no_source_provenance_attached",
                "medium",
                "No source provenance links were attached to loaded records.",
            )
        )
    if profile.freshness_status is FreshnessStatus.UNKNOWN:
        score -= 0.12
        factors.append(
            _factor(
                "unknown_freshness",
                "medium",
                "Input freshness could not be confirmed.",
            )
        )
    elif profile.freshness_status is FreshnessStatus.STALE:
        score -= 0.25
        factors.append(
            _factor(
                "stale_inputs",
                "high",
                "One or more input freshness windows are stale.",
            )
        )

    unknown_metric_count = sum(1 for metric in profile.metrics if metric.score is None)
    if unknown_metric_count:
        score -= min(0.22, unknown_metric_count * 0.06)
        factors.append(
            _factor(
                "unknown_policy_metrics",
                "medium",
                "One or more policy metrics could not be scored from available inputs.",
            )
        )

    high_warning_count = sum(1 for warning in profile.warnings if warning.severity == "high")
    if high_warning_count:
        score -= min(0.18, high_warning_count * 0.08)
        factors.append(
            _factor(
                "high_severity_warnings",
                "high",
                "High-severity data limitations are present.",
            )
        )

    score = round(max(0.0, min(1.0, score)), 4)
    level = _level_for_score(score)
    if any(metric.metric_id == "talent_export_risk" for metric in profile.metrics):
        if level is Confidence.HIGH:
            level = Confidence.MEDIUM
            factors.append(
                _factor(
                    "bounded_interpretive_layer",
                    "medium",
                    "Policy intelligence is capped because outputs are interpretive.",
                )
            )

    return PolicyConfidenceMetadata(
        level=level,
        score=score,
        label=_label_for_level(level),
        factors=tuple(factors),
    )


def build_strategy_confidence(
    *,
    base: PolicyConfidenceMetadata,
    evidence_count: int,
    warnings: tuple[PolicyWarning, ...],
    interpretive_cap: Confidence = Confidence.MEDIUM,
) -> PolicyConfidenceMetadata:
    """Conservative confidence for Layer 24B strategy interpretation."""

    score = base.score
    factors = list(base.factors)
    if evidence_count == 0:
        score -= 0.25
        factors.append(
            _factor(
                "missing_strategy_evidence",
                "high",
                "No strategy evidence rows were available beyond the base policy profile.",
            )
        )
    elif evidence_count < 3:
        score -= 0.12
        factors.append(
            _factor(
                "thin_strategy_evidence",
                "medium",
                "Strategy interpretation is based on a small evidence set.",
            )
        )

    high_warning_count = sum(1 for warning in warnings if warning.severity == "high")
    medium_warning_count = sum(1 for warning in warnings if warning.severity == "medium")
    score -= min(0.20, high_warning_count * 0.08 + medium_warning_count * 0.03)
    score = round(max(0.0, min(1.0, score)), 4)
    raw_level = _level_for_score(score)
    level = _cap_level(raw_level, interpretive_cap)
    if level is not raw_level:
        factors.append(
            _factor(
                "strategy_interpretation_cap",
                "medium",
                "Strategy outputs are capped because they are directional interpretations.",
            )
        )

    return PolicyConfidenceMetadata(
        level=level,
        score=score,
        label=_label_for_level(level),
        factors=tuple(factors),
    )


def _level_for_score(score: float) -> Confidence:
    if score >= 0.74:
        return Confidence.HIGH
    if score >= 0.50:
        return Confidence.MEDIUM
    if score >= 0.25:
        return Confidence.LOW
    return Confidence.UNKNOWN


def _label_for_level(level: Confidence) -> str:
    if level is Confidence.HIGH:
        return "High confidence with bounded interpretation"
    if level is Confidence.MEDIUM:
        return "Medium confidence; local validation recommended"
    if level is Confidence.LOW:
        return "Low confidence; treat as directional"
    return "Unknown confidence from available data"


def _cap_level(level: Confidence, max_level: Confidence) -> Confidence:
    order = {
        Confidence.UNKNOWN: 0,
        Confidence.LOW: 1,
        Confidence.MEDIUM: 2,
        Confidence.HIGH: 3,
    }
    if order[level] <= order[max_level]:
        return level
    return max_level


def _factor(code: str, severity: str, explanation: str) -> PolicyConfidenceFactor:
    return PolicyConfidenceFactor(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        explanation=explanation,
    )
