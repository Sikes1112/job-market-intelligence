"""Governance invariants for Layer 23A opportunity infrastructure."""

from __future__ import annotations

from typing import Protocol

OPPORTUNITY_RECORDS_ARE_ADDITIVE_ONLY = True
DEFAULT_RANKING_INFLUENCE_ALLOWED = False
OPPORTUNITY_ROUTING_MUTATES_OBJECTIVE_AUTHORITY = False
ROUTE_FIRST_OPPORTUNITY_ROUTING_ENABLED = True

OBJECTIVE_SCORING_AUTHORITIES = frozenset(
    {
        "region_market_scores",
        "market_snapshots",
        "company_region_snapshots",
        "sector_region_snapshots",
        "market_score_history",
        "predictive_signals",
        "market_indices",
        "market_index_versions",
        "market_index_scores",
        "benchmark_reports",
        "benchmark_report_rankings",
        "personalized_recommendation_snapshots",
        "output_metadata",
    }
)

OPPORTUNITY_LAYER_NON_GOALS = frozenset(
    {
        "generic_job_search",
        "live_scraping",
        "application_tracking",
        "referral_workflows",
        "employer_payments",
        "sponsored_ranking",
        "objective_score_mutation",
        "generic_job_listing_feed",
    }
)


class _RankingInfluenceMetadata(Protocol):
    ranking_influence_allowed: bool


class OpportunityGovernanceError(ValueError):
    pass


def assert_ranking_influence_disabled(metadata: _RankingInfluenceMetadata) -> None:
    if metadata.ranking_influence_allowed:
        raise OpportunityGovernanceError(
            "Layer 23A opportunities cannot influence objective rankings or scores"
        )


def opportunity_governance_summary() -> dict[str, object]:
    return {
        "records_additive_only": OPPORTUNITY_RECORDS_ARE_ADDITIVE_ONLY,
        "ranking_influence_allowed_default": DEFAULT_RANKING_INFLUENCE_ALLOWED,
        "route_first_routing_enabled": ROUTE_FIRST_OPPORTUNITY_ROUTING_ENABLED,
        "routing_mutates_objective_authority": (
            OPPORTUNITY_ROUTING_MUTATES_OBJECTIVE_AUTHORITY
        ),
        "objective_scoring_authorities": sorted(OBJECTIVE_SCORING_AUTHORITIES),
        "non_goals": sorted(OPPORTUNITY_LAYER_NON_GOALS),
    }
