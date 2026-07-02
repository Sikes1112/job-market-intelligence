"""Public-safe Layer 24A policy intelligence DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

PolicySeverity = Literal["info", "low", "medium", "high"]
MetricPolarity = Literal["higher_is_better", "higher_is_risk", "contextual"]
ScoreBand = Literal["very_low", "low", "moderate", "high", "very_high", "unknown"]
SourceDataBasis = Literal["canonical_market_truth", "mixed", "unknown"]

FORBIDDEN_POLICY_FIELD_NAMES = frozenset(
    {
        "admin_metadata",
        "api_key",
        "classification_confidence",
        "eligibility_override_reason",
        "eligibility_score",
        "employer_influence_metadata_id",
        "fact_source_link_id",
        "internal_review_notes",
        "normalized_company_name",
        "opportunity_review_action_id",
        "opportunity_submission_id",
        "presence_id",
        "private_metadata",
        "raw_submission_json",
        "raw_source_refs",
        "review_note",
        "reviewer_id",
        "reviewer_name",
        "source_id",
        "source_refs",
        "source_versions",
        "submitter_contact",
        "submitted_by",
        "user_id",
    }
)

DISALLOWED_POLICY_LANGUAGE = (
    "this policy caused",
    "is failing because",
    "city is failing",
    "tax incentives",
    "should give tax incentives",
    "should close this program",
    "should close",
    "students from this school will leave",
    "will definitely",
    "guaranteed",
    "guarantee",
)


class PolicyWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    severity: PolicySeverity
    message: str = Field(min_length=1, max_length=512)
    public_interpretation: str = Field(min_length=1, max_length=512)

    @field_validator("code", "message", "public_interpretation")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class PolicyConfidenceFactor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    severity: PolicySeverity
    explanation: str = Field(min_length=1, max_length=512)

    @field_validator("code", "explanation")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class PolicyConfidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: Confidence = Confidence.UNKNOWN
    score: float = Field(ge=0.0, le=1.0)
    label: str = Field(min_length=1, max_length=120)
    factors: tuple[PolicyConfidenceFactor, ...] = Field(default_factory=tuple)

    @field_validator("label")
    @classmethod
    def _label_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class PolicyFreshnessMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    freshness_expires_at: datetime | None = None
    stale: bool = False
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("generated_at", "freshness_expires_at")
    @classmethod
    def _datetime_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("policy freshness datetime values must be timezone-aware")
        return value

    @field_validator("notes")
    @classmethod
    def _notes_are_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PolicySourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: SourceDataBasis = "canonical_market_truth"
    source_count: int = Field(ge=0)
    source_categories: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    evidence_summary: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("source_categories", "evidence_summary")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PolicyPublicSafetyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    public_safe: Literal[True] = True
    redacted_internal_fields: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    student_level_data_exposed: Literal[False] = False
    partner_submission_internals_exposed: Literal[False] = False
    private_review_fields_exposed: Literal[False] = False

    @field_validator("redacted_internal_fields")
    @classmethod
    def _redacted_fields_are_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PolicyAnalysisWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Literal["current_available_market_signals"] = "current_available_market_signals"
    generated_at: datetime
    freshness_expires_at: datetime | None = None

    @field_validator("generated_at", "freshness_expires_at")
    @classmethod
    def _datetime_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("analysis window datetime values must be timezone-aware")
        return value


class PolicyMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(min_length=1, max_length=96)
    label: str = Field(min_length=1, max_length=160)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    band: ScoreBand
    polarity: MetricPolarity
    interpretation_label: str = Field(min_length=1, max_length=160)
    explainable_inputs: dict[str, Any] = Field(default_factory=dict)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @model_validator(mode="after")
    def _score_and_band_are_consistent(self) -> PolicyMetric:
        if self.score is None and self.band != "unknown":
            raise ValueError("unknown metric scores must use the unknown band")
        if self.score is not None and self.band == "unknown":
            raise ValueError("scored metrics must not use the unknown band")
        bad_fields = _find_forbidden_field_names(self.explainable_inputs)
        if bad_fields:
            raise ValueError(f"policy metric exposes forbidden input fields: {bad_fields!r}")
        return self

    @field_validator("metric_id", "label", "interpretation_label")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations", "warning_codes")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class RegionalPolicyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_concentration_score: PolicyMetric
    early_career_access_score: PolicyMetric
    internship_pipeline_score: PolicyMetric
    employer_dependency_score: PolicyMetric
    sector_diversity_score: PolicyMetric
    talent_export_risk_score: PolicyMetric


class PolicyFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1, max_length=128)
    finding_type: str = Field(min_length=1, max_length=96)
    severity: PolicySeverity
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=900)
    evidence_references: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    recommended_interpretation: str = Field(min_length=1, max_length=700)
    recommended_actions: tuple[str, ...] = Field(default_factory=tuple, max_length=8)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator(
        "finding_id",
        "finding_type",
        "title",
        "summary",
        "recommended_interpretation",
    )
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("evidence_references", "recommended_actions", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PolicyRegionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    region_type: str = Field(min_length=1, max_length=64)
    present_company_count: int = Field(ge=0)
    hiring_record_count: int = Field(ge=0)
    entry_level_record_count: int = Field(ge=0)
    score_available: bool
    normalization_basis: str = Field(min_length=1, max_length=160)

    @field_validator("region_id", "region_name", "region_type", "normalization_basis")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class RegionalPolicyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    analysis_window: PolicyAnalysisWindow
    opportunity_concentration_score: PolicyMetric
    early_career_access_score: PolicyMetric
    internship_pipeline_score: PolicyMetric
    employer_dependency_score: PolicyMetric
    sector_diversity_score: PolicyMetric
    talent_export_risk_score: PolicyMetric
    policy_findings: tuple[PolicyFinding, ...] = Field(default_factory=tuple)
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    freshness: PolicyFreshnessMetadata
    confidence: PolicyConfidenceMetadata
    source_summary: PolicySourceSummary
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata

    @model_validator(mode="after")
    def _profile_is_public_safe(self) -> RegionalPolicyProfile:
        if not self.public_safe:
            raise ValueError("Layer 24A policy profiles must be public safe")
        bad_fields = _find_forbidden_field_names(self.model_dump(mode="python"))
        if bad_fields:
            raise ValueError(f"policy profile exposes forbidden fields: {bad_fields!r}")
        return self

    @field_validator("region_id", "region_name")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class WorkforceDashboardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_summary: PolicyRegionSummary
    core_metrics: RegionalPolicyMetrics
    policy_findings: tuple[PolicyFinding, ...] = Field(default_factory=tuple)
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata

    @model_validator(mode="after")
    def _dashboard_is_public_safe(self) -> WorkforceDashboardPayload:
        if not self.public_safe:
            raise ValueError("Layer 24A dashboard payloads must be public safe")
        bad_fields = _find_forbidden_field_names(self.model_dump(mode="python"))
        if bad_fields:
            raise ValueError(f"policy dashboard exposes forbidden fields: {bad_fields!r}")
        return self


class EarlyCareerAccessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_summary: PolicyRegionSummary
    early_career_access_score: PolicyMetric
    internship_pipeline_score: PolicyMetric
    policy_findings: tuple[PolicyFinding, ...] = Field(default_factory=tuple)
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata


class EmployerConcentrationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_summary: PolicyRegionSummary
    opportunity_concentration_score: PolicyMetric
    employer_dependency_score: PolicyMetric
    sector_diversity_score: PolicyMetric
    policy_findings: tuple[PolicyFinding, ...] = Field(default_factory=tuple)
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata


class PolicyProfileReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    confidence: PolicyConfidenceMetadata
    key_metric_bands: dict[str, ScoreBand] = Field(default_factory=dict)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=24)

    @field_validator("region_id", "region_name")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("warning_codes")
    @classmethod
    def _warnings_are_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class SectorGapFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sector: str = Field(min_length=1, max_length=96)
    gap_type: str = Field(min_length=1, max_length=96)
    severity: PolicySeverity
    evidence_references: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    interpretation: str = Field(min_length=1, max_length=700)
    recommended_strategy_candidate: str = Field(min_length=1, max_length=400)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator(
        "sector",
        "gap_type",
        "interpretation",
        "recommended_strategy_candidate",
    )
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("evidence_references", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class EmployerBaseRiskFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_type: str = Field(min_length=1, max_length=96)
    severity: PolicySeverity
    interpretation: str = Field(min_length=1, max_length=700)
    evidence_references: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    strategy_candidate: str = Field(min_length=1, max_length=400)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("risk_type", "interpretation", "strategy_candidate")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("evidence_references", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PeerMetricComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(min_length=1, max_length=96)
    target_value: float | None = Field(default=None, ge=0.0, le=1.0)
    peer_value: float | None = Field(default=None, ge=0.0, le=1.0)
    comparison: Literal["target_stronger", "target_weaker", "similar", "unknown"]

    @field_validator("metric_id")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)


class PeerMetroComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    peer_region_id: str = Field(min_length=1, max_length=64)
    peer_region_name: str = Field(min_length=1, max_length=128)
    similarity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    similarity_rationale: str = Field(min_length=1, max_length=700)
    metrics_compared: tuple[PeerMetricComparison, ...] = Field(default_factory=tuple)
    target_region_stronger: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    target_region_weaker: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("peer_region_id", "peer_region_name", "similarity_rationale")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("target_region_stronger", "target_region_weaker", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class CompanyAttractionFit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str = Field(min_length=1, max_length=64)
    company_name: str = Field(min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=96)
    fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fit_band: ScoreBand
    fit_rationale: str = Field(min_length=1, max_length=700)
    regional_gap_addressed: str = Field(min_length=1, max_length=160)
    early_career_or_internship_relevance: str = Field(min_length=1, max_length=400)
    diversification_impact: str = Field(min_length=1, max_length=400)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @model_validator(mode="after")
    def _band_matches_score(self) -> CompanyAttractionFit:
        if self.fit_score is None and self.fit_band != "unknown":
            raise ValueError("unknown fit scores must use the unknown fit band")
        if self.fit_score is not None and self.fit_band == "unknown":
            raise ValueError("scored fit candidates must not use unknown fit band")
        return self

    @field_validator(
        "company_id",
        "company_name",
        "sector",
        "fit_rationale",
        "regional_gap_addressed",
        "early_career_or_internship_relevance",
        "diversification_impact",
    )
    @classmethod
    def _text_is_safe(cls, value: str | None) -> str | None:
        return _safe_text(value) if value is not None else None

    @field_validator("limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class DiversificationStrategyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_type: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=700)
    evidence_references: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("candidate_type", "title", "rationale")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("evidence_references", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class InstitutionRegionalPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    institution_id: str | None = Field(default=None, max_length=64)
    institution_name: str = Field(min_length=1, max_length=255)
    region_id: str = Field(min_length=1, max_length=64)
    program_areas_available: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    related_demand_sectors: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    nearby_early_career_demand_summary: str = Field(min_length=1, max_length=500)
    internship_access_summary: str = Field(min_length=1, max_length=500)
    alignment_confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator(
        "institution_id",
        "institution_name",
        "region_id",
        "nearby_early_career_demand_summary",
        "internship_access_summary",
    )
    @classmethod
    def _text_is_safe(cls, value: str | None) -> str | None:
        return _safe_text(value) if value is not None else None

    @field_validator("program_areas_available", "related_demand_sectors", "limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class ProgramDemandAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    program_area: str = Field(min_length=1, max_length=160)
    nearby_employer_demand: PolicyMetric
    internship_pipeline_strength: PolicyMetric
    early_career_access: PolicyMetric
    alignment_score: float | None = Field(default=None, ge=0.0, le=1.0)
    alignment_band: ScoreBand
    finding: str = Field(min_length=1, max_length=700)
    confidence: Confidence = Confidence.UNKNOWN
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @model_validator(mode="after")
    def _alignment_score_and_band_are_consistent(self) -> ProgramDemandAlignment:
        if self.alignment_score is None and self.alignment_band != "unknown":
            raise ValueError("unknown alignment scores must use the unknown band")
        if self.alignment_score is not None and self.alignment_band == "unknown":
            raise ValueError("scored alignments must not use the unknown band")
        return self

    @field_validator("program_area", "finding")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class EducationWorkforceAlignmentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    analysis_window: PolicyAnalysisWindow
    institution_pipeline_summaries: tuple[InstitutionRegionalPipeline, ...] = (
        Field(default_factory=tuple)
    )
    program_alignment_findings: tuple[ProgramDemandAlignment, ...] = Field(
        default_factory=tuple
    )
    internship_alignment_gaps: tuple[SectorGapFinding, ...] = Field(default_factory=tuple)
    local_employer_absorption_score: PolicyMetric
    talent_export_pressure_score: PolicyMetric
    student_interest_market_fit: PolicyMetric | None = None
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata

    @model_validator(mode="after")
    def _education_payload_is_public_safe(self) -> EducationWorkforceAlignmentProfile:
        if not self.public_safe:
            raise ValueError("education-workforce alignment payloads must be public safe")
        bad_fields = _find_forbidden_field_names(self.model_dump(mode="python"))
        if bad_fields:
            raise ValueError(f"education alignment exposes forbidden fields: {bad_fields!r}")
        return self

    @field_validator("region_id", "region_name")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class PeerComparisonProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    analysis_window: PolicyAnalysisWindow
    peer_metro_comparisons: tuple[PeerMetroComparison, ...] = Field(default_factory=tuple)
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata

    @model_validator(mode="after")
    def _peer_payload_is_public_safe(self) -> PeerComparisonProfile:
        if not self.public_safe:
            raise ValueError("peer comparison payloads must be public safe")
        bad_fields = _find_forbidden_field_names(self.model_dump(mode="python"))
        if bad_fields:
            raise ValueError(f"peer comparison exposes forbidden fields: {bad_fields!r}")
        return self

    @field_validator("region_id", "region_name")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


class EconomicDevelopmentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    analysis_window: PolicyAnalysisWindow
    regional_policy_profile: PolicyProfileReference
    sector_gap_findings: tuple[SectorGapFinding, ...] = Field(default_factory=tuple)
    employer_base_risk_findings: tuple[EmployerBaseRiskFinding, ...] = Field(
        default_factory=tuple
    )
    peer_metro_comparisons: tuple[PeerMetroComparison, ...] = Field(default_factory=tuple)
    company_attraction_candidates: tuple[CompanyAttractionFit, ...] = Field(
        default_factory=tuple
    )
    diversification_recommendations: tuple[DiversificationStrategyCandidate, ...] = (
        Field(default_factory=tuple)
    )
    warnings: tuple[PolicyWarning, ...] = Field(default_factory=tuple)
    confidence: PolicyConfidenceMetadata
    freshness: PolicyFreshnessMetadata
    source_summary: PolicySourceSummary
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    public_safe: bool = True
    public_safety: PolicyPublicSafetyMetadata

    @model_validator(mode="after")
    def _economic_payload_is_public_safe(self) -> EconomicDevelopmentProfile:
        if not self.public_safe:
            raise ValueError("economic development payloads must be public safe")
        bad_fields = _find_forbidden_field_names(self.model_dump(mode="python"))
        if bad_fields:
            raise ValueError(
                f"economic development profile exposes forbidden fields: {bad_fields!r}"
            )
        return self

    @field_validator("region_id", "region_name")
    @classmethod
    def _text_is_safe(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("limitations")
    @classmethod
    def _tuple_text_is_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item) for item in value if item.strip())


def band_for_score(score: float | None) -> ScoreBand:
    if score is None:
        return "unknown"
    if score < 0.2:
        return "very_low"
    if score < 0.4:
        return "low"
    if score < 0.65:
        return "moderate"
    if score < 0.8:
        return "high"
    return "very_high"


def _safe_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    lowered = stripped.casefold()
    for phrase in DISALLOWED_POLICY_LANGUAGE:
        if phrase in lowered:
            raise ValueError(f"unsafe policy language: {phrase!r}")
    return stripped


def _find_forbidden_field_names(value: Any, path: str = "") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in FORBIDDEN_POLICY_FIELD_NAMES:
                found.append(child_path)
            found.extend(_find_forbidden_field_names(child, child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_field_names(child, f"{path}[{index}]"))
    return tuple(found)
