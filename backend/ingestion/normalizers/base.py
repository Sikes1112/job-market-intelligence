"""Layer 4C normalizer contracts.

Normalizers transform raw intake into structured normalized observations. They
do not attach provenance, create fact-source links, or write canonical facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.ingestion.contracts import NormalizationResult
from backend.ingestion.status import CanonicalFactIntent, NormalizationStatus
from backend.shared.confidence import Confidence
from backend.shared.provenance import ObservationStatus


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class NormalizerDiagnosticSeverity(_Vocabulary):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NormalizerDiagnosticCode(_Vocabulary):
    MISSING_REQUIRED_FIELD = "missing_required_field"
    MALFORMED_PAYLOAD = "malformed_payload"
    UNKNOWN_VALUE = "unknown_value"
    ZERO_WITHOUT_OBSERVED_BASIS = "zero_without_observed_basis"
    CONFLICTING_INPUT = "conflicting_input"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    RAW_INTAKE_ONLY = "raw_intake_only"


class NormalizerDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: NormalizerDiagnosticCode
    severity: NormalizerDiagnosticSeverity
    field_name: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=1)


class NormalizedObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    intended_fact_type: CanonicalFactIntent
    normalized_fields: dict[str, Any]
    observation_status: ObservationStatus
    confidence: Confidence = Confidence.UNKNOWN
    proposed_fact_id: str | None = Field(default=None, min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=2048)


class NormalizerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    normalizer_name: str = Field(min_length=1)
    raw_record_id: str = Field(min_length=1, max_length=64)
    status: NormalizationStatus
    observation: NormalizedObservation | None = None
    diagnostics: tuple[NormalizerDiagnostic, ...] = Field(default_factory=tuple)
    manual_review_required: bool = False
    notes: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def _normalized_results_require_observation(self) -> NormalizerResult:
        if self.status is NormalizationStatus.NORMALIZED and self.observation is None:
            raise ValueError("normalized normalizer results require observation")
        return self

    @property
    def has_errors(self) -> bool:
        return any(
            diagnostic.severity is NormalizerDiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )

    @property
    def normalized_payload(self) -> dict[str, Any] | None:
        if self.observation is None:
            return None
        return {
            **self.observation.normalized_fields,
            "_normalization": {
                "normalizer_name": self.normalizer_name,
                "observation_status": self.observation.observation_status.value,
                "confidence": self.observation.confidence.value,
                "manual_review_required": self.manual_review_required,
                "proposed_fact_id": self.observation.proposed_fact_id,
            },
        }

    def to_normalization_result(self) -> NormalizationResult:
        return NormalizationResult(
            raw_record_id=self.raw_record_id,
            status=self.status,
            normalized_payload=self.normalized_payload,
            intended_fact_type=(
                self.observation.intended_fact_type if self.observation else None
            ),
            parsing_notes=self.notes,
            parsing_errors=tuple(
                diagnostic.message
                for diagnostic in self.diagnostics
                if diagnostic.severity is NormalizerDiagnosticSeverity.ERROR
            ),
        )


class SourceNormalizer(Protocol):
    normalizer_name: str
    supported_fact_intents: frozenset[CanonicalFactIntent]

    def normalize(self, raw_record: object | Mapping[str, Any]) -> NormalizerResult:
        """Normalize one raw intake record."""
