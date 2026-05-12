from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


class Job(Base):
    """Orchestration job record.

    Slice 2 only declares the schema. The job envelope (request/response,
    status enums, dedupe key derivation, retry policy, downstream trigger
    recommendations) lands in Slice 4. Queue dispatch and worker execution
    land in Slice 14.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_job_type", "job_type"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_queue_name", "queue_name"),
        Index("ix_jobs_dedupe_key", "dedupe_key"),
        Index(
            "uq_jobs_active_dedupe_key",
            "dedupe_key",
            unique=True,
            sqlite_where=text(
                "dedupe_key IS NOT NULL AND status IN ('queued', 'running')"
            ),
            postgresql_where=text(
                "dedupe_key IS NOT NULL AND status IN ('queued', 'running')"
            ),
        ),
        Index("ix_jobs_priority", "priority"),
    )

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    queue_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")

    trigger_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dependency_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    input_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
