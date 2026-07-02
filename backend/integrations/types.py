"""Shared vocabulary for Layer 17 integrations.

This module intentionally defines app-owned integration semantics. External
destinations receive prepared data or downloadable files; they never define
product object meaning, mutate canonical market facts, or become a sync source
of truth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntegrationDestination(StrEnum):
    CSV = "csv"
    PDF = "pdf"
    GOOGLE_SHEETS = "google_sheets"
    NOTION = "notion"
    AIRTABLE = "airtable"
    ICS_CALENDAR = "ics_calendar"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class IntegrationCapability(StrEnum):
    EXPORT_FILE = "export_file"
    PREPARED_PAYLOAD = "prepared_payload"
    CALENDAR_FILE = "calendar_file"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class IntegrationRiskPosture(StrEnum):
    LOCAL_DOWNLOAD_ONLY = "local_download_only"
    PREPARED_NO_SYNC = "prepared_no_sync"
    CALENDAR_FILE_NO_SYNC = "calendar_file_no_sync"
    UNSUPPORTED_DEFERRED = "unsupported_deferred"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ExportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"
    PREPARED_GOOGLE_SHEETS = "prepared_google_sheets"
    PREPARED_NOTION = "prepared_notion"
    PREPARED_AIRTABLE = "prepared_airtable"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ProductObjectType(StrEnum):
    REGION = "region"
    COMPANY = "company"
    COMPARISON = "comparison"
    RECOMMENDATION_STRATEGY = "recommendation_strategy"
    INSTITUTIONAL_DASHBOARD = "institutional_dashboard"
    INSTITUTIONAL_REPORT = "institutional_report"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ReminderType(StrEnum):
    APPLICATION_WINDOW = "application_window"
    INTERNSHIP_DEADLINE = "internship_deadline"
    FOLLOW_UP = "follow_up"
    MARKET_REFRESH_ALERT = "market_refresh_alert"
    INSTITUTIONAL_REPORT_REVIEW = "institutional_report_review"
    DATA_REQUEST_DUE = "data_request_due"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerImportSourceType(StrEnum):
    LOCAL_EMPLOYER_LIST = "local_employer_list"
    INTERNSHIP_PARTNER_LIST = "internship_partner_list"
    REGIONAL_WORKFORCE_DATA = "regional_workforce_data"
    AGGREGATED_CAREER_CENTER_OUTCOME_DATA = (
        "aggregated_career_center_outcome_data"
    )

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerImportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerImportStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerImportDecision(StrEnum):
    ACCEPT = "accept"
    NEEDS_REVIEW = "needs_review"
    REJECT = "reject"
    QUARANTINE = "quarantine"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerDataConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PartnerImportGovernanceWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    severity: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=512)
    record_index: int | None = Field(default=None, ge=0)
    field: str | None = Field(default=None, max_length=128)
    action: PartnerImportDecision = PartnerImportDecision.NEEDS_REVIEW


class PartnerImportValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: PartnerImportStatus
    record_count: int = Field(ge=0)
    accepted_record_count: int = Field(ge=0)
    quarantined_record_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    warnings: list[PartnerImportGovernanceWarning] = Field(default_factory=list)
    required_fields_missing: list[str] = Field(default_factory=list)
    unsupported_fields: list[str] = Field(default_factory=list)
    has_blocking_privacy_issue: bool = False
    has_blocking_source_issue: bool = False
    can_accept: bool = False

    @field_validator("required_fields_missing", "unsupported_fields")
    @classmethod
    def _unique_strings(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in seen:
                cleaned.append(stripped)
                seen.add(stripped)
        return cleaned


class PartnerContributedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partner_contributed: bool = True
    canonical_truth: bool = False
    import_batch_id: str = Field(min_length=1, max_length=64)
    import_record_id: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(min_length=1, max_length=64)
    source_type: PartnerImportSourceType
    source_attribution: str = Field(min_length=1, max_length=512)
    confidence: PartnerDataConfidence
    freshness_status: str = Field(min_length=1, max_length=64)
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    governance_warnings: list[PartnerImportGovernanceWarning] = Field(
        default_factory=list
    )
    canonical_identity_overwrite_performed: bool = False
    canonical_region_overwrite_performed: bool = False
    product_scoring_override_performed: bool = False

    @model_validator(mode="after")
    def _evidence_boundaries_hold(self) -> PartnerContributedEvidence:
        if not self.partner_contributed or self.canonical_truth:
            raise ValueError("Partner import records must remain contributed evidence.")
        if self.canonical_identity_overwrite_performed:
            raise ValueError("Partner imports must not overwrite canonical company identity.")
        if self.canonical_region_overwrite_performed:
            raise ValueError("Partner imports must not overwrite canonical region intelligence.")
        if self.product_scoring_override_performed:
            raise ValueError("Partner imports must not override product scoring.")
        return self


class PartnerImportReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_batch_id: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(min_length=1, max_length=64)
    uploaded_by_user_id: str = Field(min_length=1, max_length=64)
    source_type: PartnerImportSourceType
    status: PartnerImportStatus
    source_attribution: str = Field(min_length=1, max_length=512)
    validation_result: PartnerImportValidationResult
    permission_decision: IntegrationPermissionDecision
    partner_contributed_evidence: bool = True
    canonical_truth: bool = False
    canonical_identity_overwrite_performed: bool = False
    canonical_region_overwrite_performed: bool = False
    product_scoring_override_performed: bool = False
    governance_warnings_removed: bool = False
    student_level_pii_imported: bool = False
    individual_outcome_records_imported: bool = False
    sensitive_demographics_imported: bool = False
    internal_only_fields_exposed: bool = False
    limitations: list[str] = Field(default_factory=list, max_length=24)
    governance_warnings: list[PartnerImportGovernanceWarning] = Field(
        default_factory=list
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _receipt_boundaries_hold(self) -> PartnerImportReceipt:
        if not self.partner_contributed_evidence or self.canonical_truth:
            raise ValueError("Accepted import data must remain partner-contributed evidence.")
        if self.canonical_identity_overwrite_performed:
            raise ValueError("Partner imports must not overwrite canonical company identity.")
        if self.canonical_region_overwrite_performed:
            raise ValueError("Partner imports must not overwrite canonical region intelligence.")
        if self.product_scoring_override_performed:
            raise ValueError("Partner imports must not override product scoring.")
        if self.governance_warnings_removed:
            raise ValueError("Partner imports must not remove governance warnings.")
        if self.student_level_pii_imported:
            raise ValueError("Student-level PII must not be imported.")
        if self.individual_outcome_records_imported:
            raise ValueError("Individual outcome records must not be imported.")
        if self.sensitive_demographics_imported:
            raise ValueError("Sensitive demographics must not be imported.")
        if self.internal_only_fields_exposed:
            raise ValueError("Internal-only fields must not be exposed in import receipts.")
        return self


class ApiScope(StrEnum):
    REGION_READ = "region:read"
    COMPANY_GEOGRAPHY_READ = "company_geography:read"
    MARKET_SIGNAL_READ = "market_signal:read"
    INSTITUTION_DASHBOARD_READ = "institution_dashboard:read"
    EXPORTS_CREATE = "exports:create"
    IMPORTS_CREATE = "imports:create"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ApiClientStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ApiAccessPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scopes: list[ApiScope] = Field(default_factory=list)
    organization_id: str | None = Field(default=None, max_length=64)
    rate_limit_count: int = Field(default=60, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    allowed_origins: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("scopes")
    @classmethod
    def _unique_scopes(cls, value: list[ApiScope]) -> list[ApiScope]:
        seen: set[ApiScope] = set()
        cleaned: list[ApiScope] = []
        for item in value:
            if item not in seen:
                cleaned.append(item)
                seen.add(item)
        return cleaned

    @model_validator(mode="after")
    def _forbidden_scopes_absent(self) -> ApiAccessPolicy:
        forbidden_parts = (
            "job_application",
            "applicant",
            "candidate",
            "student_profile",
            "resume",
            "recruiter",
            "ats",
            "pipeline",
            "crm",
        )
        for scope in self.scopes:
            if any(part in scope.value for part in forbidden_parts):
                raise ValueError("Forbidden ATS/applicant/resume/recruiter scopes are not allowed")
        return self


class ApiRateLimitDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    limit: int = Field(ge=1)
    remaining: int = Field(ge=0)
    reset_at: datetime
    window_seconds: int = Field(ge=1)
    reason: str


class ApiAccessAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_client_id: str = Field(min_length=1, max_length=64)
    api_key_id: str | None = Field(default=None, max_length=64)
    scope: ApiScope | None = None
    route: str = Field(min_length=1, max_length=255)
    decision: str = Field(min_length=1, max_length=64)
    status_code: int = Field(ge=100, le=599)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApiResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    coverage_tier: str | None = Field(default=None, max_length=64)
    freshness_status: str | None = Field(default=None, max_length=64)
    confidence: str | None = Field(default=None, max_length=64)
    source_governance: list[str] = Field(default_factory=list, max_length=24)
    governance_warnings: list[str] = Field(default_factory=list, max_length=24)
    partner_contributed_evidence: list[dict[str, Any]] = Field(default_factory=list)
    rate_limit: ApiRateLimitDecision


class ApiResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data: Any
    meta: ApiResponseMeta


class SafeApiKeyDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key_id: str = Field(min_length=1, max_length=64)
    key_prefix: str = Field(min_length=1, max_length=16)
    display_key: str = Field(min_length=1, max_length=64)
    raw_key: str | None = None
    revealed_once: bool = False


class CareerPlatform(StrEnum):
    LINKEDIN = "linkedin"
    HANDSHAKE = "handshake"
    UNIVERSITY_JOB_BOARD = "university_job_board"
    COMPANY_CAREER_PAGE = "company_career_page"
    OTHER_PUBLIC_CAREER_SITE = "other_public_career_site"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class CareerPlatformRiskPosture(StrEnum):
    SAFE_MANUAL = "safe_manual"
    EXPORT_ONLY = "export_only"
    DEEP_LINK_ONLY = "deep_link_only"
    OFFICIAL_API_ONLY = "official_api_only"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED_HOSTILE_TOS = "blocked_hostile_tos"
    DEFERRED = "deferred"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ExternalCareerLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=255)
    platform: CareerPlatform
    risk_posture: CareerPlatformRiskPosture
    manual_only: bool = True
    automation_performed: bool = False
    ats_state_created: bool = False

    @model_validator(mode="after")
    def _manual_boundaries_hold(self) -> ExternalCareerLink:
        if self.automation_performed:
            raise ValueError("Career platform links must not perform automation")
        if self.ats_state_created:
            raise ValueError("Career platform links must not create ATS state")
        return self


class CareerPlatformReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str = Field(min_length=1, max_length=64)
    platform: CareerPlatform
    risk_posture: CareerPlatformRiskPosture
    subject_type: str = Field(min_length=1, max_length=64)
    subject_id: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=255)
    organization_id: str | None = Field(default=None, max_length=64)
    submitted_by_user_id: str = Field(min_length=1, max_length=64)
    manual_only: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CareerPlatformExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_platform_export_id: str = Field(min_length=1, max_length=64)
    platform: CareerPlatform
    risk_posture: CareerPlatformRiskPosture
    export_mode: str = Field(min_length=1, max_length=64)
    rows: list[dict[str, Any]]
    manual_only: bool = True
    automation_performed: bool = False
    ats_state_created: bool = False
    application_status_created: bool = False
    recruiter_outreach_created: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _export_boundaries_hold(self) -> CareerPlatformExport:
        if self.automation_performed:
            raise ValueError("Career platform exports must not automate external platforms")
        if self.ats_state_created or self.application_status_created:
            raise ValueError("Career platform exports must not create application status")
        if self.recruiter_outreach_created:
            raise ValueError("Career platform exports must not create recruiter outreach")
        return self


class IntegrationPermissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason: str = Field(min_length=1, max_length=512)
    boundary: str = Field(min_length=1, max_length=128)
    owner_user_id: str | None = Field(default=None, max_length=64)
    organization_id: str | None = Field(default=None, max_length=64)


class IntegrationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_object_type: ProductObjectType
    product_object_id: str = Field(min_length=1, max_length=255)
    product_object_label: str | None = Field(default=None, max_length=255)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    generated_by_user_id: str = Field(min_length=1, max_length=64)
    organization_id: str | None = Field(default=None, max_length=64)
    freshness_status: str = Field(default="unknown", max_length=64)
    freshness_as_of: datetime | None = None
    confidence_label: str = Field(default="unknown", max_length=64)
    evidence_basis: list[str] = Field(default_factory=list, max_length=24)
    source_object_version: str | None = Field(default=None, max_length=128)
    limitations: list[str] = Field(default_factory=list, max_length=24)
    governance_warnings: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("evidence_basis", "limitations", "governance_warnings")
    @classmethod
    def _strings_clean(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class IntegrationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    integration_id: str = Field(min_length=1, max_length=64)
    destination: IntegrationDestination
    capability: IntegrationCapability
    risk_posture: IntegrationRiskPosture
    status: str = Field(min_length=1, max_length=64)
    permission_decision: IntegrationPermissionDecision
    provenance: IntegrationProvenance
    external_write_performed: bool = False
    live_sync_enabled: bool = False
    oauth_performed: bool = False
    two_way_sync_enabled: bool = False
    product_authority_retained: bool = True
    limitations: list[str] = Field(default_factory=list, max_length=24)
    governance_warnings: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def _integration_boundaries_hold(self) -> IntegrationReceipt:
        if self.external_write_performed:
            raise ValueError("Layer 17A integrations must not perform external writes")
        if self.live_sync_enabled or self.two_way_sync_enabled:
            raise ValueError("Layer 17A integrations must not enable live or two-way sync")
        if self.oauth_performed:
            raise ValueError("Layer 17A integrations must not perform OAuth")
        if not self.product_authority_retained:
            raise ValueError("Product authority must remain with Job Market Intelligence")
        return self


def destination_for_format(export_format: ExportFormat) -> IntegrationDestination:
    if export_format == ExportFormat.CSV:
        return IntegrationDestination.CSV
    if export_format == ExportFormat.PDF:
        return IntegrationDestination.PDF
    if export_format == ExportFormat.PREPARED_GOOGLE_SHEETS:
        return IntegrationDestination.GOOGLE_SHEETS
    if export_format == ExportFormat.PREPARED_NOTION:
        return IntegrationDestination.NOTION
    return IntegrationDestination.AIRTABLE


def capability_for_destination(
    destination: IntegrationDestination,
) -> IntegrationCapability:
    if destination in {IntegrationDestination.CSV, IntegrationDestination.PDF}:
        return IntegrationCapability.EXPORT_FILE
    if destination == IntegrationDestination.ICS_CALENDAR:
        return IntegrationCapability.CALENDAR_FILE
    return IntegrationCapability.PREPARED_PAYLOAD


def risk_posture_for_destination(
    destination: IntegrationDestination,
) -> IntegrationRiskPosture:
    if destination in {IntegrationDestination.CSV, IntegrationDestination.PDF}:
        return IntegrationRiskPosture.LOCAL_DOWNLOAD_ONLY
    if destination == IntegrationDestination.ICS_CALENDAR:
        return IntegrationRiskPosture.CALENDAR_FILE_NO_SYNC
    return IntegrationRiskPosture.PREPARED_NO_SYNC


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value
