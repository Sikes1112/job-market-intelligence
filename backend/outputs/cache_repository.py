"""Repository helpers for DB-backed output cache rows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.outputs.cache import (
    CachedOutputPayload,
    payload_json,
    source_bundle_ref_for_bundle,
    source_version_refs_for_bundle,
)
from backend.outputs.hashing import artifact_hash as compute_artifact_hash
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType


@dataclass(frozen=True)
class OutputCacheObservability:
    stale_output_count: int
    stale_outputs_by_type: dict[str, int]
    last_successful_rebuild_at: datetime | None
    last_successful_rebuild_output_id: str | None
    latest_failure_reason: str | None


class OutputCacheRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, output_id: str) -> OutputMetadata | None:
        return self._session.get(OutputMetadata, output_id)

    def get_by_type_and_subject(
        self, output_type: str | OutputType, subject_id: str
    ) -> OutputMetadata | None:
        output_type_value = (
            output_type.value if isinstance(output_type, OutputType) else output_type
        )
        stmt = select(OutputMetadata).where(
            OutputMetadata.output_type == output_type_value,
            OutputMetadata.subject_id == subject_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert_cached_output(
        self,
        *,
        output_type: OutputType,
        subject_id: str,
        payload: CachedOutputPayload,
        source_version_bundle: dict[str, Any],
        freshness_expires_at: datetime | None = None,
        state: str = "fresh",
        output_id: str | None = None,
    ) -> OutputMetadata:
        row = self.get_by_type_and_subject(output_type, subject_id)
        if row is None:
            row = OutputMetadata(
                output_id=output_id or f"out_cache_{output_type.value}_{subject_id}",
                output_type=output_type.value,
                subject_id=subject_id,
            )
            self._session.add(row)
        row.cached_payload = payload_json(payload)
        row.artifact_hash = compute_artifact_hash(row.cached_payload)
        row.source_version_bundle = source_version_bundle
        row.source_version_refs = list(source_version_refs_for_bundle(source_version_bundle))
        row.source_bundle_ref = source_bundle_ref_for_bundle(source_version_bundle)
        row.freshness_expires_at = freshness_expires_at
        row.state = state
        row.rebuilt_at = datetime.now(UTC)
        row.latest_rebuild_status = "succeeded"
        row.latest_rebuild_failure_reason = None
        self._session.flush()
        return row

    def list_stale(self) -> list[OutputMetadata]:
        stmt = (
            select(OutputMetadata)
            .where(OutputMetadata.state == "stale")
            .order_by(OutputMetadata.output_type, OutputMetadata.subject_id)
        )
        return list(self._session.execute(stmt).scalars())

    def mark_stale(
        self,
        row: OutputMetadata,
        *,
        reason: str,
        invalidated_at: datetime,
        rebuild_job_key: str | None = None,
    ) -> OutputMetadata:
        if row.state == "fresh":
            row.state = "stale"
        row.stale_reason = reason
        row.invalidated_at = invalidated_at
        if rebuild_job_key is not None:
            row.rebuild_job_key = rebuild_job_key
        self._session.flush()
        return row

    def record_rebuild_failure(self, row: OutputMetadata, *, reason: str) -> OutputMetadata:
        row.latest_rebuild_status = "failed"
        row.latest_rebuild_failure_reason = reason
        self._session.flush()
        return row

    def observability(self) -> OutputCacheObservability:
        rows = list(self._session.execute(select(OutputMetadata)).scalars())
        stale_rows = [row for row in rows if row.state == "stale"]
        by_type = Counter(row.output_type for row in stale_rows)
        successful = [
            row
            for row in rows
            if row.latest_rebuild_status == "succeeded" and row.rebuilt_at is not None
        ]
        latest_success = max(successful, key=lambda row: row.rebuilt_at, default=None)
        failures = [
            row
            for row in rows
            if row.latest_rebuild_status == "failed" and row.latest_rebuild_failure_reason
        ]
        latest_failure = max(failures, key=lambda row: row.updated_at, default=None)
        return OutputCacheObservability(
            stale_output_count=len(stale_rows),
            stale_outputs_by_type=dict(by_type),
            last_successful_rebuild_at=(
                latest_success.rebuilt_at if latest_success is not None else None
            ),
            last_successful_rebuild_output_id=(
                latest_success.output_id if latest_success is not None else None
            ),
            latest_failure_reason=(
                latest_failure.latest_rebuild_failure_reason
                if latest_failure is not None
                else None
            ),
        )


__all__ = ["OutputCacheObservability", "OutputCacheRepository"]
