from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from backend.career_identity.exceptions import (
    CareerIdentityStateTransitionError,
    CareerIdentityValidationError,
    CareerIdentityVersionConflict,
)
from backend.career_identity.models import (
    CareerIdentity,
    CareerIdentityFact,
    CareerIdentityImport,
)
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityFactUpdateInput,
    CareerIdentityIngestionRequest,
    CareerIdentityPrivacyInput,
)
from backend.career_identity.service import CareerIdentityService
from backend.users.models import User
from backend.users.repository import UserRepository
from backend.users.service import UserPersonalizationPersistenceService


def _service(session: Session) -> CareerIdentityService:
    return CareerIdentityService(
        CareerIdentityRepository(session),
        UserRepository(session),
    )


def _seed_user(session: Session, user_id: str = "user_career_identity") -> str:
    session.add(User(user_id=user_id))
    session.flush()
    return user_id


def _auth_headers(subject: str = "auth0|career_identity_user") -> dict[str, str]:
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": "career@example.com",
        "email_verified": True,
        "name": "Career User",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _initialize_api_identity(api_client, headers: dict[str, str]) -> tuple[str, int]:
    identity_response = api_client.get("/me/career-identity", headers=headers)
    assert identity_response.status_code == 200
    identity = identity_response.json()["data"]
    version = identity["current_version"]
    consent_response = api_client.put(
        "/me/career-identity/privacy",
        headers=headers,
        json={"ingestion_consent_granted": True, "expected_version": version},
    )
    assert consent_response.status_code == 200
    data = consent_response.json()["data"]
    return data["career_identity_id"], data["current_version"]


def test_identity_lifecycle_version_and_noop_behavior(session: Session) -> None:
    user_id = _seed_user(session)
    svc = _service(session)

    identity = svc.get_or_create_identity(user_id)
    assert identity.user_id == user_id
    assert identity.current_version == 1
    assert svc.view_identity(user_id).current_version == 1

    result = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "Python"},
            state=CareerFactState.EXPLICIT,
        ),
    )
    assert result.outcome == "created"
    assert svc.view_identity(user_id).current_version == 2

    duplicate = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "python"},
            state=CareerFactState.EXPLICIT,
        ),
    )
    assert duplicate.outcome == "duplicate"
    assert svc.view_identity(user_id).current_version == 2


def test_all_fact_types_round_trip_and_validate_constraints(session: Session) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    payloads = [
        (CareerFactType.EDUCATION, {"institution": "State U", "degree_type": "BS"}),
        (
            CareerFactType.EXPERIENCE,
            {"organization": "Acme", "title": "Analyst", "skills": ["SQL"]},
        ),
        (CareerFactType.SKILL, {"name": "SQL"}),
        (CareerFactType.PROJECT, {"name": "Demand Model", "technologies": ["Python"]}),
        (
            CareerFactType.CREDENTIAL,
            {"name": "CPA", "issuer": "Board", "credential_type": "license"},
        ),
        (
            CareerFactType.CAREER_GOAL,
            {"goal_type": "near_term_objective", "description": "Move into analytics"},
        ),
        (CareerFactType.ROLE_PREFERENCE, {"role_title": "Data Analyst"}),
        (
            CareerFactType.INDUSTRY_PREFERENCE,
            {"industry": "Climate", "preference_kind": "preferred"},
        ),
        (
            CareerFactType.GEOGRAPHIC_CONSTRAINT,
            {"location": "Boston", "constraint_kind": "target"},
        ),
        (
            CareerFactType.COMPENSATION_CONSTRAINT,
            {"minimum_amount": 80000, "target_amount": 100000, "currency": "usd"},
        ),
        (
            CareerFactType.TIMING_PREFERENCE,
            {"timing_type": "search_urgency", "urgency": "high"},
        ),
        (
            CareerFactType.WORK_ARRANGEMENT_PREFERENCE,
            {"arrangement": "hybrid", "willingness": "preferred"},
        ),
    ]

    for fact_type, payload in payloads:
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(fact_type=fact_type, payload=payload),
        )

    view = svc.view_identity(user_id)
    assert all(view.facts[fact_type.value] for fact_type, _ in payloads)
    assert view.facts["compensation_constraint"][0]["payload"]["currency"] == "USD"

    with pytest.raises(CareerIdentityValidationError):
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(
                fact_type=CareerFactType.COMPENSATION_CONSTRAINT,
                payload={"minimum_amount": 120000, "target_amount": 100000},
            ),
        )
    with pytest.raises(CareerIdentityValidationError):
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(
                fact_type=CareerFactType.EXPERIENCE,
                payload={
                    "organization": "Acme",
                    "title": "Analyst",
                    "start_date": "2025-01-01",
                    "end_date": "2024-01-01",
                },
            ),
        )
    with pytest.raises(CareerIdentityValidationError):
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(
                fact_type=CareerFactType.GEOGRAPHIC_CONSTRAINT,
                payload={"constraint_kind": "target"},
            ),
        )


def test_provenance_precedence_confirmation_and_state_transitions(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    svc.update_privacy(
        user_id,
        CareerIdentityPrivacyInput(
            ingestion_consent_granted=True,
            inference_consent_granted=True,
        ),
    )

    imported = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "Python"},
            state=CareerFactState.IMPORTED,
        ),
    ).fact
    assert imported.state == "imported"

    confirmed = svc.confirm_fact(user_id, imported.career_identity_fact_id)
    assert confirmed.state == "confirmed"
    version_after_confirm = svc.view_identity(user_id).current_version

    weaker = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "Python"},
            state=CareerFactState.INFERRED,
        ),
    )
    assert weaker.outcome == "protected"
    assert weaker.fact.state == "confirmed"
    assert svc.view_identity(user_id).current_version == version_after_confirm

    with pytest.raises(CareerIdentityStateTransitionError):
        svc.update_fact(
            user_id,
            confirmed.career_identity_fact_id,
            CareerIdentityFactUpdateInput(state=CareerFactState.IMPORTED),
        )


def test_expected_version_conflicts_and_delete_advance_version(session: Session) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    fact = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "SQL"},
        ),
    ).fact
    current_version = svc.view_identity(user_id).current_version

    with pytest.raises(CareerIdentityVersionConflict):
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(
                fact_type=CareerFactType.SKILL,
                payload={"name": "Python"},
                expected_version=current_version - 1,
            ),
        )

    svc.delete_fact(user_id, fact.career_identity_fact_id, expected_version=current_version)
    assert svc.view_identity(user_id).current_version == current_version + 1
    assert session.query(CareerIdentityFact).count() == 0


def test_completeness_and_sufficiency_are_deterministic(session: Session) -> None:
    user_id = _seed_user(session)
    svc = _service(session)

    empty = svc.evaluate(user_id)
    assert empty["completeness_state"] == "empty"
    assert empty["sufficiency_state"] == "insufficient"
    assert "missing_skills" in empty["missing_reason_codes"]

    for fact_type, payload in [
        (
            CareerFactType.EXPERIENCE,
            {"organization": "Acme", "title": "Analyst"},
        ),
        (CareerFactType.SKILL, {"name": "Python"}),
        (
            CareerFactType.CAREER_GOAL,
            {"goal_type": "near_term_objective", "description": "Find analytics role"},
        ),
        (CareerFactType.ROLE_PREFERENCE, {"role_title": "Data Analyst"}),
        (
            CareerFactType.GEOGRAPHIC_CONSTRAINT,
            {"location": "Boston", "constraint_kind": "target"},
        ),
    ]:
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(fact_type=fact_type, payload=payload),
        )

    first = svc.evaluate(user_id)
    second = svc.evaluate(user_id)
    assert first == second
    assert first["sufficiency_state"] == "sufficient"
    assert first["identity_version"] == svc.view_identity(user_id).current_version


def test_resume_ingestion_dedupes_provenance_and_protects_confirmed_facts(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    svc.update_privacy(user_id, CareerIdentityPrivacyInput(ingestion_consent_granted=True))
    explicit = svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "Python"},
            state=CareerFactState.CONFIRMED,
        ),
    ).fact

    request = CareerIdentityIngestionRequest(
        source_type="resume_text",
        source_label="resume.txt",
        consent_granted=True,
        text="""
Skills:
Python, SQL
Education:
State U - BS - Economics
Experience:
Analyst at Acme
Projects:
Labor Market Dashboard
""",
    )
    result = svc.ingest_profile(user_id, request)

    assert result.status == "completed"
    assert result.protected_fact_count == 1
    assert result.created_fact_count >= 4
    assert session.get(CareerIdentityFact, explicit.career_identity_fact_id).state == "confirmed"
    import_row = session.query(CareerIdentityImport).one()
    assert import_row.artifact_metadata["raw_content_retained"] is False

    version_after_import = svc.view_identity(user_id).current_version
    duplicate = svc.ingest_profile(user_id, request)
    assert duplicate.status == "duplicate"
    assert svc.view_identity(user_id).current_version == version_after_import

    structured = svc.ingest_profile(
        user_id,
        CareerIdentityIngestionRequest(
            source_type="structured_profile",
            source_label="profile.json",
            consent_granted=True,
            structured_profile={
                "role_preferences": [{"role_title": "Data Analyst"}],
                "industry_preferences": [{"industry": "Climate"}],
                "geographic_constraints": [
                    {"location": "Boston", "constraint_kind": "target"}
                ],
                "compensation_constraints": [
                    {"minimum_amount": 90000, "currency": "USD"}
                ],
                "timing": [{"timing_type": "search_urgency", "urgency": "medium"}],
                "work_arrangement_preferences": [
                    {"arrangement": "hybrid", "willingness": "preferred"}
                ],
            },
        ),
    )
    assert structured.status == "completed"
    view = svc.view_identity(user_id)
    assert view.facts["role_preference"]
    assert view.facts["work_arrangement_preference"]


def test_ingestion_requires_consent_and_failure_does_not_corrupt_identity(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    before_version = svc.view_identity(user_id).current_version

    with pytest.raises(CareerIdentityValidationError):
        svc.ingest_profile(
            user_id,
            CareerIdentityIngestionRequest(
                source_type="resume_text",
                consent_granted=True,
                text="Skills:\nPython",
            ),
        )

    assert svc.view_identity(user_id).current_version == before_version
    assert session.query(CareerIdentityFact).count() == 0

    with pytest.raises(CareerIdentityValidationError):
        svc.upsert_fact(
            user_id,
            CareerIdentityFactInput(
                fact_type=CareerFactType.SKILL,
                payload={"name": "Inferred Skill"},
                state=CareerFactState.INFERRED,
            ),
        )


def test_ingestion_rolls_back_all_mutations_when_late_fact_validation_fails(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers("auth0|career_identity_atomicity")
    career_identity_id, start_version = _initialize_api_identity(api_client, headers)
    assert session.query(CareerIdentityFact).count() == 0
    assert session.query(CareerIdentityImport).count() == 0

    response = api_client.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "structured_profile",
            "source_label": "profile.json",
            "consent_granted": True,
            "expected_version": start_version,
            "structured_profile": {
                "skills": ["Private Atomicity Skill"],
                "compensation_constraints": [
                    {
                        "minimum_amount": 150000,
                        "target_amount": 100000,
                        "currency": "USD",
                    }
                ],
            },
        },
    )

    assert response.status_code == 422
    assert session.query(CareerIdentityImport).count() == 0
    assert session.query(CareerIdentityFact).count() == 0
    identity = session.get(CareerIdentity, career_identity_id)
    assert identity is not None
    assert identity.current_version == start_version


def test_ingestion_rolls_back_prior_valid_facts_when_later_fact_fails(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers("auth0|career_identity_multifact_rollback")
    career_identity_id, start_version = _initialize_api_identity(api_client, headers)

    response = api_client.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "structured_profile",
            "source_label": "profile.json",
            "consent_granted": True,
            "expected_version": start_version,
            "structured_profile": {
                "skills": ["Python", "SQL"],
                "education": [{"institution": "State U"}],
                "experience": "Software engineer at Acme",
            },
        },
    )

    assert response.status_code == 422
    assert session.query(CareerIdentityImport).count() == 0
    assert session.query(CareerIdentityFact).count() == 0
    identity = session.get(CareerIdentity, career_identity_id)
    assert identity is not None
    assert identity.current_version == start_version


@pytest.mark.parametrize(
    "structured_profile",
    [
        {"skills": {"name": "Python"}},
        {"experience": "Software engineer"},
        {"skills": [{"unexpected": "Private Nested Skill"}]},
        "Private primitive profile",
        {},
    ],
)
def test_malformed_structured_profile_returns_4xx_not_500(
    api_client,
    session: Session,
    structured_profile: object,
) -> None:
    headers = _auth_headers("auth0|career_identity_malformed")
    career_identity_id, start_version = _initialize_api_identity(api_client, headers)

    response = api_client.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "structured_profile",
            "source_label": "profile.json",
            "consent_granted": True,
            "expected_version": start_version,
            "structured_profile": structured_profile,
        },
    )

    assert 400 <= response.status_code < 500
    assert response.status_code != 500
    assert session.query(CareerIdentityImport).count() == 0
    assert session.query(CareerIdentityFact).count() == 0
    identity = session.get(CareerIdentity, career_identity_id)
    assert identity is not None
    assert identity.current_version == start_version


def test_career_identity_validation_errors_do_not_echo_input_values(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers("auth0|career_identity_redaction")
    _initialize_api_identity(api_client, headers)
    sentinel = "SENTINEL_PRIVATE_PROFILE_VALUE_35A"

    fact_response = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "compensation_constraint",
            "payload": {
                "minimum_amount": 150000,
                "target_amount": 100000,
                "currency": "USD",
                "private_note": sentinel,
            },
        },
    )
    structured_response = api_client.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "structured_profile",
            "source_label": "profile.json",
            "consent_granted": True,
            "structured_profile": {"skills": [{"unexpected": sentinel}]},
        },
    )

    for response in (fact_response, structured_response):
        body = json.dumps(response.json())
        assert response.status_code == 422
        assert sentinel not in body
        assert "input_value" not in body
        assert "input_type" not in body


def test_privacy_export_and_deactivation_include_career_identity_without_raw_content(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    svc = _service(session)
    svc.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "SQL"},
        ),
    )

    user_svc = UserPersonalizationPersistenceService(UserRepository(session))
    exported = user_svc.export_user_data(user_id)
    assert exported["career_identity"]["facts"][0]["payload"]["name"] == "SQL"
    assert "raw resume" not in json.dumps(exported).casefold()

    deleted = user_svc.deactivate_user_account(user_id)
    assert deleted.deleted_career_identities == 1
    assert deleted.deleted_career_identity_facts == 1
    assert session.query(CareerIdentity).count() == 0


def test_career_identity_api_is_authenticated_scoped_and_serialized(
    api_client,
    session: Session,
) -> None:
    assert api_client.get("/me/career-identity").status_code == 401

    headers = _auth_headers()
    identity = api_client.get("/me/career-identity", headers=headers)
    assert identity.status_code == 200
    version = identity.json()["data"]["current_version"]

    consent = api_client.put(
        "/me/career-identity/privacy",
        headers=headers,
        json={"ingestion_consent_granted": True, "expected_version": version},
    )
    assert consent.status_code == 200
    version = consent.json()["data"]["current_version"]

    created = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "skill",
            "payload": {"name": "Python"},
            "state": "imported",
            "expected_version": version,
        },
    )
    assert created.status_code == 201
    fact_id = created.json()["data"]["career_identity_fact_id"]
    version = created.json()["data"]["identity"]["current_version"]

    confirmed = api_client.post(
        f"/me/career-identity/facts/{fact_id}/confirm",
        headers=headers,
        json={"expected_version": version},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["facts"]["skill"][0]["state"] == "confirmed"

    other_headers = _auth_headers("auth0|career_identity_other")
    assert (
        api_client.post(
            f"/me/career-identity/facts/{fact_id}/confirm",
            headers=other_headers,
            json={},
        ).status_code
        == 404
    )

    bad_comp = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "compensation_constraint",
            "payload": {"minimum_amount": 10, "target_amount": 1},
        },
    )
    assert bad_comp.status_code == 422

    evaluation = api_client.get("/me/career-identity/evaluation", headers=headers)
    assert evaluation.status_code == 200
    assert evaluation.json()["data"]["identity_version"] == confirmed.json()["data"][
        "current_version"
    ]

    current_version = confirmed.json()["data"]["current_version"]
    ingested = api_client.post(
        "/me/career-identity/ingest",
        headers=headers,
        json={
            "source_type": "profile_text",
            "source_label": "profile.txt",
            "consent_granted": True,
            "expected_version": current_version,
            "text": "Skills:\nSQL",
        },
    )
    assert ingested.status_code == 200
    assert ingested.json()["data"]["status"] == "completed"
    assert ingested.json()["data"]["created_fact_count"] == 1
