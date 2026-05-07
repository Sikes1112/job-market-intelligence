"""Dependency reference structure.

A :class:`DependencyRef` is a *structural* declaration that one job depends on
a specific versioned upstream object. This module does **not** resolve the
reference, query the database, or fetch the upstream object — those concerns
belong to later orchestration slices.

The wire format used by ``JobRequest.dependency_refs`` is plain strings (per
the docs: ``["company_universe_v45", "presence_v33"]``). :class:`DependencyRef`
provides an optional richer form for callers that want to describe the ``kind``
of upstream object alongside the ``ref``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
