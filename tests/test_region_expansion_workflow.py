from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.region_expansion.models import RegionExpansionWorkflow
from backend.region_expansion.repository import RegionExpansionRepository
from backend.region_expansion.service import (
    CHECKLIST_FIELDS,
    TARGET_REGION_EXPANSION_PLAN,
    RegionDataMode,
    RegionExpansionChecklistInput,
    RegionExpansionCreateInput,
    RegionExpansionError,
    RegionExpansionService,
    RegionExpansionState,
)


def _service(session: Session) -> RegionExpansionService:
    return RegionExpansionService(RegionExpansionRepository(session))


def _create_workflow(
    session: Session,
    *,
    region_key: str = "nyc",
    display_name: str = "NYC",
    data_mode: RegionDataMode = RegionDataMode.CANDIDATE,
) -> RegionExpansionWorkflow:
    return _service(session).create_candidate(
        RegionExpansionCreateInput(
            region_key=region_key,
            display_name=display_name,
            region_data_mode=data_mode,
        )
    )


def _complete_pre_review_checks(
    service: RegionExpansionService,
    workflow: RegionExpansionWorkflow,
) -> None:
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            region_identity_check=True,
            source_coverage_check=True,
            company_region_presence_check=True,
            hiring_signal_support_check=True,
            entry_level_signal_support_check=True,
            scoring_readiness_check=True,
            freshness_readiness_check=True,
            provenance_attached_check=True,
            ingestion_contract_ref="ingestion:manual_review_contract",
            provenance_contract_ref="provenance:fact_source_links",
        ),
    )


def test_target_regions_are_represented_as_unpublished_candidates(
    session: Session,
) -> None:
    service = _service(session)

    rows = service.ensure_target_candidates()

    assert [(key, label) for key, label in TARGET_REGION_EXPANSION_PLAN] == [
        ("nyc", "NYC"),
        ("seattle", "Seattle"),
        ("austin", "Austin"),
        ("dc_nova", "DC / NoVA"),
        ("atlanta", "Atlanta"),
        ("chicago", "Chicago"),
        ("los_angeles", "Los Angeles"),
        ("raleigh_durham", "Raleigh-Durham"),
        ("denver_boulder", "Denver / Boulder"),
        ("boston", "Boston"),
        ("sf_bay_area", "SF Bay Area"),
        ("dallas", "Dallas"),
        ("miami", "Miami"),
        ("pittsburgh", "Pittsburgh"),
        ("minneapolis", "Minneapolis"),
    ]
    assert {row.region_key for row in rows} == {
        key for key, _label in TARGET_REGION_EXPANSION_PLAN
    }
    assert all(row.workflow_state == "candidate" for row in rows)
    assert all(row.region_data_mode == "candidate" for row in rows)
    assert not any(row.published for row in rows)
    assert not any(row.refresh_enabled for row in rows)


def test_valid_region_expansion_state_sequence(session: Session) -> None:
    service = _service(session)
    workflow = _create_workflow(session)

    service.transition(workflow.workflow_id, RegionExpansionState.INTAKE_STARTED)
    service.transition(workflow.workflow_id, RegionExpansionState.NORMALIZED)
    _complete_pre_review_checks(service, workflow)
    service.transition(workflow.workflow_id, RegionExpansionState.PROVENANCE_ATTACHED)
    service.transition(workflow.workflow_id, RegionExpansionState.REVIEW_READY)
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            admin_approval_check=True,
            admin_review_ref="admin_review:nyc:approved",
            output_refresh_readiness_check=True,
            output_refresh_contract_ref="refresh:output_rebuild:region:nyc",
            region_data_mode=RegionDataMode.REAL_REFRESHABLE,
        ),
    )
    service.transition(workflow.workflow_id, RegionExpansionState.APPROVED)
    service.transition(workflow.workflow_id, RegionExpansionState.PUBLISHED)
    service.transition(workflow.workflow_id, RegionExpansionState.REFRESH_ENABLED)

    assert workflow.workflow_state == "refresh_enabled"
    assert workflow.published is True
    assert workflow.refresh_enabled is True


def test_invalid_region_expansion_transitions_are_rejected(session: Session) -> None:
    service = _service(session)
    workflow = _create_workflow(session)

    with pytest.raises(RegionExpansionError):
        service.transition(workflow.workflow_id, RegionExpansionState.PUBLISHED)

    assert workflow.workflow_state == "candidate"
    assert workflow.published is False


def test_required_checklist_fields_are_validated_before_review_ready(
    session: Session,
) -> None:
    service = _service(session)
    workflow = _create_workflow(session)
    service.transition(workflow.workflow_id, RegionExpansionState.INTAKE_STARTED)
    service.transition(workflow.workflow_id, RegionExpansionState.NORMALIZED)
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            provenance_attached_check=True,
            provenance_contract_ref="provenance:attached",
        ),
    )
    service.transition(workflow.workflow_id, RegionExpansionState.PROVENANCE_ATTACHED)

    with pytest.raises(RegionExpansionError, match="review_ready requires completed checks"):
        service.transition(workflow.workflow_id, RegionExpansionState.REVIEW_READY)

    for field in CHECKLIST_FIELDS:
        assert hasattr(workflow, field)


def test_seed_demo_candidate_cannot_be_published_as_refreshable_region(
    session: Session,
) -> None:
    service = _service(session)
    workflow = _create_workflow(
        session,
        region_key="boston_seed",
        display_name="Boston Seed",
        data_mode=RegionDataMode.SEED_DEMO,
    )
    service.transition(workflow.workflow_id, RegionExpansionState.INTAKE_STARTED)
    service.transition(workflow.workflow_id, RegionExpansionState.NORMALIZED)
    _complete_pre_review_checks(service, workflow)
    service.transition(workflow.workflow_id, RegionExpansionState.PROVENANCE_ATTACHED)
    service.transition(workflow.workflow_id, RegionExpansionState.REVIEW_READY)
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            admin_approval_check=True,
            admin_review_ref="admin_review:seed",
            output_refresh_readiness_check=True,
            output_refresh_contract_ref="refresh:output_rebuild:seed",
        ),
    )
    service.transition(workflow.workflow_id, RegionExpansionState.APPROVED)

    with pytest.raises(RegionExpansionError, match="real_refreshable"):
        service.transition(workflow.workflow_id, RegionExpansionState.PUBLISHED)

    assert workflow.region_data_mode == "seed_demo"
    assert workflow.published is False


def test_workflow_requires_existing_boundary_refs_before_publication(
    session: Session,
) -> None:
    service = _service(session)
    workflow = _create_workflow(session, region_key="seattle", display_name="Seattle")
    service.transition(workflow.workflow_id, RegionExpansionState.INTAKE_STARTED)
    service.transition(workflow.workflow_id, RegionExpansionState.NORMALIZED)
    _complete_pre_review_checks(service, workflow)
    service.transition(workflow.workflow_id, RegionExpansionState.PROVENANCE_ATTACHED)
    service.transition(workflow.workflow_id, RegionExpansionState.REVIEW_READY)

    with pytest.raises(RegionExpansionError, match="admin_approval_check"):
        service.transition(workflow.workflow_id, RegionExpansionState.APPROVED)

    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            admin_approval_check=True,
            admin_review_ref="admin_review:seattle",
            region_data_mode=RegionDataMode.REAL_REFRESHABLE,
        ),
    )
    service.transition(workflow.workflow_id, RegionExpansionState.APPROVED)

    with pytest.raises(RegionExpansionError, match="output_refresh_readiness_check"):
        service.transition(workflow.workflow_id, RegionExpansionState.PUBLISHED)


def test_refresh_enabled_rechecks_refresh_readiness_if_checklist_changes(
    session: Session,
) -> None:
    service = _service(session)
    workflow = _create_workflow(session, region_key="atlanta", display_name="Atlanta")
    service.transition(workflow.workflow_id, RegionExpansionState.INTAKE_STARTED)
    service.transition(workflow.workflow_id, RegionExpansionState.NORMALIZED)
    _complete_pre_review_checks(service, workflow)
    service.transition(workflow.workflow_id, RegionExpansionState.PROVENANCE_ATTACHED)
    service.transition(workflow.workflow_id, RegionExpansionState.REVIEW_READY)
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(
            admin_approval_check=True,
            admin_review_ref="admin_review:atlanta",
            output_refresh_readiness_check=True,
            output_refresh_contract_ref="refresh:output_rebuild:atlanta",
            region_data_mode=RegionDataMode.REAL_REFRESHABLE,
        ),
    )
    service.transition(workflow.workflow_id, RegionExpansionState.APPROVED)
    service.transition(workflow.workflow_id, RegionExpansionState.PUBLISHED)
    service.update_checklist(
        workflow.workflow_id,
        RegionExpansionChecklistInput(output_refresh_readiness_check=False),
    )

    with pytest.raises(RegionExpansionError, match="output_refresh_readiness_check"):
        service.transition(workflow.workflow_id, RegionExpansionState.REFRESH_ENABLED)
