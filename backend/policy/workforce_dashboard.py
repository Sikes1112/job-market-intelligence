"""Convenience functions for Layer 24A workforce dashboard payloads."""

from __future__ import annotations

from backend.policy.schemas import (
    RegionalPolicyMetrics,
    RegionalPolicyProfile,
    WorkforceDashboardPayload,
)


def dashboard_payload_from_profile(
    profile: RegionalPolicyProfile,
    *,
    region_summary,
) -> WorkforceDashboardPayload:
    return WorkforceDashboardPayload(
        region_summary=region_summary,
        core_metrics=RegionalPolicyMetrics(
            opportunity_concentration_score=profile.opportunity_concentration_score,
            early_career_access_score=profile.early_career_access_score,
            internship_pipeline_score=profile.internship_pipeline_score,
            employer_dependency_score=profile.employer_dependency_score,
            sector_diversity_score=profile.sector_diversity_score,
            talent_export_risk_score=profile.talent_export_risk_score,
        ),
        policy_findings=profile.policy_findings,
        warnings=profile.warnings,
        confidence=profile.confidence,
        freshness=profile.freshness,
        source_summary=profile.source_summary,
        public_safe=profile.public_safe,
        public_safety=profile.public_safety,
    )
