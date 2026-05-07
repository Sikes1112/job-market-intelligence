import pytest

from backend.shared.versioning import (
    INITIAL_VERSION,
    next_version,
    parse_version_label,
    version_label,
)


def test_initial_version_is_one() -> None:
    assert INITIAL_VERSION == 1


def test_next_version_increments_deterministically() -> None:
    assert next_version(1) == 2
    assert next_version(2) == 3
    assert next_version(99) == 100


def test_next_version_rejects_zero_and_negative() -> None:
    with pytest.raises(ValueError):
        next_version(0)
    with pytest.raises(ValueError):
        next_version(-3)


def test_next_version_rejects_non_int_types() -> None:
    with pytest.raises(TypeError):
        next_version("1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        next_version(1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        # bool is technically an int subclass; reject it explicitly.
        next_version(True)  # type: ignore[arg-type]


def test_version_label_renders_v_prefix() -> None:
    assert version_label(1) == "v1"
    assert version_label(42) == "v42"


def test_version_label_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        version_label(0)
    with pytest.raises(TypeError):
        version_label("v3")  # type: ignore[arg-type]


def test_parse_version_label_round_trips() -> None:
    for n in (1, 7, 12345):
        assert parse_version_label(version_label(n)) == n


@pytest.mark.parametrize("bad", ["", "1", "version1", "v", "vx", "v-2"])
def test_parse_version_label_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_version_label(bad)
