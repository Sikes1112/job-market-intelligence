"""Institutional organization service and audit-log helpers."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.institutions.advisor import (
    AdvisorApplicationTimingRequest,
    AdvisorCareerStageComparisonRequest,
    AdvisorCompanyComparisonRequest,
    AdvisorIndustryComparisonRequest,
    AdvisorRegionComparisonRequest,
    AdvisorToolResponse,
    build_application_timing,
    build_career_stage_comparison,
    build_company_comparison,
    build_industry_comparison,
    build_region_comparison,
)
from backend.institutions.dashboard import (
    InstitutionalDashboardPayload,
    build_institutional_dashboard,
)
from backend.institutions.data_requests import (
    InstitutionalDataRequestCreateInput,
    InstitutionalDataRequestListPayload,
    InstitutionalDataRequestPayload,
    InstitutionalDataRequestStatus,
    InstitutionalDataRequestSubjectType,
    InstitutionalDataRequestType,
)
from backend.institutions.decision_infrastructure import (
    CurriculumMarketMappingPayload,
    InstitutionBenchmarkPayload,
    InstitutionDecisionDashboardPayload,
    InstitutionWorkforceReportPayload,
    InstitutionWorkforceReportType,
    build_curriculum_market_mapping,
    build_decision_dashboard,
    build_institution_benchmarks,
    build_workforce_report,
)
from backend.institutions.exceptions import (
    InstitutionalAccessDenied,
    InstitutionalReportNotFound,
    OrganizationMembershipAlreadyExists,
    OrganizationMembershipNotFound,
    OrganizationMembershipUserNotFound,
    OrganizationNotFound,
)
from backend.institutions.models import (
    InstitutionalAuditLog,
    InstitutionalDataRequest,
    InstitutionalReport,
    Organization,
    OrganizationMembership,
)
from backend.institutions.permissions import (
    InstitutionalAction,
    active_membership_for_user,
    can_perform_institutional_action,
)
from backend.institutions.reports import (
    InstitutionalReportCreateInput,
    InstitutionalReportListPayload,
    InstitutionalReportPayload,
    InstitutionalReportSummary,
    build_institutional_report,
    coverage_summary,
    privacy_summary,
    report_summary_from_payload,
)
from backend.institutions.repository import InstitutionRepository
from backend.institutions.roles import (
    InstitutionalAuditAction,
    OrganizationMembershipStatus,
    OrganizationRole,
    parse_organization_role,
)


class OrganizationMembershipCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    role: OrganizationRole
    status: OrganizationMembershipStatus = OrganizationMembershipStatus.ACTIVE

    @field_validator("user_id")
    @classmethod
    def _required_strings_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class OrganizationMembershipUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: OrganizationRole | None = None
    status: OrganizationMembershipStatus | None = None

    @model_validator(mode="after")
    def _has_update(self) -> OrganizationMembershipUpdateInput:
        if self.role is None and self.status is None:
            raise ValueError("role or status is required")
        return self


class InstitutionalAuditLogInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str = Field(min_length=1, max_length=64)
    actor_user_id: str = Field(min_length=1, max_length=64)
    actor_role: OrganizationRole | None = None
    action: InstitutionalAuditAction
    target_type: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=512)
    metadata: dict[str, Any] | list[Any] | None = None

    @field_validator("organization_id", "actor_user_id", "target_type", "target_id", "purpose")
    @classmethod
    def _strings_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class InstitutionService:
    def __init__(self, repository: InstitutionRepository) -> None:
        self._repo = repository

    def list_current_organizations(
        self,
        *,
        user_id: str,
    ) -> list[tuple[Organization, OrganizationMembership]]:
        rows: list[tuple[Organization, OrganizationMembership]] = []
        for membership in self._repo.list_active_memberships_for_user(user_id):
            organization = self._repo.get_organization(membership.organization_id)
            if organization is not None and organization.status == "active":
                rows.append((organization, membership))
        return rows

    def get_organization_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> tuple[Organization, OrganizationMembership]:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_ORGANIZATION,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.ORGANIZATION_VIEWED,
                target_type="organization",
                target_id=organization.organization_id,
                purpose="view organization institutional surface",
            )
        )
        return organization, membership

    def list_members_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> list[OrganizationMembership]:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_MEMBERS,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.ORGANIZATION_MEMBERS_VIEWED,
                target_type="organization",
                target_id=organization.organization_id,
                purpose="view organization membership list",
            )
        )
        return self._repo.list_memberships_for_organization(organization_id)

    def get_dashboard_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        minimum_group_size: int,
    ) -> InstitutionalDashboardPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_DASHBOARD,
        )
        student_memberships = self._repo.list_memberships_for_organization(
            organization.organization_id
        )
        dashboard = build_institutional_dashboard(
            self._repo.session,
            organization=organization,
            student_memberships=student_memberships,
            minimum_group_size=minimum_group_size,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTION_DASHBOARD_VIEWED,
                target_type="organization",
                target_id=organization.organization_id,
                purpose="view aggregate institutional dashboard",
                metadata={
                    "minimum_group_size": dashboard.minimum_group_size,
                    "cohort_size": dashboard.cohort_size,
                    "suppressed_category_sections": [
                        row.section for row in dashboard.suppressed_categories
                    ],
                },
            )
        )
        return dashboard

    def get_decision_dashboard_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        minimum_group_size: int,
    ) -> InstitutionDecisionDashboardPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_DASHBOARD,
        )
        dashboard = self._build_dashboard(
            organization=organization,
            minimum_group_size=minimum_group_size,
        )
        result = build_decision_dashboard(self._repo.session, dashboard=dashboard)
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTION_DASHBOARD_VIEWED,
                target_type="institutional_decision_dashboard",
                target_id=organization.organization_id,
                purpose="view privacy-safe institutional decision dashboard",
                metadata={
                    "minimum_group_size": result.privacy.minimum_cohort_size,
                    "cohort_size": result.privacy.cohort_size,
                    "suppression_applied": result.privacy.suppression_applied,
                    "forecast_note_count": len(result.forecast_notes),
                },
            )
        )
        return result

    def get_curriculum_mapping_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        minimum_group_size: int,
    ) -> CurriculumMarketMappingPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_DASHBOARD,
        )
        dashboard = self._build_dashboard(
            organization=organization,
            minimum_group_size=minimum_group_size,
        )
        result = build_curriculum_market_mapping(
            self._repo.session,
            dashboard=dashboard,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTION_DASHBOARD_VIEWED,
                target_type="institutional_curriculum_market_mapping",
                target_id=organization.organization_id,
                purpose="view privacy-safe curriculum-to-market mapping",
                metadata={
                    "program_count": len(result.programs),
                    "minimum_group_size": result.privacy.minimum_cohort_size,
                    "suppression_applied": result.privacy.suppression_applied,
                },
            )
        )
        return result

    def get_workforce_report_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        report_type: InstitutionWorkforceReportType,
        minimum_group_size: int,
    ) -> InstitutionWorkforceReportPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_REPORTS,
        )
        dashboard = self._build_dashboard(
            organization=organization,
            minimum_group_size=minimum_group_size,
        )
        result = build_workforce_report(
            self._repo.session,
            dashboard=dashboard,
            report_type=report_type,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_REPORT_VIEWED,
                target_type="institutional_workforce_report",
                target_id=report_type.value,
                purpose="view generated privacy-safe workforce decision report",
                metadata={
                    "report_type": report_type.value,
                    "minimum_group_size": result.privacy.minimum_cohort_size,
                    "suppression_applied": result.privacy.suppression_applied,
                },
            )
        )
        return result

    def get_benchmarks_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        minimum_group_size: int,
    ) -> InstitutionBenchmarkPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_DASHBOARD,
        )
        dashboard = self._build_dashboard(
            organization=organization,
            minimum_group_size=minimum_group_size,
        )
        result = build_institution_benchmarks(
            self._repo.session,
            dashboard=dashboard,
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTION_DASHBOARD_VIEWED,
                target_type="institutional_benchmarks",
                target_id=organization.organization_id,
                purpose="view privacy-safe institutional market benchmarks",
                metadata={
                    "benchmark_count": len(result.benchmarks),
                    "minimum_group_size": result.privacy.minimum_cohort_size,
                    "suppression_applied": result.privacy.suppression_applied,
                },
            )
        )
        return result

    def generate_report_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: InstitutionalReportCreateInput,
    ) -> InstitutionalReportPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_REPORTS,
        )
        student_memberships = self._repo.list_memberships_for_organization(
            organization.organization_id
        )
        dashboard = build_institutional_dashboard(
            self._repo.session,
            organization=organization,
            student_memberships=student_memberships,
            minimum_group_size=payload.minimum_group_size,
        )
        report_id = _new_id("instreport")
        report = build_institutional_report(
            report_id=report_id,
            report_type=payload.report_type,
            generated_by_user_id=user_id,
            dashboard=dashboard,
            date_range=payload.date_range,
        )
        row = InstitutionalReport(
            institutional_report_id=report.report_id,
            organization_id=organization.organization_id,
            report_type=report.report_type.value,
            title=report.title,
            generated_by_user_id=user_id,
            generated_at=report.generated_at,
            payload_json=report.model_dump(mode="json"),
            minimum_group_size=report.minimum_group_size,
            privacy_summary=privacy_summary(report),
            coverage_summary=coverage_summary(report),
            status="generated",
        )
        self._repo.add_report(row)
        self._repo.flush()
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_REPORT_GENERATED,
                target_type="institutional_report",
                target_id=report.report_id,
                purpose="generate aggregate institutional report",
                metadata={
                    "report_type": report.report_type.value,
                    "minimum_group_size": report.minimum_group_size,
                    "cohort_size": report.cohort_size,
                    "suppression_count": len(report.privacy_suppressions),
                },
            )
        )
        return report

    def list_reports_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> InstitutionalReportListPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_REPORTS,
        )
        rows = self._repo.list_reports_for_organization(organization.organization_id)
        summaries = [_report_summary_from_row(row) for row in rows]
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_REPORTS_LISTED,
                target_type="organization",
                target_id=organization.organization_id,
                purpose="list aggregate institutional reports",
                metadata={"report_count": len(summaries)},
            )
        )
        return InstitutionalReportListPayload(reports=summaries)

    def get_report_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        report_id: str,
    ) -> InstitutionalReportPayload:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_REPORTS,
        )
        row = self._repo.get_report(report_id)
        if row is None or row.organization_id != organization.organization_id:
            raise InstitutionalReportNotFound(report_id)
        report = InstitutionalReportPayload.model_validate(row.payload_json)
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_REPORT_VIEWED,
                target_type="institutional_report",
                target_id=report.report_id,
                purpose="view aggregate institutional report",
                metadata={"report_type": report.report_type.value},
            )
        )
        return report

    def compare_regions_for_advisor(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: AdvisorRegionComparisonRequest,
    ) -> AdvisorToolResponse:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.USE_ADVISOR_TOOLS,
        )
        response = build_region_comparison(
            self._repo.session,
            organization_id=organization.organization_id,
            request=payload,
        )
        self._record_advisor_audit(
            organization=organization,
            membership=membership,
            user_id=user_id,
            action=InstitutionalAuditAction.ADVISOR_COMPARE_REGIONS_USED,
            comparison_type="regions",
            input_count=len(payload.regions),
            context_keys=_present_keys(
                role_context=payload.role_context,
                industry_context=payload.industry_context,
                career_stage=payload.career_stage,
            ),
        )
        return response

    def compare_industries_for_advisor(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: AdvisorIndustryComparisonRequest,
    ) -> AdvisorToolResponse:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.USE_ADVISOR_TOOLS,
        )
        response = build_industry_comparison(
            self._repo.session,
            organization_id=organization.organization_id,
            request=payload,
        )
        self._record_advisor_audit(
            organization=organization,
            membership=membership,
            user_id=user_id,
            action=InstitutionalAuditAction.ADVISOR_COMPARE_INDUSTRIES_USED,
            comparison_type="industries",
            input_count=len(payload.industries),
            context_keys=_present_keys(
                region_context=payload.region_context,
                career_stage=payload.career_stage,
            ),
        )
        return response

    def compare_companies_for_advisor(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: AdvisorCompanyComparisonRequest,
    ) -> AdvisorToolResponse:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.USE_ADVISOR_TOOLS,
        )
        response = build_company_comparison(
            self._repo.session,
            organization_id=organization.organization_id,
            request=payload,
        )
        self._record_advisor_audit(
            organization=organization,
            membership=membership,
            user_id=user_id,
            action=InstitutionalAuditAction.ADVISOR_COMPARE_COMPANIES_USED,
            comparison_type="companies",
            input_count=len(payload.companies),
            context_keys=_present_keys(
                region_context=payload.region_context,
                industry_context=payload.industry_context,
                career_stage=payload.career_stage,
            ),
        )
        return response

    def compare_career_stages_for_advisor(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: AdvisorCareerStageComparisonRequest,
    ) -> AdvisorToolResponse:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.USE_ADVISOR_TOOLS,
        )
        response = build_career_stage_comparison(
            self._repo.session,
            organization_id=organization.organization_id,
            request=payload,
        )
        self._record_advisor_audit(
            organization=organization,
            membership=membership,
            user_id=user_id,
            action=InstitutionalAuditAction.ADVISOR_COMPARE_CAREER_STAGES_USED,
            comparison_type="career_stages",
            input_count=len(payload.career_stages),
            context_keys=_present_keys(
                region_context=payload.region_context,
                company_context=payload.company_context,
                industry_context=payload.industry_context,
            ),
        )
        return response

    def application_timing_for_advisor(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: AdvisorApplicationTimingRequest,
    ) -> AdvisorToolResponse:
        organization, membership = self._require_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.USE_ADVISOR_TOOLS,
        )
        response = build_application_timing(
            self._repo.session,
            organization_id=organization.organization_id,
            request=payload,
        )
        self._record_advisor_audit(
            organization=organization,
            membership=membership,
            user_id=user_id,
            action=InstitutionalAuditAction.ADVISOR_APPLICATION_TIMING_USED,
            comparison_type="application_timing",
            input_count=(
                len(payload.target_regions)
                + len(payload.target_industries)
                + len(payload.target_companies)
            ),
            context_keys=_present_keys(
                target_regions=payload.target_regions,
                target_industries=payload.target_industries,
                target_companies=payload.target_companies,
                career_stage=payload.career_stage,
                application_window=payload.application_window,
            ),
        )
        return response

    def add_member_for_user(
        self,
        *,
        organization_id: str,
        actor_user_id: str,
        payload: OrganizationMembershipCreateInput,
    ) -> OrganizationMembership:
        organization, actor_membership = self._require_action(
            organization_id=organization_id,
            user_id=actor_user_id,
            action=InstitutionalAction.MANAGE_MEMBERS,
        )
        if not self._repo.user_exists(payload.user_id):
            raise OrganizationMembershipUserNotFound(payload.user_id)
        existing = self._repo.get_membership(
            organization_id=organization.organization_id,
            user_id=payload.user_id,
        )
        if existing is not None:
            raise OrganizationMembershipAlreadyExists(
                organization.organization_id,
                payload.user_id,
            )
        membership = OrganizationMembership(
            organization_membership_id=_new_id("orgmem"),
            organization_id=organization.organization_id,
            user_id=payload.user_id,
            role=payload.role.value,
            status=payload.status.value,
        )
        self._repo.add_membership(membership)
        self._repo.flush()
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=actor_user_id,
                actor_role=OrganizationRole(actor_membership.role),
                action=InstitutionalAuditAction.ORGANIZATION_MEMBER_ADDED,
                target_type="organization_membership",
                target_id=membership.organization_membership_id,
                purpose="add organization member",
                metadata={
                    "target_user_id": membership.user_id,
                    "role": membership.role,
                    "status": membership.status,
                },
            )
        )
        return membership

    def update_member_for_user(
        self,
        *,
        organization_id: str,
        actor_user_id: str,
        organization_membership_id: str,
        payload: OrganizationMembershipUpdateInput,
    ) -> OrganizationMembership:
        organization, actor_membership = self._require_action(
            organization_id=organization_id,
            user_id=actor_user_id,
            action=InstitutionalAction.MANAGE_MEMBERS,
        )
        membership = self._repo.get_membership_by_id(organization_membership_id)
        if membership is None or membership.organization_id != organization.organization_id:
            raise OrganizationMembershipNotFound(organization_membership_id)

        before = {
            "role": membership.role,
            "status": membership.status,
        }
        if payload.role is not None:
            membership.role = payload.role.value
        if payload.status is not None:
            membership.status = payload.status.value
        self._repo.flush()
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=actor_user_id,
                actor_role=OrganizationRole(actor_membership.role),
                action=InstitutionalAuditAction.ORGANIZATION_MEMBER_UPDATED,
                target_type="organization_membership",
                target_id=membership.organization_membership_id,
                purpose="update organization member",
                metadata={
                    "target_user_id": membership.user_id,
                    "before": before,
                    "after": {
                        "role": membership.role,
                        "status": membership.status,
                    },
                },
            )
        )
        return membership

    def create_data_request_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
        payload: InstitutionalDataRequestCreateInput,
    ) -> InstitutionalDataRequestPayload:
        organization, membership = self._require_active_membership(
            organization_id=organization_id,
            user_id=user_id,
        )
        role = parse_organization_role(membership.role)
        subject_type = payload.subject_type or InstitutionalDataRequestSubjectType.STUDENT
        subject_user_id = payload.subject_user_id
        if payload.request_type in {
            InstitutionalDataRequestType.ORGANIZATION_EXPORT,
            InstitutionalDataRequestType.ORGANIZATION_DELETION,
        }:
            if role != OrganizationRole.ORG_ADMIN:
                raise InstitutionalAccessDenied(organization_id)
            if subject_type != InstitutionalDataRequestSubjectType.ORGANIZATION:
                raise InstitutionalAccessDenied(organization_id)
            if subject_user_id is not None:
                raise InstitutionalAccessDenied(organization_id)
        else:
            if role != OrganizationRole.STUDENT:
                raise InstitutionalAccessDenied(organization_id)
            if subject_type != InstitutionalDataRequestSubjectType.STUDENT:
                raise InstitutionalAccessDenied(organization_id)
            if subject_user_id is not None and subject_user_id != user_id:
                raise InstitutionalAccessDenied(organization_id)
            subject_user_id = user_id

        row = InstitutionalDataRequest(
            institutional_data_request_id=_new_id("instdatareq"),
            organization_id=organization.organization_id,
            requester_user_id=user_id,
            request_type=payload.request_type.value,
            subject_type=subject_type.value,
            subject_user_id=subject_user_id,
            status=InstitutionalDataRequestStatus.PENDING.value,
            reason=payload.reason,
            request_metadata={
                "source": "institutional_api",
                "automation_executed": False,
                "requested_metadata_keys": sorted((payload.metadata or {}).keys()),
            },
        )
        self._repo.add_data_request(row)
        self._repo.flush()
        result = _data_request_payload(row)
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_DATA_REQUEST_CREATED,
                target_type="institutional_data_request",
                target_id=result.data_request_id,
                purpose="create institutional data export/deletion request record",
                metadata={
                    "request_type": result.request_type.value,
                    "subject_type": result.subject_type.value,
                    "status": result.status.value,
                    "automation_executed": False,
                },
            )
        )
        return result

    def list_data_requests_for_user(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> InstitutionalDataRequestListPayload:
        organization, membership = self._require_active_membership(
            organization_id=organization_id,
            user_id=user_id,
        )
        role = parse_organization_role(membership.role)
        if role == OrganizationRole.ORG_ADMIN:
            rows = [
                row
                for row in self._repo.list_data_requests_for_organization(
                    organization.organization_id
                )
                if row.subject_type == InstitutionalDataRequestSubjectType.ORGANIZATION.value
            ]
        elif role == OrganizationRole.STUDENT:
            rows = self._repo.list_data_requests_for_user(
                organization_id=organization.organization_id,
                user_id=user_id,
            )
        else:
            raise InstitutionalAccessDenied(organization_id)
        result = InstitutionalDataRequestListPayload(
            data_requests=[_data_request_payload(row) for row in rows]
        )
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=InstitutionalAuditAction.INSTITUTIONAL_DATA_REQUESTS_LISTED,
                target_type="organization",
                target_id=organization.organization_id,
                purpose="list institutional data request records",
                metadata={"request_count": len(result.data_requests)},
            )
        )
        return result

    def record_audit_event(
        self,
        event: InstitutionalAuditLogInput,
    ) -> InstitutionalAuditLog:
        row = InstitutionalAuditLog(
            institutional_audit_log_id=_new_id("instaudit"),
            organization_id=event.organization_id,
            actor_user_id=event.actor_user_id,
            actor_role=event.actor_role.value if event.actor_role is not None else None,
            action=event.action.value,
            target_type=event.target_type,
            target_id=event.target_id,
            purpose=event.purpose,
            event_metadata=deepcopy(event.metadata),
            created_at=_utc_now(),
        )
        self._repo.add_audit_log(row)
        self._repo.flush()
        return row

    def _record_advisor_audit(
        self,
        *,
        organization: Organization,
        membership: OrganizationMembership,
        user_id: str,
        action: InstitutionalAuditAction,
        comparison_type: str,
        input_count: int,
        context_keys: list[str],
    ) -> None:
        self.record_audit_event(
            InstitutionalAuditLogInput(
                organization_id=organization.organization_id,
                actor_user_id=user_id,
                actor_role=OrganizationRole(membership.role),
                action=action,
                target_type="advisor_tool",
                target_id=comparison_type,
                purpose="use institutional advisor guidance tool",
                metadata={
                    "comparison_type": comparison_type,
                    "input_count": input_count,
                    "context_keys": context_keys,
                    "student_specific": False,
                },
            )
        )

    def _require_action(
        self,
        *,
        organization_id: str,
        user_id: str,
        action: InstitutionalAction,
    ) -> tuple[Organization, OrganizationMembership]:
        organization = self._repo.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        if organization.status != "active":
            raise InstitutionalAccessDenied(organization_id)
        if not can_perform_institutional_action(
            self._repo,
            user_id=user_id,
            organization_id=organization_id,
            action=action,
        ):
            raise InstitutionalAccessDenied(organization_id)
        membership = active_membership_for_user(
            self._repo,
            user_id=user_id,
            organization_id=organization_id,
        )
        if membership is None:
            raise InstitutionalAccessDenied(organization_id)
        return organization, membership

    def _build_dashboard(
        self,
        *,
        organization: Organization,
        minimum_group_size: int,
    ) -> InstitutionalDashboardPayload:
        student_memberships = self._repo.list_memberships_for_organization(
            organization.organization_id
        )
        return build_institutional_dashboard(
            self._repo.session,
            organization=organization,
            student_memberships=student_memberships,
            minimum_group_size=minimum_group_size,
        )

    def _require_active_membership(
        self,
        *,
        organization_id: str,
        user_id: str,
    ) -> tuple[Organization, OrganizationMembership]:
        organization = self._repo.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        if organization.status != "active":
            raise InstitutionalAccessDenied(organization_id)
        membership = active_membership_for_user(
            self._repo,
            user_id=user_id,
            organization_id=organization_id,
        )
        if membership is None:
            raise InstitutionalAccessDenied(organization_id)
        return organization, membership


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _present_keys(**values: Any) -> list[str]:
    keys: list[str] = []
    for key, value in values.items():
        if isinstance(value, list) and value:
            keys.append(key)
        elif value not in (None, "", [], {}):
            keys.append(key)
    return keys


def _report_summary_from_row(row: InstitutionalReport) -> InstitutionalReportSummary:
    payload = InstitutionalReportPayload.model_validate(row.payload_json)
    return report_summary_from_payload(payload, status=row.status)


def _data_request_payload(row: InstitutionalDataRequest) -> InstitutionalDataRequestPayload:
    metadata = deepcopy(row.request_metadata)
    return InstitutionalDataRequestPayload(
        data_request_id=row.institutional_data_request_id,
        organization_id=row.organization_id,
        requester_user_id=row.requester_user_id,
        request_type=InstitutionalDataRequestType(row.request_type),
        subject_type=InstitutionalDataRequestSubjectType(row.subject_type),
        subject_user_id=row.subject_user_id,
        status=InstitutionalDataRequestStatus(row.status),
        reason=row.reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolved_at=row.resolved_at,
        metadata=metadata if isinstance(metadata, dict) else None,
        execution_note=(
            "Request record created only; destructive deletion and full export "
            "package generation are not executed in Batch 16E."
        ),
    )
