"""Read-only Layer 24A policy intelligence service."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.metadata import aggregate_freshness_expires_at
from backend.policy.confidence import (
    PolicyConfidenceInput,
    build_policy_confidence,
    build_strategy_confidence,
)
from backend.policy.economic_development import build_economic_development_profile
from backend.policy.education_alignment import (
    build_education_profile,
    build_program_alignments,
    education_alignment_warnings,
)
from backend.policy.institution_mapping import (
    institution_pipeline_summaries,
    program_definitions,
)
from backend.policy.metrics import RegionalPolicyInputs, source_categories_for_inputs
from backend.policy.peer_metros import (
    build_peer_metro_comparisons,
    peer_comparison_profile_from_result,
)
from backend.policy.regional_inequality import build_regional_policy_metrics
from backend.policy.schemas import (
    EarlyCareerAccessPayload,
    EconomicDevelopmentProfile,
    EducationWorkforceAlignmentProfile,
    EmployerConcentrationPayload,
    PeerComparisonProfile,
    PolicyAnalysisWindow,
    PolicyFinding,
    PolicyFreshnessMetadata,
    PolicyMetric,
    PolicyPublicSafetyMetadata,
    PolicyRegionSummary,
    PolicySourceSummary,
    RegionalPolicyMetrics,
    RegionalPolicyProfile,
    WorkforceDashboardPayload,
)
from backend.policy.sector_gaps import (
    build_sector_gap_findings,
    sector_demand_snapshots,
)
from backend.policy.warnings import build_policy_warnings
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus, evaluate_freshness


class PolicyRegionNotFound(Exception):
    """Raised when a requested region does not exist."""


class PolicyIntelligenceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def build_regional_policy_profile(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> RegionalPolicyProfile:
        now = _ensure_aware(now or datetime.now(UTC))
        inputs = self._load_inputs(region_id)
        metrics = build_regional_policy_metrics(inputs)
        metric_tuple = _metric_tuple(metrics)
        freshness_expires_at = aggregate_freshness_expires_at(
            *(row.freshness_expires_at for row in inputs.hiring_rows),
            *(row.freshness_expires_at for row in inputs.entry_level_rows),
        )
        freshness_status = _freshness_status(freshness_expires_at, now=now)
        source_count = _source_count(
            *inputs.presence_rows,
            *inputs.hiring_rows,
            *inputs.entry_level_rows,
        )
        source_summary = _source_summary(inputs, source_count=source_count)
        warnings = build_policy_warnings(
            inputs=inputs,
            metrics=metric_tuple,
            freshness_status=freshness_status,
            source_count=source_count,
        )
        confidence = build_policy_confidence(
            PolicyConfidenceInput(
                present_company_count=inputs.present_company_count,
                hiring_record_count=inputs.hiring_record_count,
                entry_level_record_count=inputs.entry_level_record_count,
                source_count=source_count,
                freshness_status=freshness_status,
                metrics=metric_tuple,
                warnings=warnings,
            )
        )
        freshness = PolicyFreshnessMetadata(
            generated_at=now,
            freshness_status=freshness_status,
            freshness_expires_at=freshness_expires_at,
            stale=freshness_status is FreshnessStatus.STALE,
            notes=_freshness_notes(freshness_status),
        )
        findings = _build_findings(
            region_id=inputs.region.region_id,
            region_name=inputs.region.display_name,
            metrics=metrics,
            confidence=confidence.level,
        )
        safety = _public_safety()

        return RegionalPolicyProfile(
            region_id=inputs.region.region_id,
            region_name=inputs.region.display_name,
            analysis_window=PolicyAnalysisWindow(
                generated_at=now,
                freshness_expires_at=freshness_expires_at,
            ),
            opportunity_concentration_score=metrics.opportunity_concentration_score,
            early_career_access_score=metrics.early_career_access_score,
            internship_pipeline_score=metrics.internship_pipeline_score,
            employer_dependency_score=metrics.employer_dependency_score,
            sector_diversity_score=metrics.sector_diversity_score,
            talent_export_risk_score=metrics.talent_export_risk_score,
            policy_findings=findings,
            warnings=warnings,
            freshness=freshness,
            confidence=confidence,
            source_summary=source_summary,
            public_safe=True,
            public_safety=safety,
        )

    def build_workforce_dashboard(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> WorkforceDashboardPayload:
        profile = self.build_regional_policy_profile(region_id, now=now)
        return WorkforceDashboardPayload(
            region_summary=self._region_summary(profile.region_id),
            core_metrics=_metrics_from_profile(profile),
            policy_findings=profile.policy_findings,
            warnings=profile.warnings,
            confidence=profile.confidence,
            freshness=profile.freshness,
            source_summary=profile.source_summary,
            public_safe=True,
            public_safety=profile.public_safety,
        )

    def build_early_career_access(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> EarlyCareerAccessPayload:
        profile = self.build_regional_policy_profile(region_id, now=now)
        relevant = tuple(
            finding
            for finding in profile.policy_findings
            if finding.finding_type
            in {"early_career_access_gap", "internship_pipeline_weakness"}
        )
        return EarlyCareerAccessPayload(
            region_summary=self._region_summary(profile.region_id),
            early_career_access_score=profile.early_career_access_score,
            internship_pipeline_score=profile.internship_pipeline_score,
            policy_findings=relevant,
            warnings=profile.warnings,
            confidence=profile.confidence,
            freshness=profile.freshness,
            source_summary=profile.source_summary,
            public_safe=True,
            public_safety=profile.public_safety,
        )

    def build_employer_concentration(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> EmployerConcentrationPayload:
        profile = self.build_regional_policy_profile(region_id, now=now)
        relevant = tuple(
            finding
            for finding in profile.policy_findings
            if finding.finding_type
            in {"opportunity_concentration", "employer_dependency", "sector_gap"}
        )
        return EmployerConcentrationPayload(
            region_summary=self._region_summary(profile.region_id),
            opportunity_concentration_score=profile.opportunity_concentration_score,
            employer_dependency_score=profile.employer_dependency_score,
            sector_diversity_score=profile.sector_diversity_score,
            policy_findings=relevant,
            warnings=profile.warnings,
            confidence=profile.confidence,
            freshness=profile.freshness,
            source_summary=profile.source_summary,
            public_safe=True,
            public_safety=profile.public_safety,
        )

    def build_economic_development_profile(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> EconomicDevelopmentProfile:
        profile = self.build_regional_policy_profile(region_id, now=now)
        inputs = self._load_inputs(region_id)
        peer_result = build_peer_metro_comparisons(self._session, target_profile=profile)
        peer_sector_demand = self._peer_sector_demand(peer_result.comparisons)
        sector_findings = build_sector_gap_findings(
            inputs=inputs,
            profile=profile,
            peer_sector_demand=peer_sector_demand,
        )
        return build_economic_development_profile(
            session=self._session,
            inputs=inputs,
            policy_profile=profile,
            sector_gap_findings=sector_findings,
            peer_result=peer_result,
        )

    def build_peer_comparison_profile(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> PeerComparisonProfile:
        profile = self.build_regional_policy_profile(region_id, now=now)
        result = build_peer_metro_comparisons(self._session, target_profile=profile)
        return peer_comparison_profile_from_result(
            target_profile=profile,
            result=result,
        )

    def build_education_alignment_profile(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
    ) -> EducationWorkforceAlignmentProfile:
        profile = self.build_regional_policy_profile(region_id, now=now)
        inputs = self._load_inputs(region_id)
        snapshots = sector_demand_snapshots(inputs)
        sector_findings = build_sector_gap_findings(inputs=inputs, profile=profile)
        institutions = institution_pipeline_summaries(
            self._session,
            region_id=region_id,
            sector_snapshots=snapshots,
        )
        alignments = build_program_alignments(
            sector_snapshots=snapshots,
            program_definitions=program_definitions(),
            policy_profile=profile,
        )
        warnings = education_alignment_warnings(
            institution_count=len(institutions),
            program_alignment_count=len(alignments),
        )
        confidence = build_strategy_confidence(
            base=profile.confidence,
            evidence_count=len(institutions) + len(alignments) + len(snapshots),
            warnings=tuple((*profile.warnings, *warnings)),
        )
        return build_education_profile(
            policy_profile=profile,
            institution_pipelines=institutions,
            program_alignments=alignments,
            sector_gap_findings=sector_findings,
            warnings=warnings,
            confidence=confidence,
        )

    def _load_inputs(self, region_id: str) -> RegionalPolicyInputs:
        region = self._session.get(Region, region_id)
        if region is None:
            raise PolicyRegionNotFound(region_id)
        presence_rows = tuple(
            self._session.execute(
                select(CompanyRegionPresence)
                .where(CompanyRegionPresence.region_id == region_id)
                .order_by(
                    CompanyRegionPresence.company_id,
                    CompanyRegionPresence.presence_id,
                )
            ).scalars()
        )
        eligible_presence_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_presence",
            [row.presence_id for row in presence_rows],
        )
        presence_rows = tuple(
            row for row in presence_rows if row.presence_id in eligible_presence_ids
        )
        present_company_ids = tuple(
            row.company_id for row in presence_rows if row.presence_status == "present"
        )
        eligible_company_ids = ranking_eligible_fact_ids(
            self._session,
            "company",
            present_company_ids,
        )
        present_company_ids = tuple(
            company_id
            for company_id in present_company_ids
            if company_id in eligible_company_ids
        )
        present_companies = self._present_companies(present_company_ids)
        hiring_rows = tuple(
            self._session.execute(
                select(CompanyRegionHiring)
                .where(CompanyRegionHiring.region_id == region_id)
                .order_by(CompanyRegionHiring.company_id, CompanyRegionHiring.hiring_id)
            ).scalars()
        )
        eligible_hiring_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_hiring",
            [row.hiring_id for row in hiring_rows],
        )
        hiring_rows = tuple(row for row in hiring_rows if row.hiring_id in eligible_hiring_ids)
        entry_level_rows = tuple(
            self._session.execute(
                select(CompanyRegionEntryLevel)
                .where(CompanyRegionEntryLevel.region_id == region_id)
                .order_by(
                    CompanyRegionEntryLevel.company_id,
                    CompanyRegionEntryLevel.entry_level_id,
                )
            ).scalars()
        )
        eligible_entry_level_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_entry_level",
            [row.entry_level_id for row in entry_level_rows],
        )
        entry_level_rows = tuple(
            row for row in entry_level_rows if row.entry_level_id in eligible_entry_level_ids
        )
        score = self._session.execute(
            select(RegionMarketScore)
            .where(RegionMarketScore.region_id == region_id)
            .order_by(RegionMarketScore.region_score_id)
        ).scalars().first()
        return RegionalPolicyInputs(
            region=region,
            present_companies=present_companies,
            presence_rows=presence_rows,
            hiring_rows=hiring_rows,
            entry_level_rows=entry_level_rows,
            region_market_score=score,
        )

    def _present_companies(self, company_ids: tuple[str, ...]) -> tuple[Company, ...]:
        if not company_ids:
            return ()
        rows = self._session.execute(
            select(Company).where(Company.company_id.in_(company_ids)).order_by(Company.company_id)
        ).scalars()
        return tuple(rows)

    def _region_summary(self, region_id: str) -> PolicyRegionSummary:
        inputs = self._load_inputs(region_id)
        return PolicyRegionSummary(
            region_id=inputs.region.region_id,
            region_name=inputs.region.display_name,
            region_type=inputs.region.region_type,
            present_company_count=inputs.present_company_count,
            hiring_record_count=inputs.hiring_record_count,
            entry_level_record_count=inputs.entry_level_record_count,
            score_available=inputs.region_market_score is not None,
            normalization_basis=(
                "demonstrated_present_companies"
                if inputs.present_company_count > 0
                else "missing_present_company_denominator"
            ),
        )

    def _peer_sector_demand(self, peer_comparisons) -> dict[str, float]:
        totals: dict[str, list[float]] = {}
        for comparison in peer_comparisons:
            try:
                inputs = self._load_inputs(comparison.peer_region_id)
            except PolicyRegionNotFound:
                continue
            for snapshot in sector_demand_snapshots(inputs):
                totals.setdefault(snapshot.sector, []).append(snapshot.demand_score)
        return {
            sector: round(sum(values) / len(values), 4)
            for sector, values in sorted(totals.items())
            if values
        }


def _metrics_from_profile(profile: RegionalPolicyProfile) -> RegionalPolicyMetrics:
    return RegionalPolicyMetrics(
        opportunity_concentration_score=profile.opportunity_concentration_score,
        early_career_access_score=profile.early_career_access_score,
        internship_pipeline_score=profile.internship_pipeline_score,
        employer_dependency_score=profile.employer_dependency_score,
        sector_diversity_score=profile.sector_diversity_score,
        talent_export_risk_score=profile.talent_export_risk_score,
    )


def _metric_tuple(metrics: RegionalPolicyMetrics) -> tuple[PolicyMetric, ...]:
    return (
        metrics.opportunity_concentration_score,
        metrics.early_career_access_score,
        metrics.internship_pipeline_score,
        metrics.employer_dependency_score,
        metrics.sector_diversity_score,
        metrics.talent_export_risk_score,
    )


def _source_summary(
    inputs: RegionalPolicyInputs,
    *,
    source_count: int,
) -> PolicySourceSummary:
    categories = source_categories_for_inputs(inputs)
    evidence_summary = [
        f"{inputs.present_company_count} demonstrated present employers",
        f"{inputs.hiring_record_count} employer hiring signal rows",
        f"{inputs.entry_level_record_count} employer early-career signal rows",
    ]
    if inputs.region_market_score is not None:
        evidence_summary.append("canonical region market score available")
    return PolicySourceSummary(
        data_basis="canonical_market_truth" if categories else "unknown",
        source_count=source_count,
        source_categories=categories,
        evidence_summary=tuple(evidence_summary),
    )


def _freshness_status(
    freshness_expires_at: datetime | None,
    *,
    now: datetime,
) -> FreshnessStatus:
    if freshness_expires_at is None:
        return FreshnessStatus.UNKNOWN
    return evaluate_freshness(_ensure_aware(freshness_expires_at), now=now)


def _freshness_notes(status: FreshnessStatus) -> tuple[str, ...]:
    if status is FreshnessStatus.FRESH:
        return ("Input freshness windows are currently fresh.",)
    if status is FreshnessStatus.STALE:
        return ("One or more input freshness windows are stale.",)
    return ("Freshness windows are unavailable for one or more policy inputs.",)


def _source_count(*rows: object) -> int:
    refs: set[str] = set()
    for row in rows:
        refs.update(_source_ref_tokens(getattr(row, "source_refs", None)))
    return len(refs)


def _source_ref_tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return _mapping_ref_tokens(value)
    if isinstance(value, list | tuple):
        tokens: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                tokens.extend(_mapping_ref_tokens(item))
        return tuple(tokens)
    return ()


def _mapping_ref_tokens(value: Mapping[str, Any]) -> tuple[str, ...]:
    tokens: list[str] = []
    for key in ("fact_source_link_id", "source_id", "source_ref"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            tokens.append(item.strip())
    return tuple(tokens)


def _public_safety() -> PolicyPublicSafetyMetadata:
    return PolicyPublicSafetyMetadata(
        public_safe=True,
        redacted_internal_fields=(
            "raw source references",
            "source version bundles",
            "reviewer identities",
            "review notes",
            "submitter contact fields",
            "raw partner submission JSON",
            "student-level records",
        ),
        student_level_data_exposed=False,
        partner_submission_internals_exposed=False,
        private_review_fields_exposed=False,
    )


def _build_findings(
    *,
    region_id: str,
    region_name: str,
    metrics: RegionalPolicyMetrics,
    confidence: Confidence,
) -> tuple[PolicyFinding, ...]:
    findings: list[PolicyFinding] = []
    concentration = metrics.opportunity_concentration_score
    if concentration.score is not None and concentration.score >= 0.65:
        findings.append(
            _finding(
                region_id,
                finding_type="opportunity_concentration",
                severity="high" if concentration.score >= 0.8 else "medium",
                title="Opportunity concentration signal",
                summary=(
                    f"Available data suggests {region_name} has a concentrated "
                    "distribution of observed employer hiring signals."
                ),
                evidence=("metric:opportunity_concentration", "company_region_hiring"),
                interpretation=(
                    "This may indicate that regional opportunity access is sensitive "
                    "to a smaller set of employers. Further local validation is recommended."
                ),
                actions=(
                    "Validate employer concentration with local workforce partners.",
                    "Review whether early-career pathways span multiple employer types.",
                ),
                confidence=confidence,
            )
        )
    dependency = metrics.employer_dependency_score
    if dependency.score is not None and dependency.score >= 0.65:
        findings.append(
            _finding(
                region_id,
                finding_type="employer_dependency",
                severity="high" if dependency.score >= 0.8 else "medium",
                title="Employer dependency signal",
                summary=(
                    "This region shows signs of dependency on a concentrated "
                    "employer base in the available aggregate signals."
                ),
                evidence=("metric:employer_dependency", "company_region_entry_level"),
                interpretation=(
                    "This should be read as concentration risk, not as a conclusion "
                    "about employer behavior or local policy quality."
                ),
                actions=(
                    "Compare employer pathway coverage across sectors.",
                    "Use local validation before prioritizing workforce interventions.",
                ),
                confidence=confidence,
            )
        )
    early = metrics.early_career_access_score
    if early.score is not None and early.score <= 0.40:
        findings.append(
            _finding(
                region_id,
                finding_type="early_career_access_gap",
                severity="medium",
                title="Early-career access gap signal",
                summary=(
                    f"Available data suggests {region_name} has limited early-career "
                    "access relative to its demonstrated employer base."
                ),
                evidence=("metric:early_career_access", "company_region_entry_level"),
                interpretation=(
                    "This may indicate that entry-level access is weaker than general "
                    "employer presence. Further local validation is recommended."
                ),
                actions=(
                    "Review internship, co-op, and new-graduate pathways with education partners.",
                    "Collect additional employer-level early-career evidence.",
                ),
                confidence=confidence,
            )
        )
    pipeline = metrics.internship_pipeline_score
    if pipeline.score is not None and pipeline.score <= 0.40:
        findings.append(
            _finding(
                region_id,
                finding_type="internship_pipeline_weakness",
                severity="medium",
                title="Internship pipeline weakness signal",
                summary=(
                    "Available data suggests internship and co-op pathways are limited "
                    "relative to the demonstrated employer denominator."
                ),
                evidence=("metric:internship_pipeline", "company_region_entry_level"),
                interpretation=(
                    "This may indicate weaker student-to-workforce pipeline visibility, "
                    "not a confirmed lack of opportunity."
                ),
                actions=(
                    "Validate employer internship coverage with career centers.",
                    "Separate missing data from observed absence before public reporting.",
                ),
                confidence=confidence,
            )
        )
    diversity = metrics.sector_diversity_score
    if diversity.score is not None and diversity.score <= 0.40:
        findings.append(
            _finding(
                region_id,
                finding_type="sector_gap",
                severity="low",
                title="Sector diversity gap signal",
                summary=(
                    "Available data suggests the demonstrated employer base is "
                    "concentrated across a limited set of primary sectors."
                ),
                evidence=("metric:sector_diversity", "company_classification"),
                interpretation=(
                    "This may indicate narrower sector coverage in the current data. "
                    "It should not be read as a complete sector inventory."
                ),
                actions=(
                    "Review sector labeling completeness before drawing sector conclusions.",
                ),
                confidence=confidence,
            )
        )
    export = metrics.talent_export_risk_score
    if export.score is not None and export.score >= 0.60:
        findings.append(
            _finding(
                region_id,
                finding_type="talent_export_risk",
                severity="medium",
                title="Talent export risk signal",
                summary=(
                    f"Available data suggests {region_name} may have local pathway "
                    "weakness that could affect early-career retention."
                ),
                evidence=("metric:talent_export_risk", "metric:early_career_access"),
                interpretation=(
                    "This is a proxy signal based on access and pipeline weakness. "
                    "Further local validation is recommended."
                ),
                actions=(
                    "Validate student pathway needs with education and workforce partners.",
                    "Use observed employer pathway data before making public claims.",
                ),
                confidence=confidence,
            )
        )
    if not findings:
        findings.append(
            _finding(
                region_id,
                finding_type="data_coverage_context",
                severity="info",
                title="Policy interpretation context",
                summary=(
                    "Available data does not produce a high-severity policy finding "
                    "from the Layer 24A metrics."
                ),
                evidence=("metric:layer_24a_core_metrics",),
                interpretation=(
                    "The region should still be interpreted with the attached "
                    "freshness, confidence, and coverage warnings."
                ),
                actions=("Review warnings before public or institutional use.",),
                confidence=confidence,
            )
        )
    return tuple(findings)


def _finding(
    region_id: str,
    *,
    finding_type: str,
    severity: str,
    title: str,
    summary: str,
    evidence: tuple[str, ...],
    interpretation: str,
    actions: tuple[str, ...],
    confidence: Confidence,
) -> PolicyFinding:
    return PolicyFinding(
        finding_id=f"{region_id}:{finding_type}",
        finding_type=finding_type,
        severity=severity,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        evidence_references=evidence,
        recommended_interpretation=interpretation,
        recommended_actions=actions,
        confidence=confidence,
        limitations=(
            "Finding is evidence-informed and directional.",
            "Further local validation is recommended before policy decisions.",
        ),
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
