"""API helpers for account-aware monetization enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user
from backend.api.envelope import error_envelope
from backend.monetization.enforcement import evaluate_account_access
from backend.monetization.entitlements import AccessDecision
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.repository import MonetizationRepository

ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"


def optional_current_user(request: Request, session: Session) -> CurrentUser | None:
    try:
        return get_current_user(request, session)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def require_current_user_feature(
    *,
    repository: MonetizationRepository,
    current: CurrentUser,
    feature_key: MonetizationFeatureKey,
    now: datetime | None = None,
) -> AccessDecision | JSONResponse:
    repository.ensure_account_for_user(user_id=current.user.user_id)
    decision = evaluate_account_access(
        repository,
        user_id=current.user.user_id,
        feature_key=feature_key,
        now=now or datetime.now(UTC),
        create_usage_counter=True,
    )
    if decision.allowed:
        return decision
    return blocked_entitlement_response(decision)


def blocked_entitlement_response(decision: AccessDecision) -> JSONResponse:
    content = error_envelope(
        code=ENTITLEMENT_REQUIRED,
        message=decision.reason,
        state="blocked",
    )
    content["data"] = {"decision": decision.model_dump(mode="json")}
    return JSONResponse(status_code=403, content=content)


def decision_data(decision: AccessDecision) -> dict[str, Any]:
    return decision.model_dump(mode="json")
