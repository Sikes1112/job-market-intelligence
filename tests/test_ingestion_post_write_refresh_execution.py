from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.ingestion.contracts import (
    PostWriteRefreshExecutionDecision,
    PostWriteRefreshPlan,
    PostWriteRefreshTarget,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import (
    PostWriteRefreshExecutionStatus,
    PostWriteRefreshPlanStatus,
    PostWriteRefreshTargetType,
)
from backend.orchestration.jobs.models import Job
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from seeds import mvp_seed

_NOW = datetime(2026, 5, 21, 12, tzinfo=UTC)


def _service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _seed_company_region(session: Session) -> None:
    session.add(
        Company(
            company_id="comp_example",
            company_name="Example",
            normalized_company_name="example",
            eligibility_status="eligible",
            prestige_score=0.7,
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
    session.add(
        CompanyRegionPresence(
            presence_id="presence_existing",
            company_id="comp_example",
            region_id="greater_boston",
            presence_status="present",
        )
    )
    session.flush()


def _plan(
    *,
    refresh_plan_id: str = "refresh_plan_manual",
    status: PostWriteRefreshPlanStatus = PostWriteRefreshPlanStatus.PLANNED,
    targets: tuple[PostWriteRefreshTarget, ...],
) -> PostWriteRefreshPlan:
    return PostWriteRefreshPlan(
        refresh_plan_id=refresh_plan_id,
        execution_plan_id="write_plan_manual",
        raw_record_id="raw_manual",
        changed_canonical_entity_type="company_region_presence",
        changed_canonical_entity_id="presence_existing",
        affected_region_ids=("greater_boston",),
        affected_company_ids=("comp_example",),
        status=status,
        refresh_targets=targets,
        dry_run=True,
    )


def _decision(
    plan: PostWriteRefreshPlan,
    *,
    approved: bool = True,
    expected_target_count: int | None = None,
) -> PostWriteRefreshExecutionDecision:
    return PostWriteRefreshExecutionDecision(
        refresh_plan_id=plan.refresh_plan_id or "missing_refresh_plan_id",
        approved=approved,
        operator_note="operator approved synchronous refresh execution",
        rejection_reason=None if approved else "operator rejected refresh",
        decided_at=_NOW,
        expected_target_count=expected_target_count,
    )


def _region_score_target() -> PostWriteRefreshTarget:
    return PostWriteRefreshTarget(
        target_type=PostWriteRefreshTargetType.REGION_SCORE,
        target_id="greater_boston",
        region_id="greater_boston",
        reason="test region score refresh",
    )


def _region_output_target() -> PostWriteRefreshTarget:
    return PostWriteRefreshTarget(
        target_type=PostWriteRefreshTargetType.REGION_OUTPUT,
        target_id="greater_boston",
        region_id="greater_boston",
        reason="test region output refresh",
    )


def _company_output_target() -> PostWriteRefreshTarget:
    return PostWriteRefreshTarget(
        target_type=PostWriteRefreshTargetType.COMPANY_OUTPUT,
        target_id="comp_example",
        company_id="comp_example",
        reason="test company output refresh",
    )


def test_cannot_execute_refresh_without_explicit_approval(session: Session) -> None:
    _seed_company_region(session)
    plan = _plan(targets=(_region_score_target(),))

    result = _service(session).execute_post_write_refresh_plan(
        plan,
        _decision(plan, approved=False),
    )

    assert result.status is PostWriteRefreshExecutionStatus.REJECTED
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_rejected_refresh_decision_does_not_refresh(session: Session) -> None:
    _seed_company_region(session)
    plan = _plan(targets=(_region_output_target(),))

    result = _service(session).execute_post_write_refresh_plan(
        plan,
        _decision(plan, approved=False),
    )

    assert result.status is PostWriteRefreshExecutionStatus.REJECTED
    assert session.query(OutputMetadata).count() == 0


def test_invalid_failed_or_no_op_plan_does_not_refresh(session: Session) -> None:
    _seed_company_region(session)
    service = _service(session)
    failed = _plan(
        refresh_plan_id="refresh_plan_failed",
        status=PostWriteRefreshPlanStatus.FAILED,
        targets=(_region_score_target(),),
    )
    rejected = _plan(
        refresh_plan_id="refresh_plan_rejected",
        status=PostWriteRefreshPlanStatus.REJECTED,
        targets=(_region_output_target(),),
    )
    no_op = _plan(
        refresh_plan_id="refresh_plan_no_op",
        status=PostWriteRefreshPlanStatus.NO_OP,
        targets=(),
    )

    assert service.execute_post_write_refresh_plan(
        failed, _decision(failed)
    ).status is PostWriteRefreshExecutionStatus.BLOCKED
    assert service.execute_post_write_refresh_plan(
        rejected, _decision(rejected)
    ).status is PostWriteRefreshExecutionStatus.BLOCKED
    assert service.execute_post_write_refresh_plan(
        no_op, _decision(no_op)
    ).status is PostWriteRefreshExecutionStatus.NO_OP
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_approved_region_score_target_refreshes_score(session: Session) -> None:
    _seed_company_region(session)
    plan = _plan(targets=(_region_score_target(),))

    result = _service(session).execute_post_write_refresh_plan(plan, _decision(plan))

    assert result.status is PostWriteRefreshExecutionStatus.EXECUTED
    assert result.scores_refreshed_count == 1
    score = session.query(RegionMarketScore).one()
    assert score.region_id == "greater_boston"
    assert result.target_results[0].refreshed_artifact_id == score.region_score_id


def test_approved_region_output_target_rebuilds_region_output(
    session: Session,
) -> None:
    _seed_company_region(session)
    score_plan = _plan(
        refresh_plan_id="refresh_plan_score_first",
        targets=(_region_score_target(),),
    )
    _service(session).execute_post_write_refresh_plan(score_plan, _decision(score_plan))
    output_plan = _plan(
        refresh_plan_id="refresh_plan_region_output",
        targets=(_region_output_target(),),
    )

    result = _service(session).execute_post_write_refresh_plan(
        output_plan,
        _decision(output_plan),
    )

    assert result.status is PostWriteRefreshExecutionStatus.EXECUTED
    assert result.outputs_refreshed_count == 1
    row = session.query(OutputMetadata).one()
    assert row.output_type == OutputType.REGION_OUTPUT.value
    assert row.subject_id == "greater_boston"


def test_approved_company_output_target_rebuilds_company_output(
    session: Session,
) -> None:
    _seed_company_region(session)
    plan = _plan(targets=(_company_output_target(),))

    result = _service(session).execute_post_write_refresh_plan(plan, _decision(plan))

    assert result.status is PostWriteRefreshExecutionStatus.EXECUTED
    assert result.outputs_refreshed_count == 1
    row = session.query(OutputMetadata).one()
    assert row.output_type == OutputType.COMPANY_OUTPUT.value
    assert row.subject_id == "comp_example"


def test_unsupported_comparison_contextual_and_audit_targets_return_diagnostics(
    session: Session,
) -> None:
    _seed_company_region(session)
    plan = _plan(
        targets=(
            PostWriteRefreshTarget(
                target_type=PostWriteRefreshTargetType.COMPARISON_OUTPUT,
                target_id="greater_boston__greater_sf",
                reason="comparison dependency mapping deferred",
            ),
            PostWriteRefreshTarget(
                target_type=PostWriteRefreshTargetType.CONTEXTUAL_OUTPUT,
                target_id="greater_boston__greater_sf",
                reason="contextual dependency mapping deferred",
            ),
            PostWriteRefreshTarget(
                target_type=PostWriteRefreshTargetType.PROVENANCE_AUDIT,
                target_id="presence_existing",
                reason="audit remains diagnostic",
            ),
        ),
    )

    result = _service(session).execute_post_write_refresh_plan(plan, _decision(plan))
    codes = {
        diagnostic.code
        for target_result in result.target_results
        for diagnostic in target_result.diagnostics
    }

    assert result.status is PostWriteRefreshExecutionStatus.PARTIAL
    assert "refresh_target_unsupported" in codes
    assert "provenance_audit_refresh_deferred" in codes
    assert session.query(OutputMetadata).count() == 0


def test_refresh_execution_does_not_enqueue_or_create_ingestion_or_provenance(
    session: Session,
) -> None:
    _seed_company_region(session)
    plan = _plan(
        targets=(
            _region_score_target(),
            _region_output_target(),
            _company_output_target(),
        ),
    )
    before = (
        session.query(Job).count(),
        session.query(RawIngestionRecord).count(),
        session.query(FactSourceLink).count(),
        session.query(SourceRef).count(),
        session.query(SourceObservation).count(),
    )

    result = _service(session).execute_post_write_refresh_plan(plan, _decision(plan))

    assert result.jobs_enqueued is False
    assert result.schedules_created is False
    assert result.external_data_collected is False
    assert before == (
        session.query(Job).count(),
        session.query(RawIngestionRecord).count(),
        session.query(FactSourceLink).count(),
        session.query(SourceRef).count(),
        session.query(SourceObservation).count(),
    )


def test_repeated_refresh_execution_is_deterministic(session: Session) -> None:
    _seed_company_region(session)
    plan = _plan(
        targets=(
            _region_score_target(),
            _region_output_target(),
            _company_output_target(),
        ),
    )
    service = _service(session)

    first = service.execute_post_write_refresh_plan(plan, _decision(plan))
    second = service.execute_post_write_refresh_plan(plan, _decision(plan))

    assert first.status is PostWriteRefreshExecutionStatus.EXECUTED
    assert second.status is PostWriteRefreshExecutionStatus.NO_OP
    assert session.query(RegionMarketScore).count() == 1
    assert session.query(OutputMetadata).count() == 2
    assert all(
        target.status is PostWriteRefreshExecutionStatus.NO_OP
        for target in second.target_results
    )


def test_refresh_plan_id_and_target_count_must_match(session: Session) -> None:
    _seed_company_region(session)
    plan = _plan(targets=(_region_score_target(),))

    wrong_id = PostWriteRefreshExecutionDecision(
        refresh_plan_id="wrong_refresh_plan",
        approved=True,
        operator_note="bad id",
        decided_at=_NOW,
    )
    wrong_count = PostWriteRefreshExecutionDecision(
        refresh_plan_id=plan.refresh_plan_id or "missing_refresh_plan_id",
        approved=True,
        operator_note="bad count",
        decided_at=_NOW,
        expected_target_count=2,
    )

    assert _service(session).execute_post_write_refresh_plan(
        plan, wrong_id
    ).status is PostWriteRefreshExecutionStatus.BLOCKED
    assert _service(session).execute_post_write_refresh_plan(
        plan, wrong_count
    ).status is PostWriteRefreshExecutionStatus.BLOCKED
    assert session.query(RegionMarketScore).count() == 0


def test_demo_seed_and_full_demo_path_remain_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    assert session.get(SourceRef, "mvp_demo_seed") is not None
    assert session.query(Company).count() > 0
    assert session.query(Region).count() > 0
