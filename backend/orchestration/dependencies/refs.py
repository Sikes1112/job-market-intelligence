"""Dependency reference structure.

A :class:`DependencyRef` is a *structural* declaration that one job depends on
a specific versioned upstream object. This module does **not** query the
database or fetch the upstream object; resolution lives in
``backend.orchestration.dependencies.checks``.

The wire format used by ``JobRequest.dependency_refs`` is plain strings (per
the docs: ``["company_universe_v45", "presence_v33"]``). :class:`DependencyRef`
provides an optional richer form for callers that want to describe the ``kind``
of upstream object alongside the ``ref``.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VERSIONED_REF_RE = re.compile(
    r"^(?P<kind>[a-z_]+):(?P<object_id>[^@]+?)(?:@v(?P<version>[1-9][0-9]*))?$"
)


class ParsedDependencyRef(NamedTuple):
    kind: str
    object_id: str
    version: int | None


class DependencyRef(BaseModel):
    """One declared upstream dependency.

    * ``ref`` — required, non-empty. The opaque version string the upstream
      job committed (e.g. ``"presence_v33"``). Slice 4 does not parse this.
    * ``kind`` — optional human-readable category (e.g. ``"presence_map"``,
      ``"region_registry"``). Free-form on purpose.
    * ``required`` — whether the dependent job is blocked if this ref cannot
      be resolved at runtime. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(min_length=1)
    kind: str | None = None
    required: bool = True

    @field_validator("ref")
    @classmethod
    def _ref_no_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dependency ref must not be whitespace")
        return value

    def to_string(self) -> str:
        return self.ref

    @classmethod
    def from_string(cls, ref: str, *, kind: str | None = None) -> DependencyRef:
        return cls(ref=ref, kind=kind)


def make_versioned_dependency_ref(
    kind: str, object_id: str, *, version: int | None = None
) -> str:
    if not kind or not kind.strip() or ":" in kind or "@" in kind:
        raise ValueError("kind must be non-empty and must not contain ':' or '@'")
    if not object_id or not object_id.strip() or "@" in object_id:
        raise ValueError("object_id must be non-empty and must not contain '@'")
    base = f"{kind}:{object_id}"
    if version is None:
        return base
    if version < 1:
        raise ValueError("version must be >= 1")
    return f"{base}@v{version}"


def parse_versioned_dependency_ref(ref: str) -> ParsedDependencyRef | None:
    match = _VERSIONED_REF_RE.match(ref.strip())
    if match is None:
        return None
    raw_version = match.group("version")
    return ParsedDependencyRef(
        kind=match.group("kind"),
        object_id=match.group("object_id"),
        version=int(raw_version) if raw_version is not None else None,
    )
