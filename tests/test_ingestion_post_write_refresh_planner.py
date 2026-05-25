from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.contracts import (
    CanonicalWriteExecutionDecision,
    CanonicalWriteExecutionResult,
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
    PostWriteRefreshPlanStatus,
    PostWriteRefreshTargetType,
    ProposalReviewStatus,
)
from backend.orchestration.jobs.models import Job
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
        parsing_notes="manual refresh planner test intake",
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


def _execute_plan(
    session: Session,
    plan: CanonicalWritePlan,
) -> CanonicalWriteExecutionResult:
    return _ingestion_service(session).execute_canonical_write_plan(
        plan,
        _approved_decision(plan),
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


def _target_types(plan) -> set[PostWriteRefreshTargetType]:
    return {target.target_type for target in plan.refresh_targets}


def test_refresh_target_vocabulary_covers_downstream_artifacts() -> None:
    expected = {
        "region_score",
        "company_score",
        "region_output",
        "company_output",
        "comparison_output",
        "contextual_output",
        "provenance_audit",
        "unknown_or_unsupported",
    }

    assert expected.issubset(PostWriteRefreshTargetType.values())
    assert {"planned", "no_op", "rejected", "unsupported", "failed"}.issubset(
        PostWriteRefreshPlanStatus.values()
    )


def test_cannot_plan_refresh_from_failed_rejected_or_unapproved_execution(
    session: Session,
) -> None:
    service = _ingestion_service(session)
    rejected = CanonicalWriteExecutionResult(
        plan_id="write_plan_rejected",
        raw_record_id="raw_rejected",
        status=CanonicalWriteExecutionStatus.REJECTED,
        target_entity_type="companies",
        target_identifier="comp_example",
    )
    blocked = rejected.model_copy(
        update={
            "plan_id": "write_plan_blocked",
            "raw_record_id": "raw_blocked",
            "status": CanonicalWriteExecutionStatus.BLOCKED,
        }
    )
    failed = rejected.model_copy(
        update={
            "plan_id": "write_plan_failed",
            "raw_record_id": "raw_failed",
            "status": CanonicalWriteExecutionStatus.FAILED,
        }
    )

    rejected_plan = service.plan_post_write_refresh(rejected)
    blocked_plan = service.plan_post_write_refresh(blocked)
    failed_plan = service.plan_post_write_refresh(failed)

    assert rejected_plan.status is PostWriteRefreshPlanStatus.REJECTED
    assert blocked_plan.status is PostWriteRefreshPlanStatus.FAILED
    assert failed_plan.status is PostWriteRefreshPlanStatus.FAILED
    assert rejected_plan.refresh_targets == ()
    assert blocked_plan.refresh_targets == ()
    assert failed_plan.refresh_targets == ()


def test_company_write_produces_dry_run_company_and_region_targets(
    session: Session,
) -> None:
    _seed_present_presence(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_company_refresh",
        intent=CanonicalFactIntent.COMPANY,
        payload={
            "company_id": "comp_example",
            "company_name": "Example",
            "sector_primary": "software",
        },
        fact_id="comp_example",
    )
    execution = _execute_plan(session, plan)

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert execution.status is CanonicalWriteExecutionStatus.EXECUTED
    assert refresh.status is PostWriteRefreshPlanStatus.PLANNED
    assert refresh.dry_run is True
    assert refresh.affected_company_ids == ("comp_example",)
    assert refresh.affected_region_ids == ("greater_boston",)
    assert {
        PostWriteRefreshTargetType.COMPANY_OUTPUT,
        PostWriteRefreshTargetType.REGION_SCORE,
        PostWriteRefreshTargetType.REGION_OUTPUT,
        PostWriteRefreshTargetType.PROVENANCE_AUDIT,
    }.issubset(_target_types(refresh))


def test_region_write_produces_region_refresh_targets(session: Session) -> None:
    _seed_company_region(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_region_refresh",
        intent=CanonicalFactIntent.REGION,
        payload={
            "region_id": "greater_boston",
            "region_name": "Greater Boston",
            "display_name": "Greater Boston Area",
            "region_type": "greater_region",
        },
        fact_id="greater_boston",
    )
    execution = _execute_plan(session, plan)

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.status is PostWriteRefreshPlanStatus.PLANNED
    assert refresh.affected_region_ids == ("greater_boston",)
    assert refresh.affected_company_ids == ()
    assert PostWriteRefreshTargetType.REGION_SCORE in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_OUTPUT in _target_types(refresh)
    assert PostWriteRefreshTargetType.COMPANY_OUTPUT not in _target_types(refresh)


def test_presence_write_produces_region_and_company_refresh_targets(
    session: Session,
) -> None:
    _seed_company_region(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_presence_refresh",
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
        fact_id="presence:comp_example:greater_boston",
    )
    execution = _execute_plan(session, plan)

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.affected_company_ids == ("comp_example",)
    assert refresh.affected_region_ids == ("greater_boston",)
    assert PostWriteRefreshTargetType.COMPANY_OUTPUT in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_SCORE in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_OUTPUT in _target_types(refresh)


def test_hiring_write_produces_region_and_company_refresh_targets(
    session: Session,
) -> None:
    _seed_present_presence(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_hiring_refresh",
        intent=CanonicalFactIntent.HIRING,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "currently_hiring_flag": True,
            "active_posting_count_now": 4,
        },
        fact_id="hiring:comp_example:greater_boston",
    )
    execution = _execute_plan(session, plan)

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.affected_company_ids == ("comp_example",)
    assert refresh.affected_region_ids == ("greater_boston",)
    assert PostWriteRefreshTargetType.COMPANY_OUTPUT in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_SCORE in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_OUTPUT in _target_types(refresh)


def test_entry_level_write_produces_region_and_company_refresh_targets(
    session: Session,
) -> None:
    _seed_hiring_dependency(session)
    plan = _approved_plan(
        session,
        raw_record_id="raw_entry_refresh",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 2,
        },
        fact_id="internships_coops:comp_example:greater_boston",
    )
    execution = _execute_plan(session, plan)

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.affected_company_ids == ("comp_example",)
    assert refresh.affected_region_ids == ("greater_boston",)
    assert PostWriteRefreshTargetType.COMPANY_OUTPUT in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_SCORE in _target_types(refresh)
    assert PostWriteRefreshTargetType.REGION_OUTPUT in _target_types(refresh)


def test_unsupported_execution_type_produces_diagnostic(session: Session) -> None:
    execution = CanonicalWriteExecutionResult(
        plan_id="write_plan_score_input",
        raw_record_id="raw_score_input",
        status=CanonicalWriteExecutionStatus.EXECUTED,
        target_entity_type="score_inputs",
        target_identifier="live_market_score",
        canonical_domain_mutated=True,
    )

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.status is PostWriteRefreshPlanStatus.UNSUPPORTED
    assert refresh.diagnostics[0].code == "unsupported_refresh_mapping"
    assert refresh.refresh_targets[0].target_type is (
        PostWriteRefreshTargetType.UNKNOWN_OR_UNSUPPORTED
    )


def test_refresh_plan_does_not_run_refreshes_audits_or_schedules(
    session: Session,
) -> None:
    plan = _approved_plan(
        session,
        raw_record_id="raw_company_no_refresh",
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
        fact_id="comp_example",
    )
    execution = _execute_plan(session, plan)
    before = (
        session.query(RegionMarketScore).count(),
        session.query(OutputMetadata).count(),
        session.query(Job).count(),
        session.query(FactSourceLink).count(),
    )

    refresh = _ingestion_service(session).plan_post_write_refresh(execution)

    assert refresh.status is PostWriteRefreshPlanStatus.PLANNED
    assert execution.downstream_refresh_triggered is False
    assert before == (
        session.query(RegionMarketScore).count(),
        session.query(OutputMetadata).count(),
        session.query(Job).count(),
        session.query(FactSourceLink).count(),
    )


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
    assert session.query(Company).count() > 0
    assert session.query(Region).count() > 0
