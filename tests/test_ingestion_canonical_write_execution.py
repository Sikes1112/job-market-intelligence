from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.contracts import (
    CanonicalWriteExecutionDecision,
    CanonicalWritePlan,
    IntakeProvenanceDefinition,
    ProposalReviewDecision,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import (
    CanonicalFactIntent,
    CanonicalWriteExecutionStatus,
    CanonicalWritePlanStatus,
    ProposalReviewStatus,
)
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import ProvenanceService
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import DataOrigin, LicenseTermsCategory, SourceType
from seeds import mvp_seed

_NOW = datetime(2026, 5, 21, 12, tzinfo=UTC)


def _ingestion_service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _provenance_service(session: Session) -> ProvenanceService:
    return ProvenanceService(ProvenanceRepository(session))


def _raw_definition(
    *,
    raw_record_id: str,
    intent: CanonicalFactIntent,
    payload: dict,
) -> RawIntakeDefinition:
    return RawIntakeDefinition(
        raw_record_id=raw_record_id,
        provider_id="manual_research",
        source_type=SourceType.MANUAL_RESEARCH,
        source_name="Operator supplied observation",
        url_or_provider="manual://operator",
        external_entity_id=raw_record_id,
        raw_payload=RawObservationPayload(body=payload),
        collected_at=_NOW,
        observed_at=_NOW,
        intended_fact_type=intent,
        parsing_notes="manual execution test intake",
    )


def _attachment_definition(
    *,
    raw_record_id: str,
    source_id: str,
    observation_id: str,
) -> IntakeProvenanceDefinition:
    return IntakeProvenanceDefinition(
        raw_record_id=raw_record_id,
        source_id=source_id,
        observation_id=observation_id,
        source_type=SourceType.COMPANY_OFFICIAL,
        source_name="Example Careers",
        url_or_provider="https://example.test/careers",
        collected_at=_NOW,
        observed_at=_NOW,
        license_or_terms_category=LicenseTermsCategory.PUBLIC,
        confidence=Confidence.HIGH,
        data_origin=DataOrigin.REAL_OBSERVED,
        notes="operator reviewed source metadata",
    )


def _approved_plan(
    session: Session,
    *,
    raw_record_id: str,
    intent: CanonicalFactIntent,
    payload: dict,
    fact_id: str | None = None,
) -> CanonicalWritePlan:
    service = _ingestion_service(session)
    service.create_raw_record(
        _raw_definition(
            raw_record_id=raw_record_id,
            intent=intent,
            payload=payload,
        )
    )
    result = service.normalize_raw_record(
        raw_record_id,
        normalizer=ManualObservationNormalizer(),
    )
    source_id = f"source_{raw_record_id}"
    observation_id = f"observation_{raw_record_id}"
    service.attach_provenance_from_normalized_intake(
        _attachment_definition(
            raw_record_id=raw_record_id,
            source_id=source_id,
            observation_id=observation_id,
        ),
        provenance_service=_provenance_service(session),
    )
    proposal = service.propose_canonical_fact(
        raw_record_id=raw_record_id,
        fact_id=(
            fact_id
            or (result.observation.proposed_fact_id if result.observation else None)
            or raw_record_id
        ),
    )
    review = service.review_and_link_canonical_fact_proposal(
        proposal,
        ProposalReviewDecision(
            status=ProposalReviewStatus.APPROVED_FOR_LINKING,
            reviewer_note="operator approved source link",
        ),
        provenance_service=_provenance_service(session),
    )
    return service.plan_canonical_fact_write(proposal, review)


def _approved_decision(plan: CanonicalWritePlan) -> CanonicalWriteExecutionDecision:
    return CanonicalWriteExecutionDecision(
        plan_id=plan.plan_id,
        approved=True,
        operator_note="operator approved canonical write execution",
        decided_at=_NOW,
    )


def _seed_company_region(session: Session) -> None:
    session.add(
        Company(
            company_id="comp_example",
            company_name="Example",
            normalized_company_name="example",
        )
    )
    session.add(
        Region(
            region_id="greater_boston",
            region_name="Greater Boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_present_presence(session: Session) -> None:
    _seed_company_region(session)
    session.add(
        CompanyRegionPresence(
            presence_id="presence_existing",
            company_id="comp_example",
            region_id="greater_boston",
            presence_status="present",
        )
    )
    session.flush()


def _seed_hiring_dependency(session: Session) -> None:
    _seed_present_presence(session)
    session.add(
        CompanyRegionHiring(
            hiring_id="hiring_existing",
            company_id="comp_example",
            region_id="greater_boston",
            currently_hiring_flag=True,
        )
    )
    session.flush()


def test_cannot_execute_without_explicit_approval(session: Session) -> None:
    plan = _approved_plan(
        session,
        raw_record_id="raw_company",
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
        fact_id="comp_example",
    )

    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        CanonicalWriteExecutionDecision(
            plan_id=plan.plan_id,
            approved=False,
            rejection_reason="operator declined execution",
            decided_at=_NOW,
        ),
    )

    assert result.status is CanonicalWriteExecutionStatus.REJECTED
    assert result.canonical_domain_mutated is False
    assert session.query(Company).count() == 0


def test_rejected_execution_decision_creates_no_canonical_write(
    session: Session,
) -> None:
    plan = _approved_plan(
        session,
        raw_record_id="raw_region",
        intent=CanonicalFactIntent.REGION,
        payload={
            "region_id": "greater_boston",
            "region_name": "Greater Boston",
            "display_name": "Greater Boston",
            "region_type": "greater_region",
        },
        fact_id="greater_boston",
    )

    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        CanonicalWriteExecutionDecision(
            plan_id=plan.plan_id,
            approved=False,
            rejection_reason="operator rejected write",
            decided_at=_NOW,
        ),
    )

    assert result.status is CanonicalWriteExecutionStatus.REJECTED
    assert session.query(Region).count() == 0


def test_cannot_execute_unsupported_rejected_or_failed_plan(
    session: Session,
) -> None:
    unsupported = _approved_plan(
        session,
        raw_record_id="raw_score",
        intent=CanonicalFactIntent.SCORE_INPUT,
        payload={
            "score_input_name": "live_market_score",
            "source_fact_category": "hiring_counts",
            "value": 0.7,
        },
        fact_id="live_market_score",
    )
    rejected = _approved_plan(
        session,
        raw_record_id="raw_company",
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
        fact_id="comp_example",
    ).model_copy(update={"status": CanonicalWritePlanStatus.REJECTED})
    failed = rejected.model_copy(update={"status": CanonicalWritePlanStatus.FAILED})

    for plan in (unsupported, rejected, failed):
        result = _ingestion_service(session).execute_canonical_write_plan(
            plan,
            _approved_decision(plan),
        )
        assert result.status is CanonicalWriteExecutionStatus.BLOCKED

    assert session.query(Company).count() == 0
    assert session.query(RegionMarketScore).count() == 0


def test_cannot_execute_requires_manual_review_plan_without_override(
    session: Session,
) -> None:
    _seed_company_region(session)
    session.add(
        CompanyRegionPresence(
            presence_id="presence_existing",
            company_id="comp_example",
            region_id="greater_boston",
            presence_status="not_present",
        )
    )
    session.flush()
    plan = _approved_plan(
        session,
        raw_record_id="raw_presence_conflict",
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
        fact_id="presence:comp_example:greater_boston",
    )

    assert plan.status is CanonicalWritePlanStatus.REQUIRES_MANUAL_REVIEW
    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        _approved_decision(plan),
    )

    assert result.status is CanonicalWriteExecutionStatus.BLOCKED
    assert session.get(CompanyRegionPresence, "presence_existing").presence_status == (
        "not_present"
    )


def test_approved_company_create_and_update_write_canonical_row(
    session: Session,
) -> None:
    create_plan = _approved_plan(
        session,
        raw_record_id="raw_company_create",
        intent=CanonicalFactIntent.COMPANY,
        payload={
            "company_id": "comp_example",
            "company_name": "Example",
            "sector_primary": "ai",
        },
        fact_id="comp_example",
    )

    created = _ingestion_service(session).execute_canonical_write_plan(
        create_plan,
        _approved_decision(create_plan),
    )

    assert created.status is CanonicalWriteExecutionStatus.EXECUTED
    company = session.get(Company, "comp_example")
    assert company is not None
    assert company.company_name == "Example"
    assert company.sector_primary == "ai"

    update_plan = _approved_plan(
        session,
        raw_record_id="raw_company_update",
        intent=CanonicalFactIntent.COMPANY,
        payload={
            "company_id": "comp_example",
            "company_name": "Example",
            "sector_primary": "software",
        },
        fact_id="comp_example",
    )
    updated = _ingestion_service(session).execute_canonical_write_plan(
        update_plan,
        _approved_decision(update_plan),
    )

    assert updated.status is CanonicalWriteExecutionStatus.EXECUTED
    assert session.get(Company, "comp_example").sector_primary == "software"


def test_approved_region_create_and_update_write_canonical_row(
    session: Session,
) -> None:
    create_plan = _approved_plan(
        session,
        raw_record_id="raw_region_create",
        intent=CanonicalFactIntent.REGION,
        payload={
            "region_id": "greater_boston",
            "region_name": "Greater Boston",
            "display_name": "Greater Boston",
            "region_type": "greater_region",
        },
        fact_id="greater_boston",
    )

    created = _ingestion_service(session).execute_canonical_write_plan(
        create_plan,
        _approved_decision(create_plan),
    )

    assert created.status is CanonicalWriteExecutionStatus.EXECUTED
    assert session.get(Region, "greater_boston").display_name == "Greater Boston"

    update_plan = _approved_plan(
        session,
        raw_record_id="raw_region_update",
        intent=CanonicalFactIntent.REGION,
        payload={
            "region_id": "greater_boston",
            "region_name": "Greater Boston",
            "display_name": "Greater Boston Area",
            "region_type": "greater_region",
        },
        fact_id="greater_boston",
    )
    updated = _ingestion_service(session).execute_canonical_write_plan(
        update_plan,
        _approved_decision(update_plan),
    )

    assert updated.status is CanonicalWriteExecutionStatus.EXECUTED
    assert session.get(Region, "greater_boston").display_name == (
        "Greater Boston Area"
    )


def test_approved_presence_write_preserves_provenance_trace(
    session: Session,
) -> None:
    _seed_company_region(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_presence",
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
        fact_id="presence:comp_example:greater_boston",
    )

    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        _approved_decision(plan),
    )

    assert result.status is CanonicalWriteExecutionStatus.EXECUTED
    presence = session.query(CompanyRegionPresence).one()
    assert presence.presence_status == "present"
    assert presence.source_refs[0]["fact_source_link_id"] == plan.provenance_link_id
    assert session.get(FactSourceLink, plan.provenance_link_id) is not None


def test_approved_hiring_and_entry_level_writes_preserve_unknowns_and_zeroes(
    session: Session,
) -> None:
    _seed_present_presence(session)
    hiring_plan = _approved_plan(
        session,
        raw_record_id="raw_hiring",
        intent=CanonicalFactIntent.HIRING,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "currently_hiring_flag": True,
            "active_posting_count_now": None,
        },
        fact_id="hiring:comp_example:greater_boston",
    )

    hiring_result = _ingestion_service(session).execute_canonical_write_plan(
        hiring_plan,
        _approved_decision(hiring_plan),
    )

    assert hiring_result.status is CanonicalWriteExecutionStatus.EXECUTED
    hiring = session.query(CompanyRegionHiring).one()
    assert hiring.active_posting_count_now is None
    assert hiring.source_refs[0]["fact_source_link_id"] == hiring_plan.provenance_link_id

    entry_plan = _approved_plan(
        session,
        raw_record_id="raw_entry",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
            "internship_count_observed_basis": True,
        },
        fact_id="internships_coops:comp_example:greater_boston",
    )
    entry_result = _ingestion_service(session).execute_canonical_write_plan(
        entry_plan,
        _approved_decision(entry_plan),
    )

    assert entry_result.status is CanonicalWriteExecutionStatus.EXECUTED
    entry = session.query(CompanyRegionEntryLevel).one()
    assert entry.internship_count == 0
    assert entry.coop_count is None
    assert entry.source_refs[0]["fact_source_link_id"] == entry_plan.provenance_link_id


def test_stale_values_do_not_create_fake_zeroes(session: Session) -> None:
    _seed_hiring_dependency(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_entry_stale",
        intent=CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "entry_level_full_time_count": 4,
            "entry_level_full_time_count_freshness_status": "stale",
        },
        fact_id="early_career_programs:comp_example:greater_boston",
    )

    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        _approved_decision(plan),
    )

    assert result.status is CanonicalWriteExecutionStatus.EXECUTED
    entry = session.query(CompanyRegionEntryLevel).one()
    assert entry.entry_level_full_time_count is None


def test_repeated_execution_is_idempotent_already_applied(session: Session) -> None:
    plan = _approved_plan(
        session,
        raw_record_id="raw_company_idempotent",
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
        fact_id="comp_example",
    )
    service = _ingestion_service(session)

    first = service.execute_canonical_write_plan(plan, _approved_decision(plan))
    version_after_first = session.get(Company, "comp_example").version
    second = service.execute_canonical_write_plan(plan, _approved_decision(plan))
    version_after_second = session.get(Company, "comp_example").version

    assert first.status is CanonicalWriteExecutionStatus.EXECUTED
    assert second.status is CanonicalWriteExecutionStatus.ALREADY_APPLIED
    assert version_after_second == version_after_first
    assert session.query(Company).count() == 1


def test_execution_does_not_trigger_scoring_or_outputs(session: Session) -> None:
    plan = _approved_plan(
        session,
        raw_record_id="raw_company_no_refresh",
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
        fact_id="comp_example",
    )

    result = _ingestion_service(session).execute_canonical_write_plan(
        plan,
        _approved_decision(plan),
    )

    assert result.downstream_refresh_triggered is False
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_demo_seed_and_existing_demo_path_remain_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
    assert session.query(Company).count() > 0
    assert session.query(Region).count() > 0
