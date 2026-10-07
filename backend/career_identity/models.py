"""Career Identity persistence models.

Career Identity is user-owned app data. It references the canonical internal
``users.user_id`` and does not replace account/auth identity or market truth.
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
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base

CAREER_IDENTITY_FACT_TYPE_SQL = (
    "'education', "
    "'experience', "
    "'skill', "
    "'project', "
    "'credential', "
    "'career_goal', "
    "'role_preference', "
    "'industry_preference', "
    "'geographic_constraint', "
    "'compensation_constraint', "
    "'timing_preference', "
    "'work_arrangement_preference'"
)

CAREER_IDENTITY_FACT_STATE_SQL = (
    "'explicit', 'imported', 'inferred', 'confirmed'"
)

CAREER_IDENTITY_IMPORT_STATUS_SQL = "'completed', 'failed'"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CareerIdentity(Base):
    """Canonical user-owned Career Identity aggregate root."""

    __tablename__ = "career_identities"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_career_identities_user_id"),
        CheckConstraint("current_version >= 1", name="ck_career_identities_version"),
        CheckConstraint(
            "completeness_state IN ('empty', 'minimal', 'partial', 'complete')",
            name="ck_career_identities_completeness_state",
        ),
        CheckConstraint(
            "sufficiency_state IN ('insufficient', 'sufficient')",
            name="ck_career_identities_sufficiency_state",
        ),
        CheckConstraint(
            "privacy_visibility = 'private'",
            name="ck_career_identities_private_visibility",
        ),
        Index("ix_career_identities_user_id", "user_id"),
    )

    career_identity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completeness_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="empty"
    )
    sufficiency_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="insufficient"
    )
    completeness_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ingestion_consent_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    inference_consent_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    downstream_personalization_consent_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    retain_import_metadata: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    privacy_visibility: Mapped[str] = mapped_column(
        String(32), nullable=False, default="private"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerIdentityImport(Base):
    """Safe import metadata for resume/profile ingestion.

    Raw imported text or uploaded document content is deliberately not stored
    here; only checksums, shape metadata, status, and normalized diagnostics.
    """

    __tablename__ = "career_identity_imports"
    __table_args__ = (
        CheckConstraint(
            f"import_status IN ({CAREER_IDENTITY_IMPORT_STATUS_SQL})",
            name="ck_career_identity_imports_status",
        ),
        UniqueConstraint(
            "career_identity_id",
            "content_hash",
            name="uq_career_identity_imports_identity_hash",
        ),
        Index("ix_career_identity_imports_identity", "career_identity_id"),
        Index("ix_career_identity_imports_user_id", "user_id"),
        Index("ix_career_identity_imports_hash", "content_hash"),
    )

    career_identity_import_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    career_identity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("career_identities.career_identity_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    import_status: Mapped[str] = mapped_column(String(32), nullable=False)
    diagnostics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    imported_fact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerIdentityFact(Base):
    """One normalized career fact within the user's Career Identity aggregate."""

    __tablename__ = "career_identity_facts"
    __table_args__ = (
        CheckConstraint(
            f"fact_type IN ({CAREER_IDENTITY_FACT_TYPE_SQL})",
            name="ck_career_identity_facts_type",
        ),
        CheckConstraint(
            f"state IN ({CAREER_IDENTITY_FACT_STATE_SQL})",
            name="ck_career_identity_facts_state",
        ),
        CheckConstraint(
            "normalized_key <> ''",
            name="ck_career_identity_facts_normalized_key",
        ),
        UniqueConstraint(
            "career_identity_id",
            "fact_type",
            "normalized_key",
            name="uq_career_identity_facts_identity_type_key",
        ),
        Index("ix_career_identity_facts_identity", "career_identity_id"),
        Index("ix_career_identity_facts_user_id", "user_id"),
        Index("ix_career_identity_facts_type", "fact_type"),
        Index("ix_career_identity_facts_user_type", "user_id", "fact_type"),
    )

    career_identity_fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    career_identity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("career_identities.career_identity_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_import_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("career_identity_imports.career_identity_import_id"),
        nullable=True,
    )
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
