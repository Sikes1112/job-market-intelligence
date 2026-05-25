from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog, AdminOverride, AdminRepairAction
from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.shared.confidence import Confidence
from backend.shared.provenance import DataOrigin, LicenseTermsCategory, SourceType
from backend.users.models import User

_NOW = datetime(2026, 5, 25, 16, tzinfo=UTC)
_REVIEW_AT = "2026-06-25T16:00:00+00:00"
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


def _seed_review_rows(session: Session, *, include_provenance: bool = False) -> None:
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
                prestige_score=0.5,
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
                state="fresh",
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
                state="fresh",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_review",
                company_id="comp_review",
                region_id="region_review",
                currently_hiring_flag=True,
                active_posting_count_now=4,
                posting_count_30d=8,
                posting_count_90d=16,
                hiring_program_count=1,
                hiring_confidence="high_confidence",
                freshness_expires_at=_NOW,
                source_refs={"source_ids": ["source_review"]},
                state="fresh",
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
                state="fresh",
            ),
        ]
    )
    session.flush()
    if include_provenance:
        _seed_provenance_link(session)


def _seed_provenance_link(session: Session) -> None:
    observation = SourceObservation(
        observation_id="obs_review",
        source_id="source_review",
        source_type=SourceType.COMPANY_OFFICIAL.value,
        source_name="Review Careers",
        url_or_provider="https://example.test/review",
        collected_at=_NOW,
        observed_at=_NOW,
        license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
        confidence=Confidence.HIGH.value,
        data_origin=DataOrigin.REAL_OBSERVED.value,
        observation_status="current",
        notes="observed source history",
    )
    session.add(observation)
    session.flush()
    session.add(
        FactSourceLink(
            link_id="link_presence_review",
            observation_id=observation.observation_id,
            source_id="source_review",
            fact_type="presence_fact",
            fact_id="presence_review",
            fact_field="presence_status",
            source_type=SourceType.COMPANY_OFFICIAL.value,
            source_name="Review Careers",
            url_or_provider="https://example.test/review",
            collected_at=_NOW,
            observed_at=_NOW,
            license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
            confidence=Confidence.HIGH.value,
            data_origin=DataOrigin.REAL_OBSERVED.value,
            observation_status="current",
            notes="presence evidence",
        )
    )
    session.flush()


def _override_payload(**overrides) -> dict:
    payload = {
        "target_type": "company",
        "target_id": "comp_review",
        "override_type": "company_eligibility",
        "override_value": {"eligibility_status": "eligible"},
        "reason": "official source clarifies eligibility",
        "source_evidence": {"source_ids": ["source_review"]},
        "review_at": _REVIEW_AT,
    }
    payload.update(overrides)
    return payload


def _create_override(api_client, headers: dict[str, str], **overrides) -> str:
    response = api_client.post(
        "/admin/overrides",
        headers=headers,
        json=_override_payload(**overrides),
    )
    assert response.status_code == 200
    return response.json()["data"]["override_id"]


def _repair_payload(**overrides) -> dict:
    payload = {
        "action_type": "request_review",
        "target_type": "company",
        "target_id": "comp_review",
        "reason": "needs reviewer follow-up",
    }
    payload.update(overrides)
    return payload


def _create_repair_action(api_client, headers: dict[str, str], **overrides) -> str:
    response = api_client.post(
        "/admin/repair-actions",
        headers=headers,
        json=_repair_payload(**overrides),
    )
    assert response.status_code == 200
    return response.json()["data"]["repair_action_id"]


def _output_service(session: Session) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def test_override_creation_requires_required_review_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_override_required",
    )

    for payload in (
        _override_payload(reason=""),
        _override_payload(source_evidence={}),
        _override_payload(review_at=None),
    ):
        response = api_client.post("/admin/overrides", headers=headers, json=payload)
        assert response.status_code == 422

    assert session.query(AdminOverride).count() == 0


def test_override_creation_requires_authorized_role(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)

    unauthenticated = api_client.post("/admin/overrides", json=_override_payload())
    assert unauthenticated.status_code == 401

    ordinary_headers, _user_id = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|ordinary_override",
    )
    ordinary = api_client.post(
        "/admin/overrides",
        headers=ordinary_headers,
        json=_override_payload(),
    )
    assert ordinary.status_code == 403

    read_only_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_override_create",
    )
    read_only = api_client.post(
        "/admin/overrides",
        headers=read_only_headers,
        json=_override_payload(),
    )
    assert read_only.status_code == 403
    assert session.query(AdminOverride).count() == 0


def test_data_reviewer_can_propose_override_without_erasing_canonical_fact(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_override",
    )
    company = session.get(Company, "comp_review")
    assert company is not None
    before = (company.eligibility_status, company.eligibility_override_reason)

    response = api_client.post(
        "/admin/overrides",
        headers=headers,
        json=_override_payload(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "proposed"
    assert data["reviewer_actor"] == user_id
    assert data["previous_value"]["eligibility_status"] == "override_included"
    session.refresh(company)
    assert (company.eligibility_status, company.eligibility_override_reason) == before


def test_read_only_operator_can_view_but_not_activate_or_revoke_overrides(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_override_control",
    )
    override_id = _create_override(api_client, admin_headers)
    read_only_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_override_control",
    )

    listed = api_client.get("/admin/overrides", headers=read_only_headers)
    detail = api_client.get(f"/admin/overrides/{override_id}", headers=read_only_headers)
    activate = api_client.post(
        f"/admin/overrides/{override_id}/activate",
        headers=read_only_headers,
        json={"reason": "read-only cannot activate"},
    )
    revoke = api_client.post(
        f"/admin/overrides/{override_id}/revoke",
        headers=read_only_headers,
        json={"reason": "read-only cannot revoke"},
    )

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert activate.status_code == 403
    assert revoke.status_code == 403
    assert session.get(AdminOverride, override_id).status == "proposed"


def test_override_activation_revocation_are_logged_and_visible_in_review(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    reviewer_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_override_visible",
    )
    override_id = _create_override(api_client, reviewer_headers)
    admin_headers, admin_user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_override_visible",
    )

    activated = api_client.post(
        f"/admin/overrides/{override_id}/activate",
        headers={**admin_headers, "X-Request-ID": "override-activate-1"},
        json={"reason": "approved documented source"},
    )
    assert activated.status_code == 200
    detail = api_client.get(
        "/admin/review/companies/comp_review",
        headers=admin_headers,
    )
    assert detail.status_code == 200
    [active] = detail.json()["data"]["active_overrides"]
    assert active["override_id"] == override_id
    assert active["status"] == "active"

    revoked = api_client.post(
        f"/admin/overrides/{override_id}/revoke",
        headers=admin_headers,
        json={"reason": "superseded by later source review"},
    )
    assert revoked.status_code == 200
    detail_after = api_client.get(
        "/admin/review/companies/comp_review",
        headers=admin_headers,
    )
    assert detail_after.json()["data"]["active_overrides"] == []

    actions = {event.action: event for event in session.query(AdminEventLog).all()}
    activated_event = actions["admin.override.activated"]
    assert activated_event.actor == admin_user_id
    assert activated_event.actor_role == "admin"
    assert activated_event.object_type == "admin_override"
    assert activated_event.object_id == override_id
    assert activated_event.before_state["status"] == "proposed"
    assert activated_event.after_state["status"] == "active"
    assert activated_event.reason == "approved documented source"
    assert activated_event.timestamp is not None
    assert activated_event.request_id == "override-activate-1"
    assert actions["admin.override.revoked"].after_state["status"] == "revoked"


def test_expired_overrides_cannot_be_activated_or_surfaced_as_active(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_expired_override",
    )
    expired_id = _create_override(
        api_client,
        admin_headers,
        review_at=None,
        expires_at="2020-01-01T00:00:00+00:00",
    )

    rejected = api_client.post(
        f"/admin/overrides/{expired_id}/activate",
        headers=admin_headers,
        json={"reason": "cannot activate expired override"},
    )
    assert rejected.status_code == 400
    assert session.get(AdminOverride, expired_id).status == "proposed"

    active_id = _create_override(
        api_client,
        admin_headers,
        review_at=None,
        expires_at="2099-01-01T00:00:00+00:00",
    )
    activated = api_client.post(
        f"/admin/overrides/{active_id}/activate",
        headers=admin_headers,
        json={"reason": "temporarily active override"},
    )
    assert activated.status_code == 200
    active = session.get(AdminOverride, active_id)
    assert active is not None
    active.expires_at = datetime(2020, 1, 1, tzinfo=UTC)
    session.flush()

    detail = api_client.get(
        "/admin/review/companies/comp_review",
        headers=admin_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["active_overrides"] == []


def test_invalid_override_target_or_type_is_rejected(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|invalid_override",
    )

    incompatible = api_client.post(
        "/admin/overrides",
        headers=headers,
        json=_override_payload(override_type="presence_status"),
    )
    invalid_enum = api_client.post(
        "/admin/overrides",
        headers=headers,
        json=_override_payload(target_type="hiring_fact"),
    )

    assert incompatible.status_code == 400
    assert invalid_enum.status_code == 422


def test_repair_actions_require_authorization_and_reason(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)

    unauthenticated = api_client.post(
        "/admin/repair-actions",
        json=_repair_payload(),
    )
    assert unauthenticated.status_code == 401

    read_only_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_repair_create",
    )
    read_only = api_client.post(
        "/admin/repair-actions",
        headers=read_only_headers,
        json=_repair_payload(),
    )
    assert read_only.status_code == 403

    reviewer_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_repair_create",
    )
    missing_reason = api_client.post(
        "/admin/repair-actions",
        headers=reviewer_headers,
        json=_repair_payload(reason=""),
    )
    assert missing_reason.status_code == 422

    response = api_client.post(
        "/admin/repair-actions",
        headers=reviewer_headers,
        json=_repair_payload(),
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "requested"
    [event] = session.query(AdminEventLog).all()
    assert event.action == "admin.repair_action.requested"
    assert event.after_state["repair_action"]["status"] == "requested"


def test_data_reviewer_can_only_request_review_repairs(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_limited_repair",
    )

    response = api_client.post(
        "/admin/repair-actions",
        headers=headers,
        json=_repair_payload(
            action_type="recompute_score",
            target_type="region",
            target_id="region_review",
        ),
    )

    assert response.status_code == 400
    assert session.query(AdminRepairAction).count() == 0


def test_admin_execute_recompute_score_uses_scoring_service_path(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_recompute_score",
    )
    repair_id = _create_repair_action(
        api_client,
        admin_headers,
        action_type="recompute_score",
        target_type="region",
        target_id="region_review",
        reason="recompute after reviewed source correction",
    )
    read_only_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.READ_ONLY_OPERATOR,
        subject="auth0|readonly_repair_execute",
    )

    denied = api_client.post(
        f"/admin/repair-actions/{repair_id}/execute",
        headers=read_only_headers,
        json={"reason": "read-only cannot execute"},
    )
    executed = api_client.post(
        f"/admin/repair-actions/{repair_id}/execute",
        headers=admin_headers,
        json={"reason": "run scoring service recompute"},
    )

    assert denied.status_code == 403
    assert executed.status_code == 200
    score = session.query(RegionMarketScore).filter_by(region_id="region_review").one()
    assert score.region_score_id == "rms_region_review"
    assert score.state == "fresh"
    data = executed.json()["data"]
    assert data["status"] == "executed"
    assert data["result"]["action"] == "recompute_score"
    assert data["result"]["outcome"] == "created"
    executed_event = [
        event
        for event in session.query(AdminEventLog).all()
        if event.action == "admin.repair_action.executed"
    ][0]
    assert executed_event.before_state["repair_action"]["status"] == "requested"
    assert executed_event.after_state["repair_action"]["status"] == "executed"


def test_admin_execute_rebuild_output_uses_output_service_path(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    session.add(
        RegionMarketScore(
            region_score_id="rms_region_review",
            region_id="region_review",
            structural_ecosystem_score=0.5,
            live_market_score=0.6,
            objective_opportunity_score=0.7,
            raw_total_score=0.65,
            general_density_score=0.55,
            tech_market_density_score=0.45,
            early_career_accessibility_score=0.7,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()
    output = _output_service(session).build_region("region_review").metadata
    assert output is not None
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_rebuild_output",
    )
    repair_id = _create_repair_action(
        api_client,
        admin_headers,
        action_type="rebuild_output",
        target_type="output",
        target_id=output.output_id,
        reason="rebuild cached output after repair",
    )

    executed = api_client.post(
        f"/admin/repair-actions/{repair_id}/execute",
        headers=admin_headers,
        json={"reason": "use output assembly service"},
    )

    assert executed.status_code == 200
    session.refresh(output)
    assert output.cached_payload is not None
    assert executed.json()["data"]["result"]["action"] == "rebuild_output"


def test_mark_source_stale_preserves_source_history(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session, include_provenance=True)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_source_stale",
    )
    repair_id = _create_repair_action(
        api_client,
        admin_headers,
        action_type="mark_source_stale",
        target_type="source_ref",
        target_id="source_review",
        reason="source evidence is no longer current",
    )

    response = api_client.post(
        f"/admin/repair-actions/{repair_id}/execute",
        headers=admin_headers,
        json={"reason": "mark source stale without deleting history"},
    )

    assert response.status_code == 200
    source = session.get(SourceRef, "source_review")
    assert source is not None
    assert source.state == "stale"
    assert session.query(SourceObservation).count() == 1
    assert session.query(FactSourceLink).count() == 1


def test_deactivate_bad_fact_does_not_delete_provenance_or_source_history(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session, include_provenance=True)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_deactivate_fact",
    )
    presence = session.get(CompanyRegionPresence, "presence_review")
    assert presence is not None
    before_refs = presence.source_refs
    repair_id = _create_repair_action(
        api_client,
        admin_headers,
        action_type="deactivate_bad_fact",
        target_type="presence_fact",
        target_id="presence_review",
        reason="bad fact confirmed by reviewer",
    )

    response = api_client.post(
        f"/admin/repair-actions/{repair_id}/execute",
        headers=admin_headers,
        json={"reason": "deactivate bad fact through state machine"},
    )

    assert response.status_code == 200
    session.refresh(presence)
    assert presence.state == "blocked"
    assert presence.source_refs == before_refs
    assert session.get(SourceRef, "source_review") is not None
    assert session.query(FactSourceLink).count() == 1


def test_request_review_creates_workflow_state_without_canonical_mutation(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    reviewer_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|reviewer_request_review",
    )
    company = session.get(Company, "comp_review")
    assert company is not None
    before = (company.eligibility_status, company.version, company.updated_at)

    repair_id = _create_repair_action(
        api_client,
        reviewer_headers,
        action_type="request_review",
        target_type="company",
        target_id="comp_review",
        reason="needs second reviewer",
    )

    row = session.get(AdminRepairAction, repair_id)
    assert row is not None
    assert row.status == "requested"
    session.refresh(company)
    assert (company.eligibility_status, company.version, company.updated_at) == before


def test_audit_findings_do_not_auto_repair_production_data(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    admin_headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|admin_audit_no_auto_repair",
    )
    company = session.get(Company, "comp_review")
    assert company is not None
    before = (company.eligibility_status, company.version, company.updated_at)

    response = api_client.post(
        "/admin/review/audit-finding-transitions",
        headers=admin_headers,
        json={
            "finding_id": _FINDING_ID,
            "target_state": "acknowledged",
            "reason": "acknowledge without auto repair",
        },
    )

    assert response.status_code == 200
    assert session.query(AdminRepairAction).count() == 0
    session.refresh(company)
    assert (company.eligibility_status, company.version, company.updated_at) == before


def test_invalid_repair_action_type_or_target_is_rejected(
    api_client,
    session: Session,
) -> None:
    _seed_review_rows(session)
    headers, _user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|invalid_repair",
    )

    invalid_type = api_client.post(
        "/admin/repair-actions",
        headers=headers,
        json=_repair_payload(action_type="mutate_anything"),
    )
    incompatible = api_client.post(
        "/admin/repair-actions",
        headers=headers,
        json=_repair_payload(
            action_type="recompute_score",
            target_type="company",
            target_id="comp_review",
        ),
    )

    assert invalid_type.status_code == 422
    assert incompatible.status_code == 400
    assert session.query(AdminRepairAction).count() == 0
