"""Event payload model for Slice 15.

Source: ``EVENT_TRIGGER_MAP.md`` §10 (minimal event payload schema).

Events are *structured inputs*, not database tables. Slice 15 keeps them in
memory only — the docs require persistence for the orchestration job table
(Slice 2) and the output_metadata table (Slice 11) but **not** for the event
stream itself. If a later slice introduces an event log, that will be a
separate addition.

The model enforces the cross-cutting envelope rules (timezone-aware
``emitted_at``, non-empty source / event_id, valid :class:`EventType`).
Per-event-type scope validation lives in the router so it can use the same
helpers the rules module uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.orchestration.events.types import EventType
from backend.orchestration.jobs.types import Priority


class Event(BaseModel):
    """Structured envelope for a system event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_type: EventType
    emitted_at: datetime
    source: str = Field(min_length=1)
    scope: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    correlation_id: str | None = None
    # ``no_meaningful_change`` mirrors ``ErrorCode.NO_MEANINGFUL_CHANGE`` from
    # the job spec. When set to True the router suppresses downstream work
    # (``EVENT_TRIGGER_MAP.md`` §8 — Trigger Suppression Rules).
    no_meaningful_change: bool = False

    @field_validator("emitted_at")
    @classmethod
    def _emitted_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")
        return value

    @field_validator("correlation_id")
    @classmethod
    def _correlation_id_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("correlation_id, if provided, must be non-blank")
        return value
