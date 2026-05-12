"""Dependency-check primitives used by the queue/worker runtime.

The default resolver remains backward-compatible with opaque dependency
strings. Callers that need production-grade checks can pass
``database_dependency_resolver(session)`` to verify refs of the form
``kind:object_id@vN`` against canonical rows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.orchestration.dependencies.refs import parse_versioned_dependency_ref
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

# A dependency resolver is a callable that takes the job's
# ``dependency_refs`` list and returns the subset that is *unsatisfied*.
# An empty return list means "all dependencies satisfied".
DependencyResolver = Callable[[Iterable[str]], list[str]]


_MODEL_BY_KIND: dict[str, type] = {
    "region": Region,
    "company": Company,
    "presence": CompanyRegionPresence,
    "hiring": CompanyRegionHiring,
    "entry_level": CompanyRegionEntryLevel,
    "region_score": RegionMarketScore,
    "output": OutputMetadata,
    "output_metadata": OutputMetadata,
}


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


def database_dependency_resolver(session: Session) -> DependencyResolver:
    """Return a resolver that verifies version-aware refs against the DB.

    Opaque legacy refs without ``kind:object_id`` structure remain structural.
    Versioned refs require the row to exist, and ``@vN`` requires exact current
    row-version match.
    """

    def _resolver(refs: Iterable[str]) -> list[str]:
        unsatisfied: list[str] = []
        for ref in refs:
            if not isinstance(ref, str) or not ref.strip():
                unsatisfied.append(ref if isinstance(ref, str) else "")
                continue

            parsed = parse_versioned_dependency_ref(ref)
            if parsed is None:
                if ":" in ref or "@v" in ref:
                    unsatisfied.append(ref)
                continue

            model = _MODEL_BY_KIND.get(parsed.kind)
            if model is None:
                unsatisfied.append(ref)
                continue
            row = session.get(model, parsed.object_id)
            if row is None:
                unsatisfied.append(ref)
                continue
            if parsed.version is not None and row.version != parsed.version:
                unsatisfied.append(ref)
        return unsatisfied

    return _resolver
