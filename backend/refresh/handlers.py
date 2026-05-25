"""Refresh job handler dispatch.

The default registry is deliberately conservative. Batch 2 creates the runtime
boundary, but it does not wire heavy data refreshes. Default handlers therefore
return explicit ``handler_not_wired_yet`` failures instead of pretending that
canonical data, scores, or outputs were refreshed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.refresh.job_types import REQUIRED_REFRESH_JOB_TYPES, RefreshJobType
from backend.refresh.queue import RefreshJobRequest
from backend.refresh.status import RefreshJobStatus


@dataclass(frozen=True)
class RefreshHandlerResult:
    status: RefreshJobStatus
    failure_reason: str | None = None
    source_version_refs: tuple[str, ...] = ()
    source_version_bundle_ref: str | None = None
    stale_output_count: int | None = None


RefreshHandler = Callable[[RefreshJobRequest], RefreshHandlerResult]


class RefreshHandlerDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[RefreshJobType, RefreshHandler] = {}

    def register(self, job_type: RefreshJobType, handler: RefreshHandler) -> None:
        self._handlers[job_type] = handler

    def has(self, job_type: RefreshJobType) -> bool:
        return job_type in self._handlers

    def registered_types(self) -> frozenset[RefreshJobType]:
        return frozenset(self._handlers)

    def dispatch(self, request: RefreshJobRequest) -> RefreshHandlerResult:
        handler = self._handlers.get(request.job_type)
        if handler is None:
            return RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason=f"handler_not_registered:{request.job_type.value}",
                source_version_refs=request.source_version_refs,
                source_version_bundle_ref=request.source_version_bundle_ref,
            )
        return handler(request)


def _placeholder_handler(request: RefreshJobRequest) -> RefreshHandlerResult:
    return RefreshHandlerResult(
        status=RefreshJobStatus.FAILED,
        failure_reason=f"handler_not_wired_yet:{request.job_type.value}",
        source_version_refs=request.source_version_refs,
        source_version_bundle_ref=request.source_version_bundle_ref,
    )


def default_refresh_dispatcher() -> RefreshHandlerDispatcher:
    dispatcher = RefreshHandlerDispatcher()
    for job_type in REQUIRED_REFRESH_JOB_TYPES:
        dispatcher.register(job_type, _placeholder_handler)
    return dispatcher


assert default_refresh_dispatcher().registered_types() == REQUIRED_REFRESH_JOB_TYPES


__all__ = [
    "RefreshHandler",
    "RefreshHandlerDispatcher",
    "RefreshHandlerResult",
    "default_refresh_dispatcher",
]
