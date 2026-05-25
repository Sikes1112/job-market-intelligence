"""Layer 4B source adapter contract.

Adapters prepare explicit source inputs for raw intake only. They do not
scrape, call external APIs, attach provenance, or create canonical facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.ingestion.contracts import RawIntakeDefinition
from backend.ingestion.status import CanonicalFactIntent
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    SOURCE_TYPE_DEFAULT_ACCEPTABILITY,
    LicenseTermsCategory,
    SourceAcceptability,
    SourceType,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class AdapterResultStatus(_Vocabulary):
    SUCCESS = "success"
    NO_OBSERVATIONS = "no_observations"
    FAILED = "failed"


class AdapterDiagnosticSeverity(_Vocabulary):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AdapterDiagnosticCode(_Vocabulary):
    NO_OBSERVATIONS = "no_observations"
    INPUT_MALFORMED = "input_malformed"
    SOURCE_DISALLOWED = "source_disallowed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    ALLOWED_WITH_CAUTION = "allowed_with_caution"
    RAW_INTAKE_ONLY = "raw_intake_only"


class AdapterDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: AdapterDiagnosticCode
    severity: AdapterDiagnosticSeverity
    message: str = Field(min_length=1)


class AdapterSourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=255)
    url_or_provider: str = Field(min_length=1, max_length=1024)
    license_or_terms_category: LicenseTermsCategory = LicenseTermsCategory.UNKNOWN
    confidence: Confidence = Confidence.UNKNOWN
    default_acceptability: SourceAcceptability
    notes: str | None = Field(default=None, max_length=2048)

    @classmethod
    def from_source(
        cls,
        *,
        source_type: SourceType,
        source_name: str,
        url_or_provider: str,
        license_or_terms_category: LicenseTermsCategory = LicenseTermsCategory.UNKNOWN,
        confidence: Confidence = Confidence.UNKNOWN,
        notes: str | None = None,
    ) -> AdapterSourceMetadata:
        return cls(
            source_type=source_type,
            source_name=source_name,
            url_or_provider=url_or_provider,
            license_or_terms_category=license_or_terms_category,
            confidence=confidence,
            default_acceptability=SOURCE_TYPE_DEFAULT_ACCEPTABILITY[source_type],
            notes=notes,
        )


class AdapterRunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_name: str = Field(min_length=1)
    collected_at: datetime | None = None
    observation_count: int = Field(default=0, ge=0)
    raw_intake_only: bool = True

    @field_validator("collected_at")
    @classmethod
    def _collected_at_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("adapter collected_at must be timezone-aware")
        return value


class AdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: AdapterResultStatus
    raw_intake_definitions: tuple[RawIntakeDefinition, ...] = Field(
        default_factory=tuple
    )
    diagnostics: tuple[AdapterDiagnostic, ...] = Field(default_factory=tuple)
    source_metadata: AdapterSourceMetadata | None = None
    run_metadata: AdapterRunMetadata

    @property
    def has_errors(self) -> bool:
        return any(
            diagnostic.severity is AdapterDiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )

    @property
    def usable_as_raw_intake(self) -> bool:
        return (
            self.status is AdapterResultStatus.SUCCESS
            and bool(self.raw_intake_definitions)
            and not self.has_errors
        )


class SourceAdapter(Protocol):
    adapter_name: str
    source_type: SourceType
    supported_fact_intents: frozenset[CanonicalFactIntent]

    def prepare(self, observation: Mapping[str, Any] | object) -> AdapterResult:
        """Prepare explicit input for raw intake."""
