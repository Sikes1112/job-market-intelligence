from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.shared.db import Base, CanonicalMixin

if TYPE_CHECKING:
    pass


class Region(Base, CanonicalMixin):
    """Canonical geography object.

    region_type is one of: city | metro | greater_region | state | custom_region.
    Stored as plain string here; transition/value enforcement is out of scope
    for Slice 2.
    """

    __tablename__ = "regions"
    __table_args__ = (
        CheckConstraint(
            "market_support_status IN ('supported', 'unsupported', 'unknown')",
            name="ck_regions_market_support_status",
        ),
        CheckConstraint(
            "centroid_latitude IS NULL OR "
            "(centroid_latitude >= -90 AND centroid_latitude <= 90)",
            name="ck_regions_centroid_latitude",
        ),
        CheckConstraint(
            "centroid_longitude IS NULL OR "
            "(centroid_longitude >= -180 AND centroid_longitude <= 180)",
            name="ck_regions_centroid_longitude",
        ),
        Index("ix_regions_region_type", "region_type"),
        Index("ix_regions_parent_region_id", "parent_region_id"),
        Index("ix_regions_labor_market_group", "labor_market_group"),
        Index("ix_regions_public_slug", "public_slug", unique=True),
        Index("ix_regions_market_support_status", "market_support_status"),
    )

    region_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    region_type: Mapped[str] = mapped_column(String(32), nullable=False)

    parent_region_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    labor_market_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalization_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    public_slug: Mapped[str | None] = mapped_column(String(96), nullable=True)
    primary_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    centroid_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    focus_bounds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    market_support_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )

    parent_region: Mapped[Region | None] = relationship(
        "Region",
        remote_side="Region.region_id",
        backref="child_regions",
    )


class RegionAlias(Base):
    """One normalized compatibility/input alias owned by a canonical Region."""

    __tablename__ = "region_aliases"
    __table_args__ = (
        UniqueConstraint("normalized_alias", name="uq_region_aliases_normalized_alias"),
        CheckConstraint(
            "alias_type IN ('public_slug', 'legacy_id', 'import_key', "
            "'city_alias', 'alternate_name', 'abbreviation')",
            name="ck_region_aliases_alias_type",
        ),
        Index("ix_region_aliases_region_id", "region_id"),
        Index("ix_region_aliases_alias_type", "alias_type"),
    )

    region_alias_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RegionStateMembership(Base):
    """Authoritative many-to-many membership between a Region and US states."""

    __tablename__ = "region_state_memberships"
    __table_args__ = (
        CheckConstraint(
            "length(state_code) = 2 AND state_code = upper(state_code)",
            name="ck_region_state_memberships_state_code",
        ),
        Index("ix_region_state_memberships_state_code", "state_code"),
    )

    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), primary_key=True
    )
    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    membership_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="market_coverage"
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
