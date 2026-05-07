"""Comparison output builder + canonical_comparison_id helper.

Comparison is a *feature*, not a recomputation. Slice 11 reads stored
``RegionMarketScore`` values for each side and computes ``category_winners``
by direct numeric comparison only. No new score components are produced;
ties are reported as ``None``; categories where one or both sides lack a
score are omitted entirely.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import NamedTuple

from backend.geography.models import Region
from backend.orchestration.jobs.errors import JobWarning, WarningSeverity
from backend.outputs.exceptions import InvalidComparisonInput
from backend.outputs.metadata import (
    aggregate_freshness_expires_at,
    comparison_source_version_bundle,
)
from backend.outputs.payloads import (
    ComparisonOutput,
    ComparisonOutputBody,
    ComparisonRegionSide,
    OutputPayloadMetadata,
    RegionScoresPayload,
)
from backend.outputs.types import BuildOutcome
from backend.scoring.models import RegionMarketScore

# Documented score categories drawn from RegionMarketScore. Comparison
# winners are computed only for these fields.
_COMPARISON_CATEGORIES: tuple[str, ...] = (
    "structural_ecosystem_score",
    "live_market_score",
    "objective_opportunity_score",
    "raw_total_score",
    "general_density_score",
    "tech_market_density_score",
    "early_career_accessibility_score",
)


def canonical_comparison_id(a: str, b: str) -> str:
    """Return the canonical, order-independent subject_id for the pair.

    Rejects blank IDs and identical IDs. The format is
    ``f"{min(a,b)}__{max(a,b)}"`` so ``(boston, sf)`` and ``(sf, boston)``
    map to the same string.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        raise InvalidComparisonInput("region IDs must be strings")
    a = a.strip()
    b = b.strip()
    if not a or not b:
        raise InvalidComparisonInput("region IDs must be non-empty")
    if a == b:
        raise InvalidComparisonInput(
            f"comparison requires two distinct regions; got {a!r} twice"
        )
    return f"{min(a, b)}__{max(a, b)}"


class ComparisonBuildResult(NamedTuple):
    payload: ComparisonOutput
    outcome: BuildOutcome
    source_version_bundle: dict
    freshness_expires_at: datetime | None
    warnings: tuple[JobWarning, ...]


def _scores_payload(score: RegionMarketScore | None) -> RegionScoresPayload | None:
    if score is None:
        return None
    return RegionScoresPayload(
        structural_ecosystem_score=score.structural_ecosystem_score,
        live_market_score=score.live_market_score,
        objective_opportunity_score=score.objective_opportunity_score,
        raw_total_score=score.raw_total_score,
        general_density_score=score.general_density_score,
        tech_market_density_score=score.tech_market_density_score,
        early_career_accessibility_score=score.early_career_accessibility_score,
        score_ruleset_version=score.score_ruleset_version,
    )


def _category_winners(
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
    region_a_id: str,
    region_b_id: str,
) -> dict[str, str | None]:
    if score_a is None or score_b is None:
        return {}
    winners: dict[str, str | None] = {}
    for category in _COMPARISON_CATEGORIES:
        v_a = getattr(score_a, category)
        v_b = getattr(score_b, category)
        if v_a is None or v_b is None:
            continue
        if v_a > v_b:
            winners[category] = region_a_id
        elif v_b > v_a:
            winners[category] = region_b_id
        else:
            winners[category] = None  # honest tie
    return winners


def build_comparison_output(
    *,
    region_a: Region,
    region_b: Region,
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
    extra_freshness_inputs: Iterable[datetime | None] = (),
    now: datetime | None = None,
) -> ComparisonBuildResult:
    if now is None:
        now = datetime.now(UTC)

    if region_a.region_id == region_b.region_id:
        raise InvalidComparisonInput(
            f"comparison requires two distinct regions; got "
            f"{region_a.region_id!r} twice"
        )

    subject_id = canonical_comparison_id(region_a.region_id, region_b.region_id)
    warnings: list[JobWarning] = []

    if score_a is None:
        warnings.append(
            JobWarning(
                warning_code="region_score_missing",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region_a.region_id,
                message=f"no region_market_scores row for {region_a.region_id!r}",
            )
        )
    if score_b is None:
        warnings.append(
            JobWarning(
                warning_code="region_score_missing",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region_b.region_id,
                message=f"no region_market_scores row for {region_b.region_id!r}",
            )
        )

    body = ComparisonOutputBody(
        comparison_id=subject_id,
        region_a=ComparisonRegionSide(
            region_id=region_a.region_id,
            display_name=region_a.display_name,
            scores=_scores_payload(score_a),
        ),
        region_b=ComparisonRegionSide(
            region_id=region_b.region_id,
            display_name=region_b.display_name,
            scores=_scores_payload(score_b),
        ),
        category_winners=_category_winners(
            score_a, score_b, region_a.region_id, region_b.region_id
        ),
        notes=[],
    )

    freshness_expires_at = aggregate_freshness_expires_at(*extra_freshness_inputs)
    is_stale = freshness_expires_at is not None and freshness_expires_at <= now
    if is_stale:
        warnings.append(
            JobWarning(
                warning_code="stale_input_rows",
                severity=WarningSeverity.MEDIUM,
                scope_type="comparison",
                scope_ref=subject_id,
                message=(
                    f"comparison {subject_id!r} draws on inputs whose "
                    "freshness windows have expired"
                ),
            )
        )

    is_partial = score_a is None or score_b is None

    if is_stale:
        outcome = BuildOutcome.STALE
    elif is_partial:
        outcome = BuildOutcome.PARTIAL
    else:
        outcome = BuildOutcome.FRESH

    source_versions = comparison_source_version_bundle(
        comparison_subject_id=subject_id,
        region_a=region_a,
        region_b=region_b,
        score_a=score_a,
        score_b=score_b,
    )

    payload = ComparisonOutput(
        comparison=body,
        metadata=OutputPayloadMetadata(
            state=outcome.value,
            freshness_expires_at=freshness_expires_at,
            source_versions=source_versions,
            warnings=list(warnings),
        ),
    )
    return ComparisonBuildResult(
        payload=payload,
        outcome=outcome,
        source_version_bundle=source_versions,
        freshness_expires_at=freshness_expires_at,
        warnings=tuple(warnings),
    )
