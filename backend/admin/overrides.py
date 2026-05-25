"""Controlled admin override and repair workflows."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.admin.models import AdminOverride, AdminRepairAction
from backend.admin.repository import AdminEventLogRepository
from backend.admin.review import AdminReviewService
from backend.admin.roles import AdminRole
from backend.admin.service import AdminEventLogInput, AdminEventLogService
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.companies.types import (
    ClassificationConfidence,
    EligibilityStatus,
    PublicOrPrivate,
)
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.outputs.models import OutputMetadata
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.outputs.types import OutputType
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.presence.types import PresenceStatus
from backend.provenance.models import SourceRef
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.confidence import Confidence
from backend.shared.state import ObjectState, validate_transition


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OverrideStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class OverrideTargetType(StrEnum):
    COMPANY = "company"
    PRESENCE_FACT = "presence_fact"
    SOURCE_REF = "source_ref"


class OverrideType(StrEnum):
    COMPANY_ELIGIBILITY = "company_eligibility"
    COMPANY_CLASSIFICATION = "company_classification"
    PRESENCE_STATUS = "presence_status"
    SOURCE_CONFIDENCE = "source_confidence"


class RepairActionStatus(StrEnum):
    REQUESTED = "requested"
    EXECUTED = "executed"
    FAILED = "failed"
    REJECTED = "rejected"


class RepairActionType(StrEnum):
    RECOMPUTE_SCORE = "recompute_score"
    REBUILD_OUTPUT = "rebuild_output"
    MARK_SOURCE_STALE = "mark_source_stale"
    REQUEST_REVIEW = "request_review"
    DEACTIVATE_BAD_FACT = "deactivate_bad_fact"


class RepairTargetType(StrEnum):
    REGION = "region"
    OUTPUT = "output"
    COMPANY = "company"
    PRESENCE_FACT = "presence_fact"
    HIRING_FACT = "hiring_fact"
    ENTRY_LEVEL_FACT = "entry_level_fact"
    SOURCE_REF = "source_ref"
    AUDIT_FINDING = "audit_finding"


OVERRIDE_TARGETS: dict[OverrideType, OverrideTargetType] = {
    OverrideType.COMPANY_ELIGIBILITY: OverrideTargetType.COMPANY,
    OverrideType.COMPANY_CLASSIFICATION: OverrideTargetType.COMPANY,
    OverrideType.PRESENCE_STATUS: OverrideTargetType.PRESENCE_FACT,
    OverrideType.SOURCE_CONFIDENCE: OverrideTargetType.SOURCE_REF,
}

REPAIR_TARGETS: dict[RepairActionType, frozenset[RepairTargetType]] = {
    RepairActionType.RECOMPUTE_SCORE: frozenset({RepairTargetType.REGION}),
    RepairActionType.REBUILD_OUTPUT: frozenset({RepairTargetType.OUTPUT}),
    RepairActionType.MARK_SOURCE_STALE: frozenset({RepairTargetType.SOURCE_REF}),
    RepairActionType.REQUEST_REVIEW: frozenset(
        {
            RepairTargetType.COMPANY,
            RepairTargetType.PRESENCE_FACT,
            RepairTargetType.HIRING_FACT,
            RepairTargetType.ENTRY_LEVEL_FACT,
            RepairTargetType.SOURCE_REF,
            RepairTargetType.AUDIT_FINDING,
        }
    ),
    RepairActionType.DEACTIVATE_BAD_FACT: frozenset(
        {
            RepairTargetType.PRESENCE_FACT,
            RepairTargetType.HIRING_FACT,
            RepairTargetType.ENTRY_LEVEL_FACT,
        }
    ),
}


class OverrideWorkflowError(ValueError):
    """Raised when an override request fails workflow validation."""


class OverrideNotFound(LookupError):
    """Raised when an override record is missing."""


class RepairActionWorkflowError(ValueError):
    """Raised when a repair action fails workflow validation."""


class RepairActionNotFound(LookupError):
    """Raised when a repair action record is missing."""


class AdminOverrideCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: OverrideTargetType
    target_id: str = Field(min_length=1, max_length=128)
    override_type: OverrideType
    override_value: Any
    reason: str = Field(min_length=1, max_length=2048)
    source_evidence: dict[str, Any] | list[Any] | str
    expires_at: datetime | None = None
    review_at: datetime | None = None

    @field_validator("target_id", "reason")
    @classmethod
    def _strings_nonblank(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("source_evidence")
    @classmethod
    def _source_evidence_present(
        cls,
        value: dict[str, Any] | list[Any] | str,
    ) -> dict[str, Any] | list[Any] | str:
        if isinstance(value, str):
            return _nonblank(value)
        if isinstance(value, dict) and value:
            return value
        if isinstance(value, list) and value:
            return value
        raise ValueError("source_evidence must not be empty")

    @model_validator(mode="after")
    def _requires_expiration_or_review(self) -> AdminOverrideCreateInput:
        if self.expires_at is None and self.review_at is None:
            raise ValueError("expires_at or review_at is required")
        return self


class AdminOverrideMutationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(min_length=1, max_length=2048)

    @field_validator("reason")
    @classmethod
    def _reason_nonblank(cls, value: str) -> str:
        return _nonblank(value)


class AdminRepairActionCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: RepairActionType
    target_type: RepairTargetType
    target_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2048)
    parameters: dict[str, Any] | list[Any] | None = None
    audit_finding_id: str | None = Field(default=None, max_length=255)

    @field_validator("target_id", "reason")
    @classmethod
    def _strings_nonblank(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("audit_finding_id")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        return _optional_nonblank(value)


class AdminRepairActionExecuteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(min_length=1, max_length=2048)

    @field_validator("reason")
    @classmethod
    def _reason_nonblank(cls, value: str) -> str:
        return _nonblank(value)


@dataclass(frozen=True, slots=True)
class RepairExecutionResult:
    result: dict[str, Any]
    target_before: dict[str, Any] | None
    target_after: dict[str, Any] | None


class AdminOverrideService:
    """Controlled override workflow service."""

    def __init__(
        self,
        *,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._now = clock or _utc_now
        self._event_log = AdminEventLogService(
            AdminEventLogRepository(session),
            clock=self._now,
        )

    def list_overrides(
        self,
        *,
        limit: int = 100,
        status: OverrideStatus | None = None,
        target_type: OverrideTargetType | None = None,
        target_id: str | None = None,
    ) -> list[AdminOverride]:
        stmt = select(AdminOverride)
        if status is not None:
            stmt = stmt.where(AdminOverride.status == status.value)
        if target_type is not None:
            stmt = stmt.where(AdminOverride.target_type == target_type.value)
        if target_id is not None:
            stmt = stmt.where(AdminOverride.target_id == target_id)
        stmt = stmt.order_by(
            AdminOverride.created_at.desc(),
            AdminOverride.override_id.desc(),
        ).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def get_override(self, override_id: str) -> AdminOverride | None:
        return self._session.get(AdminOverride, override_id)

    def list_active_for_target(
        self,
        target_type: OverrideTargetType,
        target_id: str,
    ) -> list[AdminOverride]:
        now = _aware(self._now())
        stmt = (
            select(AdminOverride)
            .where(
                AdminOverride.target_type == target_type.value,
                AdminOverride.target_id == target_id,
                AdminOverride.status == OverrideStatus.ACTIVE.value,
            )
            .order_by(AdminOverride.activated_at.desc(), AdminOverride.override_id)
        )
        return [
            row
            for row in self._session.execute(stmt).scalars()
            if _override_is_effectively_active(row, now=now)
        ]

    def create_override(
        self,
        payload: AdminOverrideCreateInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AdminOverride:
        _validate_override_compatibility(payload.target_type, payload.override_type)
        _validate_override_value(payload.override_type, payload.override_value)
        target = self._override_target(payload.target_type, payload.target_id)
        if target is None:
            raise OverrideWorkflowError(
                f"override target not found: {payload.target_type.value}:{payload.target_id}"
            )

        now = _aware(self._now())
        row = AdminOverride(
            override_id=_new_override_id(),
            target_type=payload.target_type.value,
            target_id=payload.target_id,
            override_type=payload.override_type.value,
            previous_value=_observed_override_value(target, payload.override_type),
            override_value=deepcopy(payload.override_value),
            reason=payload.reason,
            reviewer_actor=actor,
            reviewer_role=role.value,
            source_evidence=deepcopy(payload.source_evidence),
            expires_at=payload.expires_at,
            review_at=payload.review_at,
            status=OverrideStatus.PROPOSED.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        self._record_override_event(
            row,
            actor=actor,
            role=role,
            action="admin.override.proposed",
            before_state=None,
            reason=payload.reason,
            request_id=request_id,
        )
        return row

    def activate_override(
        self,
        override_id: str,
        payload: AdminOverrideMutationInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AdminOverride:
        row = self._require_override(override_id)
        if row.status != OverrideStatus.PROPOSED.value:
            raise OverrideWorkflowError(
                f"only proposed overrides can be activated; got {row.status!r}"
            )

        now = _aware(self._now())
        if row.expires_at is not None and _aware(row.expires_at) <= now:
            raise OverrideWorkflowError("expired overrides cannot be activated")

        for active in self._matching_active_overrides(row):
            before = admin_override_data(active)
            active.status = OverrideStatus.SUPERSEDED.value
            active.updated_at = now
            self._session.flush()
            self._record_override_event(
                active,
                actor=actor,
                role=role,
                action="admin.override.superseded",
                before_state=before,
                reason=payload.reason,
                request_id=request_id,
            )

        before = admin_override_data(row)
        row.status = OverrideStatus.ACTIVE.value
        row.activated_at = now
        row.activated_by = actor
        row.activated_role = role.value
        row.updated_at = now
        self._session.flush()
        self._record_override_event(
            row,
            actor=actor,
            role=role,
            action="admin.override.activated",
            before_state=before,
            reason=payload.reason,
            request_id=request_id,
        )
        return row

    def revoke_override(
        self,
        override_id: str,
        payload: AdminOverrideMutationInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AdminOverride:
        row = self._require_override(override_id)
        if row.status not in {
            OverrideStatus.PROPOSED.value,
            OverrideStatus.ACTIVE.value,
        }:
            raise OverrideWorkflowError(
                f"only proposed or active overrides can be revoked; got {row.status!r}"
            )

        before = admin_override_data(row)
        now = _aware(self._now())
        row.status = OverrideStatus.REVOKED.value
        row.revoked_at = now
        row.revoked_by = actor
        row.revoked_role = role.value
        row.revocation_reason = payload.reason
        row.updated_at = now
        self._session.flush()
        self._record_override_event(
            row,
            actor=actor,
            role=role,
            action="admin.override.revoked",
            before_state=before,
            reason=payload.reason,
            request_id=request_id,
        )
        return row

    def _override_target(
        self,
        target_type: OverrideTargetType,
        target_id: str,
    ) -> Company | CompanyRegionPresence | SourceRef | None:
        if target_type is OverrideTargetType.COMPANY:
            return self._session.get(Company, target_id)
        if target_type is OverrideTargetType.PRESENCE_FACT:
            return self._session.get(CompanyRegionPresence, target_id)
        if target_type is OverrideTargetType.SOURCE_REF:
            return self._session.get(SourceRef, target_id)
        return None

    def _require_override(self, override_id: str) -> AdminOverride:
        row = self.get_override(override_id)
        if row is None:
            raise OverrideNotFound(override_id)
        return row

    def _matching_active_overrides(self, row: AdminOverride) -> list[AdminOverride]:
        stmt = (
            select(AdminOverride)
            .where(
                AdminOverride.override_id != row.override_id,
                AdminOverride.target_type == row.target_type,
                AdminOverride.target_id == row.target_id,
                AdminOverride.override_type == row.override_type,
                AdminOverride.status == OverrideStatus.ACTIVE.value,
            )
            .order_by(AdminOverride.activated_at, AdminOverride.override_id)
        )
        return list(self._session.execute(stmt).scalars())

    def _record_override_event(
        self,
        row: AdminOverride,
        *,
        actor: str,
        role: AdminRole,
        action: str,
        before_state: dict[str, Any] | None,
        reason: str,
        request_id: str | None,
    ) -> None:
        self._event_log.record_event(
            AdminEventLogInput(
                actor=actor,
                role=role,
                action=action,
                object_type="admin_override",
                object_id=row.override_id,
                before_state=before_state,
                after_state=admin_override_data(row),
                reason=reason,
                request_id=request_id,
            )
        )


class AdminRepairActionService:
    """Controlled workflow service for explicit safe repair actions."""

    def __init__(
        self,
        *,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._now = clock or _utc_now
        self._event_log = AdminEventLogService(
            AdminEventLogRepository(session),
            clock=self._now,
        )

    def list_actions(
        self,
        *,
        limit: int = 100,
        status: RepairActionStatus | None = None,
        action_type: RepairActionType | None = None,
    ) -> list[AdminRepairAction]:
        stmt = select(AdminRepairAction)
        if status is not None:
            stmt = stmt.where(AdminRepairAction.status == status.value)
        if action_type is not None:
            stmt = stmt.where(AdminRepairAction.action_type == action_type.value)
        stmt = stmt.order_by(
            AdminRepairAction.created_at.desc(),
            AdminRepairAction.repair_action_id.desc(),
        ).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def get_action(self, repair_action_id: str) -> AdminRepairAction | None:
        return self._session.get(AdminRepairAction, repair_action_id)

    def create_action(
        self,
        payload: AdminRepairActionCreateInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AdminRepairAction:
        _validate_repair_compatibility(payload.target_type, payload.action_type)
        if role is not AdminRole.ADMIN and payload.action_type is not (
            RepairActionType.REQUEST_REVIEW
        ):
            raise RepairActionWorkflowError(
                "data_reviewer can only request review repair actions"
            )
        if self._repair_target(payload.target_type, payload.target_id) is None:
            raise RepairActionWorkflowError(
                f"repair target not found: {payload.target_type.value}:{payload.target_id}"
            )

        now = _aware(self._now())
        row = AdminRepairAction(
            repair_action_id=_new_repair_action_id(),
            action_type=payload.action_type.value,
            target_type=payload.target_type.value,
            target_id=payload.target_id,
            status=RepairActionStatus.REQUESTED.value,
            reason=payload.reason,
            requested_by=actor,
            requested_role=role.value,
            requested_at=now,
            audit_finding_id=payload.audit_finding_id,
            parameters=deepcopy(payload.parameters),
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        self._record_repair_event(
            row,
            actor=actor,
            role=role,
            action="admin.repair_action.requested",
            before_state=None,
            after_state={"repair_action": admin_repair_action_data(row)},
            reason=payload.reason,
            request_id=request_id,
        )
        return row

    def execute_action(
        self,
        repair_action_id: str,
        payload: AdminRepairActionExecuteInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AdminRepairAction:
        row = self._require_action(repair_action_id)
        if row.status != RepairActionStatus.REQUESTED.value:
            raise RepairActionWorkflowError(
                f"only requested repair actions can be executed; got {row.status!r}"
            )

        before_action = admin_repair_action_data(row)
        result = self._execute_requested_action(row)
        now = _aware(self._now())
        row.status = RepairActionStatus.EXECUTED.value
        row.executed_by = actor
        row.executed_role = role.value
        row.executed_at = now
        row.result = result.result
        row.updated_at = now
        self._session.flush()
        self._record_repair_event(
            row,
            actor=actor,
            role=role,
            action="admin.repair_action.executed",
            before_state={
                "repair_action": before_action,
                "target": result.target_before,
            },
            after_state={
                "repair_action": admin_repair_action_data(row),
                "target": result.target_after,
            },
            reason=payload.reason,
            request_id=request_id,
        )
        return row

    def _require_action(self, repair_action_id: str) -> AdminRepairAction:
        row = self.get_action(repair_action_id)
        if row is None:
            raise RepairActionNotFound(repair_action_id)
        return row

    def _execute_requested_action(self, row: AdminRepairAction) -> RepairExecutionResult:
        action_type = RepairActionType(row.action_type)
        if action_type is RepairActionType.RECOMPUTE_SCORE:
            return self._execute_recompute_score(row)
        if action_type is RepairActionType.REBUILD_OUTPUT:
            return self._execute_rebuild_output(row)
        if action_type is RepairActionType.MARK_SOURCE_STALE:
            return self._execute_mark_source_stale(row)
        if action_type is RepairActionType.REQUEST_REVIEW:
            return self._execute_request_review(row)
        if action_type is RepairActionType.DEACTIVATE_BAD_FACT:
            return self._execute_deactivate_bad_fact(row)
        raise RepairActionWorkflowError(f"unsupported repair action: {row.action_type}")

    def _execute_recompute_score(
        self,
        row: AdminRepairAction,
    ) -> RepairExecutionResult:
        score_before = _score_snapshot(
            RegionScoreRepository(self._session).get_score_by_region(row.target_id)
        )
        score, outcome = RegionScoringService(
            RegionScoreRepository(self._session),
            region_repo=RegionRepository(self._session),
        ).upsert_for_recompute(row.target_id)
        score_after = _score_snapshot(score)
        return RepairExecutionResult(
            result={
                "action": "recompute_score",
                "region_id": row.target_id,
                "region_score_id": score.region_score_id,
                "outcome": outcome,
            },
            target_before=score_before,
            target_after=score_after,
        )

    def _execute_rebuild_output(
        self,
        row: AdminRepairAction,
    ) -> RepairExecutionResult:
        output_repo = OutputMetadataRepository(self._session)
        output = output_repo.get(row.target_id)
        if output is None:
            raise RepairActionWorkflowError(f"output not found: {row.target_id}")
        target_before = _target_snapshot(output, RepairTargetType.OUTPUT)
        service = _output_service(self._session, output_repo)
        if output.output_type == OutputType.REGION_OUTPUT.value:
            rebuilt = service.build_region(output.subject_id)
        elif output.output_type == OutputType.COMPANY_OUTPUT.value:
            rebuilt = service.build_company(output.subject_id)
        elif output.output_type == OutputType.COMPARISON_OUTPUT.value:
            region_a, region_b = _split_comparison_subject(output.subject_id)
            rebuilt = service.build_comparison(region_a, region_b)
        else:
            raise RepairActionWorkflowError(
                f"unsupported output type for rebuild: {output.output_type}"
            )
        assert rebuilt.metadata is not None
        return RepairExecutionResult(
            result={
                "action": "rebuild_output",
                "output_id": rebuilt.metadata.output_id,
                "output_type": rebuilt.metadata.output_type,
                "subject_id": rebuilt.metadata.subject_id,
                "outcome": rebuilt.action,
            },
            target_before=target_before,
            target_after=_target_snapshot(rebuilt.metadata, RepairTargetType.OUTPUT),
        )

    def _execute_mark_source_stale(
        self,
        row: AdminRepairAction,
    ) -> RepairExecutionResult:
        source = self._session.get(SourceRef, row.target_id)
        if source is None:
            raise RepairActionWorkflowError(f"source ref not found: {row.target_id}")
        before = _target_snapshot(source, RepairTargetType.SOURCE_REF)
        if source.state != ObjectState.STALE.value:
            validate_transition(source.state, ObjectState.STALE)
            source.state = ObjectState.STALE.value
        self._session.flush()
        after = _target_snapshot(source, RepairTargetType.SOURCE_REF)
        return RepairExecutionResult(
            result={
                "action": "mark_source_stale",
                "source_id": source.source_id,
                "source_history_preserved": True,
            },
            target_before=before,
            target_after=after,
        )

    def _execute_request_review(
        self,
        row: AdminRepairAction,
    ) -> RepairExecutionResult:
        target_type = RepairTargetType(row.target_type)
        target = self._repair_target(target_type, row.target_id)
        snapshot = _target_snapshot(target, target_type)
        return RepairExecutionResult(
            result={
                "action": "request_review",
                "review_requested": True,
                "canonical_mutation": False,
            },
            target_before=snapshot,
            target_after=snapshot,
        )

    def _execute_deactivate_bad_fact(
        self,
        row: AdminRepairAction,
    ) -> RepairExecutionResult:
        target_type = RepairTargetType(row.target_type)
        target = self._repair_target(target_type, row.target_id)
        if target is None:
            raise RepairActionWorkflowError(
                f"fact target not found: {row.target_type}:{row.target_id}"
            )
        before = _target_snapshot(target, target_type)
        _walk_to_blocked(target)
        self._session.flush()
        after = _target_snapshot(target, target_type)
        return RepairExecutionResult(
            result={
                "action": "deactivate_bad_fact",
                "target_type": row.target_type,
                "target_id": row.target_id,
                "canonical_row_preserved": True,
                "provenance_history_preserved": True,
            },
            target_before=before,
            target_after=after,
        )

    def _repair_target(
        self,
        target_type: RepairTargetType,
        target_id: str,
    ) -> Any | None:
        if target_type is RepairTargetType.REGION:
            return self._session.get(Region, target_id)
        if target_type is RepairTargetType.OUTPUT:
            return self._session.get(OutputMetadata, target_id)
        if target_type is RepairTargetType.COMPANY:
            return self._session.get(Company, target_id)
        if target_type is RepairTargetType.PRESENCE_FACT:
            return self._session.get(CompanyRegionPresence, target_id)
        if target_type is RepairTargetType.HIRING_FACT:
            return self._session.get(CompanyRegionHiring, target_id)
        if target_type is RepairTargetType.ENTRY_LEVEL_FACT:
            return self._session.get(CompanyRegionEntryLevel, target_id)
        if target_type is RepairTargetType.SOURCE_REF:
            return self._session.get(SourceRef, target_id)
        if target_type is RepairTargetType.AUDIT_FINDING:
            return AdminReviewService(session=self._session).get_audit_finding(target_id)
        return None

    def _record_repair_event(
        self,
        row: AdminRepairAction,
        *,
        actor: str,
        role: AdminRole,
        action: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any],
        reason: str,
        request_id: str | None,
    ) -> None:
        self._event_log.record_event(
            AdminEventLogInput(
                actor=actor,
                role=role,
                action=action,
                object_type="admin_repair_action",
                object_id=row.repair_action_id,
                before_state=before_state,
                after_state=after_state,
                reason=reason,
                request_id=request_id,
            )
        )


def admin_override_data(row: AdminOverride) -> dict[str, Any]:
    return {
        "override_id": row.override_id,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "override_type": row.override_type,
        "previous_value": deepcopy(row.previous_value),
        "override_value": deepcopy(row.override_value),
        "reason": row.reason,
        "reviewer_actor": row.reviewer_actor,
        "reviewer_role": row.reviewer_role,
        "source_evidence": deepcopy(row.source_evidence),
        "expires_at": _dt(row.expires_at),
        "review_at": _dt(row.review_at),
        "status": row.status,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "activated_at": _dt(row.activated_at),
        "activated_by": row.activated_by,
        "activated_role": row.activated_role,
        "revoked_at": _dt(row.revoked_at),
        "revoked_by": row.revoked_by,
        "revoked_role": row.revoked_role,
        "revocation_reason": row.revocation_reason,
    }


def admin_repair_action_data(row: AdminRepairAction) -> dict[str, Any]:
    return {
        "repair_action_id": row.repair_action_id,
        "action_type": row.action_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "status": row.status,
        "reason": row.reason,
        "requested_by": row.requested_by,
        "requested_role": row.requested_role,
        "requested_at": _dt(row.requested_at),
        "executed_by": row.executed_by,
        "executed_role": row.executed_role,
        "executed_at": _dt(row.executed_at),
        "audit_finding_id": row.audit_finding_id,
        "parameters": deepcopy(row.parameters),
        "result": deepcopy(row.result),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _validate_override_compatibility(
    target_type: OverrideTargetType,
    override_type: OverrideType,
) -> None:
    expected = OVERRIDE_TARGETS[override_type]
    if target_type is not expected:
        raise OverrideWorkflowError(
            f"{override_type.value} overrides require target_type={expected.value}"
        )


def _validate_override_value(override_type: OverrideType, value: Any) -> None:
    if value is None:
        raise OverrideWorkflowError("override_value is required")
    if override_type is OverrideType.COMPANY_ELIGIBILITY:
        raw = _field_or_value(value, "eligibility_status")
        if raw not in EligibilityStatus.values():
            raise OverrideWorkflowError("invalid company eligibility override value")
        return
    if override_type is OverrideType.COMPANY_CLASSIFICATION:
        _validate_classification_override(value)
        return
    if override_type is OverrideType.PRESENCE_STATUS:
        raw = _field_or_value(value, "presence_status")
        if raw not in PresenceStatus.values():
            raise OverrideWorkflowError("invalid presence status override value")
        return
    if override_type is OverrideType.SOURCE_CONFIDENCE:
        raw = _field_or_value(value, "confidence")
        if raw not in Confidence.values():
            raise OverrideWorkflowError("invalid source confidence override value")


def _validate_classification_override(value: Any) -> None:
    if not isinstance(value, dict) or not value:
        raise OverrideWorkflowError("company classification override must be an object")
    allowed = {
        "sector_primary",
        "sector_secondary",
        "public_or_private",
        "classification_confidence",
        "is_major_tech",
        "is_mag7",
        "prestige_score",
    }
    extra = set(value) - allowed
    if extra:
        raise OverrideWorkflowError(
            f"unsupported company classification override fields: {sorted(extra)}"
        )
    if "classification_confidence" in value and value[
        "classification_confidence"
    ] not in ClassificationConfidence.values():
        raise OverrideWorkflowError("invalid classification confidence override value")
    if "public_or_private" in value and value["public_or_private"] is not None:
        if value["public_or_private"] not in PublicOrPrivate.values():
            raise OverrideWorkflowError("invalid public/private override value")
    for key in ("sector_primary", "sector_secondary"):
        if key in value and value[key] is not None:
            _nonblank(value[key])
    for key in ("is_major_tech", "is_mag7"):
        if key in value and not isinstance(value[key], bool):
            raise OverrideWorkflowError(f"{key} override must be boolean")
    if "prestige_score" in value and value["prestige_score"] is not None:
        score = value["prestige_score"]
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise OverrideWorkflowError("prestige_score override must be numeric")
        if score < 0 or score > 1:
            raise OverrideWorkflowError("prestige_score override must be between 0 and 1")


def _validate_repair_compatibility(
    target_type: RepairTargetType,
    action_type: RepairActionType,
) -> None:
    allowed = REPAIR_TARGETS[action_type]
    if target_type not in allowed:
        allowed_values = ", ".join(sorted(target.value for target in allowed))
        raise RepairActionWorkflowError(
            f"{action_type.value} requires target_type in: {allowed_values}"
        )


def _override_is_effectively_active(row: AdminOverride, *, now: datetime) -> bool:
    if row.status != OverrideStatus.ACTIVE.value:
        return False
    if row.expires_at is not None and _aware(row.expires_at) <= now:
        return False
    return True


def _observed_override_value(
    target: Company | CompanyRegionPresence | SourceRef,
    override_type: OverrideType,
) -> dict[str, Any]:
    if override_type is OverrideType.COMPANY_ELIGIBILITY:
        assert isinstance(target, Company)
        return {
            "eligibility_status": target.eligibility_status,
            "eligibility_override_flag": target.eligibility_override_flag,
            "eligibility_override_reason": target.eligibility_override_reason,
        }
    if override_type is OverrideType.COMPANY_CLASSIFICATION:
        assert isinstance(target, Company)
        return {
            "sector_primary": target.sector_primary,
            "sector_secondary": target.sector_secondary,
            "public_or_private": target.public_or_private,
            "classification_confidence": target.classification_confidence,
            "is_major_tech": target.is_major_tech,
            "is_mag7": target.is_mag7,
            "prestige_score": target.prestige_score,
        }
    if override_type is OverrideType.PRESENCE_STATUS:
        assert isinstance(target, CompanyRegionPresence)
        return {
            "presence_status": target.presence_status,
            "presence_basis": target.presence_basis,
            "presence_confidence": target.presence_confidence,
        }
    if override_type is OverrideType.SOURCE_CONFIDENCE:
        assert isinstance(target, SourceRef)
        return {"confidence": target.confidence}
    raise OverrideWorkflowError(f"unsupported override type: {override_type.value}")


def _target_snapshot(target: Any, target_type: RepairTargetType) -> dict[str, Any] | None:
    if target is None:
        return None
    if target_type is RepairTargetType.REGION:
        return {"region_id": target.region_id, "state": target.state}
    if target_type is RepairTargetType.OUTPUT:
        return {
            "output_id": target.output_id,
            "output_type": target.output_type,
            "subject_id": target.subject_id,
            "state": target.state,
            "version": target.version,
            "artifact_hash": target.artifact_hash,
            "source_version_refs": deepcopy(target.source_version_refs),
        }
    if target_type is RepairTargetType.COMPANY:
        return {
            "company_id": target.company_id,
            "state": target.state,
            "version": target.version,
            "eligibility_status": target.eligibility_status,
            "classification_confidence": target.classification_confidence,
        }
    if target_type is RepairTargetType.PRESENCE_FACT:
        return {
            "presence_id": target.presence_id,
            "state": target.state,
            "version": target.version,
            "presence_status": target.presence_status,
            "source_refs": deepcopy(target.source_refs),
            "provenance_link_count": _fact_link_count(
                target_type.value,
                target.presence_id,
            ),
        }
    if target_type is RepairTargetType.HIRING_FACT:
        return {
            "hiring_id": target.hiring_id,
            "state": target.state,
            "version": target.version,
            "source_refs": deepcopy(target.source_refs),
            "provenance_link_count": _fact_link_count(
                target_type.value,
                target.hiring_id,
            ),
        }
    if target_type is RepairTargetType.ENTRY_LEVEL_FACT:
        return {
            "entry_level_id": target.entry_level_id,
            "state": target.state,
            "version": target.version,
            "source_refs": deepcopy(target.source_refs),
            "provenance_link_count": _fact_link_count(
                target_type.value,
                target.entry_level_id,
            ),
        }
    if target_type is RepairTargetType.SOURCE_REF:
        return {
            "source_id": target.source_id,
            "state": target.state,
            "version": target.version,
            "confidence": target.confidence,
            "observation_count": len(list(target.observations or [])),
        }
    if target_type is RepairTargetType.AUDIT_FINDING:
        return {"finding_id": target.finding_id, "review_state": target.review_state.value}
    return None


def _fact_link_count(_fact_type: str, _fact_id: str) -> int | None:
    # Counts are intentionally omitted from snapshots here because this helper
    # has no session. Tests assert persistence directly on FactSourceLink rows.
    return None


def _score_snapshot(row: RegionMarketScore | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "region_score_id": row.region_score_id,
        "region_id": row.region_id,
        "state": row.state,
        "version": row.version,
        "raw_total_score": row.raw_total_score,
        "score_ruleset_version": row.score_ruleset_version,
    }


def _walk_to_blocked(target: Any) -> None:
    if target.state == ObjectState.BLOCKED.value:
        return
    if target.state == ObjectState.FRESH.value:
        validate_transition(target.state, ObjectState.STALE)
        target.state = ObjectState.STALE.value
    validate_transition(target.state, ObjectState.BLOCKED)
    target.state = ObjectState.BLOCKED.value


def _output_service(
    session: Session,
    output_repo: OutputMetadataRepository | None = None,
) -> OutputAssemblyService:
    return OutputAssemblyService(
        output_repo or OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _field_or_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return value


def _split_comparison_subject(subject_id: str) -> tuple[str, str]:
    parts = [part for part in subject_id.split("__") if part]
    if len(parts) != 2:
        raise RepairActionWorkflowError(f"invalid comparison subject_id: {subject_id!r}")
    return parts[0], parts[1]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _nonblank(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _optional_nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    return _nonblank(value)


def _new_override_id() -> str:
    return f"admin_override_{uuid4().hex[:48]}"


def _new_repair_action_id() -> str:
    return f"admin_repair_{uuid4().hex[:50]}"


__all__ = [
    "AdminOverrideCreateInput",
    "AdminOverrideMutationInput",
    "AdminOverrideService",
    "AdminRepairActionCreateInput",
    "AdminRepairActionExecuteInput",
    "AdminRepairActionService",
    "OverrideNotFound",
    "OverrideStatus",
    "OverrideTargetType",
    "OverrideType",
    "OverrideWorkflowError",
    "RepairActionNotFound",
    "RepairActionStatus",
    "RepairActionType",
    "RepairActionWorkflowError",
    "RepairTargetType",
    "admin_override_data",
    "admin_repair_action_data",
]
