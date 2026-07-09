"""Layer 30D append-only user report signals and recheck scheduling."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.trust.models import AutomatedRecheckJob, UserReport
from backend.trust.report_schemas import (
    AutomatedRecheckJobPayload,
    UserReportCreate,
    UserReportPayload,
    UserReportSubmissionResult,
)
from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    AutomatedRecheckPriority,
    AutomatedRecheckTriggerType,
    PublicExceptionStatus,
    ReportRecheckStatus,
    TrustAssessmentSubjectType,
    UserReportSeverity,
    UserReportStatus,
    UserReportType,
)

RECHECK_STATUS_LABELS: dict[AutomatedRecheckJobStatus, str] = {
    AutomatedRecheckJobStatus.QUEUED: "Recheck queued",
    AutomatedRecheckJobStatus.PENDING: "Recheck pending",
    AutomatedRecheckJobStatus.RUNNING: "Recheck running",
    AutomatedRecheckJobStatus.COMPLETED: "Recheck completed",
    AutomatedRecheckJobStatus.FAILED: "Recheck failed",
    AutomatedRecheckJobStatus.CANCELED: "Recheck canceled",
    AutomatedRecheckJobStatus.SKIPPED: "Recheck skipped",
    AutomatedRecheckJobStatus.ESCALATED_EXCEPTION: (
        "Escalated for exception handling"
    ),
}


class UserReportNotFound(Exception):
    pass


class AutomatedRecheckJobNotFound(Exception):
    pass


class UserReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_report(self, row: UserReport) -> UserReport:
        self._session.add(row)
        return row

    def get_report(self, report_id: str) -> UserReport | None:
        return self._session.get(UserReport, report_id)

    def latest_report_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
    ) -> UserReport | None:
        subject_value = _subject_value(subject_type)
        return self._session.execute(
            select(UserReport)
            .where(
                UserReport.subject_type == subject_value,
                UserReport.subject_id == subject_id,
            )
            .order_by(UserReport.created_at.desc(), UserReport.user_report_id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def list_reports_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
        limit: int = 100,
    ) -> tuple[UserReport, ...]:
        subject_value = _subject_value(subject_type)
        rows = self._session.execute(
            select(UserReport)
            .where(
                UserReport.subject_type == subject_value,
                UserReport.subject_id == subject_id,
            )
            .order_by(UserReport.created_at.desc(), UserReport.user_report_id.desc())
            .limit(limit)
        ).scalars()
        return tuple(rows)


class AutomatedRecheckRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_job(self, row: AutomatedRecheckJob) -> AutomatedRecheckJob:
        self._session.add(row)
        return row

    def get_job(self, job_id: str) -> AutomatedRecheckJob | None:
        return self._session.get(AutomatedRecheckJob, job_id)

    def latest_job_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
    ) -> AutomatedRecheckJob | None:
        subject_value = _subject_value(subject_type)
        return self._session.execute(
            select(AutomatedRecheckJob)
            .where(
                AutomatedRecheckJob.subject_type == subject_value,
                AutomatedRecheckJob.subject_id == subject_id,
            )
            .order_by(
                AutomatedRecheckJob.created_at.desc(),
                AutomatedRecheckJob.automated_recheck_job_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()


class UserReportService:
    """Create user report signals and schedule deterministic rechecks."""

    def __init__(
        self,
        session: Session,
        *,
        clock: callable | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))
        self._reports = UserReportRepository(session)
        self._rechecks = AutomatedRecheckRepository(session)

    def submit_report(
        self,
        request: UserReportCreate,
        *,
        reporter_user_id: str | None = None,
    ) -> UserReportSubmissionResult:
        now = self._clock()
        report_id = f"user_report_{uuid4().hex}"
        recheck_job_id = f"recheck_{uuid4().hex}"
        trigger_type, priority, reason_codes = _report_recheck_mapping(
            request.report_type,
            request.severity,
        )
        status = (
            UserReportStatus.ESCALATED_EXCEPTION
            if priority is AutomatedRecheckPriority.CRITICAL
            and request.report_type in {UserReportType.SPAM, UserReportType.MISLEADING}
            else UserReportStatus.QUEUED_FOR_RECHECK
        )
        report = self._reports.add_report(
            UserReport(
                user_report_id=report_id,
                subject_type=request.subject_type.value,
                subject_id=request.subject_id,
                report_type=request.report_type.value,
                report_reason=request.report_reason,
                reporter_user_id=reporter_user_id,
                reporter_session_id=request.reporter_session_id,
                severity=request.severity.value,
                status=status.value,
                source_surface=request.source_surface,
                created_recheck_job_id=recheck_job_id,
                created_at=now,
                updated_at=now,
            )
        )
        job = self._rechecks.add_job(
            AutomatedRecheckJob(
                automated_recheck_job_id=recheck_job_id,
                subject_type=request.subject_type.value,
                subject_id=request.subject_id,
                trigger_type=trigger_type.value,
                trigger_source="user_report",
                status=AutomatedRecheckJobStatus.QUEUED.value,
                priority=priority.value,
                reason_codes_json=reason_codes,
                related_user_report_id=report_id,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.flush()
        from backend.trust.exceptions import ExceptionWorkflowService

        ExceptionWorkflowService(
            self._session,
            clock=self._clock,
        ).maybe_create_exception_from_report(report, job=job)
        summary = report_recheck_status_from_rows(report=report, job=job)
        return UserReportSubmissionResult(
            report=user_report_payload(report),
            recheck_job=automated_recheck_job_payload(job),
            status=summary,
            message=(
                "Report received. It may trigger an automated deterministic "
                "recheck; it does not directly change rankings or source data."
            ),
        )

    def report_status(self, report_id: str) -> UserReportSubmissionResult:
        report = self._reports.get_report(report_id)
        if report is None:
            raise UserReportNotFound(report_id)
        job = (
            self._rechecks.get_job(report.created_recheck_job_id)
            if report.created_recheck_job_id is not None
            else None
        )
        return UserReportSubmissionResult(
            report=user_report_payload(report),
            recheck_job=(
                automated_recheck_job_payload(job) if job is not None else None
            ),
            status=report_recheck_status_from_rows(report=report, job=job),
            message="Report status is based on append-only report and recheck signals.",
        )


def latest_report_recheck_status(
    session: Session,
    *,
    subject_type: TrustAssessmentSubjectType,
    subject_id: str,
) -> ReportRecheckStatus | None:
    reports = UserReportRepository(session)
    rechecks = AutomatedRecheckRepository(session)
    report = reports.latest_report_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
    )
    job = rechecks.latest_job_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if report is None and job is None:
        return None
    return report_recheck_status_from_rows(
        report=report,
        job=job,
        subject_type=subject_type,
        subject_id=subject_id,
    )


def report_recheck_status_from_rows(
    *,
    report: UserReport | None,
    job: AutomatedRecheckJob | None,
    subject_type: TrustAssessmentSubjectType | None = None,
    subject_id: str | None = None,
) -> ReportRecheckStatus:
    resolved_subject_type = (
        TrustAssessmentSubjectType(report.subject_type)
        if report is not None
        else TrustAssessmentSubjectType(job.subject_type)
    )
    resolved_subject_id = (
        report.subject_id if report is not None else str(job.subject_id)
    )
    if subject_type is not None:
        resolved_subject_type = subject_type
    if subject_id is not None:
        resolved_subject_id = subject_id
    status = AutomatedRecheckJobStatus(job.status) if job is not None else None
    return ReportRecheckStatus(
        subject_type=resolved_subject_type,
        subject_id=resolved_subject_id,
        latest_report_status=(
            UserReportStatus(report.status) if report is not None else None
        ),
        latest_report_type=(
            UserReportType(report.report_type) if report is not None else None
        ),
        latest_report_severity=(
            UserReportSeverity(report.severity) if report is not None else None
        ),
        latest_reported_at=_aware(report.created_at) if report is not None else None,
        active_recheck_job_id=job.automated_recheck_job_id if job is not None else None,
        recheck_status=status,
        recheck_priority=(
            AutomatedRecheckPriority(job.priority) if job is not None else None
        ),
        recheck_outcome=(
            AutomatedRecheckOutcome(job.outcome)
            if job is not None and job.outcome is not None
            else None
        ),
        recheck_status_label=RECHECK_STATUS_LABELS.get(status) if status else None,
        exception_status=_exception_status_for_subject(
            report=report,
            job=job,
            subject_type=resolved_subject_type,
            subject_id=resolved_subject_id,
        ),
        message=_status_message(report=report, job=job),
    )


def user_report_payload(row: UserReport) -> UserReportPayload:
    return UserReportPayload(
        user_report_id=row.user_report_id,
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        report_type=UserReportType(row.report_type),
        report_reason=row.report_reason,
        reporter_user_id=row.reporter_user_id,
        reporter_session_id=row.reporter_session_id,
        severity=UserReportSeverity(row.severity),
        status=UserReportStatus(row.status),
        source_surface=row.source_surface,
        related_trust_assessment_id=row.related_trust_assessment_id,
        related_risk_routing_decision_id=row.related_risk_routing_decision_id,
        created_recheck_job_id=row.created_recheck_job_id,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
        resolved_at=_aware(row.resolved_at),
    )


def automated_recheck_job_payload(
    row: AutomatedRecheckJob,
) -> AutomatedRecheckJobPayload:
    return AutomatedRecheckJobPayload(
        automated_recheck_job_id=row.automated_recheck_job_id,
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        trigger_type=AutomatedRecheckTriggerType(row.trigger_type),
        trigger_source=row.trigger_source,
        status=AutomatedRecheckJobStatus(row.status),
        priority=AutomatedRecheckPriority(row.priority),
        reason_codes=tuple(str(item) for item in row.reason_codes_json),
        related_user_report_id=row.related_user_report_id,
        related_trust_assessment_id=row.related_trust_assessment_id,
        related_risk_routing_decision_id=row.related_risk_routing_decision_id,
        scheduled_for=_aware(row.scheduled_for),
        started_at=_aware(row.started_at),
        completed_at=_aware(row.completed_at),
        outcome=(
            AutomatedRecheckOutcome(row.outcome)
            if row.outcome is not None
            else None
        ),
        outcome_reason=row.outcome_reason,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        last_error=row.last_error,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _report_recheck_mapping(
    report_type: UserReportType,
    severity: UserReportSeverity,
) -> tuple[AutomatedRecheckTriggerType, AutomatedRecheckPriority, list[str]]:
    default = {
        UserReportType.OUTDATED: (
            AutomatedRecheckTriggerType.STALE_SOURCE,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_outdated"],
        ),
        UserReportType.INCORRECT: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_incorrect"],
        ),
        UserReportType.DUPLICATE: (
            AutomatedRecheckTriggerType.CONFLICT_DETECTED,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_duplicate"],
        ),
        UserReportType.SPAM: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.CRITICAL,
            ["reported_spam", "future_exception_signal"],
        ),
        UserReportType.MISLEADING: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.HIGH,
            ["reported_misleading"],
        ),
        UserReportType.EXPIRED_OPPORTUNITY: (
            AutomatedRecheckTriggerType.EXPIRED_OPPORTUNITY,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_expired_opportunity"],
        ),
        UserReportType.WRONG_COMPANY: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_wrong_company"],
        ),
        UserReportType.WRONG_REGION: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.MEDIUM,
            ["reported_wrong_region"],
        ),
        UserReportType.SUSPICIOUS_RANKING: (
            AutomatedRecheckTriggerType.SUSPICIOUS_RANKING,
            AutomatedRecheckPriority.HIGH,
            ["reported_suspicious_ranking"],
        ),
        UserReportType.OTHER: (
            AutomatedRecheckTriggerType.USER_REPORT,
            AutomatedRecheckPriority.LOW,
            ["reported_other"],
        ),
    }[report_type]
    trigger, default_priority, codes = default
    return trigger, _max_priority(default_priority, severity), codes


def _max_priority(
    default: AutomatedRecheckPriority,
    severity: UserReportSeverity,
) -> AutomatedRecheckPriority:
    order = {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3,
    }
    severity_priority = AutomatedRecheckPriority(severity.value)
    return (
        severity_priority
        if order[severity_priority.value] > order[default.value]
        else default
    )


def _status_message(
    *,
    report: UserReport | None,
    job: AutomatedRecheckJob | None,
) -> str:
    if job is None:
        return "Report received. No automated recheck is currently attached."
    status = AutomatedRecheckJobStatus(job.status)
    if status is AutomatedRecheckJobStatus.COMPLETED:
        if job.outcome == AutomatedRecheckOutcome.NO_CHANGE.value:
            return "Recheck completed with no canonical or ranking change."
        return "Recheck completed through deterministic trust/risk services."
    if status is AutomatedRecheckJobStatus.SKIPPED:
        return "Recheck skipped safely for this subject."
    if status is AutomatedRecheckJobStatus.ESCALATED_EXCEPTION:
        return "Escalated for future exception handling, not normal approval."
    if report is not None:
        return "Report received. Automated recheck is queued."
    return "Automated recheck status is available."


def _subject_value(subject_type: TrustAssessmentSubjectType | str) -> str:
    return (
        subject_type.value
        if isinstance(subject_type, TrustAssessmentSubjectType)
        else subject_type
    )


def _exception_status_for_subject(
    *,
    report: UserReport | None,
    job: AutomatedRecheckJob | None,
    subject_type: TrustAssessmentSubjectType,
    subject_id: str,
):
    session = None
    if report is not None:
        session = report._sa_instance_state.session  # noqa: SLF001
    if session is None and job is not None:
        session = job._sa_instance_state.session  # noqa: SLF001
    if session is None:
        return None
    from backend.trust.exceptions import ExceptionWorkflowService

    status = ExceptionWorkflowService(session).get_exception_status_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if status.public_safe_status is PublicExceptionStatus.NO_EXCEPTION:
        return None
    return status


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
