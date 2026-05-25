"""Refresh queue request/result abstractions.

The production posture is RQ + Redis, but these contracts deliberately avoid
importing broker clients. Tests and local batch checks can use the in-memory
adapter in :mod:`backend.refresh.adapters`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.refresh.job_types import RefreshJobType
from backend.refresh.status import RefreshJobStatus, RefreshJobStatusRecord

RefreshEnqueueOutcome = Literal["enqueued", "already_active"]

ACTIVE_REFRESH_STATUSES = frozenset(
    {RefreshJobStatus.QUEUED, RefreshJobStatus.RUNNING}
)


class RefreshJobRequest(BaseModel):
    """Storage-neutral refresh job request.

    ``stable_job_key`` is the dedupe/admission key. It is intentionally not a
    broker-specific id; adapters may map it to an RQ job id, Redis metadata key,
    SQL key, or another stable identifier.
    """

    model_config = ConfigDict(extra="forbid")

    stable_job_key: str = Field(min_length=1)
    job_type: RefreshJobType
    target_scope: dict[str, Any] = Field(default_factory=dict)
    target_id: str | None = Field(default=None, min_length=1)
    requested_by: str = Field(default="system", min_length=1)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    source_version_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_version_bundle_ref: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_version_refs")
    @classmethod
    def _source_version_refs_must_be_nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for ref in value:
            if not ref.strip():
                raise ValueError("source version refs must be non-empty strings")
        return value


@dataclass(frozen=True)
class RefreshEnqueueResult:
    request: RefreshJobRequest
    status_record: RefreshJobStatusRecord
    outcome: RefreshEnqueueOutcome


@dataclass(frozen=True)
class ClaimedRefreshJob:
    request: RefreshJobRequest
    status_record: RefreshJobStatusRecord


class RefreshQueueAdapter(Protocol):
    """Queue adapter contract used by scheduler and worker processes."""

    def enqueue(self, request: RefreshJobRequest) -> RefreshEnqueueResult:
        """Enqueue or suppress a duplicate active job."""

    def get_status(self, stable_job_key: str) -> RefreshJobStatusRecord | None:
        """Return observable status for a stable key, if known."""

    def claim_next(self, *, started_at: datetime) -> ClaimedRefreshJob | None:
        """Claim one queued job for worker execution."""

    def finish(
        self,
        stable_job_key: str,
        *,
        status: RefreshJobStatus,
        finished_at: datetime,
        failure_reason: str | None = None,
        retry_count: int | None = None,
        source_version_refs: tuple[str, ...] | None = None,
        source_version_bundle_ref: str | None = None,
        stale_output_count: int | None = None,
    ) -> RefreshJobStatusRecord:
        """Persist the terminal status from a worker execution."""


def stable_job_key_for(
    job_type: RefreshJobType,
    target_scope: dict[str, Any] | None = None,
    *,
    target_id: str | None = None,
) -> str:
    """Build a deterministic dedupe key for a refresh job scope."""

    canonical_scope = json.dumps(
        target_scope or {},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(
        f"{job_type.value}:{target_id or ''}:{canonical_scope}".encode()
    )
    return f"{job_type.value}:{digest.hexdigest()[:16]}"


def make_refresh_job_request(
    job_type: RefreshJobType,
    *,
    target_scope: dict[str, Any] | None = None,
    target_id: str | None = None,
    requested_by: str = "system",
    retry_count: int = 0,
    max_retries: int = 3,
    source_version_refs: tuple[str, ...] = (),
    source_version_bundle_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RefreshJobRequest:
    scope = dict(target_scope or {})
    return RefreshJobRequest(
        stable_job_key=stable_job_key_for(job_type, scope, target_id=target_id),
        job_type=job_type,
        target_scope=scope,
        target_id=target_id,
        requested_by=requested_by,
        retry_count=retry_count,
        max_retries=max_retries,
        source_version_refs=source_version_refs,
        source_version_bundle_ref=source_version_bundle_ref,
        metadata=dict(metadata or {}),
    )


__all__ = [
    "ACTIVE_REFRESH_STATUSES",
    "ClaimedRefreshJob",
    "RefreshEnqueueOutcome",
    "RefreshEnqueueResult",
    "RefreshJobRequest",
    "RefreshQueueAdapter",
    "make_refresh_job_request",
    "stable_job_key_for",
]
