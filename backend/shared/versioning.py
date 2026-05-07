"""Version metadata helpers.

Versions are monotonically increasing positive integers stored on canonical
objects (see ``CanonicalMixin.version``). The string form ``v{n}`` is a
presentation convention used in docs and downstream payloads; it is not the
storage type.

These helpers are deliberately small. They do not implement audit history,
repair logic, or dependency-version resolution — those live in later slices
(orchestration / audit).
"""

from __future__ import annotations

INITIAL_VERSION: int = 1


def _validate_version_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"version must be an int, got {type(value).__name__}")
    if value < INITIAL_VERSION:
        raise ValueError(f"version must be >= {INITIAL_VERSION}, got {value}")
    return value


def next_version(current: int) -> int:
    """Return ``current + 1`` after validating ``current`` is a positive int."""
    return _validate_version_int(current) + 1


def version_label(version: int) -> str:
    """Render an integer version as the canonical ``v{n}`` label."""
    return f"v{_validate_version_int(version)}"


def parse_version_label(label: str) -> int:
    """Parse a ``v{n}`` label back to its integer form. Strict on format."""
    if not isinstance(label, str):
        raise TypeError(f"version label must be a str, got {type(label).__name__}")
    if not label.startswith("v") or len(label) < 2:
        raise ValueError(f"invalid version label: {label!r}")
    try:
        n = int(label[1:])
    except ValueError as e:
        raise ValueError(f"invalid version label: {label!r}") from e
    return _validate_version_int(n)
