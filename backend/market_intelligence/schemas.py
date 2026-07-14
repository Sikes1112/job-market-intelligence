"""Public-safe DTOs for Layer 34 market intelligence."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Any


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class CareerGoal(_Vocabulary):
    SOFTWARE_ENGINEERING = "software_engineering"
    PRODUCT_MANAGEMENT = "product_management"
    AI_ML = "ai_ml"
    CYBERSECURITY = "cybersecurity"
    DATA_SCIENCE = "data_science"


class IntelligenceConfidence(_Vocabulary):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    LIMITED = "limited"


class IntelligenceFreshness(_Vocabulary):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class ComparisonOutcome(_Vocabulary):
    MARKET_A = "market_a"
    MARKET_B = "market_b"
    TIE = "tie"
    NO_WINNER = "no_winner"


class EvidenceSufficiency(_Vocabulary):
    COMPARISON_READY = "comparison_ready"
    LIMITED_EVIDENCE = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_SUPPORTED = "not_supported"


class EvidenceBasis(_Vocabulary):
    DIRECT = "direct"
    PROXY = "proxy"
    DIRECT_AND_PROXY = "direct_and_proxy"
    NO_QUALIFYING_EVIDENCE = "no_qualifying_evidence"


class CalibrationTieStatus(_Vocabulary):
    CLEAR = "clear"
    NEAR_TIE = "near_tie"
    TIE = "tie"


class RankingStabilityStatus(_Vocabulary):
    STABLE = "stable"
    SENSITIVE = "sensitive"
    UNSTABLE = "unstable"
    INDETERMINATE = "indeterminate"


class DifferentiationFindingCode(_Vocabulary):
    REPEATED_STRENGTH = "repeated_strength"
    REPEATED_WEAKNESS = "repeated_weakness"
    REPEATED_OVERVIEW = "repeated_overview"
    REPEATED_DRIVER = "repeated_driver"
    NEAR_IDENTICAL_GOAL_ORDERING = "near_identical_goal_ordering"
    GENERIC_DESCRIPTION = "generic_description"
    UNSUPPORTED_STEREOTYPE = "unsupported_stereotype"
    MISSING_MARKET_SPECIFIC_EVIDENCE = "missing_market_specific_evidence"


class DifferentiationSeverity(_Vocabulary):
    INFO = "info"
    WARNING = "warning"
    NEEDS_IMPROVEMENT = "needs_improvement"


class RobustnessScenarioCode(_Vocabulary):
    UNKNOWN_TO_OBSERVED_ZERO = "unknown_to_observed_zero"
    OBSERVED_ZERO_TO_UNKNOWN = "observed_zero_to_unknown"
    STALE_SOURCE = "stale_source"
    EXPIRED_SOURCE = "expired_source"
    LOW_CONFIDENCE_EXCLUSION = "low_confidence_exclusion"
    RANKING_EXCLUSION = "ranking_exclusion"
    MISSING_INTERNSHIP = "missing_internship"
    MISSING_COOP = "missing_coop"
    DOMINANT_EMPLOYER = "dominant_employer"
    SOURCE_CONCENTRATION = "source_concentration"
    SPARSE_COVERAGE = "sparse_coverage"
    DIRECT_EVIDENCE_REMOVED = "direct_evidence_removed"
    PROXY_ONLY_EVIDENCE = "proxy_only_evidence"
    EQUAL_EVIDENCE_TIE = "equal_evidence_tie"
    SMALL_SCORE_PERTURBATION = "small_score_perturbation"
    CONTRADICTORY_INPUTS = "contradictory_inputs"


class CalibrationPlaceholderStatus(_Vocabulary):
    NOT_EVALUATED = "not_evaluated"


class ContradictionCode(_Vocabulary):
    HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE = "high_confidence_insufficient_evidence"
    STRONG_INTERNSHIP_MISSING_EVIDENCE = "strong_internship_missing_evidence"
    CURRENT_FRESHNESS_STALE_PRIMARY_SOURCE = "current_freshness_stale_primary_source"
    WINNER_WITH_LOWER_SCORE = "winner_with_lower_score"
    OPPOSITE_WEAKNESS_AND_DRIVER = "opposite_weakness_and_driver"
    SPECIFIC_ROLE_RECOMMENDATION_WITHOUT_DIRECT_EVIDENCE = (
        "specific_role_recommendation_without_direct_evidence"
    )
    COMPARISON_READY_WITHOUT_QUALIFYING_EVIDENCE = (
        "comparison_ready_without_qualifying_evidence"
    )
    NO_LIMITATIONS_DESPITE_CRITICAL_GAPS = "no_limitations_despite_critical_gaps"
    ALPHABETICAL_TIE_DISPLAYED_AS_WINNER = "alphabetical_tie_displayed_as_winner"


class ContradictionSeverity(_Vocabulary):
    WARNING = "warning"
    BLOCKING = "blocking"


class ContradictionStatus(_Vocabulary):
    CLEAR = "clear"
    WARNINGS = "warnings"
    BLOCKING = "blocking"


class ExplanationQualityStatus(_Vocabulary):
    PASSED = "passed"
    NEEDS_IMPROVEMENT = "needs_improvement"


@dataclass(frozen=True, slots=True)
class PublicDTO:
    def as_dict(self) -> dict[str, Any]:
        return {field.name: _json_safe(getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class EvidenceGrounding(PublicDTO):
    evidence_areas_used: tuple[str, ...]
    evidence_areas_missing: tuple[str, ...]
    direct_evidence_summary: tuple[str, ...]
    proxy_evidence_summary: tuple[str, ...]
    freshness: IntelligenceFreshness
    coverage: str
    excluded_fact_summary: str
    confidence_constraints: tuple[str, ...]
    score_margin: float | None
    stability_status: RankingStabilityStatus
    stability_scenarios: tuple[RobustnessScenarioResult, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceCategoryLabel(PublicDTO):
    code: str
    label: str


@dataclass(frozen=True, slots=True)
class CareerGoalDefinition(PublicDTO):
    goal: CareerGoal
    label: str
    description: str
    direct_signals: tuple[str, ...]
    direct_evidence_categories: tuple[str, ...] = ()
    proxy_evidence_categories: tuple[str, ...] = ()
    minimum_direct_evidence: int = 0
    minimum_total_evidence: int = 0
    proxy_only_confidence_cap: IntelligenceConfidence = IntelligenceConfidence.LIMITED
    unsupported_conditions: tuple[str, ...] = ()
    weighting_rationale: str = ""
    public_safe_labels: tuple[EvidenceCategoryLabel, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GoalEvidenceClassification(PublicDTO):
    goal: CareerGoal
    evidence_basis: EvidenceBasis
    direct_evidence_categories: tuple[str, ...]
    proxy_evidence_categories: tuple[str, ...]
    missing_direct_evidence_categories: tuple[str, ...]
    unknown_evidence_categories: tuple[str, ...]
    direct_evidence_count: int
    proxy_evidence_count: int
    total_evidence_count: int
    minimum_direct_evidence: int
    minimum_total_evidence: int
    meets_minimum_direct_evidence: bool
    meets_minimum_total_evidence: bool
    proxy_only_confidence_cap: IntelligenceConfidence
    unsupported_conditions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketInsight(PublicDTO):
    code: str
    message: str
    evidence: str
    impact: str


@dataclass(frozen=True, slots=True)
class OpportunityEnvironment(PublicDTO):
    hiring_activity: str
    employer_diversity: str
    internship_ecosystem: str
    coop_ecosystem: str
    early_career_support: str
    hiring_momentum: str
    overall: str


@dataclass(frozen=True, slots=True)
class MarketIntelligenceProfile(PublicDTO):
    market_key: str
    market_name: str
    region_id: str
    overview: str
    strengths: tuple[MarketInsight, ...]
    weaknesses: tuple[MarketInsight, ...]
    hiring_summary: str
    employer_summary: str
    internship_summary: str
    coop_summary: str
    early_career_summary: str
    opportunity_environment: OpportunityEnvironment
    confidence: IntelligenceConfidence
    confidence_score: float
    freshness: IntelligenceFreshness
    coverage_summary: str
    limitations: tuple[str, ...]
    supporting_metrics: dict[str, int | float | str | None]
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class RankingDriver(PublicDTO):
    code: str
    label: str
    contribution: float
    evidence: str


@dataclass(frozen=True, slots=True)
class ContradictionFinding(PublicDTO):
    code: ContradictionCode
    severity: ContradictionSeverity
    message: str
    evidence: str
    blocks_recommendation: bool


@dataclass(frozen=True, slots=True)
class ContradictionAnalysis(PublicDTO):
    status: ContradictionStatus
    findings: tuple[ContradictionFinding, ...]
    has_blocking: bool


@dataclass(frozen=True, slots=True)
class RobustnessScenarioRankingResult(PublicDTO):
    market_key: str
    rank: int
    score: float
    confidence: IntelligenceConfidence
    freshness: IntelligenceFreshness
    evidence_sufficiency: EvidenceSufficiency
    top_market_key: str | None


@dataclass(frozen=True, slots=True)
class RobustnessScenarioResult(PublicDTO):
    scenario: RobustnessScenarioCode
    label: str
    status: RankingStabilityStatus
    baseline_result: RobustnessScenarioRankingResult
    scenario_result: RobustnessScenarioRankingResult
    rank_change: int
    winner_change: bool
    score_delta: float
    confidence_delta: int
    sufficiency_delta: str
    explanation: str


@dataclass(frozen=True, slots=True)
class MarketGoalStabilityAnalysis(PublicDTO):
    status: RankingStabilityStatus
    scenarios: tuple[RobustnessScenarioResult, ...]


@dataclass(frozen=True, slots=True)
class DifferentiationFinding(PublicDTO):
    code: DifferentiationFindingCode
    severity: DifferentiationSeverity
    field: str
    market_keys: tuple[str, ...]
    goal_keys: tuple[CareerGoal, ...]
    message: str
    evidence: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class CrossGoalRankCorrelation(PublicDTO):
    goal_a: CareerGoal
    goal_b: CareerGoal
    common_market_count: int
    spearman_correlation: float | None
    identical_order: bool
    nearly_identical: bool
    shared_top_market_key: str | None
    rank_deltas: dict[str, int]


@dataclass(frozen=True, slots=True)
class MarketDifferentiationAudit(PublicDTO):
    profile_count: int
    goal_count: int
    differentiation_score: float
    duplicated_language_findings: tuple[DifferentiationFinding, ...]
    repeated_driver_findings: tuple[DifferentiationFinding, ...]
    cross_goal_rank_correlation_summary: tuple[CrossGoalRankCorrelation, ...]
    required_improvement_recommendations: tuple[str, ...]
    true_similarity_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExplainableRankingItem(PublicDTO):
    rank: int
    market_key: str
    market_name: str
    goal: CareerGoal
    score: float
    raw_score: float
    confidence: IntelligenceConfidence
    freshness: IntelligenceFreshness
    ranking_drivers: tuple[RankingDriver, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    limitations: tuple[str, ...]
    supporting_metrics: dict[str, int | float | str | None]
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    evidence_basis: EvidenceBasis = EvidenceBasis.NO_QUALIFYING_EVIDENCE
    is_provisional: bool = False
    abstention_reason: str | None = None
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class ExplainableRankingReport(PublicDTO):
    goal: CareerGoal
    goal_definition: CareerGoalDefinition
    ranked_markets: tuple[ExplainableRankingItem, ...]
    top_market_key: str | None
    explanation: str
    limitations: tuple[str, ...]
    tie_breaker: str
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    is_provisional: bool = False
    abstention_reason: str | None = None
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class MarketGoalCalibrationResult(PublicDTO):
    market_key: str
    market_name: str
    goal: CareerGoal
    score: float
    rank: int
    score_margin: float
    confidence: IntelligenceConfidence
    freshness: IntelligenceFreshness
    evidence_sufficiency: EvidenceSufficiency
    direct_evidence_summary: tuple[str, ...]
    proxy_evidence_summary: tuple[str, ...]
    top_drivers: tuple[RankingDriver, ...]
    limitations: tuple[str, ...]
    tie_status: CalibrationTieStatus
    tied_market_keys: tuple[str, ...]
    near_tie_market_keys: tuple[str, ...]
    stability_status: RankingStabilityStatus
    stability_scenarios: tuple[RobustnessScenarioResult, ...]
    contradiction_status: ContradictionStatus
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class MarketCalibrationReport(PublicDTO):
    as_of: str | None
    markets: tuple[str, ...]
    goals: tuple[CareerGoal, ...]
    market_goal_matrix: dict[str, dict[str, MarketGoalCalibrationResult]]
    result_count: int
    near_tie_threshold: float
    tie_breaker: str
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityEvidenceSummary(PublicDTO):
    evidence_basis: EvidenceBasis
    direct_evidence_count: int
    proxy_evidence_count: int
    direct_evidence_summary: tuple[str, ...]
    proxy_evidence_summary: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityStabilitySummary(PublicDTO):
    status: RankingStabilityStatus
    scenario_count: int
    unstable_scenarios: tuple[RobustnessScenarioCode, ...]
    sensitive_scenarios: tuple[RobustnessScenarioCode, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityAbstention(PublicDTO):
    abstains: bool
    is_provisional: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProductQualityExplanationCheck(PublicDTO):
    code: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class ProductQualityExplanationQuality(PublicDTO):
    status: ExplanationQualityStatus
    rejection_codes: tuple[str, ...]
    checks: tuple[ProductQualityExplanationCheck, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityMarketGoalResult(PublicDTO):
    market_key: str
    market_name: str
    goal: CareerGoal
    rank: int
    score: float
    score_margin: float
    confidence: IntelligenceConfidence
    freshness: IntelligenceFreshness
    sufficiency: EvidenceSufficiency
    direct_proxy_evidence: ProductQualityEvidenceSummary
    top_drivers: tuple[RankingDriver, ...]
    limitations: tuple[str, ...]
    stability: ProductQualityStabilitySummary
    contradictions: tuple[ContradictionFinding, ...]
    abstention: ProductQualityAbstention
    explanation_quality_status: ProductQualityExplanationQuality
    differentiation_findings: tuple[DifferentiationFinding, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityScoreClusterSummary(PublicDTO):
    goal: CareerGoal
    market_count: int
    min_score: float
    max_score: float
    score_spread: float
    minimum_pairwise_gap: float | None
    near_tie_pair_count: int
    status: str


@dataclass(frozen=True, slots=True)
class ProductQualityDominantMetricSummary(PublicDTO):
    goal: CareerGoal
    metric_code: str
    label: str
    market_count: int
    share: float
    dominant: bool


@dataclass(frozen=True, slots=True)
class ProductQualityUnsupportedGoalSummary(PublicDTO):
    goal: CareerGoal
    result_count: int
    reason: str


@dataclass(frozen=True, slots=True)
class ProductQualityResultReference(PublicDTO):
    goal: CareerGoal
    market_key: str
    rank: int
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProductQualityContradictionSummary(PublicDTO):
    goal: CareerGoal
    market_key: str
    status: ContradictionStatus
    codes: tuple[ContradictionCode, ...]
    blocks_recommendation: bool


@dataclass(frozen=True, slots=True)
class ProductQualityPlatformSummary(PublicDTO):
    cross_goal_ranking_similarity: tuple[CrossGoalRankCorrelation, ...]
    score_clustering: tuple[ProductQualityScoreClusterSummary, ...]
    dominant_metrics: tuple[ProductQualityDominantMetricSummary, ...]
    unsupported_goals: tuple[ProductQualityUnsupportedGoalSummary, ...]
    provisional_results: tuple[ProductQualityResultReference, ...]
    abstentions: tuple[ProductQualityResultReference, ...]
    unstable_results: tuple[ProductQualityResultReference, ...]
    contradictions: tuple[ProductQualityContradictionSummary, ...]


@dataclass(frozen=True, slots=True)
class ProductQualityEvaluationReport(PublicDTO):
    schema_version: str
    report_type: str
    artifact_path: str
    as_of: str | None
    markets: tuple[str, ...]
    goals: tuple[CareerGoal, ...]
    expected_result_count: int
    result_count: int
    results: tuple[ProductQualityMarketGoalResult, ...]
    platform_summary: ProductQualityPlatformSummary
    calibration_limitations: tuple[str, ...]
    differentiation_score: float
    differentiation_threshold: float
    differentiation_passed: bool
    differentiation_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketComparisonSide(PublicDTO):
    market_key: str
    market_name: str
    score: float
    confidence: IntelligenceConfidence
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    supporting_metrics: dict[str, int | float | str | None]
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    evidence_basis: EvidenceBasis = EvidenceBasis.NO_QUALIFYING_EVIDENCE
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class MarketComparisonReport(PublicDTO):
    goal: CareerGoal
    market_a: MarketComparisonSide
    market_b: MarketComparisonSide
    outcome: ComparisonOutcome
    winner_market_key: str | None
    explanation: str
    confidence: IntelligenceConfidence
    supporting_metrics: dict[str, int | float | str | None]
    limitations: tuple[str, ...]
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    is_provisional: bool = False
    abstention_reason: str | None = None
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class CareerGoalComparisonReport(PublicDTO):
    goal: CareerGoal
    goal_definition: CareerGoalDefinition
    ranking: ExplainableRankingReport
    recommended_market_key: str | None
    recommendation_summary: str
    confidence: IntelligenceConfidence
    limitations: tuple[str, ...]
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    is_provisional: bool = False
    abstention_reason: str | None = None
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: EvidenceGrounding | None = None


@dataclass(frozen=True, slots=True)
class PlatformMarketIntelligenceReport(PublicDTO):
    market_count: int
    profile_count: int
    supported_goals: tuple[CareerGoalDefinition, ...]
    profiles: tuple[MarketIntelligenceProfile, ...]
    default_ranking: ExplainableRankingReport
    highest_confidence_market: str | None
    public_summary: str
    limitations: tuple[str, ...]


_PUBLIC_SAFE_REDACTION_TEXT = "[redacted]"
_FORBIDDEN_PUBLIC_TEXT_TOKENS = (
    "trust_assessment_id",
    "risk_routing_decision_id",
    "internal_policy_id",
    "reviewer_notes",
    "reviewer_id",
    "reporter_id",
    "reporter_user_id",
    "reporter_session_id",
    "freeform_report",
    "report_reason",
    "raw_risk",
    "raw_internal_risk",
    "raw_provenance",
    "provenance_internal",
    "private_provenance",
    "source_ref_id",
    "fact_source_link_id",
    "stack trace",
    "traceback",
    "/users/",
    "\\users\\",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        if hasattr(value, "as_dict"):
            return value.as_dict()
        return {field.name: _json_safe(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda entry: str(entry[0])):
            safe_key = str(key)
            if _contains_forbidden_public_token(safe_key):
                continue
            result[safe_key] = _json_safe(item)
        return result
    if isinstance(value, str) and _contains_forbidden_public_token(value):
        return _PUBLIC_SAFE_REDACTION_TEXT
    return value


def _contains_forbidden_public_token(value: str) -> bool:
    normalized = value.casefold()
    return any(token in normalized for token in _FORBIDDEN_PUBLIC_TEXT_TOKENS)
