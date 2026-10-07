from __future__ import annotations

from datetime import timedelta
from urllib.error import URLError

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.config.settings import Settings
from backend.current_opportunities.adapters import StaticOpportunityAdapter
from backend.current_opportunities.models import CurrentOpportunity
from backend.current_opportunities.schemas import AcquisitionRunStatus
from backend.operations.status import opportunity_refresh_summary, readiness_payload
from backend.shared.db import create_all, make_engine
from tests.test_auth0_jwks_middleware import AUDIENCE, ISSUER, JWKS_URL, _token
from tests.test_current_opportunities import (
    NOW,
    _coverage,
    _record,
    _seed_market,
    _service,
    _source,
)


class _UnavailableAdapter:
    source_id = "src_employer"

    def acquire(self, *, requested_at, idempotency_key):  # noqa: ANN001
        raise RuntimeError("upstream source unavailable")


def test_db_unavailable_drill_readiness_fails_safely() -> None:
    class BrokenEngine:
        def connect(self):  # noqa: ANN001
            raise OSError("database host unreachable")

    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        release_id="release-db-drill",
        readiness_require_migration_current=True,
        rate_limit_enabled=False,
        security_headers_enabled=False,
        _env_file=None,
    )

    status_code, payload = readiness_payload(BrokenEngine(), settings)

    assert status_code == 503
    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"] == "failed"
    assert "database host unreachable" not in str(payload)
    assert "sqlite:///:memory:" not in str(payload)


def test_source_unavailable_drill_preserves_prior_current_opportunities(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter("src_employer", (_record("source-drill-existing"),)),
        run_id="run_source_drill_success",
        now=NOW,
    )
    before_count = session.execute(select(CurrentOpportunity)).scalars().all()
    assert len(before_count) == 1

    failed = service.refresh_source(
        _UnavailableAdapter(),  # type: ignore[arg-type]
        run_id="run_source_drill_failed",
        now=NOW + timedelta(minutes=10),
    )
    after_rows = session.execute(select(CurrentOpportunity)).scalars().all()
    summary = opportunity_refresh_summary(session, stale_after_seconds=3600)

    assert failed.status == AcquisitionRunStatus.FAILED.value
    assert len(after_rows) == 1
    assert summary["runs_by_status"][AcquisitionRunStatus.COMPLETED.value] == 1
    assert summary["runs_by_status"][AcquisitionRunStatus.FAILED.value] == 1
    assert summary["last_successful_refresh"]["run_id"] == "run_source_drill_success"
    assert "upstream source unavailable" not in str(summary)


def test_auth_outage_drill_fails_closed_while_liveness_remains_public(monkeypatch) -> None:
    def failing_urlopen(_request, timeout: int = 5):  # noqa: ANN001
        raise URLError("jwks provider unavailable")

    monkeypatch.setattr("backend.auth.jwks.urlopen", failing_urlopen)
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auth0_issuer=ISSUER,
        auth0_audience=AUDIENCE,
        auth0_jwks_url=JWKS_URL,
        rate_limit_enabled=False,
        security_headers_enabled=False,
        _env_file=None,
    )
    client = TestClient(create_app(engine=engine, settings=settings))

    protected = client.get("/me", headers={"Authorization": f"Bearer {_token()}"})
    public = client.get("/health")

    assert protected.status_code == 401
    assert protected.json()["error"]["type"] == "auth_error"
    assert "jwks provider unavailable" not in protected.text
    assert public.status_code == 200


def test_bad_deployment_drill_unversioned_schema_is_not_ready() -> None:
    engine = make_engine("sqlite:///:memory:")
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        release_id="bad-release-drill",
        readiness_require_migration_current=True,
        rate_limit_enabled=False,
        security_headers_enabled=False,
        _env_file=None,
    )
    client = TestClient(create_app(engine=engine, settings=settings))

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json()["release_id"] == "bad-release-drill"
    assert ready.status_code == 503
    assert ready.json()["release_id"] == "bad-release-drill"
    assert ready.json()["checks"]["schema"] != "current"
