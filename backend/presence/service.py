"""Company-region presence service.

Owns:
* the :class:`PresenceDefinition` Pydantic input shape,
* create / update / upsert operations against
  :class:`backend.presence.models.CompanyRegionPresence`,
* existence-only checks for company_id / region_id (no eligibility filtering,
  no geography-building),
* state-machine integration (mirrors Slice 5 / 6 patterns).

Out of scope: hiring/entry-level/scoring/output assembly, queue/worker
runtime, event routing, live source ingestion, GIS validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.companies.repository import CompanyRepository
from backend.geography.repository import RegionRepository
from backend.presence.evidence import (
    PresenceDecision,
    PresenceEvidence,
    evaluate_presence,
)
from backend.presence.exceptions import (
    DuplicatePresence,
    MissingCompanyForPresence,
    MissingRegionForPresence,
    PresenceNotFound,
)
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]


class PresenceDefinition(BaseModel):
    """Input shape for create / update / upsert operations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    presence_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    evidence: PresenceEvidence


class PresenceService:
    def __init__(
        self,
        repository: PresenceRepository,
        *,
        company_repo: CompanyRepository,
        region_repo: RegionRepository,
        prefer_hiring_evidence: bool = True,
        allow_satellite_office_presence: bool = True,
    ) -> None:
        self._repo = repository
        self._company_repo = company_repo
        self._region_repo = region_repo
        self._prefer_hiring_evidence = prefer_hiring_evidence
        self._allow_satellite_office_presence = allow_satellite_office_presence

    # --- reads -----------------------------------------------------------

    def get_presence(self, presence_id: str) -> CompanyRegionPresence:
        presence = self._repo.get(presence_id)
        if presence is None:
            raise PresenceNotFound(presence_id)
        return presence

    def get_presence_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionPresence:
        presence = self._repo.get_by_pair(company_id, region_id)
        if presence is None:
            raise PresenceNotFound(f"({company_id}, {region_id})")
        return presence

    def list_presence(self) -> list[CompanyRegionPresence]:
        return self._repo.list()

    # --- writes ----------------------------------------------------------

    def create_presence(self, definition: PresenceDefinition) -> CompanyRegionPresence:
        self._validate_existence(definition)
        if self._repo.exists(definition.presence_id):
            raise DuplicatePresence(definition.presence_id)
        if (
            self._repo.get_by_pair(definition.company_id, definition.region_id)
            is not None
        ):
            raise DuplicatePresence(
                f"({definition.company_id}, {definition.region_id})"
            )
        decision = self._decide(definition.evidence)
        presence = CompanyRegionPresence(
            presence_id=definition.presence_id,
            company_id=definition.company_id,
            region_id=definition.region_id,
            presence_status=decision.status.value,
            presence_basis=decision.basis.value,
            office_evidence_flag=definition.evidence.office_evidence_flag,
            operations_evidence_flag=definition.evidence.operations_evidence_flag,
            hiring_evidence_flag=definition.evidence.hiring_evidence_flag,
            presence_confidence=decision.confidence.value,
            source_refs=definition.evidence.source_refs,
        )
        self._repo.add(presence)
        self._repo.flush()
        return presence

    def update_presence(self, definition: PresenceDefinition) -> CompanyRegionPresence:
        existing = self.get_presence(definition.presence_id)
        if (
            existing.company_id != definition.company_id
            or existing.region_id != definition.region_id
        ):
            raise PresenceNotFound(
                f"presence {definition.presence_id!r} bound to "
                f"({existing.company_id}, {existing.region_id}), not "
                f"({definition.company_id}, {definition.region_id})"
            )
        self._validate_existence(definition)
        self._apply_decision(existing, definition.evidence)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing

    def upsert_for_mapping(
        self, definition: PresenceDefinition
    ) -> tuple[CompanyRegionPresence, UpsertOutcome]:
        """Idempotent upsert keyed on ``(company_id, region_id)``.

        State-machine flow mirrors Slice 5 / 6: brand-new rows walk
        ``new → building → fresh``; rows whose evidence is identical to the
        stored evidence return ``"unchanged"``; rows with changed evidence
        bump version and (if still ``new``/``building``) walk to ``fresh``.
        Reaching ``rebuilding`` requires ``stale`` per ``OBJECT_STATE_MODEL.md``
        §17 — Slices 14+.
        """
        self._validate_existence(definition)
        existing = self._repo.get_by_pair(definition.company_id, definition.region_id)
        if existing is None:
            presence = self.create_presence(definition)
            self._set_state(presence, ObjectState.BUILDING)
            self._set_state(presence, ObjectState.FRESH)
            self._repo.flush()
            return presence, "created"

        if self._is_unchanged(existing, definition):
            return existing, "unchanged"

        self._apply_decision(existing, definition.evidence)
        existing.version = next_version(existing.version)
        if existing.state == ObjectState.NEW.value:
            self._set_state(existing, ObjectState.BUILDING)
            self._set_state(existing, ObjectState.FRESH)
        elif existing.state == ObjectState.BUILDING.value:
            self._set_state(existing, ObjectState.FRESH)
        self._repo.flush()
        return existing, "updated"

    # --- internals -------------------------------------------------------

    def _validate_existence(self, definition: PresenceDefinition) -> None:
        if not self._company_repo.exists(definition.company_id):
            raise MissingCompanyForPresence(definition.company_id)
        if not self._region_repo.exists(definition.region_id):
            raise MissingRegionForPresence(definition.region_id)

    def _decide(self, evidence: PresenceEvidence) -> PresenceDecision:
        return evaluate_presence(
            evidence,
            prefer_hiring_evidence=self._prefer_hiring_evidence,
            allow_satellite_office_presence=self._allow_satellite_office_presence,
        )

    def _apply_decision(
        self, presence: CompanyRegionPresence, evidence: PresenceEvidence
    ) -> None:
        decision = self._decide(evidence)
        presence.presence_status = decision.status.value
        presence.presence_basis = decision.basis.value
        presence.office_evidence_flag = evidence.office_evidence_flag
        presence.operations_evidence_flag = evidence.operations_evidence_flag
        presence.hiring_evidence_flag = evidence.hiring_evidence_flag
        presence.presence_confidence = decision.confidence.value
        presence.source_refs = evidence.source_refs

    def _set_state(
        self, presence: CompanyRegionPresence, target: ObjectState
    ) -> None:
        validate_transition(presence.state, target)
        presence.state = target.value

    def _is_unchanged(
        self,
        presence: CompanyRegionPresence,
        definition: PresenceDefinition,
    ) -> bool:
        ev = definition.evidence
        return (
            presence.office_evidence_flag == ev.office_evidence_flag
            and presence.operations_evidence_flag == ev.operations_evidence_flag
            and presence.hiring_evidence_flag == ev.hiring_evidence_flag
            and presence.source_refs == ev.source_refs
        )
