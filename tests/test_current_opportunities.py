from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_decisions.models import CareerDecision
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.companies.models import Company
from backend.current_opportunities.adapters import StaticOpportunityAdapter
from backend.current_opportunities.models import (
    CurrentOpportunity,
    CurrentOpportunityIdentityEvidence,
    OpportunityPromotionReceipt,
    OpportunitySourceObservation,
)
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    AcquisitionMethod,
    AcquisitionRecordStatus,
    AcquisitionRunStatus,
    AllowedUseClassification,
    CoverageStatus,
    LicenseTermsClassification,
    OpportunityCoverageInput,
    OpportunityKind,
    OpportunitySourceType,
    SourceRegistryInput,
    SourceTrustClassification,
)
from backend.current_opportunities.service import (
    CurrentOpportunityService,
    OpportunitySourceNotFound,
)
from backend.deep_decisions.models import LongitudinalContextSnapshot, StrategicCareerReview
from backend.geography.models import Region
from backend.users.models import User

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|current_opps_user") -> dict[str, str]:
    return {
        "X-Verified-OIDC-Claims": json.dumps(
            {
                "iss": "https://jmi.us.auth0.com/",
                "sub": subject,
                "email": "current@example.com",
                "email_verified": True,
                "name": "Current User",
            }
        )
    }


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Company(
                company_id="comp_acme",
                company_name="Acme Robotics",
                normalized_company_name="acme robotics",
                sector_primary="software",
            ),
        ]
    )
    session.flush()


def _service(session: Session) -> CurrentOpportunityService:
    return CurrentOpportunityService(CurrentOpportunityRepository(session))


def _source(
    source_id: str = "src_employer",
    *,
    enabled: bool = True,
    ranking: bool = True,
    display: bool = True,
    freshness_sla_hours: int = 48,
) -> SourceRegistryInput:
    return SourceRegistryInput(
        source_id=source_id,
        provider="Acme",
        display_name="Acme Careers API",
        source_type=OpportunitySourceType.API,
        acquisition_method=AcquisitionMethod.API_PULL,
        enabled=enabled,
        allowed_use=AllowedUseClassification.ALLOWED,
        license_terms=LicenseTermsClassification.PERMISSIVE,
        trust=SourceTrustClassification.HIGH,
        freshness_sla_hours=freshness_sla_hours,
        supported_markets=("greater_boston",),
        supported_opportunity_types=(OpportunityKind.JOB,),
        ranking_use_allowed=ranking,
        display_use_allowed=display,
        provenance_requirements=("provider_record_id", "observed_at"),
    )


def _coverage(
    status: CoverageStatus = CoverageStatus.PRODUCTION_READY,
    *,
    market_key: str = "greater_boston",
    role_family: str = "software_engineering",
    opportunity_type: str = "job",
) -> OpportunityCoverageInput:
    return OpportunityCoverageInput(
        coverage_id=f"cov_{market_key}_{role_family}_{opportunity_type}",
        market_key=market_key,
        market_id=market_key if market_key != "*" else None,
        market_label="Greater Boston" if market_key == "greater_boston" else None,
        role_family=role_family,
        opportunity_type=opportunity_type,
        status=status,
        rationale="Deterministic test coverage contract.",
        source_basis={"sources": ["src_employer"]},
        minimum_expected_sources=1,
        freshness_max_age_hours=72,
        last_evaluated_at=NOW,
    )


def _record(provider_id: str = "job-1", **overrides):
    payload = {
        "provider_record_id": provider_id,
        "observed_at": NOW,
        "collected_at": NOW,
        "raw_payload": {
            "provider_record_id": provider_id,
            "company_name": "Acme Robotics",
            "title": "Software Engineer I",
            "role_family": "software_engineering",
            "seniority_level": "entry_level",
            "market_id": "greater_boston",
            "location": "Greater Boston hybrid",
            "work_arrangement": "hybrid",
            "employment_type": "full_time",
            "opportunity_type": "job",
            "posting_date": "2026-09-01",
            "application_url": f"https://jobs.acme.example/apply/{provider_id}",
            "source_url": f"https://jobs.acme.example/jobs/{provider_id}",
            "compensation_min": 100000,
            "compensation_max": 120000,
            "compensation_interval": "annual",
            "skills": ["Python", "Cloud"],
            "requirements": ["Entry-level software experience"],
            "description": "Build cloud systems with Python.",
        },
    }
    payload.update(overrides)
    return payload


def test_source_governance_fails_closed_and_unknown_sources_reject(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)

    with pytest.raises(ValueError):
        SourceRegistryInput(
            source_id="bad",
            provider="Unknown",
            display_name="Unknown",
            source_type=OpportunitySourceType.API,
            acquisition_method=AcquisitionMethod.API_PULL,
            allowed_use=AllowedUseClassification.UNKNOWN,
            license_terms=LicenseTermsClassification.UNKNOWN,
            trust=SourceTrustClassification.UNKNOWN,
            ranking_use_allowed=True,
        )

    with pytest.raises(ValueError):
        SourceRegistryInput(
            source_id="display_bad",
            provider="Unknown",
            display_name="Unknown Display Source",
            source_type=OpportunitySourceType.API,
            acquisition_method=AcquisitionMethod.API_PULL,
            allowed_use=AllowedUseClassification.INTERNAL_ONLY,
            license_terms=LicenseTermsClassification.UNKNOWN,
            trust=SourceTrustClassification.MEDIUM,
            display_use_allowed=True,
        )

    service.upsert_source(_source(enabled=False))
    run = service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_disabled",
        idempotency_key="disabled",
        now=NOW,
    )
    assert run.status == AcquisitionRunStatus.REJECTED
    assert run.failure_details["reason"] == "source_disabled"

    with pytest.raises(OpportunitySourceNotFound):
        service.refresh_source(
            StaticOpportunityAdapter(source_id="missing", records=(), collected_at=NOW),
            run_id="run_missing",
            now=NOW,
        )


def test_refresh_normalizes_promotes_and_is_idempotent(session: Session) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())

    adapter = StaticOpportunityAdapter(
        source_id="src_employer",
        records=(_record(), _record()),
        collected_at=NOW,
    )
    run = service.refresh_source(adapter, run_id="run_1", idempotency_key="same_run", now=NOW)
    replay = service.refresh_source(adapter, run_id="run_1", idempotency_key="same_run", now=NOW)

    assert run.status == AcquisitionRunStatus.COMPLETED
    assert replay.run_id == run.run_id
    assert run.acquired_count == 2
    assert run.normalized_count == 1
    assert run.promoted_count == 1
    assert run.duplicate_count == 1
    assert len(session.execute(select(OpportunitySourceObservation)).scalars().all()) == 1

    opportunities = service.list_opportunities(now=NOW)
    assert len(opportunities) == 1
    item = opportunities[0]
    assert item.company_id == "comp_acme"
    assert item.role_family == "software_engineering"
    assert item.work_arrangement == "hybrid"
    assert item.freshness_state == "fresh"
    assert item.ranking_eligible is True
    assert "raw_payload" not in json.dumps(item.model_dump(mode="json"))


def test_runtime_policy_rejects_internal_only_source_even_if_db_state_is_invalid(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    source = CurrentOpportunityRepository(session).get_source("src_employer")
    assert source is not None
    source.allowed_use = AllowedUseClassification.INTERNAL_ONLY.value
    session.flush()

    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_internal_only",
        idempotency_key="internal_only",
        now=NOW,
    )

    row = session.execute(select(CurrentOpportunity)).scalar_one()
    assert row.ranking_eligible is False
    assert "source_allowed_use_not_permitted" in row.ranking_ineligible_reasons
    assert service.list_opportunities(include_ineligible=True, now=NOW) == ()


def test_display_governance_filters_public_opportunity_surfaces(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source(display=False, ranking=False))
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_display_blocked",
        idempotency_key="display_blocked",
        now=NOW,
    )

    row = session.execute(select(CurrentOpportunity)).scalar_one()

    assert service.list_opportunities(include_ineligible=True, now=NOW) == ()
    assert service.strategic_matches("user_display", include_ineligible=True, now=NOW) == ()

    response = api_client.get(
        "/current-opportunities",
        headers=_auth_headers(),
        params={"include_ineligible": True},
    )
    assert response.status_code == 200
    assert response.json()["data"]["opportunities"] == []

    detail = api_client.get(
        f"/current-opportunities/{row.current_opportunity_id}",
        headers=_auth_headers(),
    )
    assert detail.status_code == 404


def test_malformed_payload_is_quarantined_without_canonical_write(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())

    run = service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(
                _record(
                    status=AcquisitionRecordStatus.MALFORMED,
                    error_code="bad_shape",
                    raw_payload={"unexpected": "shape"},
                ),
            ),
            collected_at=NOW,
        ),
        run_id="run_malformed",
        idempotency_key="malformed",
        now=NOW,
    )

    assert run.rejected_count == 1
    assert session.execute(select(CurrentOpportunity)).scalars().all() == []
    observation = session.execute(select(OpportunitySourceObservation)).scalar_one()
    assert observation.normalization_status == "invalid"
    assert observation.raw_payload == {"unexpected": "shape"}


def test_adapter_failure_isolated_from_successful_source(session: Session) -> None:
    class FailingAdapter:
        source_id = "src_bad"

        def acquire(self, *, run_id, checkpoint=None):  # noqa: ANN001
            raise RuntimeError("upstream timeout")

    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source("src_bad"))
    service.upsert_source(_source("src_employer"))
    service.upsert_coverage(_coverage())

    result = service.refresh_sources(
        (
            FailingAdapter(),
            StaticOpportunityAdapter(
                source_id="src_employer",
                records=(_record(),),
                collected_at=NOW,
            ),
        ),
        now=NOW,
    )

    statuses = {run.source_id: run.status for run in result.runs}
    assert statuses["src_bad"] == AcquisitionRunStatus.FAILED
    assert statuses["src_employer"] == AcquisitionRunStatus.COMPLETED
    assert len(session.execute(select(CurrentOpportunity)).scalars().all()) == 1


def test_source_staleness_uses_observation_age_not_recent_failed_run(
    session: Session,
) -> None:
    class FailingAdapter:
        source_id = "src_employer"

        def acquire(self, *, run_id, checkpoint=None):  # noqa: ANN001
            raise RuntimeError("upstream timeout")

    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source(freshness_sla_hours=48))
    service.upsert_coverage(_coverage())
    old_time = NOW - timedelta(days=7)
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(_record(observed_at=old_time, collected_at=old_time),),
            collected_at=old_time,
        ),
        run_id="run_old_observation",
        idempotency_key="old_observation",
        now=old_time,
    )
    service.refresh_source(
        FailingAdapter(),
        run_id="run_recent_failure",
        idempotency_key="recent_failure",
        now=NOW,
    )

    diagnostics = service.diagnostics(now=NOW)
    stale = next(item for item in diagnostics if item.code == "stale_source")
    assert stale.evidence["age_hours"] >= 168
    assert stale.evidence["last_observed_at"].startswith("2026-08-26T12:00:00")
    assert "failed_refresh" in {item.code for item in diagnostics}


def test_promotion_failure_rolls_back_observations_and_canonical_rows(
    session: Session,
) -> None:
    class ExplodingReceiptRepository(CurrentOpportunityRepository):
        def add(self, row: object) -> None:
            if isinstance(row, OpportunityPromotionReceipt):
                raise RuntimeError("receipt write failed")
            super().add(row)

    _seed_market(session)
    repo = ExplodingReceiptRepository(session)
    service = CurrentOpportunityService(repo)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())

    run = service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_rollback",
        idempotency_key="rollback",
        now=NOW,
    )

    assert run.status == AcquisitionRunStatus.FAILED
    assert run.failure_details["stage"] == "promotion"
    assert session.execute(select(CurrentOpportunity)).scalars().all() == []
    assert session.execute(select(OpportunitySourceObservation)).scalars().all() == []


def test_changed_payload_updates_without_faking_freshness(session: Session) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_initial",
        idempotency_key="initial",
        now=NOW,
    )
    changed = _record(
        compensation_min=110000,
        raw_payload={**_record()["raw_payload"], "compensation_min": 110000},
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(changed,),
            collected_at=NOW + timedelta(hours=1),
        ),
        run_id="run_changed",
        idempotency_key="changed",
        now=NOW + timedelta(hours=1),
    )
    row = session.execute(select(CurrentOpportunity)).scalar_one()
    row.updated_at = NOW + timedelta(days=30)
    payload = service.get_opportunity(
        row.current_opportunity_id,
        now=NOW + timedelta(hours=80),
    )

    assert payload.compensation_min == 110000
    assert payload.freshness_state == "stale"
    assert payload.ranking_eligible is False
    assert "freshness_stale" in payload.ranking_ineligible_reasons


def test_provider_stable_geography_upgrades_but_does_not_degrade_or_reassign(
    session: Session,
) -> None:
    _seed_market(session)
    session.add(
        Region(
            region_id="chicago",
            region_name="chicago",
            display_name="Chicago",
            region_type="metro",
        )
    )
    session.flush()
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())

    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(_record("stable-job"),),
            collected_at=NOW,
        ),
        run_id="run_geo_resolved",
        idempotency_key="geo-resolved",
        now=NOW,
    )
    original = session.execute(select(CurrentOpportunity)).scalar_one()
    original_id = original.current_opportunity_id

    unresolved_record = _record(
        "stable-job",
        raw_payload={
            **_record("stable-job")["raw_payload"],
            "market_id": "mystery_market",
            "location": "Somewhere uncertain",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(unresolved_record,),
            collected_at=NOW + timedelta(hours=1),
        ),
        run_id="run_geo_unresolved",
        idempotency_key="geo-unresolved",
        now=NOW + timedelta(hours=1),
    )

    rows = session.execute(select(CurrentOpportunity)).scalars().all()
    assert len(rows) == 1
    assert rows[0].current_opportunity_id == original_id
    assert rows[0].market_id == "greater_boston"
    assert rows[0].location_resolution_status == "resolved"
    assert rows[0].location_text == "Somewhere uncertain"
    link = CurrentOpportunityRepository(session).get_source_link(
        source_id="src_employer",
        provider_record_id="stable-job",
    )
    assert link is not None
    assert link.current_opportunity_id == original_id
    latest_observation = session.get(
        OpportunitySourceObservation,
        link.latest_observation_id,
    )
    assert latest_observation is not None
    assert latest_observation.normalized_payload["location_resolution_status"] == "unresolved"

    conflicting_record = _record(
        "stable-job",
        raw_payload={
            **_record("stable-job")["raw_payload"],
            "market_id": "chicago",
            "location": "Chicago",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(conflicting_record,),
            collected_at=NOW + timedelta(hours=2),
        ),
        run_id="run_geo_conflict",
        idempotency_key="geo-conflict",
        now=NOW + timedelta(hours=2),
    )
    session.refresh(rows[0])
    assert rows[0].market_id == "greater_boston"
    assert any(
        warning == "resolved_geography_conflict:greater_boston:chicago"
        for warning in rows[0].warnings
    )

    initially_unknown = _record(
        "upgrade-job",
        raw_payload={
            **_record("upgrade-job")["raw_payload"],
            "market_id": "mystery_market",
            "location": "Unknown",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(initially_unknown,),
            collected_at=NOW + timedelta(hours=3),
        ),
        run_id="run_geo_initially_unknown",
        idempotency_key="geo-initially-unknown",
        now=NOW + timedelta(hours=3),
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(_record("upgrade-job"),),
            collected_at=NOW + timedelta(hours=4),
        ),
        run_id="run_geo_upgrade",
        idempotency_key="geo-upgrade",
        now=NOW + timedelta(hours=4),
    )
    upgraded_link = CurrentOpportunityRepository(session).get_source_link(
        source_id="src_employer",
        provider_record_id="upgrade-job",
    )
    assert upgraded_link is not None
    upgraded = session.get(CurrentOpportunity, upgraded_link.current_opportunity_id)
    assert upgraded is not None
    assert upgraded.market_id == "greater_boston"
    assert upgraded.location_resolution_status == "resolved"


def test_geography_conflict_can_be_authoritatively_corrected_with_audit_history(
    session: Session,
) -> None:
    _seed_market(session)
    session.add(
        Region(
            region_id="chicago",
            region_name="chicago",
            display_name="Chicago",
            region_type="metro",
        )
    )
    session.flush()
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer", records=(_record("correct-me"),), collected_at=NOW
        ),
        run_id="run_correction_a",
        idempotency_key="correction-a",
        now=NOW,
    )
    conflicting = _record(
        "correct-me",
        raw_payload={
            **_record("correct-me")["raw_payload"],
            "market_id": "chicago",
            "location": "Chicago",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(conflicting,),
            collected_at=NOW + timedelta(hours=1),
        ),
        run_id="run_correction_b",
        idempotency_key="correction-b",
        now=NOW + timedelta(hours=1),
    )

    evidence = session.execute(
        select(CurrentOpportunityIdentityEvidence).where(
            CurrentOpportunityIdentityEvidence.geography_review_status == "pending"
        )
    ).scalar_one()
    pending = service.pending_geography_conflicts()
    assert pending == (
        {
            "identity_evidence_id": evidence.identity_evidence_id,
            "opportunity_id": evidence.current_opportunity_id,
            "source_id": "src_employer",
            "provider_record_id": "correct-me",
            "previous_region_id": "greater_boston",
            "candidate_region_id": "chicago",
            "review_status": "pending",
            "created_at": evidence.created_at.isoformat(),
        },
    )
    corrected = service.authorize_geography_correction(
        evidence.identity_evidence_id,
        corrected_region="chicago",
        reason="Provider confirmed the role moved to Chicago.",
        operator_id="operator-1",
        reviewed_at=NOW + timedelta(hours=2),
    )

    assert corrected.market_id == "chicago"
    assert corrected.location_resolution_source == "authorized_correction"
    assert "|chicago|" in corrected.canonical_identity_key
    assert evidence.geography_previous_region_id == "greater_boston"
    assert evidence.geography_candidate_region_id == "chicago"
    assert evidence.geography_corrected_region_id == "chicago"
    assert evidence.geography_reviewed_by == "operator-1"
    assert evidence.geography_review_reason == "Provider confirmed the role moved to Chicago."
    assert service.pending_geography_conflicts() == ()
    observation = session.get(
        OpportunitySourceObservation,
        evidence.source_observation_id,
    )
    assert observation is not None
    assert observation.normalized_payload["market_id"] == "chicago"


def test_provider_native_id_reuse_retires_unsupported_old_opportunity(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer", records=(_record("reused-id"),), collected_at=NOW
        ),
        run_id="run_reuse_old",
        idempotency_key="reuse-old",
        now=NOW,
    )
    old = session.execute(select(CurrentOpportunity)).scalar_one()

    replacement = _record(
        "reused-id",
        raw_payload={
            **_record("reused-id")["raw_payload"],
            "title": "Product Manager",
            "role_family": "product",
            "application_url": "https://jobs.acme.example/apply/reused-id-v2",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer",
            records=(replacement,),
            collected_at=NOW + timedelta(hours=1),
        ),
        run_id="run_reuse_new",
        idempotency_key="reuse-new",
        now=NOW + timedelta(hours=1),
    )

    rows = session.execute(
        select(CurrentOpportunity).order_by(CurrentOpportunity.created_at)
    ).scalars().all()
    assert len(rows) == 2
    session.refresh(old)
    assert old.canonical_status == "closed"
    assert old.ranking_eligible is False
    assert "no_active_source_links" in old.ranking_ineligible_reasons
    assert "source_link_reassigned" in old.warnings
    link = CurrentOpportunityRepository(session).get_source_link(
        source_id="src_employer",
        provider_record_id="reused-id",
    )
    assert link is not None
    assert link.current_opportunity_id != old.current_opportunity_id
    replacement_row = session.get(CurrentOpportunity, link.current_opportunity_id)
    assert replacement_row is not None
    assert replacement_row.canonical_status == "active"


def test_cross_source_duplicates_and_low_confidence_potential_duplicates(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source("src_employer"))
    service.upsert_source(_source("src_feed"))
    service.upsert_coverage(_coverage())

    service.refresh_source(
        StaticOpportunityAdapter(
            source_id="src_employer", records=(_record("job-1"),), collected_at=NOW
        ),
        run_id="run_a",
        idempotency_key="a",
        now=NOW,
    )
    duplicate = _record(
        "feed-9",
        raw_payload={
            **_record("feed-9")["raw_payload"],
            "application_url": "https://feed.example/apply/9",
        },
    )
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_feed", records=(duplicate,), collected_at=NOW),
        run_id="run_b",
        idempotency_key="b",
        now=NOW,
    )
    assert len(session.execute(select(CurrentOpportunity)).scalars().all()) == 1
    assert service.list_opportunities(now=NOW)[0].provenance["source_count"] == 2

    similar = _record(
        "feed-10",
        raw_payload={**_record("feed-10")["raw_payload"], "title": "Software Engineer II"},
    )
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_feed", records=(similar,), collected_at=NOW),
        run_id="run_c",
        idempotency_key="c",
        now=NOW,
    )
    rows = session.execute(select(CurrentOpportunity)).scalars().all()
    assert len(rows) == 2
    evidence = session.execute(
        select(CurrentOpportunityIdentityEvidence).where(
            CurrentOpportunityIdentityEvidence.provider_record_id == "feed-10"
        )
    ).scalar_one()
    assert evidence.resolution_status == "potential_duplicate"
    assert evidence.confidence == "low"


def test_removed_and_reappearing_source_record_lifecycle(session: Session) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_active",
        idempotency_key="active",
        now=NOW,
    )
    opportunity_id = session.execute(select(CurrentOpportunity.current_opportunity_id)).scalar_one()

    removed = _record(status=AcquisitionRecordStatus.REMOVED)
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(removed,), collected_at=NOW),
        run_id="run_removed",
        idempotency_key="removed",
        now=NOW,
    )
    assert service.get_opportunity(opportunity_id, now=NOW).status == "closed"

    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_reappeared",
        idempotency_key="reappeared",
        now=NOW,
    )
    assert service.get_opportunity(opportunity_id, now=NOW).status == "active"


def test_coverage_and_diagnostics_distinguish_unsupported_from_empty(
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    unsupported = service.coverage(
        market_key="unknown_market",
        role_family="software_engineering",
        opportunity_type="job",
        now=NOW,
    )
    assert unsupported.effective_status == CoverageStatus.UNSUPPORTED
    assert "unknown combinations fail closed" in unsupported.limitations
    assert any(item.code == "missing_expected_sources" for item in service.diagnostics(now=NOW))

    service.upsert_source(_source(ranking=False))
    service.upsert_coverage(_coverage(CoverageStatus.EXPERIMENTAL))
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_ineligible",
        idempotency_key="ineligible",
        now=NOW,
    )
    diagnostics = service.diagnostics(now=NOW + timedelta(hours=100))
    codes = {item.code for item in diagnostics}
    assert "ranking_degradation_no_eligible_opportunities" in codes
    assert "stale_source" in codes
    assert "low_coverage" in codes


def test_strategic_matching_uses_identity_decision_and_strategy_context(
    session: Session,
) -> None:
    _seed_market(session)
    session.add(User(user_id="user_match"))
    session.flush()
    identity = CareerIdentity(
        career_identity_id="identity_match",
        user_id="user_match",
        current_version=1,
        completeness_state="partial",
        sufficiency_state="sufficient",
        privacy_visibility="private",
        downstream_personalization_consent_granted=True,
    )
    session.add(identity)
    session.flush()
    session.add_all(
        [
            CareerIdentityFact(
                career_identity_fact_id="fact_skill",
                career_identity_id="identity_match",
                user_id="user_match",
                fact_type="skill",
                normalized_key="python",
                state="explicit",
                payload={"name": "Python"},
                provenance={},
            ),
            CareerIdentityFact(
                career_identity_fact_id="fact_region",
                career_identity_id="identity_match",
                user_id="user_match",
                fact_type="geographic_constraint",
                normalized_key="greater_boston",
                state="explicit",
                payload={"location": "Greater Boston"},
                provenance={},
            ),
            CareerDecision(
                decision_id="decision_match",
                user_id="user_match",
                career_identity_id="identity_match",
                decision_type="job_search_strategy",
                status="evaluating",
                title="Find a software engineering job in Boston",
                priorities=["software_engineering"],
                constraints=["hybrid"],
            ),
            LongitudinalContextSnapshot(
                longitudinal_context_id="long_match",
                user_id="user_match",
                decision_id="decision_match",
                window_end=NOW,
                record_count=1,
                context_payload={},
                evidence_payload={},
                generated_at=NOW,
            ),
            StrategicCareerReview(
                strategic_review_id="review_match",
                user_id="user_match",
                decision_id="decision_match",
                longitudinal_context_id="long_match",
                window_end=NOW,
                goals={"target_role": "software engineering"},
                strategy_performance={"route": "Boston cloud roles"},
                suggested_next_actions=["Prioritize Python cloud opportunities"],
                confidence="medium",
                uncertainty="bounded_test_context",
                generated_at=NOW,
            ),
        ]
    )
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_match",
        idempotency_key="match",
        now=NOW,
    )

    matches = service.strategic_matches(
        "user_match",
        decision_id="decision_match",
        now=NOW,
    )
    assert matches
    assert matches[0].strategic_relevance == "direct_fit"
    assert matches[0].ranking_eligible is True
    assert "career identity and decision term overlap" in matches[0].contributing_factors


def test_strategic_matching_does_not_read_unconsented_career_identity(
    session: Session,
) -> None:
    _seed_market(session)
    session.add(User(user_id="user_match_no_consent"))
    session.flush()
    session.add(
        CareerIdentity(
            career_identity_id="identity_match_no_consent",
            user_id="user_match_no_consent",
            current_version=1,
            completeness_state="partial",
            sufficiency_state="sufficient",
            privacy_visibility="private",
            downstream_personalization_consent_granted=False,
        )
    )
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="private_fact_no_consent",
            career_identity_id="identity_match_no_consent",
            user_id="user_match_no_consent",
            fact_type="skill",
            normalized_key="python",
            state="explicit",
            payload={"name": "Python"},
            provenance={},
        )
    )
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage())
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_match_no_consent",
        idempotency_key="match_no_consent",
        now=NOW,
    )

    matches = service.strategic_matches("user_match_no_consent", now=NOW)
    assert matches
    assert "career identity and decision term overlap" not in (
        matches[0].contributing_factors
    )
    assert matches[0].strategic_relevance == "weak_fit"


def test_current_opportunity_api_auth_filters_and_payload_safety(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    service = _service(session)
    service.upsert_source(_source())
    service.upsert_coverage(_coverage().model_copy(update={"last_evaluated_at": datetime.now(UTC)}))
    service.refresh_source(
        StaticOpportunityAdapter(source_id="src_employer", records=(_record(),), collected_at=NOW),
        run_id="run_api",
        idempotency_key="api",
        now=NOW,
    )

    assert api_client.get("/current-opportunities").status_code == 401
    response = api_client.get(
        "/current-opportunities",
        headers=_auth_headers(),
        params={"role_family": "software_engineering", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["opportunities"]) == 1
    opportunity_id = body["opportunities"][0]["opportunity_id"]
    assert "raw_payload" not in json.dumps(body)

    detail = api_client.get(
        f"/current-opportunities/{opportunity_id}",
        headers=_auth_headers(),
    )
    assert detail.status_code == 200
    coverage = api_client.get(
        "/current-opportunities/coverage",
        headers=_auth_headers(),
        params={
            "market_key": "greater_boston",
            "role_family": "software_engineering",
            "opportunity_type": "job",
        },
    )
    assert coverage.status_code == 200
    assert coverage.json()["data"]["effective_status"] == "production_ready"

    api_client.get("/me", headers=_auth_headers("auth0|operator"))
    operator = session.execute(select(User).where(User.user_id.like("user_%"))).scalars().all()[-1]
    operator.admin_role = "data_reviewer"
    session.flush()
    diagnostics = api_client.get(
        "/current-opportunities/diagnostics",
        headers=_auth_headers("auth0|operator"),
    )
    assert diagnostics.status_code == 200
    assert "diagnostics" in diagnostics.json()["data"]
