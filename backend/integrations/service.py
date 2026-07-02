"""Layer 17 export and reminder service."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import secrets
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple
from urllib.parse import quote_plus, urlparse
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.companies.models import Company
from backend.geography.models import Region
from backend.institutions.dashboard import build_institutional_dashboard
from backend.institutions.exceptions import (
    InstitutionalAccessDenied,
    InstitutionalReportNotFound,
    OrganizationNotFound,
)
from backend.institutions.models import Organization
from backend.institutions.permissions import (
    InstitutionalAction,
    active_membership_for_user,
    can_perform_institutional_action,
)
from backend.institutions.reports import InstitutionalReportPayload
from backend.institutions.repository import InstitutionRepository
from backend.integrations.models import (
    ApiAccessAuditEvent,
    ApiClient,
    ApiKey,
    ApiUsageRecord,
    CareerPlatformExportRecord,
    CareerPlatformReferenceRecord,
    IntegrationExportRecord,
    IntegrationReminderRecord,
    PartnerImportBatch,
    PartnerImportRecord,
)
from backend.integrations.repository import IntegrationRepository
from backend.integrations.types import (
    ApiAccessPolicy,
    ApiClientStatus,
    ApiRateLimitDecision,
    ApiResponseEnvelope,
    ApiResponseMeta,
    ApiScope,
    CareerPlatform,
    CareerPlatformExport,
    CareerPlatformReference,
    CareerPlatformRiskPosture,
    ExportFormat,
    ExternalCareerLink,
    IntegrationCapability,
    IntegrationDestination,
    IntegrationPermissionDecision,
    IntegrationProvenance,
    IntegrationReceipt,
    IntegrationRiskPosture,
    PartnerContributedEvidence,
    PartnerDataConfidence,
    PartnerImportDecision,
    PartnerImportFormat,
    PartnerImportGovernanceWarning,
    PartnerImportReceipt,
    PartnerImportSourceType,
    PartnerImportStatus,
    PartnerImportValidationResult,
    ProductObjectType,
    ReminderType,
    SafeApiKeyDisplay,
    capability_for_destination,
    destination_for_format,
    json_safe,
    risk_posture_for_destination,
)
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingCompanyForOutput,
    MissingRegionForOutput,
)
from backend.outputs.service import OutputAssemblyService


class IntegrationAccessDenied(Exception):
    pass


class IntegrationExportNotFound(Exception):
    pass


class IntegrationReminderNotFound(Exception):
    pass


class IntegrationDownloadUnavailable(Exception):
    pass


class IntegrationObjectNotFound(Exception):
    pass


class PartnerImportNotFound(Exception):
    pass


class PartnerImportValidationError(Exception):
    pass


class ApiClientNotFound(Exception):
    pass


class ApiKeyNotFound(Exception):
    pass


class ApiAuthenticationError(Exception):
    pass


class ApiScopeDenied(Exception):
    pass


class ApiRateLimitExceeded(Exception):
    def __init__(self, decision: ApiRateLimitDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class CareerPlatformBoundaryError(Exception):
    pass


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_object_type: ProductObjectType
    product_object_id: str = Field(min_length=1, max_length=255)
    export_format: ExportFormat
    organization_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("product_object_id")
    @classmethod
    def _object_id_clean(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: str
    product_object_type: ProductObjectType
    product_object_id: str
    export_format: ExportFormat
    destination: IntegrationDestination
    capability: IntegrationCapability
    risk_posture: IntegrationRiskPosture
    status: str
    filename: str | None = None
    content_type: str | None = None
    payload: dict[str, Any]
    receipt: IntegrationReceipt
    created_at: datetime
    updated_at: datetime


class ReminderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reminder_type: ReminderType
    product_object_type: ProductObjectType
    product_object_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    due_at: datetime
    organization_id: str | None = Field(default=None, min_length=1, max_length=64)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2048)
    duration_minutes: int = Field(default=30, ge=5, le=24 * 60)

    @field_validator("product_object_id", "title", "timezone")
    @classmethod
    def _strings_clean(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @model_validator(mode="after")
    def _no_ats_status_semantics(self) -> ReminderRequest:
        combined = f"{self.title} {self.description or ''}".casefold()
        forbidden_statuses = {"applied", "interviewing", "offer", "rejected"}
        if any(f"status:{status}" in combined for status in forbidden_statuses):
            raise ValueError("Reminder text must not create application status state")
        return self


class ReminderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reminder_id: str
    reminder_type: ReminderType
    product_object_type: ProductObjectType
    product_object_id: str
    destination: IntegrationDestination
    capability: IntegrationCapability
    risk_posture: IntegrationRiskPosture
    status: str
    title: str
    due_at: datetime
    timezone: str
    receipt: IntegrationReceipt
    ics_filename: str
    created_at: datetime
    updated_at: datetime


class PartnerImportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str = Field(min_length=1, max_length=64)
    source_type: PartnerImportSourceType
    import_format: PartnerImportFormat
    source_attribution: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1, max_length=2_000_000)
    original_filename: str | None = Field(default=None, max_length=255)

    @field_validator("organization_id", "content")
    @classmethod
    def _strings_clean(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("source_attribution")
    @classmethod
    def _source_attribution_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("original_filename")
    @classmethod
    def _filename_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PartnerImportRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_record_id: str
    import_batch_id: str
    organization_id: str
    record_index: int
    source_type: PartnerImportSourceType
    record_status: str
    decision: PartnerImportDecision
    source_attribution: str
    employer_name: str | None
    region_label: str | None
    confidence: PartnerDataConfidence
    freshness_status: str
    partner_payload: dict[str, Any]
    evidence: PartnerContributedEvidence
    validation_warnings: list[PartnerImportGovernanceWarning]
    created_at: datetime
    updated_at: datetime


class PartnerImportBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_batch_id: str
    organization_id: str
    uploaded_by_user_id: str
    source_type: PartnerImportSourceType
    status: PartnerImportStatus
    import_format: PartnerImportFormat
    source_attribution: str
    original_filename: str | None
    record_count: int
    accepted_record_count: int
    quarantined_record_count: int
    rejected_record_count: int
    validation_result: PartnerImportValidationResult
    receipt: PartnerImportReceipt
    governance_warnings: list[PartnerImportGovernanceWarning]
    records: list[PartnerImportRecordPayload] = Field(default_factory=list)
    preview_records: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PartnerImportListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    imports: list[PartnerImportBatchPayload]


class PartnerImportActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str | None = Field(default=None, max_length=1024)


class ApiClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1, max_length=255)
    scopes: list[ApiScope] = Field(default_factory=list)
    organization_id: str | None = Field(default=None, min_length=1, max_length=64)
    rate_limit_count: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    allowed_origins: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("display_name")
    @classmethod
    def _name_clean(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @model_validator(mode="after")
    def _policy_valid(self) -> ApiClientCreateRequest:
        ApiAccessPolicy(
            scopes=self.scopes,
            organization_id=self.organization_id,
            rate_limit_count=self.rate_limit_count,
            rate_limit_window_seconds=self.rate_limit_window_seconds,
            allowed_origins=self.allowed_origins,
        )
        return self


class ApiClientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scopes: list[ApiScope] | None = None
    rate_limit_count: int | None = Field(default=None, ge=1, le=10000)
    rate_limit_window_seconds: int | None = Field(default=None, ge=60, le=86400)
    status: ApiClientStatus | None = None


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = Field(default=None, max_length=128)


class ApiUsagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usage_record_id: str
    api_client_id: str | None
    api_key_id: str | None
    route: str
    method: str
    scope: str | None
    decision: str
    status_code: int
    rate_limit_limit: int | None
    rate_limit_remaining: int | None
    rate_limit_reset_at: datetime | None
    occurred_at: datetime


class ApiClientPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_client_id: str
    display_name: str
    created_by_user_id: str
    organization_id: str | None
    status: ApiClientStatus
    policy: ApiAccessPolicy
    keys: list[SafeApiKeyDisplay] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ApiClientCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_client: ApiClientPayload


class ApiKeyCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: SafeApiKeyDisplay


class ApiClientListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_clients: list[ApiClientPayload]


class ApiUsageListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usage: list[ApiUsagePayload]


class ExternalApiContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_client_id: str
    api_key_id: str
    organization_id: str | None
    scopes: list[ApiScope]
    rate_limit: ApiRateLimitDecision


class CareerPlatformReferenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: CareerPlatform
    subject_type: str = Field(min_length=1, max_length=64)
    subject_id: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    label: str | None = Field(default=None, max_length=255)
    organization_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("url")
    @classmethod
    def _public_http_url(cls, value: str) -> str:
        stripped = value.strip()
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Career platform references must be public HTTP(S) URLs")
        if parsed.username or parsed.password:
            raise ValueError("Career platform references must not embed credentials")
        return stripped


class CareerPlatformExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: CareerPlatform
    company_ids: list[str] = Field(default_factory=list, max_length=200)
    employer_names: list[str] = Field(default_factory=list, max_length=200)
    organization_id: str | None = Field(default=None, min_length=1, max_length=64)


class CareerPlatformRegistryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platforms: list[dict[str, Any]]


class CareerPlatformReferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: CareerPlatformReference


class CareerPlatformReferenceListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    references: list[CareerPlatformReference]


class CareerPlatformExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    export: CareerPlatformExport


class _PreparedObject(NamedTuple):
    product_object_type: ProductObjectType
    product_object_id: str
    label: str
    data: dict[str, Any]
    freshness_status: str
    confidence_label: str
    source_object_version: str | None
    limitations: list[str]
    governance_warnings: list[str]
    evidence_basis: list[str]


@dataclass(frozen=True)
class _ValidatedPartnerRecord:
    record_index: int
    raw: dict[str, Any]
    sanitized: dict[str, Any]
    warnings: list[PartnerImportGovernanceWarning]
    decision: PartnerImportDecision
    source_attribution: str
    employer_name: str | None
    normalized_employer_name: str | None
    region_label: str | None
    normalized_region_id: str | None
    confidence: PartnerDataConfidence
    freshness_status: str


FILE_EXPORT_FORMATS = {ExportFormat.CSV, ExportFormat.PDF}
PREPARED_EXPORT_FORMATS = {
    ExportFormat.PREPARED_GOOGLE_SHEETS,
    ExportFormat.PREPARED_NOTION,
    ExportFormat.PREPARED_AIRTABLE,
}
INSTITUTIONAL_PRODUCT_TYPES = {
    ProductObjectType.INSTITUTIONAL_DASHBOARD,
    ProductObjectType.INSTITUTIONAL_REPORT,
}
INTERNAL_ONLY_EXPORT_KEYS = {
    "raw_total_score",
    "score_ruleset_version",
    "source_version_bundle",
    "source_versions",
    "source_version_refs",
    "source_bundle_ref",
    "source_refs",
    "source_ref_id",
    "source_observation_id",
    "fact_source_link_id",
    "recommendation_inputs_hash",
    "admin_role",
}
INTERNAL_ONLY_KEY_PARTS = (
    "internal",
    "oauth",
    "provider_token",
    "access_token",
    "refresh_token",
)
REQUIRED_PARTNER_IMPORT_FIELDS: dict[PartnerImportSourceType, frozenset[str]] = {
    PartnerImportSourceType.LOCAL_EMPLOYER_LIST: frozenset(
        {"employer_name", "region"}
    ),
    PartnerImportSourceType.INTERNSHIP_PARTNER_LIST: frozenset(
        {"employer_name", "internship_program_name", "region"}
    ),
    PartnerImportSourceType.REGIONAL_WORKFORCE_DATA: frozenset(
        {"region", "metric_name", "metric_value", "observed_at"}
    ),
    PartnerImportSourceType.AGGREGATED_CAREER_CENTER_OUTCOME_DATA: frozenset(
        {"program_or_cohort", "graduation_year", "outcome_category", "aggregate_count"}
    ),
}
ALLOWED_PARTNER_IMPORT_FIELDS: dict[PartnerImportSourceType, frozenset[str]] = {
    PartnerImportSourceType.LOCAL_EMPLOYER_LIST: frozenset(
        {
            "employer_name",
            "company_id",
            "region",
            "sector",
            "notes",
            "source_attribution",
            "source_url",
            "observed_at",
            "as_of_date",
        }
    ),
    PartnerImportSourceType.INTERNSHIP_PARTNER_LIST: frozenset(
        {
            "employer_name",
            "company_id",
            "internship_program_name",
            "region",
            "role_family",
            "program_url",
            "notes",
            "source_attribution",
            "observed_at",
            "as_of_date",
        }
    ),
    PartnerImportSourceType.REGIONAL_WORKFORCE_DATA: frozenset(
        {
            "region",
            "metric_name",
            "metric_value",
            "metric_unit",
            "industry",
            "observed_at",
            "as_of_date",
            "source_attribution",
            "source_url",
            "notes",
        }
    ),
    PartnerImportSourceType.AGGREGATED_CAREER_CENTER_OUTCOME_DATA: frozenset(
        {
            "program_or_cohort",
            "graduation_year",
            "outcome_category",
            "aggregate_count",
            "aggregate_percentage",
            "median_salary",
            "employer_sector",
            "region",
            "source_attribution",
            "observed_at",
            "as_of_date",
            "notes",
        }
    ),
}
PII_FIELD_PARTS = (
    "student_name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "student_id",
    "person_id",
    "individual_id",
    "ssn",
    "social_security",
    "date_of_birth",
    "birthdate",
)
INDIVIDUAL_OUTCOME_FIELD_PARTS = (
    "individual_salary",
    "salary_amount",
    "starting_salary",
    "application_status",
    "application_outcome",
    "student_outcome",
    "placement_status",
)
SENSITIVE_DEMOGRAPHIC_FIELD_PARTS = (
    "race",
    "ethnicity",
    "religion",
    "disability",
    "citizenship",
    "immigration",
    "gender",
    "sexuality",
    "sexual_orientation",
    "veteran_status",
    "protected_class",
)
ATS_STATUS_VALUES = {"applied", "interviewing", "offer", "rejected"}
AMBIGUOUS_EMPLOYER_NAMES = {
    "alpha",
    "acme",
    "startup",
    "unknown",
    "local employer",
    "company",
    "tbd",
}
PARTNER_IMPORT_LIMITATIONS = [
    "Partner imports are contributed evidence, not canonical product truth.",
    "Accepted records do not overwrite company identity, region intelligence, or scoring.",
    "Student-level PII, individual outcomes, and sensitive demographic fields are "
    "quarantined or rejected.",
]
SAFE_API_SCOPES = {
    ApiScope.REGION_READ,
    ApiScope.COMPANY_GEOGRAPHY_READ,
    ApiScope.MARKET_SIGNAL_READ,
    ApiScope.INSTITUTION_DASHBOARD_READ,
    ApiScope.EXPORTS_CREATE,
    ApiScope.IMPORTS_CREATE,
}
CAREER_PLATFORM_REGISTRY: dict[CareerPlatform, dict[str, Any]] = {
    CareerPlatform.LINKEDIN: {
        "display_name": "LinkedIn",
        "risk_posture": CareerPlatformRiskPosture.DEEP_LINK_ONLY,
        "allowed_capabilities": ["manual_company_search", "manual_export"],
        "blocked_capabilities": [
            "scraping",
            "automation",
            "recruiter_outreach",
            "application_submission",
        ],
        "notes": ["Search links are user-opened deep links only."],
    },
    CareerPlatform.HANDSHAKE: {
        "display_name": "Handshake",
        "risk_posture": CareerPlatformRiskPosture.EXPORT_ONLY,
        "allowed_capabilities": ["manual_employer_lookup", "manual_export"],
        "blocked_capabilities": ["automation", "login_crawling", "application_submission"],
        "notes": ["Employer lookup is manual; no Handshake automation is performed."],
    },
    CareerPlatform.UNIVERSITY_JOB_BOARD: {
        "display_name": "University job board",
        "risk_posture": CareerPlatformRiskPosture.REQUIRES_REVIEW,
        "allowed_capabilities": ["manual_public_url_reference"],
        "blocked_capabilities": ["login_crawling", "scraping", "application_submission"],
        "notes": ["Logged-in boards remain blocked unless an official API-safe path exists."],
    },
    CareerPlatform.COMPANY_CAREER_PAGE: {
        "display_name": "Company career page",
        "risk_posture": CareerPlatformRiskPosture.SAFE_MANUAL,
        "allowed_capabilities": ["manual_public_url_reference", "open_public_link"],
        "blocked_capabilities": ["application_submission", "resume_upload"],
        "notes": ["Public URL references are stored for manual user navigation."],
    },
    CareerPlatform.OTHER_PUBLIC_CAREER_SITE: {
        "display_name": "Other public career site",
        "risk_posture": CareerPlatformRiskPosture.REQUIRES_REVIEW,
        "allowed_capabilities": ["manual_public_url_reference"],
        "blocked_capabilities": ["scraping", "automation", "application_submission"],
        "notes": ["Unknown platforms require review before broad use."],
    },
}


class IntegrationService:
    def __init__(
        self,
        repository: IntegrationRepository,
        *,
        institution_repo: InstitutionRepository,
        output_service: OutputAssemblyService,
    ) -> None:
        self._repo = repository
        self._institution_repo = institution_repo
        self._output_service = output_service

    def create_export(
        self,
        *,
        user_id: str,
        request: ExportRequest,
    ) -> ExportPayload:
        prepared = self._prepare_product_object(user_id=user_id, request=request)
        destination = destination_for_format(request.export_format)
        capability = capability_for_destination(destination)
        risk_posture = risk_posture_for_destination(destination)
        permission = IntegrationPermissionDecision(
            allowed=True,
            reason="Current user is authorized for this product object export.",
            boundary="current_user"
            if request.organization_id is None
            else "organization_membership",
            owner_user_id=user_id,
            organization_id=request.organization_id,
        )
        provenance = self._provenance(
            user_id=user_id,
            organization_id=request.organization_id,
            prepared=prepared,
        )
        export_id = _new_id("intexp")
        payload, filename, content_type, file_text = self._build_export_artifact(
            export_id=export_id,
            export_format=request.export_format,
            destination=destination,
            prepared=prepared,
            provenance=provenance,
        )
        receipt = self._receipt(
            integration_id=export_id,
            destination=destination,
            capability=capability,
            risk_posture=risk_posture,
            permission=permission,
            provenance=provenance,
            status="created",
            limitations=prepared.limitations,
            governance_warnings=prepared.governance_warnings,
        )
        row = IntegrationExportRecord(
            integration_export_id=export_id,
            owner_user_id=user_id,
            organization_id=request.organization_id,
            product_object_type=prepared.product_object_type.value,
            product_object_id=prepared.product_object_id,
            destination=destination.value,
            capability=capability.value,
            risk_posture=risk_posture.value,
            export_format=request.export_format.value,
            status="created",
            filename=filename,
            content_type=content_type,
            file_text=file_text,
            payload_json=json_safe(payload),
            receipt_json=receipt.model_dump(mode="json"),
            provenance_json=provenance.model_dump(mode="json"),
        )
        self._repo.add_export(row)
        self._repo.flush()
        return export_payload_from_row(row)

    def get_export(self, *, user_id: str, export_id: str) -> ExportPayload:
        row = self._authorized_export_row(user_id=user_id, export_id=export_id)
        return export_payload_from_row(row)

    def export_download(self, *, user_id: str, export_id: str) -> tuple[str, str, bytes]:
        row = self._authorized_export_row(user_id=user_id, export_id=export_id)
        if not row.file_text or not row.filename or not row.content_type:
            raise IntegrationDownloadUnavailable(export_id)
        body = row.file_text.encode("utf-8")
        return row.filename, row.content_type, body

    def create_reminder(
        self,
        *,
        user_id: str,
        request: ReminderRequest,
    ) -> ReminderPayload:
        if request.reminder_type in {
            ReminderType.INSTITUTIONAL_REPORT_REVIEW,
            ReminderType.DATA_REQUEST_DUE,
        } and request.organization_id is None:
            raise IntegrationAccessDenied(
                "Institutional reminder types require organization scope."
            )
        prepared = self._prepare_product_object(
            user_id=user_id,
            request=ExportRequest(
                product_object_type=request.product_object_type,
                product_object_id=request.product_object_id,
                export_format=ExportFormat.CSV,
                organization_id=request.organization_id,
            ),
        )
        destination = IntegrationDestination.ICS_CALENDAR
        capability = IntegrationCapability.CALENDAR_FILE
        risk_posture = IntegrationRiskPosture.CALENDAR_FILE_NO_SYNC
        permission = IntegrationPermissionDecision(
            allowed=True,
            reason="Current user is authorized to create a calendar file reminder.",
            boundary="current_user"
            if request.organization_id is None
            else "organization_membership",
            owner_user_id=user_id,
            organization_id=request.organization_id,
        )
        provenance = self._provenance(
            user_id=user_id,
            organization_id=request.organization_id,
            prepared=prepared,
        )
        reminder_id = _new_id("intrem")
        ics_content = build_ics_content(
            reminder_id=reminder_id,
            request=request,
            provenance=provenance,
        )
        receipt = self._receipt(
            integration_id=reminder_id,
            destination=destination,
            capability=capability,
            risk_posture=risk_posture,
            permission=permission,
            provenance=provenance,
            status="created",
            limitations=[
                "ICS export creates a local calendar file only.",
                "No Google Calendar, Outlook, or external platform write is performed.",
                "Reminder records do not create ATS applicant tracking status.",
            ],
            governance_warnings=[
                "Product-object provenance is embedded in the ICS description.",
                "Calendar tools must not be treated as product data authority.",
            ],
        )
        payload = {
            "reminder_id": reminder_id,
            "reminder_type": request.reminder_type.value,
            "title": request.title,
            "due_at": request.due_at.isoformat(),
            "timezone": request.timezone,
            "product_object": provenance.model_dump(mode="json"),
            "ics_export": {
                "filename": f"{reminder_id}.ics",
                "content_type": "text/calendar",
                "external_write_performed": False,
                "live_sync_enabled": False,
                "ats_application_status_created": False,
            },
        }
        row = IntegrationReminderRecord(
            integration_reminder_id=reminder_id,
            owner_user_id=user_id,
            organization_id=request.organization_id,
            product_object_type=request.product_object_type.value,
            product_object_id=request.product_object_id,
            reminder_type=request.reminder_type.value,
            destination=destination.value,
            capability=capability.value,
            risk_posture=risk_posture.value,
            status="created",
            title=request.title,
            due_at=_ensure_aware_utc(request.due_at),
            timezone=request.timezone,
            ics_content=ics_content,
            payload_json=json_safe(payload),
            receipt_json=receipt.model_dump(mode="json"),
            provenance_json=provenance.model_dump(mode="json"),
        )
        self._repo.add_reminder(row)
        self._repo.flush()
        return reminder_payload_from_row(row)

    def get_reminder(self, *, user_id: str, reminder_id: str) -> ReminderPayload:
        row = self._authorized_reminder_row(user_id=user_id, reminder_id=reminder_id)
        return reminder_payload_from_row(row)

    def reminder_ics(self, *, user_id: str, reminder_id: str) -> tuple[str, str, bytes]:
        row = self._authorized_reminder_row(user_id=user_id, reminder_id=reminder_id)
        return f"{row.integration_reminder_id}.ics", "text/calendar", row.ics_content.encode(
            "utf-8"
        )

    def create_partner_import(
        self,
        *,
        user_id: str,
        request: PartnerImportCreateRequest,
    ) -> PartnerImportBatchPayload:
        self._require_partner_import_action(
            organization_id=request.organization_id,
            user_id=user_id,
            action=InstitutionalAction.UPLOAD_PARTNER_IMPORTS,
        )
        validated_records, validation_result = self._validate_partner_import(
            request=request,
        )
        import_batch_id = _new_id("pib")
        receipt = self._partner_import_receipt(
            import_batch_id=import_batch_id,
            organization_id=request.organization_id,
            user_id=user_id,
            source_type=request.source_type,
            source_attribution=request.source_attribution,
            status=validation_result.status,
            validation_result=validation_result,
        )
        row = PartnerImportBatch(
            partner_import_batch_id=import_batch_id,
            organization_id=request.organization_id,
            uploaded_by_user_id=user_id,
            source_type=request.source_type.value,
            status=validation_result.status.value,
            import_format=request.import_format.value,
            source_attribution=request.source_attribution or "",
            original_filename=request.original_filename,
            raw_payload_text=request.content,
            record_count=validation_result.record_count,
            accepted_record_count=validation_result.accepted_record_count,
            quarantined_record_count=validation_result.quarantined_record_count,
            rejected_record_count=validation_result.rejected_record_count,
            validation_result_json=validation_result.model_dump(mode="json"),
            receipt_json=receipt.model_dump(mode="json"),
            governance_warnings_json=[
                warning.model_dump(mode="json") for warning in validation_result.warnings
            ],
        )
        self._repo.add_partner_import_batch(row)
        self._repo.flush()
        return partner_import_batch_payload_from_row(
            row,
            records=[],
            preview_records=_preview_partner_records(validated_records),
        )

    def list_partner_imports(
        self,
        *,
        user_id: str,
        organization_id: str,
    ) -> PartnerImportListPayload:
        self._require_partner_import_action(
            organization_id=organization_id,
            user_id=user_id,
            action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
        )
        rows = self._repo.list_partner_import_batches_for_organization(
            organization_id
        )
        return PartnerImportListPayload(
            imports=[
                partner_import_batch_payload_from_row(row, records=[], preview_records=[])
                for row in rows
            ]
        )

    def get_partner_import(
        self,
        *,
        user_id: str,
        import_batch_id: str,
    ) -> PartnerImportBatchPayload:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
        )
        records = self._repo.list_partner_import_records(import_batch_id)
        return partner_import_batch_payload_from_row(
            row,
            records=[partner_import_record_payload_from_row(record) for record in records],
            preview_records=[],
        )

    def validate_partner_import(
        self,
        *,
        user_id: str,
        import_batch_id: str,
    ) -> PartnerImportBatchPayload:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.UPLOAD_PARTNER_IMPORTS,
        )
        if row.status in {
            PartnerImportStatus.ACCEPTED.value,
            PartnerImportStatus.PARTIALLY_ACCEPTED.value,
            PartnerImportStatus.ARCHIVED.value,
        }:
            raise PartnerImportValidationError(
                "Accepted or archived import batches cannot be revalidated."
            )
        request = partner_import_request_from_row(row)
        validated_records, validation_result = self._validate_partner_import(
            request=request,
        )
        self._apply_partner_import_validation(
            row=row,
            user_id=user_id,
            validation_result=validation_result,
        )
        self._repo.flush()
        return partner_import_batch_payload_from_row(
            row,
            records=[],
            preview_records=_preview_partner_records(validated_records),
        )

    def accept_partner_import(
        self,
        *,
        user_id: str,
        import_batch_id: str,
        reason: str | None = None,
    ) -> PartnerImportBatchPayload:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.REVIEW_PARTNER_IMPORTS,
        )
        if row.status == PartnerImportStatus.ARCHIVED.value:
            raise PartnerImportValidationError("Archived import batches cannot be accepted.")
        request = partner_import_request_from_row(row)
        validated_records, validation_result = self._validate_partner_import(
            request=request,
        )
        if validation_result.accepted_record_count <= 0:
            raise PartnerImportValidationError(
                "Import batch has no records eligible for acceptance."
            )
        self._repo.delete_partner_import_records(row.partner_import_batch_id)
        for validated in validated_records:
            record = self._partner_import_record_from_validation(
                row=row,
                validated=validated,
            )
            self._repo.add_partner_import_record(record)
        row.status = (
            PartnerImportStatus.ACCEPTED.value
            if validation_result.accepted_record_count == validation_result.record_count
            else PartnerImportStatus.PARTIALLY_ACCEPTED.value
        )
        row.record_count = validation_result.record_count
        row.accepted_record_count = validation_result.accepted_record_count
        row.quarantined_record_count = validation_result.quarantined_record_count
        row.rejected_record_count = validation_result.rejected_record_count
        row.validation_result_json = validation_result.model_dump(mode="json")
        row.governance_warnings_json = [
            warning.model_dump(mode="json") for warning in validation_result.warnings
        ]
        row.receipt_json = self._partner_import_receipt(
            import_batch_id=row.partner_import_batch_id,
            organization_id=row.organization_id,
            user_id=row.uploaded_by_user_id,
            source_type=PartnerImportSourceType(row.source_type),
            source_attribution=row.source_attribution,
            status=PartnerImportStatus(row.status),
            validation_result=validation_result,
            reviewer_user_id=user_id,
            review_reason=reason,
        ).model_dump(mode="json")
        self._repo.flush()
        records = self._repo.list_partner_import_records(row.partner_import_batch_id)
        return partner_import_batch_payload_from_row(
            row,
            records=[partner_import_record_payload_from_row(record) for record in records],
            preview_records=[],
        )

    def reject_partner_import(
        self,
        *,
        user_id: str,
        import_batch_id: str,
        reason: str | None = None,
    ) -> PartnerImportBatchPayload:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.REVIEW_PARTNER_IMPORTS,
        )
        validation_result = PartnerImportValidationResult.model_validate(
            row.validation_result_json
        )
        row.status = PartnerImportStatus.REJECTED.value
        row.receipt_json = self._partner_import_receipt(
            import_batch_id=row.partner_import_batch_id,
            organization_id=row.organization_id,
            user_id=row.uploaded_by_user_id,
            source_type=PartnerImportSourceType(row.source_type),
            source_attribution=row.source_attribution,
            status=PartnerImportStatus.REJECTED,
            validation_result=validation_result,
            reviewer_user_id=user_id,
            review_reason=reason,
        ).model_dump(mode="json")
        self._repo.flush()
        return partner_import_batch_payload_from_row(row, records=[], preview_records=[])

    def archive_partner_import(
        self,
        *,
        user_id: str,
        import_batch_id: str,
        reason: str | None = None,
    ) -> PartnerImportBatchPayload:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.REVIEW_PARTNER_IMPORTS,
        )
        validation_result = PartnerImportValidationResult.model_validate(
            row.validation_result_json
        )
        row.status = PartnerImportStatus.ARCHIVED.value
        row.receipt_json = self._partner_import_receipt(
            import_batch_id=row.partner_import_batch_id,
            organization_id=row.organization_id,
            user_id=row.uploaded_by_user_id,
            source_type=PartnerImportSourceType(row.source_type),
            source_attribution=row.source_attribution,
            status=PartnerImportStatus.ARCHIVED,
            validation_result=validation_result,
            reviewer_user_id=user_id,
            review_reason=reason,
        ).model_dump(mode="json")
        self._repo.flush()
        return partner_import_batch_payload_from_row(row, records=[], preview_records=[])

    def partner_import_receipt(
        self,
        *,
        user_id: str,
        import_batch_id: str,
    ) -> PartnerImportReceipt:
        row = self._authorized_partner_import_batch(
            user_id=user_id,
            import_batch_id=import_batch_id,
            action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
        )
        return PartnerImportReceipt.model_validate(row.receipt_json)

    def create_api_client(
        self,
        *,
        user_id: str,
        request: ApiClientCreateRequest,
    ) -> ApiClientPayload:
        if not set(request.scopes).issubset(SAFE_API_SCOPES):
            raise IntegrationAccessDenied("Unsupported API scope requested.")
        if request.organization_id is not None:
            organization = self._institution_repo.get_organization(request.organization_id)
            if organization is None:
                raise OrganizationNotFound(request.organization_id)
        row = ApiClient(
            api_client_id=_new_id("apic"),
            display_name=request.display_name,
            created_by_user_id=user_id,
            organization_id=request.organization_id,
            status=ApiClientStatus.ACTIVE.value,
            scopes_json=[scope.value for scope in request.scopes],
            allowed_origins_json=list(request.allowed_origins),
            rate_limit_count=request.rate_limit_count,
            rate_limit_window_seconds=request.rate_limit_window_seconds,
        )
        self._repo.add_api_client(row)
        self._repo.flush()
        return api_client_payload_from_row(row, keys=[])

    def list_api_clients(self) -> ApiClientListPayload:
        clients = self._repo.list_api_clients()
        return ApiClientListPayload(
            api_clients=[
                api_client_payload_from_row(
                    row,
                    keys=[
                        safe_api_key_display_from_row(key, reveal_raw_key=None)
                        for key in self._repo.list_api_keys_for_client(row.api_client_id)
                    ],
                )
                for row in clients
            ]
        )

    def create_api_key(
        self,
        *,
        user_id: str,
        api_client_id: str,
    ) -> ApiKeyCreatePayload:
        client = self._repo.get_api_client(api_client_id)
        if client is None:
            raise ApiClientNotFound(api_client_id)
        raw_key = _generate_api_key()
        key = ApiKey(
            api_key_id=_new_id("apikey"),
            api_client_id=api_client_id,
            created_by_user_id=user_id,
            key_prefix=raw_key[:12],
            key_hash=_hash_api_key(raw_key),
            display_key=_display_api_key(raw_key),
            status=ApiClientStatus.ACTIVE.value,
        )
        self._repo.add_api_key(key)
        self._repo.flush()
        return ApiKeyCreatePayload(
            api_key=safe_api_key_display_from_row(key, reveal_raw_key=raw_key)
        )

    def revoke_api_key(self, *, api_key_id: str) -> SafeApiKeyDisplay:
        key = self._repo.get_api_key(api_key_id)
        if key is None:
            raise ApiKeyNotFound(api_key_id)
        key.status = ApiClientStatus.REVOKED.value
        key.revoked_at = datetime.now(UTC)
        self._repo.flush()
        return safe_api_key_display_from_row(key, reveal_raw_key=None)

    def update_api_client(
        self,
        *,
        api_client_id: str,
        request: ApiClientUpdateRequest,
    ) -> ApiClientPayload:
        client = self._repo.get_api_client(api_client_id)
        if client is None:
            raise ApiClientNotFound(api_client_id)
        if request.scopes is not None:
            if not set(request.scopes).issubset(SAFE_API_SCOPES):
                raise IntegrationAccessDenied("Unsupported API scope requested.")
            client.scopes_json = [scope.value for scope in request.scopes]
        if request.rate_limit_count is not None:
            client.rate_limit_count = request.rate_limit_count
        if request.rate_limit_window_seconds is not None:
            client.rate_limit_window_seconds = request.rate_limit_window_seconds
        if request.status is not None:
            client.status = request.status.value
        self._repo.flush()
        return api_client_payload_from_row(
            client,
            keys=[
                safe_api_key_display_from_row(key, reveal_raw_key=None)
                for key in self._repo.list_api_keys_for_client(client.api_client_id)
            ],
        )

    def list_api_usage(self, *, api_client_id: str) -> ApiUsageListPayload:
        if self._repo.get_api_client(api_client_id) is None:
            raise ApiClientNotFound(api_client_id)
        return ApiUsageListPayload(
            usage=[
                api_usage_payload_from_row(row)
                for row in self._repo.list_api_usage_for_client(api_client_id)
            ]
        )

    def authenticate_external_api_key(
        self,
        *,
        raw_key: str | None,
        required_scope: ApiScope,
        route: str,
        method: str = "GET",
        requested_organization_id: str | None = None,
    ) -> ExternalApiContext:
        if not raw_key:
            self._record_api_decision(
                api_client_id=None,
                api_key_id=None,
                route=route,
                method=method,
                scope=required_scope,
                decision="invalid_key",
                status_code=401,
                rate_limit=None,
            )
            raise ApiAuthenticationError("External API key required.")
        key = self._repo.get_api_key_by_hash(_hash_api_key(raw_key.strip()))
        if key is None:
            self._record_api_decision(
                api_client_id=None,
                api_key_id=None,
                route=route,
                method=method,
                scope=required_scope,
                decision="invalid_key",
                status_code=401,
                rate_limit=None,
            )
            raise ApiAuthenticationError("Invalid external API key.")
        client = self._repo.get_api_client(key.api_client_id)
        if client is None or client.status != ApiClientStatus.ACTIVE.value:
            self._record_api_decision(
                api_client_id=key.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="invalid_key",
                status_code=401,
                rate_limit=None,
            )
            raise ApiAuthenticationError("Invalid external API client.")
        if key.status != ApiClientStatus.ACTIVE.value:
            self._record_api_decision(
                api_client_id=client.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="revoked_key",
                status_code=401,
                rate_limit=None,
            )
            raise ApiAuthenticationError("Revoked external API key.")
        scopes = [ApiScope(scope) for scope in client.scopes_json]
        if required_scope not in scopes:
            self._record_api_decision(
                api_client_id=client.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="missing_scope",
                status_code=403,
                rate_limit=None,
            )
            raise ApiScopeDenied(f"Missing external API scope: {required_scope.value}")
        if (
            requested_organization_id is not None
            and requested_organization_id != client.organization_id
        ):
            self._record_api_decision(
                api_client_id=client.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="missing_scope",
                status_code=403,
                rate_limit=None,
            )
            raise ApiScopeDenied("External API client cannot cross institution boundary.")
        if required_scope == ApiScope.INSTITUTION_DASHBOARD_READ and (
            requested_organization_id is None
            or client.organization_id != requested_organization_id
        ):
            self._record_api_decision(
                api_client_id=client.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="missing_scope",
                status_code=403,
                rate_limit=None,
            )
            raise ApiScopeDenied(
                "Institution dashboard API clients must be bound to the requested institution."
            )

        rate_limit = self._rate_limit_decision(client)
        if not rate_limit.allowed:
            self._record_api_decision(
                api_client_id=client.api_client_id,
                api_key_id=key.api_key_id,
                route=route,
                method=method,
                scope=required_scope,
                decision="rate_limited",
                status_code=429,
                rate_limit=rate_limit,
            )
            raise ApiRateLimitExceeded(rate_limit)
        key.last_used_at = datetime.now(UTC)
        self._record_api_decision(
            api_client_id=client.api_client_id,
            api_key_id=key.api_key_id,
            route=route,
            method=method,
            scope=required_scope,
            decision="allowed",
            status_code=200,
            rate_limit=rate_limit,
        )
        self._repo.flush()
        return ExternalApiContext(
            api_client_id=client.api_client_id,
            api_key_id=key.api_key_id,
            organization_id=client.organization_id,
            scopes=scopes,
            rate_limit=rate_limit,
        )

    def external_regions(self, *, context: ExternalApiContext) -> ApiResponseEnvelope:
        regions = self._repo.session.query(Region).order_by(Region.region_id).all()
        data = [
            sanitize_export_data(
                {
                    "region_id": region.region_id,
                    "display_name": region.display_name,
                    "region_type": region.region_type,
                    "state": getattr(region, "state", None),
                }
            )
            for region in regions
        ]
        return self._external_envelope(
            data={"regions": data},
            rate_limit=context.rate_limit,
            freshness_status="unknown",
            confidence="mixed",
            coverage_tier="mixed",
        )

    def external_region_intelligence(
        self,
        *,
        region_id: str,
        context: ExternalApiContext,
    ) -> ApiResponseEnvelope:
        result = self._output_service.read_region(region_id)
        body = sanitize_export_data(result.payload.region.model_dump(mode="json"))
        metadata = result.payload.metadata.model_dump(mode="json")
        return self._external_envelope(
            data=body,
            rate_limit=context.rate_limit,
            freshness_status=_freshness_status(metadata, result.metadata),
            confidence=_confidence_label(body),
            coverage_tier=_coverage_tier(body),
        )

    def external_company_geography(
        self,
        *,
        company_id: str,
        context: ExternalApiContext,
    ) -> ApiResponseEnvelope:
        result = self._output_service.read_company(company_id)
        body = sanitize_export_data(result.payload.company.model_dump(mode="json"))
        metadata = result.payload.metadata.model_dump(mode="json")
        return self._external_envelope(
            data=body,
            rate_limit=context.rate_limit,
            freshness_status=_freshness_status(metadata, result.metadata),
            confidence=_confidence_label(body),
            coverage_tier=_coverage_tier(body),
        )

    def external_market_signals(
        self,
        *,
        context: ExternalApiContext,
    ) -> ApiResponseEnvelope:
        companies = self._repo.session.query(Company).order_by(Company.company_id).limit(100).all()
        data = [
            sanitize_export_data(
                {
                    "company_id": company.company_id,
                    "company_name": company.company_name,
                    "sector_primary": company.sector_primary,
                    "classification_confidence": company.classification_confidence,
                }
            )
            for company in companies
        ]
        return self._external_envelope(
            data={"market_signals": data},
            rate_limit=context.rate_limit,
            freshness_status="unknown",
            confidence="mixed",
            coverage_tier="mixed",
        )

    def external_institution_dashboard(
        self,
        *,
        organization_id: str,
        context: ExternalApiContext,
    ) -> ApiResponseEnvelope:
        if context.organization_id != organization_id:
            raise ApiScopeDenied("External API client cannot cross institution boundary.")
        dashboard = self._institutional_dashboard(organization_id=organization_id)
        data = sanitize_export_data(dashboard.model_dump(mode="json"))
        partner_evidence = self._partner_import_evidence_summary(
            organization_id=organization_id
        )
        if partner_evidence:
            data["partner_contributed_evidence"] = partner_evidence
        return self._external_envelope(
            data=data,
            rate_limit=context.rate_limit,
            freshness_status=str(dashboard.data_freshness.get("freshness_status", "unknown")),
            confidence="aggregate",
            coverage_tier="institutional_aggregate",
            partner_evidence=partner_evidence,
        )

    def career_platform_registry(self) -> CareerPlatformRegistryPayload:
        return CareerPlatformRegistryPayload(
            platforms=[
                {
                    "platform": platform.value,
                    **json_safe(config),
                    "manual_only": True,
                    "automation_performed": False,
                    "ats_state_created": False,
                }
                for platform, config in CAREER_PLATFORM_REGISTRY.items()
            ]
        )

    def create_career_platform_reference(
        self,
        *,
        user_id: str,
        request: CareerPlatformReferenceCreateRequest,
    ) -> CareerPlatformReferencePayload:
        registry = CAREER_PLATFORM_REGISTRY[request.platform]
        risk_posture = CareerPlatformRiskPosture(registry["risk_posture"])
        if risk_posture == CareerPlatformRiskPosture.BLOCKED_HOSTILE_TOS:
            raise CareerPlatformBoundaryError("This platform posture blocks references.")
        if request.organization_id is not None:
            self._require_partner_import_action(
                organization_id=request.organization_id,
                user_id=user_id,
                action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
            )
        reference_id = _new_id("cpr")
        row = CareerPlatformReferenceRecord(
            career_platform_reference_id=reference_id,
            platform=request.platform.value,
            risk_posture=risk_posture.value,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            url=request.url,
            label=request.label or _career_platform_label(request.platform, request.subject_id),
            organization_id=request.organization_id,
            submitted_by_user_id=user_id,
            manual_only=True,
            automation_performed=False,
            ats_state_created=False,
        )
        self._repo.add_career_platform_reference(row)
        self._repo.flush()
        return CareerPlatformReferencePayload(reference=career_platform_reference_from_row(row))

    def list_career_platform_references(
        self,
        *,
        user_id: str,
        organization_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> CareerPlatformReferenceListPayload:
        if organization_id is not None:
            self._require_partner_import_action(
                organization_id=organization_id,
                user_id=user_id,
                action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
            )
        return CareerPlatformReferenceListPayload(
            references=[
                career_platform_reference_from_row(row)
                for row in self._repo.list_career_platform_references(
                    organization_id=organization_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                )
            ]
        )

    def create_career_platform_export(
        self,
        *,
        user_id: str,
        request: CareerPlatformExportRequest,
    ) -> CareerPlatformExportPayload:
        registry = CAREER_PLATFORM_REGISTRY[request.platform]
        risk_posture = CareerPlatformRiskPosture(registry["risk_posture"])
        if request.organization_id is not None:
            self._require_partner_import_action(
                organization_id=request.organization_id,
                user_id=user_id,
                action=InstitutionalAction.VIEW_PARTNER_IMPORTS,
            )
        rows = self._career_platform_export_rows(request)
        export_model = CareerPlatformExport(
            career_platform_export_id=_new_id("cpe"),
            platform=request.platform,
            risk_posture=risk_posture,
            export_mode="manual_lookup_export",
            rows=rows,
            manual_only=True,
            automation_performed=False,
            ats_state_created=False,
            application_status_created=False,
            recruiter_outreach_created=False,
        )
        row = CareerPlatformExportRecord(
            career_platform_export_id=export_model.career_platform_export_id,
            created_by_user_id=user_id,
            organization_id=request.organization_id,
            platform=request.platform.value,
            risk_posture=risk_posture.value,
            export_mode=export_model.export_mode,
            rows_json=json_safe(rows),
            receipt_json=export_model.model_dump(mode="json"),
            manual_only=True,
            automation_performed=False,
            ats_state_created=False,
            application_status_created=False,
            recruiter_outreach_created=False,
        )
        self._repo.add_career_platform_export(row)
        self._repo.flush()
        return CareerPlatformExportPayload(export=export_model)

    def career_platform_links_for_company(self, *, company_id: str) -> dict[str, Any]:
        company = self._repo.session.get(Company, company_id)
        if company is None:
            raise IntegrationObjectNotFound(company_id)
        name = company.company_name
        encoded = quote_plus(name)
        return {
            "company_id": company_id,
            "company_name": name,
            "links": [
                ExternalCareerLink(
                    url=f"https://www.linkedin.com/search/results/companies/?keywords={encoded}",
                    label="Search this company on LinkedIn",
                    platform=CareerPlatform.LINKEDIN,
                    risk_posture=CareerPlatformRiskPosture.DEEP_LINK_ONLY,
                ).model_dump(mode="json"),
                ExternalCareerLink(
                    url=f"https://app.joinhandshake.com/stu/postings?query={encoded}",
                    label="Search this employer in Handshake",
                    platform=CareerPlatform.HANDSHAKE,
                    risk_posture=CareerPlatformRiskPosture.EXPORT_ONLY,
                ).model_dump(mode="json"),
            ],
            "blocked_workflows": [
                "scraping",
                "automated_application_submission",
                "resume_upload",
                "recruiter_outreach",
                "ats_pipeline",
                "employer_crm",
            ],
        }

    def _rate_limit_decision(self, client: ApiClient) -> ApiRateLimitDecision:
        now = datetime.now(UTC)
        window = timedelta(seconds=client.rate_limit_window_seconds)
        used = self._repo.count_allowed_api_usage_since(
            api_client_id=client.api_client_id,
            since=now - window,
        )
        allowed = used < client.rate_limit_count
        remaining = max(client.rate_limit_count - used - (1 if allowed else 0), 0)
        reset_at = now + window
        return ApiRateLimitDecision(
            allowed=allowed,
            limit=client.rate_limit_count,
            remaining=remaining,
            reset_at=reset_at,
            window_seconds=client.rate_limit_window_seconds,
            reason="request allowed" if allowed else "rate limit exhausted",
        )

    def _record_api_decision(
        self,
        *,
        api_client_id: str | None,
        api_key_id: str | None,
        route: str,
        method: str,
        scope: ApiScope,
        decision: str,
        status_code: int,
        rate_limit: ApiRateLimitDecision | None,
    ) -> None:
        usage_id = _new_id("apiuse")
        self._repo.add_api_usage_record(
            ApiUsageRecord(
                api_usage_record_id=usage_id,
                api_client_id=api_client_id,
                api_key_id=api_key_id,
                route=route,
                method=method,
                scope=scope.value,
                decision=decision,
                status_code=status_code,
                rate_limit_limit=rate_limit.limit if rate_limit else None,
                rate_limit_remaining=rate_limit.remaining if rate_limit else None,
                rate_limit_reset_at=rate_limit.reset_at if rate_limit else None,
            )
        )
        self._repo.add_api_access_audit_event(
            ApiAccessAuditEvent(
                api_access_audit_event_id=_new_id("apiaud"),
                api_client_id=api_client_id,
                api_key_id=api_key_id,
                route=route,
                scope=scope.value,
                decision=decision,
                status_code=status_code,
                event_metadata={
                    "rate_limit": rate_limit.model_dump(mode="json")
                    if rate_limit
                    else None,
                    "external_api": True,
                },
            )
        )
        self._repo.flush()

    def _external_envelope(
        self,
        *,
        data: Any,
        rate_limit: ApiRateLimitDecision,
        freshness_status: str | None,
        confidence: str | None,
        coverage_tier: str | None,
        partner_evidence: list[dict[str, Any]] | None = None,
    ) -> ApiResponseEnvelope:
        return ApiResponseEnvelope(
            data=sanitize_export_data(data),
            meta=ApiResponseMeta(
                coverage_tier=coverage_tier,
                freshness_status=freshness_status,
                confidence=confidence,
                source_governance=[
                    "External API responses preserve product governance metadata.",
                    "Internal-only scoring/source fields are withheld.",
                ],
                governance_warnings=[
                    "External API clients do not define product semantics.",
                    "Responses are controlled read/access surfaces, not open resale feeds.",
                ],
                partner_contributed_evidence=partner_evidence or [],
                rate_limit=rate_limit,
            ),
        )

    def _career_platform_export_rows(
        self,
        request: CareerPlatformExportRequest,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for company_id in request.company_ids:
            company = self._repo.session.get(Company, company_id)
            name = company.company_name if company else company_id
            rows.append(_career_platform_row(request.platform, company_id, name))
        for name in request.employer_names:
            rows.append(_career_platform_row(request.platform, None, name))
        return rows

    def _authorized_export_row(
        self,
        *,
        user_id: str,
        export_id: str,
    ) -> IntegrationExportRecord:
        row = self._repo.get_export(export_id)
        if row is None:
            raise IntegrationExportNotFound(export_id)
        if row.owner_user_id != user_id:
            raise IntegrationAccessDenied("Export belongs to another user.")
        if row.organization_id is not None:
            self._require_org_action(
                organization_id=row.organization_id,
                user_id=user_id,
                product_object_type=ProductObjectType(row.product_object_type),
            )
        return row

    def _authorized_reminder_row(
        self,
        *,
        user_id: str,
        reminder_id: str,
    ) -> IntegrationReminderRecord:
        row = self._repo.get_reminder(reminder_id)
        if row is None:
            raise IntegrationReminderNotFound(reminder_id)
        if row.owner_user_id != user_id:
            raise IntegrationAccessDenied("Reminder belongs to another user.")
        if row.organization_id is not None:
            self._require_org_action(
                organization_id=row.organization_id,
                user_id=user_id,
                product_object_type=ProductObjectType(row.product_object_type),
            )
        return row

    def _authorized_partner_import_batch(
        self,
        *,
        user_id: str,
        import_batch_id: str,
        action: InstitutionalAction,
    ) -> PartnerImportBatch:
        row = self._repo.get_partner_import_batch(import_batch_id)
        if row is None:
            raise PartnerImportNotFound(import_batch_id)
        self._require_partner_import_action(
            organization_id=row.organization_id,
            user_id=user_id,
            action=action,
        )
        return row

    def _require_partner_import_action(
        self,
        *,
        organization_id: str,
        user_id: str,
        action: InstitutionalAction,
    ) -> tuple[Organization, Any]:
        organization = self._institution_repo.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        if organization.status != "active":
            raise InstitutionalAccessDenied(organization_id)
        if not can_perform_institutional_action(
            self._institution_repo,
            user_id=user_id,
            organization_id=organization_id,
            action=action,
        ):
            raise InstitutionalAccessDenied(organization_id)
        membership = active_membership_for_user(
            self._institution_repo,
            user_id=user_id,
            organization_id=organization_id,
        )
        if membership is None:
            raise InstitutionalAccessDenied(organization_id)
        return organization, membership

    def _validate_partner_import(
        self,
        *,
        request: PartnerImportCreateRequest,
    ) -> tuple[list[_ValidatedPartnerRecord], PartnerImportValidationResult]:
        records = parse_partner_import_records(request)
        duplicate_names = _duplicate_employer_names(records)
        validated: list[_ValidatedPartnerRecord] = []
        all_warnings: list[PartnerImportGovernanceWarning] = []
        required_missing: list[str] = []
        unsupported_fields: list[str] = []

        for index, raw_record in enumerate(records):
            record = _normalize_record(raw_record)
            row_warnings = self._partner_record_warnings(
                record=record,
                source_type=request.source_type,
                record_index=index,
                batch_source_attribution=request.source_attribution,
                duplicate_names=duplicate_names,
            )
            all_warnings.extend(row_warnings)
            required_missing.extend(
                warning.field or ""
                for warning in row_warnings
                if warning.code == "missing_required_field"
            )
            unsupported_fields.extend(
                warning.field or ""
                for warning in row_warnings
                if warning.code == "unsupported_field"
            )
            decision = _decision_for_warnings(row_warnings)
            source_attribution = _record_source_attribution(
                record,
                request.source_attribution,
            )
            sanitized = sanitize_partner_import_record(
                record,
                source_type=request.source_type,
            )
            validated.append(
                _ValidatedPartnerRecord(
                    record_index=index,
                    raw=record,
                    sanitized=sanitized,
                    warnings=row_warnings,
                    decision=decision,
                    source_attribution=source_attribution or "missing_source_attribution",
                    employer_name=_clean_optional(record.get("employer_name")),
                    normalized_employer_name=_normalize_name(record.get("employer_name")),
                    region_label=_clean_optional(record.get("region")),
                    normalized_region_id=self._normalized_region_id(record.get("region")),
                    confidence=_confidence_for_decision(decision, row_warnings),
                    freshness_status=_freshness_for_record(record),
                )
            )

        accepted_count = sum(
            1 for item in validated if item.decision == PartnerImportDecision.ACCEPT
        )
        quarantined_count = sum(
            1 for item in validated if item.decision == PartnerImportDecision.QUARANTINE
        )
        rejected_count = sum(
            1 for item in validated if item.decision == PartnerImportDecision.REJECT
        )
        blocking_privacy = any(
            warning.code
            in {
                "student_level_pii",
                "individual_outcome_record",
                "sensitive_demographic_attribute",
                "ats_application_status_semantics",
            }
            for warning in all_warnings
        )
        blocking_source = any(
            warning.code == "missing_source_attribution" for warning in all_warnings
        )
        status = _validation_status(
            record_count=len(records),
            accepted_count=accepted_count,
            quarantined_count=quarantined_count,
            rejected_count=rejected_count,
            warnings=all_warnings,
        )
        result = PartnerImportValidationResult(
            status=status,
            record_count=len(records),
            accepted_record_count=accepted_count,
            quarantined_record_count=quarantined_count,
            rejected_record_count=rejected_count,
            warning_count=len(all_warnings),
            warnings=all_warnings,
            required_fields_missing=required_missing,
            unsupported_fields=unsupported_fields,
            has_blocking_privacy_issue=blocking_privacy,
            has_blocking_source_issue=blocking_source,
            can_accept=accepted_count > 0,
        )
        return validated, result

    def _partner_record_warnings(
        self,
        *,
        record: dict[str, Any],
        source_type: PartnerImportSourceType,
        record_index: int,
        batch_source_attribution: str | None,
        duplicate_names: set[str],
    ) -> list[PartnerImportGovernanceWarning]:
        warnings: list[PartnerImportGovernanceWarning] = []
        allowed = ALLOWED_PARTNER_IMPORT_FIELDS[source_type]
        required = REQUIRED_PARTNER_IMPORT_FIELDS[source_type]
        keys = set(record)

        for field in sorted(required):
            if not _present(record.get(field)):
                warnings.append(
                    _warning(
                        "missing_required_field",
                        "blocking",
                        f"Required field '{field}' is missing.",
                        record_index,
                        field,
                        PartnerImportDecision.REJECT,
                    )
                )

        for key in sorted(keys - allowed):
            normalized_key = _normalize_field_name(key)
            if _is_internal_only_import_field(normalized_key):
                warnings.append(
                    _warning(
                        "internal_only_field",
                        "blocking",
                        f"Internal-only field '{key}' is not accepted in imports.",
                        record_index,
                        key,
                        PartnerImportDecision.REJECT,
                    )
                )
            elif _is_pii_field(normalized_key):
                warnings.append(
                    _warning(
                        "student_level_pii",
                        "quarantine",
                        f"Student-level PII field '{key}' is quarantined.",
                        record_index,
                        key,
                        PartnerImportDecision.QUARANTINE,
                    )
                )
            elif _is_individual_outcome_field(normalized_key):
                warnings.append(
                    _warning(
                        "individual_outcome_record",
                        "quarantine",
                        f"Individual outcome field '{key}' is quarantined.",
                        record_index,
                        key,
                        PartnerImportDecision.QUARANTINE,
                    )
                )
            elif _is_sensitive_demographic_field(normalized_key):
                warnings.append(
                    _warning(
                        "sensitive_demographic_attribute",
                        "quarantine",
                        f"Sensitive demographic field '{key}' is quarantined.",
                        record_index,
                        key,
                        PartnerImportDecision.QUARANTINE,
                    )
                )
            else:
                warnings.append(
                    _warning(
                        "unsupported_field",
                        "warning",
                        f"Unsupported field '{key}' is ignored.",
                        record_index,
                        key,
                        PartnerImportDecision.NEEDS_REVIEW,
                    )
                )

        source_attribution = _record_source_attribution(record, batch_source_attribution)
        if not source_attribution:
            warnings.append(
                _warning(
                    "missing_source_attribution",
                    "blocking",
                    "Source attribution is required for accepted partner records.",
                    record_index,
                    "source_attribution",
                    PartnerImportDecision.REJECT,
                )
            )

        employer_name = _clean_optional(record.get("employer_name"))
        normalized_employer = _normalize_name(employer_name)
        if normalized_employer and normalized_employer in duplicate_names:
            warnings.append(
                _warning(
                    "duplicate_employer",
                    "warning",
                    f"Duplicate employer '{employer_name}' appears in this import.",
                    record_index,
                    "employer_name",
                    PartnerImportDecision.NEEDS_REVIEW,
                )
            )
        if normalized_employer in AMBIGUOUS_EMPLOYER_NAMES:
            warnings.append(
                _warning(
                    "ambiguous_employer_name",
                    "warning",
                    f"Employer name '{employer_name}' is ambiguous.",
                    record_index,
                    "employer_name",
                    PartnerImportDecision.NEEDS_REVIEW,
                )
            )
        warnings.extend(
            self._company_identity_warnings(
                record=record,
                record_index=record_index,
            )
        )
        warnings.extend(
            self._region_warnings(record=record, record_index=record_index)
        )
        stale_field = _stale_date_field(record)
        if stale_field is not None:
            warnings.append(
                _warning(
                    "stale_date",
                    "warning",
                    f"Date field '{stale_field}' is stale for partner evidence.",
                    record_index,
                    stale_field,
                    PartnerImportDecision.NEEDS_REVIEW,
                )
            )
        if _record_has_ats_status_semantics(record):
            warnings.append(
                _warning(
                    "ats_application_status_semantics",
                    "quarantine",
                    "Application status semantics are not accepted in partner imports.",
                    record_index,
                    "application_status",
                    PartnerImportDecision.QUARANTINE,
                )
            )
        if (
            source_type == PartnerImportSourceType.AGGREGATED_CAREER_CENTER_OUTCOME_DATA
            and not _present(record.get("aggregate_count"))
        ):
            warnings.append(
                _warning(
                    "unverified_outcome_claim",
                    "blocking",
                    "Career-center outcomes must be aggregate claims with counts.",
                    record_index,
                    "aggregate_count",
                    PartnerImportDecision.REJECT,
                )
            )
        return warnings

    def _company_identity_warnings(
        self,
        *,
        record: dict[str, Any],
        record_index: int,
    ) -> list[PartnerImportGovernanceWarning]:
        company_id = _clean_optional(record.get("company_id"))
        employer_name = _clean_optional(record.get("employer_name"))
        if not company_id or not employer_name:
            return []
        company = self._repo.session.get(Company, company_id)
        if company is None:
            return [
                _warning(
                    "company_identity_conflict",
                    "warning",
                    f"Company id '{company_id}' is not a known canonical company.",
                    record_index,
                    "company_id",
                    PartnerImportDecision.NEEDS_REVIEW,
                )
            ]
        canonical_name = _normalize_name(company.company_name)
        imported_name = _normalize_name(employer_name)
        if canonical_name and imported_name and canonical_name != imported_name:
            return [
                _warning(
                    "company_identity_conflict",
                    "warning",
                    "Partner employer name conflicts with canonical company identity.",
                    record_index,
                    "company_id",
                    PartnerImportDecision.NEEDS_REVIEW,
                )
            ]
        return []

    def _region_warnings(
        self,
        *,
        record: dict[str, Any],
        record_index: int,
    ) -> list[PartnerImportGovernanceWarning]:
        region_label = _clean_optional(record.get("region"))
        if not region_label:
            return []
        if self._normalized_region_id(region_label) is not None:
            return []
        return [
            _warning(
                "region_normalization_issue",
                "warning",
                f"Region '{region_label}' does not match a canonical region.",
                record_index,
                "region",
                PartnerImportDecision.NEEDS_REVIEW,
            )
        ]

    def _normalized_region_id(self, value: Any) -> str | None:
        label = _clean_optional(value)
        if not label:
            return None
        normalized = _normalize_name(label)
        if not normalized:
            return None
        rows = self._repo.session.query(Region).all()
        for row in rows:
            candidates = {
                _normalize_name(row.region_id),
                _normalize_name(row.region_name),
                _normalize_name(row.display_name),
            }
            if normalized in candidates:
                return row.region_id
        return None

    def _apply_partner_import_validation(
        self,
        *,
        row: PartnerImportBatch,
        user_id: str,
        validation_result: PartnerImportValidationResult,
    ) -> None:
        row.status = validation_result.status.value
        row.record_count = validation_result.record_count
        row.accepted_record_count = validation_result.accepted_record_count
        row.quarantined_record_count = validation_result.quarantined_record_count
        row.rejected_record_count = validation_result.rejected_record_count
        row.validation_result_json = validation_result.model_dump(mode="json")
        row.governance_warnings_json = [
            warning.model_dump(mode="json") for warning in validation_result.warnings
        ]
        row.receipt_json = self._partner_import_receipt(
            import_batch_id=row.partner_import_batch_id,
            organization_id=row.organization_id,
            user_id=row.uploaded_by_user_id,
            source_type=PartnerImportSourceType(row.source_type),
            source_attribution=row.source_attribution,
            status=validation_result.status,
            validation_result=validation_result,
            reviewer_user_id=user_id,
        ).model_dump(mode="json")

    def _partner_import_record_from_validation(
        self,
        *,
        row: PartnerImportBatch,
        validated: _ValidatedPartnerRecord,
    ) -> PartnerImportRecord:
        import_record_id = _new_id("pir")
        record_status = (
            "accepted"
            if validated.decision == PartnerImportDecision.ACCEPT
            else "quarantined"
            if validated.decision == PartnerImportDecision.QUARANTINE
            else "rejected"
        )
        evidence = PartnerContributedEvidence(
            import_batch_id=row.partner_import_batch_id,
            import_record_id=import_record_id,
            organization_id=row.organization_id,
            source_type=PartnerImportSourceType(row.source_type),
            source_attribution=validated.source_attribution,
            confidence=validated.confidence,
            freshness_status=validated.freshness_status,
            governance_warnings=validated.warnings,
        )
        return PartnerImportRecord(
            partner_import_record_id=import_record_id,
            partner_import_batch_id=row.partner_import_batch_id,
            organization_id=row.organization_id,
            record_index=validated.record_index,
            source_type=row.source_type,
            record_status=record_status,
            decision=validated.decision.value,
            source_attribution=validated.source_attribution,
            employer_name=validated.employer_name,
            normalized_employer_name=validated.normalized_employer_name,
            region_label=validated.region_label,
            normalized_region_id=validated.normalized_region_id,
            confidence=validated.confidence.value,
            freshness_status=validated.freshness_status,
            partner_payload_json=json_safe(validated.sanitized),
            evidence_json=evidence.model_dump(mode="json"),
            validation_warnings_json=[
                warning.model_dump(mode="json") for warning in validated.warnings
            ],
        )

    def _partner_import_receipt(
        self,
        *,
        import_batch_id: str,
        organization_id: str,
        user_id: str,
        source_type: PartnerImportSourceType,
        source_attribution: str | None,
        status: PartnerImportStatus,
        validation_result: PartnerImportValidationResult,
        reviewer_user_id: str | None = None,
        review_reason: str | None = None,
    ) -> PartnerImportReceipt:
        reason = "Current user is authorized for partner import operation."
        if reviewer_user_id:
            reason = "Institution review action preserved partner import boundaries."
        if review_reason:
            reason = f"{reason} Review reason recorded."
        return PartnerImportReceipt(
            import_batch_id=import_batch_id,
            organization_id=organization_id,
            uploaded_by_user_id=user_id,
            source_type=source_type,
            status=status,
            source_attribution=source_attribution or "missing_source_attribution",
            validation_result=validation_result,
            permission_decision=IntegrationPermissionDecision(
                allowed=True,
                reason=reason,
                boundary="organization_membership",
                owner_user_id=reviewer_user_id or user_id,
                organization_id=organization_id,
            ),
            limitations=PARTNER_IMPORT_LIMITATIONS,
            governance_warnings=validation_result.warnings,
        )

    def _partner_import_evidence_summary(
        self,
        *,
        organization_id: str,
    ) -> list[dict[str, Any]]:
        records = self._repo.list_accepted_partner_import_records_for_organization(
            organization_id,
            limit=50,
        )
        summary: list[dict[str, Any]] = []
        for record in records:
            warnings = [
                PartnerImportGovernanceWarning.model_validate(warning).model_dump(
                    mode="json"
                )
                for warning in record.validation_warnings_json
                if isinstance(warning, dict)
            ]
            summary.append(
                {
                    "marker": "partner_contributed_evidence",
                    "canonical_truth": False,
                    "source_type": record.source_type,
                    "source_attribution": record.source_attribution,
                    "confidence": record.confidence,
                    "freshness_status": record.freshness_status,
                    "employer_name": record.employer_name,
                    "region_label": record.region_label,
                    "governance_warnings": warnings,
                    "canonical_identity_overwrite_performed": False,
                    "canonical_region_overwrite_performed": False,
                    "product_scoring_override_performed": False,
                }
            )
        return summary

    def _prepare_product_object(
        self,
        *,
        user_id: str,
        request: ExportRequest,
    ) -> _PreparedObject:
        if request.product_object_type in INSTITUTIONAL_PRODUCT_TYPES:
            if request.organization_id is None:
                raise IntegrationAccessDenied("Institutional objects require organization scope.")
            self._require_org_action(
                organization_id=request.organization_id,
                user_id=user_id,
                product_object_type=request.product_object_type,
            )
        elif request.organization_id is not None:
            self._require_org_action(
                organization_id=request.organization_id,
                user_id=user_id,
                product_object_type=request.product_object_type,
            )

        if request.product_object_type == ProductObjectType.REGION:
            try:
                result = self._output_service.read_region(request.product_object_id)
            except MissingRegionForOutput as exc:
                raise IntegrationObjectNotFound(str(exc)) from exc
            body = result.payload.region.model_dump(mode="json")
            metadata = result.payload.metadata.model_dump(mode="json")
            return _PreparedObject(
                product_object_type=request.product_object_type,
                product_object_id=request.product_object_id,
                label=str(body.get("display_name") or request.product_object_id),
                data=sanitize_export_data(body),
                freshness_status=_freshness_status(metadata, result.metadata),
                confidence_label=_confidence_label(body),
                source_object_version=_source_object_version(result.metadata),
                limitations=_limitations_for_market_object("region"),
                governance_warnings=_governance_warnings(),
                evidence_basis=["region_output", "output_payload_metadata"],
            )

        if request.product_object_type == ProductObjectType.COMPANY:
            try:
                result = self._output_service.read_company(request.product_object_id)
            except MissingCompanyForOutput as exc:
                raise IntegrationObjectNotFound(str(exc)) from exc
            body = result.payload.company.model_dump(mode="json")
            metadata = result.payload.metadata.model_dump(mode="json")
            return _PreparedObject(
                product_object_type=request.product_object_type,
                product_object_id=request.product_object_id,
                label=str(body.get("company_name") or request.product_object_id),
                data=sanitize_export_data(body),
                freshness_status=_freshness_status(metadata, result.metadata),
                confidence_label=_confidence_label(body),
                source_object_version=_source_object_version(result.metadata),
                limitations=_limitations_for_market_object("company"),
                governance_warnings=_governance_warnings(),
                evidence_basis=["company_output", "output_payload_metadata"],
            )

        if request.product_object_type == ProductObjectType.COMPARISON:
            region_a, region_b = _comparison_ids(request)
            try:
                result = self._output_service.read_comparison(region_a, region_b)
            except (InvalidComparisonInput, MissingRegionForOutput) as exc:
                raise IntegrationObjectNotFound(str(exc)) from exc
            body = result.payload.comparison.model_dump(mode="json")
            metadata = result.payload.metadata.model_dump(mode="json")
            label = (
                f"{body.get('region_a', {}).get('display_name', region_a)} vs "
                f"{body.get('region_b', {}).get('display_name', region_b)}"
            )
            return _PreparedObject(
                product_object_type=request.product_object_type,
                product_object_id=body.get("comparison_id") or request.product_object_id,
                label=label,
                data=sanitize_export_data(body),
                freshness_status=_freshness_status(metadata, result.metadata),
                confidence_label="mixed",
                source_object_version=_source_object_version(result.metadata),
                limitations=_limitations_for_market_object("comparison"),
                governance_warnings=_governance_warnings(),
                evidence_basis=["comparison_output", "output_payload_metadata"],
            )

        if request.product_object_type == ProductObjectType.INSTITUTIONAL_REPORT:
            report = self._institutional_report(
                organization_id=request.organization_id or "",
                report_id=request.product_object_id,
            )
            partner_evidence = self._partner_import_evidence_summary(
                organization_id=request.organization_id or "",
            )
            report_data = sanitize_export_data(report.model_dump(mode="json"))
            if partner_evidence:
                report_data["partner_contributed_evidence"] = partner_evidence
            return _PreparedObject(
                product_object_type=request.product_object_type,
                product_object_id=report.report_id,
                label=report.title,
                data=report_data,
                freshness_status=str(report.data_freshness.get("freshness_status", "unknown")),
                confidence_label="aggregate",
                source_object_version=None,
                limitations=[
                    *report.limitations,
                    "Institutional exports remain aggregate-first and privacy-thresholded.",
                    "Partner import evidence is labeled and not merged into canonical truth.",
                ],
                governance_warnings=[
                    "Student-level data, searches, saved artifacts, and personal "
                    "activity are not exported.",
                    "External destinations receive prepared/manual payloads only.",
                    "Partner-contributed evidence cannot override product scoring or identity.",
                ],
                evidence_basis=[
                    "institutional_report",
                    "privacy_suppressed_aggregates",
                    *(
                        ["partner_contributed_evidence"]
                        if partner_evidence
                        else []
                    ),
                ],
            )

        if request.product_object_type == ProductObjectType.INSTITUTIONAL_DASHBOARD:
            dashboard = self._institutional_dashboard(
                organization_id=request.organization_id or "",
            )
            partner_evidence = self._partner_import_evidence_summary(
                organization_id=request.organization_id or "",
            )
            dashboard_data = sanitize_export_data(dashboard.model_dump(mode="json"))
            if partner_evidence:
                dashboard_data["partner_contributed_evidence"] = partner_evidence
            return _PreparedObject(
                product_object_type=request.product_object_type,
                product_object_id=request.organization_id or request.product_object_id,
                label=f"{dashboard.organization_name} dashboard",
                data=dashboard_data,
                freshness_status=str(dashboard.data_freshness.get("freshness_status", "unknown")),
                confidence_label="aggregate",
                source_object_version=None,
                limitations=[
                    "Institutional dashboard exports are aggregate-only and privacy-thresholded.",
                    "Suppressed cohort categories remain suppressed in exports.",
                    "Partner import evidence is labeled and not merged into canonical truth.",
                ],
                governance_warnings=[
                    "Student-level data, searches, saved artifacts, and personal "
                    "activity are not exported.",
                    "External destinations receive prepared/manual payloads only.",
                    "Partner-contributed evidence cannot override product scoring or identity.",
                ],
                evidence_basis=[
                    "institutional_dashboard",
                    "privacy_suppressed_aggregates",
                    *(
                        ["partner_contributed_evidence"]
                        if partner_evidence
                        else []
                    ),
                ],
            )

        return _PreparedObject(
            product_object_type=request.product_object_type,
            product_object_id=request.product_object_id,
            label=request.product_object_id,
            data={
                "product_object_type": request.product_object_type.value,
                "product_object_id": request.product_object_id,
                "status": "deferred",
            },
            freshness_status="unknown",
            confidence_label="unknown",
            source_object_version=None,
            limitations=["This product object export is deferred."],
            governance_warnings=_governance_warnings(),
            evidence_basis=["deferred"],
        )

    def _require_org_action(
        self,
        *,
        organization_id: str,
        user_id: str,
        product_object_type: ProductObjectType,
    ) -> tuple[Organization, Any]:
        organization = self._institution_repo.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        if organization.status != "active":
            raise InstitutionalAccessDenied(organization_id)
        action = (
            InstitutionalAction.VIEW_REPORTS
            if product_object_type == ProductObjectType.INSTITUTIONAL_REPORT
            else InstitutionalAction.VIEW_DASHBOARD
        )
        if not can_perform_institutional_action(
            self._institution_repo,
            user_id=user_id,
            organization_id=organization_id,
            action=action,
        ):
            raise InstitutionalAccessDenied(organization_id)
        membership = active_membership_for_user(
            self._institution_repo,
            user_id=user_id,
            organization_id=organization_id,
        )
        if membership is None:
            raise InstitutionalAccessDenied(organization_id)
        return organization, membership

    def _institutional_report(
        self,
        *,
        organization_id: str,
        report_id: str,
    ) -> InstitutionalReportPayload:
        row = self._institution_repo.get_report(report_id)
        if row is None or row.organization_id != organization_id:
            raise InstitutionalReportNotFound(report_id)
        return InstitutionalReportPayload.model_validate(row.payload_json)

    def _institutional_dashboard(
        self,
        *,
        organization_id: str,
    ) -> Any:
        organization = self._institution_repo.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        memberships = self._institution_repo.list_memberships_for_organization(
            organization_id
        )
        return build_institutional_dashboard(
            self._repo.session,
            organization=organization,
            student_memberships=memberships,
            minimum_group_size=5,
        )

    def _provenance(
        self,
        *,
        user_id: str,
        organization_id: str | None,
        prepared: _PreparedObject,
    ) -> IntegrationProvenance:
        return IntegrationProvenance(
            product_object_type=prepared.product_object_type,
            product_object_id=prepared.product_object_id,
            product_object_label=prepared.label,
            generated_by_user_id=user_id,
            organization_id=organization_id,
            freshness_status=prepared.freshness_status,
            confidence_label=prepared.confidence_label,
            evidence_basis=prepared.evidence_basis,
            source_object_version=prepared.source_object_version,
            limitations=prepared.limitations,
            governance_warnings=prepared.governance_warnings,
        )

    def _receipt(
        self,
        *,
        integration_id: str,
        destination: IntegrationDestination,
        capability: IntegrationCapability,
        risk_posture: IntegrationRiskPosture,
        permission: IntegrationPermissionDecision,
        provenance: IntegrationProvenance,
        status: str,
        limitations: list[str],
        governance_warnings: list[str],
    ) -> IntegrationReceipt:
        return IntegrationReceipt(
            integration_id=integration_id,
            destination=destination,
            capability=capability,
            risk_posture=risk_posture,
            status=status,
            permission_decision=permission,
            provenance=provenance,
            limitations=limitations,
            governance_warnings=governance_warnings,
        )

    def _build_export_artifact(
        self,
        *,
        export_id: str,
        export_format: ExportFormat,
        destination: IntegrationDestination,
        prepared: _PreparedObject,
        provenance: IntegrationProvenance,
    ) -> tuple[dict[str, Any], str | None, str | None, str | None]:
        if export_format == ExportFormat.CSV:
            csv_text = build_csv_export(prepared=prepared, provenance=provenance)
            filename = f"{_slug(prepared.label)}-{export_id}.csv"
            return (
                {
                    "mode": "download",
                    "filename": filename,
                    "content_type": "text/csv",
                    "external_write_performed": False,
                    "live_sync_enabled": False,
                },
                filename,
                "text/csv",
                csv_text,
            )
        if export_format == ExportFormat.PDF:
            text = build_pdf_text(prepared=prepared, provenance=provenance)
            pdf_text = build_minimal_pdf(text)
            filename = f"{_slug(prepared.label)}-{export_id}.pdf"
            return (
                {
                    "mode": "download",
                    "filename": filename,
                    "content_type": "application/pdf",
                    "limitations": prepared.limitations,
                    "governance_warnings": prepared.governance_warnings,
                    "external_write_performed": False,
                    "live_sync_enabled": False,
                },
                filename,
                "application/pdf",
                pdf_text,
            )
        if export_format in PREPARED_EXPORT_FORMATS:
            return (
                build_prepared_payload(
                    destination=destination,
                    prepared=prepared,
                    provenance=provenance,
                ),
                None,
                None,
                None,
            )
        raise ValueError(f"unsupported export format: {export_format.value}")


def partner_import_request_from_row(row: PartnerImportBatch) -> PartnerImportCreateRequest:
    return PartnerImportCreateRequest(
        organization_id=row.organization_id,
        source_type=PartnerImportSourceType(row.source_type),
        import_format=PartnerImportFormat(row.import_format),
        source_attribution=row.source_attribution,
        content=row.raw_payload_text,
        original_filename=row.original_filename,
    )


def partner_import_batch_payload_from_row(
    row: PartnerImportBatch,
    *,
    records: list[PartnerImportRecordPayload],
    preview_records: list[dict[str, Any]],
) -> PartnerImportBatchPayload:
    return PartnerImportBatchPayload(
        import_batch_id=row.partner_import_batch_id,
        organization_id=row.organization_id,
        uploaded_by_user_id=row.uploaded_by_user_id,
        source_type=PartnerImportSourceType(row.source_type),
        status=PartnerImportStatus(row.status),
        import_format=PartnerImportFormat(row.import_format),
        source_attribution=row.source_attribution,
        original_filename=row.original_filename,
        record_count=row.record_count,
        accepted_record_count=row.accepted_record_count,
        quarantined_record_count=row.quarantined_record_count,
        rejected_record_count=row.rejected_record_count,
        validation_result=PartnerImportValidationResult.model_validate(
            row.validation_result_json
        ),
        receipt=PartnerImportReceipt.model_validate(row.receipt_json),
        governance_warnings=[
            PartnerImportGovernanceWarning.model_validate(warning)
            for warning in row.governance_warnings_json
            if isinstance(warning, dict)
        ],
        records=records,
        preview_records=preview_records,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def partner_import_record_payload_from_row(
    row: PartnerImportRecord,
) -> PartnerImportRecordPayload:
    return PartnerImportRecordPayload(
        import_record_id=row.partner_import_record_id,
        import_batch_id=row.partner_import_batch_id,
        organization_id=row.organization_id,
        record_index=row.record_index,
        source_type=PartnerImportSourceType(row.source_type),
        record_status=row.record_status,
        decision=PartnerImportDecision(row.decision),
        source_attribution=row.source_attribution,
        employer_name=row.employer_name,
        region_label=row.region_label,
        confidence=PartnerDataConfidence(row.confidence),
        freshness_status=row.freshness_status,
        partner_payload=(
            deepcopy(row.partner_payload_json)
            if isinstance(row.partner_payload_json, dict)
            else {}
        ),
        evidence=PartnerContributedEvidence.model_validate(row.evidence_json),
        validation_warnings=[
            PartnerImportGovernanceWarning.model_validate(warning)
            for warning in row.validation_warnings_json
            if isinstance(warning, dict)
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def parse_partner_import_records(
    request: PartnerImportCreateRequest,
) -> list[dict[str, Any]]:
    if request.import_format == PartnerImportFormat.CSV:
        buffer = io.StringIO(request.content)
        reader = csv.DictReader(buffer)
        if not reader.fieldnames:
            raise PartnerImportValidationError("CSV import must include a header row.")
        return [dict(row) for row in reader]

    try:
        parsed = json.loads(request.content)
    except json.JSONDecodeError as exc:
        raise PartnerImportValidationError("JSON import content is invalid.") from exc
    if isinstance(parsed, list):
        records = parsed
    elif isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        records = parsed["records"]
    else:
        raise PartnerImportValidationError(
            "JSON import must be an array or an object with a records array."
        )
    if not all(isinstance(record, dict) for record in records):
        raise PartnerImportValidationError("Partner import records must be objects.")
    return [dict(record) for record in records]


def sanitize_partner_import_record(
    record: dict[str, Any],
    *,
    source_type: PartnerImportSourceType,
) -> dict[str, Any]:
    allowed = ALLOWED_PARTNER_IMPORT_FIELDS[source_type]
    cleaned: dict[str, Any] = {
        "marker": "partner_contributed_evidence",
        "canonical_truth": False,
        "source_type": source_type.value,
    }
    for key, value in record.items():
        normalized_key = _normalize_field_name(key)
        if normalized_key not in allowed:
            continue
        if _is_internal_only_import_field(normalized_key):
            continue
        if _is_pii_field(normalized_key):
            continue
        if _is_individual_outcome_field(normalized_key):
            continue
        if _is_sensitive_demographic_field(normalized_key):
            continue
        cleaned[normalized_key] = _safe_partner_value(value)
    cleaned["canonical_identity_overwrite_performed"] = False
    cleaned["canonical_region_overwrite_performed"] = False
    cleaned["product_scoring_override_performed"] = False
    return cleaned


def _preview_partner_records(
    records: list[_ValidatedPartnerRecord],
) -> list[dict[str, Any]]:
    return [
        {
            "record_index": record.record_index,
            "decision": record.decision.value,
            "record_status": (
                "accepted"
                if record.decision == PartnerImportDecision.ACCEPT
                else "quarantined"
                if record.decision == PartnerImportDecision.QUARANTINE
                else "rejected"
            ),
            "partner_payload": record.sanitized,
            "warnings": [warning.model_dump(mode="json") for warning in record.warnings],
            "partner_contributed_evidence": True,
            "canonical_truth": False,
        }
        for record in records[:10]
    ]


def export_payload_from_row(row: IntegrationExportRecord) -> ExportPayload:
    return ExportPayload(
        export_id=row.integration_export_id,
        product_object_type=ProductObjectType(row.product_object_type),
        product_object_id=row.product_object_id,
        export_format=ExportFormat(row.export_format),
        destination=IntegrationDestination(row.destination),
        capability=IntegrationCapability(row.capability),
        risk_posture=IntegrationRiskPosture(row.risk_posture),
        status=row.status,
        filename=row.filename,
        content_type=row.content_type,
        payload=deepcopy(row.payload_json) if isinstance(row.payload_json, dict) else {},
        receipt=IntegrationReceipt.model_validate(row.receipt_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def reminder_payload_from_row(row: IntegrationReminderRecord) -> ReminderPayload:
    return ReminderPayload(
        reminder_id=row.integration_reminder_id,
        reminder_type=ReminderType(row.reminder_type),
        product_object_type=ProductObjectType(row.product_object_type),
        product_object_id=row.product_object_id,
        destination=IntegrationDestination(row.destination),
        capability=IntegrationCapability(row.capability),
        risk_posture=IntegrationRiskPosture(row.risk_posture),
        status=row.status,
        title=row.title,
        due_at=row.due_at,
        timezone=row.timezone,
        receipt=IntegrationReceipt.model_validate(row.receipt_json),
        ics_filename=f"{row.integration_reminder_id}.ics",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def api_client_payload_from_row(
    row: ApiClient,
    *,
    keys: list[SafeApiKeyDisplay],
) -> ApiClientPayload:
    return ApiClientPayload(
        api_client_id=row.api_client_id,
        display_name=row.display_name,
        created_by_user_id=row.created_by_user_id,
        organization_id=row.organization_id,
        status=ApiClientStatus(row.status),
        policy=ApiAccessPolicy(
            scopes=[ApiScope(scope) for scope in row.scopes_json],
            organization_id=row.organization_id,
            rate_limit_count=row.rate_limit_count,
            rate_limit_window_seconds=row.rate_limit_window_seconds,
            allowed_origins=[
                str(origin)
                for origin in row.allowed_origins_json
                if isinstance(origin, str) and origin.strip()
            ],
        ),
        keys=keys,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def safe_api_key_display_from_row(
    row: ApiKey,
    *,
    reveal_raw_key: str | None,
) -> SafeApiKeyDisplay:
    return SafeApiKeyDisplay(
        api_key_id=row.api_key_id,
        key_prefix=row.key_prefix,
        display_key=row.display_key,
        raw_key=reveal_raw_key,
        revealed_once=reveal_raw_key is not None,
    )


def api_usage_payload_from_row(row: ApiUsageRecord) -> ApiUsagePayload:
    return ApiUsagePayload(
        usage_record_id=row.api_usage_record_id,
        api_client_id=row.api_client_id,
        api_key_id=row.api_key_id,
        route=row.route,
        method=row.method,
        scope=row.scope,
        decision=row.decision,
        status_code=row.status_code,
        rate_limit_limit=row.rate_limit_limit,
        rate_limit_remaining=row.rate_limit_remaining,
        rate_limit_reset_at=row.rate_limit_reset_at,
        occurred_at=row.occurred_at,
    )


def career_platform_reference_from_row(
    row: CareerPlatformReferenceRecord,
) -> CareerPlatformReference:
    return CareerPlatformReference(
        reference_id=row.career_platform_reference_id,
        platform=CareerPlatform(row.platform),
        risk_posture=CareerPlatformRiskPosture(row.risk_posture),
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        url=row.url,
        label=row.label,
        organization_id=row.organization_id,
        submitted_by_user_id=row.submitted_by_user_id,
        manual_only=row.manual_only,
        created_at=row.created_at,
    )


def career_platform_export_from_row(row: CareerPlatformExportRecord) -> CareerPlatformExport:
    return CareerPlatformExport(
        career_platform_export_id=row.career_platform_export_id,
        platform=CareerPlatform(row.platform),
        risk_posture=CareerPlatformRiskPosture(row.risk_posture),
        export_mode=row.export_mode,
        rows=deepcopy(row.rows_json) if isinstance(row.rows_json, list) else [],
        manual_only=row.manual_only,
        automation_performed=row.automation_performed,
        ats_state_created=row.ats_state_created,
        application_status_created=row.application_status_created,
        recruiter_outreach_created=row.recruiter_outreach_created,
        created_at=row.created_at,
    )


def sanitize_export_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in INTERNAL_ONLY_EXPORT_KEYS:
                continue
            if any(part in normalized for part in INTERNAL_ONLY_KEY_PARTS):
                continue
            cleaned[str(key)] = sanitize_export_data(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_export_data(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_export_data(item) for item in value]
    return json_safe(value)


def build_csv_export(
    *,
    prepared: _PreparedObject,
    provenance: IntegrationProvenance,
) -> str:
    rows = [
        ("provenance", "product_object_type", provenance.product_object_type.value),
        ("provenance", "product_object_id", provenance.product_object_id),
        ("provenance", "product_object_label", provenance.product_object_label or ""),
        ("provenance", "generated_at", provenance.generated_at.isoformat()),
        ("provenance", "generated_by_user_id", provenance.generated_by_user_id),
        ("provenance", "organization_id", provenance.organization_id or ""),
        ("freshness", "freshness_status", provenance.freshness_status),
        (
            "freshness",
            "freshness_as_of",
            provenance.freshness_as_of.isoformat()
            if provenance.freshness_as_of is not None
            else "",
        ),
        ("confidence", "confidence_label", provenance.confidence_label),
        ("governance", "external_write_performed", "false"),
        ("governance", "live_sync_enabled", "false"),
        ("governance", "product_authority_retained", "true"),
    ]
    for item in provenance.limitations:
        rows.append(("limitation", "notice", item))
    for item in provenance.governance_warnings:
        rows.append(("governance_warning", "notice", item))
    for key, value in _flatten(prepared.data).items():
        rows.append(("data", key, _csv_value(value)))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "field", "value"])
    writer.writerows(rows)
    return buffer.getvalue()


def build_pdf_text(
    *,
    prepared: _PreparedObject,
    provenance: IntegrationProvenance,
) -> str:
    lines = [
        "Job Market Intelligence Export",
        f"Object: {provenance.product_object_type.value} {provenance.product_object_id}",
        f"Label: {provenance.product_object_label or provenance.product_object_id}",
        f"Generated: {provenance.generated_at.isoformat()}",
        f"Freshness: {provenance.freshness_status}",
        f"Confidence: {provenance.confidence_label}",
        "",
        "Limitations and governance warnings",
    ]
    lines.extend(f"- {item}" for item in provenance.limitations)
    lines.extend(f"- {item}" for item in provenance.governance_warnings)
    lines.extend(
        [
            "- No OAuth, live sync, two-way sync, or external write was performed.",
            "- External destinations do not define product data semantics.",
            "",
            "Prepared data",
        ]
    )
    for key, value in list(_flatten(prepared.data).items())[:80]:
        lines.append(f"{key}: {_csv_value(value)}")
    return "\n".join(lines)


def build_prepared_payload(
    *,
    destination: IntegrationDestination,
    prepared: _PreparedObject,
    provenance: IntegrationProvenance,
) -> dict[str, Any]:
    rows = [
        {"field": key, "value": _csv_value(value)}
        for key, value in _flatten(prepared.data).items()
    ]
    base = {
        "mode": "prepared_manual_payload",
        "destination": destination.value,
        "operation": "manual_copy_only",
        "sync_mode": "none",
        "external_write_performed": False,
        "live_sync_enabled": False,
        "two_way_sync_enabled": False,
        "oauth_required": False,
        "destination_defines_product_semantics": False,
        "product_authority_retained": True,
        "provenance": provenance.model_dump(mode="json"),
        "limitations": prepared.limitations,
        "governance_warnings": prepared.governance_warnings,
        "rows": rows,
    }
    if destination == IntegrationDestination.GOOGLE_SHEETS:
        return {
            **base,
            "prepared_google_sheets_payload": {
                "sheet_title": prepared.label,
                "columns": ["field", "value"],
                "rows": rows,
            },
        }
    if destination == IntegrationDestination.NOTION:
        return {
            **base,
            "prepared_notion_payload": {
                "page_title": prepared.label,
                "properties": [
                    {"name": "Field", "type": "title"},
                    {"name": "Value", "type": "rich_text"},
                ],
                "rows": rows,
            },
        }
    return {
        **base,
        "prepared_airtable_payload": {
            "base_hint": "Job Market Intelligence exports",
            "table_name": prepared.product_object_type.value,
            "fields": ["field", "value"],
            "records": rows,
        },
    }


def build_ics_content(
    *,
    reminder_id: str,
    request: ReminderRequest,
    provenance: IntegrationProvenance,
) -> str:
    start = _ensure_aware_utc(request.due_at)
    end = start + timedelta(minutes=request.duration_minutes)
    description_parts = [
        request.description or "",
        f"Product object: {provenance.product_object_type.value}:{provenance.product_object_id}",
        f"Product label: {provenance.product_object_label or provenance.product_object_id}",
        f"Freshness: {provenance.freshness_status}",
        f"Confidence: {provenance.confidence_label}",
        "Created by Job Market Intelligence as an ICS file only.",
        "No external calendar write, live sync, two-way sync, OAuth, or ATS "
        "application status was created.",
    ]
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Job Market Intelligence//Layer 17A//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{reminder_id}@job-market-intelligence",
            f"DTSTAMP:{_ics_dt(datetime.now(UTC))}",
            f"DTSTART:{_ics_dt(start)}",
            f"DTEND:{_ics_dt(end)}",
            f"SUMMARY:{_ics_escape(request.title)}",
            f"DESCRIPTION:{_ics_escape(' '.join(part for part in description_parts if part))}",
            f"CATEGORIES:{_ics_escape(request.reminder_type.value)}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def build_minimal_pdf(text: str) -> str:
    escaped_lines = [_pdf_escape(line) for line in text.splitlines()]
    y = 760
    stream_lines = ["BT", "/F1 10 Tf"]
    for line in escaped_lines[:95]:
        stream_lines.append(f"72 {y} Td ({line}) Tj")
        y = -12
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('utf-8'))} >> stream\n{stream}\nendstream endobj",
    ]
    output = ["%PDF-1.4"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part.encode("utf-8")) + 1 for part in output))
        output.append(obj)
    xref_pos = sum(len(part.encode("utf-8")) + 1 for part in output)
    output.append("xref")
    output.append(f"0 {len(objects) + 1}")
    output.append("0000000000 65535 f ")
    output.extend(f"{offset:010d} 00000 n " for offset in offsets[1:])
    output.append("trailer << /Size 6 /Root 1 0 R >>")
    output.append(f"startxref\n{xref_pos}")
    output.append("%%EOF")
    return "\n".join(output)


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        normalized[_normalize_field_name(key)] = value.strip() if isinstance(value, str) else value
    return normalized


def _normalize_field_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")


def _safe_partner_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            _normalize_field_name(key): _safe_partner_value(item)
            for key, item in value.items()
            if not _is_internal_only_import_field(_normalize_field_name(key))
        }
    if isinstance(value, list):
        return [_safe_partner_value(item) for item in value]
    return value


def _duplicate_employer_names(records: list[dict[str, Any]]) -> set[str]:
    names = [
        _normalize_name(_normalize_record(record).get("employer_name"))
        for record in records
    ]
    counts = Counter(name for name in names if name)
    return {name for name, count in counts.items() if count > 1}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _normalize_name(value: Any) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", cleaned.casefold()).strip()
    normalized = re.sub(r"\b(inc|llc|ltd|corp|corporation|company|co)\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _record_source_attribution(
    record: dict[str, Any],
    batch_source_attribution: str | None,
) -> str | None:
    return _clean_optional(record.get("source_attribution")) or _clean_optional(
        batch_source_attribution
    )


def _warning(
    code: str,
    severity: str,
    message: str,
    record_index: int,
    field: str | None,
    action: PartnerImportDecision,
) -> PartnerImportGovernanceWarning:
    return PartnerImportGovernanceWarning(
        code=code,
        severity=severity,
        message=message,
        record_index=record_index,
        field=field,
        action=action,
    )


def _decision_for_warnings(
    warnings: list[PartnerImportGovernanceWarning],
) -> PartnerImportDecision:
    if any(warning.action == PartnerImportDecision.QUARANTINE for warning in warnings):
        return PartnerImportDecision.QUARANTINE
    if any(warning.action == PartnerImportDecision.REJECT for warning in warnings):
        return PartnerImportDecision.REJECT
    return PartnerImportDecision.ACCEPT


def _confidence_for_decision(
    decision: PartnerImportDecision,
    warnings: list[PartnerImportGovernanceWarning],
) -> PartnerDataConfidence:
    if decision == PartnerImportDecision.QUARANTINE:
        return PartnerDataConfidence.BLOCKED
    if decision == PartnerImportDecision.REJECT:
        return PartnerDataConfidence.UNVERIFIED
    if any(warning.severity in {"warning", "blocking"} for warning in warnings):
        return PartnerDataConfidence.LOW
    return PartnerDataConfidence.MEDIUM


def _freshness_for_record(record: dict[str, Any]) -> str:
    if _stale_date_field(record) is not None:
        return "stale"
    if any(_present(record.get(field)) for field in ("observed_at", "as_of_date")):
        return "partner_reported"
    return "unknown"


def _validation_status(
    *,
    record_count: int,
    accepted_count: int,
    quarantined_count: int,
    rejected_count: int,
    warnings: list[PartnerImportGovernanceWarning],
) -> PartnerImportStatus:
    if record_count == 0:
        return PartnerImportStatus.REJECTED
    if quarantined_count == record_count:
        return PartnerImportStatus.QUARANTINED
    if accepted_count == 0:
        return PartnerImportStatus.REJECTED
    if warnings or quarantined_count or rejected_count:
        return PartnerImportStatus.NEEDS_REVIEW
    return PartnerImportStatus.VALIDATED


def _is_internal_only_import_field(normalized_key: str) -> bool:
    if normalized_key in INTERNAL_ONLY_EXPORT_KEYS:
        return True
    return any(part in normalized_key for part in INTERNAL_ONLY_KEY_PARTS)


def _is_pii_field(normalized_key: str) -> bool:
    return any(part in normalized_key for part in PII_FIELD_PARTS)


def _is_individual_outcome_field(normalized_key: str) -> bool:
    return any(part in normalized_key for part in INDIVIDUAL_OUTCOME_FIELD_PARTS)


def _is_sensitive_demographic_field(normalized_key: str) -> bool:
    return any(part in normalized_key for part in SENSITIVE_DEMOGRAPHIC_FIELD_PARTS)


def _record_has_ats_status_semantics(record: dict[str, Any]) -> bool:
    for key, value in record.items():
        normalized_key = _normalize_field_name(key)
        if "application" not in normalized_key and "status" not in normalized_key:
            continue
        normalized_value = str(value).casefold().strip()
        if normalized_value in ATS_STATUS_VALUES:
            return True
    return False


def _stale_date_field(record: dict[str, Any]) -> str | None:
    for field in ("observed_at", "as_of_date", "date", "collected_at"):
        raw_value = _clean_optional(record.get(field))
        if raw_value is None:
            continue
        observed = _parse_partner_date(raw_value)
        if observed is None:
            continue
        if datetime.now(UTC) - observed > timedelta(days=730):
            return field
    year = _clean_optional(record.get("graduation_year"))
    if year and year.isdigit() and datetime.now(UTC).year - int(year) > 5:
        return "graduation_year"
    return None


def _parse_partner_date(value: str) -> datetime | None:
    cleaned = value.strip()
    if cleaned.isdigit() and len(cleaned) == 4:
        return datetime(int(cleaned), 1, 1, tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _comparison_ids(request: ExportRequest) -> tuple[str, str]:
    region_ids = request.source_context.get("region_ids")
    if (
        isinstance(region_ids, list)
        and len(region_ids) == 2
        and all(isinstance(item, str) and item.strip() for item in region_ids)
    ):
        return region_ids[0].strip(), region_ids[1].strip()
    parts = [part for part in re.split(r"__|:|,", request.product_object_id) if part]
    if len(parts) >= 2:
        return parts[0], parts[1]
    raise IntegrationObjectNotFound("Comparison exports require two region ids.")


def _flatten(value: Any, *, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(item, prefix=next_prefix))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            next_prefix = f"{prefix}.{index}" if prefix else str(index)
            result.update(_flatten(item, prefix=next_prefix))
        return result
    return {prefix: value}


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return str(json_safe(value))
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _freshness_status(metadata: dict[str, Any], row: Any) -> str:
    if isinstance(metadata.get("state"), str) and metadata["state"]:
        return metadata["state"]
    freshness = metadata.get("freshness")
    if isinstance(freshness, dict) and isinstance(freshness.get("freshness_status"), str):
        return freshness["freshness_status"]
    state = getattr(row, "state", None)
    return state if isinstance(state, str) and state else "unknown"


def _confidence_label(body: dict[str, Any]) -> str:
    if isinstance(body.get("classification_confidence"), str):
        return str(body["classification_confidence"])
    coverage = body.get("coverage")
    if isinstance(coverage, dict):
        if isinstance(coverage.get("label"), str):
            return str(coverage["label"])
        quality = coverage.get("quality_score")
        if isinstance(quality, (int, float)):
            if quality >= 75:
                return "strong"
            if quality >= 40:
                return "partial"
    return "unknown"


def _coverage_tier(body: dict[str, Any]) -> str:
    coverage_tier = body.get("coverage_tier")
    if isinstance(coverage_tier, str) and coverage_tier:
        return coverage_tier
    coverage = body.get("coverage")
    if isinstance(coverage, dict):
        for key in ("tier", "coverage_tier", "label"):
            value = coverage.get(key)
            if isinstance(value, str) and value:
                return value
        quality = coverage.get("quality_score")
        if isinstance(quality, (int, float)):
            if quality >= 75:
                return "strong"
            if quality >= 40:
                return "partial"
    return "unknown"


def _source_object_version(row: Any) -> str | None:
    version = getattr(row, "version", None)
    if isinstance(version, int):
        return f"v{version}"
    return None


def _limitations_for_market_object(kind: str) -> list[str]:
    return [
        f"{kind.capitalize()} exports are snapshots of app-owned product output.",
        "Missing values remain unknown and are not converted to zero.",
        "Exports do not perform live sync or external writes.",
    ]


def _governance_warnings() -> list[str]:
    return [
        "External destinations must not be treated as product authority.",
        "Internal-only scoring/source fields are withheld from export payloads.",
    ]


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ics_dt(value: datetime) -> str:
    return _ensure_aware_utc(value).strftime("%Y%m%dT%H%M%SZ")


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _pdf_escape(value: str) -> str:
    safe = value.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _generate_api_key() -> str:
    return f"jmi_live_{secrets.token_urlsafe(32)}"


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _display_api_key(raw_key: str) -> str:
    return f"{raw_key[:12]}...{raw_key[-6:]}"


def _career_platform_label(platform: CareerPlatform, subject_id: str) -> str:
    return f"{CAREER_PLATFORM_REGISTRY[platform]['display_name']} reference for {subject_id}"


def _career_platform_row(
    platform: CareerPlatform,
    company_id: str | None,
    employer_name: str,
) -> dict[str, Any]:
    encoded = quote_plus(employer_name)
    if platform == CareerPlatform.LINKEDIN:
        url = f"https://www.linkedin.com/search/results/companies/?keywords={encoded}"
        action = "manual_company_search"
    elif platform == CareerPlatform.HANDSHAKE:
        url = f"https://app.joinhandshake.com/stu/postings?query={encoded}"
        action = "manual_employer_lookup"
    else:
        url = f"https://www.google.com/search?q={encoded}+careers"
        action = "manual_public_search"
    return {
        "company_id": company_id,
        "employer_name": employer_name,
        "platform": platform.value,
        "manual_search_url": url,
        "manual_action": action,
        "manual_only": True,
        "automation_performed": False,
        "ats_state_created": False,
        "application_status_created": False,
        "resume_submission_created": False,
        "recruiter_outreach_created": False,
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:80] or "integration-export"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"
