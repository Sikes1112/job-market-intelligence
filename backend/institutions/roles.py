"""Institutional role and status vocabulary."""

from __future__ import annotations

from enum import StrEnum


class OrganizationType(StrEnum):
    SCHOOL = "school"
    CAREER_CENTER = "career_center"
    BOOTCAMP = "bootcamp"
    WORKFORCE_ORG = "workforce_org"
    ECONOMIC_DEVELOPMENT_PARTNER = "economic_development_partner"
    INTERNAL_DEMO = "internal_demo"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class OrganizationRole(StrEnum):
    ORG_ADMIN = "ORG_ADMIN"
    ADVISOR = "ADVISOR"
    STUDENT = "STUDENT"
    REPORT_VIEWER = "REPORT_VIEWER"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class OrganizationMembershipStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InstitutionalAuditAction(StrEnum):
    ORGANIZATION_VIEWED = "organization_viewed"
    ORGANIZATION_MEMBERS_VIEWED = "organization_members_viewed"
    ORGANIZATION_MEMBER_ADDED = "organization_member_added"
    ORGANIZATION_MEMBER_UPDATED = "organization_member_updated"
    INSTITUTION_DASHBOARD_VIEWED = "institution_dashboard_viewed"
    ADVISOR_COMPARE_REGIONS_USED = "advisor_compare_regions_used"
    ADVISOR_COMPARE_INDUSTRIES_USED = "advisor_compare_industries_used"
    ADVISOR_COMPARE_COMPANIES_USED = "advisor_compare_companies_used"
    ADVISOR_COMPARE_CAREER_STAGES_USED = "advisor_compare_career_stages_used"
    ADVISOR_APPLICATION_TIMING_USED = "advisor_application_timing_used"
    INSTITUTIONAL_REPORT_GENERATED = "institutional_report_generated"
    INSTITUTIONAL_REPORT_VIEWED = "institutional_report_viewed"
    INSTITUTIONAL_REPORTS_LISTED = "institutional_reports_listed"
    INSTITUTIONAL_DATA_REQUEST_CREATED = "institutional_data_request_created"
    INSTITUTIONAL_DATA_REQUESTS_LISTED = "institutional_data_requests_listed"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


ORG_ADMIN_ROLES: frozenset[OrganizationRole] = frozenset({OrganizationRole.ORG_ADMIN})
ORGANIZATION_SURFACE_ROLES: frozenset[OrganizationRole] = frozenset(
    {
        OrganizationRole.ORG_ADMIN,
        OrganizationRole.ADVISOR,
        OrganizationRole.REPORT_VIEWER,
    }
)
AUDIT_LOG_ROLES: frozenset[OrganizationRole] = ORG_ADMIN_ROLES
ADVISOR_TOOL_ROLES: frozenset[OrganizationRole] = frozenset(
    {
        OrganizationRole.ORG_ADMIN,
        OrganizationRole.ADVISOR,
    }
)
INSTITUTIONAL_REPORT_ROLES: frozenset[OrganizationRole] = ORGANIZATION_SURFACE_ROLES
DATA_REQUEST_ADMIN_ROLES: frozenset[OrganizationRole] = ORG_ADMIN_ROLES
PARTNER_IMPORT_VIEW_ROLES: frozenset[OrganizationRole] = ORGANIZATION_SURFACE_ROLES
PARTNER_IMPORT_UPLOAD_ROLES: frozenset[OrganizationRole] = ADVISOR_TOOL_ROLES
PARTNER_IMPORT_REVIEW_ROLES: frozenset[OrganizationRole] = ORG_ADMIN_ROLES


def parse_organization_role(value: OrganizationRole | str | None) -> OrganizationRole | None:
    if isinstance(value, OrganizationRole):
        return value
    if value is None:
        return None
    try:
        return OrganizationRole(value)
    except ValueError:
        return None
