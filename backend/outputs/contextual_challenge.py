"""Contextual challenge output (Slice 17).

The contextual challenge is a *secondary* derived output that asks: do the
non-primary contextual signals reinforce or challenge the primary winner of
a region comparison?

Hard rules:

* Reads only stored ``RegionMarketScore`` values. Never recomputes scores
  and never reaches into Slice 9/10 formula modules.
* Does **not** modify the primary comparison output's ``category_winners``.
  The contextual challenge is purely additive.
* Writes a single ``OutputMetadata`` row per canonical region pair under
  ``output_type='contextual_challenge_output'``. The subject_id reuses the
  canonical comparison id ``f"{min(a,b)}__{max(a,b)}"``.
* The ``OutputMetadata`` state machine follows the same first-build /
  unchanged-on-rehash pattern as Slice 11.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.outputs.comparison_output import canonical_comparison_id
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingRegionForOutput,
)
from backend.outputs.hashing import artifact_hash as compute_artifact_hash
from backend.outputs.metadata import aggregate_freshness_expires_at
from backend.outputs.models import OutputMetadata
from backend.outputs.payloads import OutputPayloadMetadata
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.types import BuildOutcome, OutputType
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

# The primary score that defines the comparison's "winner". Contextual
# signals are evaluated relative to whoever wins this score.
_PRIMARY_CATEGORY: str = "objective_opportunity_score"

# Non-primary contextual categories whose winners reinforce or challenge the
# primary winner.
_CONTEXTUAL_CATEGORIES: tuple[str, ...] = (
    "early_career_accessibility_score",
    "live_market_score",
    "structural_ecosystem_score",
    "tech_market_density_score",
    "general_density_score",
    "raw_total_score",
)


class ChallengeStatus(StrEnum):
    REINFORCED = "reinforced"
    CHALLENGED = "challenged"
    UNCHANGED = "unchanged"
    INSUFFICIENT_DATA = "insufficient_data"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ChallengeFinding(BaseModel):
    """One per comparable contextual category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    winner_region_id: str | None  # None when both sides tie on this category
    favors_primary: bool | None  # None on tie
    reason_code: str
    region_a_value: float | None = None
    region_b_value: float | None = None


class ContextualChallengeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str
    region_a_id: str
    region_b_id: str
    primary_winner_region_id: str | None
    challenge_status: ChallengeStatus
    reinforced_count: int = 0
    challenged_count: int = 0
    findings: list[ChallengeFinding] = Field(default_factory=list)
    explanation_codes: list[str] = Field(default_factory=list)


class ContextualChallengeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contextual_challenge: ContextualChallengeBody
    metadata: OutputPayloadMetadata


class ContextualChallengeBuildResult(NamedTuple):
    payload: ContextualChallengeOutput
    outcome: BuildOutcome
    source_version_bundle: dict
    freshness_expires_at: datetime | None


def _value(score: RegionMarketScore | None, attr: str) -> float | None:
    if score is None:
        return None
    return getattr(score, attr)


def _winner(
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
    region_a_id: str,
    region_b_id: str,
    attr: str,
) -> tuple[str | None, float | None, float | None] | None:
    """Return (winner_id_or_None_for_tie, value_a, value_b) or None if a side
    lacks the score."""
    v_a = _value(score_a, attr)
    v_b = _value(score_b, attr)
    if v_a is None or v_b is None:
        return None
    if v_a > v_b:
        return region_a_id, v_a, v_b
    if v_b > v_a:
        return region_b_id, v_a, v_b
    return None, v_a, v_b


def _explanation_code(category: str, *, reinforces: bool | None) -> str:
    if reinforces is True:
        return f"primary_winner_reinforced_by_{category}"
    if reinforces is False:
        return f"primary_winner_challenged_by_{category}"
    return f"contextual_tie_on_{category}"


def _source_version_bundle(
    *,
    subject_id: str,
    region_a: Region,
    region_b: Region,
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
) -> dict:
    return {
        "comparison_subject_id": subject_id,
        "challenge_kind": "contextual_challenge_output",
        "region_a": {
            "region_id": region_a.region_id,
            "region_version": region_a.version,
            "region_market_score_version": (
                score_a.version if score_a is not None else None
            ),
            "score_ruleset_version": (
                score_a.score_ruleset_version if score_a is not None else None
            ),
        },
        "region_b": {
            "region_id": region_b.region_id,
            "region_version": region_b.version,
            "region_market_score_version": (
                score_b.version if score_b is not None else None
            ),
            "score_ruleset_version": (
                score_b.score_ruleset_version if score_b is not None else None
            ),
        },
    }


def build_contextual_challenge(
    *,
    region_a: Region,
    region_b: Region,
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
    now: datetime | None = None,
) -> ContextualChallengeBuildResult:
    """Pure builder: no DB access, no service imports."""
    if now is None:
        now = datetime.now(UTC)
    if region_a.region_id == region_b.region_id:
        raise InvalidComparisonInput(
            f"contextual challenge requires two distinct regions; got "
            f"{region_a.region_id!r} twice"
        )

    # Canonicalize sides so the contextual_challenge.region_a / region_b
    # always reflect the canonical pair ordering.
    if region_a.region_id > region_b.region_id:
        region_a, region_b = region_b, region_a
        score_a, score_b = score_b, score_a

    subject_id = canonical_comparison_id(region_a.region_id, region_b.region_id)

    # Insufficient-data short circuit: either side is missing entirely, or
    # the primary score is missing on either side.
    primary_value_a = _value(score_a, _PRIMARY_CATEGORY)
    primary_value_b = _value(score_b, _PRIMARY_CATEGORY)
    if (
        score_a is None
        or score_b is None
        or primary_value_a is None
        or primary_value_b is None
    ):
        body = ContextualChallengeBody(
            comparison_id=subject_id,
            region_a_id=region_a.region_id,
            region_b_id=region_b.region_id,
            primary_winner_region_id=None,
            challenge_status=ChallengeStatus.INSUFFICIENT_DATA,
            reinforced_count=0,
            challenged_count=0,
            findings=[],
            explanation_codes=["insufficient_score_data"],
        )
        outcome = BuildOutcome.PARTIAL
        bundle = _source_version_bundle(
            subject_id=subject_id,
            region_a=region_a,
            region_b=region_b,
            score_a=score_a,
            score_b=score_b,
        )
        payload = ContextualChallengeOutput(
            contextual_challenge=body,
            metadata=OutputPayloadMetadata(
                state=outcome.value,
                freshness_expires_at=None,
                source_versions=bundle,
                warnings=[],
            ),
        )
        return ContextualChallengeBuildResult(
            payload=payload,
            outcome=outcome,
            source_version_bundle=bundle,
            freshness_expires_at=None,
        )

    # Determine primary winner (we know neither primary value is None now).
    if primary_value_a > primary_value_b:
        primary_winner = region_a.region_id
    elif primary_value_b > primary_value_a:
        primary_winner = region_b.region_id
    else:
        primary_winner = None

    findings: list[ChallengeFinding] = []
    explanation_codes: list[str] = []
    reinforced = 0
    challenged = 0

    for category in _CONTEXTUAL_CATEGORIES:
        result = _winner(
            score_a, score_b, region_a.region_id, region_b.region_id, category
        )
        if result is None:
            continue
        winner_id, v_a, v_b = result
        if primary_winner is None or winner_id is None:
            favors_primary: bool | None = None
        else:
            favors_primary = winner_id == primary_winner

        if favors_primary is True:
            reinforced += 1
        elif favors_primary is False:
            challenged += 1

        reason_code = _explanation_code(category, reinforces=favors_primary)
        explanation_codes.append(reason_code)
        findings.append(
            ChallengeFinding(
                category=category,
                winner_region_id=winner_id,
                favors_primary=favors_primary,
                reason_code=reason_code,
                region_a_value=v_a,
                region_b_value=v_b,
            )
        )

    if primary_winner is None:
        # Primary scores tie — no challenge framing is meaningful.
        status = ChallengeStatus.UNCHANGED
        explanation_codes = ["no_clear_primary_winner"]
    elif reinforced == 0 and challenged == 0:
        status = ChallengeStatus.UNCHANGED
        explanation_codes.append("no_clear_contextual_difference")
    elif reinforced > challenged:
        status = ChallengeStatus.REINFORCED
    elif challenged > reinforced:
        status = ChallengeStatus.CHALLENGED
    else:
        status = ChallengeStatus.UNCHANGED
        explanation_codes.append("no_clear_contextual_difference")

    body = ContextualChallengeBody(
        comparison_id=subject_id,
        region_a_id=region_a.region_id,
        region_b_id=region_b.region_id,
        primary_winner_region_id=primary_winner,
        challenge_status=status,
        reinforced_count=reinforced,
        challenged_count=challenged,
        findings=findings,
        explanation_codes=explanation_codes,
    )

    freshness_expires_at = aggregate_freshness_expires_at()
    outcome = BuildOutcome.FRESH

    bundle = _source_version_bundle(
        subject_id=subject_id,
        region_a=region_a,
        region_b=region_b,
        score_a=score_a,
        score_b=score_b,
    )
    payload = ContextualChallengeOutput(
        contextual_challenge=body,
        metadata=OutputPayloadMetadata(
            state=outcome.value,
            freshness_expires_at=freshness_expires_at,
            source_versions=bundle,
            warnings=[],
        ),
    )
    return ContextualChallengeBuildResult(
        payload=payload,
        outcome=outcome,
        source_version_bundle=bundle,
        freshness_expires_at=freshness_expires_at,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ContextualChallengeAssemblyResult(NamedTuple):
    metadata: OutputMetadata
    payload: ContextualChallengeOutput
    action: str  # "created" | "updated" | "unchanged"


class ContextualChallengeService:
    """Builds + persists contextual challenge OutputMetadata rows.

    Keeps the same upsert + state-machine discipline as
    :class:`backend.outputs.service.OutputAssemblyService`, but stays
    deliberately separate so Slice 11's writable-types contract
    (``SLICE_11_WRITABLE_TYPES``) remains intact.
    """

    def __init__(
        self,
        output_repo: OutputMetadataRepository,
        *,
        session: Session,
        region_repo: RegionRepository,
        score_repo: RegionScoreRepository,
    ) -> None:
        self._output_repo = output_repo
        self._session = session
        self._region_repo = region_repo
        self._score_repo = score_repo

    def build(
        self,
        region_a_id: str,
        region_b_id: str,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> ContextualChallengeAssemblyResult:
        if not isinstance(region_a_id, str) or not isinstance(region_b_id, str):
            raise InvalidComparisonInput("region IDs must be strings")
        if not region_a_id.strip() or not region_b_id.strip():
            raise InvalidComparisonInput("region IDs must be non-empty")
        if region_a_id == region_b_id:
            raise InvalidComparisonInput(
                f"contextual challenge requires two distinct regions; got "
                f"{region_a_id!r} twice"
            )

        canonical_a, canonical_b = sorted((region_a_id, region_b_id))
        region_a = self._region_repo.get(canonical_a)
        region_b = self._region_repo.get(canonical_b)
        if region_a is None:
            raise MissingRegionForOutput(canonical_a)
        if region_b is None:
            raise MissingRegionForOutput(canonical_b)

        score_a = self._score_repo.get_score_by_region(canonical_a)
        score_b = self._score_repo.get_score_by_region(canonical_b)

        now_fn = now or _default_now
        result = build_contextual_challenge(
            region_a=region_a,
            region_b=region_b,
            score_a=score_a,
            score_b=score_b,
            now=now_fn(),
        )
        subject_id = canonical_comparison_id(canonical_a, canonical_b)
        row, action = self._upsert_metadata(
            subject_id=subject_id,
            payload=result.payload,
            outcome=result.outcome,
            source_version_bundle=result.source_version_bundle,
            freshness_expires_at=result.freshness_expires_at,
        )
        return ContextualChallengeAssemblyResult(
            metadata=row, payload=result.payload, action=action
        )

    def _upsert_metadata(
        self,
        *,
        subject_id: str,
        payload: ContextualChallengeOutput,
        outcome: BuildOutcome,
        source_version_bundle: dict,
        freshness_expires_at: datetime | None,
    ) -> tuple[OutputMetadata, str]:
        ah = compute_artifact_hash(payload.model_dump(mode="json"))
        output_type = OutputType.CONTEXTUAL_CHALLENGE_OUTPUT.value

        existing = self._output_repo.get_by_type_and_subject(output_type, subject_id)
        if existing is not None and existing.artifact_hash == ah:
            return existing, "unchanged"

        if existing is None:
            row = OutputMetadata(
                output_id=f"out_contextual_{subject_id}",
                output_type=output_type,
                subject_id=subject_id,
                artifact_uri=None,
                artifact_hash=ah,
                source_version_bundle=source_version_bundle,
                freshness_expires_at=freshness_expires_at,
            )
            self._output_repo.add(row)
            self._output_repo.flush()
            self._walk_first_build_state(row, outcome)
            self._output_repo.flush()
            return row, "created"

        existing.artifact_hash = ah
        existing.source_version_bundle = source_version_bundle
        existing.freshness_expires_at = freshness_expires_at
        existing.version = next_version(existing.version)
        self._walk_changed_rebuild_state(existing, outcome)
        self._output_repo.flush()
        return existing, "updated"

    def _walk_first_build_state(
        self, row: OutputMetadata, outcome: BuildOutcome
    ) -> None:
        self._set_state(row, ObjectState.BUILDING)
        if outcome is BuildOutcome.PARTIAL:
            self._set_state(row, ObjectState.PARTIAL)
        else:
            self._set_state(row, ObjectState.FRESH)
            if outcome is BuildOutcome.STALE:
                self._set_state(row, ObjectState.STALE)

    def _walk_changed_rebuild_state(
        self, row: OutputMetadata, outcome: BuildOutcome
    ) -> None:
        if row.state == ObjectState.NEW.value:
            self._walk_first_build_state(row, outcome)
            return
        if row.state == ObjectState.BUILDING.value:
            if outcome is BuildOutcome.PARTIAL:
                self._set_state(row, ObjectState.PARTIAL)
            else:
                self._set_state(row, ObjectState.FRESH)
                if outcome is BuildOutcome.STALE:
                    self._set_state(row, ObjectState.STALE)

    def _set_state(self, row: OutputMetadata, target: ObjectState) -> None:
        validate_transition(row.state, target)
        row.state = target.value


def _default_now() -> datetime:
    return datetime.now(UTC)
