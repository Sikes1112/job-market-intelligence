"""Dependency-check primitives used by the queue/worker runtime.

Slice 14 implements *structural* checking only — a real version registry
is Slice 15+ territory. The default resolver simply ensures every
``dependency_ref`` is a non-empty, non-whitespace string. Future slices
can pass a richer resolver (e.g. one that consults stored
``source_version_bundle`` records) without changing this signature.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

# A dependency resolver is a callable that takes the job's
# ``dependency_refs`` list and returns the subset that is *unsatisfied*.
# An empty return list means "all dependencies satisfied".
DependencyResolver = Callable[[Iterable[str]], list[str]]


def default_dependency_resolver(refs: Iterable[str]) -> list[str]:
    """Structural check: a ref is satisfied iff it is a non-empty string."""
    unsatisfied: list[str] = []
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            unsatisfied.append(ref if isinstance(ref, str) else "")
    return unsatisfied


def check_dependencies(
    refs: Iterable[str], *, resolver: DependencyResolver | None = None
) -> list[str]:
    """Return the list of unsatisfied dependency refs."""
    return (resolver or default_dependency_resolver)(refs)
