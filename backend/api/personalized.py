"""POST /discover/personalized — session-scoped personalization endpoint.

Wraps :class:`PersonalizationService` in the standard API envelope. The
preference payload is **not persisted**; the response is computed in
memory and returned to the caller. There is no login, no session, no user
account.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import (
    NOT_FOUND,
    error_envelope,
    lightweight_success_envelope,
)
from backend.geography.repository import RegionRepository
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
    prefs: UserPreferences,
    session: Session = Depends(get_session),
):
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

    return lightweight_success_envelope(
        data=result.personalized.model_dump(mode="json"),
    ) | {
        # Surface warnings in the standard metadata block.
        "metadata": {
            "state": "fresh",
            "warnings": list(result.warnings),
        },
    }
