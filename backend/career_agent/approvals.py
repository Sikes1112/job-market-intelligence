"""Approval-state guardrails for career-agent tool actions."""

from __future__ import annotations

from backend.career_agent.schemas import CareerAgentToolStatus


class CareerAgentToolApprovalError(ValueError):
    """Raised when a tool approval/rejection transition is not allowed."""


class CareerAgentToolNotFound(LookupError):
    """Raised when a user-scoped tool record is not found."""


TERMINAL_STATUSES = frozenset(
    {
        CareerAgentToolStatus.APPROVED,
        CareerAgentToolStatus.EXECUTED,
        CareerAgentToolStatus.REJECTED,
        CareerAgentToolStatus.EXPIRED,
        CareerAgentToolStatus.BLOCKED,
    }
)


def assert_can_approve(
    *,
    current_status: CareerAgentToolStatus,
    approval_required: bool,
    explicit_user_approval: bool,
) -> None:
    if current_status is CareerAgentToolStatus.BLOCKED:
        raise CareerAgentToolApprovalError("Blocked tool actions cannot be approved.")
    if current_status in TERMINAL_STATUSES:
        raise CareerAgentToolApprovalError(
            f"Tool action in {current_status.value} state cannot be approved."
        )
    if not approval_required:
        raise CareerAgentToolApprovalError("This tool preview does not require approval.")
    if not explicit_user_approval:
        raise CareerAgentToolApprovalError(
            "Explicit user approval is required for this tool action."
        )


def assert_can_reject(*, current_status: CareerAgentToolStatus) -> None:
    if current_status in TERMINAL_STATUSES:
        raise CareerAgentToolApprovalError(
            f"Tool action in {current_status.value} state cannot be rejected."
        )
