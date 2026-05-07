"""Pydantic payload models for audit findings and reports.

In-memory only: ``DATA_MODEL.md`` §12 lists ``audit_reports`` as optional
and Slice 2 deferred the table. Slice 16 returns an :class:`AuditReport` in
``JobResponse.outputs`` and via the service's return value; nothing is
persisted to a new table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit.types import (
    AuditCategory,
    AuditOverallStatus,
    AuditSeverity,
)


class AuditFinding(BaseModel):
    """One structured integrity finding.

    ``finding_id`` is deterministic per (category, scope_ref, sub_kind) so
    re-running the audit on the same data produces stable IDs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    severity: AuditSeverity
    category: AuditCategory
    scope_type: str = Field(min_length=1)
    scope_ref: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    recommendation: str | None = None

    @field_validator("finding_id", "scope_type", "scope_ref", "message")
    @classmethod
    def _no_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be whitespace")
        return value


class AuditScope(BaseModel):
    """Optional scope payload accepted by the audit job handler.

    For MVP the audit always inspects the full data set; the optional
    region/company filters are accepted for forward compatibility but are
    advisory — the service can choose to honor them or run a full audit.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_ids: list[str] = Field(default_factory=list)
    company_ids: list[str] = Field(default_factory=list)
    audit_mode: str | None = None

    @field_validator("region_ids", "company_ids")
    @classmethod
    def _entries_non_empty(cls, value: list[str]) -> list[str]:
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("entries must be non-empty strings")
        return value


class AuditReport(BaseModel):
    """The deliverable of one audit run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1)
    generated_at: datetime
    overall_status: AuditOverallStatus
    findings: list[AuditFinding] = Field(default_factory=list)
    summary_by_severity: dict[str, int] = Field(default_factory=dict)
    summary_by_category: dict[str, int] = Field(default_factory=dict)
    scopes_checked: dict[str, Any] = Field(default_factory=dict)

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


def summarize_findings(
    findings: list[AuditFinding],
) -> tuple[dict[str, int], dict[str, int]]:
    """Return ``(by_severity, by_category)`` counts for the findings list.

    Both dicts include zero entries for every documented enum value so the
    summary is stable across runs even when no findings of a given kind
    appear.
    """
    by_severity = {sev.value: 0 for sev in AuditSeverity}
    by_category = {cat.value: 0 for cat in AuditCategory}
    for finding in findings:
        by_severity[finding.severity.value] += 1
        by_category[finding.category.value] += 1
    return by_severity, by_category
