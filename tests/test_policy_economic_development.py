from __future__ import annotations

from sqlalchemy.orm import Session

from backend.policy.service import PolicyIntelligenceService
from tests.policy_strategy_helpers import (
    NOW,
    seed_company_region_signal,
    seed_region,
)

_SAFE_STRATEGY_METRIC_REFS = {
    "metric:employer_dependency",
    "metric:opportunity_concentration",
    "metric:sector_diversity",
    "metric:internship_pipeline",
    "metric:early_career_access",
}


def _seed_economic_development_market(session: Session) -> None:
    seed_region(session, "strategy_target", display_name="Strategy Target")
    seed_region(session, "strategy_peer_one", display_name="Strategy Peer One")
    seed_region(session, "strategy_peer_two", display_name="Strategy Peer Two")

    for index, postings in enumerate([80, 8, 8, 8, 8]):
        seed_company_region_signal(
            session,
            region_id="strategy_target",
            company_id=f"target_software_{index}",
            company_name=f"Target Software {index}",
            sector="software",
            active_postings=postings,
            internship_count=0,
            coop_count=0,
            entry_level_full_time_count=3 if index == 0 else 0,
            formal_program=False,
            is_major_tech=index == 0,
        )

    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="strategy_peer_one",
            company_id=f"peer_one_{sector}_{index}",
            company_name=f"Peer One {sector.title()} {index}",
            sector=sector,
            active_postings=12,
            internship_count=2,
            coop_count=1,
            entry_level_full_time_count=1,
            formal_program=True,
        )

    seed_company_region_signal(
        session,
        region_id="strategy_peer_one",
        company_id="candidate_software",
        company_name="Candidate Software",
        sector="software",
        active_postings=18,
        internship_count=3,
        coop_count=1,
        entry_level_full_time_count=2,
        formal_program=True,
    )

    for index, sector in enumerate(["software", "software", "cloud", "ai", "fintech"]):
        seed_company_region_signal(
            session,
            region_id="strategy_peer_two",
            company_id=f"peer_two_{index}",
            company_name=f"Peer Two Company {index}",
            sector=sector,
            active_postings=9 + index,
            internship_count=1,
            coop_count=0,
            entry_level_full_time_count=1,
            formal_program=True,
        )


def test_economic_development_profile_is_deterministic_and_downstream_of_24a(
    session: Session,
) -> None:
    _seed_economic_development_market(session)

    service = PolicyIntelligenceService(session)
    first = service.build_economic_development_profile("strategy_target", now=NOW)
    second = service.build_economic_development_profile("strategy_target", now=NOW)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.region_id == "strategy_target"
    assert first.regional_policy_profile.region_id == "strategy_target"
    assert first.regional_policy_profile.key_metric_bands["employer_dependency"] in {
        "high",
        "very_high",
    }
    assert first.freshness.generated_at == NOW
    assert first.source_summary.source_count > 0
    assert first.public_safe is True
    assert first.limitations


def test_sector_gaps_and_employer_base_risks_use_structured_evidence(
    session: Session,
) -> None:
    _seed_economic_development_market(session)

    profile = PolicyIntelligenceService(session).build_economic_development_profile(
        "strategy_target",
        now=NOW,
    )

    gap_types = {finding.gap_type for finding in profile.sector_gap_findings}
    assert "internship_pathway_gap" in gap_types
    assert "early_career_access_gap" in gap_types
    assert "full_time_without_internship_pathway" in gap_types
    assert all(finding.evidence_references for finding in profile.sector_gap_findings)
    assert all(finding.recommended_strategy_candidate for finding in profile.sector_gap_findings)

    assert profile.employer_base_risk_findings
    for finding in profile.employer_base_risk_findings:
        metric_refs = {
            ref for ref in finding.evidence_references if ref.startswith("metric:")
        }
        assert metric_refs
        assert metric_refs.issubset(_SAFE_STRATEGY_METRIC_REFS)
        assert "not economic forecasts" in " ".join(finding.limitations).casefold()


def test_company_attraction_candidates_are_directional_not_guarantees(
    session: Session,
) -> None:
    _seed_economic_development_market(session)

    profile = PolicyIntelligenceService(session).build_economic_development_profile(
        "strategy_target",
        now=NOW,
    )

    candidate = next(
        item
        for item in profile.company_attraction_candidates
        if item.company_id == "candidate_software"
    )
    assert candidate.fit_band in {"moderate", "high", "very_high"}
    assert "directionally aligned" in candidate.fit_rationale
    assert "strategy candidate" in " ".join(candidate.limitations)
    assert candidate.regional_gap_addressed == "sector:software"

    serialized = str(profile.model_dump(mode="json")).casefold()
    for phrase in (
        "tax incentives",
        "will expand",
        "guaranteed",
        "guarantee",
        "policy caused",
        "city is failing",
    ):
        assert phrase not in serialized
