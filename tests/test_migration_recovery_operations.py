from __future__ import annotations

import json
import sqlite3

import pytest
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.api.app import create_app
from backend.config.settings import Settings
from backend.operations.migrations import database_migration_status, expected_migration_heads
from backend.shared.db import create_all, make_engine
from backend.shared.migrations import upgrade_database


def test_strict_readiness_blocks_unversioned_schema_until_recovery_stamp(tmp_path) -> None:
    database_path = tmp_path / "unversioned-current-schema.db"
    database_url = f"sqlite:///{database_path}"
    engine = make_engine(database_url)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        readiness_require_migration_current=True,
        _env_file=None,
    )
    try:
        create_all(engine)
        app = create_app(engine=engine, settings=settings)

        before = TestClient(app).get("/ready")
        assert before.status_code == 503
        assert before.json()["checks"]["schema"] == "unversioned"
        engine.dispose()

        upgrade_database(database_url, allow_existing_schema_stamp=True)

        recovered_engine = make_engine(database_url)
        try:
            after = TestClient(create_app(engine=recovered_engine, settings=settings)).get("/ready")
            assert after.status_code == 200
            assert after.json()["checks"]["schema"] == "current"
            assert database_migration_status(
                recovered_engine,
                database_url,
            ).current_revisions == expected_migration_heads(database_url)
        finally:
            recovered_engine.dispose()
    finally:
        engine.dispose()


def test_failed_partial_upgrade_requires_restore_before_forward_recovery(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed_path = tmp_path / "failed-partial.db"
    backup_path = tmp_path / "pre-upgrade-backup.db"
    recovered_path = tmp_path / "recovered.db"
    failed_url = f"sqlite:///{failed_path}"
    recovered_url = f"sqlite:///{recovered_path}"

    upgrade_database(failed_url, revision="0038_deep_decision_intelligence")
    _sqlite_backup(failed_path, backup_path)

    engine_at_0038 = make_engine(failed_url)
    try:
        assert database_migration_status(engine_at_0038, failed_url).current_revisions == (
            "0038_deep_decision_intelligence",
        )
    finally:
        engine_at_0038.dispose()

    original_create_index = Operations.create_index

    def fail_after_current_opportunities_table(
        self,
        index_name,
        table_name,
        columns,
        *args,
        **kwargs,
    ):
        if index_name == "ix_current_opportunities_company":
            raise RuntimeError("controlled 39B migration failure")
        return original_create_index(self, index_name, table_name, columns, *args, **kwargs)

    monkeypatch.setattr(Operations, "create_index", fail_after_current_opportunities_table)
    with pytest.raises(RuntimeError, match="controlled 39B migration failure"):
        upgrade_database(failed_url)

    failed_engine = make_engine(failed_url)
    try:
        status = database_migration_status(failed_engine, failed_url)
        assert status.current_revisions == ("0038_deep_decision_intelligence",)
        assert status.status == "mismatch"
        tables = set(inspect(failed_engine).get_table_names())
        assert "opportunity_data_sources" in tables
        assert "current_opportunities" in tables
        assert "opportunity_acquisition_runs" not in tables

        settings = Settings(
            app_env="test",
            database_url=failed_url,
            readiness_require_migration_current=True,
            _env_file=None,
        )
        ready = TestClient(create_app(engine=failed_engine, settings=settings)).get("/ready")
        assert ready.status_code == 503
        assert ready.json()["checks"]["schema"] == "mismatch"
    finally:
        failed_engine.dispose()

    monkeypatch.undo()
    with pytest.raises(Exception, match="already exists"):
        upgrade_database(failed_url)

    _sqlite_backup(backup_path, recovered_path)
    upgrade_database(recovered_url)
    recovered_engine = make_engine(recovered_url)
    try:
        recovered_status = database_migration_status(recovered_engine, recovered_url)
        assert recovered_status.current_revisions == expected_migration_heads(recovered_url)
        assert recovered_status.status == "current"
        recovered_settings = Settings(
            app_env="test",
            database_url=recovered_url,
            readiness_require_migration_current=True,
            _env_file=None,
        )
        client = TestClient(create_app(engine=recovered_engine, settings=recovered_settings))
        ready = client.get("/ready")
        assert ready.status_code == 200
        response = client.get("/current-opportunities", headers=_auth_headers())
        assert response.status_code == 200
        assert response.json()["data"]["opportunities"] == []
    finally:
        recovered_engine.dispose()


def _sqlite_backup(source_path, target_path) -> None:
    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _auth_headers() -> dict[str, str]:
    return {
        "X-Verified-OIDC-Claims": json.dumps(
            {
                "iss": "https://jmi.us.auth0.com/",
                "sub": "auth0|migration_recovery",
                "email": "migration-recovery@example.com",
                "email_verified": True,
                "name": "Migration Recovery",
            }
        )
    }
