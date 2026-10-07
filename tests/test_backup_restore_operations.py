from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.api.app import create_app
from backend.career_agent.models import CareerAgentToolRecord, CareerMemoryEntryRecord
from backend.career_decisions.models import CareerDecision
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.config.settings import Settings
from backend.current_opportunities.models import (
    OpportunityAcquisitionRun,
    OpportunityDataSource,
)
from backend.deep_decisions.models import LongitudinalContextSnapshot
from backend.operations.migrations import database_migration_status, expected_migration_heads
from backend.orchestration.jobs.models import Job
from backend.shared.db import make_engine, make_session_factory
from backend.shared.migrations import upgrade_database
from backend.users.models import ExternalAuthIdentity, User, UserProfile

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


def test_sqlite_backup_restore_preserves_representative_application_state(tmp_path) -> None:
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    restore_path = tmp_path / "restore.db"
    source_url = f"sqlite:///{source_path}"
    restore_url = f"sqlite:///{restore_path}"

    upgrade_database(source_url)
    source_engine = make_engine(source_url)
    try:
        _seed_representative_state(source_engine)
        source_engine.dispose()
        _sqlite_backup(source_path, backup_path)
        _sqlite_backup(backup_path, restore_path)

        restore_engine = make_engine(restore_url)
        try:
            factory = make_session_factory(restore_engine)
            with factory() as session:
                revision = database_migration_status(restore_engine, restore_url)
                assert revision.current_revisions == expected_migration_heads(restore_url)
                restored_user = session.execute(
                    select(User).where(User.user_id == "user_restore")
                ).scalar_one()
                assert restored_user.user_id == "user_restore"
                restored_identity = session.execute(select(CareerIdentity)).scalar_one()
                assert restored_identity.user_id == "user_restore"
                assert session.execute(select(CareerIdentityFact)).scalar_one().payload == {
                    "skill": "Python"
                }
                assert session.execute(select(CareerDecision)).scalar_one().title == (
                    "Choose first product role"
                )
                assert (
                    session.execute(select(LongitudinalContextSnapshot))
                    .scalar_one()
                    .record_count
                    == 1
                )
                assert session.execute(select(CareerMemoryEntryRecord)).scalar_one().value == (
                    "healthtech"
                )
                assert session.execute(select(CareerAgentToolRecord)).scalar_one().status == (
                    "preview_ready"
                )
                assert session.execute(select(OpportunityDataSource)).scalar_one().source_id == (
                    "src_restore"
                )
                assert session.execute(select(OpportunityAcquisitionRun)).scalar_one().status == (
                    "completed"
                )
                assert session.execute(select(Job)).scalar_one().status == "succeeded"
                assert session.execute(text("PRAGMA foreign_key_check")).all() == []

            app = create_app(
                engine=restore_engine,
                settings=Settings(
                    app_env="test",
                    database_url=restore_url,
                    readiness_require_migration_current=True,
                    _env_file=None,
                ),
            )
            ready = TestClient(app).get("/ready")
            assert ready.status_code == 200
            assert ready.json()["checks"]["schema"] == "current"
        finally:
            restore_engine.dispose()
    finally:
        source_engine.dispose()


def _sqlite_backup(source_path, target_path) -> None:
    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _seed_representative_state(engine) -> None:
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(User(user_id="user_restore", status="active"))
        session.flush()
        session.add_all(
            [
                ExternalAuthIdentity(
                    external_identity_id="identity_restore",
                    user_id="user_restore",
                    provider="auth0",
                    issuer="https://jmi.us.auth0.com/",
                    subject="auth0|restore",
                    email="restore@example.com",
                    email_verified=True,
                    last_seen_at=NOW,
                ),
                UserProfile(
                    user_id="user_restore",
                    display_name="Restore User",
                    email="restore@example.com",
                ),
            ]
        )
        session.flush()
        session.add(
            CareerIdentity(
                career_identity_id="ci_restore",
                user_id="user_restore",
                current_version=1,
                completeness_state="minimal",
                sufficiency_state="insufficient",
                ingestion_consent_granted=True,
                inference_consent_granted=True,
                downstream_personalization_consent_granted=True,
            )
        )
        session.flush()
        session.add_all(
            [
                CareerIdentityFact(
                    career_identity_fact_id="fact_restore",
                    career_identity_id="ci_restore",
                    user_id="user_restore",
                    fact_type="skill",
                    normalized_key="python",
                    state="explicit",
                    payload={"skill": "Python"},
                    provenance={"source": "restore_fixture"},
                ),
                CareerDecision(
                    decision_id="decision_restore",
                    user_id="user_restore",
                    career_identity_id="ci_restore",
                    decision_type="role_choice",
                    status="draft",
                    title="Choose first product role",
                    priorities=["learning"],
                    constraints=["remote"],
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                LongitudinalContextSnapshot(
                    longitudinal_context_id="long_restore",
                    user_id="user_restore",
                    decision_id="decision_restore",
                    window_end=NOW,
                    record_count=1,
                    context_payload={"decision_id": "decision_restore"},
                    evidence_payload={"basis": "fixture"},
                    generated_at=NOW,
                ),
                CareerMemoryEntryRecord(
                    career_memory_entry_id="memory_restore",
                    user_id="user_restore",
                    category="preferred_industries",
                    value="healthtech",
                    label="Healthtech",
                    notes="User wants mission-driven startups.",
                ),
                CareerAgentToolRecord(
                    career_agent_tool_id="tool_restore",
                    user_id="user_restore",
                    tool_type="application_prep_checklist",
                    status="preview_ready",
                    action_boundary="read_only_preview",
                    privacy_classification="user_private",
                    approval_required=False,
                    explicit_user_approval_required=False,
                    approval_reason="preview only",
                    proposed_action_summary="Prepare application checklist",
                    preview_payload={"steps": ["tailor resume"]},
                    evidence_refs=[],
                    freshness={"status": "fresh"},
                    uncertainty={"level": "low"},
                    warnings=[],
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                OpportunityDataSource(
                    source_id="src_restore",
                    provider="Example Provider",
                    display_name="Example Provider Jobs",
                    source_type="api",
                    acquisition_method="api_pull",
                    enabled=True,
                    allowed_use="allowed",
                    license_terms="permissive",
                    trust_classification="high",
                    freshness_sla_hours=24,
                    supported_domains=[],
                    supported_markets=["greater_boston"],
                    supported_opportunity_types=["job"],
                    ranking_use_allowed=True,
                    display_use_allowed=True,
                    refresh_config={},
                    provenance_requirements=[],
                    operational_status="enabled",
                ),
                Job(
                    job_id="job_restore",
                    job_type="current_opportunity_refresh",
                    queue_name="refresh",
                    status="succeeded",
                    created_at=NOW,
                    updated_at=NOW,
                    completed_at=NOW,
                ),
            ]
        )
        session.flush()
        session.add(
            OpportunityAcquisitionRun(
                run_id="run_restore",
                source_id="src_restore",
                idempotency_key="src_restore:run_restore",
                status="completed",
                trigger_type="manual",
                started_at=NOW,
                completed_at=NOW,
                retry_classification="none",
                retry_count=0,
                acquired_count=1,
                normalized_count=1,
                promoted_count=1,
                failure_details={},
                warnings=[],
            )
        )
        session.commit()
