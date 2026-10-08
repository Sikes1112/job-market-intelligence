"""Operator workflow metadata for planned region expansion.

Rows here are workflow/checklist state only. They do not create canonical
regions, ingest market data, or publish outputs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


class RegionExpansionWorkflow(Base):
    __tablename__ = "region_expansion_workflows"
    __table_args__ = (
        CheckConstraint(
            "workflow_state IN ("
            "'candidate', "
            "'intake_started', "
            "'normalized', "
            "'provenance_attached', "
            "'review_ready', "
            "'approved', "
            "'published', "
            "'refresh_enabled'"
            ")",
            name="ck_region_expansion_workflows_state",
        ),
        CheckConstraint(
            "region_data_mode IN ('seed_demo', 'candidate', 'real_refreshable')",
            name="ck_region_expansion_workflows_data_mode",
        ),
        UniqueConstraint("region_key", name="uq_region_expansion_workflows_region_key"),
        Index("ix_region_expansion_workflows_state", "workflow_state"),
        Index("ix_region_expansion_workflows_data_mode", "region_data_mode"),
    )

    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_region_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=True
    )
    workflow_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
    )
    region_data_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
    )
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refresh_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_contract_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance_contract_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    admin_review_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_refresh_contract_ref: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    checklist_notes: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    region_identity_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_coverage_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    company_region_presence_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    hiring_signal_support_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    entry_level_signal_support_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    scoring_readiness_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    freshness_readiness_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    provenance_attached_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    admin_approval_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    output_refresh_readiness_check: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
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
