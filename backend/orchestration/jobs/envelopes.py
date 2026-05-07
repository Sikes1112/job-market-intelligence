"""Job request and response envelopes.

Source: ``JOB_CONTRACT_SPEC.md`` §3.

These models capture the shape of every job's input and output. They do *not*
run jobs, persist anything, or coordinate workers — that arrives in Slice 14.
The cross-field validators below encode the structural rules from
``JOB_CONTRACT_SPEC.md`` §21 (success semantics):

* a ``failed`` response must carry ``error_code`` and ``error_message``;
* a ``succeeded`` response must not carry ``error_code``;
* a ``succeeded_with_warnings`` response must carry at least one warning.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.orchestration.events.recommendations import (
    DownstreamTriggerRecommendation,
)
from backend.orchestration.jobs.errors import ErrorCode, JobWarning
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _ensure_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


class JobRequest(BaseModel):
    """Standard job request envelope."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    job_type: JobType
    trigger_type: TriggerType
    requested_by: str = Field(min_length=1)
    priority: Priority = Priority.NORMAL
    request_time: datetime
    scope: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    # Wire format per docs: list of opaque version-string refs.
    # Use backend.orchestration.dependencies.refs.DependencyRef for richer
    # programmatic descriptions; this list stays as plain strings on the wire.
    dependency_refs: list[str] = Field(default_factory=list)

    @field_validator("request_time")
    @classmethod
    def _request_time_must_be_aware(cls, value: datetime) -> datetime:
        return _ensure_aware(value, label="request_time")

    @field_validator("dependency_refs")
    @classmethod
    def _dependency_refs_nonempty_strings(cls, value: list[str]) -> list[str]:
        for ref in value:
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError("each dependency ref must be a non-empty string")
        return value


class JobResponse(BaseModel):
    """Standard job response envelope."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    job_type: JobType
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[JobWarning] = Field(default_factory=list)
    error_code: ErrorCode | None = None
    error_message: str | None = None
    retry_recommended: bool = False
    downstream_trigger_recommendations: list[DownstreamTriggerRecommendation] = Field(
        default_factory=list
    )

    @field_validator("started_at", "completed_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _ensure_aware(value, label="timestamp")

    @model_validator(mode="after")
    def _check_status_consistency(self) -> JobResponse:
        if self.status is JobStatus.FAILED:
            if self.error_code is None:
                raise ValueError("failed response must include error_code")
            if not self.error_message:
                raise ValueError("failed response must include error_message")
        if self.status is JobStatus.SUCCEEDED and self.error_code is not None:
            raise ValueError("succeeded response must not include error_code")
        if self.status is JobStatus.SUCCEEDED_WITH_WARNINGS and not self.warnings:
            raise ValueError("succeeded_with_warnings response must include at least one warning")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not be earlier than started_at")
        return self
