"""Structural provenance service.

This layer only creates source references, source observations, and
fact-to-source links. It does not collect sources, judge source quality beyond
the canonical vocabulary, or run audit checks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.provenance.exceptions import (
    ProvenanceBindingRequired,
    SourceObservationNotFound,
    SourceRefNotFound,
)
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import (
    REAL_DATA_ORIGINS,
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]


class SourceRefDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=64)
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=255)
    url_or_provider: str = Field(min_length=1, max_length=1024)
    collected_at: datetime | None = None
    observed_at: datetime | None = None
    license_or_terms_category: LicenseTermsCategory = LicenseTermsCategory.UNKNOWN
    confidence: Confidence = Confidence.UNKNOWN
    freshness_status: FreshnessStatus | None = None
    data_origin: DataOrigin = DataOrigin.UNKNOWN_ORIGIN
    notes: str | None = Field(default=None, max_length=2048)


class SourceObservationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    collected_at: datetime
    observed_at: datetime
    data_origin: DataOrigin = DataOrigin.UNKNOWN_ORIGIN
    observation_status: ObservationStatus = ObservationStatus.UNKNOWN
    confidence: Confidence | None = None
    freshness_status: FreshnessStatus | None = None
    notes: str | None = Field(default=None, max_length=2048)


class FactSourceLinkDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    link_id: str = Field(min_length=1, max_length=128)
    observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    fact_type: FactBindingType
    fact_id: str = Field(min_length=1, max_length=128)
    fact_field: str | None = Field(default=None, min_length=1, max_length=128)
    data_origin: DataOrigin = DataOrigin.UNKNOWN_ORIGIN
    observation_status: ObservationStatus = ObservationStatus.UNKNOWN
    confidence: Confidence | None = None
    freshness_status: FreshnessStatus | None = None
    notes: str | None = Field(default=None, max_length=2048)


class ProvenanceService:
    def __init__(self, repository: ProvenanceRepository) -> None:
        self._repo = repository

    def create_source_ref(self, definition: SourceRefDefinition) -> SourceRef:
        source_ref = SourceRef(
            source_id=definition.source_id,
            source_type=definition.source_type.value,
            source_name=definition.source_name,
            url_or_provider=definition.url_or_provider,
            collected_at=definition.collected_at,
            observed_at=definition.observed_at,
            license_or_terms_category=definition.license_or_terms_category.value,
            confidence=definition.confidence.value,
            freshness_status=(
                definition.freshness_status.value
                if definition.freshness_status is not None
                else None
            ),
            data_origin=definition.data_origin.value,
            notes=definition.notes,
        )
        self._repo.add_source_ref(source_ref)
        self._repo.flush()
        return source_ref

    def upsert_source_ref(
        self, definition: SourceRefDefinition
    ) -> tuple[SourceRef, UpsertOutcome]:
        existing = self._repo.get_source_ref(definition.source_id)
        if existing is None:
            return self.create_source_ref(definition), "created"
        if self._source_ref_matches(existing, definition):
            return existing, "unchanged"
        self._apply_source_ref(existing, definition)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing, "updated"

    def create_observation(
        self, definition: SourceObservationDefinition
    ) -> SourceObservation:
        source_ref = self._require_source_ref(definition.source_id)
        observation = self._build_observation(definition, source_ref)
        self._repo.add_observation(observation)
        self._repo.flush()
        return observation

    def upsert_observation(
        self, definition: SourceObservationDefinition
    ) -> tuple[SourceObservation, UpsertOutcome]:
        existing = self._repo.get_observation(definition.observation_id)
        source_ref = self._require_source_ref(definition.source_id)
        if existing is None:
            return self.create_observation(definition), "created"
        if self._observation_matches(existing, definition, source_ref):
            return existing, "unchanged"
        self._apply_observation(existing, definition, source_ref)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing, "updated"

    def create_fact_source_link(
        self, definition: FactSourceLinkDefinition
    ) -> FactSourceLink:
        observation = self._require_observation_for_link(definition)
        link = self._build_fact_source_link(definition, observation)
        self._repo.add_fact_source_link(link)
        self._repo.flush()
        return link

    def upsert_fact_source_link(
        self, definition: FactSourceLinkDefinition
    ) -> tuple[FactSourceLink, UpsertOutcome]:
        observation = self._require_observation_for_link(definition)
        existing = self._repo.get_fact_source_link(definition.link_id)
        if existing is None:
            return self.create_fact_source_link(definition), "created"
        if self._fact_source_link_matches(existing, definition, observation):
            return existing, "unchanged"
        self._apply_fact_source_link(existing, definition, observation)
        existing.version = next_version(existing.version)
        self._repo.flush()
        return existing, "updated"

    def _require_source_ref(self, source_id: str) -> SourceRef:
        source_ref = self._repo.get_source_ref(source_id)
        if source_ref is None:
            raise SourceRefNotFound(source_id)
        return source_ref

    def _require_observation_for_link(
        self, definition: FactSourceLinkDefinition
    ) -> SourceObservation:
        if definition.observation_id is None:
            if definition.data_origin in REAL_DATA_ORIGINS:
                raise ProvenanceBindingRequired(
                    "real observed or derived facts require a source observation"
                )
            raise ProvenanceBindingRequired("fact-source links require observation_id")
        observation = self._repo.get_observation(definition.observation_id)
        if observation is None:
            raise SourceObservationNotFound(definition.observation_id)
        return observation

    def _build_observation(
        self,
        definition: SourceObservationDefinition,
        source_ref: SourceRef,
    ) -> SourceObservation:
        return SourceObservation(
            observation_id=definition.observation_id,
            source_id=source_ref.source_id,
            source_type=source_ref.source_type,
            source_name=source_ref.source_name,
            url_or_provider=source_ref.url_or_provider,
            collected_at=definition.collected_at,
            observed_at=definition.observed_at,
            license_or_terms_category=source_ref.license_or_terms_category,
            confidence=(definition.confidence or Confidence(source_ref.confidence)).value,
            freshness_status=(
                definition.freshness_status.value
                if definition.freshness_status is not None
                else source_ref.freshness_status
            ),
            data_origin=definition.data_origin.value,
            observation_status=definition.observation_status.value,
            notes=definition.notes,
        )

    def _build_fact_source_link(
        self,
        definition: FactSourceLinkDefinition,
        observation: SourceObservation,
    ) -> FactSourceLink:
        return FactSourceLink(
            link_id=definition.link_id,
            observation_id=observation.observation_id,
            source_id=observation.source_id,
            fact_type=definition.fact_type.value,
            fact_id=definition.fact_id,
            fact_field=definition.fact_field,
            source_type=observation.source_type,
            source_name=observation.source_name,
            url_or_provider=observation.url_or_provider,
            collected_at=observation.collected_at,
            observed_at=observation.observed_at,
            license_or_terms_category=observation.license_or_terms_category,
            confidence=(definition.confidence or Confidence(observation.confidence)).value,
            freshness_status=(
                definition.freshness_status.value
                if definition.freshness_status is not None
                else observation.freshness_status
            ),
            data_origin=definition.data_origin.value,
            observation_status=definition.observation_status.value,
            notes=definition.notes,
        )

    def _apply_source_ref(
        self, source_ref: SourceRef, definition: SourceRefDefinition
    ) -> None:
        source_ref.source_type = definition.source_type.value
        source_ref.source_name = definition.source_name
        source_ref.url_or_provider = definition.url_or_provider
        source_ref.collected_at = definition.collected_at
        source_ref.observed_at = definition.observed_at
        source_ref.license_or_terms_category = (
            definition.license_or_terms_category.value
        )
        source_ref.confidence = definition.confidence.value
        source_ref.freshness_status = (
            definition.freshness_status.value
            if definition.freshness_status is not None
            else None
        )
        source_ref.data_origin = definition.data_origin.value
        source_ref.notes = definition.notes

    def _apply_observation(
        self,
        observation: SourceObservation,
        definition: SourceObservationDefinition,
        source_ref: SourceRef,
    ) -> None:
        observation.source_id = source_ref.source_id
        observation.source_type = source_ref.source_type
        observation.source_name = source_ref.source_name
        observation.url_or_provider = source_ref.url_or_provider
        observation.collected_at = definition.collected_at
        observation.observed_at = definition.observed_at
        observation.license_or_terms_category = source_ref.license_or_terms_category
        observation.confidence = (
            definition.confidence or Confidence(source_ref.confidence)
        ).value
        observation.freshness_status = (
            definition.freshness_status.value
            if definition.freshness_status is not None
            else source_ref.freshness_status
        )
        observation.data_origin = definition.data_origin.value
        observation.observation_status = definition.observation_status.value
        observation.notes = definition.notes

    def _apply_fact_source_link(
        self,
        link: FactSourceLink,
        definition: FactSourceLinkDefinition,
        observation: SourceObservation,
    ) -> None:
        rebuilt = self._build_fact_source_link(definition, observation)
        link.observation_id = rebuilt.observation_id
        link.source_id = rebuilt.source_id
        link.fact_type = rebuilt.fact_type
        link.fact_id = rebuilt.fact_id
        link.fact_field = rebuilt.fact_field
        link.source_type = rebuilt.source_type
        link.source_name = rebuilt.source_name
        link.url_or_provider = rebuilt.url_or_provider
        link.collected_at = rebuilt.collected_at
        link.observed_at = rebuilt.observed_at
        link.license_or_terms_category = rebuilt.license_or_terms_category
        link.confidence = rebuilt.confidence
        link.freshness_status = rebuilt.freshness_status
        link.data_origin = rebuilt.data_origin
        link.observation_status = rebuilt.observation_status
        link.notes = rebuilt.notes

    def _source_ref_matches(
        self, source_ref: SourceRef, definition: SourceRefDefinition
    ) -> bool:
        return (
            source_ref.source_type == definition.source_type.value
            and source_ref.source_name == definition.source_name
            and source_ref.url_or_provider == definition.url_or_provider
            and _same_instant(source_ref.collected_at, definition.collected_at)
            and _same_instant(source_ref.observed_at, definition.observed_at)
            and source_ref.license_or_terms_category
            == definition.license_or_terms_category.value
            and source_ref.confidence == definition.confidence.value
            and source_ref.freshness_status
            == (
                definition.freshness_status.value
                if definition.freshness_status is not None
                else None
            )
            and source_ref.data_origin == definition.data_origin.value
            and source_ref.notes == definition.notes
        )

    def _observation_matches(
        self,
        observation: SourceObservation,
        definition: SourceObservationDefinition,
        source_ref: SourceRef,
    ) -> bool:
        candidate = self._build_observation(definition, source_ref)
        return (
            observation.source_id == candidate.source_id
            and observation.source_type == candidate.source_type
            and observation.source_name == candidate.source_name
            and observation.url_or_provider == candidate.url_or_provider
            and _same_instant(observation.collected_at, candidate.collected_at)
            and _same_instant(observation.observed_at, candidate.observed_at)
            and observation.license_or_terms_category
            == candidate.license_or_terms_category
            and observation.confidence == candidate.confidence
            and observation.freshness_status == candidate.freshness_status
            and observation.data_origin == candidate.data_origin
            and observation.observation_status == candidate.observation_status
            and observation.notes == candidate.notes
        )

    def _fact_source_link_matches(
        self,
        link: FactSourceLink,
        definition: FactSourceLinkDefinition,
        observation: SourceObservation,
    ) -> bool:
        candidate = self._build_fact_source_link(definition, observation)
        return (
            link.observation_id == candidate.observation_id
            and link.source_id == candidate.source_id
            and link.fact_type == candidate.fact_type
            and link.fact_id == candidate.fact_id
            and link.fact_field == candidate.fact_field
            and link.source_type == candidate.source_type
            and link.source_name == candidate.source_name
            and link.url_or_provider == candidate.url_or_provider
            and _same_instant(link.collected_at, candidate.collected_at)
            and _same_instant(link.observed_at, candidate.observed_at)
            and link.license_or_terms_category
            == candidate.license_or_terms_category
            and link.confidence == candidate.confidence
            and link.freshness_status == candidate.freshness_status
            and link.data_origin == candidate.data_origin
            and link.observation_status == candidate.observation_status
            and link.notes == candidate.notes
        )


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    if left.tzinfo is None:
        left = left.replace(tzinfo=UTC)
    if right.tzinfo is None:
        right = right.replace(tzinfo=UTC)
    return left == right


def utc_now() -> datetime:
    return datetime.now(UTC)
