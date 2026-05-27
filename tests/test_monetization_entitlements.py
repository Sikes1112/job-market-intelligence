from __future__ import annotations

import ast
from pathlib import Path

from backend.monetization.entitlements import decide_access
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import BuyerKind, PlanKey, plan_definition, plan_definitions

REPO_ROOT = Path(__file__).resolve().parent.parent
MONETIZATION_ROOT = REPO_ROOT / "backend" / "monetization"


def test_required_plans_exist() -> None:
    assert {plan.plan_key for plan in plan_definitions()} == {
        PlanKey.FREE,
        PlanKey.INDIVIDUAL_MONTHLY,
        PlanKey.INDIVIDUAL_ANNUAL,
        PlanKey.STUDENT_ANNUAL,
        PlanKey.CAREER_CENTER_LICENSE,
        PlanKey.BOOTCAMP_LICENSE,
        PlanKey.UNIVERSITY_LICENSE,
        PlanKey.WORKFORCE_BOARD_LICENSE,
    }


def test_free_plan_allows_useful_basic_exploration_and_recommendation_preview() -> None:
    free_features = plan_definition(PlanKey.FREE).included_feature_keys

    assert MonetizationFeatureKey.BASIC_REGION_EXPLORATION in free_features
    assert MonetizationFeatureKey.PUBLIC_DEMO_MARKETS in free_features
    assert MonetizationFeatureKey.LIMITED_COMPARISONS in free_features
    assert MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY in free_features
    assert MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW in free_features
    assert decide_access(
        PlanKey.FREE,
        MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
    ).allowed


def test_free_plan_blocks_paid_workflow_features_without_hiding_core_result() -> None:
    blocked_features = (
        MonetizationFeatureKey.FULL_REPORT_GENERATION,
        MonetizationFeatureKey.ALERTS,
        MonetizationFeatureKey.SAVED_WATCHLISTS,
        MonetizationFeatureKey.FULL_MARKET_COVERAGE,
    )

    for feature_key in blocked_features:
        decision = decide_access(PlanKey.FREE, feature_key)
        assert not decision.allowed
        assert decision.upgrade_plan_keys

    assert decide_access(
        PlanKey.FREE,
        MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
    ).allowed


def test_paid_individual_plans_allow_individual_paid_features() -> None:
    individual_paid_features = (
        MonetizationFeatureKey.SAVED_WATCHLISTS,
        MonetizationFeatureKey.ALERTS,
        MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS,
        MonetizationFeatureKey.FULL_MARKET_COVERAGE,
        MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
        MonetizationFeatureKey.DEEPER_COMPANY_GEOGRAPHY,
        MonetizationFeatureKey.SAVED_COMPARISON_HISTORY,
        MonetizationFeatureKey.FULL_REPORT_GENERATION,
    )

    for plan_key in (
        PlanKey.INDIVIDUAL_MONTHLY,
        PlanKey.INDIVIDUAL_ANNUAL,
        PlanKey.STUDENT_ANNUAL,
    ):
        for feature_key in individual_paid_features:
            assert decide_access(plan_key, feature_key).allowed


def test_institutional_plans_expose_institutional_license_capabilities() -> None:
    institutional_plans = (
        PlanKey.CAREER_CENTER_LICENSE,
        PlanKey.BOOTCAMP_LICENSE,
        PlanKey.UNIVERSITY_LICENSE,
        PlanKey.WORKFORCE_BOARD_LICENSE,
    )

    for plan_key in institutional_plans:
        plan = plan_definition(plan_key)
        assert plan.buyer_kind is BuyerKind.INSTITUTIONAL
        assert plan.buyer_segment is not None
        assert MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT in (
            plan.included_feature_keys
        )
        assert MonetizationFeatureKey.COHORT_GUIDANCE_TEMPLATES in plan.included_feature_keys
        assert decide_access(
            plan_key,
            MonetizationFeatureKey.PRIVACY_PRESERVING_PROGRAM_INSIGHTS,
        ).allowed


def test_blocked_access_decisions_return_upgrade_targets_and_usage_details() -> None:
    feature_key = MonetizationFeatureKey.FULL_REPORT_GENERATION
    not_in_plan = decide_access(PlanKey.FREE, feature_key)

    assert not not_in_plan.allowed
    assert PlanKey.INDIVIDUAL_MONTHLY in not_in_plan.upgrade_plan_keys
    assert not_in_plan.usage_limit is None

    limit_reached = decide_access(
        PlanKey.INDIVIDUAL_MONTHLY,
        feature_key,
        usage_context={"used": 3},
    )

    assert not limit_reached.allowed
    assert limit_reached.usage_limit is not None
    assert limit_reached.remaining_usage == 0
    assert PlanKey.INDIVIDUAL_ANNUAL in limit_reached.upgrade_plan_keys


def test_entitlement_decisions_are_centralized_and_deterministic() -> None:
    first = decide_access(
        PlanKey.FREE,
        MonetizationFeatureKey.LIMITED_COMPARISONS,
        usage_context={"used": 1},
    )
    second = decide_access(
        PlanKey.FREE,
        MonetizationFeatureKey.LIMITED_COMPARISONS,
        usage_context={"used": 1},
    )

    assert first == second
    assert first.allowed
    assert first.usage_limit is not None
    assert first.remaining_usage == 2


def test_monetization_domain_does_not_import_recommendation_ranking_or_providers() -> None:
    always_forbidden_prefixes = {
        "backend.recommendations",
        "stripe",
        "fastapi",
    }
    pure_modules = {
        "accounts.py",
        "enforcement.py",
        "entitlements.py",
        "features.py",
        "plans.py",
        "reports.py",
        "resolver.py",
        "segments.py",
        "usage.py",
    }
    violations: dict[str, list[str]] = {}

    for path in sorted(MONETIZATION_ROOT.glob("*.py")):
        imports = _imports(path)
        bad = [
            name
            for name in imports
            if any(name.startswith(prefix) for prefix in always_forbidden_prefixes)
        ]
        if path.name in pure_modules:
            bad.extend(name for name in imports if name.startswith("sqlalchemy"))
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations


def test_monetization_tests_do_not_import_recommendation_ranking() -> None:
    test_files = sorted(REPO_ROOT.glob("tests/test_monetization*.py"))
    violations: dict[str, list[str]] = {}

    for path in test_files:
        imports = _imports(path)
        bad = [name for name in imports if name.startswith("backend.recommendations")]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names
