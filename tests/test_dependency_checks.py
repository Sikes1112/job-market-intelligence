from backend.orchestration.dependencies.checks import (
    check_dependencies,
    default_dependency_resolver,
)


def test_empty_refs_satisfied() -> None:
    assert check_dependencies([]) == []


def test_well_formed_refs_satisfied() -> None:
    assert check_dependencies(["presence_v33", "hiring_v71"]) == []


def test_blank_string_unsatisfied() -> None:
    missing = check_dependencies(["presence_v33", "  "])
    assert missing == ["  "]


def test_empty_string_unsatisfied() -> None:
    assert check_dependencies(["", "valid"]) == [""]


def test_non_string_treated_as_unsatisfied() -> None:
    # Defensive — runtime should not pass non-strings, but if it does
    # the resolver must report it.
    missing = check_dependencies([None, 42, "valid"])  # type: ignore[list-item]
    assert len(missing) == 2


def test_default_resolver_is_pure() -> None:
    """The resolver must be a pure function (no DB, no service calls)."""
    a = default_dependency_resolver(["x", "y"])
    b = default_dependency_resolver(["x", "y"])
    assert a == b == []


def test_custom_resolver_can_be_injected() -> None:
    """Future slices may pass a richer resolver; the contract is just
    callable[Iterable[str], list[str]]."""

    def strict_resolver(refs):
        # Treat anything not starting with "v" as unsatisfied.
        return [r for r in refs if not r.startswith("v")]

    assert check_dependencies(["v1", "x"], resolver=strict_resolver) == ["x"]
