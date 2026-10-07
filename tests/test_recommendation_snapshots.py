from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.users.exceptions import (
    CrossUserAccessBlocked,
    PreferenceProfileNotFound,
    RecommendationSnapshotNotFound,
)
from backend.users.models import User
from backend.users.repository import UserRepository
from backend.users.service import (
    PersonalizedRecommendationSnapshotInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)

_NOW = datetime(2026, 5, 21, 14, tzinfo=UTC)


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
        ]
    )
    session.flush()


def _seed_preference(session: Session, user_id: str = "user_a") -> None:
    _service(session).upsert_preference_profile(
        user_id,
        UserPreferenceProfileInput(
            role_interests=["product"],
            preferred_regions=["greater_boston"],
            prestige_weighting="medium",
        ),
    )


def _snapshot_input(
    *,
    generated_at: datetime = _NOW,
    preference_profile_id: str | None = "user_a",
    recommendation_version: str = "personalized_rec_v1",
    recommendation_inputs_hash: str = "sha256:input-bundle-a",
) -> PersonalizedRecommendationSnapshotInput:
    return PersonalizedRecommendationSnapshotInput(
        preference_profile_id=preference_profile_id,
        personalized_output={
            "ranked_regions": [
                {
                    "region_id": "greater_boston",
                    "personalized_rank": 1,
                    "personalized_score": 0.91,
                }
            ],
        },
        recommendation_version=recommendation_version,
        source_version_bundle={
            "region_market_scores": {"greater_boston": 3},
            "source_refs": {"source_a": 4},
        },
        objective_output_refs=[
            {
                "output_type": "region",
                "subject_id": "greater_boston",
                "version": 3,
            },
            "company:comp_a:v2",
        ],
        recommendation_inputs_hash=recommendation_inputs_hash,
        generated_at=generated_at,
    )


def _seed_market_rows(session: Session) -> None:
    session.add_all(
        [
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
    session.add(
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
        )
    )
    session.flush()


def test_create_recommendation_snapshot_for_user(session: Session) -> None:
    _seed_users(session)
    _seed_preference(session)

    snapshot = _service(session).create_recommendation_snapshot(
        "user_a",
        _snapshot_input(),
    )

    assert snapshot.user_id == "user_a"
    assert snapshot.preference_profile_id == "user_a"
    assert snapshot.recommendation_snapshot_id.startswith("recommendation_snapshot_")
    assert snapshot.personalized_output["ranked_regions"][0]["region_id"] == ("greater_boston")
    assert snapshot.recommendation_version == "personalized_rec_v1"
    assert snapshot.source_version_bundle == {
        "region_market_scores": {"greater_boston": 3},
        "source_refs": {"source_a": 4},
    }
    assert snapshot.objective_output_refs[0]["output_type"] == "region"
    assert snapshot.recommendation_inputs_hash == "sha256:input-bundle-a"
    assert snapshot.generated_at == _NOW


def test_list_and_get_recommendation_snapshots_for_same_user(
    session: Session,
) -> None:
    _seed_users(session)
    _seed_preference(session)
    service = _service(session)
    older = service.create_recommendation_snapshot(
        "user_a",
        _snapshot_input(
            generated_at=_NOW - timedelta(hours=1),
            recommendation_inputs_hash="sha256:older",
        ),
    )
    newer = service.create_recommendation_snapshot(
        "user_a",
        _snapshot_input(
            generated_at=_NOW,
            recommendation_inputs_hash="sha256:newer",
        ),
    )

    listed = service.list_recommendation_snapshots("user_a")
    assert [row.recommendation_snapshot_id for row in listed] == [
        newer.recommendation_snapshot_id,
        older.recommendation_snapshot_id,
    ]
    fetched = service.get_recommendation_snapshot(
        "user_a",
        older.recommendation_snapshot_id,
    )
    assert fetched.recommendation_snapshot_id == older.recommendation_snapshot_id


def test_cross_user_snapshot_access_is_blocked_or_excluded(session: Session) -> None:
    _seed_users(session)
    _seed_preference(session, "user_b")
    service = _service(session)
    saved = service.create_recommendation_snapshot(
        "user_b",
        _snapshot_input(preference_profile_id="user_b"),
    )

    assert service.list_recommendation_snapshots("user_a") == []
    with pytest.raises(CrossUserAccessBlocked):
        service.list_recommendation_snapshots("user_a", owner_user_id="user_b")
    with pytest.raises(CrossUserAccessBlocked):
        service.get_recommendation_snapshot(
            "user_a",
            saved.recommendation_snapshot_id,
        )
    with pytest.raises(CrossUserAccessBlocked):
        service.create_recommendation_snapshot(
            "user_a",
            _snapshot_input(preference_profile_id="user_b"),
        )


def test_snapshot_can_omit_preference_profile_id(session: Session) -> None:
    _seed_users(session)

    snapshot = _service(session).create_recommendation_snapshot(
        "user_a",
        _snapshot_input(preference_profile_id=None),
    )

    assert snapshot.preference_profile_id is None


def test_snapshot_rejects_missing_preference_profile(session: Session) -> None:
    _seed_users(session)

    with pytest.raises(PreferenceProfileNotFound):
        _service(session).create_recommendation_snapshot(
            "user_a",
            _snapshot_input(preference_profile_id="user_a"),
        )


def test_generated_at_is_distinct_from_source_version_bundle(session: Session) -> None:
    _seed_users(session)
    _seed_preference(session)

    snapshot = _service(session).create_recommendation_snapshot(
        "user_a",
        _snapshot_input(generated_at=_NOW),
    )

    assert snapshot.generated_at == _NOW
    assert snapshot.source_version_bundle == {
        "region_market_scores": {"greater_boston": 3},
        "source_refs": {"source_a": 4},
    }
    assert "generated_at" not in snapshot.source_version_bundle


def test_recommendation_version_is_required() -> None:
    with pytest.raises(ValidationError):
        _snapshot_input(recommendation_version=" ")


def test_missing_snapshot_raises_not_found(session: Session) -> None:
    _seed_users(session)

    with pytest.raises(RecommendationSnapshotNotFound):
        _service(session).get_recommendation_snapshot("user_a", "missing_snapshot")


def test_creating_snapshot_does_not_modify_market_truth(session: Session) -> None:
    _seed_users(session)
    _seed_preference(session)
    _seed_market_rows(session)
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    score = session.get(RegionMarketScore, "score_boston")
    source_ref = session.get(SourceRef, "source_a")
    observation = session.get(SourceObservation, "obs_a")
    link = session.get(FactSourceLink, "link_score_boston")
    source_ref_collected_at = source_ref.collected_at
    observation_observed_at = observation.observed_at
    versions = {
        "region": region.version,
        "company": company.version,
        "score": score.version,
        "source_ref": source_ref.version,
        "observation": observation.version,
        "link": link.version,
    }

    _service(session).create_recommendation_snapshot(
        "user_a",
        PersonalizedRecommendationSnapshotInput(
            preference_profile_id="user_a",
            personalized_output={
                "ranked_regions": [
                    {
                        "region_id": "greater_boston",
                        "display_name": "User-only name",
                        "objective_opportunity_score": 999,
                    }
                ]
            },
            recommendation_version="personalized_rec_v1",
            source_version_bundle={"region_market_scores": {"greater_boston": 3}},
            objective_output_refs=[{"output_type": "region", "subject_id": "greater_boston"}],
            recommendation_inputs_hash="sha256:market-boundary",
            generated_at=_NOW,
        ),
    )

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    session.refresh(source_ref)
    session.refresh(observation)
    session.refresh(link)
    assert region.version == versions["region"]
    assert company.version == versions["company"]
    assert score.version == versions["score"]
    assert source_ref.version == versions["source_ref"]
    assert observation.version == versions["observation"]
    assert link.version == versions["link"]
    assert region.display_name == "Greater Boston"
    assert score.objective_opportunity_score == 0.74
    assert source_ref.collected_at == source_ref_collected_at
    assert observation.observed_at == observation_observed_at
