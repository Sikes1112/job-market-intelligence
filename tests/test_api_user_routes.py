from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.alerts.repository import AlertRepository
from backend.alerts.service import AlertChangeInput, AlertEventType, AlertService
from backend.career_agent.models import (
    CareerAgentToolAuditEventRecord,
    CareerAgentToolRecord,
    CareerMemoryEntryRecord,
    CareerMemoryPermissionRecord,
)
from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.models import RawIngestionRecord
from backend.monetization.accounts import (
    MonetizationAccountType,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.plans import PlanKey
from backend.monetization.repository import MonetizationRepository
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.users.models import User, UserPreferenceProfile
from backend.users.repository import UserRepository

_NOW = datetime(2026, 5, 21, 16, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|user_a") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
        "picture": f"https://cdn.example.com/{suffix}.png",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client, subject: str = "auth0|user_a") -> str:
    response = api_client.get("/me", headers=_auth_headers(subject))
    assert response.status_code == 200
    return response.json()["data"]["user"]["user_id"]


def _assign_paid_plan(
    api_client,
    session: Session,
    subject: str = "auth0|user_a",
    plan_key: PlanKey = PlanKey.INDIVIDUAL_MONTHLY,
) -> str:
    user_id = _current_user_id(api_client, subject)
    repo = MonetizationRepository(session)
    account = repo.ensure_account_for_user(
        user_id=user_id,
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=plan_key.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.TEST_FIXTURE,
        effective_at=_NOW,
    )
    return user_id


def _alert_service(session: Session) -> AlertService:
    return AlertService(AlertRepository(session))


def _seed_market_rows(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
            SourceRef(
                source_id="source_a",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
            ),
            OutputMetadata(
                output_id="out_region_boston",
                output_type="region_output",
                subject_id="greater_boston",
                source_version_bundle={"source_a": 4},
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                score_ruleset_version="marketscore_v1",
                source_version_bundle={"source_a": 4},
            ),
            SourceObservation(
                observation_id="obs_a",
                source_id="source_a",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            FactSourceLink(
                link_id="link_score_boston",
                observation_id="obs_a",
                source_id="source_a",
                fact_type="region_score",
                fact_id="score_boston",
                fact_field="objective_opportunity_score",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                collected_at=_NOW,
                observed_at=_NOW,
                license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
                confidence=Confidence.HIGH.value,
                data_origin=DataOrigin.REAL_OBSERVED.value,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
            ),
            RawIngestionRecord(
                raw_record_id="raw_a",
                provider_id="manual",
                source_type=SourceType.COMPANY_OFFICIAL.value,
                source_name="Example Careers",
                url_or_provider="https://example.test/careers",
                external_entity_id="greater_boston",
                raw_payload={"objective_opportunity_score": 0.74},
                normalized_payload={"region_id": "greater_boston"},
                payload_checksum="checksum_a",
                schema_version="manual_v1",
                collected_at=_NOW,
                observed_at=_NOW,
                ingestion_status="stored",
                normalization_status="normalized",
                intended_fact_type="region_score",
                source_id="source_a",
                observation_id="obs_a",
            ),
        ]
    )
    session.flush()


def _market_state(session: Session) -> dict:
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    score = session.get(RegionMarketScore, "score_boston")
    source = session.get(SourceRef, "source_a")
    observation = session.get(SourceObservation, "obs_a")
    link = session.get(FactSourceLink, "link_score_boston")
    raw = session.get(RawIngestionRecord, "raw_a")
    output = session.get(OutputMetadata, "out_region_boston")
    return {
        "region": (region.display_name, region.version),
        "company": (company.company_name, company.version),
        "score": (score.objective_opportunity_score, score.version),
        "source": (source.collected_at, source.version),
        "observation": (observation.observed_at, observation.version),
        "link": (link.fact_id, link.version),
        "raw": (deepcopy(raw.raw_payload), raw.version),
        "output": (deepcopy(output.source_version_bundle), output.version),
    }


def test_get_current_user_profile_requires_verified_claims(api_client) -> None:
    unauthenticated = api_client.get("/me")
    assert unauthenticated.status_code == 401

    response = api_client.get("/me", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["user"]["user_id"].startswith("user_")
    assert body["data"]["user"]["status"] == "active"
    assert body["data"]["profile"]["email"] == "user_a@example.com"


def test_preferences_get_update_delete_for_current_user(api_client) -> None:
    headers = _auth_headers()

    initial = api_client.get("/me/preferences", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["persisted"] is False
    assert initial.json()["data"]["scoring_weights"]["entry_level_access"] == 0.3

    updated = api_client.put(
        "/me/preferences",
        headers=headers,
        json={
            "role_interests": ["product"],
            "industry_interests": ["software"],
            "preferred_regions": ["greater_boston"],
            "prestige_weighting": "medium",
            "career_stage": "entry_level",
            "scoring_weights": {
                "entry_level_access": 0.4,
                "hiring_density": 0.2,
                "prestige": 0.1,
                "industry_fit": 0.2,
                "role_fit": 0.1,
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["persisted"] is True
    assert updated.json()["data"]["role_interests"] == ["product"]
    assert updated.json()["data"]["scoring_weights"]["entry_level_access"] == 0.4

    fetched = api_client.get("/me/preferences", headers=headers)
    assert fetched.json()["data"]["preferred_regions"] == ["greater_boston"]

    deleted = api_client.delete("/me/preferences", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_preference_profiles"] == 1
    assert api_client.get("/me/preferences", headers=headers).json()["data"]["persisted"] is False


def test_saved_market_artifacts_create_list_get_delete_for_current_user(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers()
    _assign_paid_plan(api_client, session)

    created = api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={
            "artifact_type": "role_family",
            "artifact_ref": "product",
            "label": "Product",
            "snapshot": {"saved_from": "region_role_family"},
        },
    )

    assert created.status_code == 201
    artifact = created.json()["data"]
    assert artifact["artifact_type"] == "role_family"

    listed = api_client.get("/me/saved-market-artifacts", headers=headers)
    listed_ids = [
        row["saved_artifact_id"]
        for row in listed.json()["data"]["saved_market_artifacts"]
    ]
    assert listed_ids == [artifact["saved_artifact_id"]]

    fetched = api_client.get(
        f"/me/saved-market-artifacts/{artifact['saved_artifact_id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["artifact_ref"] == "product"

    deleted = api_client.delete(
        f"/me/saved-market-artifacts/{artifact['saved_artifact_id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert api_client.get("/me/saved-market-artifacts", headers=headers).json()["data"][
        "saved_market_artifacts"
    ] == []


def test_saved_market_artifact_rejects_unsafe_snapshot_payload(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers()
    _assign_paid_plan(api_client, session)

    response = api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={
            "artifact_type": "region",
            "artifact_ref": "greater_boston",
            "snapshot": {
                "entity_id": "greater_boston",
                "entity_type": "region",
                "score": 0.74,
                "sources": ["source_a"],
            },
        },
    )

    assert response.status_code == 422
    listed = api_client.get("/me/saved-market-artifacts", headers=headers)
    assert listed.json()["data"]["saved_market_artifacts"] == []


def test_alert_feed_list_read_and_dismiss_for_current_user(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers()
    user_id = _assign_paid_plan(api_client, session)
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={"artifact_type": "company", "artifact_ref": "comp_a"},
    )
    service = _alert_service(session)
    event = service.create_event(
        AlertChangeInput(
            event_type=AlertEventType.NEW_HIRING_ACTIVITY,
            company_id="comp_a",
            region_id="greater_boston",
            previous_value={"currently_hiring_flag": False},
            new_value={"currently_hiring_flag": True},
            change_summary={
                "changed_fields": ["currently_hiring_flag"],
                "source_ref_count": 1,
            },
            freshness_status="fresh",
            source_refs=["source_ref:careers"],
            change_basis_refs=["company_region_hiring:h_a:v2"],
            detection_basis="structured_refreshable_state",
        )
    )
    service.materialize_user_alerts_for_event(event)

    listed = api_client.get("/me/alerts", headers=headers)
    assert listed.status_code == 200
    alert = listed.json()["data"]["alerts"][0]
    assert alert["user_id"] == user_id
    assert alert["event"]["event_type"] == "new_hiring_activity"
    assert alert["event"]["company_id"] == "comp_a"
    assert alert["relevance"]["reason"] == "saved_company"
    assert "company_name" not in str(alert)

    read = api_client.post(f"/me/alerts/{alert['user_alert_id']}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["data"]["is_read"] is True
    dismissed = api_client.post(
        f"/me/alerts/{alert['user_alert_id']}/dismiss",
        headers=headers,
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["data"]["dismissed"] is True

    visible = api_client.get("/me/alerts", headers=headers)
    assert visible.json()["data"]["alerts"] == []
    included = api_client.get("/me/alerts?include_dismissed=true", headers=headers)
    assert len(included.json()["data"]["alerts"]) == 1


def test_recommendation_snapshots_create_list_get_for_current_user(api_client) -> None:
    headers = _auth_headers()
    user_id = _current_user_id(api_client)
    api_client.put(
        "/me/preferences",
        headers=headers,
        json={
            "role_interests": ["product"],
            "preferred_regions": ["greater_boston"],
        },
    )

    created = api_client.post(
        "/me/recommendation-snapshots",
        headers=headers,
        json={
            "preference_profile_id": user_id,
            "personalized_output": {"ranked_regions": [{"region_id": "greater_boston"}]},
            "recommendation_version": "personalized_rec_v1",
            "source_version_bundle": {"region_market_scores": {"greater_boston": 3}},
            "objective_output_refs": [
                {"output_type": "region", "subject_id": "greater_boston"}
            ],
            "recommendation_inputs_hash": "sha256:user-a-inputs",
            "generated_at": _NOW.isoformat(),
        },
    )

    assert created.status_code == 201
    snapshot = created.json()["data"]
    assert snapshot["recommendation_version"] == "personalized_rec_v1"
    assert snapshot["recommendation_inputs_hash"] == "sha256:user-a-inputs"

    listed = api_client.get("/me/recommendation-snapshots", headers=headers)
    assert listed.status_code == 200
    assert [row["recommendation_snapshot_id"] for row in listed.json()["data"][
        "personalized_recommendation_snapshots"
    ]] == [snapshot["recommendation_snapshot_id"]]

    fetched = api_client.get(
        f"/me/recommendation-snapshots/{snapshot['recommendation_snapshot_id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["objective_output_refs"] == [
        {"output_type": "region", "subject_id": "greater_boston"}
    ]


def test_scoring_preview_uses_saved_controls_without_persisting_overlay(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers()
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
                sector_primary="ai",
                prestige_score=0.8,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_a",
                company_id="comp_a",
                region_id="greater_boston",
                presence_status="present",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_a",
                company_id="comp_a",
                region_id="greater_boston",
                currently_hiring_flag=True,
                role_family_summary={"product": 5},
            ),
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                live_market_score=0.5,
                early_career_accessibility_score=0.6,
                score_ruleset_version="marketscore_v1",
            ),
        ]
    )
    session.flush()
    before_version = session.get(RegionMarketScore, "score_boston").version

    api_client.put(
        "/me/preferences",
        headers=headers,
        json={
            "role_interests": ["product"],
            "industry_interests": ["ai"],
            "preferred_regions": ["greater_boston"],
            "scoring_weights": {
                "entry_level_access": 0.4,
                "hiring_density": 0.2,
                "prestige": 0.1,
                "industry_fit": 0.2,
                "role_fit": 0.1,
            },
        },
    )
    response = api_client.post(
        "/me/scoring-preview",
        headers=headers,
        json={"region_ids": ["greater_boston"]},
    )

    assert response.status_code == 200
    body = response.json()
    region = body["data"]["regions"][0]
    assert region["canonical_default_scores"]["objective_opportunity_score"] == 0.74
    assert region["personalized_overlay_score"] is not None
    assert region["components"]["entry_level_access"]["status"] == "used"
    assert body["data"]["scoring_weights"]["entry_level_access"] == 0.4
    assert body["metadata"]["warnings"] == []
    session.refresh(session.get(RegionMarketScore, "score_boston"))
    assert session.get(RegionMarketScore, "score_boston").version == before_version


def test_malformed_stored_scoring_weights_fall_back_to_defaults_in_api(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers()
    user_id = _current_user_id(api_client)
    session.add(
        UserPreferenceProfile(
            user_id=user_id,
            role_interests=["product"],
            industry_interests=[],
            preferred_regions=["greater_boston"],
            scoring_weights={"entry_level_access": "bad"},
        )
    )
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id="score_boston_malformed_weights",
            region_id="greater_boston",
            objective_opportunity_score=0.74,
            live_market_score=0.5,
            early_career_accessibility_score=0.6,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()

    preferences = api_client.get("/me/preferences", headers=headers)
    preview = api_client.post(
        "/me/scoring-preview",
        headers=headers,
        json={"region_ids": ["greater_boston"]},
    )

    assert preferences.status_code == 200
    assert preferences.json()["data"]["scoring_weights"]["entry_level_access"] == 0.3
    assert preview.status_code == 200
    assert preview.json()["data"]["scoring_weights"]["hiring_density"] == 0.25
    assert preview.json()["data"]["regions"][0]["personalized_overlay_score"] is not None


def test_export_and_deactivate_current_user_data(api_client, session) -> None:
    headers = _auth_headers()
    user_id = _assign_paid_plan(api_client, session)
    api_client.put(
        "/me/preferences",
        headers=headers,
        json={"role_interests": ["product"]},
    )
    api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={"artifact_type": "company", "artifact_ref": "comp_a"},
    )
    memory = api_client.put(
        "/me/career-memory",
        headers=headers,
        json={
            "explicit_user_permission": True,
            "permissions": [
                {
                    "category": "career_constraints",
                    "enabled": True,
                    "personalize_allowed": True,
                    "visibility": "private",
                }
            ],
            "entries": [
                {
                    "category": "career_constraints",
                    "value": "hybrid only",
                }
            ],
            "replace_categories": ["career_constraints"],
        },
    )
    assert memory.status_code == 200
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="metro",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id="score_career_agent_cleanup",
            region_id="greater_boston",
            objective_opportunity_score=0.74,
            live_market_score=0.5,
            early_career_accessibility_score=0.66,
            score_ruleset_version="career_agent_cleanup_test",
        )
    )
    session.flush()
    tool_preview = api_client.post(
        "/me/career-agent/tools/preview",
        headers=headers,
        json={
            "tool_type": "reminder",
            "career_agent_request": {
                "question_type": "city_fit",
                "target_region_ids": ["greater_boston"],
                "include_forecasts": False,
            },
        },
    )
    assert tool_preview.status_code == 200
    tool_id = tool_preview.json()["data"]["tool_request_id"]

    exported = api_client.get("/me/export", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["data"]["user"]["user_id"] == user_id
    assert exported.json()["data"]["preference_profile"]["role_interests"] == ["product"]
    assert exported.json()["data"]["saved_market_artifacts"][0]["artifact_ref"] == "comp_a"
    exported_text = json.dumps(exported.json())
    assert "hybrid only" not in exported_text
    assert tool_id not in exported_text
    assert "career_memory" not in exported_text
    assert "career_agent_tool" not in exported_text

    deactivated = api_client.delete("/me", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["user_status"] == "deactivated"
    assert session.get(User, user_id).status == "deactivated"
    assert UserRepository(session).list_external_identities(user_id) == []
    assert session.query(CareerMemoryPermissionRecord).filter_by(user_id=user_id).all() == []
    assert session.query(CareerMemoryEntryRecord).filter_by(user_id=user_id).all() == []
    assert session.query(CareerAgentToolAuditEventRecord).filter_by(user_id=user_id).all() == []
    assert session.query(CareerAgentToolRecord).filter_by(user_id=user_id).all() == []


def test_cross_user_route_access_is_blocked_or_excluded(api_client, session: Session) -> None:
    user_a_headers = _auth_headers("auth0|user_a")
    user_b_headers = _auth_headers("auth0|user_b")
    user_b_id = _assign_paid_plan(api_client, session, "auth0|user_b")
    api_client.put(
        "/me/preferences",
        headers=user_b_headers,
        json={"role_interests": ["finance"]},
    )
    user_b_artifact = api_client.post(
        "/me/saved-market-artifacts",
        headers=user_b_headers,
        json={"artifact_type": "region", "artifact_ref": "greater_boston"},
    ).json()["data"]
    user_b_snapshot = api_client.post(
        "/me/recommendation-snapshots",
        headers=user_b_headers,
        json={
            "preference_profile_id": user_b_id,
            "personalized_output": {"ranked_regions": [{"region_id": "greater_boston"}]},
            "recommendation_version": "personalized_rec_v1",
            "source_version_bundle": {"region_market_scores": {"greater_boston": 3}},
            "objective_output_refs": ["region:greater_boston:v3"],
            "recommendation_inputs_hash": "sha256:user-b",
            "generated_at": _NOW.isoformat(),
        },
    ).json()["data"]

    assert api_client.get("/me/preferences", headers=user_a_headers).json()["data"][
        "persisted"
    ] is False
    assert api_client.get("/me/saved-market-artifacts", headers=user_a_headers).json()[
        "data"
    ]["saved_market_artifacts"] == []
    assert api_client.get("/me/recommendation-snapshots", headers=user_a_headers).json()[
        "data"
    ]["personalized_recommendation_snapshots"] == []
    assert api_client.get(
        f"/me/saved-market-artifacts/{user_b_artifact['saved_artifact_id']}",
        headers=user_a_headers,
    ).status_code == 404
    assert api_client.get(
        f"/me/recommendation-snapshots/{user_b_snapshot['recommendation_snapshot_id']}",
        headers=user_a_headers,
    ).status_code == 404


def test_public_market_routes_remain_unauthenticated(api_client, session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()

    response = api_client.get("/regions")

    assert response.status_code == 200
    assert response.json()["data"]["regions"][0]["region_id"] == "greater_boston"


def test_protected_user_routes_do_not_mutate_canonical_market_rows(
    api_client,
    session,
) -> None:
    _seed_market_rows(session)
    before = _market_state(session)
    headers = _auth_headers()
    user_id = _assign_paid_plan(api_client, session)

    api_client.put(
        "/me/preferences",
        headers=headers,
        json={
            "role_interests": ["product"],
            "preferred_regions": ["greater_boston"],
        },
    )
    artifact = api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={
            "artifact_type": "region",
            "artifact_ref": "greater_boston",
            "snapshot": {
                "entity_id": "greater_boston",
                "entity_type": "region",
                "label": "User label",
            },
        },
    ).json()["data"]
    snapshot = api_client.post(
        "/me/recommendation-snapshots",
        headers=headers,
        json={
            "preference_profile_id": user_id,
            "personalized_output": {
                "ranked_regions": [
                    {"region_id": "greater_boston", "objective_opportunity_score": 999}
                ]
            },
            "recommendation_version": "personalized_rec_v1",
            "source_version_bundle": {"region_market_scores": {"greater_boston": 3}},
            "objective_output_refs": [
                {"output_type": "region", "subject_id": "greater_boston"}
            ],
            "recommendation_inputs_hash": "sha256:boundary",
            "generated_at": _NOW.isoformat(),
        },
    ).json()["data"]
    api_client.get("/me/export", headers=headers)
    api_client.delete("/me/preferences", headers=headers)
    api_client.delete(
        f"/me/saved-market-artifacts/{artifact['saved_artifact_id']}",
        headers=headers,
    )
    assert snapshot["recommendation_snapshot_id"]
    api_client.delete("/me", headers=headers)

    assert _market_state(session) == before
