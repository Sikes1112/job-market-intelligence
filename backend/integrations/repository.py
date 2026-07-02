"""Repository helpers for Layer 17 integration records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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


class IntegrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add_export(self, row: IntegrationExportRecord) -> None:
        self._session.add(row)

    def get_export(self, export_id: str) -> IntegrationExportRecord | None:
        return self._session.get(IntegrationExportRecord, export_id)

    def list_exports_for_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
    ) -> list[IntegrationExportRecord]:
        rows = self._session.execute(
            select(IntegrationExportRecord)
            .where(IntegrationExportRecord.owner_user_id == user_id)
            .order_by(
                IntegrationExportRecord.created_at.desc(),
                IntegrationExportRecord.integration_export_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_reminder(self, row: IntegrationReminderRecord) -> None:
        self._session.add(row)

    def get_reminder(self, reminder_id: str) -> IntegrationReminderRecord | None:
        return self._session.get(IntegrationReminderRecord, reminder_id)

    def list_reminders_for_user(
        self,
        user_id: str,
        *,
        limit: int = 100,
    ) -> list[IntegrationReminderRecord]:
        rows = self._session.execute(
            select(IntegrationReminderRecord)
            .where(IntegrationReminderRecord.owner_user_id == user_id)
            .order_by(
                IntegrationReminderRecord.due_at.asc(),
                IntegrationReminderRecord.integration_reminder_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_partner_import_batch(self, row: PartnerImportBatch) -> None:
        self._session.add(row)

    def get_partner_import_batch(
        self,
        import_batch_id: str,
    ) -> PartnerImportBatch | None:
        return self._session.get(PartnerImportBatch, import_batch_id)

    def list_partner_import_batches_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = 100,
    ) -> list[PartnerImportBatch]:
        rows = self._session.execute(
            select(PartnerImportBatch)
            .where(PartnerImportBatch.organization_id == organization_id)
            .order_by(
                PartnerImportBatch.created_at.desc(),
                PartnerImportBatch.partner_import_batch_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_partner_import_record(self, row: PartnerImportRecord) -> None:
        self._session.add(row)

    def list_partner_import_records(
        self,
        import_batch_id: str,
    ) -> list[PartnerImportRecord]:
        rows = self._session.execute(
            select(PartnerImportRecord)
            .where(PartnerImportRecord.partner_import_batch_id == import_batch_id)
            .order_by(
                PartnerImportRecord.record_index.asc(),
                PartnerImportRecord.partner_import_record_id.asc(),
            )
        ).scalars()
        return list(rows)

    def list_accepted_partner_import_records_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = 100,
    ) -> list[PartnerImportRecord]:
        rows = self._session.execute(
            select(PartnerImportRecord)
            .where(
                PartnerImportRecord.organization_id == organization_id,
                PartnerImportRecord.record_status == "accepted",
            )
            .order_by(
                PartnerImportRecord.created_at.desc(),
                PartnerImportRecord.partner_import_record_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def delete_partner_import_records(self, import_batch_id: str) -> None:
        self._session.execute(
            delete(PartnerImportRecord).where(
                PartnerImportRecord.partner_import_batch_id == import_batch_id
            )
        )

    def add_api_client(self, row: ApiClient) -> None:
        self._session.add(row)

    def get_api_client(self, api_client_id: str) -> ApiClient | None:
        return self._session.get(ApiClient, api_client_id)

    def list_api_clients(self, *, limit: int = 100) -> list[ApiClient]:
        rows = self._session.execute(
            select(ApiClient)
            .order_by(ApiClient.created_at.desc(), ApiClient.api_client_id.desc())
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_api_key(self, row: ApiKey) -> None:
        self._session.add(row)

    def get_api_key(self, api_key_id: str) -> ApiKey | None:
        return self._session.get(ApiKey, api_key_id)

    def get_api_key_by_hash(self, key_hash: str) -> ApiKey | None:
        return self._session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        ).scalar_one_or_none()

    def list_api_keys_for_client(self, api_client_id: str) -> list[ApiKey]:
        rows = self._session.execute(
            select(ApiKey)
            .where(ApiKey.api_client_id == api_client_id)
            .order_by(ApiKey.created_at.desc(), ApiKey.api_key_id.desc())
        ).scalars()
        return list(rows)

    def add_api_usage_record(self, row: ApiUsageRecord) -> None:
        self._session.add(row)

    def count_allowed_api_usage_since(
        self,
        *,
        api_client_id: str,
        since: datetime,
    ) -> int:
        count = self._session.execute(
            select(func.count())
            .select_from(ApiUsageRecord)
            .where(
                ApiUsageRecord.api_client_id == api_client_id,
                ApiUsageRecord.decision == "allowed",
                ApiUsageRecord.occurred_at >= since,
            )
        ).scalar_one()
        return int(count)

    def list_api_usage_for_client(
        self,
        api_client_id: str,
        *,
        limit: int = 100,
    ) -> list[ApiUsageRecord]:
        rows = self._session.execute(
            select(ApiUsageRecord)
            .where(ApiUsageRecord.api_client_id == api_client_id)
            .order_by(
                ApiUsageRecord.occurred_at.desc(),
                ApiUsageRecord.api_usage_record_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_api_access_audit_event(self, row: ApiAccessAuditEvent) -> None:
        self._session.add(row)

    def add_career_platform_reference(
        self,
        row: CareerPlatformReferenceRecord,
    ) -> None:
        self._session.add(row)

    def list_career_platform_references(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        organization_id: str | None = None,
        limit: int = 100,
    ) -> list[CareerPlatformReferenceRecord]:
        stmt = select(CareerPlatformReferenceRecord)
        if subject_type is not None:
            stmt = stmt.where(CareerPlatformReferenceRecord.subject_type == subject_type)
        if subject_id is not None:
            stmt = stmt.where(CareerPlatformReferenceRecord.subject_id == subject_id)
        if organization_id is not None:
            stmt = stmt.where(CareerPlatformReferenceRecord.organization_id == organization_id)
        rows = self._session.execute(
            stmt.order_by(
                CareerPlatformReferenceRecord.created_at.desc(),
                CareerPlatformReferenceRecord.career_platform_reference_id.desc(),
            ).limit(limit)
        ).scalars()
        return list(rows)

    def add_career_platform_export(self, row: CareerPlatformExportRecord) -> None:
        self._session.add(row)

    def get_career_platform_export(
        self,
        career_platform_export_id: str,
    ) -> CareerPlatformExportRecord | None:
        return self._session.get(CareerPlatformExportRecord, career_platform_export_id)

    def flush(self) -> None:
        self._session.flush()
