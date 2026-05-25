"""DB-backed output cache helpers.

The cache is stored on ``OutputMetadata`` so local SQLite and production
Postgres use the same logical model. JSON payload storage is intentionally
simple; object storage can be layered behind ``artifact_uri`` later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from backend.orchestration.jobs.errors import JobWarning, WarningSeverity
from backend.outputs.hashing import artifact_hash
from backend.outputs.models import OutputMetadata
from backend.outputs.payloads import (
    CompanyOutput,
    ComparisonOutput,
    OutputPayloadMetadata,
    RegionOutput,
)
from backend.outputs.types import OutputType

CachedOutputPayload = RegionOutput | CompanyOutput | ComparisonOutput

_PAYLOAD_MODELS = {
    OutputType.REGION_OUTPUT.value: RegionOutput,
    OutputType.COMPANY_OUTPUT.value: CompanyOutput,
    OutputType.COMPARISON_OUTPUT.value: ComparisonOutput,
}


def source_version_refs_for_bundle(bundle: dict[str, Any] | None) -> tuple[str, ...]:
    """Flatten a source-version bundle into deterministic opaque refs."""

    refs: list[str] = []

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                walk(next_prefix, value[key])
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(f"{prefix}[{index}]", item)
            return
        refs.append(f"{prefix}={value}")

    walk("", bundle or {})
    return tuple(ref for ref in refs if ref and not ref.endswith("={}"))


def source_bundle_ref_for_bundle(bundle: dict[str, Any] | None) -> str | None:
    if not bundle:
        return None
    return f"source_bundle:{artifact_hash(bundle)[:16]}"


def payload_json(payload: CachedOutputPayload) -> dict[str, Any]:
    return payload.model_dump(mode="json")


def load_cached_output(row: OutputMetadata) -> CachedOutputPayload | None:
    """Validate and return cached output, adjusted to current row state.

    Invalid cache payloads return ``None`` so callers can fall back to live
    assembly without mutating the cache row.
    """

    if row.cached_payload is None:
        return None
    model = _PAYLOAD_MODELS.get(row.output_type)
    if model is None:
        return None
    try:
        payload = model.model_validate(row.cached_payload)
    except ValidationError:
        return None

    metadata = payload.metadata.model_copy(
        update={
            "state": row.state,
            "freshness_expires_at": row.freshness_expires_at,
            "source_versions": row.source_version_bundle or payload.metadata.source_versions,
            "warnings": _warnings_with_cache_state(payload.metadata, row),
        }
    )
    return payload.model_copy(update={"metadata": metadata})


def output_data_block(payload: CachedOutputPayload) -> dict[str, Any]:
    if isinstance(payload, RegionOutput):
        return payload.region.model_dump(mode="json")
    if isinstance(payload, CompanyOutput):
        return payload.company.model_dump(mode="json")
    return payload.comparison.model_dump(mode="json")


def mark_rebuild_failed(row: OutputMetadata, *, reason: str) -> None:
    row.latest_rebuild_status = "failed"
    row.latest_rebuild_failure_reason = reason


def mark_rebuild_succeeded(row: OutputMetadata, *, rebuilt_at: datetime | None = None) -> None:
    row.rebuilt_at = rebuilt_at or datetime.now(UTC)
    row.latest_rebuild_status = "succeeded"
    row.latest_rebuild_failure_reason = None
    row.rebuild_job_key = None
    row.stale_reason = None


def _warnings_with_cache_state(
    metadata: OutputPayloadMetadata, row: OutputMetadata
) -> list[JobWarning]:
    warnings = list(metadata.warnings)
    if row.state == "stale" and row.stale_reason:
        warnings.append(
            JobWarning(
                warning_code="output_cache_stale",
                severity=WarningSeverity.MEDIUM,
                scope_type=row.output_type,
                scope_ref=row.subject_id,
                message=row.stale_reason,
            )
        )
    if row.latest_rebuild_status == "failed" and row.latest_rebuild_failure_reason:
        warnings.append(
            JobWarning(
                warning_code="output_rebuild_failed",
                severity=WarningSeverity.HIGH,
                scope_type=row.output_type,
                scope_ref=row.subject_id,
                message=row.latest_rebuild_failure_reason,
            )
        )
    return warnings


__all__ = [
    "CachedOutputPayload",
    "load_cached_output",
    "mark_rebuild_failed",
    "mark_rebuild_succeeded",
    "output_data_block",
    "payload_json",
    "source_bundle_ref_for_bundle",
    "source_version_refs_for_bundle",
]
