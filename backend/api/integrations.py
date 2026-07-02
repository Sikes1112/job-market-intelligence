"""Layer 17 ecosystem integration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    CurrentAdmin,
    CurrentUser,
    get_current_user,
    get_output_service,
    get_session,
    require_admin_mutation_access,
    require_admin_read_access,
)
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.institutions.exceptions import InstitutionalAccessDenied, OrganizationNotFound
from backend.institutions.repository import InstitutionRepository
from backend.integrations.repository import IntegrationRepository
from backend.integrations.service import (
    ApiClientCreateRequest,
    ApiClientNotFound,
    ApiClientUpdateRequest,
    ApiKeyCreateRequest,
    ApiKeyNotFound,
    CareerPlatformBoundaryError,
    CareerPlatformExportRequest,
    CareerPlatformReferenceCreateRequest,
    ExportRequest,
    IntegrationAccessDenied,
    IntegrationDownloadUnavailable,
    IntegrationExportNotFound,
    IntegrationObjectNotFound,
    IntegrationReminderNotFound,
    IntegrationService,
    PartnerImportActionRequest,
    PartnerImportCreateRequest,
    PartnerImportNotFound,
    PartnerImportValidationError,
    ReminderRequest,
)
from backend.outputs.service import OutputAssemblyService

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

FORBIDDEN = "FORBIDDEN"


def _service(
    session: Session,
    output_service: OutputAssemblyService,
) -> IntegrationService:
    return IntegrationService(
        IntegrationRepository(session),
        institution_repo=InstitutionRepository(session),
        output_service=output_service,
    )


@router.post("/exports", status_code=status.HTTP_201_CREATED, response_model=None)
def create_export(
    payload: ExportRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        export = _service(session, output_service).create_export(
            user_id=current.user.user_id,
            request=payload,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Export access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except IntegrationObjectNotFound as exc:
        return _not_found(f"Export product object not found: {exc!s}")
    return lightweight_success_envelope(data={"export": export.model_dump(mode="json")})


@router.get("/exports/{export_id}", response_model=None)
def get_export(
    export_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        export = _service(session, output_service).get_export(
            user_id=current.user.user_id,
            export_id=export_id,
        )
    except IntegrationExportNotFound:
        return _not_found("Export not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Export access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data={"export": export.model_dump(mode="json")})


@router.get("/exports/{export_id}/download", response_model=None)
def download_export(
    export_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | Response:
    try:
        filename, content_type, body = _service(session, output_service).export_download(
            user_id=current.user.user_id,
            export_id=export_id,
        )
    except IntegrationExportNotFound:
        return _not_found("Export not found.")
    except IntegrationDownloadUnavailable:
        return _validation_error("This integration export has no downloadable file.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Export access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reminders", status_code=status.HTTP_201_CREATED, response_model=None)
def create_reminder(
    payload: ReminderRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        reminder = _service(session, output_service).create_reminder(
            user_id=current.user.user_id,
            request=payload,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Reminder access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except IntegrationObjectNotFound as exc:
        return _not_found(f"Reminder product object not found: {exc!s}")
    return lightweight_success_envelope(
        data={"reminder": reminder.model_dump(mode="json")}
    )


@router.get("/reminders/{reminder_id}", response_model=None)
def get_reminder(
    reminder_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        reminder = _service(session, output_service).get_reminder(
            user_id=current.user.user_id,
            reminder_id=reminder_id,
        )
    except IntegrationReminderNotFound:
        return _not_found("Reminder not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Reminder access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(
        data={"reminder": reminder.model_dump(mode="json")}
    )


@router.get("/reminders/{reminder_id}/ics", response_model=None)
def download_reminder_ics(
    reminder_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | Response:
    try:
        filename, content_type, body = _service(session, output_service).reminder_ics(
            user_id=current.user.user_id,
            reminder_id=reminder_id,
        )
    except IntegrationReminderNotFound:
        return _not_found("Reminder not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Reminder access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/partner-imports", status_code=status.HTTP_201_CREATED, response_model=None)
def create_partner_import(
    payload: PartnerImportCreateRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).create_partner_import(
            user_id=current.user.user_id,
            request=payload,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except PartnerImportValidationError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.get("/partner-imports", response_model=None)
def list_partner_imports(
    organization_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).list_partner_imports(
            user_id=current.user.user_id,
            organization_id=organization_id,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data=imported.model_dump(mode="json"))


@router.get("/partner-imports/{import_batch_id}", response_model=None)
def get_partner_import(
    import_batch_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).get_partner_import(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.post("/partner-imports/{import_batch_id}/validate", response_model=None)
def validate_partner_import(
    import_batch_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).validate_partner_import(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except PartnerImportValidationError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.post("/partner-imports/{import_batch_id}/accept", response_model=None)
def accept_partner_import(
    import_batch_id: str,
    payload: PartnerImportActionRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).accept_partner_import(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
            reason=payload.reason if payload else None,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except PartnerImportValidationError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.post("/partner-imports/{import_batch_id}/reject", response_model=None)
def reject_partner_import(
    import_batch_id: str,
    payload: PartnerImportActionRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).reject_partner_import(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
            reason=payload.reason if payload else None,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.post("/partner-imports/{import_batch_id}/archive", response_model=None)
def archive_partner_import(
    import_batch_id: str,
    payload: PartnerImportActionRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        imported = _service(session, output_service).archive_partner_import(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
            reason=payload.reason if payload else None,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except PartnerImportValidationError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(
        data={"partner_import": imported.model_dump(mode="json")}
    )


@router.get("/partner-imports/{import_batch_id}/receipt", response_model=None)
def get_partner_import_receipt(
    import_batch_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        receipt = _service(session, output_service).partner_import_receipt(
            user_id=current.user.user_id,
            import_batch_id=import_batch_id,
        )
    except PartnerImportNotFound:
        return _not_found("Partner import not found.")
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Partner import access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data={"receipt": receipt.model_dump(mode="json")})


@router.post("/api-clients", status_code=status.HTTP_201_CREATED, response_model=None)
def create_api_client(
    payload: ApiClientCreateRequest,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).create_api_client(
            user_id=admin.current.user.user_id,
            request=payload,
        )
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    except IntegrationAccessDenied as exc:
        return _forbidden(str(exc))
    return lightweight_success_envelope(data={"api_client": result.model_dump(mode="json")})


@router.get("/api-clients", response_model=None)
def list_api_clients(
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> dict:
    result = _service(session, output_service).list_api_clients()
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.patch("/api-clients/{api_client_id}", response_model=None)
def update_api_client(
    api_client_id: str,
    payload: ApiClientUpdateRequest,
    _admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).update_api_client(
            api_client_id=api_client_id,
            request=payload,
        )
    except ApiClientNotFound:
        return _not_found("API client not found.")
    except IntegrationAccessDenied as exc:
        return _forbidden(str(exc))
    return lightweight_success_envelope(data={"api_client": result.model_dump(mode="json")})


@router.post(
    "/api-clients/{api_client_id}/keys",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_api_key(
    api_client_id: str,
    _payload: ApiKeyCreateRequest | None = None,
    admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).create_api_key(
            user_id=admin.current.user.user_id,
            api_client_id=api_client_id,
        )
    except ApiClientNotFound:
        return _not_found("API client not found.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/api-keys/{api_key_id}/revoke", response_model=None)
def revoke_api_key(
    api_key_id: str,
    _admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).revoke_api_key(api_key_id=api_key_id)
    except ApiKeyNotFound:
        return _not_found("API key not found.")
    return lightweight_success_envelope(data={"api_key": result.model_dump(mode="json")})


@router.get("/api-clients/{api_client_id}/usage", response_model=None)
def list_api_usage(
    api_client_id: str,
    _admin: CurrentAdmin = Depends(require_admin_read_access),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).list_api_usage(
            api_client_id=api_client_id,
        )
    except ApiClientNotFound:
        return _not_found("API client not found.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.get("/career-platforms", response_model=None)
def get_career_platform_registry(
    _current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> dict:
    result = _service(session, output_service).career_platform_registry()
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.get("/career-platforms/companies/{company_id}/links", response_model=None)
def get_career_platform_company_links(
    company_id: str,
    _current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).career_platform_links_for_company(
            company_id=company_id,
        )
    except IntegrationObjectNotFound:
        return _not_found("Company not found.")
    return lightweight_success_envelope(data=result)


@router.post(
    "/career-platform-references",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_career_platform_reference(
    payload: CareerPlatformReferenceCreateRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).create_career_platform_reference(
            user_id=current.user.user_id,
            request=payload,
        )
    except CareerPlatformBoundaryError as exc:
        return _validation_error(str(exc))
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Career platform reference access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.get("/career-platform-references", response_model=None)
def list_career_platform_references(
    organization_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).list_career_platform_references(
            user_id=current.user.user_id,
            organization_id=organization_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Career platform reference access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post(
    "/career-platform-exports",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_career_platform_export(
    payload: CareerPlatformExportRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    try:
        result = _service(session, output_service).create_career_platform_export(
            user_id=current.user.user_id,
            request=payload,
        )
    except (IntegrationAccessDenied, InstitutionalAccessDenied):
        return _forbidden("Career platform export access denied.")
    except OrganizationNotFound:
        return _not_found("Organization not found.")
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


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
