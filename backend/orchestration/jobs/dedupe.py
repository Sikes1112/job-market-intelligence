"""Deterministic dedupe-key and scope-hash helpers.

Pure functions. No DB access, no JobType-specific subject extraction.

* :func:`scope_hash` produces a stable SHA-256 over the canonical JSON form of
  a scope dict. Same input → same hash, regardless of key insertion order.
* :func:`dedupe_key` formats a queue dedupe key as
  ``{job_type}::[extra_segments::]{scope_hash}``. The optional
  ``extra_segments`` mirror the human-readable subject embedded in the
  documented examples (``QUEUE_AND_WORKER_MODEL.md`` §6 rule 4:
  ``region_score_recompute::greater_boston::regionscore_inputs_hash``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from backend.orchestration.jobs.types import JobType


def scope_hash(scope: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hex digest of a scope mapping."""
    if scope is None:
        scope = {}
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dedupe_key(
    job_type: JobType | str,
    scope: Mapping[str, Any],
    *,
    extra_segments: Sequence[str] = (),
) -> str:
    jt = JobType(job_type) if not isinstance(job_type, JobType) else job_type
    parts: list[str] = [jt.value]
    for segment in extra_segments:
        if not isinstance(segment, str) or not segment:
            raise ValueError(f"dedupe extra segment must be a non-empty string: {segment!r}")
        if "::" in segment:
            raise ValueError(f"dedupe segment must not contain '::': {segment!r}")
        parts.append(segment)
    parts.append(scope_hash(scope))
    return "::".join(parts)
