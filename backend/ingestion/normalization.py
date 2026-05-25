"""Narrow Layer 4A normalization helpers.

These helpers validate and label payloads. They do not parse live sources,
canonicalize facts, or create provenance records.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from backend.ingestion.contracts import (
    NormalizationResult,
    RawObservationPayload,
)
from backend.ingestion.status import CanonicalFactIntent, NormalizationStatus


def payload_checksum(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_raw_payload(payload: object) -> RawObservationPayload:
    if not isinstance(payload, dict):
        raise ValueError("raw payload must be a JSON object")
    try:
        return RawObservationPayload(body=payload)
    except ValidationError as exc:
        raise ValueError("raw payload failed validation") from exc


def parsed_result(
    *,
    raw_record_id: str,
    parsing_notes: str | None = None,
) -> NormalizationResult:
    return NormalizationResult(
        raw_record_id=raw_record_id,
        status=NormalizationStatus.PARSED,
        parsing_notes=parsing_notes,
    )


def normalized_result(
    *,
    raw_record_id: str,
    intended_fact_type: CanonicalFactIntent,
    normalized_payload: Mapping[str, Any],
    parsing_notes: str | None = None,
) -> NormalizationResult:
    return NormalizationResult(
        raw_record_id=raw_record_id,
        status=NormalizationStatus.NORMALIZED,
        intended_fact_type=intended_fact_type,
        normalized_payload=dict(normalized_payload),
        parsing_notes=parsing_notes,
    )


def conflicting_result(
    *,
    raw_record_id: str,
    parsing_notes: str,
    parsing_errors: tuple[str, ...] = (),
) -> NormalizationResult:
    return NormalizationResult(
        raw_record_id=raw_record_id,
        status=NormalizationStatus.CONFLICTING,
        parsing_notes=parsing_notes,
        parsing_errors=parsing_errors,
    )


def rejected_result(
    *,
    raw_record_id: str,
    error: str,
) -> NormalizationResult:
    return NormalizationResult(
        raw_record_id=raw_record_id,
        status=NormalizationStatus.REJECTED,
        parsing_errors=(error,),
    )
