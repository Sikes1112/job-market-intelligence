from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
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
        Index("ix_regions_region_type", "region_type"),
        Index("ix_regions_parent_region_id", "parent_region_id"),
        Index("ix_regions_labor_market_group", "labor_market_group"),
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

    parent_region: Mapped[Region | None] = relationship(
        "Region",
        remote_side="Region.region_id",
        backref="child_regions",
    )
