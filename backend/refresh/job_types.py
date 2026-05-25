"""Stable refresh job vocabulary for Layer 8.

These names describe refresh-level production contracts. They intentionally do
not replace the narrower orchestration handler names that already exist under
``backend.orchestration.jobs``.
"""

from __future__ import annotations

from enum import StrEnum


class RefreshJobType(StrEnum):
    COMPANY_UNIVERSE_REFRESH = "company_universe_refresh"
    PRESENCE_REFRESH = "presence_refresh"
    HIRING_REFRESH = "hiring_refresh"
    ENTRY_LEVEL_REFRESH = "entry_level_refresh"
    SCORE_RECOMPUTE = "score_recompute"
    OUTPUT_REBUILD = "output_rebuild"
    AUDIT_RUN = "audit_run"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


REQUIRED_REFRESH_JOB_TYPES: frozenset[RefreshJobType] = frozenset(RefreshJobType)


def coerce_refresh_job_type(value: RefreshJobType | str) -> RefreshJobType:
    if isinstance(value, RefreshJobType):
        return value
    if not isinstance(value, str):
        raise ValueError(
            f"refresh job type must be str or RefreshJobType, got {type(value).__name__}"
        )
    return RefreshJobType(value)


__all__ = [
    "REQUIRED_REFRESH_JOB_TYPES",
    "RefreshJobType",
    "coerce_refresh_job_type",
]
