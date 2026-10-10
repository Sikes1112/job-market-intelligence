from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from backend.career_identity.models import CareerIdentityFact
from backend.career_identity.personalization import (
    build_personalization_from_career_identity,
)
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityPrivacyInput,
)
from backend.career_identity.service import CareerIdentityService
from backend.current_opportunities.normalization import normalize_opportunity_payload
from backend.geography.catalog import apply_curated_geography, load_curated_geographies
from backend.geography.exceptions import (
    GeographicIdentityConflict,
    GeographicInputAmbiguous,
    GeographicInputUnknown,
    PublishedSlugImmutable,
)
from backend.geography.models import (
    Region,
    RegionCanonicalRedirect,
    RegionIdentityClaim,
    RegionStateMembership,
)
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver, normalize_geographic_input
from backend.geography.service import GeographyService, RegionDefinition
from backend.imports.service import import_curated_market_dataset
from backend.personalization.payloads import UserPreferences
from backend.shared.db import make_engine, make_session_factory
from backend.shared.migrations import upgrade_database
from backend.users.models import SavedMarketArtifact, User
from backend.users.repository import UserRepository
from backend.users.service import (
    SavedMarketArtifactInput,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)
from seeds import mvp_seed


def _seed_curated_regions(session) -> RegionRepository:  # noqa: ANN001
    repository = RegionRepository(session)
    for definition in load_curated_geographies().values():
        session.add(
            Region(
                region_id=definition.region_id,
                region_name=definition.primary_city,
                display_name=definition.primary_city,
                region_type="greater_region",
            )
        )
    session.flush()
    for region_id in load_curated_geographies():
        assert apply_curated_geography(repository, region_id)
    return repository


def test_versioned_map_geometry_covers_states_and_frontend_copy_matches() -> None:
    source_path = Path("data/geography/us_states_simplified.geojson")
    frontend_path = Path("frontend/public/data/us_states_simplified.geojson")
    assert source_path.read_bytes() == frontend_path.read_bytes()
    payload = json.loads(source_path.read_text())
    codes = {feature["properties"]["state_code"] for feature in payload["features"]}
    assert len(codes) == 51
    assert {"AK", "HI", "DC", "MA", "CA"} <= codes
    assert "U.S. Census Bureau 2024" in payload["source"]


def test_canonical_resolver_accepts_all_curated_identity_forms(session) -> None:
    repository = _seed_curated_regions(session)
    resolver = GeographicResolver(repository)
    cases = {
        "greater_boston": "greater_boston",
        "boston": "greater_boston",
        "BOSTON-CAMBRIDGE": "greater_boston",
        "new-york": "greater_nyc",
        "NYC": "greater_nyc",
        "Greater NYC": "greater_nyc",
        "seattle": "greater_seattle",
        "san_francisco_bay_area": "sf_bay_area",
        "greater_sf": "sf_bay_area",
        "Bay Area": "sf_bay_area",
        "San Francisco": "sf_bay_area",
        "washington-dc": "washington_dc",
        "dc_nova": "washington_dc",
        "DC / NoVA": "washington_dc",
        "greater_atlanta": "atlanta",
        "greater_austin": "austin",
        "chicago": "chicago",
    }
    for value, expected_region_id in cases.items():
        result = resolver.resolve(value)
        assert result.status == "resolved", value
        assert result.region_id == expected_region_id, value
        assert result.public_slug


def test_lookup_normalization_is_deterministic_but_not_persisted_identity(session) -> None:
    repository = _seed_curated_regions(session)
    resolver = GeographicResolver(repository)

    assert normalize_geographic_input("  SF-Bay_Area  ") == "sf bay area"
    assert resolver.resolve("SF-Bay_Area").region_id == "sf_bay_area"
    assert repository.get("SF-Bay_Area") is None


def test_unknown_and_ambiguous_inputs_fail_closed(session) -> None:
    repository = _seed_curated_regions(session)
    session.add_all(
        [
            Region(
                region_id="springfield_il",
                region_name="Springfield",
                display_name="Springfield",
                region_type="city",
            ),
            Region(
                region_id="springfield_ma",
                region_name="Springfield",
                display_name="Springfield",
                region_type="city",
            ),
        ]
    )
    session.flush()
    resolver = GeographicResolver(repository)

    unknown = resolver.resolve("Not A Real Market")
    ambiguous = resolver.resolve("Springfield")
    assert unknown.status == "unresolved"
    assert unknown.region_id is None
    assert ambiguous.status == "ambiguous"
    assert ambiguous.region_id is None
    assert ambiguous.candidate_region_ids == ("springfield_il", "springfield_ma")


def test_alias_conflicts_are_prevented_and_state_membership_is_many_to_many(session) -> None:
    repository = _seed_curated_regions(session)
    assert repository.state_codes("greater_nyc") == ("CT", "NJ", "NY")
    assert repository.state_codes("washington_dc") == ("DC", "MD", "VA")
    session.add(
        Region(
            region_id="boston_city_evidence",
            region_name="Boston city evidence",
            display_name="Boston City",
            region_type="city",
            parent_region_id="greater_boston",
        )
    )
    session.add(
        RegionStateMembership(
            region_id="boston_city_evidence",
            state_code="MA",
            membership_type="market_coverage",
        )
    )
    session.flush()

    ma_regions = set(
        session.execute(
            select(RegionStateMembership.region_id).where(RegionStateMembership.state_code == "MA")
        ).scalars()
    )
    assert ma_regions == {"greater_boston", "boston_city_evidence"}
    assert session.get(Region, "boston_city_evidence").parent_region_id == "greater_boston"
    assert len(repository.aliases_for_normalized("boston")) == 1


def test_region_id_slug_and_alias_share_one_conflict_safe_namespace(session) -> None:
    repository = RegionRepository(session)
    service = GeographyService(repository)
    service.create_region(
        RegionDefinition(
            region_id="foo",
            region_name="Foo",
            display_name="Foo",
            region_type="city",
        )
    )
    service.create_region(
        RegionDefinition(
            region_id="bar",
            region_name="Bar",
            display_name="Bar",
            region_type="city",
            public_slug="bar-public",
        )
    )

    with pytest.raises(GeographicIdentityConflict):
        service.add_alias(
            region_alias_id="alias_bar_foo",
            region_id="bar",
            alias="foo",
            alias_type="alternate_name",
        )
    with pytest.raises(GeographicIdentityConflict):
        service.add_alias(
            region_alias_id="alias_foo_bar_public",
            region_id="foo",
            alias="bar public",
            alias_type="alternate_name",
        )
    with pytest.raises(GeographicIdentityConflict):
        service.create_region(
            RegionDefinition(
                region_id="baz",
                region_name="Baz",
                display_name="Baz",
                region_type="city",
                public_slug="foo",
            )
        )

    redundant = service.add_alias(
        region_alias_id="alias_bar_slug",
        region_id="bar",
        alias="Bar Public",
        alias_type="alternate_name",
    )
    assert redundant.region_id == "bar"
    assert GeographicResolver(repository).resolve("bar-public").region_id == "bar"


def test_identity_claim_primary_key_is_database_enforced_and_postgresql_atomic(
    session,
) -> None:
    session.add_all(
        [
            Region(
                region_id="claim_a",
                region_name="Claim A",
                display_name="Claim A",
                region_type="city",
            ),
            Region(
                region_id="claim_b",
                region_name="Claim B",
                display_name="Claim B",
                region_type="city",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionIdentityClaim(
                normalized_token="shared token",
                region_id="claim_a",
                claim_type="alias",
            ),
            RegionIdentityClaim(
                normalized_token="shared token",
                region_id="claim_b",
                claim_type="public_slug",
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

    ddl = str(CreateTable(RegionIdentityClaim.__table__).compile(dialect=postgresql.dialect()))
    assert "PRIMARY KEY (normalized_token)" in ddl


def test_public_slug_normalization_immutability_and_future_city_conflict(session) -> None:
    repository = _seed_curated_regions(session)
    service = GeographyService(repository)
    created = service.create_region(
        RegionDefinition(
            region_id="northwest_test",
            region_name="Northwest Test",
            display_name="Northwest Test",
            region_type="city",
            public_slug="  North_West!! ",
        )
    )
    assert created.public_slug == "north-west"

    with pytest.raises(PublishedSlugImmutable):
        service.update_region(
            RegionDefinition(
                region_id="northwest_test",
                region_name="Northwest Test",
                display_name="Northwest Test",
                region_type="city",
                public_slug="different-slug",
            )
        )
    with pytest.raises(ValidationError):
        RegionDefinition(
            region_id="invalid_slug",
            region_name="Invalid",
            display_name="Invalid",
            region_type="city",
            public_slug="!!!",
        )
    with pytest.raises(GeographicIdentityConflict):
        service.create_region(
            RegionDefinition(
                region_id="san_francisco_city",
                region_name="San Francisco",
                display_name="San Francisco",
                region_type="city",
                public_slug="san-francisco",
            )
        )


def test_resolver_api_emits_canonical_identity_and_legacy_urls_work(api_client, session) -> None:
    _seed_curated_regions(session)

    resolved = api_client.get("/regions/resolve", params={"input": "greater_sf"})
    assert resolved.status_code == 200
    assert resolved.json()["data"]["region_id"] == "sf_bay_area"
    assert resolved.json()["data"]["public_slug"] == "san-francisco-bay-area"
    assert resolved.json()["data"]["state_codes"] == ["CA"]

    listing = api_client.get("/regions")
    sf = next(
        item for item in listing.json()["data"]["regions"] if item["region_id"] == "sf_bay_area"
    )
    assert sf["public_slug"] == "san-francisco-bay-area"
    assert sf["market_support_status"] == "supported"
    assert sf["centroid"] == {"latitude": 37.7272, "longitude": -123.0322}

    for token in ("sf_bay_area", "san-francisco-bay-area", "greater_sf"):
        assert api_client.get(f"/regions/{token}").status_code == 200
        assert api_client.get(f"/platform/history/regions/{token}").status_code == 200
        assert api_client.get("/companies/search", params={"region_id": token}).status_code == 200
    assert api_client.get("/regions/not-a-real-market").status_code == 404
    assert api_client.get("/platform/history/regions/not-a-real-market").status_code == 404


def test_career_identity_resolution_preserves_raw_fact_and_reports_unknown(session) -> None:
    repository = _seed_curated_regions(session)
    session.add(User(user_id="geo_user"))
    session.flush()
    identity_service = CareerIdentityService(
        CareerIdentityRepository(session), UserRepository(session)
    )
    identity_service.get_or_create_identity("geo_user")
    identity_service.update_privacy(
        "geo_user",
        CareerIdentityPrivacyInput(downstream_personalization_consent_granted=True),
    )
    for location in ("Bay Area", "Unknown Place"):
        identity_service.upsert_fact(
            "geo_user",
            CareerIdentityFactInput(
                fact_type=CareerFactType.GEOGRAPHIC_CONSTRAINT,
                state=CareerFactState.EXPLICIT,
                payload={"location": location, "constraint_kind": "target"},
            ),
        )

    adapted = build_personalization_from_career_identity(
        current_user_id="geo_user",
        base_preferences=UserPreferences(region_ids=["greater_boston"]),
        career_identity_repo=CareerIdentityRepository(session),
        region_repo=repository,
    )
    facts = session.execute(
        select(CareerIdentityFact).where(CareerIdentityFact.fact_type == "geographic_constraint")
    ).scalars()
    assert {fact.payload["location"] for fact in facts} == {"Bay Area", "Unknown Place"}
    assert adapted.preferences.region_ids == ["sf_bay_area"]
    statuses = {
        item["raw_location"]: item["status"] for item in adapted.metadata["geographic_resolutions"]
    }
    assert statuses == {"Bay Area": "resolved", "Unknown Place": "unresolved"}


def test_new_region_saves_are_canonical_and_legacy_saves_remain_readable(session) -> None:
    repository = _seed_curated_regions(session)
    session.add(User(user_id="save_user"))
    session.flush()
    service = UserPersonalizationPersistenceService(UserRepository(session), repository)

    saved = service.save_market_artifact(
        "save_user",
        SavedMarketArtifactInput(artifact_type="region", artifact_ref="greater_sf"),
    )
    assert saved.artifact_ref == "sf_bay_area"

    historical = SavedMarketArtifact(
        saved_artifact_id="historical_geo_save",
        user_id="save_user",
        artifact_type="region",
        artifact_ref="DC/NoVA",
    )
    session.add(historical)
    session.flush()
    resolution = service.resolve_saved_region_reference(historical)
    assert historical.artifact_ref == "DC/NoVA"
    assert resolution is not None
    assert resolution.region_id == "washington_dc"


def test_new_region_saves_and_preferences_reject_unknown_or_ambiguous_values(
    session,
) -> None:
    repository = _seed_curated_regions(session)
    session.add_all(
        [
            User(user_id="strict_geo_user"),
            Region(
                region_id="springfield_il",
                region_name="Springfield",
                display_name="Springfield",
                region_type="city",
            ),
            Region(
                region_id="springfield_ma",
                region_name="Springfield",
                display_name="Springfield",
                region_type="city",
            ),
        ]
    )
    session.flush()
    service = UserPersonalizationPersistenceService(UserRepository(session), repository)

    with pytest.raises(GeographicInputUnknown):
        service.save_market_artifact(
            "strict_geo_user",
            SavedMarketArtifactInput(
                artifact_type="region",
                artifact_ref="Not A Real Place",
            ),
        )
    with pytest.raises(GeographicInputAmbiguous):
        service.save_market_artifact(
            "strict_geo_user",
            SavedMarketArtifactInput(artifact_type="region", artifact_ref="Springfield"),
        )
    with pytest.raises(GeographicInputUnknown):
        service.upsert_preference_profile(
            "strict_geo_user",
            UserPreferenceProfileInput(preferred_regions=["Not A Real Place"]),
        )
    with pytest.raises(GeographicInputAmbiguous):
        service.upsert_preference_profile(
            "strict_geo_user",
            UserPreferenceProfileInput(preferred_regions=["Springfield"]),
        )

    canonical = service.upsert_preference_profile(
        "strict_geo_user",
        UserPreferenceProfileInput(preferred_regions=["greater_sf"]),
    )
    assert canonical.preferred_regions == ["sf_bay_area"]
    assert service.list_saved_market_artifacts("strict_geo_user") == []


def test_current_opportunity_geography_resolves_legacy_and_preserves_unknown_raw_text(
    session,
) -> None:
    repository = _seed_curated_regions(session)
    resolver = GeographicResolver(repository)
    common = {
        "company_name": "Example Co",
        "title": "Software Engineer",
        "application_url": "https://example.com/jobs/1",
    }

    resolved = normalize_opportunity_payload(
        {**common, "market_id": "greater_sf", "location": "Bay Area hybrid"},
        provider_record_id="resolved-1",
        companies_by_name={},
        geographic_resolver=resolver,
    )
    unresolved = normalize_opportunity_payload(
        {**common, "market_id": "mystery_market", "location": "Somewhere, USA"},
        provider_record_id="unresolved-1",
        companies_by_name={},
        geographic_resolver=resolver,
    )

    assert resolved.market_id == "sf_bay_area"
    assert resolved.location_resolution_status == "resolved"
    assert resolved.market_label == "Bay Area hybrid"
    assert resolved.location_text == "Bay Area hybrid"
    assert unresolved.market_id is None
    assert unresolved.location_resolution_status == "unresolved"
    assert unresolved.market_label == "Somewhere, USA"
    assert unresolved.location_text == "Somewhere, USA"


def test_0041_backfills_existing_curated_regions_without_changing_ids(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'geo-migration.db'}"
    upgrade_database(database_url, revision="0040_product_measurement_beta_ops")
    engine = make_engine(database_url)
    try:
        now = datetime.now(UTC)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO regions "
                    "(region_id, region_name, display_name, region_type, parent_region_id, "
                    "labor_market_group, normalization_profile_id, state, version, created_at, "
                    "updated_at) VALUES "
                    "('greater_nyc', 'Greater NYC', 'Greater NYC', 'greater_region', NULL, "
                    "NULL, NULL, 'fresh', 1, :now, :now), "
                    "('washington_dc', 'Washington DC', 'Washington DC', 'greater_region', "
                    "NULL, NULL, NULL, 'fresh', 1, :now, :now)"
                ),
                {"now": now},
            )
    finally:
        engine.dispose()

    upgrade_database(database_url)
    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            regions = connection.execute(
                text(
                    "SELECT region_id, public_slug FROM regions "
                    "WHERE region_id IN ('greater_nyc', 'washington_dc') ORDER BY region_id"
                )
            ).all()
            states = connection.execute(
                text(
                    "SELECT region_id, state_code FROM region_state_memberships "
                    "ORDER BY region_id, state_code"
                )
            ).all()
        assert regions == [
            ("greater_nyc", "new-york"),
            ("washington_dc", "washington-dc"),
        ]
        assert states == [
            ("greater_nyc", "CT"),
            ("greater_nyc", "NJ"),
            ("greater_nyc", "NY"),
            ("washington_dc", "DC"),
            ("washington_dc", "MD"),
            ("washington_dc", "VA"),
        ]
    finally:
        engine.dispose()


def test_0041_rejects_preexisting_cross_namespace_identity_conflict(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'geo-conflict-migration.db'}"
    upgrade_database(database_url, revision="0040_product_measurement_beta_ops")
    engine = make_engine(database_url)
    try:
        now = datetime.now(UTC)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO regions "
                    "(region_id, region_name, display_name, region_type, parent_region_id, "
                    "labor_market_group, normalization_profile_id, state, version, created_at, "
                    "updated_at) VALUES "
                    "('greater_boston', 'Greater Boston', 'Greater Boston', "
                    "'greater_region', NULL, NULL, NULL, 'fresh', 1, :now, :now), "
                    "('boston', 'Boston City', 'Boston City', 'city', NULL, NULL, NULL, "
                    "'fresh', 1, :now, :now)"
                ),
                {"now": now},
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="geographic identity conflict"):
        upgrade_database(database_url)

    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(regions)")).all()
            }
        assert "public_slug" not in columns
    finally:
        engine.dispose()


def test_0042_converges_legacy_demo_sf_without_rewriting_historical_region_fk(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy-sf-convergence.db'}"
    upgrade_database(database_url, revision="0040_product_measurement_beta_ops")
    engine = make_engine(database_url)
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO regions "
                    "(region_id, region_name, display_name, region_type, parent_region_id, "
                    "labor_market_group, normalization_profile_id, state, version, created_at, "
                    "updated_at) VALUES "
                    "('greater_boston', 'greater_boston', 'Greater Boston', 'greater_region', "
                    "NULL, NULL, NULL, 'fresh', 1, :now, :now), "
                    "('greater_sf', 'greater_sf', 'Greater San Francisco', 'greater_region', "
                    "NULL, NULL, NULL, 'fresh', 1, :now, :now), "
                    "('legacy_sf_child', 'Legacy SF child', 'Legacy SF child', 'city', "
                    "'greater_sf', NULL, NULL, 'fresh', 1, :now, :now)"
                ),
                {"now": now},
            )
    finally:
        engine.dispose()

    upgrade_database(database_url)
    engine = make_engine(database_url)
    factory = make_session_factory(engine)
    session = factory()
    try:
        repository = RegionRepository(session)
        redirect = session.get(RegionCanonicalRedirect, "greater_sf")
        assert redirect is not None
        assert redirect.canonical_region_id == "sf_bay_area"
        assert session.get(Region, "greater_sf") is not None
        assert session.get(Region, "legacy_sf_child").parent_region_id == "greater_sf"
        assert [row.region_id for row in repository.list()] == [
            "greater_boston",
            "legacy_sf_child",
            "sf_bay_area",
        ]

        resolver = GeographicResolver(repository)
        for token in (
            "greater_sf",
            "sf_bay_area",
            "san_francisco_bay_area",
            "San Francisco",
            "san-francisco-bay-area",
        ):
            assert resolver.require(token).region_id == "sf_bay_area"

        imported = import_curated_market_dataset(
            session,
            "san_francisco_bay_area",
            as_of=date(2026, 7, 9),
        )
        assert imported.ok
        session.flush()
        assert session.query(Region).filter_by(region_id="sf_bay_area").count() == 1
        assert [row.region_id for row in repository.list()].count("sf_bay_area") == 1
        claim = session.get(RegionIdentityClaim, "greater sf")
        assert claim is not None
        assert claim.region_id == "sf_bay_area"
        first_seed = mvp_seed.run_seed(session)
        second_seed = mvp_seed.run_seed(session)
        assert first_seed.regions.get("created", 0) == 0
        assert second_seed.regions["unchanged"] == 2
        assert session.query(Region).filter_by(region_id="greater_sf").count() == 1
        assert [row.region_id for row in repository.list()].count("sf_bay_area") == 1
    finally:
        session.close()
        engine.dispose()
