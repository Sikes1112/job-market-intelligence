"""Audit job handler tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.audit.service import AuditService
from backend.companies.models import Company
from backend.orchestration.jobs.audit import handle_audit
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.orchestration.workers.registry import default_registry
from backend.outputs.models import OutputMetadata


def _service(session: Session) -> AuditService:
    return AuditService(
        session=session, clock=lambda: datetime(2026, 5, 7, 12, tzinfo=UTC)
    )


def _request(scope: dict | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_audit_001",
        job_type=JobType.AUDIT,
        trigger_type=TriggerType.SCHEDULED,
        requested_by="system",
        priority=Priority.NORMAL,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope=scope or {},
        inputs={},
        options={},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


# --- happy path -----------------------------------------------------------


def test_handler_succeeds_on_clean_dataset(session: Session) -> None:
    response = handle_audit(
        _request(),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.error_code is None
    assert response.outputs["overall_status"] == "passed"
    assert response.outputs["audit_report"]["findings"] == []


def test_handler_returns_warnings_when_findings_exist(session: Session) -> None:
    session.add(
        Company(
            company_id="comp_a",
            company_name="A",
            normalized_company_name="a",
            eligibility_status="override_included",
            eligibility_override_flag=True,
            eligibility_override_reason=None,
        )
    )
    session.flush()

    response = handle_audit(
        _request(),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED_WITH_WARNINGS
    assert len(response.warnings) >= 1
    assert response.outputs["audit_report"]["overall_status"] in {
        "warning",
        "failed",
        "critical",
    }


def test_handler_critical_finding_still_succeeds_with_warnings(session: Session) -> None:
    """Critical audit findings don't fail the audit *job* — the job
    succeeded; the findings are the deliverable."""
    session.add(
        OutputMetadata(
            output_id="o_personalized",
            output_type="personalized_output",
            subject_id="user_xyz",
        )
    )
    session.flush()
    response = handle_audit(
        _request(),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED_WITH_WARNINGS
    assert response.outputs["overall_status"] == "critical"


# --- input validation -----------------------------------------------------


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    response = handle_audit(
        _request(job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_malformed_scope(session: Session) -> None:
    response = handle_audit(
        _request(scope={"region_ids": ["greater_boston", ""]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_accepts_optional_audit_scope(session: Session) -> None:
    response = handle_audit(
        _request(scope={"region_ids": ["greater_boston"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED


def test_handler_ignores_unknown_scope_keys(session: Session) -> None:
    """Slice 4 JobRequest.scope is a free-form dict; the audit handler
    extracts only audit-specific keys and ignores the rest."""
    response = handle_audit(
        _request(
            scope={"region_ids": ["greater_boston"], "unrelated": "ok"}
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED


# --- envelope correctness ------------------------------------------------


def test_handler_returns_valid_envelope(session: Session) -> None:
    response = handle_audit(
        _request(),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.completed_at >= response.started_at
    assert response.error_code is None


def test_handler_does_not_enqueue_or_emit_events(session: Session) -> None:
    """Sanity: the handler returns a JobResponse synchronously and does
    not interact with queue or event router. We can only check that no
    side effects occur on the OutputMetadata or jobs tables beyond the
    handler's normal return."""
    pre_outputs = session.query(OutputMetadata).count()
    handle_audit(
        _request(),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert session.query(OutputMetadata).count() == pre_outputs


# --- registry behavior ---------------------------------------------------


def test_audit_handler_is_not_registered_in_default_runtime() -> None:
    """Per the slice prompt's conservative-default guidance, JobType.AUDIT
    is intentionally not registered with the Slice 14 default registry.
    Future slices may register it once event-driven audits are needed."""
    registry = default_registry()
    assert not registry.has(JobType.AUDIT)
