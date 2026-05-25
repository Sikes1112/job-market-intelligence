from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog
from backend.admin.repository import AdminEventLogRepository
from backend.admin.roles import AdminRole
from backend.admin.service import AdminEventLogInput, AdminEventLogService
from backend.api.dependencies import (
    CurrentUser,
    require_admin_mutation_access,
    require_admin_read_access,
    require_data_review_access,
)
from backend.users.models import ExternalAuthIdentity, User, UserProfile


def _auth_headers(subject: str = "auth0|admin_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _assign_role(
    api_client,
    session: Session,
    role: AdminRole | str | None,
    *,
    subject: str = "auth0|admin_user",
) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if isinstance(role, AdminRole) else role
    session.flush()
    return headers, user_id


def _current(role: AdminRole | str | None) -> CurrentUser:
    role_value = role.value if isinstance(role, AdminRole) else role
    user = User(user_id="user_role_test", status="active", admin_role=role_value)
    identity = ExternalAuthIdentity(
        external_identity_id="identity_role_test",
        user_id=user.user_id,
        provider="auth0",
        issuer="https://jmi.us.auth0.com/",
        subject="auth0|role_test",
    )
    profile = UserProfile(user_id=user.user_id)
    return CurrentUser(user=user, identity=identity, profile=profile)


def _service(session: Session, *, when: datetime) -> AdminEventLogService:
    return AdminEventLogService(
        AdminEventLogRepository(session),
        clock=lambda: when,
    )


def test_admin_has_admin_access() -> None:
    admin = require_admin_mutation_access(_current(AdminRole.ADMIN))

    assert admin.role is AdminRole.ADMIN
    assert require_data_review_access(_current(AdminRole.ADMIN)).role is AdminRole.ADMIN
    assert require_admin_read_access(_current(AdminRole.ADMIN)).role is AdminRole.ADMIN


def test_data_reviewer_has_reviewer_access() -> None:
    reviewer = require_data_review_access(_current(AdminRole.DATA_REVIEWER))

    assert reviewer.role is AdminRole.DATA_REVIEWER
    assert require_admin_read_access(_current(AdminRole.DATA_REVIEWER)).role is (
        AdminRole.DATA_REVIEWER
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin_mutation_access(_current(AdminRole.DATA_REVIEWER))
    assert exc_info.value.status_code == 403


def test_read_only_operator_has_read_only_admin_access() -> None:
    read_only = require_admin_read_access(_current(AdminRole.READ_ONLY_OPERATOR))

    assert read_only.role is AdminRole.READ_ONLY_OPERATOR
    with pytest.raises(HTTPException) as review_exc:
        require_data_review_access(_current(AdminRole.READ_ONLY_OPERATOR))
    assert review_exc.value.status_code == 403
    with pytest.raises(HTTPException) as mutation_exc:
        require_admin_mutation_access(_current(AdminRole.READ_ONLY_OPERATOR))
    assert mutation_exc.value.status_code == 403


def test_non_admin_users_are_rejected(api_client, session: Session) -> None:
    unauthenticated = api_client.get("/admin/me")
    assert unauthenticated.status_code == 401

    headers, _user_id = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|ordinary_user",
    )
    no_role = api_client.get("/admin/me", headers=headers)
    assert no_role.status_code == 403

    with pytest.raises(HTTPException) as invalid_role:
        require_admin_read_access(_current("member"))
    assert invalid_role.value.status_code == 403


def test_admin_me_reports_role_capabilities(api_client, session: Session) -> None:
    headers, user_id = _assign_role(api_client, session, AdminRole.ADMIN)

    response = api_client.get("/admin/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["user_id"] == user_id
    assert body["data"]["role"] == "admin"
    assert body["data"]["capabilities"] == {
        "read_admin_data": True,
        "review_data": True,
        "controlled_admin_mutations": True,
    }


def test_read_only_operator_can_inspect_admin_event_log(
    api_client,
    session: Session,
) -> None:
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|read_only_user",
    )
    _service(session, when=datetime(2026, 5, 25, 12, tzinfo=UTC)).record_event(
        AdminEventLogInput(
            actor="user_admin",
            role=AdminRole.ADMIN,
            action="admin.test_event",
            object_type="test_fixture",
            object_id="fixture_1",
            before_state={"status": "old"},
            after_state={"status": "new"},
            reason="verify read-only admin access",
            request_id="req-layer-9a",
        )
    )

    response = api_client.get("/admin/event-log", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    [row] = body["data"]["admin_event_log"]
    assert row["actor"] == "user_admin"
    assert row["role"] == "admin"
    assert row["request_id"] == "req-layer-9a"


def test_admin_event_log_records_are_append_only(session: Session) -> None:
    service = _service(session, when=datetime(2026, 5, 25, 12, tzinfo=UTC))
    first = service.record_event(
        AdminEventLogInput(
            actor="user_admin",
            role=AdminRole.ADMIN,
            action="admin.first",
            object_type="fixture",
            object_id="fixture_1",
            reason="first record",
        )
    )
    second = service.record_event(
        AdminEventLogInput(
            actor="user_admin",
            role=AdminRole.ADMIN,
            action="admin.second",
            object_type="fixture",
            object_id="fixture_1",
            reason="second record",
        )
    )
    session.commit()
    first_id = first.admin_event_id

    assert first.admin_event_id != second.admin_event_id
    assert session.query(AdminEventLog).count() == 2

    first.reason = "rewritten"
    with pytest.raises(ValueError, match="append-only"):
        session.flush()
    session.rollback()

    first = session.get(AdminEventLog, first_id)
    assert first is not None
    session.delete(first)
    with pytest.raises(ValueError, match="append-only"):
        session.flush()


def test_admin_event_log_captures_required_fields(session: Session) -> None:
    now = datetime(2026, 5, 25, 13, 30, tzinfo=UTC)
    row = _service(session, when=now).record_event(
        AdminEventLogInput(
            actor="user_admin",
            role=AdminRole.ADMIN,
            action="admin.review_decision.recorded",
            object_type="raw_ingestion_record",
            object_id="raw_123",
            before_state={"review_status": "pending"},
            after_state={"review_status": "approved"},
            reason="source evidence matched canonical record",
            request_id="review-req-1",
        )
    )

    assert row.actor == "user_admin"
    assert row.actor_role == "admin"
    assert row.action == "admin.review_decision.recorded"
    assert row.object_type == "raw_ingestion_record"
    assert row.object_id == "raw_123"
    assert row.before_state == {"review_status": "pending"}
    assert row.after_state == {"review_status": "approved"}
    assert row.reason == "source evidence matched canonical record"
    assert row.timestamp == now
    assert row.request_id == "review-req-1"
