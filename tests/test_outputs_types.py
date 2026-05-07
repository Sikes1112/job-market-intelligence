from backend.outputs.types import SLICE_11_WRITABLE_TYPES, BuildOutcome, OutputType


def test_output_type_includes_all_five_documented_values() -> None:
    assert OutputType.values() == {
        "region_output",
        "company_output",
        "comparison_output",
        "contextual_challenge_output",
        "personalized_output",
    }


def test_slice_11_writable_types_only_three() -> None:
    assert SLICE_11_WRITABLE_TYPES == {
        "region_output",
        "company_output",
        "comparison_output",
    }


def test_build_outcome_values() -> None:
    assert BuildOutcome.values() == {"fresh", "partial", "stale"}
