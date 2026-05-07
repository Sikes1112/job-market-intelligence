"""API response envelope helpers.

Wraps Slice 11 output payloads in the documented envelope shape from
``API_SURFACES.md`` §2.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.outputs.models import OutputMetadata
from backend.outputs.payloads import OutputPayloadMetadata

# Documented envelope error codes (``API_SURFACES.md`` §10).
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"


def _is_stale(freshness_expires_at: datetime | None, *, now: datetime) -> bool:
    if freshness_expires_at is None:
        return False
    if freshness_expires_at.tzinfo is None:
        freshness_expires_at = freshness_expires_at.replace(tzinfo=UTC)
    return freshness_expires_at <= now


def _status_for_state(state: str) -> str:
    if state == "fresh":
        return "success"
    if state in {"partial", "stale"}:
        return "partial"
    if state in {"failed", "blocked"}:
        return "error"
    # ``new`` / ``building`` / ``rebuilding`` / unknown → success-with-state
    return "success"


def success_envelope(
    *,
    data: Any,
    output_metadata_row: OutputMetadata | None = None,
    payload_metadata: OutputPayloadMetadata | None = None,
    explicit_state: str | None = None,
) -> dict[str, Any]:
    """Build a success/partial/stale envelope around assembled output data.

    Either ``payload_metadata`` (preferred — comes from Slice 11 builders)
    or ``explicit_state`` should be supplied. ``output_metadata_row``
    contributes ``last_updated_at`` and the persisted state when present.
    """
    now = datetime.now(UTC)
    state = (
        payload_metadata.state if payload_metadata is not None else explicit_state
    ) or "fresh"
    freshness_expires_at = (
        payload_metadata.freshness_expires_at
        if payload_metadata is not None
        else None
    )
    last_updated_at = (
        output_metadata_row.updated_at if output_metadata_row is not None else None
    )
    if last_updated_at is not None and last_updated_at.tzinfo is None:
        last_updated_at = last_updated_at.replace(tzinfo=UTC)

    warnings = (
        [w.model_dump(mode="json") for w in payload_metadata.warnings]
        if payload_metadata is not None
        else []
    )
    source_versions = (
        payload_metadata.source_versions if payload_metadata is not None else {}
    )

    metadata = {
        "state": state,
        "freshness": {
            "last_updated_at": (
                last_updated_at.isoformat() if last_updated_at is not None else None
            ),
            "freshness_expires_at": (
                freshness_expires_at.isoformat()
                if freshness_expires_at is not None
                else None
            ),
            "is_stale": _is_stale(freshness_expires_at, now=now),
        },
        "source_versions": source_versions,
        "warnings": warnings,
    }
    return {
        "status": _status_for_state(state),
        "data": data,
        "metadata": metadata,
        "error": None,
    }


def lightweight_success_envelope(*, data: Any, state: str = "fresh") -> dict[str, Any]:
    """Envelope for endpoints that don't go through Slice 11 (e.g. /regions list)."""
    return {
        "status": "success",
        "data": data,
        "metadata": {"state": state, "warnings": []},
        "error": None,
    }


def error_envelope(*, code: str, message: str, state: str = "failed") -> dict[str, Any]:
    return {
        "status": "error",
        "data": None,
        "metadata": {"state": state, "warnings": []},
        "error": {"code": code, "message": message},
    }
