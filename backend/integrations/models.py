"""Persistence models for Layer 17 prepared integrations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IntegrationTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class IntegrationExportRecord(Base, IntegrationTimestampMixin):
    """User-owned prepared export artifact.

    The stored payload may be a local downloadable file body or a prepared
    manual-copy payload for an external tool. It never represents a live sync
    cursor or external destination authority.
    """

    __tablename__ = "integration_exports"
    __table_args__ = (
        CheckConstraint(
            "destination IN ('csv', 'pdf', 'google_sheets', 'notion', 'airtable')",
            name="ck_integration_exports_destination",
        ),
        CheckConstraint(
            "capability IN ('export_file', 'prepared_payload')",
            name="ck_integration_exports_capability",
        ),
        CheckConstraint(
            "risk_posture IN ("
            "'local_download_only', "
            "'prepared_no_sync', "
            "'unsupported_deferred'"
            ")",
            name="ck_integration_exports_risk_posture",
        ),
        CheckConstraint(
            "export_format IN ("
            "'csv', "
            "'pdf', "
            "'prepared_google_sheets', "
            "'prepared_notion', "
            "'prepared_airtable'"
            ")",
            name="ck_integration_exports_format",
        ),
        CheckConstraint(
            "product_object_type IN ("
            "'region', "
            "'company', "
            "'comparison', "
            "'recommendation_strategy', "
            "'institutional_dashboard', "
            "'institutional_report'"
            ")",
            name="ck_integration_exports_product_object_type",
        ),
        CheckConstraint(
            "status IN ('created', 'blocked', 'deferred')",
            name="ck_integration_exports_status",
        ),
        Index("ix_integration_exports_owner", "owner_user_id"),
        Index("ix_integration_exports_org", "organization_id"),
        Index("ix_integration_exports_object", "product_object_type", "product_object_id"),
        Index("ix_integration_exports_created_at", "created_at"),
    )

    integration_export_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    product_object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    export_format: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    receipt_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)


class IntegrationReminderRecord(Base, IntegrationTimestampMixin):
    """User-owned reminder with downloadable ICS content only."""

    __tablename__ = "integration_reminders"
    __table_args__ = (
        CheckConstraint(
            "destination IN ('ics_calendar')",
            name="ck_integration_reminders_destination",
        ),
        CheckConstraint(
            "capability IN ('calendar_file')",
            name="ck_integration_reminders_capability",
        ),
        CheckConstraint(
            "risk_posture IN ('calendar_file_no_sync', 'unsupported_deferred')",
            name="ck_integration_reminders_risk_posture",
        ),
        CheckConstraint(
            "reminder_type IN ("
            "'application_window', "
            "'internship_deadline', "
            "'follow_up', "
            "'market_refresh_alert', "
            "'institutional_report_review', "
            "'data_request_due'"
            ")",
            name="ck_integration_reminders_type",
        ),
        CheckConstraint(
            "product_object_type IN ("
            "'region', "
            "'company', "
            "'comparison', "
            "'recommendation_strategy', "
            "'institutional_dashboard', "
            "'institutional_report'"
            ")",
            name="ck_integration_reminders_product_object_type",
        ),
        CheckConstraint(
            "status IN ('created', 'blocked', 'deferred')",
            name="ck_integration_reminders_status",
        ),
        Index("ix_integration_reminders_owner", "owner_user_id"),
        Index("ix_integration_reminders_org", "organization_id"),
        Index("ix_integration_reminders_type", "reminder_type"),
        Index("ix_integration_reminders_due_at", "due_at"),
        Index("ix_integration_reminders_object", "product_object_type", "product_object_id"),
    )

    integration_reminder_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    product_object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(64), nullable=False)
    destination: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    ics_content: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    receipt_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)


class PartnerImportBatch(Base, IntegrationTimestampMixin):
    """Institution-scoped partner import batch.

    Partner import batches preserve uploaded data as contributed evidence. They
    do not represent canonical company identity, region intelligence, scoring
    inputs, CRM records, or applicant/application state.
    """

    __tablename__ = "partner_import_batches"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ("
            "'local_employer_list', "
            "'internship_partner_list', "
            "'regional_workforce_data', "
            "'aggregated_career_center_outcome_data'"
            ")",
            name="ck_partner_import_batches_source_type",
        ),
        CheckConstraint(
            "status IN ("
            "'uploaded', "
            "'validated', "
            "'needs_review', "
            "'accepted', "
            "'partially_accepted', "
            "'rejected', "
            "'archived', "
            "'quarantined'"
            ")",
            name="ck_partner_import_batches_status",
        ),
        CheckConstraint(
            "import_format IN ('csv', 'json')",
            name="ck_partner_import_batches_format",
        ),
        Index("ix_partner_import_batches_org", "organization_id"),
        Index("ix_partner_import_batches_uploader", "uploaded_by_user_id"),
        Index("ix_partner_import_batches_status", "status"),
        Index("ix_partner_import_batches_source_type", "source_type"),
        Index("ix_partner_import_batches_created_at", "created_at"),
    )

    partner_import_batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    import_format: Mapped[str] = mapped_column(String(16), nullable=False)
    source_attribution: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload_text: Mapped[str] = mapped_column(Text, nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    accepted_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    quarantined_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rejected_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    validation_result_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    receipt_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    governance_warnings_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)


class PartnerImportRecord(Base, IntegrationTimestampMixin):
    """Sanitized partner-contributed evidence row scoped to one institution."""

    __tablename__ = "partner_import_records"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ("
            "'local_employer_list', "
            "'internship_partner_list', "
            "'regional_workforce_data', "
            "'aggregated_career_center_outcome_data'"
            ")",
            name="ck_partner_import_records_source_type",
        ),
        CheckConstraint(
            "record_status IN ("
            "'accepted', "
            "'needs_review', "
            "'rejected', "
            "'quarantined', "
            "'archived'"
            ")",
            name="ck_partner_import_records_status",
        ),
        CheckConstraint(
            "decision IN ('accept', 'needs_review', 'reject', 'quarantine')",
            name="ck_partner_import_records_decision",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown', 'unverified', 'blocked')",
            name="ck_partner_import_records_confidence",
        ),
        Index("ix_partner_import_records_batch", "partner_import_batch_id"),
        Index("ix_partner_import_records_org", "organization_id"),
        Index("ix_partner_import_records_status", "record_status"),
        Index("ix_partner_import_records_employer", "normalized_employer_name"),
        Index("ix_partner_import_records_region", "normalized_region_id"),
    )

    partner_import_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    partner_import_batch_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("partner_import_batches.partner_import_batch_id"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    record_index: Mapped[int] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(String(96), nullable=False)
    record_status: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    source_attribution: Mapped[str] = mapped_column(String(512), nullable=False)
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_employer_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    region_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_region_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(64), nullable=False)
    partner_payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    validation_warnings_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)


class ApiClient(Base, IntegrationTimestampMixin):
    """Controlled external API client with scoped read/access policy."""

    __tablename__ = "api_clients"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_api_clients_status",
        ),
        Index("ix_api_clients_created_by", "created_by_user_id"),
        Index("ix_api_clients_org", "organization_id"),
        Index("ix_api_clients_status", "status"),
    )

    api_client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    allowed_origins_json: Mapped[list] = mapped_column(JSON, nullable=False)
    rate_limit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    rate_limit_window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
    )


class ApiKey(Base, IntegrationTimestampMixin):
    """Hashed external API key. Raw secret is never persisted."""

    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_api_keys_status",
        ),
        Index("ix_api_keys_client", "api_client_id"),
        Index("ix_api_keys_hash", "key_hash"),
        Index("ix_api_keys_prefix", "key_prefix"),
        Index("ix_api_keys_status", "status"),
    )

    api_key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_client_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("api_clients.api_client_id"),
        nullable=False,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    display_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ApiUsageRecord(Base):
    """Append-style usage and rate-limit record for external API requests."""

    __tablename__ = "api_usage_records"
    __table_args__ = (
        CheckConstraint(
            "decision IN ("
            "'allowed', "
            "'missing_scope', "
            "'invalid_key', "
            "'revoked_key', "
            "'rate_limited'"
            ")",
            name="ck_api_usage_records_decision",
        ),
        Index("ix_api_usage_records_client", "api_client_id"),
        Index("ix_api_usage_records_key", "api_key_id"),
        Index("ix_api_usage_records_occurred_at", "occurred_at"),
        Index("ix_api_usage_records_scope", "scope"),
    )

    api_usage_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_client_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("api_clients.api_client_id"),
        nullable=True,
    )
    api_key_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("api_keys.api_key_id"),
        nullable=True,
    )
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(96), nullable=True)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_limit_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class ApiAccessAuditEvent(Base):
    """Governance audit event for external API access decisions."""

    __tablename__ = "api_access_audit_events"
    __table_args__ = (
        Index("ix_api_access_audit_events_client", "api_client_id"),
        Index("ix_api_access_audit_events_occurred_at", "occurred_at"),
        Index("ix_api_access_audit_events_decision", "decision"),
    )

    api_access_audit_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_client_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("api_clients.api_client_id"),
        nullable=True,
    )
    api_key_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("api_keys.api_key_id"),
        nullable=True,
    )
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(96), nullable=True)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    event_metadata: Mapped[dict | list | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class CareerPlatformReferenceRecord(Base, IntegrationTimestampMixin):
    """Manual public URL/reference for a career platform destination."""

    __tablename__ = "career_platform_references"
    __table_args__ = (
        CheckConstraint(
            "platform IN ("
            "'linkedin', "
            "'handshake', "
            "'university_job_board', "
            "'company_career_page', "
            "'other_public_career_site'"
            ")",
            name="ck_career_platform_references_platform",
        ),
        CheckConstraint(
            "risk_posture IN ("
            "'safe_manual', "
            "'export_only', "
            "'deep_link_only', "
            "'official_api_only', "
            "'requires_review', "
            "'blocked_hostile_tos', "
            "'deferred'"
            ")",
            name="ck_career_platform_references_risk_posture",
        ),
        Index("ix_career_platform_references_platform", "platform"),
        Index("ix_career_platform_references_subject", "subject_type", "subject_id"),
        Index("ix_career_platform_references_org", "organization_id"),
        Index("ix_career_platform_references_user", "submitted_by_user_id"),
    )

    career_platform_reference_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    submitted_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    manual_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    automation_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    ats_state_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CareerPlatformExportRecord(Base, IntegrationTimestampMixin):
    """Manual/export-only career platform artifact."""

    __tablename__ = "career_platform_exports"
    __table_args__ = (
        CheckConstraint(
            "platform IN ("
            "'linkedin', "
            "'handshake', "
            "'university_job_board', "
            "'company_career_page', "
            "'other_public_career_site'"
            ")",
            name="ck_career_platform_exports_platform",
        ),
        CheckConstraint(
            "risk_posture IN ("
            "'safe_manual', "
            "'export_only', "
            "'deep_link_only', "
            "'official_api_only', "
            "'requires_review', "
            "'blocked_hostile_tos', "
            "'deferred'"
            ")",
            name="ck_career_platform_exports_risk_posture",
        ),
        Index("ix_career_platform_exports_user", "created_by_user_id"),
        Index("ix_career_platform_exports_org", "organization_id"),
        Index("ix_career_platform_exports_platform", "platform"),
    )

    career_platform_export_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    export_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    rows_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    receipt_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    manual_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    automation_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    ats_state_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    application_status_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    recruiter_outreach_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
