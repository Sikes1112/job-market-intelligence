"""Protected admin foundation and review routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog
from backend.admin.overrides import (
    AdminOverrideCreateInput,
    AdminOverrideMutationInput,
    AdminOverrideService,
    AdminRepairActionCreateInput,
    AdminRepairActionExecuteInput,
    AdminRepairActionService,
    OverrideNotFound,
    OverrideStatus,
    OverrideTargetType,
    OverrideWorkflowError,
    RepairActionNotFound,
    RepairActionStatus,
    RepairActionType,
    RepairActionWorkflowError,
    admin_override_data,
    admin_repair_action_data,
)
from backend.admin.repository import AdminEventLogRepository
from backend.admin.review import (
    AdminReviewService,
    AuditFindingLifecycleError,
    AuditFindingLifecycleService,
    AuditFindingNotFound,
    AuditFindingTransitionInput,
    audit_finding_review_data,
)
from backend.admin.roles import can_admin_mutate, can_read_admin_data, can_review_data
from backend.admin.service import AdminEventLogService
from backend.api.dependencies import (
    CurrentAdmin,
    get_session,
    require_admin_mutation_access,
    require_admin_read_access,
    require_data_review_access,
)
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.request_context import get_request_id
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import SourceRef

router = APIRouter(prefix="/admin", tags=["admin"])


def _event_log_service(session: Session) -> AdminEventLogService:
    return AdminEventLogService(AdminEventLogRepository(session))


def _review_service(session: Session) -> AdminReviewService:
    return AdminReviewService(session=session)


def _override_service(session: Session) -> AdminOverrideService:
    return AdminOverrideService(session=session)


def _repair_action_service(session: Session) -> AdminRepairActionService:
    return AdminRepairActionService(session=session)


@router.get("/me")
def get_admin_access(
    admin: CurrentAdmin = Depends(require_admin_read_access),
) -> dict:
    role = admin.role
    return lightweight_success_envelope(
        data={
            "user_id": admin.current.user.user_id,
            "role": role.value,
            "capabilities": {
                "read_admin_data": can_read_admin_data(role),
                "review_data": can_review_data(role),
                "controlled_admin_mutations": can_admin_mutate(role),
            },
        }
    )


@router.get("/event-log")
def list_admin_event_log(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _event_log_service(session).list_events(limit=limit)
    return lightweight_success_envelope(
        data={"admin_event_log": [_admin_event_log_data(row) for row in rows]}
    )


@router.get("/review/companies")
def list_review_companies(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_companies(limit=limit)
    return lightweight_success_envelope(
        data={"companies": [_company_data(row, session=session) for row in rows]}
    )


@router.get("/review/companies/{company_id}")
def get_review_company(
    company_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _review_service(session).get_company(company_id)
    if row is None:
        return _not_found(f"Company not found: {company_id!r}")
    return lightweight_success_envelope(data=_company_data(row, session=session))


@router.get("/review/presence")
def list_review_presence(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_presence(limit=limit)
    return lightweight_success_envelope(
        data={"presence_facts": [_presence_data(row, session=session) for row in rows]}
    )


@router.get("/review/presence/{presence_id}")
def get_review_presence(
    presence_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _review_service(session).get_presence(presence_id)
    if row is None:
        return _not_found(f"Presence fact not found: {presence_id!r}")
    return lightweight_success_envelope(data=_presence_data(row, session=session))


@router.get("/review/hiring")
def list_review_hiring(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_hiring(limit=limit)
    return lightweight_success_envelope(
        data={"hiring_facts": [_hiring_data(row) for row in rows]}
    )


@router.get("/review/hiring/{hiring_id}")
def get_review_hiring(
    hiring_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _review_service(session).get_hiring(hiring_id)
    if row is None:
        return _not_found(f"Hiring fact not found: {hiring_id!r}")
    return lightweight_success_envelope(data=_hiring_data(row))


@router.get("/review/entry-level")
def list_review_entry_level(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_entry_level(limit=limit)
    return lightweight_success_envelope(
        data={"entry_level_facts": [_entry_level_data(row) for row in rows]}
    )


@router.get("/review/entry-level/{entry_level_id}")
def get_review_entry_level(
    entry_level_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _review_service(session).get_entry_level(entry_level_id)
    if row is None:
        return _not_found(f"Entry-level fact not found: {entry_level_id!r}")
    return lightweight_success_envelope(data=_entry_level_data(row))


@router.get("/review/source-refs")
def list_review_source_refs(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_source_refs(limit=limit)
    return lightweight_success_envelope(
        data={"source_refs": [_source_ref_data(row, session=session) for row in rows]}
    )


@router.get("/review/source-refs/{source_id}")
def get_review_source_ref(
    source_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _review_service(session).get_source_ref(source_id)
    if row is None:
        return _not_found(f"Source ref not found: {source_id!r}")
    return lightweight_success_envelope(data=_source_ref_data(row, session=session))


@router.get("/review/audit-findings")
def list_review_audit_findings(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _review_service(session).list_audit_findings(limit=limit)
    return lightweight_success_envelope(
        data={"audit_findings": [audit_finding_review_data(row) for row in rows]}
    )


@router.post("/review/audit-finding-transitions")
def transition_review_audit_finding(
    transition: AuditFindingTransitionInput,
    admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    try:
        view = AuditFindingLifecycleService(session=session).transition(
            transition,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except AuditFindingNotFound:
        return _not_found(f"Audit finding not found: {transition.finding_id!r}")
    except AuditFindingLifecycleError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=audit_finding_review_data(view))


@router.get("/review/audit-findings/{finding_id:path}")
def get_review_audit_finding(
    finding_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    view = _review_service(session).get_audit_finding(finding_id)
    if view is None:
        return _not_found(f"Audit finding not found: {finding_id!r}")
    return lightweight_success_envelope(data=audit_finding_review_data(view))


@router.get("/overrides")
def list_admin_overrides(
    limit: int = Query(default=100, ge=1, le=500),
    status: OverrideStatus | None = None,
    target_type: OverrideTargetType | None = None,
    target_id: str | None = None,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _override_service(session).list_overrides(
        limit=limit,
        status=status,
        target_type=target_type,
        target_id=target_id,
    )
    return lightweight_success_envelope(
        data={"overrides": [admin_override_data(row) for row in rows]}
    )


@router.post("/overrides")
def create_admin_override(
    payload: AdminOverrideCreateInput,
    admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    try:
        row = _override_service(session).create_override(
            payload,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except OverrideWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=admin_override_data(row))


@router.get("/overrides/{override_id}")
def get_admin_override(
    override_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _override_service(session).get_override(override_id)
    if row is None:
        return _not_found(f"Override not found: {override_id!r}")
    return lightweight_success_envelope(data=admin_override_data(row))


@router.post("/overrides/{override_id}/activate")
def activate_admin_override(
    override_id: str,
    payload: AdminOverrideMutationInput,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
):
    try:
        row = _override_service(session).activate_override(
            override_id,
            payload,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except OverrideNotFound:
        return _not_found(f"Override not found: {override_id!r}")
    except OverrideWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=admin_override_data(row))


@router.post("/overrides/{override_id}/revoke")
def revoke_admin_override(
    override_id: str,
    payload: AdminOverrideMutationInput,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
):
    try:
        row = _override_service(session).revoke_override(
            override_id,
            payload,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except OverrideNotFound:
        return _not_found(f"Override not found: {override_id!r}")
    except OverrideWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=admin_override_data(row))


@router.get("/repair-actions")
def list_admin_repair_actions(
    limit: int = Query(default=100, ge=1, le=500),
    status: RepairActionStatus | None = None,
    action_type: RepairActionType | None = None,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
) -> dict:
    rows = _repair_action_service(session).list_actions(
        limit=limit,
        status=status,
        action_type=action_type,
    )
    return lightweight_success_envelope(
        data={"repair_actions": [admin_repair_action_data(row) for row in rows]}
    )


@router.post("/repair-actions")
def create_admin_repair_action(
    payload: AdminRepairActionCreateInput,
    admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    try:
        row = _repair_action_service(session).create_action(
            payload,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except RepairActionWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=admin_repair_action_data(row))


@router.get("/repair-actions/{repair_action_id}")
def get_admin_repair_action(
    repair_action_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
):
    row = _repair_action_service(session).get_action(repair_action_id)
    if row is None:
        return _not_found(f"Repair action not found: {repair_action_id!r}")
    return lightweight_success_envelope(data=admin_repair_action_data(row))


@router.post("/repair-actions/{repair_action_id}/execute")
def execute_admin_repair_action(
    repair_action_id: str,
    payload: AdminRepairActionExecuteInput,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
):
    try:
        row = _repair_action_service(session).execute_action(
            repair_action_id,
            payload,
            actor=admin.current.user.user_id,
            role=admin.role,
            request_id=get_request_id(),
        )
    except RepairActionNotFound:
        return _not_found(f"Repair action not found: {repair_action_id!r}")
    except RepairActionWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=admin_repair_action_data(row))


def _admin_event_log_data(row: AdminEventLog) -> dict[str, Any]:
    return {
        "admin_event_id": row.admin_event_id,
        "actor": row.actor,
        "role": row.actor_role,
        "action": row.action,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "before_state": row.before_state,
        "after_state": row.after_state,
        "reason": row.reason,
        "timestamp": _dt(row.timestamp),
        "request_id": row.request_id,
    }


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _company_data(row: Company, *, session: Session | None = None) -> dict[str, Any]:
    return {
        **_canonical_data(row),
        "company_id": row.company_id,
        "company_name": row.company_name,
        "normalized_company_name": row.normalized_company_name,
        "sector_primary": row.sector_primary,
        "sector_secondary": row.sector_secondary,
        "public_or_private": row.public_or_private,
        "eligibility_status": row.eligibility_status,
        "eligibility_score": row.eligibility_score,
        "eligibility_override_flag": row.eligibility_override_flag,
        "eligibility_override_reason": row.eligibility_override_reason,
        "classification_confidence": row.classification_confidence,
        "is_major_tech": row.is_major_tech,
        "major_tech_score": row.major_tech_score,
        "is_mag7": row.is_mag7,
        "prestige_score": row.prestige_score,
        "active_overrides": _active_overrides(
            session,
            OverrideTargetType.COMPANY,
            row.company_id,
        ),
    }


def _presence_data(
    row: CompanyRegionPresence,
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    return {
        **_canonical_data(row),
        "presence_id": row.presence_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "presence_status": row.presence_status,
        "presence_basis": row.presence_basis,
        "office_evidence_flag": row.office_evidence_flag,
        "operations_evidence_flag": row.operations_evidence_flag,
        "hiring_evidence_flag": row.hiring_evidence_flag,
        "presence_confidence": row.presence_confidence,
        "source_refs": row.source_refs,
        "active_overrides": _active_overrides(
            session,
            OverrideTargetType.PRESENCE_FACT,
            row.presence_id,
        ),
    }


def _hiring_data(row: CompanyRegionHiring) -> dict[str, Any]:
    return {
        **_canonical_data(row),
        "hiring_id": row.hiring_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "currently_hiring_flag": row.currently_hiring_flag,
        "active_posting_count_now": row.active_posting_count_now,
        "posting_count_30d": row.posting_count_30d,
        "posting_count_90d": row.posting_count_90d,
        "annualized_trend_signal": row.annualized_trend_signal,
        "seasonal_student_hiring_signal": row.seasonal_student_hiring_signal,
        "hiring_program_count": row.hiring_program_count,
        "role_family_summary": row.role_family_summary,
        "hiring_confidence": row.hiring_confidence,
        "freshness_expires_at": _dt(row.freshness_expires_at),
        "source_refs": row.source_refs,
        "active_overrides": [],
    }


def _entry_level_data(row: CompanyRegionEntryLevel) -> dict[str, Any]:
    return {
        **_canonical_data(row),
        "entry_level_id": row.entry_level_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "internship_count": row.internship_count,
        "coop_count": row.coop_count,
        "entry_level_full_time_count": row.entry_level_full_time_count,
        "formal_early_career_program_flag": row.formal_early_career_program_flag,
        "student_season_recurrence_signal": row.student_season_recurrence_signal,
        "entry_level_access_score": row.entry_level_access_score,
        "entry_level_confidence": row.entry_level_confidence,
        "freshness_expires_at": _dt(row.freshness_expires_at),
        "source_refs": row.source_refs,
        "active_overrides": [],
    }


def _source_ref_data(
    row: SourceRef,
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    return {
        **_canonical_data(row),
        "source_id": row.source_id,
        "source_type": row.source_type,
        "source_name": row.source_name,
        "url_or_provider": row.url_or_provider,
        "collected_at": _dt(row.collected_at),
        "observed_at": _dt(row.observed_at),
        "license_or_terms_category": row.license_or_terms_category,
        "confidence": row.confidence,
        "data_origin": row.data_origin,
        "notes": row.notes,
        "active_overrides": _active_overrides(
            session,
            OverrideTargetType.SOURCE_REF,
            row.source_id,
        ),
    }


def _canonical_data(row: Any) -> dict[str, Any]:
    return {
        "state": row.state,
        "version": row.version,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _active_overrides(
    session: Session | None,
    target_type: OverrideTargetType,
    target_id: str,
) -> list[dict[str, Any]]:
    if session is None:
        return []
    rows = _override_service(session).list_active_for_target(target_type, target_id)
    return [admin_override_data(row) for row in rows]


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
