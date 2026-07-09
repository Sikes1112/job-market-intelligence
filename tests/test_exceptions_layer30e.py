from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.config.settings import Settings
from backend.trust.exceptions import (
    ExceptionWorkflowService,
    exception_case_payload,
)
from backend.trust.models import AutomatedRecheckJob, ExceptionCase
from backend.trust.recheck import AutomatedRecheckService
from backend.trust.report_schemas import UserReportCreate
from backend.trust.reports import UserReportService
from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    AutomatedRecheckPriority,
    AutomatedRecheckTriggerType,
    ExceptionCaseStatus,
    ExceptionCaseType,
    ExceptionSeverity,
    PublicExceptionStatus,
    RankingInfluenceDecision,
    RiskLevel,
    RiskRoutingDecisionResult,
    RoutingOutcome,
    TrustAssessmentSubjectType,
    TrustTier,
    UserReportSeverity,
    UserReportType,
)

NOW = datetime(2026, 7, 8, 12, tzinfo=UTC)


def test_normal_report_does_not_create_exception_case(session: Session) -> None:
    result = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_normal_report",
            report_type=UserReportType.OUTDATED,
            severity=UserReportSeverity.MEDIUM,
        )
    )

    assert session.query(ExceptionCase).count() == 0
    assert result.status.exception_status is None


def test_critical_spam_report_creates_rare_exception_case(session: Session) -> None:
    result = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_spam_report",
            report_type=UserReportType.SPAM,
            severity=UserReportSeverity.CRITICAL,
        )
    )

    row = session.query(ExceptionCase).one()
    assert row.exception_type == ExceptionCaseType.FRAUD_SPAM.value
    assert row.status == ExceptionCaseStatus.BLOCKED.value
    assert row.severity == ExceptionSeverity.CRITICAL.value
    assert result.status.exception_status is not None
    assert result.status.exception_status.public_safe_status is PublicExceptionStatus.BLOCKED
    assert "approval" not in row.summary.lower()


def test_suspicious_ranking_report_waits_for_unresolved_or_critical_signal(
    session: Session,
) -> None:
    UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_suspicious",
            report_type=UserReportType.SUSPICIOUS_RANKING,
            severity=UserReportSeverity.HIGH,
        )
    )
    assert session.query(ExceptionCase).count() == 0

    UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_suspicious_critical",
            report_type=UserReportType.SUSPICIOUS_RANKING,
            severity=UserReportSeverity.CRITICAL,
        )
    )

    row = session.query(ExceptionCase).one()
    assert row.exception_type == ExceptionCaseType.SUSPICIOUS_RANKING.value


def test_failed_high_risk_recheck_creates_exception_case(session: Session) -> None:
    report = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.COMPANY_FACT,
            subject_id="company_fact_missing",
            report_type=UserReportType.SUSPICIOUS_RANKING,
            severity=UserReportSeverity.HIGH,
        )
    )
    assert report.recheck_job is not None

    result = AutomatedRecheckService(session, clock=lambda: NOW).run_recheck_job(
        report.recheck_job.automated_recheck_job_id
    )

    assert result.job.status is AutomatedRecheckJobStatus.ESCALATED_EXCEPTION
    row = session.query(ExceptionCase).one()
    assert row.exception_type == ExceptionCaseType.REPEATED_FAILED_RECHECK.value
    assert row.related_recheck_job_id == report.recheck_job.automated_recheck_job_id


def test_unresolved_conflict_after_recheck_creates_exception_case(
    session: Session,
) -> None:
    job = AutomatedRecheckJob(
        automated_recheck_job_id="recheck_conflict_unresolved",
        subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT.value,
        subject_id="candidate_conflict",
        trigger_type=AutomatedRecheckTriggerType.CONFLICT_DETECTED.value,
        trigger_source="test",
        status=AutomatedRecheckJobStatus.COMPLETED.value,
        priority=AutomatedRecheckPriority.HIGH.value,
        reason_codes_json=["reported_duplicate"],
        outcome=AutomatedRecheckOutcome.NO_CHANGE.value,
        attempts=1,
        max_attempts=3,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    session.flush()

    row = ExceptionWorkflowService(
        session,
        clock=lambda: NOW,
    ).maybe_create_exception_from_recheck(job)

    assert row is not None
    assert row.exception_type == ExceptionCaseType.UNRESOLVED_CONFLICT.value


def test_critical_risk_decision_creates_single_open_exception_case(
    session: Session,
) -> None:
    decision = RiskRoutingDecisionResult(
        subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
        subject_id="opp_critical_risk",
        trust_tier=TrustTier.BLOCKED,
        risk_level=RiskLevel.CRITICAL,
        routing_outcome=RoutingOutcome.BLOCKED,
        ranking_influence_decision=RankingInfluenceDecision.DENIED,
        ranking_influence_allowed=False,
        ranking_influence_reason="Blocked by deterministic risk routing.",
        decided_at=NOW,
    )

    service = ExceptionWorkflowService(session, clock=lambda: NOW)
    first = service.maybe_create_exception_from_risk_decision(decision)
    second = service.maybe_create_exception_from_risk_decision(decision)

    assert first is not None
    assert second is not None
    assert first.exception_case_id == second.exception_case_id
    assert session.query(ExceptionCase).count() == 1


def test_public_exception_status_redacts_internal_fields(session: Session) -> None:
    result = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_internal_redaction",
            report_type=UserReportType.SPAM,
            severity=UserReportSeverity.CRITICAL,
        )
    )
    row = session.query(ExceptionCase).one()
    row.internal_notes = "Internal legal notes and reviewer identity."
    session.flush()

    status = ExceptionWorkflowService(session).get_exception_status_for_subject(
        subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
        subject_id="opp_internal_redaction",
    )

    assert result.status.exception_status is not None
    serialized_status = status.model_dump_json()
    assert "Internal legal notes" not in serialized_status
    assert "reviewer" not in serialized_status.lower()
    assert "internal_notes" not in serialized_status
    assert "internal_notes" in exception_case_payload(row).model_dump()


def test_exception_subject_status_api_is_public_safe(api_client: TestClient) -> None:
    response = api_client.get(
        "/exceptions/subject-status",
        params={"subject_type": "opportunity", "subject_id": "none"},
    )
    protected = api_client.get("/exceptions")

    assert response.status_code == 200
    assert response.json()["data"]["public_safe_status"] == "no_exception"
    assert "internal_notes" not in response.text
    assert protected.status_code == 401


def test_public_demo_can_read_safe_status_but_cannot_mutate_exceptions(
    session: Session,
) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///explicit-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    status = client.get(
        "/exceptions/subject-status",
        params={"subject_type": "opportunity", "subject_id": "demo"},
    )
    listing = client.get("/exceptions")
    update = client.patch(
        "/exceptions/exception_missing/status",
        json={"status": "closed"},
    )

    assert status.status_code == 200
    assert status.json()["data"]["public_safe_status"] == "no_exception"
    assert listing.status_code == 403
    assert update.status_code == 403
    assert session.query(ExceptionCase).count() == 0
