from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.geography.models import Region


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client, subject: str) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["data"]["user"]["user_id"]


def _seed_region(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()


def _reminder_body(**overrides):
    body = {
        "reminder_type": "market_refresh_alert",
        "product_object_type": "region",
        "product_object_id": "greater_boston",
        "title": "Review Greater Boston refresh",
        "due_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        "timezone": "UTC",
        "description": "Review market freshness.",
    }
    body.update(overrides)
    return body


def test_reminder_creation_does_not_create_ats_application_status_state(
    api_client,
    session: Session,
) -> None:
    _seed_region(session)
    headers, _ = _current_user_id(api_client, "auth0|reminder_user")

    created = api_client.post(
        "/api/integrations/reminders",
        headers=headers,
        json=_reminder_body(),
    )

    assert created.status_code == 201
    reminder = created.json()["data"]["reminder"]
    assert reminder["receipt"]["external_write_performed"] is False
    assert reminder["receipt"]["live_sync_enabled"] is False
    assert reminder["receipt"]["two_way_sync_enabled"] is False
    assert reminder["receipt"]["destination"] == "ics_calendar"
    assert "application_status" not in json.dumps(reminder)
    assert "ats" in " ".join(reminder["receipt"]["limitations"]).casefold()


def test_ics_export_includes_product_object_provenance(api_client, session: Session) -> None:
    _seed_region(session)
    headers, _ = _current_user_id(api_client, "auth0|ics_user")
    created = api_client.post(
        "/api/integrations/reminders",
        headers=headers,
        json=_reminder_body(reminder_type="application_window"),
    )
    reminder_id = created.json()["data"]["reminder"]["reminder_id"]

    downloaded = api_client.get(
        f"/api/integrations/reminders/{reminder_id}/ics",
        headers=headers,
    )

    assert downloaded.status_code == 200
    text = downloaded.text
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert "Product object: region:greater_boston" in text
    assert "No external calendar write" in text
    assert "ATS application status" in text


def test_reminder_request_rejects_application_status_fields(api_client, session: Session) -> None:
    _seed_region(session)
    headers, _ = _current_user_id(api_client, "auth0|ats_status_user")

    response = api_client.post(
        "/api/integrations/reminders",
        headers=headers,
        json={
            **_reminder_body(),
            "application_status": "applied",
        },
    )

    assert response.status_code == 422
