"""Entry-level opportunity service.

Owns:
* :class:`EntryLevelSnapshot` — structured input for one refresh of a
  company-region pair;
* :class:`EntryLevelDefinition` — wraps the snapshot with its identifiers;
* :class:`EntryLevelService` — create / update / upsert with the
  conservative state-machine flow established by Slices 5–8.

Out of scope: scoring beyond the access-score formula in
:mod:`backend.entry_level.scoring`, region scoring, output assembly,
ingestion, NLP. The service uses only the :class:`HiringRepository` from
upstream domains for *existence* checks — never the hiring service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.entry_level.exceptions import (
    DuplicateEntryLevel,
    EntryLevelNotFound,
    MissingHiringForEntryLevel,
)
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.scoring import compute_entry_level_access_score
from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)
from backend.hiring.repository import HiringRepository
from backend.shared.provenance import ObservationStatus
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]


class EntryLevelSnapshot(BaseModel):
    """One snapshot of early-career opportunity for a company-region pair.

    Counts default to ``None`` (unknown). Internships and co-ops are stored
    separately but treated equally by the scoring formula (see
    :mod:`backend.entry_level.scoring`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    internship_count: int | None = None
    internship_count_status: ObservationStatus | None = None
    coop_count: int | None = None
    coop_count_status: ObservationStatus | None = None
    entry_level_full_time_count: int | None = None
    entry_level_full_time_count_status: ObservationStatus | None = None
    formal_early_career_program_flag: bool = False
    student_season_recurrence_signal: StudentSeasonRecurrenceSignal | None = None
    freshness_expires_at: datetime | None = None
    source_refs: list[dict] | dict | None = None

    @field_validator(
        "internship_count",
        "coop_count",
        "entry_level_full_time_count",
        mode="before",
    )
    @classmethod
    def _counts_non_negative(cls, value: object) -> int | None:
        if value is None:
            return None
        # ``mode="before"`` lets us see the raw type before Pydantic coerces
        # ``bool → int``. Booleans must be rejected explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"count must be an int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"count must be non-negative, got {value}")
        return value

    @field_validator("freshness_expires_at")
    @classmethod
    def _freshness_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("freshness_expires_at must be timezone-aware")
        return value


class EntryLevelDefinition(BaseModel):
    """Input shape for create / update / upsert."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_level_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    snapshot: EntryLevelSnapshot


class EntryLevelService:
    def __init__(
        self,
        repository: EntryLevelRepository,
        *,
        hiring_repo: HiringRepository,
    ) -> None:
        self._repo = repository
        self._hiring_repo = hiring_repo

    # --- reads -----------------------------------------------------------

    def get_entry_level(self, entry_level_id: str) -> CompanyRegionEntryLevel:
        row = self._repo.get(entry_level_id)
        if row is None:
            raise EntryLevelNotFound(entry_level_id)
        return row

    def get_entry_level_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionEntryLevel:
        row = self._repo.get_by_pair(company_id, region_id)
        if row is None:
            raise EntryLevelNotFound(f"({company_id}, {region_id})")
        return row

    def list_entry_level(self) -> list[CompanyRegionEntryLevel]:
        return self._repo.list()

    # --- writes ----------------------------------------------------------

    def create_entry_level(
        self, definition: EntryLevelDefinition
    ) -> CompanyRegionEntryLevel:
        self._validate_pair(definition.company_id, definition.region_id)
        if self._repo.exists(definition.entry_level_id):
            raise DuplicateEntryLevel(definition.entry_level_id)
        if (
            self._repo.get_by_pair(definition.company_id, definition.region_id)
            is not None
        ):
            raise DuplicateEntryLevel(
                f"({definition.company_id}, {definition.region_id})"
            )
        row = CompanyRegionEntryLevel(
            entry_level_id=definition.entry_level_id,
            company_id=definition.company_id,
            region_id=definition.region_id,
        )
        self._apply_snapshot(row, definition.snapshot)
        self._repo.add(row)
        self._repo.flush()
        return row

    def update_entry_level(
        self, definition: EntryLevelDefinition
    ) -> CompanyRegionEntryLevel:
        existing = self.get_entry_level(definition.entry_level_id)
        if (
            existing.company_id != definition.company_id
            or existing.region_id != definition.region_id
        ):
            raise EntryLevelNotFound(
                f"entry_level {definition.entry_level_id!r} bound to "
                f"({existing.company_id}, {existing.region_id}), not "
                f"({definition.company_id}, {definition.region_id})"
            )
        self._validate_pair(definition.company_id, definition.region_id)
        self._apply_snapshot(existing, definition.snapshot)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing

    def upsert_for_refresh(
        self, definition: EntryLevelDefinition
    ) -> tuple[CompanyRegionEntryLevel, UpsertOutcome]:
        """Idempotent upsert keyed on ``(company_id, region_id)``.

        Mirrors Slice 5–8 state-machine flow. ``"unchanged"`` is returned
        when every snapshot field except ``freshness_expires_at`` matches
        the stored row (rolling the freshness window forward without
        changing data is not a meaningful change).
        """
        self._validate_pair(definition.company_id, definition.region_id)
        existing = self._repo.get_by_pair(definition.company_id, definition.region_id)
        if existing is None:
            row = self.create_entry_level(definition)
            self._set_state(row, ObjectState.BUILDING)
            self._set_state(row, ObjectState.FRESH)
            self._repo.flush()
            return row, "created"

        if self._is_unchanged(existing, definition.snapshot):
            return existing, "unchanged"

        self._apply_snapshot(existing, definition.snapshot)
        existing.version = next_version(existing.version)
        if existing.state == ObjectState.NEW.value:
            self._set_state(existing, ObjectState.BUILDING)
            self._set_state(existing, ObjectState.FRESH)
        elif existing.state == ObjectState.BUILDING.value:
            self._set_state(existing, ObjectState.FRESH)
        self._repo.flush()
        return existing, "updated"

    # --- internals -------------------------------------------------------

    def _validate_pair(self, company_id: str, region_id: str) -> None:
        hiring = self._hiring_repo.get_by_pair(company_id, region_id)
        if hiring is None:
            raise MissingHiringForEntryLevel(f"({company_id}, {region_id})")

    def _apply_snapshot(
        self, row: CompanyRegionEntryLevel, snapshot: EntryLevelSnapshot
    ) -> None:
        row.internship_count = snapshot.internship_count
        row.internship_count_status = (
            snapshot.internship_count_status.value
            if snapshot.internship_count_status
            else None
        )
        row.coop_count = snapshot.coop_count
        row.coop_count_status = (
            snapshot.coop_count_status.value if snapshot.coop_count_status else None
        )
        row.entry_level_full_time_count = snapshot.entry_level_full_time_count
        row.entry_level_full_time_count_status = (
            snapshot.entry_level_full_time_count_status.value
            if snapshot.entry_level_full_time_count_status
            else None
        )
        row.formal_early_career_program_flag = snapshot.formal_early_career_program_flag
        row.student_season_recurrence_signal = (
            snapshot.student_season_recurrence_signal.value
            if snapshot.student_season_recurrence_signal
            else None
        )
        row.freshness_expires_at = snapshot.freshness_expires_at
        row.source_refs = snapshot.source_refs

        result = compute_entry_level_access_score(
            internship_count=snapshot.internship_count,
            coop_count=snapshot.coop_count,
            entry_level_full_time_count=snapshot.entry_level_full_time_count,
            formal_early_career_program_flag=snapshot.formal_early_career_program_flag,
            student_season_recurrence_signal=snapshot.student_season_recurrence_signal,
        )
        row.entry_level_access_score = result.score
        row.entry_level_confidence = result.confidence.value

    def _set_state(
        self, row: CompanyRegionEntryLevel, target: ObjectState
    ) -> None:
        validate_transition(row.state, target)
        row.state = target.value

    def _is_unchanged(
        self,
        row: CompanyRegionEntryLevel,
        snapshot: EntryLevelSnapshot,
    ) -> bool:
        proposed_recurrence = (
            snapshot.student_season_recurrence_signal.value
            if snapshot.student_season_recurrence_signal
            else None
        )
        proposed_internship_status = (
            snapshot.internship_count_status.value
            if snapshot.internship_count_status
            else None
        )
        proposed_coop_status = (
            snapshot.coop_count_status.value if snapshot.coop_count_status else None
        )
        proposed_full_time_status = (
            snapshot.entry_level_full_time_count_status.value
            if snapshot.entry_level_full_time_count_status
            else None
        )
        return (
            row.internship_count == snapshot.internship_count
            and row.internship_count_status == proposed_internship_status
            and row.coop_count == snapshot.coop_count
            and row.coop_count_status == proposed_coop_status
            and row.entry_level_full_time_count == snapshot.entry_level_full_time_count
            and row.entry_level_full_time_count_status == proposed_full_time_status
            and row.formal_early_career_program_flag
            == snapshot.formal_early_career_program_flag
            and row.student_season_recurrence_signal == proposed_recurrence
            and row.source_refs == snapshot.source_refs
        )


# Re-export so callers may also access the bare formula helpers when
# needed (e.g. tests). Kept thin to avoid circular imports.
__all__ = [
    "EntryLevelConfidence",
    "EntryLevelDefinition",
    "EntryLevelService",
    "EntryLevelSnapshot",
    "StudentSeasonRecurrenceSignal",
]
