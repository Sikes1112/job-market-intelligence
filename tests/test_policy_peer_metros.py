from __future__ import annotations

from sqlalchemy.orm import Session

from backend.policy.service import PolicyIntelligenceService
from tests.policy_strategy_helpers import (
    NOW,
    seed_company_region_signal,
    seed_region,
)


def _seed_peer_market(session: Session) -> None:
    seed_region(session, "peer_target", display_name="Peer Target")
    seed_region(session, "peer_low_access", display_name="Peer Low Access")
    seed_region(session, "peer_concentrated", display_name="Peer Concentrated")

    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="peer_target",
            company_id=f"peer_target_{index}",
            company_name=f"Peer Target Company {index}",
            sector=sector,
            active_postings=10 + index,
            internship_count=2,
            coop_count=1,
            entry_level_full_time_count=1,
            formal_program=True,
        )

    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="peer_low_access",
            company_id=f"peer_low_access_{index}",
            company_name=f"Peer Low Access Company {index}",
            sector=sector,
            active_postings=8 + index,
            internship_count=0,
            coop_count=0,
            entry_level_full_time_count=0,
            formal_program=False,
        )

    for index, postings in enumerate([70, 3, 3, 3, 3]):
        seed_company_region_signal(
            session,
            region_id="peer_concentrated",
            company_id=f"peer_concentrated_{index}",
            company_name=f"Peer Concentrated Company {index}",
            sector="software",
            active_postings=postings,
            internship_count=0 if index else 1,
            coop_count=0,
            entry_level_full_time_count=1 if index == 0 else 0,
            formal_program=index == 0,
        )


def test_peer_metro_comparisons_are_explainable(session: Session) -> None:
    _seed_peer_market(session)

    profile = PolicyIntelligenceService(session).build_peer_comparison_profile(
        "peer_target",
        now=NOW,
    )

    assert profile.peer_metro_comparisons
    comparison = profile.peer_metro_comparisons[0]
    assert comparison.peer_region_id in {"peer_low_access", "peer_concentrated"}
    assert "available policy metrics" in comparison.similarity_rationale
    assert comparison.metrics_compared
    assert comparison.similarity_score is not None
    assert comparison.target_region_stronger or comparison.target_region_weaker
    assert comparison.limitations
    assert profile.limitations
    assert profile.public_safe is True


def test_low_data_peer_comparison_emits_warning_and_limitation(
    session: Session,
) -> None:
    seed_region(session, "no_peer_target", display_name="No Peer Target")
    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="no_peer_target",
            company_id=f"no_peer_target_{index}",
            company_name=f"No Peer Target Company {index}",
            sector=sector,
            active_postings=10,
            internship_count=1,
            coop_count=0,
            entry_level_full_time_count=1,
            formal_program=True,
        )

    profile = PolicyIntelligenceService(session).build_peer_comparison_profile(
        "no_peer_target",
        now=NOW,
    )

    assert profile.peer_metro_comparisons == ()
    assert "low_peer_comparison_coverage" in {warning.code for warning in profile.warnings}
    assert any("limited" in limitation.casefold() for limitation in profile.limitations)
    assert profile.public_safe is True
