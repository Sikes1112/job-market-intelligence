from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import CurrentAdmin, get_session, require_admin_read_access
from backend.api.envelope import lightweight_success_envelope
from backend.operations.metrics import metrics_registry_from_app_state
from backend.operations.status import detailed_health_payload

router = APIRouter(prefix="/admin/operations", tags=["operations"])


@router.get("/health")
def detailed_health(
    request: Request,
    session=Depends(get_session),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
) -> dict:
    return lightweight_success_envelope(
        data=detailed_health_payload(
            app_state=request.app.state,
            session=session,
            settings=request.app.state.settings,
        )
    )


@router.get("/metrics")
def metrics(
    request: Request,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
) -> dict:
    registry = metrics_registry_from_app_state(request.app.state)
    snapshot = registry.snapshot() if registry is not None else {"http": []}
    return lightweight_success_envelope(data=snapshot)
