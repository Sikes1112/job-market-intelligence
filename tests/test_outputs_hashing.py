from backend.outputs.hashing import artifact_hash, canonical_json


def test_canonical_json_sorts_keys() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b


def test_canonical_json_separators_are_compact() -> None:
    s = canonical_json({"a": 1, "b": 2})
    assert " " not in s
    assert s == '{"a":1,"b":2}'


def test_canonical_json_handles_nested_dicts_and_lists() -> None:
    payload = {"x": [3, 1, 2], "y": {"b": True, "a": None}}
    a = canonical_json(payload)
    b = canonical_json({"y": {"a": None, "b": True}, "x": [3, 1, 2]})
    assert a == b


def test_canonical_json_list_order_is_preserved() -> None:
    """Lists are semantically ordered (top-N is the obvious case)."""
    a = canonical_json([1, 2, 3])
    b = canonical_json([3, 2, 1])
    assert a != b


def test_artifact_hash_is_deterministic() -> None:
    payload = {"a": 1, "b": [1, 2, 3]}
    assert artifact_hash(payload) == artifact_hash(payload)


def test_artifact_hash_is_key_order_independent() -> None:
    a = artifact_hash({"x": 1, "y": 2})
    b = artifact_hash({"y": 2, "x": 1})
    assert a == b


def test_artifact_hash_differs_for_different_payloads() -> None:
    assert artifact_hash({"a": 1}) != artifact_hash({"a": 2})


def test_artifact_hash_handles_datetimes_via_default_str() -> None:
    from datetime import UTC, datetime

    payload = {"ts": datetime(2026, 5, 7, tzinfo=UTC)}
    h = artifact_hash(payload)
    assert isinstance(h, str)
    assert len(h) == 64  # sha256 hex
