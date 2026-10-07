"""Acquisition adapter contract for Layer 38A."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from backend.current_opportunities.schemas import (
    AcquiredOpportunityRecord,
    AcquisitionResult,
    AcquisitionRunStatus,
    RetryClassification,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OpportunityAcquisitionAdapter(Protocol):
    """Provider-specific acquisition boundary.

    Adapters fetch or read approved source data and return raw observations.
    They do not normalize, resolve identity, write canonical rows, or decide
    ranking eligibility.
    """

    source_id: str

    def acquire(
        self,
        *,
        run_id: str,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> AcquisitionResult: ...


@dataclass(frozen=True, slots=True)
class StaticOpportunityAdapter:
    """Deterministic adapter used by tests and approved curated inputs."""

    source_id: str
    records: tuple[dict[str, Any], ...]
    collected_at: datetime | None = None
    status: AcquisitionRunStatus = AcquisitionRunStatus.COMPLETED
    retry_classification: RetryClassification = RetryClassification.NONE
    failure_details: Mapping[str, Any] | None = None
    warnings: tuple[str, ...] = ()

    def acquire(
        self,
        *,
        run_id: str,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> AcquisitionResult:
        collected = self.collected_at or _utc_now()
        records = tuple(
            AcquiredOpportunityRecord(
                provider_record_id=str(item["provider_record_id"]),
                observed_at=item.get("observed_at") or collected,
                collected_at=item.get("collected_at") or collected,
                cursor=item.get("cursor"),
                raw_payload=dict(item.get("raw_payload", item)),
                status=item.get("status", "active"),
                retry_classification=item.get("retry_classification", "none"),
                terminal_failure=bool(item.get("terminal_failure", False)),
                error_code=item.get("error_code"),
                error_message=item.get("error_message"),
            )
            for item in self.records
        )
        return AcquisitionResult(
            source_id=self.source_id,
            run_id=run_id,
            collected_at=collected,
            records=records,
            cursor=(records[-1].cursor if records else None),
            checkpoint=dict(checkpoint or {}),
            status=self.status,
            retry_classification=self.retry_classification,
            failure_details=dict(self.failure_details or {}),
            warnings=self.warnings,
        )


class AdapterRegistry:
    """Small typed registry; avoids spreading provider-specific logic."""

    def __init__(self) -> None:
        self._adapters: dict[str, OpportunityAcquisitionAdapter] = {}

    def register(self, adapter: OpportunityAcquisitionAdapter) -> None:
        self._adapters[adapter.source_id] = adapter

    def get(self, source_id: str) -> OpportunityAcquisitionAdapter:
        try:
            return self._adapters[source_id]
        except KeyError as exc:
            raise KeyError(f"no current-opportunity adapter registered for {source_id!r}") from exc
