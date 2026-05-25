"""Evidence-packet contracts for structured explanations.

The explanation layer is not a market-truth source. Callers must provide
already-structured evidence from existing outputs, scoring previews, alerts,
freshness/source summaries, or watchlist context.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExplanationEntityType(StrEnum):
    REGION = "region"
    COMPANY = "company"
    COMPARISON = "comparison"
    ALERT = "alert"


class ExplanationStatus(StrEnum):
    OK = "ok"
    CONSTRAINED = "constrained"
    REFUSED = "refused"


class ExplanationSectionType(StrEnum):
    STRUCTURED_FACT = "structured_fact"
    SCORE_INTERPRETATION = "score_interpretation"
    FRESHNESS_LIMITATION = "freshness_limitation"
    MISSING_UNSUPPORTED_DATA = "missing_unsupported_data"
    PERSONALIZED_OVERLAY = "personalized_overlay"


class FreshnessEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    freshness_status: str | None = Field(default=None, max_length=32)
    data_basis: str | None = Field(default=None, max_length=32)
    last_updated_at: str | None = Field(default=None, max_length=64)
    freshness_expires_at: str | None = Field(default=None, max_length=64)
    source_count: int | None = Field(default=None, ge=0, le=10_000)

    @field_validator("freshness_status", "data_basis", "last_updated_at", "freshness_expires_at")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("freshness evidence strings must not be blank")
        return stripped


class ScoringFactorEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    factor: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, min_length=1, max_length=96)
    value: float | None = Field(default=None, ge=0, le=1)
    weight: float | None = Field(default=None, ge=0, le=1)
    status: str | None = Field(default=None, max_length=32)

    @field_validator("factor", "label", "status")
    @classmethod
    def _strip_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("scoring factor strings must not be blank")
        return stripped


class AlertEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(min_length=1, max_length=64)
    relevance_reason: str | None = Field(default=None, min_length=1, max_length=64)
    changed_fields: list[str] = Field(default_factory=list, max_length=20)
    detection_basis: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("event_type", "relevance_reason", "detection_basis")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("alert evidence strings must not be blank")
        return stripped

    @field_validator("changed_fields")
    @classmethod
    def _changed_fields_are_safe(cls, value: list[str]) -> list[str]:
        return [_safe_label(item, "changed_fields") for item in value]


class ExplanationEvidencePacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: ExplanationEntityType
    subject_refs: dict[str, str] = Field(default_factory=dict, max_length=8)
    display_label: str | None = Field(default=None, min_length=1, max_length=128)
    canonical_scores: dict[str, float | None] = Field(default_factory=dict, max_length=12)
    personalized_overlay: dict[str, float | None] = Field(default_factory=dict, max_length=12)
    scoring_factors: list[ScoringFactorEvidence] = Field(default_factory=list, max_length=20)
    freshness: FreshnessEvidence | None = None
    source_refs: list[str] = Field(default_factory=list, max_length=50)
    alert: AlertEvidence | None = None
    watchlist_context: list[str] = Field(default_factory=list, max_length=20)
    missing_data: list[str] = Field(default_factory=list, max_length=30)
    unsupported_data: list[str] = Field(default_factory=list, max_length=30)
    demo_or_seeded: bool = False
    notes: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("subject_refs")
    @classmethod
    def _subject_refs_are_safe(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, item in value.items():
            cleaned[_safe_key(key, "subject_refs")] = _safe_label(item, "subject_refs")
        return cleaned

    @field_validator("canonical_scores", "personalized_overlay")
    @classmethod
    def _scores_are_bounded(cls, value: dict[str, float | None]) -> dict[str, float | None]:
        cleaned: dict[str, float | None] = {}
        for key, item in value.items():
            safe_key = _safe_key(key, "scores")
            if item is None:
                cleaned[safe_key] = None
                continue
            number = float(item)
            if number < 0 or number > 1:
                raise ValueError("score evidence values must be between 0 and 1")
            cleaned[safe_key] = number
        return cleaned

    @field_validator("display_label")
    @classmethod
    def _label_is_safe(cls, value: str | None) -> str | None:
        return _safe_label(value, "display_label") if value is not None else None

    @field_validator(
        "source_refs",
        "watchlist_context",
        "missing_data",
        "unsupported_data",
        "notes",
    )
    @classmethod
    def _lists_are_safe(cls, value: list[str]) -> list[str]:
        return [_safe_label(item, "evidence list") for item in value]

    @model_validator(mode="after")
    def _must_have_some_evidence(self) -> ExplanationEvidencePacket:
        if not any(
            (
                self.subject_refs,
                self.canonical_scores,
                self.personalized_overlay,
                self.scoring_factors,
                self.freshness,
                self.source_refs,
                self.alert,
                self.watchlist_context,
                self.missing_data,
                self.unsupported_data,
                self.notes,
            )
        ):
            raise ValueError("explanation evidence packet must contain structured evidence")
        return self


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence: ExplanationEvidencePacket


class ExplanationSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_type: ExplanationSectionType
    title: str
    statements: list[str] = Field(default_factory=list)


class ExplanationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_mode: str = "deterministic_structured_guidance"
    status: ExplanationStatus
    entity_type: ExplanationEntityType
    subject_refs: dict[str, str]
    sections: list[ExplanationSection]
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


UNSAFE_EVIDENCE_KEY_NAMES: frozenset[str] = frozenset(
    {
        "canonicalscore",
        "companies",
        "companydetail",
        "entrylevelsignal",
        "evidence",
        "freshness",
        "hiring",
        "marketoutput",
        "output",
        "personalizedscore",
        "provenance",
        "regiondetail",
        "regions",
        "score",
        "scores",
        "sources",
        "sourcesummary",
    }
)

UNSAFE_EVIDENCE_KEY_PARTS: tuple[str, ...] = (
    "companydetail",
    "entrylevelsignal",
    "evidence",
    "hiring",
    "marketoutput",
    "payload",
    "provenance",
    "regiondetail",
    "raw",
    "scrape",
    "secret",
    "source",
    "token",
    "cookie",
    "html",
)


def _safe_key(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} keys must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} keys must not be blank")
    normalized = "".join(character for character in stripped.casefold() if character.isalnum())
    if normalized in UNSAFE_EVIDENCE_KEY_NAMES or any(
        part in normalized for part in UNSAFE_EVIDENCE_KEY_PARTS
    ):
        raise ValueError(
            f"{label} keys must not carry copied market payload, source, "
            "provenance, or secret material"
        )
    if len(stripped) > 64:
        raise ValueError(f"{label} keys must be 64 characters or fewer")
    return stripped


def _safe_label(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    if len(stripped) > 256:
        raise ValueError(f"{label} entries must be 256 characters or fewer")
    return stripped
