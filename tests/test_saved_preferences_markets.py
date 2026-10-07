from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.personalization.controls import ScoringWeightsInput
from backend.scoring.models import RegionMarketScore
from backend.users.exceptions import (
    CrossUserAccessBlocked,
    InvalidSavedMarketArtifactType,
    SavedMarketArtifactNotFound,
)
from backend.users.models import User, UserPreferenceProfile
from backend.users.repository import UserRepository
from backend.users.service import (
    SavedMarketArtifactInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)


def _service(session: Session) -> UserPersonalizationPersistenceService:
    return UserPersonalizationPersistenceService(UserRepository(session))


def _seed_users(session: Session) -> None:
    session.add_all(
        [
            User(user_id="user_a"),
            User(user_id="user_b"),
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="sf_bay_area",
                region_name="sf_bay_area",
                display_name="SF Bay Area",
                region_type="greater_region",
            ),
        ]
    )
    session.flush()


def _seed_market_rows(session: Session) -> None:
    session.add_all(
        [
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id="score_boston",
            region_id="greater_boston",
            objective_opportunity_score=0.74,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()


def test_get_preferences_returns_safe_defaults_for_empty_user(session: Session) -> None:
    _seed_users(session)

    view = _service(session).get_preference_profile("user_a")

    assert view.user_id == "user_a"
    assert view.persisted is False
    assert view.role_interests == []
    assert view.industry_interests == []
    assert view.preferred_regions == []
    assert view.prestige_weighting is None
    assert view.remote_hybrid_preference is None
    assert view.scoring_weights.entry_level_access == 0.30


def test_create_update_get_preferences_for_user(session: Session) -> None:
    _seed_users(session)
    service = _service(session)

    created = service.upsert_preference_profile(
        "user_a",
        UserPreferenceProfileInput(
            role_interests=["product", "ai_cloud_adjacent"],
            industry_interests=["ai", "cloud"],
            preferred_regions=["greater_boston", "sf_bay_area"],
            prestige_weighting="high",
            brand_weighting="medium",
            career_stage="entry_level",
            remote_hybrid_preference="hybrid",
            scoring_weights=ScoringWeightsInput(
                entry_level_access=0.4,
                hiring_density=0.2,
                prestige=0.1,
                industry_fit=0.2,
                role_fit=0.1,
            ),
        ),
    )

    assert created.persisted is True
    assert created.role_interests == ["product", "ai_cloud_adjacent"]
    assert created.prestige_weighting == "high"
    assert created.scoring_weights.entry_level_access == 0.4

    updated = service.upsert_preference_profile(
        "user_a",
        UserPreferenceProfileInput(
            role_interests=["product"],
            industry_interests=["software"],
            preferred_regions=["greater_boston"],
            prestige_weighting="low",
            brand_weighting="low",
            career_stage="entry_level",
            remote_hybrid_preference="remote",
            scoring_weights=ScoringWeightsInput(
                entry_level_access=0.2,
                hiring_density=0.3,
                prestige=0.1,
                industry_fit=0.2,
                role_fit=0.2,
            ),
        ),
    )
    fetched = service.get_preference_profile("user_a")

    assert updated.role_interests == ["product"]
    assert fetched.industry_interests == ["software"]
    assert fetched.preferred_regions == ["greater_boston"]
    assert fetched.prestige_weighting == "low"
    assert fetched.remote_hybrid_preference == "remote"
    assert fetched.scoring_weights.hiring_density == 0.3


def test_malformed_stored_scoring_weights_fall_back_to_defaults(
    session: Session,
) -> None:
    _seed_users(session)
    session.add(
        UserPreferenceProfile(
            user_id="user_a",
            role_interests=["product"],
            industry_interests=[],
            preferred_regions=[],
            scoring_weights={"entry_level_access": "not-a-number"},
        )
    )
    session.flush()

    view = _service(session).get_preference_profile("user_a")

    assert view.persisted is True
    assert view.role_interests == ["product"]
    assert view.scoring_weights.entry_level_access == 0.30
    assert view.scoring_weights.hiring_density == 0.25


def test_preference_updates_do_not_modify_market_truth(session: Session) -> None:
    _seed_users(session)
    _seed_market_rows(session)
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    score = session.get(RegionMarketScore, "score_boston")
    region_version = region.version
    company_version = company.version
    score_version = score.version
    score_value = score.objective_opportunity_score

    _service(session).upsert_preference_profile(
        "user_a",
        UserPreferenceProfileInput(
            role_interests=["product"],
            preferred_regions=["greater_boston"],
            prestige_weighting="medium",
        ),
    )

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    assert region.version == region_version
    assert company.version == company_version
    assert score.version == score_version
    assert score.objective_opportunity_score == score_value


def test_cross_user_preference_access_is_blocked(session: Session) -> None:
    _seed_users(session)
    service = _service(session)
    service.upsert_preference_profile(
        "user_b",
        UserPreferenceProfileInput(role_interests=["product"]),
    )

    with pytest.raises(CrossUserAccessBlocked):
        service.get_preference_profile("user_a", owner_user_id="user_b")
    with pytest.raises(CrossUserAccessBlocked):
        service.upsert_preference_profile(
            "user_a",
            UserPreferenceProfileInput(role_interests=["cloud"]),
            owner_user_id="user_b",
        )


@pytest.mark.parametrize(
    ("artifact_type", "artifact_ref"),
    [
        ("region", "greater_boston"),
        ("company", "comp_a"),
        ("role_family", "product"),
        ("comparison", "greater_boston__greater_sf"),
        ("discovery_result", "discovery:user_a:query_001"),
    ],
)
def test_save_list_delete_market_artifact_types(
    session: Session,
    artifact_type: str,
    artifact_ref: str,
) -> None:
    _seed_users(session)
    service = _service(session)

    saved = service.save_market_artifact(
        "user_a",
        SavedMarketArtifactInput(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            artifact_ref=artifact_ref,
            label=f"Saved {artifact_type}",
            notes="review later",
            snapshot={
                "entity_id": artifact_ref,
                "entity_type": artifact_type,
                "saved_from": "test",
            },
        ),
    )

    assert saved.user_id == "user_a"
    assert saved.artifact_type == artifact_type
    assert saved.artifact_ref == artifact_ref
    assert saved.snapshot == {
        "entity_id": artifact_ref,
        "entity_type": artifact_type,
        "saved_from": "test",
    }

    listed = service.list_saved_market_artifacts("user_a", artifact_type=artifact_type)
    assert [row.saved_artifact_id for row in listed] == [saved.saved_artifact_id]
    assert service.list_saved_market_artifacts("user_b") == []

    fetched = service.get_saved_market_artifact("user_a", saved.saved_artifact_id)
    assert fetched.saved_artifact_id == saved.saved_artifact_id

    service.delete_saved_market_artifact("user_a", saved.saved_artifact_id)
    assert service.list_saved_market_artifacts("user_a") == []
    with pytest.raises(SavedMarketArtifactNotFound):
        service.get_saved_market_artifact("user_a", saved.saved_artifact_id)


def test_invalid_saved_artifact_type_fails(session: Session) -> None:
    _seed_users(session)
    service = _service(session)

    with pytest.raises(ValidationError):
        SavedMarketArtifactInput(artifact_type="job", artifact_ref="job_1")  # type: ignore[arg-type]
    with pytest.raises(InvalidSavedMarketArtifactType):
        service.list_saved_market_artifacts("user_a", artifact_type="job")


@pytest.mark.parametrize(
    "snapshot",
    [
        {"score": 0.74},
        {"scores": {"objective_opportunity_score": 0.74}},
        {"freshness": {"state": "fresh"}},
        {"provenance": {"source_id": "source_a"}},
        {"sources": ["source_a"]},
        {"source_summary": {"source_count": 1}},
        {"evidence": ["source_a"]},
        {"companies": [{"company_id": "comp_a"}]},
        {"regions": [{"region_id": "greater_boston"}]},
        {"market_output": {"region_id": "greater_boston"}},
        {"output": {"payload": {}}},
        {"hiring": {"currently_hiring_flag": True}},
        {"entry_level_signal": {"internship_count": 2}},
        {"company_detail": {"company_id": "comp_a"}},
        {"region_detail": {"region_id": "greater_boston"}},
        {"filters": {"score": 0.8}},
    ],
)
def test_saved_artifact_snapshot_rejects_copied_market_facts(
    session: Session,
    snapshot: dict,
) -> None:
    _seed_users(session)

    with pytest.raises(ValidationError):
        SavedMarketArtifactInput(
            artifact_type="region",
            artifact_ref="greater_boston",
            snapshot=snapshot,
        )

    assert _service(session).list_saved_market_artifacts("user_a") == []


def test_cross_user_saved_artifact_access_is_blocked(session: Session) -> None:
    _seed_users(session)
    service = _service(session)
    saved = service.save_market_artifact(
        "user_b",
        SavedMarketArtifactInput(
            artifact_type="region",
            artifact_ref="greater_boston",
        ),
    )

    with pytest.raises(CrossUserAccessBlocked):
        service.get_saved_market_artifact("user_a", saved.saved_artifact_id)
    with pytest.raises(CrossUserAccessBlocked):
        service.delete_saved_market_artifact("user_a", saved.saved_artifact_id)
    assert service.list_saved_market_artifacts("user_a") == []
    assert len(service.list_saved_market_artifacts("user_b")) == 1


def test_saved_artifact_snapshot_does_not_modify_market_truth(session: Session) -> None:
    _seed_users(session)
    _seed_market_rows(session)
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    score = session.get(RegionMarketScore, "score_boston")
    region_version = region.version
    company_version = company.version
    score_version = score.version

    _service(session).save_market_artifact(
        "user_a",
        SavedMarketArtifactInput(
            artifact_type="region",
            artifact_ref="greater_boston",
            snapshot={
                "entity_id": "greater_boston",
                "entity_type": "region",
                "label": "User label only",
            },
        ),
    )

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    assert region.version == region_version
    assert company.version == company_version
    assert score.version == score_version
    assert region.display_name == "Greater Boston"
    assert score.objective_opportunity_score == 0.74
