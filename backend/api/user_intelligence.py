"""Read-only Layer 30.1 user intelligence dashboard API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import lightweight_success_envelope
from backend.api.monetization_access import optional_current_user
from backend.user_intelligence.service import UserIntelligenceDashboardService

router = APIRouter(tags=["user-intelligence"])


@router.get("/user-intelligence/dashboard")
def user_intelligence_dashboard(
    request: Request,
    region_limit: int = Query(default=5, ge=0, le=25),
    company_limit: int = Query(default=5, ge=0, le=25),
    opportunity_limit: int = Query(default=5, ge=0, le=25),
    forecast_limit: int = Query(default=5, ge=0, le=25),
    session: Session = Depends(get_session),
) -> dict:
    current = optional_current_user(request, session)
    payload = UserIntelligenceDashboardService(session).build_dashboard(
        current_user_id=current.user.user_id if current is not None else None,
        region_limit=region_limit,
        company_limit=company_limit,
        opportunity_limit=opportunity_limit,
        forecast_limit=forecast_limit,
    )
    state = "partial" if payload.market_warnings else "fresh"
    envelope = lightweight_success_envelope(
        data=payload.model_dump(mode="json"),
        state=state,
    )
    envelope["metadata"]["warnings"] = [
        warning.model_dump(mode="json") for warning in payload.market_warnings
    ]
    return envelope
