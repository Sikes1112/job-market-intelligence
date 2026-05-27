"""Institutional domain exceptions."""

from __future__ import annotations


class OrganizationNotFound(Exception):
    def __init__(self, organization_id: str) -> None:
        super().__init__(organization_id)
        self.organization_id = organization_id


class InstitutionalAccessDenied(Exception):
    def __init__(self, organization_id: str) -> None:
        super().__init__(organization_id)
        self.organization_id = organization_id


class OrganizationMembershipNotFound(Exception):
    def __init__(self, organization_membership_id: str) -> None:
        super().__init__(organization_membership_id)
        self.organization_membership_id = organization_membership_id


class OrganizationMembershipAlreadyExists(Exception):
    def __init__(self, organization_id: str, user_id: str) -> None:
        super().__init__(organization_id, user_id)
        self.organization_id = organization_id
        self.user_id = user_id


class OrganizationMembershipUserNotFound(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__(user_id)
        self.user_id = user_id


class InstitutionalReportNotFound(Exception):
    def __init__(self, report_id: str) -> None:
        super().__init__(report_id)
        self.report_id = report_id
