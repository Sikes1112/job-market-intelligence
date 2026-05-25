"""Thin data-access layer for admin event log rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog


class AdminEventLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: AdminEventLog) -> None:
        self._session.add(row)

    def get(self, admin_event_id: str) -> AdminEventLog | None:
        return self._session.get(AdminEventLog, admin_event_id)

    def list(self, *, limit: int = 100) -> list[AdminEventLog]:
        rows = self._session.execute(
            select(AdminEventLog)
            .order_by(AdminEventLog.timestamp.desc(), AdminEventLog.admin_event_id.desc())
            .limit(limit)
        ).scalars()
        return list(rows)

    def flush(self) -> None:
        self._session.flush()

