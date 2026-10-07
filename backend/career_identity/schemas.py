from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class CareerFactType(_Vocabulary):
    EDUCATION = "education"
    EXPERIENCE = "experience"
    SKILL = "skill"
    PROJECT = "project"
    CREDENTIAL = "credential"
    CAREER_GOAL = "career_goal"
    ROLE_PREFERENCE = "role_preference"
    INDUSTRY_PREFERENCE = "industry_preference"
    GEOGRAPHIC_CONSTRAINT = "geographic_constraint"
    COMPENSATION_CONSTRAINT = "compensation_constraint"
    TIMING_PREFERENCE = "timing_preference"
    WORK_ARRANGEMENT_PREFERENCE = "work_arrangement_preference"


class CareerFactState(_Vocabulary):
    EXPLICIT = "explicit"
    IMPORTED = "imported"
    INFERRED = "inferred"
    CONFIRMED = "confirmed"


class CareerCompletenessState(_Vocabulary):
    EMPTY = "empty"
    MINIMAL = "minimal"
    PARTIAL = "partial"
    COMPLETE = "complete"


class CareerSufficiencyState(_Vocabulary):
    INSUFFICIENT = "insufficient"
    SUFFICIENT = "sufficient"


class WorkArrangement(_Vocabulary):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class PreferenceKind(_Vocabulary):
    PREFERRED = "preferred"
    EXCLUDED = "excluded"
    NEUTRAL = "neutral"
    HISTORICAL = "historical"


class FactProvenanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str | None = Field(default=None, min_length=1, max_length=64)
    source_label: str | None = Field(default=None, min_length=1, max_length=255)
    source_ref: str | None = Field(default=None, min_length=1, max_length=512)
    source_import_id: str | None = Field(default=None, min_length=1, max_length=64)
    observed_at: datetime | date | None = None
    extraction_method: str | None = Field(default=None, min_length=1, max_length=128)
    confidence: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("source_label", "source_ref", "extraction_method", "confidence", "notes")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class EducationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    institution: str = Field(min_length=1, max_length=255)
    degree_type: str | None = Field(default=None, min_length=1, max_length=128)
    field_of_study: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    expected_completion_date: date | None = None
    currently_enrolled: bool = False
    location: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("institution", "degree_type", "field_of_study", "location", "description")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _dates_are_valid(self) -> Self:
        _validate_date_range(self.start_date, self.end_date, "education")
        if self.end_date is not None and self.expected_completion_date is not None:
            raise ValueError("education cannot have both end_date and expected_completion_date")
        return self


class ExperiencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    engagement_type: str | None = Field(default=None, min_length=1, max_length=128)
    start_date: date | None = None
    end_date: date | None = None
    current_role: bool = False
    location: str | None = Field(default=None, min_length=1, max_length=255)
    work_arrangement: WorkArrangement | None = None
    description: str | None = Field(default=None, min_length=1, max_length=4096)
    achievements: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    skills: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("organization", "title", "engagement_type", "location", "description")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("achievements", "skills", mode="before")
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value)

    @model_validator(mode="after")
    def _dates_are_valid(self) -> Self:
        _validate_date_range(self.start_date, self.end_date, "experience")
        if self.current_role and self.end_date is not None:
            raise ValueError("current experience cannot have end_date")
        return self


class SkillPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    normalized_name: str | None = Field(default=None, min_length=1, max_length=128)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("name", "normalized_name")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value)


class ProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4096)
    start_date: date | None = None
    end_date: date | None = None
    technologies: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    outcomes: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    links: tuple[str, ...] = Field(default_factory=tuple, max_length=10)

    @field_validator("name", "role", "description")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("technologies", "outcomes", "links", mode="before")
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _clean_string_tuple(value)

    @model_validator(mode="after")
    def _dates_are_valid(self) -> Self:
        _validate_date_range(self.start_date, self.end_date, "project")
        return self


class CredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=255)
    issuer: str | None = Field(default=None, min_length=1, max_length=255)
    credential_type: Literal["certification", "license", "award", "formal_credential"] | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("name", "issuer", "credential_id", "url")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _dates_are_valid(self) -> Self:
        _validate_date_range(self.issue_date, self.expiration_date, "credential")
        return self


class CareerGoalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_type: Literal[
        "career_direction",
        "near_term_objective",
        "long_term_objective",
        "role_progression",
        "learning_development",
    ]
    description: str = Field(min_length=1, max_length=2048)
    target_date: date | None = None
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str) -> str:
        return _clean_text(value)


class RolePreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role_title: str | None = Field(default=None, min_length=1, max_length=255)
    function: str | None = Field(default=None, min_length=1, max_length=128)
    seniority: str | None = Field(default=None, min_length=1, max_length=128)
    employment_type: str | None = Field(default=None, min_length=1, max_length=128)
    preference_kind: PreferenceKind = PreferenceKind.PREFERRED
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("role_title", "function", "seniority", "employment_type")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _has_role_signal(self) -> Self:
        if not any([self.role_title, self.function, self.seniority, self.employment_type]):
            raise ValueError("role preference requires at least one role signal")
        return self


class IndustryPreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    industry: str = Field(min_length=1, max_length=128)
    preference_kind: PreferenceKind = PreferenceKind.PREFERRED
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("industry")
    @classmethod
    def _clean_industry(cls, value: str) -> str:
        return _clean_text(value)


class GeographicConstraintPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    location: str | None = Field(default=None, min_length=1, max_length=255)
    constraint_kind: Literal["target", "acceptable", "excluded", "remote_restriction"] = "target"
    relocation_willingness: Literal["yes", "no", "conditional"] | None = None
    relocation_constraints: str | None = Field(default=None, min_length=1, max_length=1024)
    commute_radius_miles: int | None = Field(default=None, ge=0, le=250)
    remote_location_restriction: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("location", "relocation_constraints", "remote_location_restriction")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _constraint_is_coherent(self) -> Self:
        if self.constraint_kind != "remote_restriction" and self.location is None:
            raise ValueError(
                "geographic constraint requires location unless it is remote_restriction"
            )
        if (
            self.constraint_kind == "remote_restriction"
            and self.remote_location_restriction is None
        ):
            raise ValueError("remote_restriction requires remote_location_restriction")
        return self


class CompensationConstraintPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_amount: int | None = Field(default=None, ge=0)
    target_amount: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    period: Literal["hourly", "monthly", "annual", "project"] = "annual"
    compensation_type: Literal["salary", "hourly", "total", "contract"] = "salary"
    negotiable: bool | None = None

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        cleaned = _clean_text(value).upper()
        if not re.fullmatch(r"[A-Z]{3}", cleaned):
            raise ValueError("currency must be a three-letter ISO-style code")
        return cleaned

    @model_validator(mode="after")
    def _range_is_valid(self) -> Self:
        if self.minimum_amount is None and self.target_amount is None:
            raise ValueError("compensation constraint requires minimum_amount or target_amount")
        if (
            self.minimum_amount is not None
            and self.target_amount is not None
            and self.target_amount < self.minimum_amount
        ):
            raise ValueError("target_amount must be greater than or equal to minimum_amount")
        return self


class TimingPreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timing_type: Literal[
        "desired_start",
        "availability",
        "search_urgency",
        "graduation",
        "internship_window",
        "seasonal_window",
    ]
    date_value: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    urgency: Literal["low", "medium", "high", "immediate"] | None = None
    description: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def _timing_is_valid(self) -> Self:
        _validate_date_range(self.start_date, self.end_date, "timing")
        if self.timing_type == "search_urgency" and self.urgency is None:
            raise ValueError("search_urgency timing requires urgency")
        if self.date_value is None and self.start_date is None and self.urgency is None:
            raise ValueError("timing preference requires a date, window, or urgency")
        return self


class WorkArrangementPreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    arrangement: WorkArrangement
    willingness: Literal["yes", "no", "preferred", "required", "excluded"]
    constraints: str | None = Field(default=None, min_length=1, max_length=1024)
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("constraints")
    @classmethod
    def _clean_constraints(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


PAYLOAD_MODEL_BY_FACT_TYPE = {
    CareerFactType.EDUCATION: EducationPayload,
    CareerFactType.EXPERIENCE: ExperiencePayload,
    CareerFactType.SKILL: SkillPayload,
    CareerFactType.PROJECT: ProjectPayload,
    CareerFactType.CREDENTIAL: CredentialPayload,
    CareerFactType.CAREER_GOAL: CareerGoalPayload,
    CareerFactType.ROLE_PREFERENCE: RolePreferencePayload,
    CareerFactType.INDUSTRY_PREFERENCE: IndustryPreferencePayload,
    CareerFactType.GEOGRAPHIC_CONSTRAINT: GeographicConstraintPayload,
    CareerFactType.COMPENSATION_CONSTRAINT: CompensationConstraintPayload,
    CareerFactType.TIMING_PREFERENCE: TimingPreferencePayload,
    CareerFactType.WORK_ARRANGEMENT_PREFERENCE: WorkArrangementPreferencePayload,
}


class CareerIdentityFactInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_type: CareerFactType
    payload: dict[str, Any]
    state: CareerFactState = CareerFactState.EXPLICIT
    provenance: FactProvenanceInput | None = None
    normalized_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("normalized_key")
    @classmethod
    def _clean_key(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class CareerIdentityFactUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, Any] | None = None
    state: CareerFactState | None = None
    provenance: FactProvenanceInput | None = None
    normalized_key: str | None = Field(default=None, min_length=1, max_length=255)
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("normalized_key")
    @classmethod
    def _clean_key(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class CareerIdentityPrivacyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ingestion_consent_granted: bool | None = None
    inference_consent_granted: bool | None = None
    downstream_personalization_consent_granted: bool | None = None
    retain_import_metadata: bool | None = None
    expected_version: int | None = Field(default=None, ge=1)


class CareerIdentityIngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: Literal["resume_text", "profile_text", "structured_profile"]
    source_label: str | None = Field(default=None, min_length=1, max_length=255)
    text: str | None = Field(default=None, min_length=1, max_length=20000)
    structured_profile: dict[str, Any] | None = None
    consent_granted: bool = False
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("source_label")
    @classmethod
    def _clean_source_label(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("text")
    @classmethod
    def _clean_text_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _input_shape_matches_source_type(self) -> Self:
        if self.source_type in {"resume_text", "profile_text"}:
            if self.text is None:
                raise ValueError("text is required for resume_text/profile_text ingestion")
            if self.structured_profile is not None:
                raise ValueError("structured_profile is not accepted for text ingestion")
        if self.source_type == "structured_profile":
            if self.structured_profile is None:
                raise ValueError("structured_profile is required")
            if self.text is not None:
                raise ValueError("text is not accepted for structured_profile ingestion")
        return self


class CareerIdentityFactView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_identity_fact_id: str
    fact_type: CareerFactType
    normalized_key: str
    state: CareerFactState
    payload: dict[str, Any]
    provenance: dict[str, Any]
    source_import_id: str | None
    source_label: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CareerIdentityView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_identity_id: str
    user_id: str
    current_version: int
    completeness_state: CareerCompletenessState
    sufficiency_state: CareerSufficiencyState
    privacy: dict[str, Any]
    completeness: dict[str, Any] | None
    facts: dict[str, list[dict[str, Any]]]
    created_at: datetime
    updated_at: datetime


class CareerIdentityIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_identity_import_id: str | None
    identity_version: int
    status: Literal["completed", "failed", "duplicate"]
    imported_fact_count: int
    created_fact_count: int
    updated_fact_count: int
    protected_fact_count: int
    duplicate_fact_count: int
    diagnostics: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    completeness: dict[str, Any]


def validate_payload(fact_type: CareerFactType, payload: dict[str, Any]) -> BaseModel:
    model_type = PAYLOAD_MODEL_BY_FACT_TYPE[fact_type]
    return model_type.model_validate(payload)


def canonical_payload(fact_type: CareerFactType, payload: dict[str, Any]) -> dict[str, Any]:
    return validate_payload(fact_type, payload).model_dump(mode="json")


def normalized_key_for_payload(
    fact_type: CareerFactType,
    payload: dict[str, Any],
    provided_key: str | None = None,
) -> str:
    if provided_key is not None:
        return _key_part(provided_key)
    validated = validate_payload(fact_type, payload)
    data = validated.model_dump(mode="json")
    if fact_type is CareerFactType.EDUCATION:
        return "education:" + ":".join(
            _key_part(data.get(key))
            for key in ("institution", "degree_type", "field_of_study")
            if data.get(key)
        )
    if fact_type is CareerFactType.EXPERIENCE:
        return "experience:" + ":".join(
            _key_part(data.get(key))
            for key in ("organization", "title", "start_date")
            if data.get(key)
        )
    if fact_type is CareerFactType.SKILL:
        return "skill:" + _key_part(data.get("normalized_name") or data["name"])
    if fact_type is CareerFactType.PROJECT:
        return "project:" + _key_part(data["name"])
    if fact_type is CareerFactType.CREDENTIAL:
        return "credential:" + ":".join(
            _key_part(data.get(key)) for key in ("issuer", "name") if data.get(key)
        )
    if fact_type is CareerFactType.CAREER_GOAL:
        return f"goal:{data['goal_type']}:{_key_part(data['description'])[:80]}"
    if fact_type is CareerFactType.ROLE_PREFERENCE:
        return "role_preference:" + ":".join(
            _key_part(data.get(key))
            for key in ("preference_kind", "role_title", "function", "seniority", "employment_type")
            if data.get(key)
        )
    if fact_type is CareerFactType.INDUSTRY_PREFERENCE:
        return f"industry_preference:{data['preference_kind']}:{_key_part(data['industry'])}"
    if fact_type is CareerFactType.GEOGRAPHIC_CONSTRAINT:
        basis = data.get("location") or data.get("remote_location_restriction")
        return f"geographic_constraint:{data['constraint_kind']}:{_key_part(basis)}"
    if fact_type is CareerFactType.COMPENSATION_CONSTRAINT:
        return (
            "compensation_constraint:"
            f"{data['currency']}:{data['period']}:{data['compensation_type']}"
        )
    if fact_type is CareerFactType.TIMING_PREFERENCE:
        return f"timing_preference:{data['timing_type']}"
    if fact_type is CareerFactType.WORK_ARRANGEMENT_PREFERENCE:
        return f"work_arrangement_preference:{data['arrangement']}"
    raise AssertionError(f"unhandled fact type {fact_type}")


def provenance_payload(
    state: CareerFactState,
    provenance: FactProvenanceInput | None,
    *,
    source_import_id: str | None = None,
) -> dict[str, Any]:
    payload = provenance.model_dump(mode="json") if provenance is not None else {}
    payload["state"] = state.value
    payload["created_by"] = (
        "user" if state in {CareerFactState.EXPLICIT, CareerFactState.CONFIRMED} else "system"
    )
    if source_import_id is not None:
        payload["source_import_id"] = source_import_id
    payload.setdefault("history", [])
    return payload


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _clean_text(value)


def _clean_text(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError("string fields must not be blank")
    return cleaned


def _clean_string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else value
    if not isinstance(values, tuple | list):
        raise ValueError("expected a list of strings")
    cleaned = tuple(dict.fromkeys(_clean_text(str(item)) for item in values))
    return cleaned


def _validate_date_range(
    start_date: date | None,
    end_date: date | None,
    label: str,
) -> None:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError(f"{label} end_date cannot be before start_date")


def _key_part(value: object) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"
