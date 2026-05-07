from backend.hiring.role_families import (
    DOCUMENTED_ROLE_FAMILIES,
    validate_role_family_summary,
)
from backend.hiring.time_windows import TimeWindow
from backend.hiring.types import (
    AnnualizedTrendSignal,
    HiringConfidence,
    SeasonalStudentHiringSignal,
)


def test_annualized_trend_signal_values() -> None:
    assert AnnualizedTrendSignal.values() == {
        "positive",
        "neutral",
        "negative",
        "unknown",
    }


def test_seasonal_student_hiring_signal_values() -> None:
    assert SeasonalStudentHiringSignal.values() == {
        "strong",
        "moderate",
        "weak",
        "none",
        "unknown",
    }


def test_hiring_confidence_values() -> None:
    assert HiringConfidence.values() == {
        "high_confidence",
        "moderate_confidence",
        "low_confidence",
        "unknown",
    }


def test_time_window_values() -> None:
    assert TimeWindow.values() == {"now", "30d", "90d"}


def test_documented_role_families_match_mvp_scope() -> None:
    assert DOCUMENTED_ROLE_FAMILIES == {
        "product",
        "ai_cloud_adjacent",
        "cybersecurity",
    }


def test_validate_role_family_summary_accepts_none() -> None:
    validate_role_family_summary(None)  # no raise


def test_validate_role_family_summary_accepts_empty() -> None:
    validate_role_family_summary({})


def test_validate_role_family_summary_accepts_documented_keys() -> None:
    validate_role_family_summary({"product": 3, "ai_cloud_adjacent": 5})


def test_validate_role_family_summary_rejects_negative() -> None:
    import pytest

    with pytest.raises(ValueError):
        validate_role_family_summary({"product": -1})


def test_validate_role_family_summary_rejects_blank_key() -> None:
    import pytest

    with pytest.raises(ValueError):
        validate_role_family_summary({" ": 1})


def test_validate_role_family_summary_rejects_non_int_count() -> None:
    import pytest

    with pytest.raises(ValueError):
        validate_role_family_summary({"product": "many"})


def test_validate_role_family_summary_rejects_bool() -> None:
    import pytest

    with pytest.raises(ValueError):
        validate_role_family_summary({"product": True})


def test_validate_role_family_summary_rejects_non_dict() -> None:
    import pytest

    with pytest.raises(ValueError):
        validate_role_family_summary([("product", 3)])  # type: ignore[arg-type]
