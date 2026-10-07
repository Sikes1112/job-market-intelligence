"""Add canonical geographic identity, aliases, and state membership.

Revision ID: 0041_canonical_geographic_foundation
Revises: 0040_product_measurement_beta_ops
Create Date: 2026-10-07
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0041_canonical_geographic_foundation"
down_revision = "0040_product_measurement_beta_ops"
branch_labels = None
depends_on = None


_CURATED = (
    {
        "region_id": "greater_boston",
        "public_slug": "boston",
        "primary_city": "Boston",
        "states": ("MA",),
        "aliases": (
            ("boston", "boston", "import_key"),
            ("Greater Boston", "greater boston", "alternate_name"),
            ("Boston-Cambridge", "boston cambridge", "alternate_name"),
        ),
    },
    {
        "region_id": "greater_nyc",
        "public_slug": "new-york",
        "primary_city": "New York",
        "states": ("CT", "NJ", "NY"),
        "aliases": (
            ("nyc", "nyc", "import_key"),
            ("Greater NYC", "greater nyc", "alternate_name"),
            ("New York", "new york", "city_alias"),
        ),
    },
    {
        "region_id": "greater_seattle",
        "public_slug": "seattle",
        "primary_city": "Seattle",
        "states": ("WA",),
        "aliases": (
            ("seattle", "seattle", "import_key"),
            ("Greater Seattle", "greater seattle", "alternate_name"),
        ),
    },
    {
        "region_id": "sf_bay_area",
        "public_slug": "san-francisco-bay-area",
        "primary_city": "San Francisco",
        "states": ("CA",),
        "aliases": (
            ("san_francisco_bay_area", "san francisco bay area", "import_key"),
            ("greater_sf", "greater sf", "legacy_id"),
            ("Bay Area", "bay area", "alternate_name"),
            ("SF Bay Area", "sf bay area", "abbreviation"),
            ("San Francisco", "san francisco", "city_alias"),
        ),
    },
    {
        "region_id": "washington_dc",
        "public_slug": "washington-dc",
        "primary_city": "Washington",
        "states": ("DC", "MD", "VA"),
        "aliases": (
            ("Washington DC", "washington dc", "import_key"),
            ("dc_nova", "dc nova", "legacy_id"),
        ),
    },
    {
        "region_id": "atlanta",
        "public_slug": "atlanta",
        "primary_city": "Atlanta",
        "states": ("GA",),
        "aliases": (("greater_atlanta", "greater atlanta", "legacy_id"),),
    },
    {
        "region_id": "austin",
        "public_slug": "austin",
        "primary_city": "Austin",
        "states": ("TX",),
        "aliases": (("greater_austin", "greater austin", "legacy_id"),),
    },
    {
        "region_id": "chicago",
        "public_slug": "chicago",
        "primary_city": "Chicago",
        "states": ("IL",),
        "aliases": (),
    },
)


def _normalized_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"[\s_\-/,\.]+", " ", normalized).strip()


def _assert_conflict_safe_existing_namespace(connection) -> None:  # noqa: ANN001
    existing_region_ids = {
        row[0] for row in connection.execute(sa.text("SELECT region_id FROM regions")).all()
    }
    owners: dict[str, str] = {}

    def claim(value: str, region_id: str) -> None:
        token = _normalized_identity(value)
        existing_owner = owners.get(token)
        if existing_owner is not None and existing_owner != region_id:
            raise RuntimeError(
                "0041 geographic identity conflict for normalized token "
                f"{token!r}: {existing_owner!r} vs {region_id!r}"
            )
        owners[token] = region_id

    for region_id in existing_region_ids:
        claim(region_id, region_id)
    for market in _CURATED:
        region_id = market["region_id"]
        if region_id not in existing_region_ids:
            continue
        claim(market["public_slug"], region_id)
        for alias, _normalized_alias, _alias_type in market["aliases"]:
            claim(alias, region_id)


def upgrade() -> None:
    connection = op.get_bind()
    # Validate before any SQLite DDL because SQLite migration DDL is not
    # transactional.  A pre-existing ID may not be shadowed by a curated slug
    # or alias belonging to another Region.
    _assert_conflict_safe_existing_namespace(connection)
    op.add_column("regions", sa.Column("public_slug", sa.String(length=96), nullable=True))
    op.add_column("regions", sa.Column("primary_city", sa.String(length=128), nullable=True))
    op.add_column("regions", sa.Column("centroid_latitude", sa.Float(), nullable=True))
    op.add_column("regions", sa.Column("centroid_longitude", sa.Float(), nullable=True))
    op.add_column("regions", sa.Column("focus_bounds", sa.JSON(), nullable=True))
    op.add_column(
        "regions",
        sa.Column(
            "market_support_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_index("ix_regions_public_slug", "regions", ["public_slug"], unique=True)
    op.create_index("ix_regions_market_support_status", "regions", ["market_support_status"])

    op.create_table(
        "region_aliases",
        sa.Column("region_alias_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "alias_type IN ('public_slug', 'legacy_id', 'import_key', "
            "'city_alias', 'alternate_name', 'abbreviation')",
            name="ck_region_aliases_alias_type",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("region_alias_id"),
        sa.UniqueConstraint("normalized_alias", name="uq_region_aliases_normalized_alias"),
    )
    op.create_index("ix_region_aliases_alias_type", "region_aliases", ["alias_type"])
    op.create_index("ix_region_aliases_region_id", "region_aliases", ["region_id"])

    op.create_table(
        "region_state_memberships",
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("membership_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(state_code) = 2 AND state_code = upper(state_code)",
            name="ck_region_state_memberships_state_code",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("region_id", "state_code"),
    )
    op.create_index(
        "ix_region_state_memberships_state_code",
        "region_state_memberships",
        ["state_code"],
    )

    op.add_column(
        "current_opportunities",
        sa.Column(
            "location_resolution_status",
            sa.String(length=32),
            nullable=False,
            server_default="unresolved",
        ),
    )
    op.add_column(
        "current_opportunities",
        sa.Column("location_resolution_source", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_current_opportunities_location_resolution",
        "current_opportunities",
        ["location_resolution_status"],
    )

    # SQLite cannot add CHECK constraints to existing tables without a table
    # rebuild. Fresh SQLite schemas receive these constraints from the ORM;
    # PostgreSQL upgrades receive them directly here.
    if connection.dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_regions_market_support_status",
            "regions",
            "market_support_status IN ('supported', 'unsupported', 'unknown')",
        )
        op.create_check_constraint(
            "ck_regions_centroid_latitude",
            "regions",
            "centroid_latitude IS NULL OR (centroid_latitude >= -90 AND centroid_latitude <= 90)",
        )
        op.create_check_constraint(
            "ck_regions_centroid_longitude",
            "regions",
            "centroid_longitude IS NULL OR "
            "(centroid_longitude >= -180 AND centroid_longitude <= 180)",
        )
        op.create_check_constraint(
            "ck_current_opportunities_location_resolution",
            "current_opportunities",
            "location_resolution_status IN ('resolved', 'unresolved', 'ambiguous')",
        )
    now = datetime.now(UTC)
    for market in _CURATED:
        exists = connection.execute(
            sa.text("SELECT 1 FROM regions WHERE region_id = :region_id"),
            {"region_id": market["region_id"]},
        ).scalar_one_or_none()
        if not exists:
            continue
        connection.execute(
            sa.text(
                "UPDATE regions SET public_slug = :public_slug, "
                "primary_city = :primary_city, market_support_status = 'supported' "
                "WHERE region_id = :region_id"
            ),
            market,
        )
        for state_code in market["states"]:
            connection.execute(
                sa.text(
                    "INSERT INTO region_state_memberships "
                    "(region_id, state_code, membership_type, source, created_at, updated_at) "
                    "VALUES (:region_id, :state_code, 'market_coverage', :source, :now, :now)"
                ),
                {
                    "region_id": market["region_id"],
                    "state_code": state_code,
                    "source": "0041 curated import reconciliation",
                    "now": now,
                },
            )
        for index, (alias, normalized_alias, alias_type) in enumerate(market["aliases"], start=1):
            connection.execute(
                sa.text(
                    "INSERT INTO region_aliases "
                    "(region_alias_id, region_id, alias, normalized_alias, alias_type, "
                    "source, created_at, updated_at) VALUES "
                    "(:alias_id, :region_id, :alias, :normalized_alias, :alias_type, "
                    ":source, :now, :now)"
                ),
                {
                    "alias_id": f"geo_alias_{market['region_id']}_{index}",
                    "region_id": market["region_id"],
                    "alias": alias,
                    "normalized_alias": normalized_alias,
                    "alias_type": alias_type,
                    "source": "0041 curated import reconciliation",
                    "now": now,
                },
            )

    connection.execute(
        sa.text(
            "UPDATE current_opportunities SET location_resolution_status = 'resolved', "
            "location_resolution_source = 'legacy_canonical_region_fk' "
            "WHERE market_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "ck_current_opportunities_location_resolution",
            "current_opportunities",
            type_="check",
        )
        op.drop_constraint("ck_regions_centroid_longitude", "regions", type_="check")
        op.drop_constraint("ck_regions_centroid_latitude", "regions", type_="check")
        op.drop_constraint("ck_regions_market_support_status", "regions", type_="check")
    op.drop_index(
        "ix_current_opportunities_location_resolution",
        table_name="current_opportunities",
    )
    op.drop_column("current_opportunities", "location_resolution_source")
    op.drop_column("current_opportunities", "location_resolution_status")
    op.drop_index(
        "ix_region_state_memberships_state_code",
        table_name="region_state_memberships",
    )
    op.drop_table("region_state_memberships")
    op.drop_index("ix_region_aliases_region_id", table_name="region_aliases")
    op.drop_index("ix_region_aliases_alias_type", table_name="region_aliases")
    op.drop_table("region_aliases")
    op.drop_index("ix_regions_market_support_status", table_name="regions")
    op.drop_index("ix_regions_public_slug", table_name="regions")
    op.drop_column("regions", "market_support_status")
    op.drop_column("regions", "focus_bounds")
    op.drop_column("regions", "centroid_longitude")
    op.drop_column("regions", "centroid_latitude")
    op.drop_column("regions", "primary_city")
    op.drop_column("regions", "public_slug")
