from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.ingestion.models import RawIngestionRecord
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.users.exceptions import CrossUserAccessBlocked
from backend.users.models import (
    ExternalAuthIdentity,
    User,
    UserPreferenceProfile,
    UserProfile,
)
from backend.users.repository import UserRepository
from backend.users.service import (
    PersonalizedRecommendationSnapshotInput,
    SavedMarketArtifactInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)

_NOW = datetime(2026, 5, 21, 15, tzinfo=UTC)


def _service(session: Session) -> UserPersonalizationPersistenceService:
    return UserPersonalizationPersistenceService(UserRepository(session))


def _seed_user_account(session: Session, user_id: str) -> None:
    suffix = user_id[-1]
    session.add(
        User(
            user_id=user_id,
        )
    )
    session.flush()
    session.add_all(
        [
            ExternalAuthIdentity(
                external_identity_id=f"external_{user_id}",
                user_id=user_id,
                provider="auth0",
                issuer="https://jmi.us.auth0.com/",
                subject=f"auth0|{user_id}",
                email=f"person-{suffix}@example.com",
                email_verified=True,
                last_seen_at=_NOW,
            ),
            UserProfile(
                user_id=user_id,
                display_name=f"Person {suffix.upper()}",
                email=f"person-{suffix}@example.com",
                avatar_url=f"https://cdn.example.com/{user_id}.png",
            ),
        ]
    )
    session.flush()


def _seed_user_owned_data(session: Session, user_id: str) -> None:
    service = _service(session)
    service.upsert_preference_profile(
        user_id,
        UserPreferenceProfileInput(
            role_interests=[f"role_{user_id}"],
            industry_interests=["software"],
            preferred_regions=["greater_boston"],
            prestige_weighting="medium",
            career_stage="entry_level",
        ),
    )
    service.save_market_artifact(
        user_id,
        SavedMarketArtifactInput(
            artifact_type="region",
            artifact_ref="greater_boston",
            label=f"Boston for {user_id}",
            snapshot={
                "entity_id": "greater_boston",
                "entity_type": "region",
                "saved_from": "privacy_controls",
            },
        ),
    )
    if user_id == "user_a":
        service.save_market_artifact(
            user_id,
            SavedMarketArtifactInput(
                artifact_type="company",
                artifact_ref="comp_a",
                notes="review later",
                snapshot={
                    "entity_id": "comp_a",
                    "entity_type": "company",
                    "saved_from": "privacy_controls",
                },
            ),
        )
    service.create_recommendation_snapshot(
        user_id,
        PersonalizedRecommendationSnapshotInput(
            preference_profile_id=user_id,
            personalized_output={
                "ranked_regions": [{"region_id": "greater_boston", "rank": 1}]
            },
            recommendation_version="personalized_rec_v1",
            source_version_bundle={"region_market_scores": {"greater_boston": 3}},
            objective_output_refs=[
                {"output_type": "region", "subject_id": "greater_boston"}
            ],
            recommendation_inputs_hash=f"sha256:{user_id}",
            generated_at=_NOW,
        ),
    )


def _seed_users_and_personalization(session: Session) -> None:
    for user_id in ("user_a", "user_b"):
        _seed_user_account(session, user_id)
        _seed_user_owned_data(session, user_id)


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
    source_ref = session.get(SourceRef, "source_a")
    observation = session.get(SourceObservation, "obs_a")
    link = session.get(FactSourceLink, "link_score_boston")
    raw = session.get(RawIngestionRecord, "raw_a")
    return {
        "region_version": region.version,
        "region_display_name": region.display_name,
        "company_version": company.version,
        "score_version": score.version,
        "score_value": score.objective_opportunity_score,
        "source_ref_version": source_ref.version,
        "source_ref_collected_at": source_ref.collected_at,
        "observation_version": observation.version,
        "observation_observed_at": observation.observed_at,
        "link_version": link.version,
        "raw_version": raw.version,
        "raw_payload": deepcopy(raw.raw_payload),
        "raw_status": raw.ingestion_status,
    }


def _assert_market_unchanged(session: Session, before: dict) -> None:
    assert _market_state(session) == before


def _seed_everything(session: Session) -> dict:
    _seed_market_rows(session)
    _seed_users_and_personalization(session)
    return _market_state(session)


def test_export_includes_current_user_owned_data_and_excludes_other_users(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    exported = service.export_user_data("user_a")

    assert exported["export_schema_version"] == "layer7_privacy_export_v1"
    assert exported["user"]["user_id"] == "user_a"
    assert exported["profile"]["email"] == "person-a@example.com"
    assert exported["profile"]["created_at"] is not None
    assert exported["external_auth_identities"][0]["subject"] == "auth0|user_a"
    assert exported["preference_profile"]["role_interests"] == ["role_user_a"]
    assert exported["preference_profile"]["created_at"] is not None
    assert {row["artifact_ref"] for row in exported["saved_market_artifacts"]} == {
        "greater_boston",
        "comp_a",
    }
    snapshot = exported["personalized_recommendation_snapshots"][0]
    assert snapshot["recommendation_version"] == "personalized_rec_v1"
    assert snapshot["recommendation_inputs_hash"] == "sha256:user_a"
    assert snapshot["objective_output_refs"] == [
        {"output_type": "region", "subject_id": "greater_boston"}
    ]
    assert snapshot["generated_at"].startswith("2026-05-21T15:00:00")
    assert "user_b" not in json.dumps(exported, sort_keys=True)

    with pytest.raises(CrossUserAccessBlocked):
        service.export_user_data("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_preferences_removes_only_current_user_preferences(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_preference_profile("user_a")

    assert deleted == 1
    assert session.get(UserPreferenceProfile, "user_a") is None
    assert session.get(UserPreferenceProfile, "user_b") is not None
    snapshots = service.list_recommendation_snapshots("user_a")
    assert len(snapshots) == 1
    assert snapshots[0].preference_profile_id is None
    assert service.list_recommendation_snapshots("user_b")[0].preference_profile_id == (
        "user_b"
    )
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_preference_profile("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_saved_artifacts_removes_only_current_user_artifacts(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_saved_market_artifacts("user_a")

    assert deleted == 2
    assert service.list_saved_market_artifacts("user_a") == []
    assert len(service.list_saved_market_artifacts("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_saved_market_artifacts("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_delete_recommendation_snapshots_removes_only_current_user_snapshots(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    deleted = service.delete_recommendation_snapshots("user_a")

    assert deleted == 1
    assert service.list_recommendation_snapshots("user_a") == []
    assert len(service.list_recommendation_snapshots("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_recommendation_snapshots("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_deactivate_account_removes_current_user_owned_layer7_data_only(
    session: Session,
) -> None:
    before = _seed_everything(session)
    service = _service(session)

    result = service.deactivate_user_account("user_a")

    assert result.user_id == "user_a"
    assert result.user_status == "deactivated"
    assert result.deleted_preference_profiles == 1
    assert result.deleted_saved_market_artifacts == 2
    assert result.deleted_recommendation_snapshots == 1
    assert result.deleted_profiles == 1
    assert result.deleted_external_auth_identities == 1
    assert session.get(User, "user_a").status == "deactivated"
    assert session.get(UserProfile, "user_a") is None
    assert UserRepository(session).list_external_identities("user_a") == []
    assert session.get(UserPreferenceProfile, "user_a") is None
    assert service.list_saved_market_artifacts("user_a") == []
    assert service.list_recommendation_snapshots("user_a") == []

    assert session.get(User, "user_b").status == "active"
    assert session.get(UserProfile, "user_b") is not None
    assert len(UserRepository(session).list_external_identities("user_b")) == 1
    assert session.get(UserPreferenceProfile, "user_b") is not None
    assert len(service.list_saved_market_artifacts("user_b")) == 1
    assert len(service.list_recommendation_snapshots("user_b")) == 1
    with pytest.raises(CrossUserAccessBlocked):
        service.deactivate_user_account("user_a", owner_user_id="user_b")
    _assert_market_unchanged(session, before)


def test_privacy_docs_defer_auth0_provider_account_deletion() -> None:
    docs = Path("docs/AUTH_USER_FOUNDATION.md").read_text()
    normalized = " ".join(docs.split())

    assert "Auth0 provider account deletion is deferred" in docs
    assert "does not call Auth0 Management API" in normalized
    assert "public market exploration endpoints remain unauthenticated" in normalized
