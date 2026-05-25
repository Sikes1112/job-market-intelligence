from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.contracts import (
    IntakeProvenanceDefinition,
    ProposalReviewDecision,
    ProposalReviewResult,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import (
    CanonicalFactIntent,
    CanonicalWriteOperationType,
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
from backend.shared.provenance import (
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
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
        parsing_notes="manual planner test intake",
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


def _approved_source_linked_proposal(
    session: Session,
    *,
    raw_record_id: str = "raw_manual_1",
    intent: CanonicalFactIntent = CanonicalFactIntent.PRESENCE,
    payload: dict | None = None,
    fact_id: str | None = None,
) -> tuple:
    if payload is None:
        payload = {
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        }
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
    return proposal, review


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


def test_cannot_plan_write_without_approved_linked_proposal(session: Session) -> None:
    proposal, review = _approved_source_linked_proposal(session)
    unlinked_review = ProposalReviewResult(
        raw_record_id=review.raw_record_id,
        proposed_fact_id=review.proposed_fact_id,
        fact_type=review.fact_type,
        approval_status=ProposalReviewStatus.APPROVED_FOR_LINKING,
        reviewer_note="approved but not linked",
        source_id=review.source_id,
        observation_id=review.observation_id,
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(
        proposal,
        unlinked_review,
    )

    assert plan.status is CanonicalWritePlanStatus.FAILED
    assert any(d.code == "proposal_not_source_linked" for d in plan.diagnostics)
    assert plan.operations == ()


def test_cannot_plan_write_from_rejected_proposal(session: Session) -> None:
    proposal, _review = _approved_source_linked_proposal(session)
    rejected_review = ProposalReviewResult(
        raw_record_id=proposal.raw_record_id,
        proposed_fact_id=proposal.fact_id,
        fact_type=proposal.fact_type,
        approval_status=ProposalReviewStatus.REJECTED,
        reviewer_note="rejected by operator",
        source_id=proposal.source_id,
        observation_id=proposal.observation_id,
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(
        proposal,
        rejected_review,
    )

    assert plan.status is CanonicalWritePlanStatus.REJECTED
    assert plan.operations == ()
    assert any(d.code == "proposal_rejected" for d in plan.diagnostics)


def test_valid_company_proposal_produces_dry_run_create_plan(session: Session) -> None:
    proposal, review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_company",
        intent=CanonicalFactIntent.COMPANY,
        payload={
            "company_id": "comp_example",
            "company_name": "Example",
            "sector_primary": "ai",
        },
        fact_id="comp_example",
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.dry_run is True
    assert plan.status is CanonicalWritePlanStatus.PLANNED
    [operation] = plan.operations
    assert operation.operation_type is CanonicalWriteOperationType.CREATE
    assert operation.target_entity_type == "companies"
    assert operation.target_identifier == "comp_example"
    assert operation.proposed_field_changes["company_name"] == "Example"
    assert operation.proposed_field_changes["normalized_company_name"] == "example"
    assert session.query(Company).count() == 0


def test_valid_region_proposal_produces_dry_run_update_plan(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="Greater Boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    proposal, review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_region",
        intent=CanonicalFactIntent.REGION,
        payload={
            "region_id": "greater_boston",
            "region_name": "Greater Boston",
            "display_name": "Greater Boston Area",
            "region_type": "greater_region",
        },
        fact_id="greater_boston",
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.status is CanonicalWritePlanStatus.PLANNED
    [operation] = plan.operations
    assert operation.operation_type is CanonicalWriteOperationType.UPDATE
    assert operation.target_entity_type == "regions"
    assert operation.target_identifier == "greater_boston"
    assert operation.proposed_field_changes == {
        "display_name": "Greater Boston Area"
    }
    assert session.get(Region, "greater_boston").display_name == "Greater Boston"


def test_presence_proposal_produces_dry_run_plan(session: Session) -> None:
    proposal, review = _approved_source_linked_proposal(session)

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.status is CanonicalWritePlanStatus.PLANNED
    [operation] = plan.operations
    assert operation.operation_type is CanonicalWriteOperationType.CREATE
    assert operation.target_entity_type == "company_region_presence"
    assert operation.proposed_field_changes["presence_status"] == "present"


def test_hiring_proposal_preserves_unknown_vs_zero(session: Session) -> None:
    proposal, review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_hiring_unknown",
        intent=CanonicalFactIntent.HIRING,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "currently_hiring_flag": True,
            "active_posting_count_now": None,
        },
        fact_id="hiring:comp_example:greater_boston",
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    [operation] = plan.operations
    assert operation.proposed_field_changes["active_posting_count_now"] is None
    assert operation.value_statuses["active_posting_count_now"] == (
        ObservationStatus.UNKNOWN.value
    )
    assert any(
        d.code == "count_value_not_planned_as_zero"
        and d.field_name == "active_posting_count_now"
        for d in operation.diagnostics
    )


def test_entry_level_plans_preserve_not_collected_and_stale(
    session: Session,
) -> None:
    internship_proposal, internship_review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_internship",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 2,
        },
        fact_id="internships_coops:comp_example:greater_boston",
    )
    early_proposal, early_review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_early",
        intent=CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "entry_level_full_time_count": 4,
            "entry_level_full_time_count_freshness_status": "stale",
        },
        fact_id="early_career_programs:comp_example:greater_boston",
    )

    internship_plan = _ingestion_service(session).plan_canonical_fact_write(
        internship_proposal,
        internship_review,
    )
    early_plan = _ingestion_service(session).plan_canonical_fact_write(
        early_proposal,
        early_review,
    )

    internship_op = internship_plan.operations[0]
    assert internship_op.proposed_field_changes["coop_count"] is None
    assert internship_op.value_statuses["coop_count"] == (
        ObservationStatus.NOT_COLLECTED.value
    )
    early_op = early_plan.operations[0]
    assert early_op.proposed_field_changes["entry_level_full_time_count"] is None
    assert early_op.value_statuses["entry_level_full_time_count"] == (
        ObservationStatus.STALE.value
    )


def test_zero_write_is_planned_only_with_zero_observed_basis(
    session: Session,
) -> None:
    without_basis_proposal, without_basis_review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_zero_without_basis",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
        },
        fact_id="internships_coops:comp_example:greater_boston",
    )
    with_basis_proposal, with_basis_review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_zero_with_basis",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
            "internship_count_observed_basis": True,
        },
        fact_id="internships_coops:comp_example:greater_boston",
    )

    without_basis_plan = _ingestion_service(session).plan_canonical_fact_write(
        without_basis_proposal,
        without_basis_review,
    )
    with_basis_plan = _ingestion_service(session).plan_canonical_fact_write(
        with_basis_proposal,
        with_basis_review,
    )

    without_basis_op = without_basis_plan.operations[0]
    assert without_basis_op.proposed_field_changes["internship_count"] is None
    assert without_basis_op.value_statuses["internship_count"] == (
        ObservationStatus.UNKNOWN.value
    )
    with_basis_op = with_basis_plan.operations[0]
    assert with_basis_op.proposed_field_changes["internship_count"] == 0
    assert with_basis_op.value_statuses["internship_count"] == (
        ObservationStatus.ZERO_OBSERVED.value
    )


def test_conflicting_proposed_value_requires_manual_review(session: Session) -> None:
    _seed_company_region(session)
    session.add(
        CompanyRegionPresence(
            presence_id="p_existing",
            company_id="comp_example",
            region_id="greater_boston",
            presence_status="not_present",
        )
    )
    session.flush()
    proposal, review = _approved_source_linked_proposal(session)

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.status is CanonicalWritePlanStatus.REQUIRES_MANUAL_REVIEW
    [operation] = plan.operations
    assert operation.operation_type is CanonicalWriteOperationType.REQUIRES_MANUAL_REVIEW
    assert any(
        d.code == "existing_value_conflict" and d.field_name == "presence_status"
        for d in operation.diagnostics
    )
    assert session.get(CompanyRegionPresence, "p_existing").presence_status == (
        "not_present"
    )


def test_unsupported_score_input_mapping_yields_diagnostic_not_crash(
    session: Session,
) -> None:
    proposal, review = _approved_source_linked_proposal(
        session,
        raw_record_id="raw_score_input",
        intent=CanonicalFactIntent.SCORE_INPUT,
        payload={
            "score_input_name": "live_market_score",
            "source_fact_category": "hiring_counts",
            "value": 0.7,
        },
        fact_id="live_market_score",
    )

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.status is CanonicalWritePlanStatus.UNSUPPORTED
    assert plan.manual_review_required is True
    assert any(d.code == "unsupported_mapping" for d in plan.diagnostics)


def test_dry_run_planning_does_not_mutate_canonical_scoring_or_outputs(
    session: Session,
) -> None:
    proposal, review = _approved_source_linked_proposal(session)

    plan = _ingestion_service(session).plan_canonical_fact_write(proposal, review)

    assert plan.dry_run is True
    assert session.query(Company).count() == 0
    assert session.query(Region).count() == 0
    assert session.query(CompanyRegionPresence).count() == 0
    assert session.query(CompanyRegionHiring).count() == 0
    assert session.query(CompanyRegionEntryLevel).count() == 0
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0
    assert session.query(FactSourceLink).count() == 1


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
