"""Layer 30E exception workflow API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.trust.schemas import (
    ExceptionCaseStatus,
    ExceptionCaseType,
    ExceptionResolutionCode,
    ExceptionSeverity,
    ExceptionSubjectStatus,
    PublicExceptionStatus,
    TrustAssessmentSubjectType,
)


class _ExceptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExceptionCasePayload(_ExceptionModel):
    exception_case_id: str
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    exception_type: ExceptionCaseType
    status: ExceptionCaseStatus
    severity: ExceptionSeverity
    source: str
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    summary: str
    related_user_report_id: str | None = None
    related_recheck_job_id: str | None = None
    related_trust_assessment_id: str | None = None
    related_risk_routing_decision_id: str | None = None
    public_safe_status: PublicExceptionStatus | None = None
    internal_notes: str | None = None
    assigned_owner: str | None = None
    resolved_at: datetime | None = None
    resolution_code: ExceptionResolutionCode | None = None
    created_at: datetime
    updated_at: datetime


class ExceptionCaseStatusUpdate(_ExceptionModel):
    status: ExceptionCaseStatus
    resolution_code: ExceptionResolutionCode | None = None
    public_safe_status: PublicExceptionStatus | None = None
    internal_notes: str | None = Field(default=None, max_length=2048)
    assigned_owner: str | None = Field(default=None, max_length=128)


class ExceptionSubjectStatusPayload(_ExceptionModel):
    status: ExceptionSubjectStatus
