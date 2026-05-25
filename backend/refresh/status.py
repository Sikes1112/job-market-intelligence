"""Refresh status and observability contract models."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.refresh.job_types import RefreshJobType


class RefreshJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def successful(cls) -> frozenset[RefreshJobStatus]:
        return frozenset({cls.SUCCEEDED, cls.SUCCEEDED_WITH_WARNINGS})


class RefreshJobStatusRecord(BaseModel):
    """Observable status fields for a refresh job.

    This model is storage-neutral. A future worker can persist equivalent fields
    in SQL, Redis metadata, or an observability sink without changing the
    contract.
    """

    model_config = ConfigDict(extra="forbid")

    stable_job_key: str = Field(min_length=1)
    job_id: str | None = Field(default=None, min_length=1)
    job_type: RefreshJobType
    target_scope: dict[str, Any] = Field(default_factory=dict)
    target_id: str | None = Field(default=None, min_length=1)
    status: RefreshJobStatus
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    failure_reason: str | None = Field(default=None, min_length=1)
    retry_count: int = Field(default=0, ge=0)
    source_version_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_version_bundle_ref: str | None = Field(default=None, min_length=1)
    stale_output_count: int | None = Field(default=None, ge=0)

    @field_validator("enqueued_at", "started_at", "finished_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("refresh job timestamps must be timezone-aware")
        return value

    @field_validator("source_version_refs")
    @classmethod
    def _source_version_refs_must_be_nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for ref in value:
            if not ref.strip():
                raise ValueError("source version refs must be non-empty strings")
        return value

    @model_validator(mode="after")
    def _validate_status_observability(self) -> RefreshJobStatusRecord:
        if self.started_at is not None and self.started_at < self.enqueued_at:
            raise ValueError("started_at must not be earlier than enqueued_at")
        if self.finished_at is not None:
            if self.started_at is None:
                raise ValueError("finished_at requires started_at")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must not be earlier than started_at")
        if self.status is RefreshJobStatus.FAILED and not self.failure_reason:
            raise ValueError("failed refresh status must include failure_reason")
        if (
            self.duration_seconds is None
            and self.started_at is not None
            and self.finished_at is not None
        ):
            self.duration_seconds = (self.finished_at - self.started_at).total_seconds()
        return self


class RefreshObservabilitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_type: RefreshJobType | None = None
    target_scope: dict[str, Any] = Field(default_factory=dict)
    target_id: str | None = None
    last_successful_run_at: datetime | None = None
    last_successful_job_key: str | None = None
    stale_output_count: int = Field(default=0, ge=0)


def summarize_refresh_observability(
    records: Iterable[RefreshJobStatusRecord],
    *,
    stale_output_count: int = 0,
    job_type: RefreshJobType | None = None,
    target_scope: dict[str, Any] | None = None,
    target_id: str | None = None,
) -> RefreshObservabilitySummary:
    """Return last-success and stale-output summary fields for dashboards/API."""

    successful = [
        record
        for record in records
        if record.status in RefreshJobStatus.successful() and record.finished_at is not None
    ]
    latest = max(successful, key=lambda record: record.finished_at, default=None)
    return RefreshObservabilitySummary(
        job_type=job_type,
        target_scope=target_scope or {},
        target_id=target_id,
        last_successful_run_at=latest.finished_at if latest else None,
        last_successful_job_key=latest.stable_job_key if latest else None,
        stale_output_count=stale_output_count,
    )


__all__ = [
    "RefreshJobStatus",
    "RefreshJobStatusRecord",
    "RefreshObservabilitySummary",
    "summarize_refresh_observability",
]
