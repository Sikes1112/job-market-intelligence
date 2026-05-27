"""Repository helpers for institutional organization state."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.institutions.models import (
    InstitutionalAuditLog,
    InstitutionalDataRequest,
    InstitutionalReport,
    Organization,
    OrganizationMembership,
)
from backend.users.models import User


class InstitutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get_organization(self, organization_id: str) -> Organization | None:
        return self._session.get(Organization, organization_id)

    def add_organization(self, organization: Organization) -> None:
        self._session.add(organization)

    def user_exists(self, user_id: str) -> bool:
        return self._session.get(User, user_id) is not None

    def get_membership(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> OrganizationMembership | None:
        return self._session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
        ).scalar_one_or_none()

    def get_membership_by_id(
        self,
        organization_membership_id: str,
    ) -> OrganizationMembership | None:
        return self._session.get(OrganizationMembership, organization_membership_id)

    def list_active_memberships_for_user(
        self,
        user_id: str,
    ) -> list[OrganizationMembership]:
        rows = self._session.execute(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == "active",
            )
            .order_by(
                OrganizationMembership.organization_id,
                OrganizationMembership.organization_membership_id,
            )
        ).scalars()
        return list(rows)

    def list_memberships_for_organization(
        self,
        organization_id: str,
    ) -> list[OrganizationMembership]:
        rows = self._session.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(
                OrganizationMembership.role,
                OrganizationMembership.user_id,
                OrganizationMembership.organization_membership_id,
            )
        ).scalars()
        return list(rows)

    def add_membership(self, membership: OrganizationMembership) -> None:
        self._session.add(membership)

    def add_audit_log(self, audit_log: InstitutionalAuditLog) -> None:
        self._session.add(audit_log)

    def add_report(self, report: InstitutionalReport) -> None:
        self._session.add(report)

    def get_report(self, report_id: str) -> InstitutionalReport | None:
        return self._session.get(InstitutionalReport, report_id)

    def list_reports_for_organization(
        self,
        organization_id: str,
    ) -> list[InstitutionalReport]:
        rows = self._session.execute(
            select(InstitutionalReport)
            .where(InstitutionalReport.organization_id == organization_id)
            .order_by(
                InstitutionalReport.generated_at.desc(),
                InstitutionalReport.institutional_report_id.desc(),
            )
        ).scalars()
        return list(rows)

    def add_data_request(self, data_request: InstitutionalDataRequest) -> None:
        self._session.add(data_request)

    def list_data_requests_for_organization(
        self,
        organization_id: str,
    ) -> list[InstitutionalDataRequest]:
        rows = self._session.execute(
            select(InstitutionalDataRequest)
            .where(InstitutionalDataRequest.organization_id == organization_id)
            .order_by(
                InstitutionalDataRequest.created_at.desc(),
                InstitutionalDataRequest.institutional_data_request_id.desc(),
            )
        ).scalars()
        return list(rows)

    def list_data_requests_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> list[InstitutionalDataRequest]:
        rows = self._session.execute(
            select(InstitutionalDataRequest)
            .where(
                InstitutionalDataRequest.organization_id == organization_id,
                InstitutionalDataRequest.subject_user_id == user_id,
            )
            .order_by(
                InstitutionalDataRequest.created_at.desc(),
                InstitutionalDataRequest.institutional_data_request_id.desc(),
            )
        ).scalars()
        return list(rows)

    def list_audit_logs(
        self,
        *,
        organization_id: str,
        limit: int = 100,
    ) -> list[InstitutionalAuditLog]:
        rows = self._session.execute(
            select(InstitutionalAuditLog)
            .where(InstitutionalAuditLog.organization_id == organization_id)
            .order_by(
                InstitutionalAuditLog.created_at.desc(),
                InstitutionalAuditLog.institutional_audit_log_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def flush(self) -> None:
        self._session.flush()
