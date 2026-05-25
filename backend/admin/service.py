"""Admin event log service."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.admin.models import AdminEventLog
from backend.admin.repository import AdminEventLogRepository
from backend.admin.roles import AdminRole


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AdminEventLogInput(BaseModel):
    """Payload required to append one admin event log record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor: str = Field(min_length=1, max_length=128)
    role: AdminRole | None = None
    action: str = Field(min_length=1, max_length=128)
    object_type: str = Field(min_length=1, max_length=64)
    object_id: str = Field(min_length=1, max_length=128)
    before_state: dict[str, Any] | list[Any] | None = None
    after_state: dict[str, Any] | list[Any] | None = None
    reason: str = Field(min_length=1, max_length=2048)
    request_id: str | None = Field(default=None, max_length=128)

    @field_validator("actor", "action", "object_type", "object_id", "reason")
    @classmethod
    def _required_strings_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("request_id")
    @classmethod
    def _optional_strings_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank when provided")
        return stripped


class AdminEventLogService:
    """Append and read admin event log records.

    The service exposes no update or delete operation; historical records are
    immutable at the ORM model boundary as well.
    """

    def __init__(
        self,
        repository: AdminEventLogRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repository
        self._now = clock or _utc_now

    def record_event(self, event: AdminEventLogInput) -> AdminEventLog:
        timestamp = self._now()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        row = AdminEventLog(
            admin_event_id=_new_admin_event_id(),
            actor=event.actor,
            actor_role=event.role.value if event.role is not None else None,
            action=event.action,
            object_type=event.object_type,
            object_id=event.object_id,
            before_state=deepcopy(event.before_state),
            after_state=deepcopy(event.after_state),
            reason=event.reason,
            request_id=event.request_id,
            timestamp=timestamp,
        )
        self._repo.add(row)
        self._repo.flush()
        return row

    def list_events(self, *, limit: int = 100) -> list[AdminEventLog]:
        return self._repo.list(limit=limit)


def _new_admin_event_id() -> str:
    return f"admin_event_{uuid4().hex[:52]}"
