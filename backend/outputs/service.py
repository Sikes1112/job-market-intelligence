"""Output assembly service.

Reads canonical truth via Slice 5–10 repositories and writes only
``OutputMetadata`` rows. Returns ``(OutputMetadata row, payload, action)``
tuples so callers (Slice 12 API) can serialize the payload from memory
without reading it from storage.

Hard rules enforced at this layer:

* upstream domain *services* and the Slice 9/10 scoring formulas are
  forbidden imports (verified by the layer-isolation test);
* the only writable target is ``OutputMetadata``;
* API read paths can assemble payloads without mutating ``OutputMetadata``;
* identical persisted builds (matching ``artifact_hash``) return ``"unchanged"`` —
  no version bump, no state change;
* changed persisted rebuilds walk through ``rebuilding`` instead of preserving
  stale/fresh/partial state incorrectly.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.market_coverage import (
    CoverageMetadataPayload,
    build_region_coverage_metadata,
)
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.outputs.cache import (
    load_cached_output,
    mark_rebuild_succeeded,
    payload_json,
    source_bundle_ref_for_bundle,
    source_version_refs_for_bundle,
)
from backend.outputs.company_output import build_company_output
from backend.outputs.comparison_output import (
    build_comparison_output,
    canonical_comparison_id,
)
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingCompanyForOutput,
    MissingRegionForOutput,
)
from backend.outputs.hashing import artifact_hash as compute_artifact_hash
from backend.outputs.models import OutputMetadata
from backend.outputs.payloads import (
    CompanyOutput,
    ComparisonOutput,
    RegionOutput,
)
from backend.outputs.region_output import build_region_output
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.types import BuildOutcome, OutputType
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.scoring.repository import RegionScoreRepository
from backend.shared.state import ObjectState, validate_transition

UpsertOutcome = Literal["created", "updated", "unchanged"]
AssemblyAction = Literal["created", "updated", "unchanged", "read_only", "cached"]


class _AssembledOutput(NamedTuple):
    subject_id: str
    payload: RegionOutput | CompanyOutput | ComparisonOutput
    outcome: BuildOutcome
    source_version_bundle: dict
    freshness_expires_at: datetime | None
    output_id_default: str


class RegionAssemblyResult(NamedTuple):
    metadata: OutputMetadata | None
    payload: RegionOutput
    action: AssemblyAction


class CompanyAssemblyResult(NamedTuple):
    metadata: OutputMetadata | None
    payload: CompanyOutput
    action: AssemblyAction


class ComparisonAssemblyResult(NamedTuple):
    metadata: OutputMetadata | None
    payload: ComparisonOutput
    action: AssemblyAction


class OutputAssemblyService:
    def __init__(
        self,
        output_repo: OutputMetadataRepository,
        *,
        session: Session,
        region_repo: RegionRepository,
        company_repo: CompanyRepository,
        presence_repo: PresenceRepository,
        hiring_repo: HiringRepository,
        entry_level_repo: EntryLevelRepository,
        score_repo: RegionScoreRepository,
    ) -> None:
        self._output_repo = output_repo
        self._session = session
        self._region_repo = region_repo
        self._company_repo = company_repo
        self._presence_repo = presence_repo
        self._hiring_repo = hiring_repo
        self._entry_level_repo = entry_level_repo
        self._score_repo = score_repo

    # --- region output ---------------------------------------------------

    def build_region(
        self, region_id: str, *, now: Callable[[], datetime] | None = None
    ) -> RegionAssemblyResult:
        assembled = self._assemble_region(region_id, now=now)
        row, action = self._upsert_metadata(
            output_type=OutputType.REGION_OUTPUT,
            subject_id=assembled.subject_id,
            payload=assembled.payload,
            outcome=assembled.outcome,
            source_version_bundle=assembled.source_version_bundle,
            freshness_expires_at=assembled.freshness_expires_at,
            output_id_default=assembled.output_id_default,
        )
        return RegionAssemblyResult(metadata=row, payload=assembled.payload, action=action)

    def read_region(
        self, region_id: str, *, now: Callable[[], datetime] | None = None
    ) -> RegionAssemblyResult:
        cached = self._cached_region(region_id)
        if cached is not None:
            row, payload = cached
            return RegionAssemblyResult(metadata=row, payload=payload, action="cached")
        assembled = self._assemble_region(region_id, now=now)
        row = self._output_repo.get_by_type_and_subject(
            OutputType.REGION_OUTPUT.value, assembled.subject_id
        )
        return RegionAssemblyResult(
            metadata=row, payload=assembled.payload, action="read_only"
        )

    def _assemble_region(
        self, region_id: str, *, now: Callable[[], datetime] | None = None
    ) -> _AssembledOutput:
        region = self._region_repo.get(region_id)
        if region is None:
            raise MissingRegionForOutput(region_id)

        present_companies = self._score_repo.list_present_companies_for_region(region_id)
        presence_rows = self._present_pairs_for_region(region_id)
        hiring_rows = self._score_repo.list_hiring_for_region(region_id)
        entry_level_rows = self._score_repo.list_entry_level_for_region(region_id)
        region_market_score = self._score_repo.get_score_by_region(region_id)

        result = build_region_output(
            region=region,
            region_market_score=region_market_score,
            present_companies=present_companies,
            presence_rows=presence_rows,
            hiring_rows=hiring_rows,
            entry_level_rows=entry_level_rows,
            now=(now or _default_now)(),
        )
        return _AssembledOutput(
            subject_id=region_id,
            payload=result.payload,
            outcome=result.outcome,
            source_version_bundle=result.source_version_bundle,
            freshness_expires_at=result.freshness_expires_at,
            output_id_default=f"out_region_{region_id}",
        )

    def _present_pairs_for_region(
        self, region_id: str
    ) -> list[CompanyRegionPresence]:
        stmt = (
            select(CompanyRegionPresence)
            .where(
                CompanyRegionPresence.region_id == region_id,
                CompanyRegionPresence.presence_status == "present",
            )
            .order_by(CompanyRegionPresence.company_id)
        )
        return list(self._session.execute(stmt).scalars())

    # --- company output --------------------------------------------------

    def build_company(
        self, company_id: str, *, now: Callable[[], datetime] | None = None
    ) -> CompanyAssemblyResult:
        assembled = self._assemble_company(company_id, now=now)
        row, action = self._upsert_metadata(
            output_type=OutputType.COMPANY_OUTPUT,
            subject_id=assembled.subject_id,
            payload=assembled.payload,
            outcome=assembled.outcome,
            source_version_bundle=assembled.source_version_bundle,
            freshness_expires_at=assembled.freshness_expires_at,
            output_id_default=assembled.output_id_default,
        )
        return CompanyAssemblyResult(metadata=row, payload=assembled.payload, action=action)

    def read_company(
        self, company_id: str, *, now: Callable[[], datetime] | None = None
    ) -> CompanyAssemblyResult:
        cached = self._cached_company(company_id)
        if cached is not None:
            row, payload = cached
            return CompanyAssemblyResult(metadata=row, payload=payload, action="cached")
        assembled = self._assemble_company(company_id, now=now)
        row = self._output_repo.get_by_type_and_subject(
            OutputType.COMPANY_OUTPUT.value, assembled.subject_id
        )
        return CompanyAssemblyResult(
            metadata=row, payload=assembled.payload, action="read_only"
        )

    def _assemble_company(
        self, company_id: str, *, now: Callable[[], datetime] | None = None
    ) -> _AssembledOutput:
        company = self._company_repo.get(company_id)
        if company is None:
            raise MissingCompanyForOutput(company_id)

        presence_rows = self._presence_for_company(company_id)
        hiring_rows = self._hiring_for_company(company_id)
        entry_level_rows = self._entry_level_for_company(company_id)
        regions = self._regions_for_pairs(presence_rows, hiring_rows, entry_level_rows)
        coverage_by_region = {
            region.region_id: self._coverage_for_region(region.region_id)
            for region in regions
        }

        result = build_company_output(
            company=company,
            presence_rows=presence_rows,
            hiring_rows=hiring_rows,
            entry_level_rows=entry_level_rows,
            regions=regions,
            coverage_by_region=coverage_by_region,
            now=(now or _default_now)(),
        )
        return _AssembledOutput(
            subject_id=company_id,
            payload=result.payload,
            outcome=result.outcome,
            source_version_bundle=result.source_version_bundle,
            freshness_expires_at=result.freshness_expires_at,
            output_id_default=f"out_company_{company_id}",
        )

    def _presence_for_company(self, company_id: str) -> list[CompanyRegionPresence]:
        stmt = (
            select(CompanyRegionPresence)
            .where(CompanyRegionPresence.company_id == company_id)
            .order_by(CompanyRegionPresence.region_id)
        )
        return list(self._session.execute(stmt).scalars())

    def _hiring_for_company(self, company_id: str) -> list[CompanyRegionHiring]:
        stmt = (
            select(CompanyRegionHiring)
            .where(CompanyRegionHiring.company_id == company_id)
            .order_by(CompanyRegionHiring.region_id)
        )
        return list(self._session.execute(stmt).scalars())

    def _entry_level_for_company(
        self, company_id: str
    ) -> list[CompanyRegionEntryLevel]:
        stmt = (
            select(CompanyRegionEntryLevel)
            .where(CompanyRegionEntryLevel.company_id == company_id)
            .order_by(CompanyRegionEntryLevel.region_id)
        )
        return list(self._session.execute(stmt).scalars())

    def _regions_for_pairs(
        self,
        presence_rows: list[CompanyRegionPresence],
        hiring_rows: list[CompanyRegionHiring],
        entry_level_rows: list[CompanyRegionEntryLevel],
    ) -> list[Region]:
        ids = (
            {p.region_id for p in presence_rows}
            | {h.region_id for h in hiring_rows}
            | {e.region_id for e in entry_level_rows}
        )
        if not ids:
            return []
        stmt = select(Region).where(Region.region_id.in_(ids)).order_by(Region.region_id)
        return list(self._session.execute(stmt).scalars())

    # --- comparison output -----------------------------------------------

    def build_comparison(
        self,
        region_a_id: str,
        region_b_id: str,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> ComparisonAssemblyResult:
        assembled = self._assemble_comparison(region_a_id, region_b_id, now=now)
        row, action = self._upsert_metadata(
            output_type=OutputType.COMPARISON_OUTPUT,
            subject_id=assembled.subject_id,
            payload=assembled.payload,
            outcome=assembled.outcome,
            source_version_bundle=assembled.source_version_bundle,
            freshness_expires_at=assembled.freshness_expires_at,
            output_id_default=assembled.output_id_default,
        )
        return ComparisonAssemblyResult(
            metadata=row, payload=assembled.payload, action=action
        )

    def read_comparison(
        self,
        region_a_id: str,
        region_b_id: str,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> ComparisonAssemblyResult:
        subject_id = canonical_comparison_id(region_a_id, region_b_id)
        cached = self._cached_comparison(subject_id)
        if cached is not None:
            row, payload = cached
            return ComparisonAssemblyResult(metadata=row, payload=payload, action="cached")
        assembled = self._assemble_comparison(region_a_id, region_b_id, now=now)
        row = self._output_repo.get_by_type_and_subject(
            OutputType.COMPARISON_OUTPUT.value, assembled.subject_id
        )
        return ComparisonAssemblyResult(
            metadata=row, payload=assembled.payload, action="read_only"
        )

    def _assemble_comparison(
        self,
        region_a_id: str,
        region_b_id: str,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> _AssembledOutput:
        if not isinstance(region_a_id, str) or not isinstance(region_b_id, str):
            raise InvalidComparisonInput("region IDs must be strings")
        if not region_a_id.strip() or not region_b_id.strip():
            raise InvalidComparisonInput("region IDs must be non-empty")
        if region_a_id == region_b_id:
            raise InvalidComparisonInput(
                f"comparison requires two distinct regions; got {region_a_id!r} twice"
            )

        # Canonicalize the pair ordering before reading regions so the
        # subject_id is order-independent.
        canonical_a, canonical_b = sorted((region_a_id, region_b_id))
        region_a = self._region_repo.get(canonical_a)
        region_b = self._region_repo.get(canonical_b)
        if region_a is None:
            raise MissingRegionForOutput(canonical_a)
        if region_b is None:
            raise MissingRegionForOutput(canonical_b)

        score_a = self._score_repo.get_score_by_region(canonical_a)
        score_b = self._score_repo.get_score_by_region(canonical_b)

        # Aggregate freshness across both regions' hiring/entry-level rows.
        hiring_a = self._score_repo.list_hiring_for_region(canonical_a)
        hiring_b = self._score_repo.list_hiring_for_region(canonical_b)
        entry_a = self._score_repo.list_entry_level_for_region(canonical_a)
        entry_b = self._score_repo.list_entry_level_for_region(canonical_b)
        coverage_a = self._coverage_for_region(
            canonical_a,
            score=score_a,
            hiring_rows=hiring_a,
            entry_level_rows=entry_a,
        )
        coverage_b = self._coverage_for_region(
            canonical_b,
            score=score_b,
            hiring_rows=hiring_b,
            entry_level_rows=entry_b,
        )
        extra_freshness = (
            [h.freshness_expires_at for h in hiring_a]
            + [h.freshness_expires_at for h in hiring_b]
            + [e.freshness_expires_at for e in entry_a]
            + [e.freshness_expires_at for e in entry_b]
        )

        result = build_comparison_output(
            region_a=region_a,
            region_b=region_b,
            score_a=score_a,
            score_b=score_b,
            coverage_a=coverage_a,
            coverage_b=coverage_b,
            extra_freshness_inputs=extra_freshness,
            now=(now or _default_now)(),
        )
        subject_id = canonical_comparison_id(canonical_a, canonical_b)
        return _AssembledOutput(
            subject_id=subject_id,
            payload=result.payload,
            outcome=result.outcome,
            source_version_bundle=result.source_version_bundle,
            freshness_expires_at=result.freshness_expires_at,
            output_id_default=f"out_comparison_{subject_id}",
        )

    # --- shared upsert + state-machine -----------------------------------

    def _upsert_metadata(
        self,
        *,
        output_type: OutputType,
        subject_id: str,
        payload,
        outcome: BuildOutcome,
        source_version_bundle: dict,
        freshness_expires_at: datetime | None,
        output_id_default: str,
    ) -> tuple[OutputMetadata, UpsertOutcome]:
        payload_data = payload_json(payload)
        ah = compute_artifact_hash(payload_data)

        existing = self._output_repo.get_by_type_and_subject(
            output_type.value, subject_id
        )
        if existing is not None and existing.artifact_hash == ah:
            self._apply_cache_fields(
                existing,
                payload_data=payload_data,
                source_version_bundle=source_version_bundle,
                freshness_expires_at=freshness_expires_at,
            )
            if existing.state != outcome.value:
                self._walk_changed_rebuild_state(existing, outcome)
            mark_rebuild_succeeded(existing)
            self._output_repo.flush()
            return existing, "unchanged"

        if existing is None:
            row = OutputMetadata(
                output_id=output_id_default,
                output_type=output_type.value,
                subject_id=subject_id,
                artifact_uri=None,
                artifact_hash=ah,
                cached_payload=payload_data,
                source_version_bundle=source_version_bundle,
                source_version_refs=list(source_version_refs_for_bundle(source_version_bundle)),
                source_bundle_ref=source_bundle_ref_for_bundle(source_version_bundle),
                freshness_expires_at=freshness_expires_at,
            )
            self._output_repo.add(row)
            self._output_repo.flush()
            self._walk_first_build_state(row, outcome)
            mark_rebuild_succeeded(row)
            self._output_repo.flush()
            return row, "created"

        existing.artifact_hash = ah
        self._apply_cache_fields(
            existing,
            payload_data=payload_data,
            source_version_bundle=source_version_bundle,
            freshness_expires_at=freshness_expires_at,
        )
        from backend.shared.versioning import next_version

        existing.version = next_version(existing.version)
        self._walk_changed_rebuild_state(existing, outcome)
        mark_rebuild_succeeded(existing)
        self._output_repo.flush()
        return existing, "updated"

    def _apply_cache_fields(
        self,
        row: OutputMetadata,
        *,
        payload_data: dict,
        source_version_bundle: dict,
        freshness_expires_at: datetime | None,
    ) -> None:
        row.cached_payload = payload_data
        row.source_version_bundle = source_version_bundle
        row.source_version_refs = list(source_version_refs_for_bundle(source_version_bundle))
        row.source_bundle_ref = source_bundle_ref_for_bundle(source_version_bundle)
        row.freshness_expires_at = freshness_expires_at

    def _cached_region(self, region_id: str):
        row = self._output_repo.get_by_type_and_subject(
            OutputType.REGION_OUTPUT.value, region_id
        )
        if row is None:
            return None
        payload = load_cached_output(row)
        if not isinstance(payload, RegionOutput):
            return None
        return row, payload

    def _cached_company(self, company_id: str):
        row = self._output_repo.get_by_type_and_subject(
            OutputType.COMPANY_OUTPUT.value, company_id
        )
        if row is None:
            return None
        payload = load_cached_output(row)
        if not isinstance(payload, CompanyOutput):
            return None
        return row, payload

    def _cached_comparison(self, subject_id: str):
        row = self._output_repo.get_by_type_and_subject(
            OutputType.COMPARISON_OUTPUT.value, subject_id
        )
        if row is None:
            return None
        payload = load_cached_output(row)
        if not isinstance(payload, ComparisonOutput):
            return None
        return row, payload

    def _walk_first_build_state(
        self, row: OutputMetadata, outcome: BuildOutcome
    ) -> None:
        # new → building first.
        self._set_state(row, ObjectState.BUILDING)
        if outcome is BuildOutcome.PARTIAL:
            # building → partial is in the documented transition table.
            self._set_state(row, ObjectState.PARTIAL)
        else:
            # building → fresh, then optionally fresh → stale.
            self._set_state(row, ObjectState.FRESH)
            if outcome is BuildOutcome.STALE:
                self._set_state(row, ObjectState.STALE)

    def _walk_changed_rebuild_state(
        self, row: OutputMetadata, outcome: BuildOutcome
    ) -> None:
        target = ObjectState(outcome.value)
        if row.state == ObjectState.NEW.value:
            self._walk_first_build_state(row, outcome)
            return
        if row.state == ObjectState.BUILDING.value:
            if outcome is BuildOutcome.PARTIAL:
                self._set_state(row, ObjectState.PARTIAL)
            else:
                self._set_state(row, ObjectState.FRESH)
                if outcome is BuildOutcome.STALE:
                    self._set_state(row, ObjectState.STALE)
            return
        if row.state == target.value:
            return
        if row.state in {
            ObjectState.FRESH.value,
            ObjectState.STALE.value,
            ObjectState.PARTIAL.value,
            ObjectState.FAILED.value,
            ObjectState.BLOCKED.value,
            ObjectState.REBUILDING.value,
        }:
            if row.state != ObjectState.REBUILDING.value:
                self._set_state(row, ObjectState.REBUILDING)
            if target is ObjectState.STALE:
                # rebuilding → stale is not a valid direct transition; a stale
                # rebuilt payload is still a successful rebuild whose inputs
                # have already expired.
                self._set_state(row, ObjectState.FRESH)
                self._set_state(row, ObjectState.STALE)
            else:
                self._set_state(row, target)

    def _set_state(self, row: OutputMetadata, target: ObjectState) -> None:
        validate_transition(row.state, target)
        row.state = target.value

    def _coverage_for_region(
        self,
        region_id: str,
        *,
        score=None,
        hiring_rows: list[CompanyRegionHiring] | None = None,
        entry_level_rows: list[CompanyRegionEntryLevel] | None = None,
    ) -> CoverageMetadataPayload:
        present_companies = self._score_repo.list_present_companies_for_region(region_id)
        presence_rows = self._present_pairs_for_region(region_id)
        if score is None:
            score = self._score_repo.get_score_by_region(region_id)
        if hiring_rows is None:
            hiring_rows = self._score_repo.list_hiring_for_region(region_id)
        if entry_level_rows is None:
            entry_level_rows = self._score_repo.list_entry_level_for_region(region_id)
        freshness_expires_at = _min_freshness_expires_at(
            [h.freshness_expires_at for h in hiring_rows]
            + [e.freshness_expires_at for e in entry_level_rows]
        )
        now = _default_now()
        is_stale = (
            freshness_expires_at is not None and freshness_expires_at <= now
        )
        return build_region_coverage_metadata(
            present_company_count=len(present_companies),
            presence_record_count=len(presence_rows),
            hiring_record_count=len(hiring_rows),
            entry_level_record_count=len(entry_level_rows),
            has_region_score=score is not None,
            freshness_expires_at_known=freshness_expires_at is not None,
            freshness_is_stale=is_stale,
            source_evidence_loaded=False,
        )


def _default_now() -> datetime:
    return datetime.now(UTC)


def _min_freshness_expires_at(values: list[datetime | None]) -> datetime | None:
    non_null = [
        value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value
        for value in values
        if value is not None
    ]
    return min(non_null) if non_null else None
