"""Layer 26C safe career-agent tool previews and approval records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_agent.approvals import (
    CareerAgentToolNotFound,
    assert_can_approve,
    assert_can_reject,
)
from backend.career_agent.memory import values_for_category
from backend.career_agent.models import (
    CareerAgentToolAuditEventRecord,
    CareerAgentToolRecord,
)
from backend.career_agent.planning import CareerActionPlanningService
from backend.career_agent.schemas import (
    CareerActionPlan,
    CareerAgentActionBoundary,
    CareerAgentApprovalRequirement,
    CareerAgentEvidenceRef,
    CareerAgentEvidenceType,
    CareerAgentFreshness,
    CareerAgentGuardrailViolation,
    CareerAgentRequestedToolAction,
    CareerAgentToolApproval,
    CareerAgentToolAuditEvent,
    CareerAgentToolExecution,
    CareerAgentToolPreview,
    CareerAgentToolPrivacy,
    CareerAgentToolRequest,
    CareerAgentToolStatus,
    CareerAgentToolType,
    CareerAgentUncertainty,
    CareerMemoryCategory,
    CareerMemoryProfile,
    validate_career_agent_tool_preview,
)
from backend.career_agent.service import CareerAgentGroundingService


@dataclass(frozen=True, slots=True)
class _GroundedToolBasis:
    title: str
    summary: str
    evidence_refs: tuple[CareerAgentEvidenceRef, ...]
    freshness: CareerAgentFreshness
    uncertainty: CareerAgentUncertainty
    warnings: tuple[str, ...]
    source_answer_id: str | None = None
    source_plan_id: str | None = None
    plan: CareerActionPlan | None = None


class CareerAgentToolService:
    """Create and transition user-scoped career-agent tool preview records."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._grounding = CareerAgentGroundingService(session)
        self._planning = CareerActionPlanningService(session)

    def preview_tool(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        memory_profile: CareerMemoryProfile | None = None,
        now: datetime | None = None,
    ) -> CareerAgentToolPreview:
        generated_at = _aware(now or datetime.now(UTC))
        basis = self._basis_for_request(
            request,
            memory_profile=memory_profile if request.include_memory else None,
            now=generated_at,
        )
        preview = self._build_preview(
            user_id,
            request,
            basis=basis,
            memory_profile=memory_profile if request.include_memory else None,
            now=generated_at,
        )
        validate_career_agent_tool_preview(preview)
        row = _record_from_preview(preview)
        self._session.add(row)
        self._session.flush()
        self._add_audit(
            row,
            event_type=(
                "blocked"
                if preview.status is CareerAgentToolStatus.BLOCKED
                else "preview_created"
            ),
            summary=(
                "Career-agent tool action was blocked by guardrails."
                if preview.status is CareerAgentToolStatus.BLOCKED
                else "Career-agent tool preview created."
            ),
        )
        self._session.flush()
        return self.get_tool(user_id, row.career_agent_tool_id)

    def list_tools(self, user_id: str) -> tuple[CareerAgentToolPreview, ...]:
        rows = self._session.execute(
            select(CareerAgentToolRecord)
            .where(CareerAgentToolRecord.user_id == user_id)
            .order_by(
                CareerAgentToolRecord.created_at.desc(),
                CareerAgentToolRecord.career_agent_tool_id,
            )
        ).scalars()
        return tuple(self._preview_from_record(row) for row in rows)

    def get_tool(self, user_id: str, tool_request_id: str) -> CareerAgentToolPreview:
        row = self._get_row(user_id, tool_request_id)
        return self._preview_from_record(row)

    def approve_tool(
        self,
        user_id: str,
        approval: CareerAgentToolApproval,
        *,
        now: datetime | None = None,
    ) -> CareerAgentToolExecution:
        row = self._get_row(user_id, approval.tool_request_id)
        assert_can_approve(
            current_status=CareerAgentToolStatus(row.status),
            approval_required=row.approval_required,
            explicit_user_approval=approval.explicit_user_approval,
        )
        timestamp = _aware(now or datetime.now(UTC))
        row.status = CareerAgentToolStatus.APPROVED.value
        row.approved_at = timestamp
        row.updated_at = timestamp
        row.runtime_execution_performed = False
        self._add_audit(
            row,
            event_type="approval_recorded",
            summary="Explicit user approval recorded; no runtime tool execution was performed.",
            now=timestamp,
        )
        self._session.flush()
        preview = self._preview_from_record(row)
        validate_career_agent_tool_preview(preview)
        return CareerAgentToolExecution(
            tool_request_id=row.career_agent_tool_id,
            status=CareerAgentToolStatus.APPROVED,
            runtime_execution_performed=False,
            executed_at=None,
            summary=(
                "Approval recorded. This Layer 26C flow stores an approval record "
                "and does not execute external integrations."
            ),
            warnings=(
                "No reminder, export, notification, watchlist, outreach, or "
                "application runtime was executed.",
            ),
            tool_preview=preview,
        )

    def reject_tool(
        self,
        user_id: str,
        approval: CareerAgentToolApproval,
        *,
        now: datetime | None = None,
    ) -> CareerAgentToolExecution:
        row = self._get_row(user_id, approval.tool_request_id)
        assert_can_reject(current_status=CareerAgentToolStatus(row.status))
        timestamp = _aware(now or datetime.now(UTC))
        row.status = CareerAgentToolStatus.REJECTED.value
        row.rejected_at = timestamp
        row.updated_at = timestamp
        self._add_audit(
            row,
            event_type="rejection_recorded",
            summary="Career-agent tool action rejected by the user.",
            now=timestamp,
        )
        self._session.flush()
        preview = self._preview_from_record(row)
        validate_career_agent_tool_preview(preview)
        return CareerAgentToolExecution(
            tool_request_id=row.career_agent_tool_id,
            status=CareerAgentToolStatus.REJECTED,
            runtime_execution_performed=False,
            executed_at=None,
            summary="Tool action rejected. No runtime execution was performed.",
            warnings=(),
            tool_preview=preview,
        )

    def _basis_for_request(
        self,
        request: CareerAgentToolRequest,
        *,
        memory_profile: CareerMemoryProfile | None,
        now: datetime,
    ) -> _GroundedToolBasis:
        if request.action_plan_request is not None:
            plan = self._planning.generate_plan(
                request.action_plan_request,
                memory_profile=memory_profile,
                now=now,
            )
            return _GroundedToolBasis(
                title=plan.steps[0].title,
                summary=plan.summary,
                evidence_refs=plan.evidence_refs,
                freshness=plan.freshness,
                uncertainty=plan.uncertainty,
                warnings=(*plan.warnings, *plan.limitations),
                source_plan_id=plan.plan_id,
                plan=plan,
            )
        if request.career_agent_request is None:
            raise CareerAgentGuardrailViolation("Tool preview requires grounded input.")
        answer = self._grounding.answer(request.career_agent_request, now=now)
        if not answer.recommendations:
            raise CareerAgentGuardrailViolation(
                "Tool preview requires at least one grounded recommendation."
            )
        recommendation = answer.recommendations[0]
        return _GroundedToolBasis(
            title=recommendation.title,
            summary=answer.summary,
            evidence_refs=_dedupe_refs(
                ref for item in answer.recommendations for ref in item.evidence_refs
            ),
            freshness=answer.freshness,
            uncertainty=answer.uncertainty,
            warnings=(
                *answer.guardrails.warnings,
                *answer.limitations,
                *(
                    warning
                    for item in answer.recommendations
                    for warning in (*item.warnings, *item.limitations)
                ),
            ),
            source_answer_id=answer.answer_id,
        )

    def _build_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        memory_profile: CareerMemoryProfile | None,
        now: datetime,
    ) -> CareerAgentToolPreview:
        blocked_reason = _blocked_reason(request, basis)
        if blocked_reason is not None:
            blocked_boundary = (
                CareerAgentActionBoundary.APPLICATION_SUBMISSION
                if request.tool_type is CareerAgentToolType.JOB_APPLICATION_SUBMISSION
                or request.requested_action is CareerAgentRequestedToolAction.SUBMIT_APPLICATION
                else CareerAgentActionBoundary.EXTERNAL_CONTACT
            )
            return _preview(
                user_id,
                request,
                basis=basis,
                now=now,
                status=CareerAgentToolStatus.BLOCKED,
                action_boundary=blocked_boundary,
                privacy=CareerAgentToolPrivacy.BLOCKED,
                approval=_approval(
                    required=True,
                    boundary=blocked_boundary,
                    reason=(
                        "This action is blocked because the career agent cannot submit "
                        "applications or contact employers."
                    ),
                    runtime_available=False,
                ),
                summary="Blocked career-agent tool action",
                payload={
                    "blocked": True,
                    "reason": blocked_reason,
                    "runtime_execution_performed": False,
                },
                warnings=(blocked_reason, *basis.warnings),
            )

        if request.target_opportunity_ids:
            unsupported = _unsupported_opportunity_ids(
                request.target_opportunity_ids,
                basis.evidence_refs,
            )
            if unsupported:
                return _preview(
                    user_id,
                    request,
                    basis=basis,
                    now=now,
                    status=CareerAgentToolStatus.BLOCKED,
                    action_boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
                    privacy=CareerAgentToolPrivacy.BLOCKED,
                    approval=_approval(
                        required=False,
                        boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
                        reason="Unsupported opportunity targets are blocked before preview.",
                    ),
                    summary="Blocked unsupported opportunity action",
                    payload={
                        "blocked": True,
                        "unsupported_opportunity_ids": unsupported,
                    },
                    warnings=(
                        "Unsupported or fabricated opportunity targets were blocked.",
                        *basis.warnings,
                    ),
                )

        if request.tool_type is CareerAgentToolType.REMINDER:
            return self._reminder_preview(user_id, request, basis=basis, now=now)
        if request.tool_type is CareerAgentToolType.CAREER_REPORT_EXPORT:
            return self._export_preview(
                user_id,
                request,
                basis=basis,
                memory_profile=memory_profile,
                now=now,
            )
        if request.tool_type is CareerAgentToolType.WATCHLIST_UPDATE_SUGGESTION:
            return self._watchlist_preview(user_id, request, basis=basis, now=now)
        if request.tool_type is CareerAgentToolType.NOTIFICATION_PREFERENCE:
            return self._notification_preview(user_id, request, basis=basis, now=now)
        if request.tool_type is CareerAgentToolType.OUTREACH_DRAFT:
            return self._outreach_preview(user_id, request, basis=basis, now=now)
        if request.tool_type is CareerAgentToolType.APPLICATION_PREP_CHECKLIST:
            return self._application_checklist_preview(user_id, request, basis=basis, now=now)
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.BLOCKED,
            action_boundary=CareerAgentActionBoundary.APPLICATION_SUBMISSION,
            privacy=CareerAgentToolPrivacy.BLOCKED,
            approval=_approval(
                required=True,
                boundary=CareerAgentActionBoundary.APPLICATION_SUBMISSION,
                reason="Autonomous job applications are prohibited.",
            ),
            summary="Blocked autonomous application action",
            payload={"blocked": True},
            warnings=("Autonomous job applications are blocked.", *basis.warnings),
        )

    def _reminder_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        now: datetime,
    ) -> CareerAgentToolPreview:
        first_step = basis.plan.steps[0] if basis.plan is not None else None
        title = f"Review {basis.title}"
        suggested_date = (now + timedelta(days=2)).date()
        if first_step is not None and first_step.milestone.target_date is not None:
            suggested_date = first_step.milestone.target_date
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.AWAITING_USER_APPROVAL,
            action_boundary=CareerAgentActionBoundary.REMINDER_CREATION,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=True,
                boundary=CareerAgentActionBoundary.REMINDER_CREATION,
                reason="Creating a reminder changes user-owned state and requires approval.",
            ),
            summary=f"Prepare a reminder suggestion for {basis.title}.",
            payload={
                "title": title,
                "suggested_date": suggested_date.isoformat(),
                "runtime_wired": False,
                "execution_note": (
                    "Approval stores a tool record only; no reminder runtime is wired "
                    "in Layer 26C."
                ),
            },
            warnings=(
                "Reminder runtime is not wired; approval records only the prepared action.",
                *basis.warnings,
            ),
        )

    def _export_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        memory_profile: CareerMemoryProfile | None,
        now: datetime,
    ) -> CareerAgentToolPreview:
        public_payload = {
            "report_title": f"Career Agent Report: {basis.title}",
            "summary": basis.summary,
            "source_answer_id": basis.source_answer_id,
            "source_plan_id": basis.source_plan_id,
            "evidence_ref_ids": [ref.ref_id for ref in basis.evidence_refs],
            "freshness": basis.freshness.model_dump(mode="json"),
            "uncertainty": basis.uncertainty.model_dump(mode="json"),
            "private_memory_included": False,
        }
        payload: dict = {
            "public_export_payload": public_payload,
            "runtime_wired": False,
            "execution_note": (
                "Approval records export intent only; no file export runtime is wired "
                "in Layer 26C."
            ),
        }
        if request.include_private_memory_in_export and memory_profile is not None:
            payload["private_memory_payload"] = {
                category.value: values_for_category(memory_profile, category)
                for category in CareerMemoryCategory
            }
            payload["public_export_payload"] = {
                **public_payload,
                "private_memory_included": True,
                "private_memory_redacted_from_public_payload": True,
            }
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.AWAITING_USER_APPROVAL,
            action_boundary=CareerAgentActionBoundary.USER_DATA_EXPORT,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=True,
                boundary=CareerAgentActionBoundary.USER_DATA_EXPORT,
                reason="Exporting a user-specific report requires explicit approval.",
            ),
            summary=f"Prepare a career report export preview for {basis.title}.",
            payload=payload,
            warnings=(
                "Export runtime is not wired; approval records only the prepared export.",
                *basis.warnings,
            ),
        )

    def _watchlist_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        now: datetime,
    ) -> CareerAgentToolPreview:
        suggestions = _watchlist_suggestions(basis.evidence_refs, limit=request.limit)
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.AWAITING_USER_APPROVAL,
            action_boundary=CareerAgentActionBoundary.WATCHLIST_MUTATION,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=True,
                boundary=CareerAgentActionBoundary.WATCHLIST_MUTATION,
                reason="Updating watchlists changes user-owned state and requires approval.",
            ),
            summary=f"Suggest watchlist additions from {basis.title}.",
            payload={
                "suggestions": suggestions,
                "runtime_wired": False,
                "execution_note": (
                    "Approval records intent only; no watchlist mutation is performed "
                    "in Layer 26C."
                ),
            },
            warnings=(
                "Watchlist mutation runtime is not wired for career-agent tools.",
                *basis.warnings,
            ),
        )

    def _notification_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        now: datetime,
    ) -> CareerAgentToolPreview:
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.AWAITING_USER_APPROVAL,
            action_boundary=CareerAgentActionBoundary.NOTIFICATION_CHANGE,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=True,
                boundary=CareerAgentActionBoundary.NOTIFICATION_CHANGE,
                reason=(
                    "Creating notification preferences changes user-owned state and "
                    "requires approval."
                ),
            ),
            summary=f"Suggest a change-alert rule for {basis.title}.",
            payload={
                "rules": [
                    {
                        "rule_type": "trusted_opportunity_change",
                        "subject": basis.title,
                        "condition": "Notify when trusted structured evidence changes.",
                    }
                ],
                "runtime_wired": False,
                "execution_note": (
                    "Approval records intent only; no notification runtime is created "
                    "in Layer 26C."
                ),
            },
            warnings=(
                "Notification runtime is not wired for career-agent tools.",
                *basis.warnings,
            ),
        )

    def _outreach_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        now: datetime,
    ) -> CareerAgentToolPreview:
        recipient = request.draft_recipient_role or "career contact"
        evidence_claim = _first_evidence_claim(basis.evidence_refs)
        user_claims = tuple(request.user_context_claims)
        body_lines = [
            f"Hello {recipient},",
            "",
            "I am exploring early-career opportunities and wanted to ask for advice.",
            f"Evidence-backed context: {evidence_claim}",
        ]
        if user_claims:
            body_lines.append(
                "User-provided context: " + "; ".join(user_claims[:3])
            )
        body_lines.append(
            "I would appreciate any public guidance you are comfortable sharing."
        )
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.DRAFTED,
            action_boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=False,
                boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
                reason="Drafting outreach text is a read-only preparation action.",
            ),
            summary=f"Draft an outreach message using grounded context for {basis.title}.",
            payload={
                "draft_subject": f"Question about {basis.title}",
                "draft_body": "\n".join(body_lines),
                "send_enabled": False,
                "evidence_backed_claims": (evidence_claim,),
                "user_provided_claims": user_claims,
                "execution_note": "No outreach sending mechanism is invoked by Layer 26C.",
            },
            warnings=(
                "Outreach is drafted only; employer contact is not performed.",
                *basis.warnings,
            ),
        )

    def _application_checklist_preview(
        self,
        user_id: str,
        request: CareerAgentToolRequest,
        *,
        basis: _GroundedToolBasis,
        now: datetime,
    ) -> CareerAgentToolPreview:
        has_opportunity = any(
            ref.evidence_type is CareerAgentEvidenceType.OPPORTUNITY
            for ref in basis.evidence_refs
        )
        items = [
            "Verify eligibility against the official source before applying.",
            "Confirm location, program type, and required materials manually.",
            "Prepare resume and role-specific notes locally; do not submit through the agent.",
        ]
        if has_opportunity:
            items.append(
                "Check the stored opportunity source for any listed timing before using dates."
            )
        return _preview(
            user_id,
            request,
            basis=basis,
            now=now,
            status=CareerAgentToolStatus.PREVIEW_READY,
            action_boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
            privacy=CareerAgentToolPrivacy.USER_PRIVATE,
            approval=_approval(
                required=False,
                boundary=CareerAgentActionBoundary.READ_ONLY_PREVIEW,
                reason="Application-prep checklists are read-only preparation actions.",
            ),
            summary=f"Prepare an application checklist for {basis.title}.",
            payload={
                "checklist_items": items,
                "submission_performed": False,
                "contact_performed": False,
                "deadline_policy": (
                    "Dates appear only when the user verifies trusted opportunity "
                    "sources."
                ),
            },
            warnings=(
                "The checklist does not apply, submit materials, contact employers, "
                "or promise outcomes.",
                *basis.warnings,
            ),
        )

    def _get_row(self, user_id: str, tool_request_id: str) -> CareerAgentToolRecord:
        row = self._session.execute(
            select(CareerAgentToolRecord).where(
                CareerAgentToolRecord.user_id == user_id,
                CareerAgentToolRecord.career_agent_tool_id == tool_request_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise CareerAgentToolNotFound(tool_request_id)
        return row

    def _preview_from_record(self, row: CareerAgentToolRecord) -> CareerAgentToolPreview:
        audit_events = tuple(
            CareerAgentToolAuditEvent(
                event_type=event.event_type,  # type: ignore[arg-type]
                occurred_at=event.created_at,
                summary=event.summary,
            )
            for event in self._session.execute(
                select(CareerAgentToolAuditEventRecord)
                .where(
                    CareerAgentToolAuditEventRecord.career_agent_tool_id
                    == row.career_agent_tool_id
                )
                .order_by(CareerAgentToolAuditEventRecord.created_at)
            ).scalars()
        )
        preview = CareerAgentToolPreview(
            tool_request_id=row.career_agent_tool_id,
            tool_type=CareerAgentToolType(row.tool_type),
            proposed_action_summary=row.proposed_action_summary,
            user_visible_preview=dict(row.preview_payload),
            evidence_refs=tuple(
                CareerAgentEvidenceRef.model_validate(ref)
                for ref in (row.evidence_refs or [])
            ),
            freshness=CareerAgentFreshness.model_validate(row.freshness),
            uncertainty=CareerAgentUncertainty.model_validate(row.uncertainty),
            warnings=tuple(row.warnings or []),
            approval_requirement=CareerAgentApprovalRequirement(
                approval_required=row.approval_required,
                explicit_user_approval_required=row.explicit_user_approval_required,
                reason=row.approval_reason,
                boundary=CareerAgentActionBoundary(row.action_boundary),
                approval_button_label=(
                    "Approve prepared action" if row.approval_required else None
                ),
                runtime_execution_available=False,
            ),
            action_boundary=CareerAgentActionBoundary(row.action_boundary),
            status=CareerAgentToolStatus(row.status),
            privacy_classification=CareerAgentToolPrivacy(row.privacy_classification),
            source_answer_id=row.source_answer_id,
            source_plan_id=row.source_plan_id,
            user_id=row.user_id,
            runtime_execution_performed=row.runtime_execution_performed,
            created_at=row.created_at,
            updated_at=row.updated_at,
            audit_events=audit_events,
        )
        validate_career_agent_tool_preview(preview)
        return preview

    def _add_audit(
        self,
        row: CareerAgentToolRecord,
        *,
        event_type: str,
        summary: str,
        now: datetime | None = None,
    ) -> None:
        timestamp = _aware(now or datetime.now(UTC))
        self._session.add(
            CareerAgentToolAuditEventRecord(
                career_agent_tool_audit_event_id=_stable_id(
                    "career_agent_tool_audit",
                    row.career_agent_tool_id,
                    event_type,
                    timestamp.isoformat(),
                ),
                career_agent_tool_id=row.career_agent_tool_id,
                user_id=row.user_id,
                event_type=event_type,
                summary=summary,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )


def _preview(
    user_id: str,
    request: CareerAgentToolRequest,
    *,
    basis: _GroundedToolBasis,
    now: datetime,
    status: CareerAgentToolStatus,
    action_boundary: CareerAgentActionBoundary,
    privacy: CareerAgentToolPrivacy,
    approval: CareerAgentApprovalRequirement,
    summary: str,
    payload: dict,
    warnings: tuple[str, ...],
) -> CareerAgentToolPreview:
    warnings = _dedupe_strings((*warnings, *_partner_warnings(basis)))
    preview = CareerAgentToolPreview(
        tool_request_id=_stable_id(
            "career_agent_tool",
            user_id,
            request.tool_type.value,
            now.isoformat(),
            basis.source_answer_id or basis.source_plan_id or basis.title,
        ),
        tool_type=request.tool_type,
        proposed_action_summary=summary,
        user_visible_preview=payload,
        evidence_refs=basis.evidence_refs,
        freshness=basis.freshness,
        uncertainty=basis.uncertainty,
        warnings=warnings,
        approval_requirement=approval,
        action_boundary=action_boundary,
        status=status,
        privacy_classification=privacy,
        source_answer_id=basis.source_answer_id,
        source_plan_id=basis.source_plan_id,
        user_id=user_id,
        runtime_execution_performed=False,
        created_at=now,
        updated_at=now,
    )
    validate_career_agent_tool_preview(preview)
    return preview


def _approval(
    *,
    required: bool,
    boundary: CareerAgentActionBoundary,
    reason: str,
    runtime_available: bool = False,
) -> CareerAgentApprovalRequirement:
    return CareerAgentApprovalRequirement(
        approval_required=required,
        explicit_user_approval_required=required,
        reason=reason,
        boundary=boundary,
        approval_button_label="Approve prepared action" if required else None,
        runtime_execution_available=runtime_available,
    )


def _record_from_preview(preview: CareerAgentToolPreview) -> CareerAgentToolRecord:
    return CareerAgentToolRecord(
        career_agent_tool_id=preview.tool_request_id,
        user_id=preview.user_id or "",
        tool_type=preview.tool_type.value,
        status=preview.status.value,
        action_boundary=preview.action_boundary.value,
        privacy_classification=preview.privacy_classification.value,
        approval_required=preview.approval_requirement.approval_required,
        explicit_user_approval_required=(
            preview.approval_requirement.explicit_user_approval_required
        ),
        approval_reason=preview.approval_requirement.reason,
        proposed_action_summary=preview.proposed_action_summary,
        preview_payload=preview.user_visible_preview,
        evidence_refs=[
            ref.model_dump(mode="json")
            for ref in preview.evidence_refs
        ],
        freshness=preview.freshness.model_dump(mode="json"),
        uncertainty=preview.uncertainty.model_dump(mode="json"),
        warnings=list(preview.warnings),
        source_answer_id=preview.source_answer_id,
        source_plan_id=preview.source_plan_id,
        runtime_execution_performed=False,
        created_at=preview.created_at,
        updated_at=preview.updated_at,
    )


def _blocked_reason(
    request: CareerAgentToolRequest,
    basis: _GroundedToolBasis,
) -> str | None:
    del basis
    if request.tool_type is CareerAgentToolType.JOB_APPLICATION_SUBMISSION:
        return "Autonomous job applications are prohibited."
    if request.requested_action is CareerAgentRequestedToolAction.SUBMIT_APPLICATION:
        return "Job application submission is prohibited for the career agent."
    if (
        request.tool_type is CareerAgentToolType.OUTREACH_DRAFT
        and request.requested_action is CareerAgentRequestedToolAction.SEND
    ):
        return "Outreach sending is blocked; the career agent may draft only."
    return None


def _unsupported_opportunity_ids(
    requested_ids: tuple[str, ...],
    evidence_refs: tuple[CareerAgentEvidenceRef, ...],
) -> tuple[str, ...]:
    supported = {
        ref.entity_id
        for ref in evidence_refs
        if ref.evidence_type is CareerAgentEvidenceType.OPPORTUNITY
    }
    return tuple(item for item in requested_ids if item not in supported)


def _watchlist_suggestions(
    evidence_refs: tuple[CareerAgentEvidenceRef, ...],
    *,
    limit: int,
) -> tuple[dict, ...]:
    suggestions: list[dict] = []
    for ref in evidence_refs:
        if ref.evidence_type is CareerAgentEvidenceType.COMPANY:
            artifact_type = "company"
        elif ref.evidence_type is CareerAgentEvidenceType.REGION:
            artifact_type = "region"
        elif ref.evidence_type is CareerAgentEvidenceType.OPPORTUNITY:
            artifact_type = "opportunity"
        else:
            continue
        suggestions.append(
            {
                "artifact_type": artifact_type,
                "artifact_ref": ref.entity_id,
                "label": ref.label,
                "evidence_ref_id": ref.ref_id,
            }
        )
        if len(suggestions) >= limit:
            break
    return tuple(suggestions)


def _first_evidence_claim(evidence_refs: tuple[CareerAgentEvidenceRef, ...]) -> str:
    if not evidence_refs:
        return "No unsupported market claim is included."
    first = evidence_refs[0]
    return f"{first.label}: {first.summary}"


def _partner_warnings(basis: _GroundedToolBasis) -> tuple[str, ...]:
    text = " ".join(
        (
            *basis.warnings,
            *(ref.summary for ref in basis.evidence_refs),
            *(ref.confidence_label or "" for ref in basis.evidence_refs),
        )
    ).casefold()
    if "paid partner" in text or "partner_submitted" in text or "partner-submitted" in text:
        return (
            "Paid/partner influence is disclosed and does not authorize ranking or "
            "tool execution bias.",
        )
    return ()


def _dedupe_refs(refs) -> tuple[CareerAgentEvidenceRef, ...]:  # noqa: ANN001
    seen: set[str] = set()
    deduped: list[CareerAgentEvidenceRef] = []
    for ref in refs:
        if ref.ref_id in seen:
            continue
        seen.add(ref.ref_id)
        deduped.append(ref)
    return tuple(deduped)


def _dedupe_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in values if item))


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join((prefix, *parts))
    return f"{prefix}_{uuid5(NAMESPACE_URL, joined).hex[:24]}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
