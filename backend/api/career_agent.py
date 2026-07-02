"""Layer 26A grounded career-agent API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.career_agent.approvals import (
    CareerAgentToolApprovalError,
    CareerAgentToolNotFound,
)
from backend.career_agent.memory import CareerMemoryPermissionError, CareerMemoryService
from backend.career_agent.planning import CareerActionPlanningService
from backend.career_agent.schemas import (
    CareerActionPlanRequest,
    CareerAgentGuardrailViolation,
    CareerAgentRequest,
    CareerAgentToolApproval,
    CareerAgentToolRequest,
    CareerMemoryDeleteRequest,
    CareerMemoryUpdateRequest,
)
from backend.career_agent.service import CareerAgentGroundingService
from backend.career_agent.tools import CareerAgentToolService

router = APIRouter(tags=["career-agent"])


@router.post("/career-agent/answers", response_model=None)
def career_agent_answer(
    request: CareerAgentRequest,
    session: Session = Depends(get_session),
) -> Any:
    service = CareerAgentGroundingService(session)
    try:
        answer = service.answer(request)
    except CareerAgentGuardrailViolation as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    envelope = lightweight_success_envelope(
        data=answer.model_dump(mode="json"),
        state=_response_state(answer),
    )
    envelope["metadata"]["warnings"] = list(
        dict.fromkeys((*answer.guardrails.warnings, *answer.limitations))
    )
    return envelope


@router.post("/career-agent/action-plans", response_model=None)
def career_agent_action_plan(
    request: CareerActionPlanRequest,
    session: Session = Depends(get_session),
) -> Any:
    if request.include_memory:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code=VALIDATION_ERROR,
                message="Career memory personalization requires the protected /me route.",
            ),
        )
    return _action_plan_response(request, session=session, memory_profile=None)


@router.post("/me/career-agent/action-plans", response_model=None)
def career_agent_action_plan_with_memory(
    request: CareerActionPlanRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    memory_profile = (
        CareerMemoryService(session).get_profile(current.user.user_id)
        if request.include_memory
        else None
    )
    return _action_plan_response(request, session=session, memory_profile=memory_profile)


@router.get("/me/career-memory", response_model=None)
def get_career_memory(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    profile = CareerMemoryService(session).get_profile(current.user.user_id)
    return lightweight_success_envelope(data=profile.model_dump(mode="json"))


@router.put("/me/career-memory", response_model=None)
def update_career_memory(
    request: CareerMemoryUpdateRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        profile = CareerMemoryService(session).update_memory(
            current.user.user_id,
            request,
        )
    except CareerMemoryPermissionError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(data=profile.model_dump(mode="json"))


@router.delete("/me/career-memory", response_model=None)
def delete_career_memory(
    request: CareerMemoryDeleteRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    profile = CareerMemoryService(session).delete_memory(
        current.user.user_id,
        request,
    )
    return lightweight_success_envelope(data=profile.model_dump(mode="json"))


@router.post("/me/career-agent/tools/preview", response_model=None)
def preview_career_agent_tool(
    request: CareerAgentToolRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    memory_profile = (
        CareerMemoryService(session).get_profile(current.user.user_id)
        if request.include_memory or request.include_private_memory_in_export
        else None
    )
    try:
        preview = CareerAgentToolService(session).preview_tool(
            current.user.user_id,
            request,
            memory_profile=memory_profile,
        )
    except CareerAgentGuardrailViolation as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return _tool_preview_envelope(preview)


@router.get("/me/career-agent/tools", response_model=None)
def list_career_agent_tools(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    previews = CareerAgentToolService(session).list_tools(current.user.user_id)
    return lightweight_success_envelope(
        data={"tool_previews": [preview.model_dump(mode="json") for preview in previews]}
    )


@router.post("/me/career-agent/tools/approve", response_model=None)
def approve_career_agent_tool(
    approval: CareerAgentToolApproval,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        execution = CareerAgentToolService(session).approve_tool(
            current.user.user_id,
            approval,
        )
    except CareerAgentToolNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Tool preview not found."),
        )
    except CareerAgentToolApprovalError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(
        data=execution.model_dump(mode="json"),
        state="partial",
    )


@router.post("/me/career-agent/tools/reject", response_model=None)
def reject_career_agent_tool(
    approval: CareerAgentToolApproval,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        execution = CareerAgentToolService(session).reject_tool(
            current.user.user_id,
            approval,
        )
    except CareerAgentToolNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Tool preview not found."),
        )
    except CareerAgentToolApprovalError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(
        data=execution.model_dump(mode="json"),
        state="partial",
    )


@router.get("/me/career-agent/tools/{tool_request_id}", response_model=None)
def get_career_agent_tool(
    tool_request_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        preview = CareerAgentToolService(session).get_tool(
            current.user.user_id,
            tool_request_id,
        )
    except CareerAgentToolNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Tool preview not found."),
        )
    return _tool_preview_envelope(preview)


def _action_plan_response(
    request: CareerActionPlanRequest,
    *,
    session: Session,
    memory_profile,
) -> Any:  # noqa: ANN001
    service = CareerActionPlanningService(session)
    try:
        plan = service.generate_plan(request, memory_profile=memory_profile)
    except CareerAgentGuardrailViolation as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    envelope = lightweight_success_envelope(
        data=plan.model_dump(mode="json"),
        state=_response_state(plan),
    )
    envelope["metadata"]["warnings"] = list(
        dict.fromkeys((*plan.warnings, *plan.limitations))
    )
    return envelope


def _tool_preview_envelope(preview) -> dict:  # noqa: ANN001
    envelope = lightweight_success_envelope(
        data=preview.model_dump(mode="json"),
        state="partial" if preview.warnings or preview.status.value == "blocked" else "fresh",
    )
    envelope["metadata"]["warnings"] = list(preview.warnings)
    return envelope


def _response_state(answer) -> str:  # noqa: ANN001
    items = getattr(answer, "recommendations", None)
    if items is None:
        items = getattr(answer, "steps", ())
    if not items:
        return "partial"
    warnings = getattr(answer.guardrails, "warnings", ())
    if answer.limitations or warnings:
        return "partial"
    if answer.freshness.freshness_status.value != "fresh":
        return "partial"
    if answer.uncertainty.confidence_level.value in {"low", "unknown"}:
        return "partial"
    return "fresh"
