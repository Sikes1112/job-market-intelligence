"""Layer 4A ingestion contracts.

Contracts here represent raw intake, normalization results, provenance
attachment, and canonical fact proposals. They deliberately stop before
creating trusted canonical facts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.ingestion.status import (
    CanonicalFactIntent,
    CanonicalWriteExecutionStatus,
    CanonicalWriteOperationType,
    CanonicalWritePlanStatus,
    IngestionStatus,
    ManualIngestionRunMode,
    ManualIngestionRunStatus,
    NormalizationStatus,
    PostWriteRefreshExecutionStatus,
    PostWriteRefreshPlanStatus,
    PostWriteRefreshTargetType,
    ProposalReviewStatus,
    fact_binding_type_for_intent,
    provenance_fact_type_for_intent,
)
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    ProvenanceFactType,
    SourceAcceptability,
    SourceType,
)

RAW_INTAKE_SCHEMA_VERSION = "raw_ingestion_v1"


class RawObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body: dict[str, Any] = Field(default_factory=dict)
    content_type: str = Field(default="application/json", min_length=1)

    @field_validator("body")
    @classmethod
    def _body_must_be_json_serializable(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        _assert_json_serializable(value)
        return value


class RawIntakeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(min_length=1, max_length=128)
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=255)
    url_or_provider: str = Field(min_length=1, max_length=1024)
    external_entity_id: str | None = Field(default=None, min_length=1, max_length=128)
    raw_payload: RawObservationPayload
    collected_at: datetime
    observed_at: datetime | None = None
    ingestion_status: IngestionStatus = IngestionStatus.RECEIVED
    normalization_status: NormalizationStatus = NormalizationStatus.RAW_UNREVIEWED
    intended_fact_type: CanonicalFactIntent | None = None
    source_id: str | None = Field(default=None, min_length=1, max_length=64)
    observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    parsing_notes: str | None = Field(default=None, max_length=2048)
    schema_version: str = Field(default=RAW_INTAKE_SCHEMA_VERSION, min_length=1)

    @field_validator("collected_at", "observed_at")
    @classmethod
    def _timestamps_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("ingestion timestamps must be timezone-aware")
        return value


class NormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    status: NormalizationStatus
    normalized_payload: dict[str, Any] | None = None
    intended_fact_type: CanonicalFactIntent | None = None
    parsing_notes: str | None = Field(default=None, max_length=2048)
    parsing_errors: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("normalized_payload")
    @classmethod
    def _normalized_payload_must_be_json_serializable(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is not None:
            _assert_json_serializable(value)
        return value

    @model_validator(mode="after")
    def _normalized_results_need_payload_and_intent(self) -> NormalizationResult:
        if self.status is NormalizationStatus.NORMALIZED:
            if self.normalized_payload is None:
                raise ValueError("normalized results require normalized_payload")
            if self.intended_fact_type is None:
                raise ValueError("normalized results require intended_fact_type")
        return self


class ProvenanceAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    observation_id: str = Field(min_length=1, max_length=64)


class IntakeProvenanceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    observation_id: str = Field(min_length=1, max_length=64)
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=255)
    url_or_provider: str = Field(min_length=1, max_length=1024)
    collected_at: datetime | None = None
    observed_at: datetime | None = None
    license_or_terms_category: LicenseTermsCategory = LicenseTermsCategory.UNKNOWN
    confidence: Confidence = Confidence.UNKNOWN
    data_origin: DataOrigin = DataOrigin.UNKNOWN_ORIGIN
    observation_status: ObservationStatus | None = None
    notes: str | None = Field(default=None, max_length=2048)

    @field_validator("collected_at", "observed_at")
    @classmethod
    def _provenance_timestamps_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("provenance timestamps must be timezone-aware")
        return value


class IntakeProvenanceAttachmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str
    source_id: str
    observation_id: str
    source_ref_outcome: str
    observation_outcome: str
    source_acceptability: SourceAcceptability
    manual_review_required: bool = False
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class CanonicalFactProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    intent: CanonicalFactIntent
    fact_type: FactBindingType
    provenance_fact_type: ProvenanceFactType
    fact_id: str = Field(min_length=1, max_length=128)
    fact_field: str | None = Field(default=None, min_length=1, max_length=128)
    normalized_payload: dict[str, Any]
    source_id: str = Field(min_length=1, max_length=64)
    observation_id: str = Field(min_length=1, max_length=64)

    @classmethod
    def from_intake(
        cls,
        *,
        raw_record_id: str,
        intent: CanonicalFactIntent,
        fact_id: str,
        normalized_payload: Mapping[str, Any],
        source_id: str,
        observation_id: str,
        fact_field: str | None = None,
    ) -> CanonicalFactProposal:
        payload = dict(normalized_payload)
        _assert_json_serializable(payload)
        return cls(
            raw_record_id=raw_record_id,
            intent=intent,
            fact_type=fact_binding_type_for_intent(intent),
            provenance_fact_type=provenance_fact_type_for_intent(intent),
            fact_id=fact_id,
            fact_field=fact_field,
            normalized_payload=payload,
            source_id=source_id,
            observation_id=observation_id,
        )


class ProposalReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProposalReviewStatus = ProposalReviewStatus.APPROVED_FOR_LINKING
    reviewer_note: str | None = Field(default=None, min_length=1, max_length=2048)
    override_manual_review: bool = False


class ProposalReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    proposed_fact_id: str = Field(min_length=1, max_length=128)
    fact_type: FactBindingType
    approval_status: ProposalReviewStatus
    reviewer_note: str | None = Field(default=None, max_length=2048)
    diagnostics: tuple[str, ...] = Field(default_factory=tuple)
    source_id: str | None = Field(default=None, min_length=1, max_length=64)
    observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    fact_source_link_id: str | None = Field(default=None, min_length=1, max_length=128)
    fact_source_link_outcome: str | None = None
    manual_review_required: bool = False
    canonical_domain_mutated: bool = False


class CanonicalWriteDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    field_name: str | None = Field(default=None, min_length=1, max_length=128)


class CanonicalWriteOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_type: CanonicalWriteOperationType
    target_entity_type: str = Field(min_length=1, max_length=128)
    target_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    proposed_field_changes: dict[str, Any] = Field(default_factory=dict)
    value_statuses: dict[str, str] = Field(default_factory=dict)
    provenance_link_id: str | None = Field(default=None, min_length=1, max_length=128)
    confidence: Confidence = Confidence.UNKNOWN
    observation_status: ObservationStatus = ObservationStatus.UNKNOWN
    diagnostics: tuple[CanonicalWriteDiagnostic, ...] = Field(default_factory=tuple)
    manual_review_required: bool = False


class CanonicalWritePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    plan_id: str = Field(min_length=1, max_length=128)
    proposal_fact_intent: CanonicalFactIntent
    proposed_fact_id: str = Field(min_length=1, max_length=128)
    fact_type: FactBindingType
    status: CanonicalWritePlanStatus
    target_entity_type: str = Field(min_length=1, max_length=128)
    target_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    operations: tuple[CanonicalWriteOperation, ...] = Field(default_factory=tuple)
    provenance_link_id: str | None = Field(default=None, min_length=1, max_length=128)
    confidence: Confidence = Confidence.UNKNOWN
    observation_status: ObservationStatus = ObservationStatus.UNKNOWN
    diagnostics: tuple[CanonicalWriteDiagnostic, ...] = Field(default_factory=tuple)
    manual_review_required: bool = False
    dry_run: Literal[True] = True


class CanonicalWriteExecutionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1, max_length=128)
    approved: bool
    operator_note: str | None = Field(default=None, min_length=1, max_length=2048)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("decided_at")
    @classmethod
    def _decision_timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execution decision timestamp must be timezone-aware")
        return value


class CanonicalWriteExecutionDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    field_name: str | None = Field(default=None, min_length=1, max_length=128)


class CanonicalWriteExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1, max_length=128)
    raw_record_id: str = Field(min_length=1, max_length=64)
    status: CanonicalWriteExecutionStatus
    target_entity_type: str = Field(min_length=1, max_length=128)
    target_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    operation_type: CanonicalWriteOperationType | None = None
    diagnostics: tuple[CanonicalWriteExecutionDiagnostic, ...] = Field(
        default_factory=tuple
    )
    fact_source_link_id: str | None = Field(default=None, min_length=1, max_length=128)
    canonical_domain_mutated: bool = False
    downstream_refresh_triggered: bool = False


class PostWriteRefreshDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    field_name: str | None = Field(default=None, min_length=1, max_length=128)


class PostWriteRefreshTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: PostWriteRefreshTargetType
    target_id: str | None = Field(default=None, min_length=1, max_length=128)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)
    dry_run: Literal[True] = True


class PostWriteRefreshPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    refresh_plan_id: str | None = Field(default=None, min_length=1, max_length=128)
    execution_plan_id: str = Field(min_length=1, max_length=128)
    raw_record_id: str = Field(min_length=1, max_length=64)
    changed_canonical_entity_type: str = Field(min_length=1, max_length=128)
    changed_canonical_entity_id: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    affected_region_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_company_ids: tuple[str, ...] = Field(default_factory=tuple)
    status: PostWriteRefreshPlanStatus
    refresh_targets: tuple[PostWriteRefreshTarget, ...] = Field(default_factory=tuple)
    diagnostics: tuple[PostWriteRefreshDiagnostic, ...] = Field(default_factory=tuple)
    dry_run: Literal[True] = True


class PostWriteRefreshExecutionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    refresh_plan_id: str = Field(min_length=1, max_length=128)
    approved: bool
    operator_note: str | None = Field(default=None, min_length=1, max_length=2048)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=2048)
    expected_target_count: int | None = Field(default=None, ge=0)

    @field_validator("decided_at")
    @classmethod
    def _refresh_decision_timestamp_must_be_aware(
        cls, value: datetime
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError("refresh execution decision timestamp must be timezone-aware")
        return value


class PostWriteRefreshExecutionDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    target_type: PostWriteRefreshTargetType | None = None
    target_id: str | None = Field(default=None, min_length=1, max_length=128)


class PostWriteRefreshTargetExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: PostWriteRefreshTargetType
    target_id: str | None = Field(default=None, min_length=1, max_length=128)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    status: PostWriteRefreshExecutionStatus
    action: str | None = Field(default=None, min_length=1, max_length=64)
    refreshed_artifact_id: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    diagnostics: tuple[PostWriteRefreshExecutionDiagnostic, ...] = Field(
        default_factory=tuple
    )


class PostWriteRefreshExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    refresh_plan_id: str = Field(min_length=1, max_length=128)
    execution_plan_id: str = Field(min_length=1, max_length=128)
    raw_record_id: str = Field(min_length=1, max_length=64)
    status: PostWriteRefreshExecutionStatus
    target_results: tuple[PostWriteRefreshTargetExecutionResult, ...] = Field(
        default_factory=tuple
    )
    diagnostics: tuple[PostWriteRefreshExecutionDiagnostic, ...] = Field(
        default_factory=tuple
    )
    scores_refreshed_count: int = 0
    outputs_refreshed_count: int = 0
    jobs_enqueued: bool = False
    schedules_created: bool = False
    external_data_collected: bool = False


class ManualIngestionRunDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    stage: str | None = Field(default=None, min_length=1, max_length=64)


class ManualIngestionRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manual_observation: dict[str, Any]
    mode: ManualIngestionRunMode = ManualIngestionRunMode.DRY_RUN_ONLY
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED
    source_id: str | None = Field(default=None, min_length=1, max_length=64)
    observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    review_decision: ProposalReviewDecision | None = None
    write_execution_decision: CanonicalWriteExecutionDecision | None = None
    refresh_execution_decision: PostWriteRefreshExecutionDecision | None = None
    requested_fact_id: str | None = Field(default=None, min_length=1, max_length=128)


class ManualIngestionStepResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    stage: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=64)
    diagnostics: tuple[ManualIngestionRunDiagnostic, ...] = Field(default_factory=tuple)
    payload: Any | None = None


class ManualIngestionRunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    mode: ManualIngestionRunMode
    status: ManualIngestionRunStatus
    adapter_result: Any | None = None
    raw_records_created: tuple[str, ...] = Field(default_factory=tuple)
    normalization_result: Any | None = None
    provenance_attachment_result: IntakeProvenanceAttachmentResult | None = None
    canonical_proposal: CanonicalFactProposal | None = None
    proposal_review_result: ProposalReviewResult | None = None
    write_plan: CanonicalWritePlan | None = None
    write_execution_result: CanonicalWriteExecutionResult | None = None
    refresh_plan: PostWriteRefreshPlan | None = None
    refresh_execution_result: PostWriteRefreshExecutionResult | None = None
    steps: tuple[ManualIngestionStepResult, ...] = Field(default_factory=tuple)
    diagnostics: tuple[ManualIngestionRunDiagnostic, ...] = Field(default_factory=tuple)


def _assert_json_serializable(value: Mapping[str, Any]) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON-serializable") from exc
