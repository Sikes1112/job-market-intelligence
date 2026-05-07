"""Canonical-JSON + SHA-256 helpers for ``artifact_hash``.

Mirrors the deterministic-hash pattern from
:mod:`backend.orchestration.jobs.dedupe`. Same payload always produces the
same hash; key ordering in dicts is irrelevant; list ordering *is* relevant
because lists are part of the payload's semantic shape (top-N orderings
matter).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return a canonical JSON encoding of ``payload``.

    * keys are sorted alphabetically
    * no whitespace
    * datetimes / unsupported types fall back to ``str()``
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def artifact_hash(payload: Any) -> str:
    """Return the SHA-256 hex digest of ``canonical_json(payload)``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
