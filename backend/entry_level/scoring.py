"""Entry-level access score — minimal deterministic MVP formula.

This module is **isolated**: it does not import region-scoring modules,
output assembly, personalization, or any other business layer. Slice 10
(region scoring) consumes the score this module emits, but Slice 9 must not
reach into Slice 10.

Design constraints:

* **Internships and co-ops are treated equally** (``MVP_SCOPE.md`` /
  ``DATA_MODEL.md`` §7). They are summed before normalization.
* Counts that arrive as ``None`` are not silently treated as zero. If every
  count is ``None``, the score is ``None`` and the confidence is
  ``unknown``. Partial metadata downgrades the confidence rather than
  fabricating precision.
* The score is bounded ``[0.0, 1.0]`` and deterministic for the same input.

The shape of the formula is intentionally boring. It is *not* the
final scoring engine — it's a stable, audit-friendly placeholder that
Slice 10 can read without surprise.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)

# Saturation cap. A pair with more than ~10 of a kind looks the same as one
# with exactly 10 for MVP scoring purposes. Keeps the formula bounded and
# avoids letting one outlier dominate.
_COUNT_SATURATION = 10

# Component weights (must sum to <= 1.0 before clamping).
_WEIGHT_EARLY_CAREER = 0.5  # internships + co-ops, treated equally
_WEIGHT_FULL_TIME = 0.4
_WEIGHT_FORMAL_PROGRAM_BONUS = 0.1


@dataclass(frozen=True, slots=True)
class EntryLevelScore:
    """Result of :func:`compute_entry_level_access_score`.

    ``score`` is ``None`` when there is not enough information to score
    honestly (every count is ``None``). Otherwise it is bounded
    ``[0.0, 1.0]``.
    """

    score: float | None
    confidence: EntryLevelConfidence


def _saturate(count: int) -> float:
    if count <= 0:
        return 0.0
    return min(count, _COUNT_SATURATION) / _COUNT_SATURATION


def compute_entry_level_access_score(
    *,
    internship_count: int | None,
    coop_count: int | None,
    entry_level_full_time_count: int | None,
    formal_early_career_program_flag: bool,
    student_season_recurrence_signal: StudentSeasonRecurrenceSignal | None,
) -> EntryLevelScore:
    counts = (internship_count, coop_count, entry_level_full_time_count)

    # All-unknown input → no score, no fake precision.
    if all(c is None for c in counts):
        return EntryLevelScore(score=None, confidence=EntryLevelConfidence.UNKNOWN)

    # Treat ``None`` as 0 *only* when at least one count is provided. That
    # zero-substitution is reflected in a downgraded confidence (low) so
    # callers know the score is partial.
    early_career_sum = (internship_count or 0) + (coop_count or 0)
    full_time = entry_level_full_time_count or 0

    early_career_component = _saturate(early_career_sum) * _WEIGHT_EARLY_CAREER
    full_time_component = _saturate(full_time) * _WEIGHT_FULL_TIME
    formal_component = (
        _WEIGHT_FORMAL_PROGRAM_BONUS if formal_early_career_program_flag else 0.0
    )

    score = early_career_component + full_time_component + formal_component
    score = min(max(score, 0.0), 1.0)

    confidence = _classify_confidence(
        counts=counts,
        recurrence=student_season_recurrence_signal,
    )
    return EntryLevelScore(score=score, confidence=confidence)


def _classify_confidence(
    *,
    counts: tuple[int | None, int | None, int | None],
    recurrence: StudentSeasonRecurrenceSignal | None,
) -> EntryLevelConfidence:
    has_unknown_count = any(c is None for c in counts)
    if has_unknown_count:
        # Partial metadata — never claim better than low.
        return EntryLevelConfidence.LOW_CONFIDENCE

    # All counts are explicit; the recurrence signal disambiguates moderate
    # vs high. An ``unknown`` (or omitted) recurrence signal keeps confidence
    # at moderate — we don't have the seasonal pattern.
    if recurrence is None or recurrence is StudentSeasonRecurrenceSignal.UNKNOWN:
        return EntryLevelConfidence.MODERATE_CONFIDENCE
    return EntryLevelConfidence.HIGH_CONFIDENCE
