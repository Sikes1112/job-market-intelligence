"""Economic development profile assembly for Layer 24B."""

from __future__ import annotations

from backend.policy.company_attraction import build_company_attraction_fits
from backend.policy.confidence import build_strategy_confidence
from backend.policy.metrics import RegionalPolicyInputs
from backend.policy.peer_metros import PeerSelectionResult
from backend.policy.schemas import (
    DiversificationStrategyCandidate,
    EconomicDevelopmentProfile,
    EmployerBaseRiskFinding,
    PolicyProfileReference,
    PolicyWarning,
    RegionalPolicyProfile,
    SectorGapFinding,
)
from backend.shared.confidence import Confidence


def build_economic_development_profile(
    *,
    session,
    inputs: RegionalPolicyInputs,
    policy_profile: RegionalPolicyProfile,
    sector_gap_findings: tuple[SectorGapFinding, ...],
    peer_result: PeerSelectionResult,
) -> EconomicDevelopmentProfile:
    warnings = tuple((*policy_profile.warnings, *peer_result.warnings))
    candidates = build_company_attraction_fits(
        session,
        region_id=policy_profile.region_id,
        sector_gaps=sector_gap_findings,
    )
    risk_findings = _employer_base_risks(policy_profile)
    diversification = _diversification_candidates(
        sector_gap_findings=sector_gap_findings,
        risk_findings=risk_findings,
    )
    evidence_count = (
        len(sector_gap_findings)
        + len(peer_result.comparisons)
        + len(candidates)
        + inputs.hiring_record_count
        + inputs.entry_level_record_count
    )
    confidence = build_strategy_confidence(
        base=policy_profile.confidence,
        evidence_count=evidence_count,
        warnings=warnings,
    )
    return EconomicDevelopmentProfile(
        region_id=policy_profile.region_id,
        region_name=policy_profile.region_name,
        analysis_window=policy_profile.analysis_window,
        regional_policy_profile=_policy_reference(policy_profile),
        sector_gap_findings=sector_gap_findings,
        employer_base_risk_findings=risk_findings,
        peer_metro_comparisons=peer_result.comparisons,
        company_attraction_candidates=candidates,
        diversification_recommendations=diversification,
        warnings=warnings,
        confidence=confidence,
        freshness=policy_profile.freshness,
        source_summary=policy_profile.source_summary,
        limitations=(
            "Economic development outputs are strategy intelligence, not prescriptions.",
            "Company attraction fits are candidates for analysis, not expansion predictions.",
            "Further local validation is recommended before public strategy decisions.",
        ),
        public_safe=True,
        public_safety=policy_profile.public_safety,
    )


def economic_development_warning(
    *,
    code: str,
    severity: str,
    message: str,
    interpretation: str,
) -> PolicyWarning:
    return PolicyWarning(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        public_interpretation=interpretation,
    )


def _policy_reference(profile: RegionalPolicyProfile) -> PolicyProfileReference:
    return PolicyProfileReference(
        region_id=profile.region_id,
        region_name=profile.region_name,
        confidence=profile.confidence,
        key_metric_bands={
            "opportunity_concentration": profile.opportunity_concentration_score.band,
            "early_career_access": profile.early_career_access_score.band,
            "internship_pipeline": profile.internship_pipeline_score.band,
            "employer_dependency": profile.employer_dependency_score.band,
            "sector_diversity": profile.sector_diversity_score.band,
            "talent_export_risk": profile.talent_export_risk_score.band,
        },
        warning_codes=tuple(warning.code for warning in profile.warnings),
    )


def _employer_base_risks(
    profile: RegionalPolicyProfile,
) -> tuple[EmployerBaseRiskFinding, ...]:
    findings: list[EmployerBaseRiskFinding] = []
    dependency = profile.employer_dependency_score.score
    concentration = profile.opportunity_concentration_score.score
    diversity = profile.sector_diversity_score.score
    internship = profile.internship_pipeline_score.score
    if dependency is not None and dependency >= 0.65:
        findings.append(
            _risk(
                "employer_dependency",
                "high" if dependency >= 0.80 else "medium",
                (
                    "Available signals suggest the regional employer base may be "
                    "sensitive to a concentrated set of employers."
                ),
                "Compare adjacent employer categories that could broaden opportunity access.",
                profile.confidence.level,
                ("metric:employer_dependency", "regional_policy_profile"),
            )
        )
    if concentration is not None and concentration >= 0.65:
        findings.append(
            _risk(
                "opportunity_concentration",
                "high" if concentration >= 0.80 else "medium",
                (
                    "Observed hiring signals are concentrated across a smaller employer set."
                ),
                "Use concentration analysis as an input to employer-base diversification review.",
                profile.confidence.level,
                ("metric:opportunity_concentration", "regional_policy_profile"),
            )
        )
    if diversity is not None and diversity <= 0.40:
        findings.append(
            _risk(
                "sector_concentration",
                "medium",
                (
                    "The demonstrated employer base shows limited sector diversity in "
                    "available data."
                ),
                "Review adjacent sectors as candidates for further local validation.",
                profile.confidence.level,
                ("metric:sector_diversity", "regional_policy_profile"),
            )
        )
    if internship is not None and internship <= 0.40:
        findings.append(
            _risk(
                "early_career_employer_diversity",
                "medium",
                (
                    "Internship access appears concentrated or limited across the "
                    "demonstrated employer base."
                ),
                "Map which employer types offer student-facing pathways before strategy action.",
                profile.confidence.level,
                (
                    "metric:internship_pipeline",
                    "metric:early_career_access",
                    "regional_policy_profile",
                ),
            )
        )
    return tuple(findings)


def _risk(
    risk_type: str,
    severity: str,
    interpretation: str,
    strategy: str,
    confidence: Confidence,
    evidence_references: tuple[str, ...],
) -> EmployerBaseRiskFinding:
    return EmployerBaseRiskFinding(
        risk_type=risk_type,
        severity=severity,  # type: ignore[arg-type]
        interpretation=interpretation,
        evidence_references=evidence_references,
        strategy_candidate=strategy,
        confidence=confidence,
        limitations=(
            "Risk findings are not economic forecasts.",
            "Further local validation is recommended.",
        ),
    )


def _diversification_candidates(
    *,
    sector_gap_findings: tuple[SectorGapFinding, ...],
    risk_findings: tuple[EmployerBaseRiskFinding, ...],
) -> tuple[DiversificationStrategyCandidate, ...]:
    candidates: list[DiversificationStrategyCandidate] = []
    for finding in sector_gap_findings[:5]:
        candidates.append(
            DiversificationStrategyCandidate(
                candidate_type="sector_gap_validation",
                title=f"{finding.sector.title()} gap validation",
                rationale=(
                    "This sector may benefit from local validation because available "
                    "signals show a strategy-relevant gap."
                ),
                evidence_references=finding.evidence_references,
                confidence=finding.confidence,
                limitations=finding.limitations,
            )
        )
    if risk_findings:
        candidates.append(
            DiversificationStrategyCandidate(
                candidate_type="employer_base_diversification",
                title="Employer-base diversification review",
                rationale=(
                    "Available employer-base risk findings suggest diversification "
                    "analysis may be useful."
                ),
                evidence_references=("regional_policy_profile", "layer_24a_metrics"),
                confidence=risk_findings[0].confidence,
                limitations=(
                    "This is a candidate for review, not a prescriptive policy action.",
                ),
            )
        )
    return tuple(candidates)
