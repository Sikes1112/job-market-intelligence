from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.orchestration.jobs.models import Job


def test_job_created_with_required_fields(session: Session) -> None:
    job = Job(job_id="job_1", job_type="hiring_refresh")
    session.add(job)
    session.flush()
    fetched = session.get(Job, "job_1")
    assert fetched is not None
    assert fetched.job_type == "hiring_refresh"
    assert fetched.status == "queued"
    assert fetched.priority == "normal"
    assert fetched.retry_count == 0
    assert fetched.max_retries == 3
    assert isinstance(fetched.created_at, datetime)


def test_job_missing_job_type_raises(session: Session) -> None:
    job = Job(job_id="job_2")
    session.add(job)
    with pytest.raises(IntegrityError):
        session.flush()


def test_job_round_trip_with_envelope_payloads(session: Session) -> None:
    job = Job(
        job_id="job_3",
        job_type="region_score_recompute",
        queue_name="refresh",
        status="running",
        priority="high",
        trigger_type="event_driven",
        requested_by="system",
        scope={"region_ids": ["greater_boston"]},
        scope_hash="abc123",
        dedupe_key="region_score_recompute::greater_boston::abc123",
        inputs={"hiring_map_version": "hiring_v71"},
        options={"recompute_normalized_views": True},
        dependency_refs=["hiring_v71", "entry_v29"],
        input_hash="ihash",
        output_hash="ohash",
        warnings=[
            {"warning_code": "LOW_CONFIDENCE_ENTRY_LEVEL", "severity": "low"},
        ],
    )
    session.add(job)
    session.flush()
    fetched = session.get(Job, "job_3")
    assert fetched is not None
    assert fetched.scope == {"region_ids": ["greater_boston"]}
    assert fetched.dependency_refs == ["hiring_v71", "entry_v29"]
    assert fetched.warnings[0]["warning_code"] == "LOW_CONFIDENCE_ENTRY_LEVEL"
    assert fetched.dedupe_key.startswith("region_score_recompute::")
