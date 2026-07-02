"""Opt-in, user-scoped career-agent progress memory."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.career_agent.models import (
    CareerMemoryEntryRecord,
    CareerMemoryPermissionRecord,
)
from backend.career_agent.schemas import (
    CareerMemoryAuditEvent,
    CareerMemoryCategory,
    CareerMemoryDeleteRequest,
    CareerMemoryEntry,
    CareerMemoryPermission,
    CareerMemoryProfile,
    CareerMemoryUpdateRequest,
    CareerMemoryVisibility,
)


class CareerMemoryPermissionError(ValueError):
    """Raised when a memory update lacks explicit category permission."""


class CareerMemoryService:
    """Persist and read private, category-scoped career memory."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_profile(
        self,
        user_id: str,
        *,
        audit_events: tuple[CareerMemoryAuditEvent, ...] = (),
    ) -> CareerMemoryProfile:
        permission_rows = self._permission_rows(user_id)
        permissions_by_category = {
            CareerMemoryCategory(row.category): _permission_from_row(row)
            for row in permission_rows
        }
        permissions = tuple(
            permissions_by_category.get(
                category,
                CareerMemoryPermission(category=category),
            )
            for category in CareerMemoryCategory
        )
        enabled_categories = {
            permission.category
            for permission in permissions
            if permission.enabled
        }
        entries = tuple(
            _entry_from_row(row)
            for row in self._entry_rows(user_id)
            if CareerMemoryCategory(row.category) in enabled_categories
        )
        grouped = {
            category.value: tuple(
                entry for entry in entries if entry.category is category
            )
            for category in CareerMemoryCategory
        }
        return CareerMemoryProfile(
            user_id=user_id,
            memory_enabled=any(permission.enabled for permission in permissions),
            permissions=permissions,
            entries=entries,
            entries_by_category=grouped,
            audit_events=audit_events,
        )

    def update_memory(
        self,
        user_id: str,
        request: CareerMemoryUpdateRequest,
    ) -> CareerMemoryProfile:
        now = datetime.now(UTC)
        audit_events: list[CareerMemoryAuditEvent] = []

        if _requires_explicit_permission(request) and not request.explicit_user_permission:
            raise CareerMemoryPermissionError(
                "Career memory cannot be saved or enabled without explicit user permission."
            )

        effective_permissions = {
            CareerMemoryCategory(row.category): _permission_from_row(row)
            for row in self._permission_rows(user_id)
        }

        for permission in request.permissions:
            row = self._get_permission_row(user_id, permission.category)
            if row is None:
                row = CareerMemoryPermissionRecord(
                    career_memory_permission_id=_permission_id(
                        user_id,
                        permission.category,
                    ),
                    user_id=user_id,
                    category=permission.category.value,
                    enabled=permission.enabled,
                    personalize_allowed=permission.personalize_allowed,
                    visibility=permission.visibility.value,
                )
                self._session.add(row)
            else:
                row.enabled = permission.enabled
                row.personalize_allowed = (
                    permission.personalize_allowed if permission.enabled else False
                )
                row.visibility = permission.visibility.value
            effective_permissions[permission.category] = CareerMemoryPermission(
                category=permission.category,
                enabled=row.enabled,
                personalize_allowed=row.personalize_allowed,
                visibility=CareerMemoryVisibility.PRIVATE,
            )
            if not row.enabled:
                self._delete_entries_for_category(user_id, permission.category)
            audit_events.append(
                _audit(
                    "permission_updated",
                    now=now,
                    category=permission.category,
                    summary=(
                        f"Career memory permission updated for {permission.category.value}."
                    ),
                )
            )

        for category in request.replace_categories:
            self._delete_entries_for_category(user_id, category)

        for entry in request.entries:
            permission = effective_permissions.get(entry.category)
            if permission is None or not permission.enabled:
                raise CareerMemoryPermissionError(
                    f"Career memory category {entry.category.value} is not enabled."
                )
            row = self._get_entry_row(user_id, entry.category, entry.value)
            if row is None:
                row = CareerMemoryEntryRecord(
                    career_memory_entry_id=_entry_id(
                        user_id,
                        entry.category,
                        entry.value,
                    ),
                    user_id=user_id,
                    category=entry.category.value,
                    value=entry.value,
                    label=entry.label,
                    notes=entry.notes,
                    visibility=CareerMemoryVisibility.PRIVATE.value,
                    source="user_provided",
                )
                self._session.add(row)
            else:
                row.label = entry.label
                row.notes = entry.notes
                row.visibility = CareerMemoryVisibility.PRIVATE.value
                row.source = "user_provided"
            audit_events.append(
                _audit(
                    "entry_saved",
                    now=now,
                    category=entry.category,
                    memory_entry_id=row.career_memory_entry_id,
                    summary=f"Career memory entry saved for {entry.category.value}.",
                )
            )

        self._session.flush()
        return self.get_profile(user_id, audit_events=tuple(audit_events))

    def delete_memory(
        self,
        user_id: str,
        request: CareerMemoryDeleteRequest,
    ) -> CareerMemoryProfile:
        now = datetime.now(UTC)
        audit_events: list[CareerMemoryAuditEvent] = []
        if request.clear_all:
            deleted_entries = self._session.execute(
                delete(CareerMemoryEntryRecord).where(
                    CareerMemoryEntryRecord.user_id == user_id
                )
            ).rowcount or 0
            self._session.execute(
                delete(CareerMemoryPermissionRecord).where(
                    CareerMemoryPermissionRecord.user_id == user_id
                )
            )
            audit_events.append(
                _audit(
                    "memory_cleared",
                    now=now,
                    summary=f"Cleared {deleted_entries} career memory entries.",
                )
            )
            self._session.flush()
            return self.get_profile(user_id, audit_events=tuple(audit_events))

        for category in request.categories:
            deleted = self._delete_entries_for_category(user_id, category)
            if request.disable_permissions:
                permission = self._get_permission_row(user_id, category)
                if permission is not None:
                    permission.enabled = False
                    permission.personalize_allowed = False
            audit_events.append(
                _audit(
                    "entry_deleted",
                    now=now,
                    category=category,
                    summary=f"Deleted {deleted} career memory entries for {category.value}.",
                )
            )

        for memory_entry_id in request.memory_entry_ids:
            row = self._session.execute(
                select(CareerMemoryEntryRecord).where(
                    CareerMemoryEntryRecord.user_id == user_id,
                    CareerMemoryEntryRecord.career_memory_entry_id == memory_entry_id,
                )
            ).scalar_one_or_none()
            if row is None:
                continue
            category = CareerMemoryCategory(row.category)
            self._session.delete(row)
            audit_events.append(
                _audit(
                    "entry_deleted",
                    now=now,
                    category=category,
                    memory_entry_id=memory_entry_id,
                    summary=f"Deleted career memory entry for {category.value}.",
                )
            )
        self._session.flush()
        return self.get_profile(user_id, audit_events=tuple(audit_events))

    def personalizable_values(
        self,
        profile: CareerMemoryProfile,
        category: CareerMemoryCategory,
    ) -> tuple[str, ...]:
        permission = next(
            (
                item
                for item in profile.permissions
                if item.category is category
            ),
            None,
        )
        if permission is None or not permission.enabled or not permission.personalize_allowed:
            return ()
        return tuple(
            entry.value
            for entry in profile.entries
            if entry.category is category and entry.counts_as_evidence is False
        )

    def _permission_rows(self, user_id: str) -> tuple[CareerMemoryPermissionRecord, ...]:
        rows = self._session.execute(
            select(CareerMemoryPermissionRecord)
            .where(CareerMemoryPermissionRecord.user_id == user_id)
            .order_by(CareerMemoryPermissionRecord.category)
        ).scalars()
        return tuple(rows)

    def _entry_rows(self, user_id: str) -> tuple[CareerMemoryEntryRecord, ...]:
        rows = self._session.execute(
            select(CareerMemoryEntryRecord)
            .where(CareerMemoryEntryRecord.user_id == user_id)
            .order_by(CareerMemoryEntryRecord.category, CareerMemoryEntryRecord.value)
        ).scalars()
        return tuple(rows)

    def _get_permission_row(
        self,
        user_id: str,
        category: CareerMemoryCategory,
    ) -> CareerMemoryPermissionRecord | None:
        return self._session.execute(
            select(CareerMemoryPermissionRecord).where(
                CareerMemoryPermissionRecord.user_id == user_id,
                CareerMemoryPermissionRecord.category == category.value,
            )
        ).scalar_one_or_none()

    def _get_entry_row(
        self,
        user_id: str,
        category: CareerMemoryCategory,
        value: str,
    ) -> CareerMemoryEntryRecord | None:
        return self._session.execute(
            select(CareerMemoryEntryRecord).where(
                CareerMemoryEntryRecord.user_id == user_id,
                CareerMemoryEntryRecord.category == category.value,
                CareerMemoryEntryRecord.value == value,
            )
        ).scalar_one_or_none()

    def _delete_entries_for_category(
        self,
        user_id: str,
        category: CareerMemoryCategory,
    ) -> int:
        result = self._session.execute(
            delete(CareerMemoryEntryRecord).where(
                CareerMemoryEntryRecord.user_id == user_id,
                CareerMemoryEntryRecord.category == category.value,
            )
        )
        return result.rowcount or 0


def _requires_explicit_permission(request: CareerMemoryUpdateRequest) -> bool:
    if request.entries:
        return True
    return any(
        permission.enabled or permission.personalize_allowed
        for permission in request.permissions
    )


def _permission_from_row(row: CareerMemoryPermissionRecord) -> CareerMemoryPermission:
    return CareerMemoryPermission(
        category=CareerMemoryCategory(row.category),
        enabled=row.enabled,
        personalize_allowed=row.personalize_allowed,
        visibility=CareerMemoryVisibility.PRIVATE,
    )


def _entry_from_row(row: CareerMemoryEntryRecord) -> CareerMemoryEntry:
    return CareerMemoryEntry(
        memory_entry_id=row.career_memory_entry_id,
        category=CareerMemoryCategory(row.category),
        value=row.value,
        label=row.label,
        notes=row.notes,
        visibility=CareerMemoryVisibility.PRIVATE,
        source="user_provided",
        counts_as_evidence=False,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit(
    event_type: str,
    *,
    now: datetime,
    summary: str,
    category: CareerMemoryCategory | None = None,
    memory_entry_id: str | None = None,
) -> CareerMemoryAuditEvent:
    return CareerMemoryAuditEvent(
        event_type=event_type,  # type: ignore[arg-type]
        category=category,
        memory_entry_id=memory_entry_id,
        occurred_at=now,
        summary=summary,
    )


def _permission_id(user_id: str, category: CareerMemoryCategory) -> str:
    suffix = uuid5(NAMESPACE_URL, f"{user_id}:permission:{category.value}").hex[:24]
    return f"career_mem_perm_{suffix}"


def _entry_id(user_id: str, category: CareerMemoryCategory, value: str) -> str:
    normalized = value.strip().casefold()
    suffix = uuid5(
        NAMESPACE_URL,
        f"{user_id}:entry:{category.value}:{normalized}",
    ).hex[:22]
    return f"career_mem_entry_{suffix}"


def entries_for_category(
    profile: CareerMemoryProfile | None,
    category: CareerMemoryCategory,
) -> tuple[CareerMemoryEntry, ...]:
    if profile is None:
        return ()
    permission = next(
        (item for item in profile.permissions if item.category is category),
        None,
    )
    if permission is None or not permission.enabled or not permission.personalize_allowed:
        return ()
    return tuple(entry for entry in profile.entries if entry.category is category)


def values_for_category(
    profile: CareerMemoryProfile | None,
    category: CareerMemoryCategory,
) -> tuple[str, ...]:
    return tuple(entry.value for entry in entries_for_category(profile, category))
