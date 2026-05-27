"""Institutional organization API shell."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.institutions.advisor import (
    AdvisorApplicationTimingRequest,
    AdvisorCareerStageComparisonRequest,
    AdvisorCompanyComparisonRequest,
    AdvisorIndustryComparisonRequest,
    AdvisorRegionComparisonRequest,
)
from backend.institutions.dashboard import DEFAULT_MINIMUM_GROUP_SIZE, MAXIMUM_GROUP_SIZE
from backend.institutions.data_requests import InstitutionalDataRequestCreateInput
from backend.institutions.exceptions import (
    InstitutionalAccessDenied,
    InstitutionalReportNotFound,
    OrganizationMembershipAlreadyExists,
    OrganizationMembershipNotFound,
    OrganizationMembershipUserNotFound,
    OrganizationNotFound,
)
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.reports import InstitutionalReportCreateInput
from backend.institutions.repository import InstitutionRepository
from backend.institutions.service import (
    InstitutionService,
    OrganizationMembershipCreateInput,
    OrganizationMembershipUpdateInput,
)

router = APIRouter(prefix="/api/institutions", tags=["institutions"])

FORBIDDEN = "FORBIDDEN"


def _service(session: Session) -> InstitutionService:
    return InstitutionService(InstitutionRepository(session))


@router.get("/organizations/current")
def list_current_organizations(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    rows = _service(session).list_current_organizations(
        user_id=current.user.user_id,
    )
    return lightweight_success_envelope(
        data={
            "organizations": [
                {
                    "organization": _organization_data(organization),
                    "membership": _membership_data(membership),
                }
                for organization, membership in rows
            ]
        }
    )


@router.get("/organizations/{organization_id}", response_model=None)
def get_organization(
    organization_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        organization, membership = _service(session).get_organization_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional organization access denied.")
    return lightweight_success_envelope(
        data={
            "organization": _organization_data(organization),
            "membership": _membership_data(membership),
        }
    )


@router.get("/organizations/{organization_id}/members", response_model=None)
def list_organization_members(
    organization_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        rows = _service(session).list_members_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional member access denied.")
    return lightweight_success_envelope(
        data={"members": [_membership_data(row) for row in rows]}
    )


@router.get("/organizations/{organization_id}/dashboard", response_model=None)
def get_organization_dashboard(
    organization_id: str,
    minimum_group_size: int = Query(
        default=DEFAULT_MINIMUM_GROUP_SIZE,
        ge=DEFAULT_MINIMUM_GROUP_SIZE,
        le=MAXIMUM_GROUP_SIZE,
    ),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        dashboard = _service(session).get_dashboard_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
            minimum_group_size=minimum_group_size,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional dashboard access denied.")
    return lightweight_success_envelope(data=dashboard.model_dump(mode="json"))


@router.post(
    "/organizations/{organization_id}/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def generate_institutional_report(
    organization_id: str,
    payload: InstitutionalReportCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        report = _service(session).generate_report_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional report access denied.")
    return lightweight_success_envelope(data={"report": report.model_dump(mode="json")})


@router.get("/organizations/{organization_id}/reports", response_model=None)
def list_institutional_reports(
    organization_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        reports = _service(session).list_reports_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional report access denied.")
    return lightweight_success_envelope(data=reports.model_dump(mode="json"))


@router.get("/organizations/{organization_id}/reports/{report_id}", response_model=None)
def get_institutional_report(
    organization_id: str,
    report_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        report = _service(session).get_report_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
            report_id=report_id,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalReportNotFound:
        return _not_found(f"Institutional report not found: {report_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional report access denied.")
    return lightweight_success_envelope(data={"report": report.model_dump(mode="json")})


@router.post(
    "/organizations/{organization_id}/data-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_institutional_data_request(
    organization_id: str,
    payload: InstitutionalDataRequestCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        data_request = _service(session).create_data_request_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional data request access denied.")
    return lightweight_success_envelope(
        data={"data_request": data_request.model_dump(mode="json")}
    )


@router.get("/organizations/{organization_id}/data-requests", response_model=None)
def list_institutional_data_requests(
    organization_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        data_requests = _service(session).list_data_requests_for_user(
            organization_id=organization_id,
            user_id=current.user.user_id,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional data request access denied.")
    return lightweight_success_envelope(data=data_requests.model_dump(mode="json"))


@router.post("/organizations/{organization_id}/advisor/compare-regions", response_model=None)
def advisor_compare_regions(
    organization_id: str,
    payload: AdvisorRegionComparisonRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        result = _service(session).compare_regions_for_advisor(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional advisor tool access denied.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/organizations/{organization_id}/advisor/compare-industries", response_model=None)
def advisor_compare_industries(
    organization_id: str,
    payload: AdvisorIndustryComparisonRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        result = _service(session).compare_industries_for_advisor(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional advisor tool access denied.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/organizations/{organization_id}/advisor/compare-companies", response_model=None)
def advisor_compare_companies(
    organization_id: str,
    payload: AdvisorCompanyComparisonRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        result = _service(session).compare_companies_for_advisor(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional advisor tool access denied.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post(
    "/organizations/{organization_id}/advisor/compare-career-stages",
    response_model=None,
)
def advisor_compare_career_stages(
    organization_id: str,
    payload: AdvisorCareerStageComparisonRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        result = _service(session).compare_career_stages_for_advisor(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional advisor tool access denied.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/organizations/{organization_id}/advisor/application-timing", response_model=None)
def advisor_application_timing(
    organization_id: str,
    payload: AdvisorApplicationTimingRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        result = _service(session).application_timing_for_advisor(
            organization_id=organization_id,
            user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional advisor tool access denied.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post(
    "/organizations/{organization_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def add_organization_member(
    organization_id: str,
    payload: OrganizationMembershipCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        row = _service(session).add_member_for_user(
            organization_id=organization_id,
            actor_user_id=current.user.user_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional member management access denied.")
    except OrganizationMembershipUserNotFound as exc:
        return _validation_error(f"User not found: {exc.user_id!r}")
    except OrganizationMembershipAlreadyExists as exc:
        return _validation_error(
            "Organization membership already exists for "
            f"{exc.user_id!r} in {exc.organization_id!r}."
        )
    return lightweight_success_envelope(data={"membership": _membership_data(row)})


@router.patch(
    "/organizations/{organization_id}/members/{organization_membership_id}",
    response_model=None,
)
def update_organization_member(
    organization_id: str,
    organization_membership_id: str,
    payload: OrganizationMembershipUpdateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    try:
        row = _service(session).update_member_for_user(
            organization_id=organization_id,
            actor_user_id=current.user.user_id,
            organization_membership_id=organization_membership_id,
            payload=payload,
        )
    except OrganizationNotFound:
        return _not_found(f"Organization not found: {organization_id!r}")
    except OrganizationMembershipNotFound:
        return _not_found(f"Organization membership not found: {organization_membership_id!r}")
    except InstitutionalAccessDenied:
        return _forbidden("Institutional member management access denied.")
    return lightweight_success_envelope(data={"membership": _membership_data(row)})


def _organization_data(row: Organization) -> dict[str, Any]:
    return {
        "organization_id": row.organization_id,
        "name": row.name,
        "organization_type": row.organization_type,
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _membership_data(row: OrganizationMembership) -> dict[str, Any]:
    return {
        "organization_membership_id": row.organization_membership_id,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "role": row.role,
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(code=NOT_FOUND, message=message),
    )


def _forbidden(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_envelope(code=FORBIDDEN, message=message, state="blocked"),
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_envelope(code=VALIDATION_ERROR, message=message),
    )


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
