"""Reusable organization-aware permission helpers."""

from __future__ import annotations

from enum import StrEnum

from backend.institutions.models import OrganizationMembership
from backend.institutions.repository import InstitutionRepository
from backend.institutions.roles import (
    ADVISOR_TOOL_ROLES,
    AUDIT_LOG_ROLES,
    DATA_REQUEST_ADMIN_ROLES,
    INSTITUTIONAL_REPORT_ROLES,
    ORG_ADMIN_ROLES,
    ORGANIZATION_SURFACE_ROLES,
    PARTNER_IMPORT_REVIEW_ROLES,
    PARTNER_IMPORT_UPLOAD_ROLES,
    PARTNER_IMPORT_VIEW_ROLES,
    OrganizationMembershipStatus,
    OrganizationRole,
    parse_organization_role,
)


class InstitutionalAction(StrEnum):
    VIEW_ORGANIZATION = "view_organization"
    VIEW_DASHBOARD = "view_dashboard"
    USE_ADVISOR_TOOLS = "use_advisor_tools"
    VIEW_REPORTS = "view_reports"
    MANAGE_DATA_REQUESTS = "manage_data_requests"
    VIEW_MEMBERS = "view_members"
    MANAGE_MEMBERS = "manage_members"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    VIEW_PARTNER_IMPORTS = "view_partner_imports"
    UPLOAD_PARTNER_IMPORTS = "upload_partner_imports"
    REVIEW_PARTNER_IMPORTS = "review_partner_imports"


REQUIRED_ROLES_BY_ACTION: dict[InstitutionalAction, frozenset[OrganizationRole]] = {
    InstitutionalAction.VIEW_ORGANIZATION: ORGANIZATION_SURFACE_ROLES,
    InstitutionalAction.VIEW_DASHBOARD: ORGANIZATION_SURFACE_ROLES,
    InstitutionalAction.USE_ADVISOR_TOOLS: ADVISOR_TOOL_ROLES,
    InstitutionalAction.VIEW_REPORTS: INSTITUTIONAL_REPORT_ROLES,
    InstitutionalAction.MANAGE_DATA_REQUESTS: DATA_REQUEST_ADMIN_ROLES,
    InstitutionalAction.VIEW_MEMBERS: ORG_ADMIN_ROLES,
    InstitutionalAction.MANAGE_MEMBERS: ORG_ADMIN_ROLES,
    InstitutionalAction.VIEW_AUDIT_LOGS: AUDIT_LOG_ROLES,
    InstitutionalAction.VIEW_PARTNER_IMPORTS: PARTNER_IMPORT_VIEW_ROLES,
    InstitutionalAction.UPLOAD_PARTNER_IMPORTS: PARTNER_IMPORT_UPLOAD_ROLES,
    InstitutionalAction.REVIEW_PARTNER_IMPORTS: PARTNER_IMPORT_REVIEW_ROLES,
}


def active_membership_for_user(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> OrganizationMembership | None:
    membership = repository.get_membership(
        organization_id=organization_id,
        user_id=user_id,
    )
    if membership is None:
        return None
    if membership.status != OrganizationMembershipStatus.ACTIVE.value:
        return None
    return membership


def is_active_member(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return (
        active_membership_for_user(
            repository,
            user_id=user_id,
            organization_id=organization_id,
        )
        is not None
    )


def has_required_institutional_role(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
    required_roles: frozenset[OrganizationRole],
) -> bool:
    membership = active_membership_for_user(
        repository,
        user_id=user_id,
        organization_id=organization_id,
    )
    if membership is None:
        return False
    role = parse_organization_role(membership.role)
    return role in required_roles


def can_administer_organization(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=ORG_ADMIN_ROLES,
    )


def can_view_organization_surfaces(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=ORGANIZATION_SURFACE_ROLES,
    )


def can_access_audit_logs(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=AUDIT_LOG_ROLES,
    )


def can_use_advisor_tools(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=ADVISOR_TOOL_ROLES,
    )


def can_view_institutional_reports(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=INSTITUTIONAL_REPORT_ROLES,
    )


def can_manage_data_requests(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=DATA_REQUEST_ADMIN_ROLES,
    )


def can_view_partner_imports(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=PARTNER_IMPORT_VIEW_ROLES,
    )


def can_upload_partner_imports(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=PARTNER_IMPORT_UPLOAD_ROLES,
    )


def can_review_partner_imports(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=PARTNER_IMPORT_REVIEW_ROLES,
    )


def can_access_student_private_data(
    _repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
    student_user_id: str | None = None,
) -> bool:
    """Student-specific advising access is deferred until explicit consent exists."""

    _ = (user_id, organization_id, student_user_id)
    return False


def can_perform_institutional_action(
    repository: InstitutionRepository,
    *,
    user_id: str,
    organization_id: str,
    action: InstitutionalAction,
) -> bool:
    required_roles = REQUIRED_ROLES_BY_ACTION[action]
    return has_required_institutional_role(
        repository,
        user_id=user_id,
        organization_id=organization_id,
        required_roles=required_roles,
    )
