"""Refresh scheduler planning and enqueue runner.

The scheduler process plans cadence-driven jobs and enqueues them. It does not
call refresh handlers or perform data refresh work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.refresh.cadence import CADENCE_BY_JOB_TYPE, TriggerPosture
from backend.refresh.job_types import RefreshJobType
from backend.refresh.queue import (
    RefreshEnqueueResult,
    RefreshJobRequest,
    RefreshQueueAdapter,
    make_refresh_job_request,
)

SCHEDULED_TRIGGER_POSTURES = frozenset(
    {
        TriggerPosture.SCHEDULED,
        TriggerPosture.SCHEDULED_AND_EVENT_DRIVEN,
        TriggerPosture.SCHEDULED_OR_MANUAL,
    }
)

DEFAULT_SCHEDULE_TARGET_SCOPES: dict[RefreshJobType, dict[str, str]] = {
    RefreshJobType.COMPANY_UNIVERSE_REFRESH: {"scope": "all_markets"},
    RefreshJobType.PRESENCE_REFRESH: {"scope": "all_active_companies"},
    RefreshJobType.HIRING_REFRESH: {"scope": "all_active_markets"},
    RefreshJobType.ENTRY_LEVEL_REFRESH: {"scope": "entry_level_markets"},
    RefreshJobType.AUDIT_RUN: {"scope": "system"},
}


@dataclass(frozen=True)
class RefreshSchedulePlan:
    planned_at: datetime
    requests: tuple[RefreshJobRequest, ...]


@dataclass(frozen=True)
class RefreshScheduleRunResult:
    plan: RefreshSchedulePlan
    enqueue_results: tuple[RefreshEnqueueResult, ...]


class RefreshSchedulerPlanner:
    """Build deterministic cadence-driven refresh requests."""

    def __init__(
        self,
        target_scopes: dict[RefreshJobType, dict[str, str]] | None = None,
    ) -> None:
        self._target_scopes = target_scopes or DEFAULT_SCHEDULE_TARGET_SCOPES

    def plan(self, *, now: datetime) -> RefreshSchedulePlan:
        requests: list[RefreshJobRequest] = []
        for job_type, policy in CADENCE_BY_JOB_TYPE.items():
            if policy.trigger_posture not in SCHEDULED_TRIGGER_POSTURES:
                continue
            target_scope = self._target_scopes.get(job_type)
            if target_scope is None:
                continue
            requests.append(
                make_refresh_job_request(
                    job_type,
                    target_scope=target_scope,
                    requested_by="scheduler",
                    metadata={
                        "planned_at": now.isoformat(),
                        "cadence_class": policy.cadence_class.value,
                        "trigger_posture": policy.trigger_posture.value,
                        "default_queue_group": policy.default_queue_group,
                    },
                )
            )
        return RefreshSchedulePlan(planned_at=now, requests=tuple(requests))


class RefreshSchedulerRunner:
    def __init__(
        self,
        queue: RefreshQueueAdapter,
        *,
        planner: RefreshSchedulerPlanner | None = None,
    ) -> None:
        self._queue = queue
        self._planner = planner or RefreshSchedulerPlanner()

    def enqueue_due(self, *, now: datetime) -> RefreshScheduleRunResult:
        plan = self._planner.plan(now=now)
        results = tuple(self._queue.enqueue(request) for request in plan.requests)
        return RefreshScheduleRunResult(plan=plan, enqueue_results=results)


__all__ = [
    "DEFAULT_SCHEDULE_TARGET_SCOPES",
    "RefreshSchedulePlan",
    "RefreshScheduleRunResult",
    "RefreshSchedulerPlanner",
    "RefreshSchedulerRunner",
    "SCHEDULED_TRIGGER_POSTURES",
]
