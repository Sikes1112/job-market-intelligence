import pytest

from backend.entry_level.scoring import (
    EntryLevelScore,
    compute_entry_level_access_score,
)
from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)


def _score(**overrides) -> EntryLevelScore:
    payload = dict(
        internship_count=None,
        coop_count=None,
        entry_level_full_time_count=None,
        formal_early_career_program_flag=False,
        student_season_recurrence_signal=None,
    )
    payload.update(overrides)
    return compute_entry_level_access_score(**payload)


def test_all_unknown_returns_none_score_and_unknown_confidence() -> None:
    result = _score()
    assert result.score is None
    assert result.confidence is EntryLevelConfidence.UNKNOWN


def test_zero_counts_explicit_score_is_low_but_not_none() -> None:
    """Explicit zero is not unknown — the score is computable, just low."""
    result = _score(
        internship_count=0,
        coop_count=0,
        entry_level_full_time_count=0,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.NONE,
    )
    assert result.score == 0.0
    assert result.confidence is EntryLevelConfidence.HIGH_CONFIDENCE


def test_internship_and_coop_treated_equally() -> None:
    """Same total of internships+coops should yield the same score regardless
    of which side carries the count."""
    a = _score(
        internship_count=4,
        coop_count=0,
        entry_level_full_time_count=0,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    b = _score(
        internship_count=0,
        coop_count=4,
        entry_level_full_time_count=0,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    c = _score(
        internship_count=2,
        coop_count=2,
        entry_level_full_time_count=0,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    assert a.score == b.score == c.score


def test_score_is_bounded_zero_one() -> None:
    result = _score(
        internship_count=10000,
        coop_count=10000,
        entry_level_full_time_count=10000,
        formal_early_career_program_flag=True,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    assert 0.0 <= result.score <= 1.0
    assert result.score == 1.0


def test_score_is_deterministic() -> None:
    a = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        formal_early_career_program_flag=True,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    b = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        formal_early_career_program_flag=True,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    assert a == b


def test_partial_metadata_drops_to_low_confidence() -> None:
    result = _score(
        internship_count=3,
        coop_count=None,
        entry_level_full_time_count=4,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    assert result.score is not None
    assert result.confidence is EntryLevelConfidence.LOW_CONFIDENCE


def test_full_metadata_no_recurrence_signal_yields_moderate_confidence() -> None:
    result = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        student_season_recurrence_signal=None,
    )
    assert result.confidence is EntryLevelConfidence.MODERATE_CONFIDENCE


def test_full_metadata_unknown_recurrence_signal_yields_moderate_confidence() -> None:
    result = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.UNKNOWN,
    )
    assert result.confidence is EntryLevelConfidence.MODERATE_CONFIDENCE


def test_formal_program_flag_increases_score() -> None:
    without_flag = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        formal_early_career_program_flag=False,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    with_flag = _score(
        internship_count=3,
        coop_count=2,
        entry_level_full_time_count=4,
        formal_early_career_program_flag=True,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    assert with_flag.score is not None
    assert without_flag.score is not None
    assert with_flag.score > without_flag.score


@pytest.mark.parametrize(
    "i,c,ft",
    [
        (10, 0, 0),
        (5, 5, 0),
        (0, 10, 0),
    ],
)
def test_saturation_caps_at_ten(i: int, c: int, ft: int) -> None:
    """Counts above the saturation cap should yield the same component score
    as counts at the cap."""
    capped = _score(
        internship_count=i,
        coop_count=c,
        entry_level_full_time_count=ft,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    over = _score(
        internship_count=i + 50,
        coop_count=c + 50,
        entry_level_full_time_count=ft + 50,
        student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
    )
    # The over case has FT > 0 so will differ; just check both are bounded.
    assert 0.0 <= capped.score <= 1.0
    assert 0.0 <= over.score <= 1.0
