"""Job dispatch / lifecycle enums.

These enums describe orchestration-job concerns (what kind of job, what
execution status, what trigger class, what priority). They are intentionally
separate from :class:`backend.shared.state.ObjectState`, which models the
lifecycle of canonical truth and derived output objects.

Source: ``DATA_MODEL.md`` §9, ``JOB_CONTRACT_SPEC.md`` §2, and
``JOB_ORCHESTRATION_MATRIX.md`` §2.
"""

from __future__ import annotations

from enum import StrEnum


class JobType(StrEnum):
    """Every job type the MVP orchestration model knows about."""

    GEOGRAPHY_BUILD = "geography_build"
    COMPANY_UNIVERSE_INTAKE = "company_universe_intake"
    ELIGIBILITY_CLASSIFICATION = "eligibility_classification"
    PRESENCE_MAPPING = "presence_mapping"
    HIRING_REFRESH = "hiring_refresh"
    ENTRY_LEVEL_REFRESH = "entry_level_refresh"
    REGION_SCORE_RECOMPUTE = "region_score_recompute"
    REGION_OUTPUT_BUILD = "region_output_build"
    COMPANY_OUTPUT_BUILD = "company_output_build"
    COMPARISON_CACHE_BUILD = "comparison_cache_build"
    PERSONAL_OVERLAY_QUERY = "personal_overlay_query"
    CONTEXTUAL_CHALLENGE_BUILD = "contextual_challenge_build"
    AUDIT = "audit"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class JobStatus(StrEnum):
    """Job execution lifecycle.

    Distinct from :class:`backend.shared.state.ObjectState`. Object state is
    "is the *thing* fresh / stale / blocked"; job status is "did the *job*
    succeed / fail / time out".
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)

    @classmethod
    def terminal(cls) -> frozenset[JobStatus]:
        """Statuses after which the job will not run again on its own."""
        return frozenset({cls.SUCCEEDED, cls.SUCCEEDED_WITH_WARNINGS, cls.PARTIAL,
                          cls.FAILED, cls.CANCELLED})

    @classmethod
    def successful(cls) -> frozenset[JobStatus]:
        """Statuses that count as success per ``JOB_CONTRACT_SPEC.md`` §21."""
        return frozenset({cls.SUCCEEDED, cls.SUCCEEDED_WITH_WARNINGS})


class TriggerType(StrEnum):
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    MANUAL = "manual"
    USER_QUERY = "user_query"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
