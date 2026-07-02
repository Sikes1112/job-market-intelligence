"""Layer 24A warning generation and policy-language guardrails."""

from __future__ import annotations

from backend.policy.metrics import RegionalPolicyInputs
from backend.policy.schemas import PolicyMetric, PolicyWarning
from backend.shared.freshness import FreshnessStatus

LOW_DATA_PRESENT_COMPANY_THRESHOLD = 5
LOW_DATA_SIGNAL_RECORD_THRESHOLD = 3


def build_policy_warnings(
    *,
    inputs: RegionalPolicyInputs,
    metrics: tuple[PolicyMetric, ...],
    freshness_status: FreshnessStatus,
    source_count: int,
) -> tuple[PolicyWarning, ...]:
    warnings: dict[str, PolicyWarning] = {}

    def add(warning: PolicyWarning) -> None:
        warnings[warning.code] = warning

    if inputs.present_company_count < LOW_DATA_PRESENT_COMPANY_THRESHOLD:
        add(
            _warning(
                "low_data_region",
                "high",
                "The region has limited demonstrated employer coverage.",
                (
                    "Available data should be read as directional because the "
                    "demonstrated employer base is small."
                ),
            )
        )
    if (
        inputs.hiring_record_count < LOW_DATA_SIGNAL_RECORD_THRESHOLD
        or inputs.entry_level_record_count < LOW_DATA_SIGNAL_RECORD_THRESHOLD
    ):
        add(
            _warning(
                "low_signal_coverage",
                "medium",
                "Hiring or early-career signal coverage is limited.",
                (
                    "Regional conclusions may shift as more employer-level signals "
                    "are collected."
                ),
            )
        )
    if inputs.region_market_score is None:
        add(
            _warning(
                "missing_region_score",
                "medium",
                "No canonical region market score is available for this region.",
                (
                    "Policy outputs rely more heavily on company-level records and "
                    "should not be read as complete market scoring."
                ),
            )
        )
    if inputs.present_company_count == 0:
        add(
            _warning(
                "missing_normalization_denominator",
                "high",
                "No demonstrated present-company denominator is available.",
                (
                    "Raw regional counts are not enough for fair regional policy "
                    "interpretation without a normalization basis."
                ),
            )
        )
    if freshness_status is FreshnessStatus.UNKNOWN:
        add(
            _warning(
                "unknown_source_freshness",
                "medium",
                "Source freshness is unknown for one or more policy inputs.",
                "Further source review is recommended before current-state claims.",
            )
        )
    if freshness_status is FreshnessStatus.STALE:
        add(
            _warning(
                "stale_policy_inputs",
                "high",
                "One or more policy input freshness windows are stale.",
                "Current regional interpretation requires refreshed inputs.",
            )
        )
    if source_count == 0:
        add(
            _warning(
                "no_source_provenance_attached",
                "medium",
                "No source provenance links were attached to the loaded policy inputs.",
                (
                    "The output remains based on canonical structured records, but "
                    "public citation strength is limited."
                ),
            )
        )
    add(
        _warning(
            "bounded_public_interpretation",
            "info",
            "Policy findings are bounded interpretations of available labor-market signals.",
            "They should be validated with local public, education, and employer context.",
        )
    )

    for metric in metrics:
        for code in metric.warning_codes:
            if code not in warnings:
                add(
                    _warning(
                        code,
                        "medium",
                        f"The {metric.label.casefold()} metric reported {code}.",
                        "The affected metric should be read with its limitations.",
                    )
                )

    return tuple(warnings[code] for code in sorted(warnings))


def _warning(
    code: str,
    severity: str,
    message: str,
    public_interpretation: str,
) -> PolicyWarning:
    return PolicyWarning(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        public_interpretation=public_interpretation,
    )
