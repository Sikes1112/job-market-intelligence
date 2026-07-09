"""Layer 30E rare exception workflow.

Exception cases are deterministic signals for unresolved serious trust/risk
conditions. They are not normal approval or moderation records.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.trust.exception_schemas import ExceptionCasePayload, ExceptionCaseStatusUpdate
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    UserReport,
)
from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    AutomatedRecheckPriority,
    AutomatedRecheckTriggerType,
    ExceptionCaseStatus,
    ExceptionCaseType,
    ExceptionResolutionCode,
    ExceptionSeverity,
    ExceptionSubjectStatus,
    PublicExceptionStatus,
    RiskLevel,
    RiskRoutingDecisionResult,
    RoutingOutcome,
    TrustAssessmentSubjectType,
    UserReportSeverity,
    UserReportStatus,
    UserReportType,
)

OPEN_EXCEPTION_STATUSES = frozenset(
    {
        ExceptionCaseStatus.OPEN.value,
        ExceptionCaseStatus.AUTO_RECHECK_PENDING.value,
        ExceptionCaseStatus.WAITING_FOR_PARTNER_EVIDENCE.value,
        ExceptionCaseStatus.QUARANTINED.value,
        ExceptionCaseStatus.BLOCKED.value,
        ExceptionCaseStatus.REQUIRES_HUMAN_EXCEPTION.value,
    }
)


class ExceptionCaseNotFound(Exception):
    pass


class ExceptionCaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_case(self, row: ExceptionCase) -> ExceptionCase:
        self._session.add(row)
        return row

    def get_case(self, exception_case_id: str) -> ExceptionCase | None:
        return self._session.get(ExceptionCase, exception_case_id)

    def open_case_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
        exception_type: ExceptionCaseType,
    ) -> ExceptionCase | None:
        subject_value = _subject_value(subject_type)
        return self._session.execute(
            select(ExceptionCase)
            .where(
                ExceptionCase.subject_type == subject_value,
                ExceptionCase.subject_id == subject_id,
                ExceptionCase.exception_type == exception_type.value,
                ExceptionCase.status.in_(OPEN_EXCEPTION_STATUSES),
            )
            .order_by(ExceptionCase.created_at.desc(), ExceptionCase.exception_case_id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def latest_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
    ) -> ExceptionCase | None:
        subject_value = _subject_value(subject_type)
        return self._session.execute(
            select(ExceptionCase)
            .where(
                ExceptionCase.subject_type == subject_value,
                ExceptionCase.subject_id == subject_id,
            )
            .order_by(ExceptionCase.created_at.desc(), ExceptionCase.exception_case_id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def list_cases(
        self,
        *,
        status: ExceptionCaseStatus | None = None,
        limit: int = 100,
    ) -> tuple[ExceptionCase, ...]:
        statement = select(ExceptionCase).order_by(
            ExceptionCase.created_at.desc(),
            ExceptionCase.exception_case_id.desc(),
        )
        if status is not None:
            statement = statement.where(ExceptionCase.status == status.value)
        rows = self._session.execute(statement.limit(limit)).scalars()
        return tuple(rows)


class ExceptionWorkflowService:
    """Create rare exception cases from unresolved deterministic signals."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))
        self._repo = ExceptionCaseRepository(session)

    def maybe_create_exception_from_report(
        self,
        report: UserReport,
        *,
        job: AutomatedRecheckJob | None = None,
    ) -> ExceptionCase | None:
        report_type = UserReportType(report.report_type)
        severity = UserReportSeverity(report.severity)

        rule = _report_exception_rule(
            report_type=report_type,
            severity=severity,
            repeated_serious_reports=self._serious_report_count(report) >= 3,
            report_reason=report.report_reason,
        )
        if rule is None:
            return None

        case = self._create_case(
            subject_type=TrustAssessmentSubjectType(report.subject_type),
            subject_id=report.subject_id,
            exception_type=rule.exception_type,
            status=rule.status,
            severity=rule.severity,
            source="user_report",
            reason_codes=rule.reason_codes,
            summary=rule.summary,
            related_user_report_id=report.user_report_id,
            related_recheck_job_id=(
                job.automated_recheck_job_id if job is not None else None
            ),
        )
        report.status = UserReportStatus.ESCALATED_EXCEPTION.value
        report.updated_at = self._clock()
        if job is not None and rule.severity is ExceptionSeverity.CRITICAL:
            job.status = AutomatedRecheckJobStatus.ESCALATED_EXCEPTION.value
            job.updated_at = self._clock()
        self._session.flush()
        return case

    def maybe_create_exception_from_recheck(
        self,
        job: AutomatedRecheckJob,
    ) -> ExceptionCase | None:
        rule = _recheck_exception_rule(job)
        if rule is None:
            return None
        case = self._create_case(
            subject_type=TrustAssessmentSubjectType(job.subject_type),
            subject_id=job.subject_id,
            exception_type=rule.exception_type,
            status=rule.status,
            severity=rule.severity,
            source="automated_recheck",
            reason_codes=rule.reason_codes,
            summary=rule.summary,
            related_user_report_id=job.related_user_report_id,
            related_recheck_job_id=job.automated_recheck_job_id,
            related_trust_assessment_id=job.related_trust_assessment_id,
            related_risk_routing_decision_id=job.related_risk_routing_decision_id,
        )
        job.status = AutomatedRecheckJobStatus.ESCALATED_EXCEPTION.value
        job.updated_at = self._clock()
        self._session.flush()
        return case

    def maybe_create_exception_from_risk_decision(
        self,
        decision: RiskRoutingDecisionResult | RiskRoutingDecision,
    ) -> ExceptionCase | None:
        normalized = _risk_decision_fields(decision)
        rule = _risk_exception_rule(
            risk_level=normalized.risk_level,
            routing_outcome=normalized.routing_outcome,
        )
        if rule is None:
            return None
        return self._create_case(
            subject_type=normalized.subject_type,
            subject_id=normalized.subject_id,
            exception_type=rule.exception_type,
            status=rule.status,
            severity=rule.severity,
            source="risk_routing_decision",
            reason_codes=rule.reason_codes,
            summary=rule.summary,
            related_risk_routing_decision_id=normalized.risk_routing_decision_id,
        )

    def get_exception_status_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType,
        subject_id: str,
    ) -> ExceptionSubjectStatus:
        row = self._repo.latest_for_subject(
            subject_type=subject_type,
            subject_id=subject_id,
        )
        if row is None:
            return ExceptionSubjectStatus(subject_type=subject_type, subject_id=subject_id)
        return public_exception_status_from_row(row)

    def update_exception_status(
        self,
        exception_case_id: str,
        update: ExceptionCaseStatusUpdate,
    ) -> ExceptionCase:
        row = self._repo.get_case(exception_case_id)
        if row is None:
            raise ExceptionCaseNotFound(exception_case_id)
        now = self._clock()
        row.status = update.status.value
        row.public_safe_status = (
            update.public_safe_status.value
            if update.public_safe_status is not None
            else _public_status_for_status(update.status).value
        )
        row.internal_notes = update.internal_notes
        row.assigned_owner = update.assigned_owner
        if update.resolution_code is not None:
            row.resolution_code = update.resolution_code.value
        if update.status in {ExceptionCaseStatus.RESOLVED_BY_SYSTEM, ExceptionCaseStatus.CLOSED}:
            row.resolved_at = now
        row.updated_at = now
        self._session.flush()
        return row

    def _serious_report_count(self, report: UserReport) -> int:
        rows = self._session.execute(
            select(func.count(UserReport.user_report_id)).where(
                UserReport.subject_type == report.subject_type,
                UserReport.subject_id == report.subject_id,
                UserReport.report_type.in_(
                    [
                        UserReportType.SPAM.value,
                        UserReportType.MISLEADING.value,
                    ]
                ),
                UserReport.severity.in_(
                    [
                        UserReportSeverity.HIGH.value,
                        UserReportSeverity.CRITICAL.value,
                    ]
                ),
            )
        )
        return int(rows.scalar_one())

    def _create_case(
        self,
        *,
        subject_type: TrustAssessmentSubjectType,
        subject_id: str,
        exception_type: ExceptionCaseType,
        status: ExceptionCaseStatus,
        severity: ExceptionSeverity,
        source: str,
        reason_codes: tuple[str, ...],
        summary: str,
        related_user_report_id: str | None = None,
        related_recheck_job_id: str | None = None,
        related_trust_assessment_id: str | None = None,
        related_risk_routing_decision_id: str | None = None,
    ) -> ExceptionCase:
        existing = self._repo.open_case_for_subject(
            subject_type=subject_type,
            subject_id=subject_id,
            exception_type=exception_type,
        )
        if existing is not None:
            return existing
        now = self._clock()
        public_status = _public_status_for_status(status)
        row = self._repo.add_case(
            ExceptionCase(
                exception_case_id=f"exception_{uuid4().hex}",
                subject_type=subject_type.value,
                subject_id=subject_id,
                exception_type=exception_type.value,
                status=status.value,
                severity=severity.value,
                source=source,
                reason_codes_json=list(dict.fromkeys(reason_codes)),
                summary=summary,
                related_user_report_id=related_user_report_id,
                related_recheck_job_id=related_recheck_job_id,
                related_trust_assessment_id=related_trust_assessment_id,
                related_risk_routing_decision_id=related_risk_routing_decision_id,
                public_safe_status=public_status.value,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.flush()
        return row


def exception_case_payload(row: ExceptionCase) -> ExceptionCasePayload:
    return ExceptionCasePayload(
        exception_case_id=row.exception_case_id,
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        exception_type=ExceptionCaseType(row.exception_type),
        status=ExceptionCaseStatus(row.status),
        severity=ExceptionSeverity(row.severity),
        source=row.source,
        reason_codes=tuple(str(item) for item in row.reason_codes_json),
        summary=row.summary,
        related_user_report_id=row.related_user_report_id,
        related_recheck_job_id=row.related_recheck_job_id,
        related_trust_assessment_id=row.related_trust_assessment_id,
        related_risk_routing_decision_id=row.related_risk_routing_decision_id,
        public_safe_status=(
            PublicExceptionStatus(row.public_safe_status)
            if row.public_safe_status is not None
            else None
        ),
        internal_notes=row.internal_notes,
        assigned_owner=row.assigned_owner,
        resolved_at=_aware(row.resolved_at),
        resolution_code=(
            ExceptionResolutionCode(row.resolution_code)
            if row.resolution_code is not None
            else None
        ),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def public_exception_status_from_row(row: ExceptionCase) -> ExceptionSubjectStatus:
    status = ExceptionCaseStatus(row.status)
    public_status = (
        PublicExceptionStatus(row.public_safe_status)
        if row.public_safe_status is not None
        else _public_status_for_status(status)
    )
    return ExceptionSubjectStatus(
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        has_open_exception=row.status in OPEN_EXCEPTION_STATUSES,
        exception_case_id=row.exception_case_id,
        exception_type=ExceptionCaseType(row.exception_type),
        status=status,
        severity=ExceptionSeverity(row.severity),
        public_safe_status=public_status,
        label=PUBLIC_EXCEPTION_LABELS[public_status],
        message=PUBLIC_EXCEPTION_MESSAGES[public_status],
        updated_at=_aware(row.updated_at),
        resolved_at=_aware(row.resolved_at),
    )


class _ExceptionRule:
    def __init__(
        self,
        *,
        exception_type: ExceptionCaseType,
        status: ExceptionCaseStatus,
        severity: ExceptionSeverity,
        reason_codes: tuple[str, ...],
        summary: str,
    ) -> None:
        self.exception_type = exception_type
        self.status = status
        self.severity = severity
        self.reason_codes = reason_codes
        self.summary = summary


def _report_exception_rule(
    *,
    report_type: UserReportType,
    severity: UserReportSeverity,
    repeated_serious_reports: bool,
    report_reason: str | None,
) -> _ExceptionRule | None:
    if report_type is UserReportType.SPAM and severity is UserReportSeverity.CRITICAL:
        return _rule(
            ExceptionCaseType.FRAUD_SPAM,
            ExceptionSeverity.CRITICAL,
            ("critical_spam_report",),
            "Critical spam report requires rare exception handling.",
        )
    if report_type is UserReportType.MISLEADING and severity is UserReportSeverity.CRITICAL:
        return _rule(
            ExceptionCaseType.ABUSE_REPORT,
            ExceptionSeverity.CRITICAL,
            ("critical_misleading_report",),
            "Critical misleading report requires rare exception handling.",
        )
    if report_type is UserReportType.SUSPICIOUS_RANKING and severity is UserReportSeverity.CRITICAL:
        return _rule(
            ExceptionCaseType.SUSPICIOUS_RANKING,
            ExceptionSeverity.CRITICAL,
            ("critical_suspicious_ranking_report",),
            "Critical suspicious ranking report requires rare exception handling.",
        )
    if repeated_serious_reports:
        return _rule(
            ExceptionCaseType.FRAUD_SPAM,
            ExceptionSeverity.HIGH,
            ("repeated_serious_reports",),
            "Repeated serious user reports require rare exception handling.",
        )
    if severity is UserReportSeverity.CRITICAL and _mentions_legal_or_abuse(report_reason):
        return _rule(
            ExceptionCaseType.LEGAL_RISK,
            ExceptionSeverity.CRITICAL,
            ("critical_legal_or_abuse_signal",),
            "Critical legal or abuse signal requires rare exception handling.",
        )
    return None


def _recheck_exception_rule(job: AutomatedRecheckJob) -> _ExceptionRule | None:
    priority = AutomatedRecheckPriority(job.priority)
    status = AutomatedRecheckJobStatus(job.status)
    trigger = AutomatedRecheckTriggerType(job.trigger_type)
    outcome = (
        AutomatedRecheckOutcome(job.outcome) if job.outcome is not None else None
    )
    high_priority = priority in {
        AutomatedRecheckPriority.HIGH,
        AutomatedRecheckPriority.CRITICAL,
    }
    if (
        status in {AutomatedRecheckJobStatus.FAILED, AutomatedRecheckJobStatus.SKIPPED}
        and high_priority
    ):
        return _rule(
            ExceptionCaseType.REPEATED_FAILED_RECHECK,
            _severity_for_priority(priority),
            ("failed_or_skipped_high_risk_recheck",),
            "High-risk automated recheck failed or skipped.",
        )
    if (
        trigger is AutomatedRecheckTriggerType.CONFLICT_DETECTED
        and high_priority
        and outcome in {
            AutomatedRecheckOutcome.FAILED,
            AutomatedRecheckOutcome.NO_CHANGE,
            AutomatedRecheckOutcome.NEEDS_EXCEPTION,
        }
    ):
        return _rule(
            ExceptionCaseType.UNRESOLVED_CONFLICT,
            ExceptionSeverity.HIGH,
            ("unresolved_conflict_after_recheck",),
            "Conflict signal remains unresolved after automated recheck.",
        )
    if trigger is AutomatedRecheckTriggerType.SUSPICIOUS_RANKING and (
        priority is AutomatedRecheckPriority.CRITICAL
        or outcome in {
            AutomatedRecheckOutcome.FAILED,
            AutomatedRecheckOutcome.NO_CHANGE,
            AutomatedRecheckOutcome.NEEDS_EXCEPTION,
        }
    ):
        return _rule(
            ExceptionCaseType.SUSPICIOUS_RANKING,
            _severity_for_priority(priority),
            ("suspicious_ranking_unresolved_after_recheck",),
            "Suspicious ranking signal remains unresolved after automated recheck.",
        )
    if outcome in {
        AutomatedRecheckOutcome.BLOCKED,
        AutomatedRecheckOutcome.QUARANTINED,
        AutomatedRecheckOutcome.NEEDS_EXCEPTION,
    } and high_priority:
        return _rule(
            ExceptionCaseType.BLOCKED_OR_QUARANTINED_CRITICAL,
            _severity_for_priority(priority),
            ("blocked_or_quarantined_after_recheck",),
            "Automated recheck produced a severe blocked or quarantined outcome.",
        )
    return None


class _RiskDecisionFields:
    def __init__(
        self,
        *,
        subject_type: TrustAssessmentSubjectType,
        subject_id: str,
        risk_level: RiskLevel,
        routing_outcome: RoutingOutcome,
        risk_routing_decision_id: str | None,
    ) -> None:
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.risk_level = risk_level
        self.routing_outcome = routing_outcome
        self.risk_routing_decision_id = risk_routing_decision_id


def _risk_decision_fields(
    decision: RiskRoutingDecisionResult | RiskRoutingDecision,
) -> _RiskDecisionFields:
    if isinstance(decision, RiskRoutingDecisionResult):
        return _RiskDecisionFields(
            subject_type=decision.subject_type,
            subject_id=decision.subject_id,
            risk_level=decision.risk_level,
            routing_outcome=decision.routing_outcome,
            risk_routing_decision_id=None,
        )
    return _RiskDecisionFields(
        subject_type=TrustAssessmentSubjectType(decision.subject_type),
        subject_id=decision.subject_id,
        risk_level=RiskLevel(decision.risk_level),
        routing_outcome=RoutingOutcome(decision.routing_outcome),
        risk_routing_decision_id=decision.risk_routing_decision_id,
    )


def _risk_exception_rule(
    *,
    risk_level: RiskLevel,
    routing_outcome: RoutingOutcome,
) -> _ExceptionRule | None:
    if routing_outcome is RoutingOutcome.ESCALATE_EXCEPTION:
        return _rule(
            ExceptionCaseType.RANKING_INFLUENCE_EXCEPTION,
            ExceptionSeverity.HIGH,
            ("risk_routing_escalate_exception",),
            "Risk routing requested rare exception handling.",
        )
    if risk_level is RiskLevel.CRITICAL or routing_outcome in {
        RoutingOutcome.BLOCKED,
        RoutingOutcome.QUARANTINE,
    }:
        return _rule(
            ExceptionCaseType.BLOCKED_OR_QUARANTINED_CRITICAL,
            ExceptionSeverity.CRITICAL,
            ("critical_risk_or_blocked_routing",),
            "Critical risk or blocked/quarantined routing requires exception tracking.",
        )
    return None


def _rule(
    exception_type: ExceptionCaseType,
    severity: ExceptionSeverity,
    reason_codes: tuple[str, ...],
    summary: str,
) -> _ExceptionRule:
    status = (
        ExceptionCaseStatus.BLOCKED
        if severity is ExceptionSeverity.CRITICAL
        else ExceptionCaseStatus.REQUIRES_HUMAN_EXCEPTION
    )
    return _ExceptionRule(
        exception_type=exception_type,
        status=status,
        severity=severity,
        reason_codes=reason_codes,
        summary=summary,
    )


def _public_status_for_status(status: ExceptionCaseStatus) -> PublicExceptionStatus:
    return {
        ExceptionCaseStatus.OPEN: PublicExceptionStatus.REQUIRES_EXCEPTION_HANDLING,
        ExceptionCaseStatus.AUTO_RECHECK_PENDING: PublicExceptionStatus.AUTOMATED_RECHECK_PENDING,
        ExceptionCaseStatus.WAITING_FOR_PARTNER_EVIDENCE: (
            PublicExceptionStatus.REQUIRES_EXCEPTION_HANDLING
        ),
        ExceptionCaseStatus.QUARANTINED: PublicExceptionStatus.QUARANTINED,
        ExceptionCaseStatus.BLOCKED: PublicExceptionStatus.BLOCKED,
        ExceptionCaseStatus.RESOLVED_BY_SYSTEM: PublicExceptionStatus.RESOLVED_BY_SYSTEM,
        ExceptionCaseStatus.REQUIRES_HUMAN_EXCEPTION: (
            PublicExceptionStatus.REQUIRES_EXCEPTION_HANDLING
        ),
        ExceptionCaseStatus.CLOSED: PublicExceptionStatus.CLOSED,
    }[status]


PUBLIC_EXCEPTION_LABELS: dict[PublicExceptionStatus, str] = {
    PublicExceptionStatus.NO_EXCEPTION: "No exception",
    PublicExceptionStatus.AUTOMATED_RECHECK_PENDING: "Automated recheck pending",
    PublicExceptionStatus.QUARANTINED: "Quarantined",
    PublicExceptionStatus.BLOCKED: "Blocked",
    PublicExceptionStatus.RESOLVED_BY_SYSTEM: "Resolved by system",
    PublicExceptionStatus.REQUIRES_EXCEPTION_HANDLING: "Requires exception handling",
    PublicExceptionStatus.CLOSED: "Closed",
}

PUBLIC_EXCEPTION_MESSAGES: dict[PublicExceptionStatus, str] = {
    PublicExceptionStatus.NO_EXCEPTION: "No rare exception case is open for this item.",
    PublicExceptionStatus.AUTOMATED_RECHECK_PENDING: (
        "Automated recheck is pending before this item can be relied on."
    ),
    PublicExceptionStatus.QUARANTINED: (
        "This item is quarantined because unresolved risk signals remain."
    ),
    PublicExceptionStatus.BLOCKED: (
        "This item is blocked because unresolved critical risk signals remain."
    ),
    PublicExceptionStatus.RESOLVED_BY_SYSTEM: (
        "The exception case was resolved by deterministic system signals."
    ),
    PublicExceptionStatus.REQUIRES_EXCEPTION_HANDLING: (
        "This rare unresolved case needs exception handling, not normal approval."
    ),
    PublicExceptionStatus.CLOSED: "The exception case is closed.",
}


def _mentions_legal_or_abuse(value: str | None) -> bool:
    if not value:
        return False
    text = value.casefold()
    return any(token in text for token in ("legal", "abuse", "harassment", "fraud"))


def _severity_for_priority(priority: AutomatedRecheckPriority) -> ExceptionSeverity:
    if priority is AutomatedRecheckPriority.CRITICAL:
        return ExceptionSeverity.CRITICAL
    return ExceptionSeverity.HIGH


def _subject_value(subject_type: TrustAssessmentSubjectType | str) -> str:
    return (
        subject_type.value
        if isinstance(subject_type, TrustAssessmentSubjectType)
        else subject_type
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
