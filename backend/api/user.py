"""Protected Layer 7 user-owned persistence routes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.alerts.repository import AlertRepository
from backend.alerts.service import AlertNotFound, AlertService, user_alert_data
from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.monetization_access import require_current_user_feature
from backend.explanations.payloads import (
    ExplanationEntityType,
    ExplanationRequest,
)
from backend.explanations.service import ExplanationService
from backend.geography.exceptions import (
    GeographicInputAmbiguous,
    GeographicInputUnknown,
)
from backend.geography.repository import RegionRepository
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.repository import MonetizationRepository
from backend.personalization.exceptions import MissingRegionForPersonalization
from backend.personalization.payloads import ScoringPreviewRequest
from backend.personalization.service import PersonalizationService
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import (
    CrossUserAccessBlocked,
    InvalidSavedMarketArtifactType,
    PreferenceProfileNotFound,
    RecommendationSnapshotNotFound,
    SavedMarketArtifactNotFound,
)
from backend.users.models import (
    PersonalizedRecommendationSnapshot,
    SavedMarketArtifact,
    User,
    UserProfile,
)
from backend.users.repository import UserRepository
from backend.users.service import (
    PersonalizedRecommendationSnapshotInput,
    SavedMarketArtifactInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
    UserPreferenceProfileView,
)

router = APIRouter(prefix="/me", tags=["user"])


class UserEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: dict[str, Any]
    profile: dict[str, Any]


def _service(session: Session) -> UserPersonalizationPersistenceService:
    return UserPersonalizationPersistenceService(UserRepository(session), RegionRepository(session))


def _personalization_service(session: Session) -> PersonalizationService:
    return PersonalizationService(
        session=session,
        region_repo=RegionRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _alert_service(session: Session) -> AlertService:
    return AlertService(AlertRepository(session))


def _explanation_service() -> ExplanationService:
    return ExplanationService()


def _observe_authenticated_product_visit(
    request: Request,
    session: Session,
    user_id: str,
) -> None:
    try:
        with session.begin_nested():
            ProductMeasurementService(session).observe_authenticated_product_visit(
                user_id,
                product_surface=str(request.url.path or "/me"),
            )
    except Exception:
        return


@router.get("")
def get_current_user_profile(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _observe_authenticated_product_visit(request, session, current.user.user_id)
    return lightweight_success_envelope(
        data=UserEnvelope(
            user=_user_data(current.user),
            profile=_profile_data(current.profile),
        ).model_dump(mode="json")
    )


@router.get("/preferences")
def get_preferences(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    view = _service(session).get_preference_profile(current.user.user_id)
    return lightweight_success_envelope(data=_preference_data(view))


@router.put("/preferences")
def update_preferences(
    profile: UserPreferenceProfileInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        view = _service(session).upsert_preference_profile(
            current.user.user_id,
            profile,
        )
    except (GeographicInputUnknown, GeographicInputAmbiguous) as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=_preference_data(view))


@router.delete("/preferences")
def delete_preferences(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    deleted = _service(session).delete_preference_profile(current.user.user_id)
    return lightweight_success_envelope(data={"deleted_preference_profiles": deleted})


@router.post("/scoring-preview")
def preview_scoring_overlay(
    request: ScoringPreviewRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    preferences = _service(session).get_preference_profile(current.user.user_id)
    effective_request = request.model_copy(
        update={
            "role_interests": (
                request.role_interests
                if request.role_interests is not None
                else preferences.role_interests
            ),
            "industry_interests": (
                request.industry_interests
                if request.industry_interests is not None
                else preferences.industry_interests
            ),
            "scoring_weights": request.scoring_weights or preferences.scoring_weights,
        }
    )
    try:
        result = _personalization_service(session).scoring_preview(effective_request)
    except MissingRegionForPersonalization as exc:
        return _not_found(f"Region not found: {exc!s}")

    data = result.model_dump(mode="json")
    warnings = data.pop("warnings", [])
    envelope = lightweight_success_envelope(data=data)
    envelope["metadata"]["warnings"] = warnings
    return envelope


@router.post("/saved-market-artifacts", status_code=status.HTTP_201_CREATED)
def create_saved_market_artifact(
    artifact: SavedMarketArtifactInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    access = require_current_user_feature(
        repository=MonetizationRepository(session),
        current=current,
        feature_key=MonetizationFeatureKey.SAVED_WATCHLISTS,
    )
    if isinstance(access, JSONResponse):
        return access
    try:
        row = _service(session).save_market_artifact(current.user.user_id, artifact)
    except (GeographicInputUnknown, GeographicInputAmbiguous) as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=_saved_artifact_data(row))


@router.get("/saved-market-artifacts")
def list_saved_market_artifacts(
    artifact_type: str | None = Query(default=None, min_length=1),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        rows = _service(session).list_saved_market_artifacts(
            current.user.user_id,
            artifact_type=artifact_type,
        )
    except InvalidSavedMarketArtifactType as exc:
        return _validation_error(f"Invalid saved artifact type: {exc.artifact_type!r}")
    return lightweight_success_envelope(
        data={"saved_market_artifacts": [_saved_artifact_data(row) for row in rows]}
    )


@router.get("/saved-market-artifacts/{saved_artifact_id}")
def get_saved_market_artifact(
    saved_artifact_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        row = _service(session).get_saved_market_artifact(
            current.user.user_id,
            saved_artifact_id,
        )
    except (CrossUserAccessBlocked, SavedMarketArtifactNotFound):
        return _not_found("Saved market artifact not found.")
    return lightweight_success_envelope(data=_saved_artifact_data(row))


@router.delete("/saved-market-artifacts/{saved_artifact_id}")
def delete_saved_market_artifact(
    saved_artifact_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        _service(session).delete_saved_market_artifact(
            current.user.user_id,
            saved_artifact_id,
        )
    except (CrossUserAccessBlocked, SavedMarketArtifactNotFound):
        return _not_found("Saved market artifact not found.")
    return lightweight_success_envelope(data={"deleted_saved_market_artifacts": 1})


@router.get("/alerts")
def list_alerts(
    include_dismissed: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    access = require_current_user_feature(
        repository=MonetizationRepository(session),
        current=current,
        feature_key=MonetizationFeatureKey.ALERTS,
    )
    if isinstance(access, JSONResponse):
        return access
    rows = _alert_service(session).list_user_alerts(
        current.user.user_id,
        include_dismissed=include_dismissed,
        limit=limit,
    )
    return lightweight_success_envelope(
        data={"alerts": [user_alert_data(alert, event) for alert, event in rows]}
    )


@router.post("/alerts/{user_alert_id}/read")
def mark_alert_read(
    user_alert_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    access = require_current_user_feature(
        repository=MonetizationRepository(session),
        current=current,
        feature_key=MonetizationFeatureKey.ALERTS,
    )
    if isinstance(access, JSONResponse):
        return access
    try:
        alert = _alert_service(session).mark_read(
            user_id=current.user.user_id,
            user_alert_id=user_alert_id,
        )
    except AlertNotFound:
        return _not_found("Alert not found.")
    event = AlertRepository(session).get_event(alert.alert_event_id)
    if event is None:
        return _not_found("Alert event not found.")
    return lightweight_success_envelope(data=user_alert_data(alert, event))


@router.post("/alerts/{user_alert_id}/dismiss")
def dismiss_alert(
    user_alert_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    access = require_current_user_feature(
        repository=MonetizationRepository(session),
        current=current,
        feature_key=MonetizationFeatureKey.ALERTS,
    )
    if isinstance(access, JSONResponse):
        return access
    try:
        alert = _alert_service(session).dismiss(
            user_id=current.user.user_id,
            user_alert_id=user_alert_id,
        )
    except AlertNotFound:
        return _not_found("Alert not found.")
    event = AlertRepository(session).get_event(alert.alert_event_id)
    if event is None:
        return _not_found("Alert event not found.")
    return lightweight_success_envelope(data=user_alert_data(alert, event))


@router.post("/explanations/region")
def explain_region_guidance(
    request: ExplanationRequest,
    _current: CurrentUser = Depends(get_current_user),
):
    return _explain_with_entity_type(request, ExplanationEntityType.REGION)


@router.post("/explanations/company")
def explain_company_guidance(
    request: ExplanationRequest,
    _current: CurrentUser = Depends(get_current_user),
):
    return _explain_with_entity_type(request, ExplanationEntityType.COMPANY)


@router.post("/explanations/comparison")
def explain_comparison_guidance(
    request: ExplanationRequest,
    _current: CurrentUser = Depends(get_current_user),
):
    return _explain_with_entity_type(request, ExplanationEntityType.COMPARISON)


@router.post("/explanations/alert")
def explain_alert_guidance(
    request: ExplanationRequest,
    _current: CurrentUser = Depends(get_current_user),
):
    return _explain_with_entity_type(request, ExplanationEntityType.ALERT)


@router.post("/recommendation-snapshots", status_code=status.HTTP_201_CREATED)
def create_recommendation_snapshot(
    snapshot: PersonalizedRecommendationSnapshotInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        row = _service(session).create_recommendation_snapshot(
            current.user.user_id,
            snapshot,
        )
    except (CrossUserAccessBlocked, PreferenceProfileNotFound):
        return _validation_error("Invalid recommendation snapshot preference link.")
    return lightweight_success_envelope(data=_recommendation_snapshot_data(row))


@router.get("/recommendation-snapshots")
def list_recommendation_snapshots(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_recommendation_snapshots(current.user.user_id)
    return lightweight_success_envelope(
        data={
            "personalized_recommendation_snapshots": [
                _recommendation_snapshot_data(row) for row in rows
            ]
        }
    )


@router.get("/recommendation-snapshots/{recommendation_snapshot_id}")
def get_recommendation_snapshot(
    recommendation_snapshot_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        row = _service(session).get_recommendation_snapshot(
            current.user.user_id,
            recommendation_snapshot_id,
        )
    except (CrossUserAccessBlocked, RecommendationSnapshotNotFound):
        return _not_found("Recommendation snapshot not found.")
    return lightweight_success_envelope(data=_recommendation_snapshot_data(row))


@router.get("/export")
def export_current_user_data(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    exported = _service(session).export_user_data(current.user.user_id)
    return lightweight_success_envelope(data=exported)


@router.delete("")
def deactivate_current_user_account(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    result = _service(session).deactivate_user_account(current.user.user_id)
    return lightweight_success_envelope(data=asdict(result))


def _user_data(row: User) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _profile_data(row: UserProfile) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "display_name": row.display_name,
        "email": row.email,
        "avatar_url": row.avatar_url,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _preference_data(view: UserPreferenceProfileView) -> dict[str, Any]:
    return view.model_dump(mode="json")


def _saved_artifact_data(row: SavedMarketArtifact) -> dict[str, Any]:
    return {
        "saved_artifact_id": row.saved_artifact_id,
        "user_id": row.user_id,
        "artifact_type": row.artifact_type,
        "artifact_ref": row.artifact_ref,
        "label": row.label,
        "notes": row.notes,
        "snapshot": row.snapshot,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _recommendation_snapshot_data(
    row: PersonalizedRecommendationSnapshot,
) -> dict[str, Any]:
    return {
        "recommendation_snapshot_id": row.recommendation_snapshot_id,
        "user_id": row.user_id,
        "preference_profile_id": row.preference_profile_id,
        "personalized_output": row.personalized_output,
        "recommendation_version": row.recommendation_version,
        "source_version_bundle": row.source_version_bundle,
        "objective_output_refs": row.objective_output_refs,
        "recommendation_inputs_hash": row.recommendation_inputs_hash,
        "generated_at": _dt(row.generated_at),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _explain_with_entity_type(
    request: ExplanationRequest,
    expected_type: ExplanationEntityType,
) -> dict | JSONResponse:
    if request.evidence.entity_type != expected_type:
        return _validation_error(
            f"Explanation endpoint expects entity_type={expected_type.value!r}."
        )
    result = _explanation_service().explain(request.evidence)
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(code=NOT_FOUND, message=message),
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_envelope(code=VALIDATION_ERROR, message=message),
    )
