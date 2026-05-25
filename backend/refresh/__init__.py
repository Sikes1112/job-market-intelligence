"""Refresh queue/job contract foundation.

This package is intentionally contract-only. It describes the production
refresh posture, job vocabulary, cadence defaults, and observability fields
without starting workers, schedulers, routes, or external network clients.
"""

from backend.refresh.cadence import CADENCE_BY_JOB_TYPE, CadenceClass, cadence_for
from backend.refresh.contracts import REFRESH_JOB_CONTRACTS, RefreshJobContract, contract_for
from backend.refresh.handlers import RefreshHandlerDispatcher, RefreshHandlerResult
from backend.refresh.job_types import REQUIRED_REFRESH_JOB_TYPES, RefreshJobType
from backend.refresh.queue import RefreshJobRequest, stable_job_key_for
from backend.refresh.queue_decision import SELECTED_QUEUE_DECISION, QueueBackend
from backend.refresh.runner import RefreshWorkerRunner
from backend.refresh.scheduler import RefreshSchedulerPlanner, RefreshSchedulerRunner
from backend.refresh.status import (
    RefreshJobStatus,
    RefreshJobStatusRecord,
    RefreshObservabilitySummary,
    summarize_refresh_observability,
)

__all__ = [
    "CADENCE_BY_JOB_TYPE",
    "REQUIRED_REFRESH_JOB_TYPES",
    "REFRESH_JOB_CONTRACTS",
    "SELECTED_QUEUE_DECISION",
    "CadenceClass",
    "QueueBackend",
    "RefreshHandlerDispatcher",
    "RefreshHandlerResult",
    "RefreshJobRequest",
    "RefreshJobContract",
    "RefreshJobStatus",
    "RefreshJobStatusRecord",
    "RefreshJobType",
    "RefreshObservabilitySummary",
    "RefreshSchedulerPlanner",
    "RefreshSchedulerRunner",
    "RefreshWorkerRunner",
    "cadence_for",
    "contract_for",
    "stable_job_key_for",
    "summarize_refresh_observability",
]
