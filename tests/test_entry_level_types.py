from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)


def test_student_season_recurrence_values() -> None:
    assert StudentSeasonRecurrenceSignal.values() == {
        "strong",
        "moderate",
        "weak",
        "none",
        "unknown",
    }


def test_entry_level_confidence_values() -> None:
    assert EntryLevelConfidence.values() == {
        "high_confidence",
        "moderate_confidence",
        "low_confidence",
        "unknown",
    }
