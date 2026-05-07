"""Hiring activity service.

Owns:

* :class:`HiringSnapshot` — the structured payload describing one
  refresh of a company-region pair;
* :class:`HiringDefinition` — wraps a snapshot with the
  ``hiring_id`` / ``company_id`` / ``region_id`` it applies to;
* :class:`HiringService` — create / update / upsert with the
  conservative state-machine flow established by Slices 5–7.

Out of scope: live source ingestion, scoring, normalization, entry-level
extraction. The service uses only the :class:`PresenceRepository` from
upstream domains for *existence* checks — never the presence service or
evidence-evaluation logic (the slice plan forbids re-evaluating presence).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.hiring.exceptions import (
    DuplicateHiring,
    HiringNotFound,
    InvalidHiringPair,
    MissingPresenceForHiring,
)
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.hiring.role_families import validate_role_family_summary
from backend.hiring.types import (
    AnnualizedTrendSignal,
    HiringConfidence,
    SeasonalStudentHiringSignal,
)
from backend.presence.repository import PresenceRepository
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]

# Presence statuses that allow hiring tracking. Only ``present`` qualifies.
# ``uncertain`` and ``not_present`` should not carry hiring records — that's
# the documented semantics in STAGE_BY_STAGE_EXECUTION_PROTOCOL.md §8 ("only
# present firms continue into region-specific hiring assessment").
_PRESENCE_OK = frozenset({"present"})


class HiringSnapshot(BaseModel):
    """One snapshot of hiring activity for a company-region pair.

    Counts default to ``None`` (unknown). They never silently roll forward as
    zero. Pydantic validators reject negative counts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    currently_hiring_flag: bool
    active_posting_count_now: int | None = None
    posting_count_30d: int | None = None
    posting_count_90d: int | None = None
    annualized_trend_signal: AnnualizedTrendSignal | None = None
    seasonal_student_hiring_signal: SeasonalStudentHiringSignal | None = None
    hiring_program_count: int | None = None
    role_family_summary: dict[str, int] | None = None
    hiring_confidence: HiringConfidence | None = None
    freshness_expires_at: datetime | None = None
    source_refs: list[dict] | dict | None = None

    @field_validator(
        "active_posting_count_now",
        "posting_count_30d",
        "posting_count_90d",
        "hiring_program_count",
    )
    @classmethod
    def _counts_non_negative(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"count must be an int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"count must be non-negative, got {value}")
        return value

    @field_validator("role_family_summary")
    @classmethod
    def _role_family_summary_well_formed(
        cls, value: Any
    ) -> dict[str, int] | None:
        validate_role_family_summary(value)
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


class HiringDefinition(BaseModel):
    """Input shape for create / update / upsert."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hiring_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    snapshot: HiringSnapshot


class HiringService:
    def __init__(
        self,
        repository: HiringRepository,
        *,
        presence_repo: PresenceRepository,
    ) -> None:
        self._repo = repository
        self._presence_repo = presence_repo

    # --- reads -----------------------------------------------------------

    def get_hiring(self, hiring_id: str) -> CompanyRegionHiring:
        row = self._repo.get(hiring_id)
        if row is None:
            raise HiringNotFound(hiring_id)
        return row

    def get_hiring_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionHiring:
        row = self._repo.get_by_pair(company_id, region_id)
        if row is None:
            raise HiringNotFound(f"({company_id}, {region_id})")
        return row

    def list_hiring(self) -> list[CompanyRegionHiring]:
        return self._repo.list()

    # --- writes ----------------------------------------------------------

    def create_hiring(self, definition: HiringDefinition) -> CompanyRegionHiring:
        self._validate_pair(definition.company_id, definition.region_id)
        if self._repo.exists(definition.hiring_id):
            raise DuplicateHiring(definition.hiring_id)
        if (
            self._repo.get_by_pair(definition.company_id, definition.region_id)
            is not None
        ):
            raise DuplicateHiring(
                f"({definition.company_id}, {definition.region_id})"
            )
        row = CompanyRegionHiring(
            hiring_id=definition.hiring_id,
            company_id=definition.company_id,
            region_id=definition.region_id,
        )
        self._apply_snapshot(row, definition.snapshot)
        self._repo.add(row)
        self._repo.flush()
        return row

    def update_hiring(self, definition: HiringDefinition) -> CompanyRegionHiring:
        existing = self.get_hiring(definition.hiring_id)
        if (
            existing.company_id != definition.company_id
            or existing.region_id != definition.region_id
        ):
            raise HiringNotFound(
                f"hiring {definition.hiring_id!r} bound to "
                f"({existing.company_id}, {existing.region_id}), not "
                f"({definition.company_id}, {definition.region_id})"
            )
        self._validate_pair(definition.company_id, definition.region_id)
        self._apply_snapshot(existing, definition.snapshot)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing

    def upsert_for_refresh(
        self, definition: HiringDefinition
    ) -> tuple[CompanyRegionHiring, UpsertOutcome]:
        """Idempotent upsert keyed on ``(company_id, region_id)``.

        Mirrors Slice 5/6/7 state-machine flow. ``"unchanged"`` is returned
        when every data field on the snapshot matches the stored row;
        ``freshness_expires_at`` is intentionally **not** part of the
        comparison because rolling the freshness window forward without
        changing data is not a meaningful change.
        """
        self._validate_pair(definition.company_id, definition.region_id)
        existing = self._repo.get_by_pair(definition.company_id, definition.region_id)
        if existing is None:
            row = self.create_hiring(definition)
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
        presence = self._presence_repo.get_by_pair(company_id, region_id)
        if presence is None:
            raise MissingPresenceForHiring(f"({company_id}, {region_id})")
        if presence.presence_status not in _PRESENCE_OK:
            raise InvalidHiringPair(
                f"({company_id}, {region_id}) presence_status="
                f"{presence.presence_status!r}, only 'present' qualifies for "
                "hiring tracking"
            )

    def _apply_snapshot(
        self, row: CompanyRegionHiring, snapshot: HiringSnapshot
    ) -> None:
        row.currently_hiring_flag = snapshot.currently_hiring_flag
        row.active_posting_count_now = snapshot.active_posting_count_now
        row.posting_count_30d = snapshot.posting_count_30d
        row.posting_count_90d = snapshot.posting_count_90d
        row.annualized_trend_signal = (
            snapshot.annualized_trend_signal.value
            if snapshot.annualized_trend_signal
            else None
        )
        row.seasonal_student_hiring_signal = (
            snapshot.seasonal_student_hiring_signal.value
            if snapshot.seasonal_student_hiring_signal
            else None
        )
        row.hiring_program_count = snapshot.hiring_program_count
        row.role_family_summary = snapshot.role_family_summary
        row.hiring_confidence = (
            snapshot.hiring_confidence.value if snapshot.hiring_confidence else None
        )
        row.freshness_expires_at = snapshot.freshness_expires_at
        row.source_refs = snapshot.source_refs

    def _set_state(self, row: CompanyRegionHiring, target: ObjectState) -> None:
        validate_transition(row.state, target)
        row.state = target.value

    def _is_unchanged(
        self, row: CompanyRegionHiring, snapshot: HiringSnapshot
    ) -> bool:
        proposed_trend = (
            snapshot.annualized_trend_signal.value
            if snapshot.annualized_trend_signal
            else None
        )
        proposed_seasonal = (
            snapshot.seasonal_student_hiring_signal.value
            if snapshot.seasonal_student_hiring_signal
            else None
        )
        proposed_confidence = (
            snapshot.hiring_confidence.value
            if snapshot.hiring_confidence
            else None
        )
        return (
            row.currently_hiring_flag == snapshot.currently_hiring_flag
            and row.active_posting_count_now == snapshot.active_posting_count_now
            and row.posting_count_30d == snapshot.posting_count_30d
            and row.posting_count_90d == snapshot.posting_count_90d
            and row.annualized_trend_signal == proposed_trend
            and row.seasonal_student_hiring_signal == proposed_seasonal
            and row.hiring_program_count == snapshot.hiring_program_count
            and row.role_family_summary == snapshot.role_family_summary
            and row.hiring_confidence == proposed_confidence
            and row.source_refs == snapshot.source_refs
        )
