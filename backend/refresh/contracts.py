"""Refresh job contracts and layer boundaries.

The refresh layer defines the queue/job contract surface only. Existing
ingestion, provenance, scoring, output, and API modules remain authoritative
for truth construction and user-facing semantics.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.refresh.job_types import (
    REQUIRED_REFRESH_JOB_TYPES,
    RefreshJobType,
    coerce_refresh_job_type,
)


class RefreshOperationKind(StrEnum):
    SOURCE_DATA_REFRESH = "source_data_refresh"
    DERIVED_DATA_RECOMPUTE = "derived_data_recompute"
    OUTPUT_REBUILD = "output_rebuild"
    AUDIT = "audit"


class RefreshScopeKind(StrEnum):
    GLOBAL = "global"
    COMPANY = "company"
    REGION = "region"
    COMPANY_REGION = "company_region"
    OUTPUT = "output"
    AUDIT_SCOPE = "audit_scope"


class SourcePreservationRequirement(BaseModel):
    """Version-preservation requirements for jobs that write derived state."""

    model_config = ConfigDict(frozen=True)

    source_version_refs_required: bool
    source_bundle_ref_required: bool
    reason: str = Field(min_length=1)


class RefreshContractBoundary(BaseModel):
    """Negative capabilities the refresh queue must not take over."""

    model_config = ConfigDict(frozen=True)

    queue_owns_scoring_policy: bool = False
    queue_owns_ingestion_truth: bool = False
    queue_owns_source_freshness_rules: bool = False
    queue_owns_output_semantics: bool = False


class RefreshJobContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_type: RefreshJobType
    operation_kind: RefreshOperationKind
    target_scope_kind: RefreshScopeKind
    target_scope_required: bool
    description: str = Field(min_length=1)
    source_preservation: SourcePreservationRequirement
    boundary: RefreshContractBoundary = Field(default_factory=RefreshContractBoundary)

    @property
    def requires_source_preservation(self) -> bool:
        return (
            self.source_preservation.source_version_refs_required
            and self.source_preservation.source_bundle_ref_required
        )


_SOURCE_WRITER_PRESERVATION = SourcePreservationRequirement(
    source_version_refs_required=True,
    source_bundle_ref_required=True,
    reason=(
        "Refresh jobs that write data, scores, or outputs must carry source "
        "version references and preserve the source_version_bundle used by "
        "the authoritative writer."
    ),
)

_AUDIT_PRESERVATION = SourcePreservationRequirement(
    source_version_refs_required=False,
    source_bundle_ref_required=False,
    reason=(
        "Audit runs inspect existing records and may report source-version "
        "gaps, but this contract does not make audits write refreshed data."
    ),
)


REFRESH_JOB_CONTRACTS: dict[RefreshJobType, RefreshJobContract] = {
    RefreshJobType.COMPANY_UNIVERSE_REFRESH: RefreshJobContract(
        job_type=RefreshJobType.COMPANY_UNIVERSE_REFRESH,
        operation_kind=RefreshOperationKind.SOURCE_DATA_REFRESH,
        target_scope_kind=RefreshScopeKind.REGION,
        target_scope_required=True,
        description="Refresh the company universe for a configured market scope.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.PRESENCE_REFRESH: RefreshJobContract(
        job_type=RefreshJobType.PRESENCE_REFRESH,
        operation_kind=RefreshOperationKind.SOURCE_DATA_REFRESH,
        target_scope_kind=RefreshScopeKind.COMPANY_REGION,
        target_scope_required=True,
        description="Refresh company presence evidence for a company/region scope.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.HIRING_REFRESH: RefreshJobContract(
        job_type=RefreshJobType.HIRING_REFRESH,
        operation_kind=RefreshOperationKind.SOURCE_DATA_REFRESH,
        target_scope_kind=RefreshScopeKind.COMPANY_REGION,
        target_scope_required=True,
        description="Refresh hiring signals for a company/region or market scope.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.ENTRY_LEVEL_REFRESH: RefreshJobContract(
        job_type=RefreshJobType.ENTRY_LEVEL_REFRESH,
        operation_kind=RefreshOperationKind.SOURCE_DATA_REFRESH,
        target_scope_kind=RefreshScopeKind.COMPANY_REGION,
        target_scope_required=True,
        description="Refresh entry-level hiring signals for recruiting-window scopes.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.SCORE_RECOMPUTE: RefreshJobContract(
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        operation_kind=RefreshOperationKind.DERIVED_DATA_RECOMPUTE,
        target_scope_kind=RefreshScopeKind.REGION,
        target_scope_required=True,
        description="Recompute derived market scores after canonical data changes.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.OUTPUT_REBUILD: RefreshJobContract(
        job_type=RefreshJobType.OUTPUT_REBUILD,
        operation_kind=RefreshOperationKind.OUTPUT_REBUILD,
        target_scope_kind=RefreshScopeKind.OUTPUT,
        target_scope_required=True,
        description="Rebuild prepared output objects after score or data changes.",
        source_preservation=_SOURCE_WRITER_PRESERVATION,
    ),
    RefreshJobType.AUDIT_RUN: RefreshJobContract(
        job_type=RefreshJobType.AUDIT_RUN,
        operation_kind=RefreshOperationKind.AUDIT,
        target_scope_kind=RefreshScopeKind.AUDIT_SCOPE,
        target_scope_required=False,
        description="Run scheduled or manual integrity audits without rebuilding data.",
        source_preservation=_AUDIT_PRESERVATION,
    ),
}


def contract_for(job_type: RefreshJobType | str) -> RefreshJobContract:
    return REFRESH_JOB_CONTRACTS[coerce_refresh_job_type(job_type)]


def contracts_requiring_source_preservation() -> tuple[RefreshJobContract, ...]:
    return tuple(
        contract
        for contract in REFRESH_JOB_CONTRACTS.values()
        if contract.requires_source_preservation
    )


assert frozenset(REFRESH_JOB_CONTRACTS) == REQUIRED_REFRESH_JOB_TYPES


__all__ = [
    "REFRESH_JOB_CONTRACTS",
    "RefreshContractBoundary",
    "RefreshJobContract",
    "RefreshOperationKind",
    "RefreshScopeKind",
    "SourcePreservationRequirement",
    "contract_for",
    "contracts_requiring_source_preservation",
]
