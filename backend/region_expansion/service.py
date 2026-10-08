"""Repeatable region-expansion workflow contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.geography.exceptions import GeographicResolutionError
from backend.geography.market_coverage import PRIORITY_MARKETS
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.region_expansion.models import RegionExpansionWorkflow
from backend.region_expansion.repository import RegionExpansionRepository


class RegionExpansionState(StrEnum):
    CANDIDATE = "candidate"
    INTAKE_STARTED = "intake_started"
    NORMALIZED = "normalized"
    PROVENANCE_ATTACHED = "provenance_attached"
    REVIEW_READY = "review_ready"
    APPROVED = "approved"
    PUBLISHED = "published"
    REFRESH_ENABLED = "refresh_enabled"


class RegionDataMode(StrEnum):
    SEED_DEMO = "seed_demo"
    CANDIDATE = "candidate"
    REAL_REFRESHABLE = "real_refreshable"


class RegionExpansionError(ValueError):
    pass


class RegionExpansionNotFound(LookupError):
    pass


TARGET_REGION_EXPANSION_PLAN: tuple[tuple[str, str], ...] = tuple(
    (market.market_id, market.display_name) for market in PRIORITY_MARKETS
)

CHECKLIST_FIELDS: tuple[str, ...] = (
    "region_identity_check",
    "source_coverage_check",
    "company_region_presence_check",
    "hiring_signal_support_check",
    "entry_level_signal_support_check",
    "scoring_readiness_check",
    "freshness_readiness_check",
    "provenance_attached_check",
    "admin_approval_check",
    "output_refresh_readiness_check",
)

PRE_REVIEW_CHECKS: tuple[str, ...] = (
    "region_identity_check",
    "source_coverage_check",
    "company_region_presence_check",
    "hiring_signal_support_check",
    "entry_level_signal_support_check",
    "scoring_readiness_check",
    "freshness_readiness_check",
    "provenance_attached_check",
)

ALLOWED_TRANSITIONS: frozenset[tuple[RegionExpansionState, RegionExpansionState]] = frozenset(
    {
        (RegionExpansionState.CANDIDATE, RegionExpansionState.INTAKE_STARTED),
        (RegionExpansionState.INTAKE_STARTED, RegionExpansionState.NORMALIZED),
        (RegionExpansionState.NORMALIZED, RegionExpansionState.PROVENANCE_ATTACHED),
        (RegionExpansionState.PROVENANCE_ATTACHED, RegionExpansionState.REVIEW_READY),
        (RegionExpansionState.REVIEW_READY, RegionExpansionState.APPROVED),
        (RegionExpansionState.APPROVED, RegionExpansionState.PUBLISHED),
        (RegionExpansionState.PUBLISHED, RegionExpansionState.REFRESH_ENABLED),
    }
)


@dataclass(frozen=True, slots=True)
class TargetRegionCandidate:
    region_key: str
    display_name: str
    initial_state: RegionExpansionState = RegionExpansionState.CANDIDATE
    region_data_mode: RegionDataMode = RegionDataMode.CANDIDATE


class RegionExpansionCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    canonical_region_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_data_mode: RegionDataMode = RegionDataMode.CANDIDATE

    @field_validator("region_key", "display_name", "canonical_region_id")
    @classmethod
    def _strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("region expansion strings must not be blank")
        return stripped


class RegionExpansionChecklistInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_identity_check: bool | None = None
    source_coverage_check: bool | None = None
    company_region_presence_check: bool | None = None
    hiring_signal_support_check: bool | None = None
    entry_level_signal_support_check: bool | None = None
    scoring_readiness_check: bool | None = None
    freshness_readiness_check: bool | None = None
    provenance_attached_check: bool | None = None
    admin_approval_check: bool | None = None
    output_refresh_readiness_check: bool | None = None
    ingestion_contract_ref: str | None = Field(default=None, min_length=1, max_length=128)
    provenance_contract_ref: str | None = Field(default=None, min_length=1, max_length=128)
    admin_review_ref: str | None = Field(default=None, min_length=1, max_length=128)
    output_refresh_contract_ref: str | None = Field(default=None, min_length=1, max_length=128)
    checklist_notes: dict[str, Any] | None = None
    region_data_mode: RegionDataMode | None = None


class RegionExpansionService:
    def __init__(self, repository: RegionExpansionRepository) -> None:
        self._repo = repository

    def planned_target_candidates(self) -> list[TargetRegionCandidate]:
        return [
            TargetRegionCandidate(region_key=key, display_name=label)
            for key, label in TARGET_REGION_EXPANSION_PLAN
        ]

    def ensure_target_candidates(self) -> list[RegionExpansionWorkflow]:
        rows: list[RegionExpansionWorkflow] = []
        for candidate in self.planned_target_candidates():
            row = self._repo.get_by_region_key(candidate.region_key)
            if row is None:
                row = self.create_candidate(
                    RegionExpansionCreateInput(
                        region_key=candidate.region_key,
                        display_name=candidate.display_name,
                        region_data_mode=candidate.region_data_mode,
                    )
                )
            rows.append(row)
        return rows

    def create_candidate(
        self,
        candidate: RegionExpansionCreateInput,
    ) -> RegionExpansionWorkflow:
        existing = self._repo.get_by_region_key(candidate.region_key)
        if existing is not None:
            raise RegionExpansionError(
                f"region expansion workflow already exists for {candidate.region_key!r}"
            )
        canonical_region_id = candidate.canonical_region_id
        if canonical_region_id is not None:
            try:
                resolution = GeographicResolver(
                    RegionRepository(self._repo.session)
                ).require(canonical_region_id)
            except GeographicResolutionError as exc:
                raise RegionExpansionError(str(exc)) from exc
            assert resolution.region_id is not None
            canonical_region_id = resolution.region_id
        row = RegionExpansionWorkflow(
            workflow_id=_new_workflow_id(),
            region_key=candidate.region_key,
            display_name=candidate.display_name,
            canonical_region_id=canonical_region_id,
            workflow_state=RegionExpansionState.CANDIDATE.value,
            region_data_mode=candidate.region_data_mode.value,
        )
        self._repo.add(row)
        self._repo.flush()
        return row

    def update_checklist(
        self,
        workflow_id: str,
        update: RegionExpansionChecklistInput,
    ) -> RegionExpansionWorkflow:
        row = self._workflow(workflow_id)
        for field in CHECKLIST_FIELDS:
            value = getattr(update, field)
            if value is not None:
                setattr(row, field, value)
        for field in (
            "ingestion_contract_ref",
            "provenance_contract_ref",
            "admin_review_ref",
            "output_refresh_contract_ref",
            "checklist_notes",
        ):
            value = getattr(update, field)
            if value is not None:
                setattr(row, field, value)
        if update.region_data_mode is not None:
            row.region_data_mode = update.region_data_mode.value
        self._repo.flush()
        return row

    def transition(
        self,
        workflow_id: str,
        target_state: RegionExpansionState,
    ) -> RegionExpansionWorkflow:
        row = self._workflow(workflow_id)
        current = RegionExpansionState(row.workflow_state)
        if (current, target_state) not in ALLOWED_TRANSITIONS:
            raise RegionExpansionError(
                f"region expansion transition not allowed: {current.value} -> "
                f"{target_state.value}"
            )
        _validate_transition_requirements(row, target_state)
        row.workflow_state = target_state.value
        if target_state is RegionExpansionState.PUBLISHED:
            row.published = True
        if target_state is RegionExpansionState.REFRESH_ENABLED:
            row.refresh_enabled = True
        self._repo.flush()
        return row

    def list_workflows(self) -> list[RegionExpansionWorkflow]:
        return self._repo.list_workflows()

    def _workflow(self, workflow_id: str) -> RegionExpansionWorkflow:
        row = self._repo.get(workflow_id)
        if row is None:
            raise RegionExpansionNotFound(workflow_id)
        return row


def region_expansion_workflow_data(row: RegionExpansionWorkflow) -> dict[str, Any]:
    return {
        "workflow_id": row.workflow_id,
        "region_key": row.region_key,
        "display_name": row.display_name,
        "canonical_region_id": row.canonical_region_id,
        "workflow_state": row.workflow_state,
        "region_data_mode": row.region_data_mode,
        "published": row.published,
        "refresh_enabled": row.refresh_enabled,
        "integration_refs": {
            "ingestion_contract_ref": row.ingestion_contract_ref,
            "provenance_contract_ref": row.provenance_contract_ref,
            "admin_review_ref": row.admin_review_ref,
            "output_refresh_contract_ref": row.output_refresh_contract_ref,
        },
        "checklist": {field: getattr(row, field) for field in CHECKLIST_FIELDS},
        "checklist_notes": row.checklist_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _validate_transition_requirements(
    row: RegionExpansionWorkflow,
    target_state: RegionExpansionState,
) -> None:
    if target_state is RegionExpansionState.PROVENANCE_ATTACHED:
        if not row.provenance_attached_check or not row.provenance_contract_ref:
            raise RegionExpansionError(
                "provenance_attached requires provenance_attached_check and "
                "provenance_contract_ref"
            )
    if target_state is RegionExpansionState.REVIEW_READY:
        missing = [field for field in PRE_REVIEW_CHECKS if not getattr(row, field)]
        if missing:
            raise RegionExpansionError(
                f"review_ready requires completed checks: {', '.join(missing)}"
            )
        if not row.ingestion_contract_ref or not row.provenance_contract_ref:
            raise RegionExpansionError(
                "review_ready requires ingestion and provenance contract references"
            )
    if target_state is RegionExpansionState.APPROVED:
        if not row.admin_approval_check or not row.admin_review_ref:
            raise RegionExpansionError(
                "approved requires admin_approval_check and admin_review_ref"
            )
    if target_state is RegionExpansionState.PUBLISHED:
        if row.region_data_mode != RegionDataMode.REAL_REFRESHABLE.value:
            raise RegionExpansionError(
                "published requires region_data_mode='real_refreshable'"
            )
        if not row.provenance_attached_check or not row.provenance_contract_ref:
            raise RegionExpansionError(
                "published requires provenance_attached_check and "
                "provenance_contract_ref"
            )
        if not row.admin_approval_check or not row.admin_review_ref:
            raise RegionExpansionError(
                "published requires admin_approval_check and admin_review_ref"
            )
        if not row.output_refresh_readiness_check or not row.output_refresh_contract_ref:
            raise RegionExpansionError(
                "published requires output_refresh_readiness_check and "
                "output_refresh_contract_ref"
            )
    if target_state is RegionExpansionState.REFRESH_ENABLED:
        if not row.published:
            raise RegionExpansionError("refresh_enabled requires published workflow")
        if not row.output_refresh_readiness_check or not row.output_refresh_contract_ref:
            raise RegionExpansionError(
                "refresh_enabled requires output_refresh_readiness_check and "
                "output_refresh_contract_ref"
            )


def _new_workflow_id() -> str:
    return f"region_expansion_{uuid4().hex[:46]}"
