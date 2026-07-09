"""Layer 30D user report and automated recheck API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    AutomatedRecheckPriority,
    AutomatedRecheckTriggerType,
    ReportRecheckStatus,
    TrustAssessmentSubjectType,
    UserReportSeverity,
    UserReportStatus,
    UserReportType,
)


class _ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UserReportCreate(_ReportModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str = Field(min_length=1, max_length=128)
    report_type: UserReportType
    report_reason: str | None = Field(default=None, max_length=2048)
    severity: UserReportSeverity = UserReportSeverity.MEDIUM
    reporter_session_id: str | None = Field(default=None, max_length=128)
    source_surface: str | None = Field(default=None, max_length=128)

    @field_validator("report_reason", "reporter_session_id", "source_surface")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UserReportPayload(_ReportModel):
    user_report_id: str
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    report_type: UserReportType
    report_reason: str | None = None
    reporter_user_id: str | None = None
    reporter_session_id: str | None = None
    severity: UserReportSeverity
    status: UserReportStatus
    source_surface: str | None = None
    related_trust_assessment_id: str | None = None
    related_risk_routing_decision_id: str | None = None
    created_recheck_job_id: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class AutomatedRecheckJobPayload(_ReportModel):
    automated_recheck_job_id: str
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    trigger_type: AutomatedRecheckTriggerType
    trigger_source: str
    status: AutomatedRecheckJobStatus
    priority: AutomatedRecheckPriority
    reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    related_user_report_id: str | None = None
    related_trust_assessment_id: str | None = None
    related_risk_routing_decision_id: str | None = None
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    outcome: AutomatedRecheckOutcome | None = None
    outcome_reason: str | None = None
    attempts: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class UserReportSubmissionResult(_ReportModel):
    report: UserReportPayload
    recheck_job: AutomatedRecheckJobPayload | None = None
    status: ReportRecheckStatus
    message: str


class RecheckRunResult(_ReportModel):
    job: AutomatedRecheckJobPayload
    status: ReportRecheckStatus
    message: str
