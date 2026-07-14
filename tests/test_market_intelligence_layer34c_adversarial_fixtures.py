from __future__ import annotations

import json
from pathlib import Path

from backend.imports.registry import load_market_registry
from backend.market_intelligence.adversarial_fixtures import (
    adversarial_market_fixtures,
    build_adversarial_fixture_bundle,
)
from backend.market_intelligence.robustness import evaluate_ranking_robustness
from backend.market_intelligence.schemas import (
    CareerGoal,
    EvidenceBasis,
    EvidenceSufficiency,
    IntelligenceConfidence,
    IntelligenceFreshness,
    RankingStabilityStatus,
    RobustnessScenarioCode,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_IMPORTS = REPO_ROOT / "data" / "imports"

EXPECTED_FIXTURE_CODES = (
    "strong_ai_weak_internships",
    "broad_employer_weak_early_career",
    "smaller_market_strong_coop",
    "stale_otherwise_strong",
    "dominant_single_employer",
    "many_unknowns",
    "strong_direct_role_evidence",
    "mostly_proxy_evidence",
)


def test_layer34c_adversarial_fixtures_are_synthetic_deterministic_and_complete() -> None:
    first = adversarial_market_fixtures()
    second = adversarial_market_fixtures()
    first_payload = [fixture.validation_payload() for fixture in first]

    assert first_payload == [fixture.validation_payload() for fixture in second]
    assert tuple(fixture.code for fixture in first) == EXPECTED_FIXTURE_CODES
    assert len({fixture.market_key for fixture in first}) == len(EXPECTED_FIXTURE_CODES)
    assert all(fixture.market_key.startswith("layer34c_fixture_") for fixture in first)
    assert all("synthetic" in fixture.description.lower() for fixture in first)
    assert all(fixture.expected_scenarios for fixture in first)
    assert {fixture.primary_goal for fixture in first}.issubset(set(CareerGoal))

    production_markets = set(load_market_registry())
    assert {fixture.market_key for fixture in first}.isdisjoint(production_markets)

    json.dumps(first_payload, sort_keys=True)
    _assert_public_payload_safe(first_payload)


def test_layer34c_adversarial_fixtures_preserve_required_archetypes() -> None:
    bundle = build_adversarial_fixture_bundle()
    by_code = {fixture.code: fixture for fixture in bundle.fixtures}

    ai = by_code["strong_ai_weak_internships"].metrics
    assert ai.ai_cloud_activity == 36
    assert ai.ai_cloud_employer_count == 5
    assert ai.internship_total == 1

    broad = by_code["broad_employer_weak_early_career"].metrics
    assert broad.employer_count == 20
    assert broad.product_activity == 0
    assert broad.formal_program_count == 0
    assert broad.early_career_score is not None and broad.early_career_score < 1

    coop = by_code["smaller_market_strong_coop"].metrics
    assert coop.employer_count < broad.employer_count
    assert coop.coop_total == 12

    stale = by_code["stale_otherwise_strong"].metrics
    assert stale.active_posting_total == 52
    assert stale.freshness is IntelligenceFreshness.STALE
    assert stale.stale_source_count == 1

    dominated = by_code["dominant_single_employer"].metrics
    assert dominated.employer_count == 1
    assert any("dominant employer" in item for item in dominated.limitations)

    unknowns = by_code["many_unknowns"].metrics
    assert unknowns.unknown_fact_count > unknowns.observed_zero_fact_count
    assert unknowns.active_posting_unknown_rows > 0
    assert unknowns.confidence is IntelligenceConfidence.LOW

    direct = by_code["strong_direct_role_evidence"].metrics
    assert direct.cybersecurity_activity == 27
    assert direct.cybersecurity_employer_count == 5

    proxy = by_code["mostly_proxy_evidence"].metrics
    assert proxy.product_activity == 0
    assert proxy.formal_program_count == 0
    assert proxy.employer_count > 0
    assert proxy.early_career_score is not None and proxy.early_career_score > 0


def test_layer34c_adversarial_fixtures_drive_expected_ranking_states() -> None:
    bundle = build_adversarial_fixture_bundle()

    strong_ai = _ranked_item(
        bundle,
        CareerGoal.AI_ML,
        "strong_ai_weak_internships",
    )
    assert strong_ai.rank == 1
    assert strong_ai.evidence_sufficiency is EvidenceSufficiency.COMPARISON_READY
    assert strong_ai.evidence_basis is EvidenceBasis.DIRECT_AND_PROXY

    broad_pm = _ranked_item(
        bundle,
        CareerGoal.PRODUCT_MANAGEMENT,
        "broad_employer_weak_early_career",
    )
    assert broad_pm.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert broad_pm.evidence_basis is EvidenceBasis.PROXY
    assert broad_pm.confidence is IntelligenceConfidence.LOW

    proxy_pm = _ranked_item(
        bundle,
        CareerGoal.PRODUCT_MANAGEMENT,
        "mostly_proxy_evidence",
    )
    assert proxy_pm.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert proxy_pm.evidence_basis is EvidenceBasis.PROXY

    stale_se = _ranked_item(
        bundle,
        CareerGoal.SOFTWARE_ENGINEERING,
        "stale_otherwise_strong",
    )
    assert stale_se.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert stale_se.freshness is IntelligenceFreshness.STALE

    dominated_cyber = _ranked_item(
        bundle,
        CareerGoal.CYBERSECURITY,
        "dominant_single_employer",
    )
    assert dominated_cyber.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert any("dominant employer" in item for item in dominated_cyber.limitations)

    direct_cyber = _ranked_item(
        bundle,
        CareerGoal.CYBERSECURITY,
        "strong_direct_role_evidence",
    )
    assert direct_cyber.rank == 1
    assert direct_cyber.evidence_sufficiency is EvidenceSufficiency.COMPARISON_READY
    assert direct_cyber.evidence_basis is EvidenceBasis.DIRECT_AND_PROXY

    unknown_se = _ranked_item(bundle, CareerGoal.SOFTWARE_ENGINEERING, "many_unknowns")
    assert unknown_se.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert unknown_se.confidence is IntelligenceConfidence.LOW


def test_layer34c_adversarial_fixtures_support_expected_robustness_scenarios() -> None:
    bundle = build_adversarial_fixture_bundle()
    first = evaluate_ranking_robustness(
        rankings=bundle.rankings,
        profiles=bundle.profiles,
        metrics_by_market=bundle.metrics_by_market,
    )
    second = evaluate_ranking_robustness(
        rankings=bundle.rankings,
        profiles=bundle.profiles,
        metrics_by_market=bundle.metrics_by_market,
    )

    assert _stability_payload(first) == _stability_payload(second)

    for fixture in bundle.fixtures:
        scenarios = {
            scenario.scenario: scenario
            for scenario in first[fixture.primary_goal][fixture.market_key].scenarios
        }
        for expected in fixture.expected_scenarios:
            assert scenarios[expected].status is not RankingStabilityStatus.INDETERMINATE
            assert scenarios[expected].baseline_result.market_key == fixture.market_key
            assert scenarios[expected].scenario_result.market_key == fixture.market_key
            assert scenarios[expected].explanation

    concentrated = by_fixture_code(
        bundle,
        first,
        "dominant_single_employer",
        RobustnessScenarioCode.SOURCE_CONCENTRATION,
    )
    contradictory = by_fixture_code(
        bundle,
        first,
        "many_unknowns",
        RobustnessScenarioCode.CONTRADICTORY_INPUTS,
    )
    assert concentrated.status is not RankingStabilityStatus.INDETERMINATE
    assert "source coverage" in concentrated.explanation
    assert contradictory.status is not RankingStabilityStatus.INDETERMINATE
    assert "contradictory-input" in contradictory.explanation

    json.dumps(_stability_payload(first), sort_keys=True)
    _assert_public_payload_safe(_stability_payload(first))


def test_layer34c_adversarial_fixtures_do_not_mutate_curated_import_datasets() -> None:
    before = _data_import_inventory()
    bundle = build_adversarial_fixture_bundle()
    evaluate_ranking_robustness(
        rankings=bundle.rankings,
        profiles=bundle.profiles,
        metrics_by_market=bundle.metrics_by_market,
    )

    assert _data_import_inventory() == before


def _ranked_item(bundle, goal: CareerGoal, fixture_code: str):
    fixture = next(item for item in bundle.fixtures if item.code == fixture_code)
    return next(
        item
        for item in bundle.rankings[goal].ranked_markets
        if item.market_key == fixture.market_key
    )


def by_fixture_code(
    bundle,
    analysis,
    fixture_code: str,
    scenario_code: RobustnessScenarioCode,
):
    fixture = next(item for item in bundle.fixtures if item.code == fixture_code)
    return next(
        scenario
        for scenario in analysis[fixture.primary_goal][fixture.market_key].scenarios
        if scenario.scenario is scenario_code
    )


def _stability_payload(analysis) -> dict[str, dict[str, object]]:
    return {
        goal.value: {
            market_key: result.as_dict()
            for market_key, result in sorted(by_market.items())
        }
        for goal, by_market in sorted(analysis.items(), key=lambda item: item[0].value)
    }


def _data_import_inventory() -> tuple[tuple[str, int, int], ...]:
    return tuple(
        sorted(
            (
                str(path.relative_to(DATA_IMPORTS)),
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in DATA_IMPORTS.rglob("*")
            if path.is_file()
        )
    )


def _assert_public_payload_safe(payload) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    forbidden = (
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
        "provenance_internal",
        "private_provenance",
        "Traceback",
        str(REPO_ROOT),
    )
    assert all(token not in serialized for token in forbidden)
