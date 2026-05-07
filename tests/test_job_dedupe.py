import pytest

from backend.orchestration.jobs.dedupe import dedupe_key, scope_hash
from backend.orchestration.jobs.types import JobType


def test_scope_hash_is_deterministic() -> None:
    a = scope_hash({"region_ids": ["greater_boston"], "k": 1})
    b = scope_hash({"region_ids": ["greater_boston"], "k": 1})
    assert a == b


def test_scope_hash_is_order_independent_for_keys() -> None:
    a = scope_hash({"region_ids": ["greater_boston"], "k": 1})
    b = scope_hash({"k": 1, "region_ids": ["greater_boston"]})
    assert a == b


def test_scope_hash_is_order_sensitive_for_lists() -> None:
    """List ordering is part of the scope; reordering means a different scope."""
    a = scope_hash({"region_ids": ["greater_boston", "greater_sf"]})
    b = scope_hash({"region_ids": ["greater_sf", "greater_boston"]})
    assert a != b


def test_scope_hash_different_inputs_produce_different_hashes() -> None:
    a = scope_hash({"region_ids": ["greater_boston"]})
    b = scope_hash({"region_ids": ["greater_sf"]})
    assert a != b


def test_scope_hash_handles_none_as_empty() -> None:
    assert scope_hash(None) == scope_hash({})  # type: ignore[arg-type]


def test_dedupe_key_basic_format() -> None:
    key = dedupe_key(JobType.REGION_SCORE_RECOMPUTE, {"region_ids": ["greater_boston"]})
    parts = key.split("::")
    assert parts[0] == "region_score_recompute"
    assert len(parts) == 2
    # Second segment must be the scope hash and stable.
    assert parts[1] == scope_hash({"region_ids": ["greater_boston"]})


def test_dedupe_key_with_extra_segments() -> None:
    key = dedupe_key(
        JobType.REGION_SCORE_RECOMPUTE,
        {"region_ids": ["greater_boston"]},
        extra_segments=["greater_boston"],
    )
    parts = key.split("::")
    assert parts == [
        "region_score_recompute",
        "greater_boston",
        scope_hash({"region_ids": ["greater_boston"]}),
    ]


def test_dedupe_key_accepts_string_job_type() -> None:
    a = dedupe_key("hiring_refresh", {"region_ids": ["greater_boston"]})
    b = dedupe_key(JobType.HIRING_REFRESH, {"region_ids": ["greater_boston"]})
    assert a == b


def test_dedupe_key_rejects_unknown_job_type_string() -> None:
    with pytest.raises(ValueError):
        dedupe_key("not_a_job_type", {})


@pytest.mark.parametrize("bad", ["", "a::b", None])
def test_dedupe_key_rejects_bad_extra_segment(bad) -> None:
    with pytest.raises(ValueError):
        dedupe_key(JobType.AUDIT, {}, extra_segments=[bad])


def test_dedupe_key_is_deterministic_for_equal_scopes() -> None:
    a = dedupe_key(JobType.HIRING_REFRESH, {"x": 1, "y": 2})
    b = dedupe_key(JobType.HIRING_REFRESH, {"y": 2, "x": 1})
    assert a == b
