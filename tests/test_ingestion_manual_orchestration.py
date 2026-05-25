from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.ingestion.contracts import (
    CanonicalWriteExecutionDecision,
    ManualIngestionRunRequest,
    PostWriteRefreshExecutionDecision,
    ProposalReviewDecision,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import (
    CanonicalFactIntent,
    CanonicalWriteExecutionStatus,
    ManualIngestionRunMode,
    ManualIngestionRunStatus,
)
from backend.orchestration.jobs.models import Job
from backend.outputs.models import OutputMetadata
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import ProvenanceService
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from seeds import mvp_seed

_NOW = datetime(2026, 5, 21, 12, tzinfo=UTC)


def _service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _provenance_service(session: Session) -> ProvenanceService:
    return ProvenanceService(ProvenanceRepository(session))


def _review_decision(*, override: bool = True) -> ProposalReviewDecision:
    return ProposalReviewDecision(
        reviewer_note="operator reviewed manual source",
        override_manual_review=override,
    )


def _write_decision(plan_id: str, *, approved: bool = True) -> CanonicalWriteExecutionDecision:
    return CanonicalWriteExecutionDecision(
        plan_id=plan_id,
        approved=approved,
        operator_note="operator approved canonical write",
        rejection_reason=None if approved else "operator rejected canonical write",
        decided_at=_NOW,
    )


def _refresh_decision(
    refresh_or_write_plan_id: str,
    *,
    approved: bool = True,
    expected_target_count: int | None = None,
) -> PostWriteRefreshExecutionDecision:
    return PostWriteRefreshExecutionDecision(
        refresh_plan_id=refresh_or_write_plan_id,
        approved=approved,
        operator_note="operator approved refresh execution",
        rejection_reason=None if approved else "operator rejected refresh",
        decided_at=_NOW,
        expected_target_count=expected_target_count,
    )


def _company_observation(
    raw_record_id: str,
    company_id: str = "comp_example",
    *,
    source_type: SourceType = SourceType.MANUAL_RESEARCH,
) -> dict:
    return {
        "raw_record_id": raw_record_id,
        "source_name": "Operator Research",
        "url_or_provider": "manual://operator/company",
        "source_type": source_type.value,
        "collected_at": _NOW,
        "observed_at": _NOW,
        "intended_fact_type": CanonicalFactIntent.COMPANY.value,
        "raw_payload": {
            "company_id": company_id,
            "company_name": "Example",
            "sector_primary": "software",
        },
        "confidence": Confidence.HIGH.value,
        "license_or_terms_category": LicenseTermsCategory.PUBLIC.value,
        "notes": "operator supplied company observation",
    }


def _internship_observation(raw_record_id: str) -> dict:
    return {
        "raw_record_id": raw_record_id,
        "source_name": "Operator Research",
        "url_or_provider": "manual://operator/internships",
        "source_type": SourceType.MANUAL_RESEARCH.value,
        "collected_at": _NOW,
        "observed_at": _NOW,
        "intended_fact_type": CanonicalFactIntent.INTERNSHIPS_COOPS.value,
        "raw_payload": {
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
        },
        "confidence": Confidence.MEDIUM.value,
        "license_or_terms_category": LicenseTermsCategory.PUBLIC.value,
    }


def test_default_run_mode_is_dry_run_only() -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_default")
    )

    assert request.mode is ManualIngestionRunMode.DRY_RUN_ONLY


def test_dry_run_only_does_not_execute_writes_or_refreshes(
    session: Session,
) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_dry_run")
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.mode is ManualIngestionRunMode.DRY_RUN_ONLY
    assert result.status is ManualIngestionRunStatus.COMPLETED_WITH_WARNINGS
    assert result.canonical_proposal is not None
    assert result.proposal_review_result is None
    assert result.write_execution_result is None
    assert result.refresh_execution_result is None
    assert session.query(Company).count() == 0
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_disallowed_source_stops_safely_with_diagnostics(session: Session) -> None:
    observation = _company_observation("raw_disallowed")
    observation["source_type"] = SourceType.LLM_GENERATED.value
    request = ManualIngestionRunRequest(manual_observation=observation)

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.status is ManualIngestionRunStatus.FAILED
    assert result.adapter_result is not None
    assert result.raw_records_created == ()
    assert session.query(RawIngestionRecord).count() == 0
    assert any(d.code == "adapter_output_not_usable" for d in result.diagnostics)


def test_malformed_payload_stops_safely_with_diagnostics(session: Session) -> None:
    observation = _company_observation("raw_malformed")
    observation["raw_payload"] = {"company_id": "comp_example"}
    request = ManualIngestionRunRequest(manual_observation=observation)

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.status is ManualIngestionRunStatus.STOPPED
    assert result.normalization_result is not None
    assert result.provenance_attachment_result is None
    assert any(d.code == "normalization_not_usable" for d in result.diagnostics)
    assert session.query(SourceRef).count() == 0


def test_unknown_zero_semantics_survive_orchestration(session: Session) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_internship_observation("raw_unknown_zero")
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    payload = result.normalization_result.normalized_payload
    assert payload["internship_count"] is None
    assert payload["internship_count_status"] == ObservationStatus.UNKNOWN.value
    assert session.query(Company).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_manual_review_required_state_is_surfaced_not_overridden(
    session: Session,
) -> None:
    observation = _company_observation("raw_manual_review")
    observation["raw_payload"]["requires_manual_review"] = True
    request = ManualIngestionRunRequest(manual_observation=observation)

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert "manual_review_required" in codes
    assert result.proposal_review_result is None
    assert session.query(FactSourceLink).count() == 0


def test_link_only_can_create_fact_source_link_with_review_approval(
    session: Session,
) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_link_only"),
        mode=ManualIngestionRunMode.LINK_ONLY,
        review_decision=_review_decision(),
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.status is ManualIngestionRunStatus.COMPLETED_WITH_WARNINGS
    assert result.proposal_review_result is not None
    assert result.proposal_review_result.fact_source_link_id is not None
    assert result.write_plan is not None
    assert session.query(FactSourceLink).count() == 1
    assert session.query(Company).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_link_only_does_not_mutate_canonical_domain_tables(session: Session) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_link_no_domain"),
        mode=ManualIngestionRunMode.LINK_ONLY,
        review_decision=_review_decision(),
    )

    _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert session.query(Company).count() == 0
    assert session.query(Region).count() == 0
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_execute_write_with_approval_requires_explicit_write_approval(
    session: Session,
) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation(
            "raw_write_requires_approval",
            source_type=SourceType.COMPANY_OFFICIAL,
        ),
        mode=ManualIngestionRunMode.EXECUTE_WRITE_WITH_APPROVAL,
        review_decision=_review_decision(),
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.status is ManualIngestionRunStatus.STOPPED
    assert result.write_plan is not None
    assert result.write_execution_result is None
    assert any(
        d.code == "write_execution_decision_required" for d in result.diagnostics
    )
    assert session.query(Company).count() == 0


def test_execute_write_with_approval_writes_only_when_approval_supplied(
    session: Session,
) -> None:
    base_request = ManualIngestionRunRequest(
        manual_observation=_company_observation(
            "raw_write_approved",
            source_type=SourceType.COMPANY_OFFICIAL,
        ),
        mode=ManualIngestionRunMode.EXECUTE_WRITE_WITH_APPROVAL,
        review_decision=_review_decision(),
    )
    preview = _service(session).run_manual_ingestion(
        base_request,
        provenance_service=_provenance_service(session),
    )
    request = base_request.model_copy(
        update={"write_execution_decision": _write_decision(preview.write_plan.plan_id)}
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.write_execution_result is not None
    assert result.write_execution_result.status is CanonicalWriteExecutionStatus.EXECUTED
    assert result.refresh_plan is not None
    assert result.refresh_execution_result is None
    assert session.query(Company).count() == 1
    assert session.query(OutputMetadata).count() == 0


def test_execute_write_with_approval_produces_refresh_plan_but_no_refresh(
    session: Session,
) -> None:
    base_request = ManualIngestionRunRequest(
        manual_observation=_company_observation(
            "raw_write_refresh_plan",
            source_type=SourceType.COMPANY_OFFICIAL,
        ),
        mode=ManualIngestionRunMode.EXECUTE_WRITE_WITH_APPROVAL,
        review_decision=_review_decision(),
    )
    preview = _service(session).run_manual_ingestion(
        base_request,
        provenance_service=_provenance_service(session),
    )
    request = base_request.model_copy(
        update={"write_execution_decision": _write_decision(preview.write_plan.plan_id)}
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.refresh_plan is not None
    assert result.refresh_execution_result is None
    assert session.query(OutputMetadata).count() == 0
    assert session.query(Job).count() == 0


def test_execute_write_and_refresh_requires_separate_refresh_approval(
    session: Session,
) -> None:
    base_request = ManualIngestionRunRequest(
        manual_observation=_company_observation(
            "raw_refresh_requires_approval",
            source_type=SourceType.COMPANY_OFFICIAL,
        ),
        mode=ManualIngestionRunMode.EXECUTE_WRITE_AND_REFRESH_WITH_APPROVAL,
        review_decision=_review_decision(),
    )
    preview = _service(session).run_manual_ingestion(
        base_request,
        provenance_service=_provenance_service(session),
    )
    request = base_request.model_copy(
        update={"write_execution_decision": _write_decision(preview.write_plan.plan_id)}
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.status is ManualIngestionRunStatus.STOPPED
    assert result.write_execution_result is not None
    assert result.refresh_plan is not None
    assert result.refresh_execution_result is None
    assert any(
        d.code == "refresh_execution_decision_required" for d in result.diagnostics
    )
    assert session.query(OutputMetadata).count() == 0


def test_execute_write_and_refresh_runs_only_with_separate_refresh_approval(
    session: Session,
) -> None:
    base_request = ManualIngestionRunRequest(
        manual_observation=_company_observation(
            "raw_refresh_approved",
            source_type=SourceType.COMPANY_OFFICIAL,
        ),
        mode=ManualIngestionRunMode.EXECUTE_WRITE_AND_REFRESH_WITH_APPROVAL,
        review_decision=_review_decision(),
    )
    preview = _service(session).run_manual_ingestion(
        base_request,
        provenance_service=_provenance_service(session),
    )
    write_plan_id = preview.write_plan.plan_id
    request = base_request.model_copy(
        update={
            "write_execution_decision": _write_decision(write_plan_id),
            "refresh_execution_decision": _refresh_decision(write_plan_id),
        }
    )

    result = _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert result.write_execution_result.status is CanonicalWriteExecutionStatus.EXECUTED
    assert result.refresh_execution_result is not None
    assert result.refresh_execution_result.outputs_refreshed_count == 1
    assert session.query(OutputMetadata).count() == 1
    assert session.query(Job).count() == 0


def test_repeated_link_only_orchestration_is_deterministic(session: Session) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_repeat_link"),
        mode=ManualIngestionRunMode.LINK_ONLY,
        review_decision=_review_decision(),
    )
    service = _service(session)

    first = service.run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )
    second = service.run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert first.write_plan.plan_id == second.write_plan.plan_id
    assert session.query(RawIngestionRecord).count() == 1
    assert session.query(FactSourceLink).count() == 1
    assert session.query(SourceRef).count() == 1
    assert session.query(SourceObservation).count() == 1


def test_orchestration_creates_no_jobs_schedules_or_workers(session: Session) -> None:
    request = ManualIngestionRunRequest(
        manual_observation=_company_observation("raw_no_jobs"),
        mode=ManualIngestionRunMode.LINK_ONLY,
        review_decision=_review_decision(),
    )

    _service(session).run_manual_ingestion(
        request,
        provenance_service=_provenance_service(session),
    )

    assert session.query(Job).count() == 0


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.get(SourceRef, "mvp_demo_seed") is not None
    assert session.query(RawIngestionRecord).count() == 0
    assert session.query(Company).count() > 0
    assert session.query(Region).count() > 0
