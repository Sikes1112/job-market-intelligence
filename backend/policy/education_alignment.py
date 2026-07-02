"""Education-to-workforce alignment for Layer 24B."""

from __future__ import annotations

from backend.policy.metrics import bounded, public_metric_inputs
from backend.policy.schemas import (
    EducationWorkforceAlignmentProfile,
    PolicyMetric,
    PolicyWarning,
    ProgramDemandAlignment,
    RegionalPolicyProfile,
    SectorGapFinding,
    band_for_score,
)
from backend.policy.sector_gaps import SectorDemandSnapshot, sector_metric


def build_program_alignments(
    *,
    sector_snapshots: tuple[SectorDemandSnapshot, ...],
    program_definitions: tuple,
    policy_profile: RegionalPolicyProfile,
) -> tuple[ProgramDemandAlignment, ...]:
    by_sector = {snapshot.sector: snapshot for snapshot in sector_snapshots}
    alignments: list[ProgramDemandAlignment] = []
    for program in program_definitions:
        snapshots = tuple(
            by_sector[sector]
            for sector in program.sectors
            if sector in by_sector
        )
        demand_score = _avg(tuple(snapshot.demand_score for snapshot in snapshots))
        internship_score = _avg(
            tuple(snapshot.internship_pipeline_score for snapshot in snapshots)
        )
        access_score = _avg(
            tuple(snapshot.early_career_access_score for snapshot in snapshots)
        )
        alignment_score = _avg(
            tuple(
                value
                for value in (demand_score, internship_score, access_score)
                if value is not None
            )
        )
        alignments.append(
            ProgramDemandAlignment(
                program_area=program.program_name,
                nearby_employer_demand=sector_metric(
                    metric_id=f"program_demand_{_key(program.program_name)}",
                    label=f"{program.program_name} nearby employer demand",
                    score=demand_score,
                    interpretation_label=_label(demand_score, "employer demand"),
                    explainable_inputs={
                        "matched_sector_count": len(snapshots),
                        "program_sector_count": len(program.sectors),
                    },
                    limitations=(
                        (
                            "Uses program-area sector mappings from existing "
                            "institution planning contracts."
                        ),
                        "Does not infer outcomes for individual students.",
                    ),
                ),
                internship_pipeline_strength=sector_metric(
                    metric_id=f"program_internship_{_key(program.program_name)}",
                    label=f"{program.program_name} internship pipeline strength",
                    score=internship_score,
                    interpretation_label=_label(internship_score, "internship pipeline"),
                    explainable_inputs={
                        "matched_sector_count": len(snapshots),
                    },
                    limitations=(
                        "Internship alignment is based on aggregate employer pathway signals.",
                    ),
                ),
                early_career_access=sector_metric(
                    metric_id=f"program_access_{_key(program.program_name)}",
                    label=f"{program.program_name} early-career access",
                    score=access_score,
                    interpretation_label=_label(access_score, "early-career access"),
                    explainable_inputs={
                        "matched_sector_count": len(snapshots),
                    },
                    limitations=(
                        "Early-career access is a market signal, not a program-quality rating.",
                    ),
                ),
                alignment_score=alignment_score,
                alignment_band=band_for_score(alignment_score),
                finding=_finding(program.program_name, alignment_score),
                confidence=policy_profile.confidence.level,
                limitations=(
                    "Program alignment is aggregate-only.",
                    "No individual student outcomes are inferred.",
                    "Further local validation is recommended.",
                ),
            )
        )
    return tuple(sorted(alignments, key=lambda item: item.program_area))


def education_alignment_warnings(
    *,
    institution_count: int,
    program_alignment_count: int,
) -> tuple[PolicyWarning, ...]:
    warnings: list[PolicyWarning] = []
    if institution_count == 0:
        warnings.append(
            PolicyWarning(
                code="no_institution_pipeline_records",
                severity="medium",
                message="No active institution pipeline records were available for mapping.",
                public_interpretation=(
                    "Education alignment should be read from program-area demand only "
                    "until institution pipeline records are connected."
                ),
            )
        )
    if program_alignment_count == 0:
        warnings.append(
            PolicyWarning(
                code="no_program_alignment_records",
                severity="high",
                message="No program-area mappings could be compared with local demand.",
                public_interpretation=(
                    "Education-to-workforce alignment is not supported for this region "
                    "from available structured data."
                ),
            )
        )
    warnings.append(
        PolicyWarning(
            code="aggregate_only_education_alignment",
            severity="info",
            message="Education alignment is aggregate-only.",
            public_interpretation=(
                "No student-level records, student identities, or individual outcomes "
                "are used in this payload."
            ),
        )
    )
    return tuple(warnings)


def local_absorption_metric(
    alignments: tuple[ProgramDemandAlignment, ...],
) -> PolicyMetric:
    score = _avg(
        tuple(
            alignment.alignment_score
            for alignment in alignments
            if alignment.alignment_score is not None
        )
    )
    return PolicyMetric(
        metric_id="local_employer_absorption",
        label="Local employer absorption",
        score=score,
        band=band_for_score(score),
        polarity="higher_is_better",
        interpretation_label=_label(score, "local employer absorption"),
        explainable_inputs=public_metric_inputs(program_alignment_count=len(alignments)),
        limitations=(
            "This is an aggregate market-alignment signal, not a placement outcome.",
            "Institution-specific program catalogs are not connected in this layer.",
        ),
        warning_codes=(),
    )


def student_interest_market_fit_metric() -> PolicyMetric:
    return PolicyMetric(
        metric_id="student_interest_market_fit",
        label="Student interest market fit",
        score=None,
        band="unknown",
        polarity="contextual",
        interpretation_label="Student interest market fit unavailable",
        explainable_inputs=public_metric_inputs(student_interest_inputs_used=False),
        limitations=(
            "Student-owned preference records are not used in this public policy payload.",
            "Aggregate institution dashboards remain separate protected surfaces.",
        ),
        warning_codes=("student_interest_not_used_public_policy_payload",),
    )


def internship_alignment_gaps(
    sector_gap_findings: tuple[SectorGapFinding, ...],
) -> tuple[SectorGapFinding, ...]:
    return tuple(
        finding
        for finding in sector_gap_findings
        if finding.gap_type
        in {
            "internship_pathway_gap",
            "early_career_access_gap",
            "full_time_without_internship_pathway",
            "peer_relative_sector_gap",
        }
    )


def build_education_profile(
    *,
    policy_profile: RegionalPolicyProfile,
    institution_pipelines,
    program_alignments: tuple[ProgramDemandAlignment, ...],
    sector_gap_findings: tuple[SectorGapFinding, ...],
    warnings: tuple[PolicyWarning, ...],
    confidence,
) -> EducationWorkforceAlignmentProfile:
    local_absorption = local_absorption_metric(program_alignments)
    return EducationWorkforceAlignmentProfile(
        region_id=policy_profile.region_id,
        region_name=policy_profile.region_name,
        analysis_window=policy_profile.analysis_window,
        institution_pipeline_summaries=tuple(institution_pipelines),
        program_alignment_findings=program_alignments,
        internship_alignment_gaps=internship_alignment_gaps(sector_gap_findings),
        local_employer_absorption_score=local_absorption,
        talent_export_pressure_score=policy_profile.talent_export_risk_score,
        student_interest_market_fit=student_interest_market_fit_metric(),
        warnings=tuple((*policy_profile.warnings, *warnings)),
        confidence=confidence,
        freshness=policy_profile.freshness,
        source_summary=policy_profile.source_summary,
        limitations=(
            "Education alignment is aggregate-only and public-safe.",
            "Program mappings use existing program-area contracts, not a full curriculum catalog.",
            "No individual student outcomes are inferred.",
        ),
        public_safe=True,
        public_safety=policy_profile.public_safety,
    )


def _avg(values: tuple[float | None, ...]) -> float | None:
    observed = tuple(value for value in values if value is not None)
    if not observed:
        return None
    return bounded(sum(observed) / len(observed))


def _label(score: float | None, subject: str) -> str:
    if score is None:
        return f"{subject.title()} unknown"
    if score >= 0.65:
        return f"Strong {subject} signal"
    if score >= 0.40:
        return f"Moderate {subject} signal"
    return f"Limited {subject} signal"


def _finding(program_name: str, score: float | None) -> str:
    if score is None:
        return (
            f"{program_name} cannot be aligned from available local demand signals. "
            "Further local validation is recommended."
        )
    if score >= 0.65:
        return (
            f"{program_name} appears directionally aligned with available local "
            "employer and early-career signals."
        )
    if score >= 0.40:
        return (
            f"{program_name} has mixed alignment with available local employer "
            "and internship signals."
        )
    return (
        f"{program_name} appears locally under-absorbed based on available demand "
        "signals."
    )


def _key(value: str) -> str:
    return value.casefold().replace(" ", "_").replace("/", "_")
