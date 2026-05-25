"""Output rebuild refresh handler wiring.

This module lives in ``backend.refresh`` so the output assembly layer remains
free of worker/runtime imports. The handler uses the existing
``OutputAssemblyService`` builders, which preserve output semantics and source
version bundles.
"""

from __future__ import annotations

from backend.outputs.cache_repository import OutputCacheRepository
from backend.outputs.models import OutputMetadata
from backend.outputs.service import OutputAssemblyService
from backend.outputs.types import OutputType
from backend.refresh.handlers import RefreshHandler, RefreshHandlerResult
from backend.refresh.queue import RefreshJobRequest
from backend.refresh.status import RefreshJobStatus


def make_output_rebuild_handler(
    *,
    cache_repo: OutputCacheRepository,
    output_service: OutputAssemblyService,
) -> RefreshHandler:
    def _handler(request: RefreshJobRequest) -> RefreshHandlerResult:
        output_id = request.target_scope.get("output_id")
        if not isinstance(output_id, str) or not output_id:
            return RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason="output_rebuild_missing_output_id",
                source_version_refs=request.source_version_refs,
                source_version_bundle_ref=request.source_version_bundle_ref,
            )

        row = cache_repo.get(output_id)
        if row is None:
            return RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason=f"output_rebuild_output_not_found:{output_id}",
                source_version_refs=request.source_version_refs,
                source_version_bundle_ref=request.source_version_bundle_ref,
            )

        try:
            rebuilt = _rebuild(row, output_service)
        except Exception as exc:
            reason = f"output_rebuild_failed:{type(exc).__name__}:{exc!s}"
            cache_repo.record_rebuild_failure(row, reason=reason)
            return RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason=reason,
                source_version_refs=tuple(row.source_version_refs or request.source_version_refs),
                source_version_bundle_ref=row.source_bundle_ref
                or request.source_version_bundle_ref,
            )

        rebuilt_row = rebuilt.metadata
        return RefreshHandlerResult(
            status=RefreshJobStatus.SUCCEEDED,
            source_version_refs=tuple(rebuilt_row.source_version_refs or ()),
            source_version_bundle_ref=rebuilt_row.source_bundle_ref,
            stale_output_count=cache_repo.observability().stale_output_count,
        )

    return _handler


def _rebuild(row: OutputMetadata, output_service: OutputAssemblyService):
    if row.output_type == OutputType.REGION_OUTPUT.value:
        return output_service.build_region(row.subject_id)
    if row.output_type == OutputType.COMPANY_OUTPUT.value:
        return output_service.build_company(row.subject_id)
    if row.output_type == OutputType.COMPARISON_OUTPUT.value:
        region_a, region_b = _split_comparison_subject(row.subject_id)
        return output_service.build_comparison(region_a, region_b)
    raise ValueError(f"output_rebuild_unsupported_output_type:{row.output_type}")


def _split_comparison_subject(subject_id: str) -> tuple[str, str]:
    parts = [part for part in subject_id.split("__") if part]
    if len(parts) != 2:
        raise ValueError(f"invalid comparison subject_id: {subject_id!r}")
    return parts[0], parts[1]


__all__ = ["make_output_rebuild_handler"]
