from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.admin.roles import AdminRole
from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.current_opportunities.models import (
    OpportunityAcquisitionRun,
    OpportunityDataSource,
)
from backend.orchestration.jobs.models import Job
from backend.users.models import User

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|ops_admin") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"Ops {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _assign_role(
    api_client: TestClient,
    session: Session,
    role: AdminRole | None,
) -> dict[str, str]:
    headers = _auth_headers()
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if role is not None else None
    session.flush()
    return headers


def _seed_operations_state(session: Session) -> None:
    session.add_all(
        [
            Job(
                job_id="job_running_stale",
                job_type="current_opportunity_refresh",
                queue_name="refresh",
                status="running",
                started_at=NOW - timedelta(hours=3),
                created_at=NOW - timedelta(hours=3),
                updated_at=NOW - timedelta(hours=3),
            ),
            Job(
                job_id="job_failed",
                job_type="deep_decision_analysis",
                queue_name="default",
                status="failed",
                error_code="PROVIDER_TIMEOUT",
                error_message="contains no exported payload",
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
    )
    session.flush()
    session.add(
        OpportunityDataSource(
            source_id="src_ops",
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
        )
    )
    session.flush()
    session.add(
        OpportunityAcquisitionRun(
            run_id="run_failed",
            source_id="src_ops",
            idempotency_key="src_ops:run_failed",
            status="failed",
            trigger_type="manual",
            started_at=NOW,
            completed_at=NOW,
            retry_classification="retryable",
            retry_count=1,
            failure_count=1,
            failure_details={"Authorization": "Bearer secret-token", "error": "timeout"},
            warnings=[],
        )
    )
    session.flush()


def test_operator_health_is_admin_read_protected(api_client: TestClient, session: Session) -> None:
    unauthenticated = api_client.get("/admin/operations/health")
    assert unauthenticated.status_code == 401

    normal_headers = _assign_role(api_client, session, None)
    normal = api_client.get("/admin/operations/health", headers=normal_headers)
    assert normal.status_code == 403

    admin_headers = _assign_role(api_client, session, AdminRole.READ_ONLY_OPERATOR)
    response = api_client.get("/admin/operations/health", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["readiness"]["checks"]["database"] == "ok"
    assert body["release_id"] == "unknown"
    assert "database_url" not in response.text


def test_operator_health_reports_safe_job_and_refresh_state(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_operations_state(session)
    headers = _assign_role(api_client, session, AdminRole.ADMIN)

    response = api_client.get("/admin/operations/health", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["jobs"]["by_status"]["running"] == 1
    assert data["jobs"]["stale_running_count"] == 1
    assert data["current_opportunities"]["source_count"] == 1
    assert data["current_opportunities"]["runs_by_status"]["failed"] == 1
    assert data["current_opportunities"]["recent_runs"][0]["failure_summary"] == {
        "keys": ["Authorization", "error"]
    }
    assert "secret-token" not in response.text


def test_metrics_endpoint_uses_bounded_route_labels(
    api_client: TestClient,
    session: Session,
) -> None:
    headers = _assign_role(api_client, session, AdminRole.READ_ONLY_OPERATOR)
    api_client.get("/health")
    api_client.get("/companies/company-1234567890-sensitive")

    response = api_client.get("/admin/operations/metrics", headers=headers)

    assert response.status_code == 200
    series = response.json()["data"]["http"]
    routes = {item["route"] for item in series}
    assert "/health" in routes
    assert "company-1234567890-sensitive" not in json.dumps(series)


def test_error_monitoring_failure_does_not_break_safe_error_response(
    session: Session,
) -> None:
    app = _app_with_raising_route(session)

    class BrokenMonitor:
        def capture_exception(self, exc, *, context):  # noqa: ANN001
            raise RuntimeError("monitoring sink down")

    app.state.error_monitor = BrokenMonitor()

    response = TestClient(app, raise_server_exceptions=False).get(
        "/boom",
        headers={"X-Request-ID": "ops-monitoring-1"},
    )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "ops-monitoring-1"
    assert "monitoring sink down" not in response.text
    assert "ValueError" not in response.text


def _app_with_raising_route(session: Session) -> FastAPI:
    app = create_app(engine=session.bind)

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    @app.get("/boom")
    def boom() -> None:
        raise ValueError("sensitive internal exception")

    return app
