"""POST /discover/personalized — session-scoped personalization endpoint.

Wraps :class:`PersonalizationService` in the standard API envelope. The
preference payload is **not persisted**; the response is computed in
memory and returned to the caller. Anonymous requests remain supported;
authenticated requests use account state only for usage metering.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import (
    NOT_FOUND,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.monetization_access import (
    blocked_entitlement_response,
    optional_current_user,
)
from backend.geography.repository import RegionRepository
from backend.monetization.enforcement import (
    evaluate_account_access,
    increment_feature_usage,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.repository import MonetizationRepository
from backend.personalization.exceptions import (
    InvalidPreferenceInput,
    MissingRegionForPersonalization,
)
from backend.personalization.payloads import UserPreferences
from backend.personalization.service import PersonalizationService
from backend.scoring.repository import RegionScoreRepository

router = APIRouter()


def _build_service(session: Session) -> PersonalizationService:
    return PersonalizationService(
        session=session,
        region_repo=RegionRepository(session),
        score_repo=RegionScoreRepository(session),
    )


@router.post("/discover/personalized")
def discover_personalized(
    request: Request,
    prefs: UserPreferences,
    session: Session = Depends(get_session),
):
    current = optional_current_user(request, session)
    repo = MonetizationRepository(session)
    if current is not None:
        repo.ensure_account_for_user(user_id=current.user.user_id)
        access = evaluate_account_access(
            repo,
            user_id=current.user.user_id,
            feature_key=MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
            create_usage_counter=True,
        )
        if not access.allowed:
            return blocked_entitlement_response(access)

    service = _build_service(session)
    try:
        result = service.discover(prefs)
    except MissingRegionForPersonalization as e:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Region not found: {e!s}"
            ),
        )
    except InvalidPreferenceInput as e:
        from backend.api.envelope import VALIDATION_ERROR

        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(e)),
        )

    envelope = lightweight_success_envelope(
        data=result.personalized.model_dump(mode="json"),
    )
    # Surface warnings in the standard metadata block.
    envelope["metadata"]["warnings"] = list(result.warnings)
    if current is not None:
        usage_decision = increment_feature_usage(
            repo,
            user_id=current.user.user_id,
            feature_key=MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
        )
        envelope["metadata"]["monetization_access"] = usage_decision.model_dump(
            mode="json"
        )
    return envelope
