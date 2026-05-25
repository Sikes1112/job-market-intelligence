from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog, AuditFindingReview
from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import SourceRef
from backend.shared.confidence import Confidence
from backend.shared.provenance import DataOrigin, LicenseTermsCategory, SourceType
from backend.users.models import User

_NOW = datetime(2026, 5, 25, 15, tzinfo=UTC)
_FINDING_ID = "override_balance::comp_review::missing_reason"


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


def _assign_role(
    api_client,
    session: Session,
    role: AdminRole | None,
    *,
    subject: str,
) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if role is not None else None
    session.flush()
    return headers, user_id


def _seed_review_rows(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="region_review",
                region_name="region_review",
                display_name="Review Region",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_review",
                company_name="Review Co",
                normalized_company_name="review co",
                eligibility_status="override_included",
                eligibility_override_flag=True,
                eligibility_override_reason=None,
                classification_confidence="high_confidence",
            ),
            SourceRef(
                source_id="source_review",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Review Careers",
                url_or_provider="https://example.test/review",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
                notes="source under review",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_review",
                company_id="comp_review",
                region_id="region_review",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                operations_evidence_flag=False,
                hiring_evidence_flag=True,
                presence_confidence="high_confidence",
                source_refs={"source_ids": ["source_review"]},
            ),
            CompanyRegionHiring(
                hiring_id="hiring_review",
                company_id="comp_review",
                region_id="region_review",
                currently_hiring_flag=True,
                active_posting_count_now=4,
                posting_count_30d=8,
                posting_count_90d=16,
                hiring_confidence="high_confidence",
                freshness_expires_at=_NOW,
                source_refs={"source_ids": ["source_review"]},
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_review",
                company_id="comp_review",
                region_id="region_review",
                internship_count=2,
                coop_count=1,
                entry_level_full_time_count=3,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.7,
                entry_level_confidence="high_confidence",
                freshness_expires_at=_NOW,
                source_refs={"source_ids": ["source_review"]},
            ),
        ]
    )
    session.flush()


def test_admin_can_view_review_data(api_client, session: Session) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_review_view",
    )

    response = api_client.get("/admin/review/companies", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["companies"][0]["company_id"] == "comp_review"


def test_data_reviewer_can_view_review_data(api_client, session: Session) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_review_view",
    )

    response = api_client.get("/admin/review/source-refs", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["source_refs"][0]["source_id"] == "source_review"


def test_read_only_operator_can_view_review_data(api_client, session: Session) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_review_view",
    )

    response = api_client.get("/admin/review/audit-findings", headers=headers)

    assert response.status_code == 200
    finding_ids = [row["finding_id"] for row in response.json()["data"]["audit_findings"]]
    assert _FINDING_ID in finding_ids


def test_unauthorized_users_cannot_access_review_data(api_client, session: Session) -> None:
    _seed_review_rows(session)

    unauthenticated = api_client.get("/admin/review/companies")
    assert unauthenticated.status_code == 401

    headers, _user_id = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|ordinary_review_user",
    )
    no_role = api_client.get("/admin/review/companies", headers=headers)
    assert no_role.status_code == 403


def test_admin_can_transition_audit_finding_lifecycle(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_transition",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=headers,
        json={
            "finding_id": _FINDING_ID,
            "target_state": "acknowledged",
            "reason": "reviewed missing override reason",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["review_state"] == "acknowledged"
    row = session.get(AuditFindingReview, _FINDING_ID)
    assert row is not None
    assert row.review_state == "acknowledged"


def test_data_reviewer_can_transition_audit_finding_lifecycle(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_transition",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=headers,
        json={
            "finding_id": _FINDING_ID,
            "target_state": "escalated",
            "reason": "needs senior review",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["review_state"] == "escalated"


def test_read_only_operator_cannot_transition_audit_finding_lifecycle(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_transition",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=headers,
        json={
            "finding_id": _FINDING_ID,
            "target_state": "acknowledged",
            "reason": "read only users cannot do this",
        },
    )

    assert response.status_code == 403
    assert session.get(AuditFindingReview, _FINDING_ID) is None


def test_invalid_lifecycle_transition_is_rejected(api_client, session: Session) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|invalid_transition",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=headers,
        json={
            "finding_id": _FINDING_ID,
            "target_state": "resolved",
            "reason": "open findings cannot resolve directly",
        },
    )

    assert response.status_code == 400
    assert session.get(AuditFindingReview, _FINDING_ID) is None


def test_missing_lifecycle_transition_reason_is_rejected(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|missing_reason",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=headers,
        json={"finding_id": _FINDING_ID, "target_state": "acknowledged"},
    )

    assert response.status_code == 422
    assert session.get(AuditFindingReview, _FINDING_ID) is None


def test_lifecycle_transition_writes_admin_event_log(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|event_log_transition",
    )

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers={**headers, "X-Request-ID": "lifecycle-req-1"},
        json={
            "finding_id": _FINDING_ID,
            "target_state": "acknowledged",
            "reason": "capturing lifecycle event",
        },
    )

    assert response.status_code == 200
    [event] = session.query(AdminEventLog).all()
    assert event.actor == user_id
    assert event.actor_role == "admin"
    assert event.action == "admin.audit_finding.lifecycle_transition"
    assert event.object_type == "audit_finding"
    assert event.object_id == _FINDING_ID
    assert event.before_state["review_state"] == "open"
    assert event.after_state["review_state"] == "acknowledged"
    assert event.reason == "capturing lifecycle event"
    assert event.timestamp is not None
    assert event.request_id == "lifecycle-req-1"


def test_review_endpoints_do_not_mutate_production_records(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_non_mutation",
    )
    before = _production_state(session)

    for path in (
        "/admin/review/companies",
        "/admin/review/companies/comp_review",
        "/admin/review/presence",
        "/admin/review/presence/presence_review",
        "/admin/review/hiring",
        "/admin/review/hiring/hiring_review",
        "/admin/review/entry-level",
        "/admin/review/entry-level/entry_review",
        "/admin/review/source-refs",
        "/admin/review/source-refs/source_review",
        "/admin/review/audit-findings",
    ):
        response = api_client.get(path, headers=headers)
        assert response.status_code == 200, path

    assert _production_state(session) == before
    assert session.query(AdminEventLog).count() == 0
    assert session.query(AuditFindingReview).count() == 0


def _production_state(session: Session) -> dict:
    company = session.get(Company, "comp_review")
    presence = session.get(CompanyRegionPresence, "presence_review")
    hiring = session.get(CompanyRegionHiring, "hiring_review")
    entry = session.get(CompanyRegionEntryLevel, "entry_review")
    source = session.get(SourceRef, "source_review")
    assert company and presence and hiring and entry and source
    return {
        "company": (
            company.company_name,
            company.eligibility_status,
            company.version,
            company.updated_at,
        ),
        "presence": (
            presence.presence_status,
            presence.source_refs,
            presence.version,
            presence.updated_at,
        ),
        "hiring": (
            hiring.currently_hiring_flag,
            hiring.active_posting_count_now,
            hiring.source_refs,
            hiring.version,
            hiring.updated_at,
        ),
        "entry": (
            entry.internship_count,
            entry.entry_level_access_score,
            entry.source_refs,
            entry.version,
            entry.updated_at,
        ),
        "source": (
            source.source_name,
            source.confidence,
            source.notes,
            source.version,
            source.updated_at,
        ),
    }

