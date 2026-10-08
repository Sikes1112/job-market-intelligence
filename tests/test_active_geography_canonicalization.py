from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from backend.api.user import _saved_artifact_data
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.current_opportunities.adapters import StaticOpportunityAdapter
from backend.current_opportunities.models import (
    CurrentOpportunity,
    OpportunityCoverageContract,
    OpportunityDataSource,
    OpportunitySourceObservation,
)
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    AcquisitionMethod,
    AllowedUseClassification,
    CoverageStatus,
    LicenseTermsClassification,
    OpportunityCoverageInput,
    OpportunityKind,
    OpportunitySourceType,
    SourceRegistryInput,
    SourceTrustClassification,
)
from backend.current_opportunities.service import CurrentOpportunityService
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import (
    EntryLevelDefinition,
    EntryLevelService,
    EntryLevelSnapshot,
)
from backend.geography.exceptions import GeographicInputAmbiguous, GeographicInputUnknown
from backend.geography.models import (
    Region,
    RegionCanonicalRedirect,
    RegionIdentityClaim,
)
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringDefinition, HiringService, HiringSnapshot
from backend.institutions.dashboard import _target_market_contributors
from backend.opportunities.models import OpportunityRegionBinding
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import OpportunityCreate, OpportunityRegionBindingCreate
from backend.opportunities.service import OpportunityService
from backend.presence.evidence import PresenceEvidence
from backend.presence.exceptions import MissingRegionForPresence
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceDefinition, PresenceService
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.db import make_engine, make_session_factory
from backend.shared.migrations import upgrade_database
from backend.users.models import SavedMarketArtifact, User, UserPreferenceProfile
from backend.users.repository import UserRepository
from backend.users.service import UserPersonalizationPersistenceService

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _seed_redirect(session) -> None:  # noqa: ANN001
    session.add_all(
        [
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater San Francisco",
                region_type="greater_region",
            ),
            Region(
                region_id="sf_bay_area",
                region_name="sf_bay_area",
                display_name="San Francisco Bay Area",
                region_type="greater_region",
                public_slug="san-francisco-bay-area",
            ),
        ]
    )
    session.flush()
    session.add(
        RegionCanonicalRedirect(
            legacy_region_id="greater_sf",
            canonical_region_id="sf_bay_area",
            reason="test redirect",
        )
    )
    for token, claim_type in (
        ("greater sf", "legacy"),
        ("sf bay area", "region_id"),
        ("san francisco bay area", "public_slug"),
        ("bay area", "alias"),
    ):
        session.add(
            RegionIdentityClaim(
                normalized_token=token,
                region_id="sf_bay_area",
                claim_type=claim_type,
            )
        )
    session.flush()


def _current_service(session) -> CurrentOpportunityService:  # noqa: ANN001
    return CurrentOpportunityService(CurrentOpportunityRepository(session))


def _source_request() -> SourceRegistryInput:
    return SourceRegistryInput(
        source_id="src_legacy_sf",
        provider="Legacy Provider",
        display_name="Legacy Provider Feed",
        source_type=OpportunitySourceType.API,
        acquisition_method=AcquisitionMethod.API_PULL,
        allowed_use=AllowedUseClassification.ALLOWED,
        license_terms=LicenseTermsClassification.PERMISSIVE,
        trust=SourceTrustClassification.HIGH,
        freshness_sla_hours=8760,
        supported_markets=("greater_sf",),
        supported_opportunity_types=(OpportunityKind.JOB,),
        ranking_use_allowed=True,
        display_use_allowed=True,
        provenance_requirements=("provider_record_id", "observed_at"),
    )


def _coverage_request() -> OpportunityCoverageInput:
    return OpportunityCoverageInput(
        coverage_id="cov_legacy_sf",
        market_key="greater_sf",
        market_id="greater_sf",
        market_label="Greater San Francisco",
        role_family="software_engineering",
        opportunity_type="job",
        status=CoverageStatus.PRODUCTION_READY,
        rationale="Migration fixture coverage.",
        source_basis={"sources": ["src_legacy_sf"]},
        minimum_expected_sources=1,
        freshness_max_age_hours=8760,
        last_evaluated_at=NOW,
    )


def _opportunity_record() -> dict:
    return {
        "provider_record_id": "legacy-job-1",
        "observed_at": NOW,
        "collected_at": NOW,
        "raw_payload": {
            "provider_record_id": "legacy-job-1",
            "company_name": "Legacy Robotics",
            "company_id": "comp_legacy_sf",
            "title": "Software Engineer I",
            "role_family": "software_engineering",
            "seniority_level": "entry_level",
            "market_id": "greater_sf",
            "location": "Greater San Francisco",
            "work_arrangement": "hybrid",
            "employment_type": "full_time",
            "opportunity_type": "job",
            "application_url": "https://jobs.example.com/legacy-job-1",
            "source_url": "https://jobs.example.com/source/legacy-job-1",
        },
    }


def _prepare_0042_database(database_url: str, *, collision: bool = False) -> str:
    upgrade_database(database_url, revision="0040_product_measurement_beta_ops")
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO regions (region_id, region_name, display_name, region_type, "
                    "parent_region_id, labor_market_group, normalization_profile_id, state, "
                    "version, created_at, updated_at) VALUES "
                    "('greater_sf', 'greater_sf', 'Greater San Francisco', "
                    "'greater_region', NULL, NULL, NULL, 'fresh', 1, :now, :now)"
                ),
                {"now": NOW},
            )
    finally:
        engine.dispose()

    upgrade_database(database_url, revision="0042_geographic_contract_closure")
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        session.add_all(
            [
                Company(
                    company_id="comp_legacy_sf",
                    company_name="Legacy Robotics",
                    normalized_company_name="legacy robotics",
                ),
                User(user_id="legacy_geo_user"),
            ]
        )
        session.flush()
        current_service = _current_service(session)
        current_service.upsert_source(_source_request())
        current_service.upsert_coverage(_coverage_request())
        current_service.refresh_source(
            StaticOpportunityAdapter(
                source_id="src_legacy_sf",
                records=(_opportunity_record(),),
                collected_at=NOW,
            ),
            run_id="run_legacy_sf",
            idempotency_key="run_legacy_sf",
            now=NOW,
        )
        row = session.execute(select(CurrentOpportunity)).scalar_one()
        legacy_opportunity_id = row.current_opportunity_id
        row.market_id = "greater_sf"
        row.market_label = "Greater San Francisco"
        row.canonical_identity_key = row.canonical_identity_key.replace(
            "sf bay area", "greater sf"
        )
        row.duplicate_group_key = row.duplicate_group_key.replace(
            "sf bay area", "greater sf"
        )
        source = session.get(OpportunityDataSource, "src_legacy_sf")
        assert source is not None
        source.supported_markets = ["greater_sf", "sf_bay_area"]
        coverage = session.get(OpportunityCoverageContract, "cov_legacy_sf")
        assert coverage is not None
        coverage.market_key = "greater_sf"
        coverage.market_id = "greater_sf"
        coverage.market_label = "Greater San Francisco"
        session.add(
            CompanyRegionPresence(
                presence_id="presence_legacy_sf",
                company_id="comp_legacy_sf",
                region_id="greater_sf",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                operations_evidence_flag=False,
                presence_confidence="high_confidence",
            )
        )
        session.add_all(
            [
                CompanyRegionHiring(
                    hiring_id="hiring_legacy_sf",
                    company_id="comp_legacy_sf",
                    region_id="greater_sf",
                    currently_hiring_flag=True,
                ),
                CompanyRegionEntryLevel(
                    entry_level_id="entry_legacy_sf",
                    company_id="comp_legacy_sf",
                    region_id="greater_sf",
                    formal_early_career_program_flag=True,
                ),
                RegionMarketScore(
                    region_score_id="score_legacy_sf",
                    region_id="greater_sf",
                    score_ruleset_version="legacy_fixture_v1",
                ),
            ]
        )
        legacy_payload = OpportunityService(OpportunityRepository(session)).create_opportunity(
            OpportunityCreate(
                opportunity_id="legacy_opportunity",
                employer_name="Legacy Robotics",
                program_name="Legacy Internship",
                program_type="internship",
                application_url="https://jobs.example.com/internship",
                source_url="https://jobs.example.com/internship/source",
                source_type="employer_official",
                region_bindings=(
                    OpportunityRegionBindingCreate(
                        opportunity_region_binding_id="legacy_binding",
                        region_id="greater_sf",
                        region_label="Greater San Francisco",
                    ),
                ),
            )
        )
        assert legacy_payload.region_bindings[0].region_id == "sf_bay_area"
        session.execute(
            text(
                "UPDATE opportunity_region_bindings SET region_id = 'greater_sf' "
                "WHERE opportunity_region_binding_id = 'legacy_binding'"
            )
        )
        session.add_all(
            [
                UserPreferenceProfile(
                    user_id="legacy_geo_user",
                    preferred_regions=["greater_sf", "sf_bay_area"],
                ),
                SavedMarketArtifact(
                    saved_artifact_id="saved_legacy_sf",
                    user_id="legacy_geo_user",
                    artifact_type="region",
                    artifact_ref="greater_sf",
                ),
            ]
        )
        if collision:
            values = {
                column.name: getattr(row, column.name)
                for column in CurrentOpportunity.__table__.columns
            }
            values.update(
                current_opportunity_id="canonical_collision_survivor",
                market_id="sf_bay_area",
                market_label="San Francisco Bay Area",
                canonical_identity_key=row.canonical_identity_key.replace(
                    "greater sf", "sf bay area"
                ),
                duplicate_group_key=row.duplicate_group_key.replace(
                    "greater sf", "sf bay area"
                ),
                created_at=NOW.replace(hour=11),
            )
            session.add(CurrentOpportunity(**values))
        session.commit()
        return legacy_opportunity_id
    finally:
        session.close()
        engine.dispose()


def test_0043_canonicalizes_active_rows_and_preserves_historical_evidence(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'active-geography.db'}"
    opportunity_id = _prepare_0042_database(database_url)

    upgrade_database(database_url)
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        row = session.get(CurrentOpportunity, opportunity_id)
        assert row is not None
        assert row.market_id == "sf_bay_area"
        assert "|sf bay area|" in row.canonical_identity_key
        assert "|sf bay area|" in row.duplicate_group_key
        source = session.get(OpportunityDataSource, "src_legacy_sf")
        assert source is not None
        assert source.supported_markets == ["sf_bay_area"]
        coverage = session.get(OpportunityCoverageContract, "cov_legacy_sf")
        assert coverage is not None
        assert (coverage.market_key, coverage.market_id) == (
            "sf_bay_area",
            "sf_bay_area",
        )
        assert session.get(CompanyRegionPresence, "presence_legacy_sf").region_id == (
            "sf_bay_area"
        )
        assert session.get(CompanyRegionHiring, "hiring_legacy_sf").region_id == (
            "sf_bay_area"
        )
        assert session.get(CompanyRegionEntryLevel, "entry_legacy_sf").region_id == (
            "sf_bay_area"
        )
        assert session.get(RegionMarketScore, "score_legacy_sf").region_id == (
            "sf_bay_area"
        )
        assert session.get(OpportunityRegionBinding, "legacy_binding").region_id == (
            "sf_bay_area"
        )

        service = _current_service(session)
        canonical = service.list_opportunities(market="sf_bay_area", now=NOW)
        legacy = service.list_opportunities(market="greater_sf", now=NOW)
        assert [item.opportunity_id for item in canonical] == [opportunity_id]
        assert legacy == canonical
        detail = service.get_opportunity(opportunity_id, now=NOW)
        assert detail.market_id == "sf_bay_area"
        assert detail.market_public_slug == "san-francisco-bay-area"
        assert detail.original_market_id is None

        observation = session.execute(select(OpportunitySourceObservation)).scalar_one()
        assert observation.raw_payload["market_id"] == "greater_sf"
        preference = session.get(UserPreferenceProfile, "legacy_geo_user")
        saved = session.get(SavedMarketArtifact, "saved_legacy_sf")
        assert preference.preferred_regions == ["greater_sf", "sf_bay_area"]
        assert saved.artifact_ref == "greater_sf"
    finally:
        session.close()
        engine.dispose()


def test_0043_reconciles_canonical_current_opportunity_collision(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'active-geography-collision.db'}"
    legacy_opportunity_id = _prepare_0042_database(database_url, collision=True)

    upgrade_database(database_url)
    engine = make_engine(database_url)
    session = make_session_factory(engine)()
    try:
        rows = session.execute(select(CurrentOpportunity)).scalars().all()
        assert [row.current_opportunity_id for row in rows] == [
            "canonical_collision_survivor"
        ]
        survivor = rows[0]
        assert survivor.market_id == "sf_bay_area"
        assert survivor.source_count == 1
        assert any(
            warning.startswith(f"merged_active_geography:{legacy_opportunity_id}:")
            for warning in survivor.warnings
        )
        links = CurrentOpportunityRepository(session).list_source_links(
            survivor.current_opportunity_id
        )
        assert len(links) == 1
        assert links[0].current_opportunity_id == survivor.current_opportunity_id
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize(
    "supplied_region",
    ("sf_bay_area", "greater_sf", "san-francisco-bay-area", "Bay Area"),
)
def test_presence_writer_persists_final_active_region(session, supplied_region: str) -> None:
    _seed_redirect(session)
    company_id = f"company_{supplied_region}".replace("/", "_")
    session.add(
        Company(
            company_id=company_id,
            company_name=company_id,
            normalized_company_name=company_id,
        )
    )
    session.flush()
    row = PresenceService(
        PresenceRepository(session),
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
    ).create_presence(
        PresenceDefinition(
            presence_id=f"presence_{company_id}",
            company_id=company_id,
            region_id=supplied_region,
            evidence=PresenceEvidence(
                office_evidence_flag=True,
                operations_evidence_flag=True,
                hiring_evidence_flag=False,
            ),
        )
    )
    assert row.region_id == "sf_bay_area"


def test_adjacent_active_market_truth_writers_persist_final_region(session) -> None:
    _seed_redirect(session)
    session.add(
        Company(
            company_id="company_adjacent_writers",
            company_name="Adjacent Writers",
            normalized_company_name="adjacent writers",
            eligibility_status="eligible",
        )
    )
    session.flush()
    presence_repo = PresenceRepository(session)
    PresenceService(
        presence_repo,
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
    ).create_presence(
        PresenceDefinition(
            presence_id="presence_adjacent_writers",
            company_id="company_adjacent_writers",
            region_id="greater_sf",
            evidence=PresenceEvidence(
                office_evidence_flag=True,
                operations_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
        )
    )
    hiring_repo = HiringRepository(session)
    hiring = HiringService(
        hiring_repo,
        presence_repo=presence_repo,
    ).create_hiring(
        HiringDefinition(
            hiring_id="hiring_adjacent_writers",
            company_id="company_adjacent_writers",
            region_id="greater_sf",
            snapshot=HiringSnapshot(currently_hiring_flag=True),
        )
    )
    entry = EntryLevelService(
        EntryLevelRepository(session),
        hiring_repo=hiring_repo,
    ).create_entry_level(
        EntryLevelDefinition(
            entry_level_id="entry_adjacent_writers",
            company_id="company_adjacent_writers",
            region_id="greater_sf",
            snapshot=EntryLevelSnapshot(internship_count=1),
        )
    )
    score, _outcome = RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    ).upsert_for_recompute("greater_sf")

    assert hiring.region_id == "sf_bay_area"
    assert entry.region_id == "sf_bay_area"
    assert score.region_id == "sf_bay_area"


def test_active_writers_reject_unknown_and_ambiguous_regions(session) -> None:
    _seed_redirect(session)
    session.add_all(
        [
            Company(
                company_id="company_invalid_geo",
                company_name="Invalid Geo",
                normalized_company_name="invalid geo",
            ),
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
    presence_service = PresenceService(
        PresenceRepository(session),
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
    )
    evidence = PresenceEvidence(
        office_evidence_flag=True,
        operations_evidence_flag=True,
        hiring_evidence_flag=False,
    )
    with pytest.raises(MissingRegionForPresence):
        presence_service.create_presence(
            PresenceDefinition(
                presence_id="presence_unknown",
                company_id="company_invalid_geo",
                region_id="unknown market",
                evidence=evidence,
            )
        )
    with pytest.raises(GeographicInputAmbiguous):
        presence_service.create_presence(
            PresenceDefinition(
                presence_id="presence_ambiguous",
                company_id="company_invalid_geo",
                region_id="Springfield",
                evidence=evidence,
            )
        )

    opportunity_service = OpportunityService(OpportunityRepository(session))

    def request(region_id: str) -> OpportunityCreate:
        return OpportunityCreate(
            employer_name="Invalid Geography Employer",
            program_name=f"Program {region_id}",
            program_type="internship",
            application_url="https://jobs.example.com/invalid-geography",
            source_url="https://jobs.example.com/invalid-geography/source",
            source_type="employer_official",
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id=region_id,
                    region_label=region_id,
                ),
            ),
        )

    with pytest.raises(GeographicInputUnknown):
        opportunity_service.create_opportunity(request("unknown market"))
    with pytest.raises(GeographicInputAmbiguous):
        opportunity_service.create_opportunity(request("Springfield"))


@pytest.mark.parametrize(
    "supplied_region",
    ("sf_bay_area", "greater_sf", "san-francisco-bay-area", "Bay Area"),
)
def test_legacy_opportunity_binding_writer_persists_final_active_region(
    session,
    supplied_region: str,
) -> None:
    _seed_redirect(session)
    payload = OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id=f"opportunity_{supplied_region}".replace("/", "_"),
            employer_name="Canonical Employer",
            program_name=f"Program {supplied_region}",
            program_type="internship",
            application_url=f"https://jobs.example.com/{supplied_region}",
            source_url=f"https://jobs.example.com/source/{supplied_region}",
            source_type="employer_official",
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id=supplied_region,
                    region_label=supplied_region,
                ),
            ),
        )
    )
    assert payload.region_bindings[0].region_id == "sf_bay_area"
    assert payload.region_bindings[0].region_label == "San Francisco Bay Area"


def test_historical_saved_and_preferred_region_reads_emit_one_current_identity(session) -> None:
    _seed_redirect(session)
    session.add(User(user_id="historical_read_user"))
    session.flush()
    session.add_all(
        [
            UserPreferenceProfile(
                user_id="historical_read_user",
                preferred_regions=["greater_sf", "sf_bay_area"],
            ),
            SavedMarketArtifact(
                saved_artifact_id="historical_saved_region",
                user_id="historical_read_user",
                artifact_type="region",
                artifact_ref="greater_sf",
            ),
        ]
    )
    session.flush()
    service = UserPersonalizationPersistenceService(
        UserRepository(session), RegionRepository(session)
    )
    preferences = service.get_preference_profile("historical_read_user")
    saved = session.get(SavedMarketArtifact, "historical_saved_region")
    saved_output = _saved_artifact_data(saved, session=session)

    assert preferences.preferred_regions == ["sf_bay_area"]
    assert saved_output["artifact_ref"] == "sf_bay_area"
    assert saved_output["original_artifact_ref"] == "greater_sf"
    assert saved_output["region_identity"] == {
        "region_id": "sf_bay_area",
        "public_slug": "san-francisco-bay-area",
        "display_name": "San Francisco Bay Area",
    }
    assert saved.artifact_ref == "greater_sf"


def test_institutional_target_market_aggregation_converges_mixed_ids(session) -> None:
    _seed_redirect(session)
    profiles = [
        UserPreferenceProfile(user_id="student_a", preferred_regions=["greater_sf"]),
        UserPreferenceProfile(user_id="student_b", preferred_regions=["sf_bay_area"]),
    ]
    artifacts = [
        SavedMarketArtifact(
            saved_artifact_id="student_a_sf_save",
            user_id="student_a",
            artifact_type="region",
            artifact_ref="sf_bay_area",
        ),
        SavedMarketArtifact(
            saved_artifact_id="student_b_legacy_sf_save",
            user_id="student_b",
            artifact_type="region",
            artifact_ref="greater_sf",
        ),
    ]
    contributors, labels = _target_market_contributors(
        profiles,
        artifacts,
        region_labels={"sf_bay_area": "San Francisco Bay Area"},
        resolver=GeographicResolver(RegionRepository(session)),
    )
    assert contributors == {"sf_bay_area": {"student_a", "student_b"}}
    assert labels == {"sf_bay_area": "San Francisco Bay Area"}
