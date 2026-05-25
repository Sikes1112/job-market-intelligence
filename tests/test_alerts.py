from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.alerts.models import AlertEvent
from backend.alerts.repository import AlertRepository
from backend.alerts.service import (
    AlertChangeInput,
    AlertEventType,
    AlertService,
    StructuredAlertState,
)
from backend.companies.models import Company
from backend.geography.models import Region
from backend.users.models import User, UserPreferenceProfile
from backend.users.repository import UserRepository
from backend.users.service import SavedMarketArtifactInput, UserPersonalizationPersistenceService

_NOW = datetime(2026, 5, 25, 14, tzinfo=UTC)


def _alert_service(session: Session) -> AlertService:
    return AlertService(AlertRepository(session))


def _user_service(session: Session) -> UserPersonalizationPersistenceService:
    return UserPersonalizationPersistenceService(UserRepository(session))


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="Company A",
                normalized_company_name="company a",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()


def _seed_users(session: Session, *user_ids: str) -> None:
    session.add_all([User(user_id=user_id) for user_id in user_ids])
    session.flush()


def _change(**overrides) -> AlertChangeInput:
    values = {
        "event_type": AlertEventType.NEW_HIRING_ACTIVITY,
        "company_id": "comp_a",
        "region_id": "greater_boston",
        "role_family": "product",
        "previous_value": {
            "currently_hiring_flag": False,
            "active_posting_count_now": 0,
        },
        "new_value": {
            "currently_hiring_flag": True,
            "active_posting_count_now": 3,
        },
        "change_summary": {
            "changed_fields": ["currently_hiring_flag", "active_posting_count_now"],
            "source_ref_count": 1,
        },
        "freshness_status": "fresh",
        "freshness_observed_at": _NOW,
        "freshness_expires_at": datetime(2026, 6, 25, 14, tzinfo=UTC),
        "source_refs": ["source_ref:careers"],
        "change_basis_refs": ["company_region_hiring:h_a_boston:v2"],
        "detection_basis": "structured_refreshable_state",
    }
    values.update(overrides)
    return AlertChangeInput(**values)


def test_alert_event_enum_validation() -> None:
    with pytest.raises(ValidationError):
        _change(event_type="unsupported_alert")


@pytest.mark.parametrize(
    "payload",
    [
        {"companies": [{"company_id": "comp_a"}]},
        {"regions": [{"region_id": "greater_boston"}]},
        {"company_detail": {"company_name": "Company A"}},
        {"region_detail": {"display_name": "Greater Boston"}},
        {"market_output": {"top_companies_hiring": []}},
        {"provenance": {"source_id": "source_a"}},
        {"source_summary": {"source_count": 1}},
        {"evidence": ["source_a"]},
    ],
)
def test_alert_change_metadata_rejects_copied_market_payloads(payload: dict) -> None:
    with pytest.raises(ValidationError):
        _change(previous_value=payload)
    with pytest.raises(ValidationError):
        _change(change_summary=payload)


def test_structured_detection_requires_previous_state_to_avoid_fake_alerts(
    session: Session,
) -> None:
    current = StructuredAlertState(
        company_id="comp_a",
        region_id="greater_boston",
        values={"internship_count": 2, "coop_count": 0},
        source_refs=["source_ref:careers"],
        change_basis_refs=["company_region_entry_level:e_a_boston:v1"],
    )

    changes = _alert_service(session).detect_changes_from_structured_states(
        previous=None,
        current=current,
    )

    assert changes == []


def test_structured_detection_emits_bounded_change_types(session: Session) -> None:
    previous = StructuredAlertState(
        company_id="comp_a",
        region_id="greater_boston",
        role_family="product",
        values={
            "currently_hiring_flag": False,
            "active_posting_count_now": 0,
            "internship_count": 0,
            "coop_count": 0,
            "objective_opportunity_score": 0.71,
        },
        source_refs=["source_ref:careers"],
        change_basis_refs=["previous:bundle:v1"],
    )
    current = StructuredAlertState(
        company_id="comp_a",
        region_id="greater_boston",
        role_family="product",
        values={
            "currently_hiring_flag": True,
            "active_posting_count_now": 3,
            "internship_count": 1,
            "coop_count": 0,
            "objective_opportunity_score": 0.74,
        },
        freshness_status="fresh",
        freshness_observed_at=_NOW,
        source_refs=["source_ref:careers"],
        change_basis_refs=["current:bundle:v2"],
    )

    changes = _alert_service(session).detect_changes_from_structured_states(
        previous=previous,
        current=current,
    )

    assert {change.event_type for change in changes} == {
        AlertEventType.NEW_HIRING_ACTIVITY,
        AlertEventType.ENTRY_LEVEL_SIGNAL_CHANGED,
        AlertEventType.REGION_SCORE_CHANGED,
        AlertEventType.INTERNSHIP_WINDOW_OPENED,
    }


def test_watchlist_and_preference_relevance_materializes_user_alerts(
    session: Session,
) -> None:
    _seed_market(session)
    _seed_users(
        session,
        "user_company",
        "user_region",
        "user_comparison",
        "user_false_comparison",
        "user_role",
        "user_preference",
        "user_false_preference",
    )
    user_service = _user_service(session)
    user_service.save_market_artifact(
        "user_company",
        SavedMarketArtifactInput(artifact_type="company", artifact_ref="comp_a"),
    )
    user_service.save_market_artifact(
        "user_region",
        SavedMarketArtifactInput(artifact_type="region", artifact_ref="greater_boston"),
    )
    user_service.save_market_artifact(
        "user_comparison",
        SavedMarketArtifactInput(
            artifact_type="comparison",
            artifact_ref="greater_boston__greater_sf",
            snapshot={"region_ids": ["greater_boston", "greater_sf"]},
        ),
    )
    user_service.save_market_artifact(
        "user_false_comparison",
        SavedMarketArtifactInput(
            artifact_type="comparison",
            artifact_ref="greater_boston_area__greater_sf",
        ),
    )
    user_service.save_market_artifact(
        "user_role",
        SavedMarketArtifactInput(artifact_type="role_family", artifact_ref="product"),
    )
    session.add(
        UserPreferenceProfile(
            user_id="user_preference",
            role_interests=[],
            industry_interests=[],
            preferred_regions=["greater_boston"],
        )
    )
    session.add(
        UserPreferenceProfile(
            user_id="user_false_preference",
            role_interests=["productivity"],
            industry_interests=[],
            preferred_regions=["greater_boston_area"],
        )
    )
    session.flush()

    service = _alert_service(session)
    event = service.create_event(_change())
    user_alerts = service.materialize_user_alerts_for_event(event)

    assert {alert.user_id for alert in user_alerts} == {
        "user_company",
        "user_region",
        "user_comparison",
        "user_role",
        "user_preference",
    }
    reasons = {alert.user_id: alert.relevance_reason for alert in user_alerts}
    assert reasons["user_company"] == "saved_company"
    assert reasons["user_region"] == "saved_region"
    assert reasons["user_comparison"] == "saved_comparison"
    assert reasons["user_role"] == "saved_role_family"
    assert reasons["user_preference"] == "preferred_region"


def test_user_alert_read_and_dismiss_are_user_specific(session: Session) -> None:
    _seed_market(session)
    _seed_users(session, "user_a")
    _user_service(session).save_market_artifact(
        "user_a",
        SavedMarketArtifactInput(artifact_type="company", artifact_ref="comp_a"),
    )
    service = _alert_service(session)
    event = service.create_event(_change())
    alert = service.materialize_user_alerts_for_event(event)[0]

    read = service.mark_read(user_id="user_a", user_alert_id=alert.user_alert_id)
    dismissed = service.dismiss(user_id="user_a", user_alert_id=alert.user_alert_id)

    assert read.is_read is True
    assert read.read_at is not None
    assert dismissed.dismissed is True
    assert dismissed.dismissed_at is not None
    assert service.list_user_alerts("user_a") == []
    assert len(service.list_user_alerts("user_a", include_dismissed=True)) == 1


def test_alert_records_store_minimal_change_metadata_not_full_market_payloads(
    session: Session,
) -> None:
    _seed_market(session)
    service = _alert_service(session)

    event = service.create_event(_change())
    row = session.get(AlertEvent, event.alert_event_id)

    assert row.previous_value == {
        "currently_hiring_flag": False,
        "active_posting_count_now": 0,
    }
    assert row.new_value == {
        "currently_hiring_flag": True,
        "active_posting_count_now": 3,
    }
    assert "company_name" not in str(row.previous_value)
    assert "display_name" not in str(row.new_value)
    assert row.source_refs == ["source_ref:careers"]
