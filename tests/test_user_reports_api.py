from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.config.settings import Settings
from backend.trust.models import UserReport


def test_user_report_api_creates_signal_and_safe_recheck_response(
    api_client: TestClient,
    session: Session,
) -> None:
    response = api_client.post(
        "/user-reports",
        json={
            "subject_type": "opportunity",
            "subject_id": "opp_missing_but_reportable",
            "report_type": "suspicious_ranking",
            "report_reason": "This appears to rank too highly.",
            "severity": "medium",
            "source_surface": "test_api",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report"]["status"] == "queued_for_recheck"
    assert data["report"]["report_type"] == "suspicious_ranking"
    assert "report_reason" not in data["report"]
    assert "reporter_user_id" not in data["report"]
    assert "reporter_session_id" not in data["report"]
    assert data["recheck_job"]["trigger_type"] == "suspicious_ranking"
    assert data["recheck_job"]["priority"] == "high"
    assert data["status"]["recheck_status_label"] == "Recheck queued"
    assert "does not directly change rankings" in data["message"]
    assert session.query(UserReport).count() == 1
    assert "internal_review_notes" not in response.text
    assert "reviewer_identity" not in response.text


def test_user_report_status_and_subject_listing_are_safe(api_client: TestClient) -> None:
    created = api_client.post(
        "/user-reports",
        json={
            "subject_type": "opportunity",
            "subject_id": "opp_report_status",
            "report_type": "outdated",
            "severity": "low",
        },
    ).json()["data"]

    status = api_client.get(
        f"/user-reports/status/{created['report']['user_report_id']}"
    )
    listing = api_client.get(
        "/user-reports",
        params={"subject_type": "opportunity", "subject_id": "opp_report_status"},
    )

    assert status.status_code == 200
    assert status.json()["data"]["report"]["status"] == "queued_for_recheck"
    assert "report_reason" not in status.json()["data"]["report"]
    assert "reporter_session_id" not in status.json()["data"]["report"]
    assert listing.status_code == 200
    assert len(listing.json()["data"]["reports"]) == 1
    assert "report_reason" not in listing.json()["data"]["reports"][0]
    assert "reporter_user_id" not in listing.json()["data"]["reports"][0]
    assert listing.json()["data"]["status"]["latest_report_type"] == "outdated"

    explanation = api_client.get(
        "/trust/explanation",
        params={"subject_type": "opportunity", "subject_id": "opp_report_status"},
    )
    assert explanation.status_code == 200
    assert explanation.json()["data"]["report_recheck_status"][
        "latest_report_status"
    ] == "queued_for_recheck"


def test_user_report_api_rejects_invalid_subject_and_report_type(
    api_client: TestClient,
) -> None:
    bad_subject = api_client.post(
        "/user-reports",
        json={
            "subject_type": "unsafe_subject",
            "subject_id": "x",
            "report_type": "outdated",
        },
    )
    bad_report_type = api_client.post(
        "/user-reports",
        json={
            "subject_type": "opportunity",
            "subject_id": "x",
            "report_type": "owner_approval_request",
        },
    )

    assert bad_subject.status_code == 422
    assert bad_report_type.status_code == 422


def test_public_demo_blocks_user_report_submission(session: Session) -> None:
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

    response = client.post(
        "/user-reports",
        json={
            "subject_type": "opportunity",
            "subject_id": "opp_public_demo",
            "report_type": "outdated",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["type"] == "public_demo_read_only"
    assert session.query(UserReport).count() == 0
