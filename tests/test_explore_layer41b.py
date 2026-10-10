from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.career_agent.authorities import CareerAgentAuthorityAdapter
from backend.career_agent.planning import CareerActionPlanningService
from backend.career_agent.schemas import (
    CareerActionPlanRequest,
    CareerAgentGuardrailViolation,
    CareerAgentQuestionType,
    CareerAgentRequest,
    CareerAgentToolRequest,
    CareerAgentToolType,
    CareerPlanType,
)
from backend.career_agent.service import CareerAgentGroundingService
from backend.career_agent.tools import CareerAgentToolService
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.career_identity.repository import CareerIdentityRepository
from backend.current_opportunities.models import CurrentOpportunity
from backend.explore.context import (
    ExploreContextService,
    context_fingerprint,
    map_role_or_goal,
)
from backend.explore.schemas import (
    ExploreContextValues,
    ExploreFitState,
    ExploreMarketsRequest,
    ExplorePersonalizationState,
    ExploreSessionOverrides,
    GeographicScopeInput,
    GoalMappingState,
)
from backend.explore.service import ExploreFitService
from backend.geography.models import Region, RegionAlias
from backend.geography.repository import RegionRepository
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.market_intelligence.calibration import scores_are_near_tie
from backend.market_intelligence.schemas import (
    CareerGoal,
    ContradictionCode,
    ContradictionFinding,
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceSufficiency,
    IntelligenceConfidence,
    IntelligenceFreshness,
    RankingDriver,
)
from backend.product_measurement.models import ProductAnalyticsEvent
from backend.users.models import User
from tests.test_api_user_routes import _auth_headers, _current_user_id

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


@dataclass(frozen=True)
class _FakeItem:
    market_key: str
    market_name: str
    score: float
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.COMPARISON_READY
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH
    freshness: IntelligenceFreshness = IntelligenceFreshness.CURRENT
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    abstention_reason: str | None = None
    limitations: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ("A documented tradeoff.",)
    ranking_drivers: tuple[RankingDriver, ...] = (
        RankingDriver(
            code="hiring_activity",
            label="Hiring activity",
            contribution=0.4,
            evidence="Governed Layer 34 evidence.",
        ),
    )
    supporting_metrics: dict[str, Any] = None  # type: ignore[assignment]
    grounding: Any = None
    contradictions: tuple[ContradictionFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.supporting_metrics is None:
            object.__setattr__(
                self,
                "supporting_metrics",
                {"ranking_eligible_fact_count": 4, "unknown_fact_count": 0},
            )


class _FakeRanking:
    def __init__(self, items: tuple[_FakeItem, ...]) -> None:
        self.ranked_markets = items
        self.limitations = ()
        self.contradictions = tuple(finding for item in items for finding in item.contradictions)
        self.contradiction_status = (
            ContradictionStatus.BLOCKING
            if any(item.contradiction_status is ContradictionStatus.BLOCKING for item in items)
            else ContradictionStatus.CLEAR
        )
        self.abstention_reason = (
            "Layer 34 contradiction blocks recommendation."
            if self.contradiction_status is ContradictionStatus.BLOCKING
            else None
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "market_key": item.market_key,
                    "score": item.score,
                    "sufficiency": item.evidence_sufficiency.value,
                }
                for item in self.ranked_markets
            ]
        }


class _FakeMarketIntelligence:
    def __init__(self, items: tuple[_FakeItem, ...]) -> None:
        self.items = items
        self.goals: list[str] = []

    def ranking(self, *, goal: str, as_of=None):  # noqa: ANN001, ANN201
        self.goals.append(goal)
        return _FakeRanking(self.items)


@dataclass(frozen=True)
class _FakeProfile:
    market_key: str
    market_name: str
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH
    freshness: IntelligenceFreshness = IntelligenceFreshness.CURRENT
    limitations: tuple[str, ...] = ()
    supporting_metrics: dict[str, Any] = None  # type: ignore[assignment]
    coverage_summary: str = "Governed market profile coverage."
    grounding: Any = None
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    contradictions: tuple[ContradictionFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.supporting_metrics is None:
            object.__setattr__(self, "supporting_metrics", {})


class _FakeGeneralReport:
    def __init__(self, profiles: tuple[_FakeProfile, ...]) -> None:
        self.profiles = profiles
        self.limitations = ()

    def as_dict(self) -> dict[str, Any]:
        return {"profiles": [profile.market_key for profile in self.profiles]}


class _FakeGeneralMarketIntelligence(_FakeMarketIntelligence):
    def __init__(self, profiles: tuple[_FakeProfile, ...]) -> None:
        super().__init__(())
        self.profiles = profiles

    def platform_summary(self, *, as_of=None):  # noqa: ANN001, ANN201
        return _FakeGeneralReport(self.profiles)


def _seed_regions(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="boston",
                display_name="Greater Boston",
                region_type="greater_region",
                public_slug="boston",
                primary_city="Boston",
                centroid_latitude=42.36,
                centroid_longitude=-71.06,
                market_support_status="supported",
            ),
            Region(
                region_id="greater_seattle",
                region_name="seattle",
                display_name="Greater Seattle",
                region_type="greater_region",
                public_slug="seattle",
                primary_city="Seattle",
                market_support_status="supported",
            ),
        ]
    )
    session.flush()


def _registry() -> dict[str, Any]:
    return {
        "boston": SimpleNamespace(region_id="greater_boston"),
        "seattle": SimpleNamespace(region_id="greater_seattle"),
    }


def _seed_identity(session: Session, *, user_id: str = "explore_user", consent=True) -> None:
    session.add(User(user_id=user_id))
    session.flush()
    session.add(
        CareerIdentity(
            career_identity_id=f"identity_{user_id}",
            user_id=user_id,
            current_version=3,
            downstream_personalization_consent_granted=consent,
        )
    )
    session.add_all(
        [
            CareerIdentityFact(
                career_identity_fact_id=f"role_{user_id}",
                career_identity_id=f"identity_{user_id}",
                user_id=user_id,
                fact_type="role_preference",
                normalized_key="role:software",
                state="explicit",
                payload={
                    "role_title": "Software Engineer",
                    "employment_type": "full_time",
                    "seniority": "entry_level",
                    "preference_kind": "preferred",
                },
                provenance={},
            ),
            CareerIdentityFact(
                career_identity_fact_id=f"industry_{user_id}",
                career_identity_id=f"identity_{user_id}",
                user_id=user_id,
                fact_type="industry_preference",
                normalized_key="industry:ai",
                state="confirmed",
                payload={"industry": "AI", "preference_kind": "preferred"},
                provenance={},
            ),
        ]
    )
    session.flush()


def _context_service(session: Session) -> ExploreContextService:
    return ExploreContextService(
        CareerIdentityRepository(session),
        RegionRepository(session),
    )


def _opportunity(opportunity_id: str, market_id: str) -> CurrentOpportunity:
    return CurrentOpportunity(
        current_opportunity_id=opportunity_id,
        canonical_identity_key=f"identity|{opportunity_id}",
        duplicate_group_key=f"duplicate|{opportunity_id}",
        company_name="Example Company",
        original_title="Software Engineer",
        normalized_title="software engineer",
        role_family="software_engineering",
        seniority_level="entry_level",
        market_id=market_id,
        market_label=market_id,
        location_resolution_status="resolved",
        work_arrangement="hybrid",
        compensation_interval="unknown",
        employment_type="full_time",
        opportunity_type="job",
        source_values={},
        normalization_confidence="high",
        identity_confidence="high",
        canonical_status="active",
        canonical_updated_at=NOW,
        freshness_state="fresh",
        ranking_eligible=True,
        ranking_ineligible_reasons=[],
        warnings=[],
        source_count=1,
    )


def test_context_defaults_overrides_and_fingerprint_are_deterministic(
    session: Session,
) -> None:
    _seed_regions(session)
    _seed_identity(session)
    service = _context_service(session)

    first = service.build("explore_user")
    repeated = service.build("explore_user")
    overridden = service.build(
        "explore_user",
        ExploreSessionOverrides(
            goal="Product Management",
            industries=("Health Tech",),
            opportunity_types=("internship",),
        ),
    )

    assert first.supported_goal == "software_engineering"
    assert first.effective_context.industries == ("ai",)
    assert first.context_fingerprint == repeated.context_fingerprint
    assert first.fingerprint_version == "explore_context_v2"
    assert first.context_fingerprint.startswith("explore_context_v2:")
    assert overridden.supported_goal == "product_management"
    assert overridden.effective_context.industries == ("health tech",)
    assert overridden.effective_context.opportunity_types == ("internship",)
    assert set(overridden.applied_context) == {"goal"}
    assert {item.field for item in overridden.unapplied_context} == {
        "role_families",
        "industries",
        "opportunity_types",
        "career_stage",
    }
    assert overridden.unsupported_context == ()
    assert overridden.context_fingerprint != first.context_fingerprint
    identity = CareerIdentityRepository(session).get_identity_for_user("explore_user")
    assert identity is not None and identity.current_version == 3


def test_context_consent_missing_identity_and_role_mapping_boundaries(
    session: Session,
) -> None:
    _seed_identity(session, user_id="no_consent", consent=False)
    session.add(User(user_id="no_identity"))
    session.flush()
    service = _context_service(session)

    no_consent = service.build("no_consent")
    missing = service.build("no_identity")

    assert no_consent.profile_defaults.role_families == ()
    assert no_consent.personalization_state == "general_market_intelligence"
    assert missing.career_identity_id is None
    assert map_role_or_goal(("Software Engineer",)).goal is CareerGoal.SOFTWARE_ENGINEERING
    assert map_role_or_goal(("Software Engineer and Product Manager",)).state is (
        GoalMappingState.AMBIGUOUS
    )
    assert map_role_or_goal(("Actuary",)).state is GoalMappingState.UNSUPPORTED


def test_compound_role_mapping_is_punctuation_invariant_and_explicitly_ambiguous() -> None:
    ai_product_variants = (
        "AI Product Manager",
        "AI/ML Product Manager",
        "AI ML Product Manager",
        "machine-learning product manager",
    )
    mappings = tuple(map_role_or_goal((value,)) for value in ai_product_variants)
    assert all(mapping.state is GoalMappingState.AMBIGUOUS for mapping in mappings)
    assert all(
        mapping.candidates == (CareerGoal.PRODUCT_MANAGEMENT, CareerGoal.AI_ML)
        for mapping in mappings
    )
    security = map_role_or_goal(("Security Product Manager",))
    assert security.state is GoalMappingState.AMBIGUOUS
    assert security.candidates == (
        CareerGoal.PRODUCT_MANAGEMENT,
        CareerGoal.CYBERSECURITY,
    )
    for unsupported in ("Data Engineer", "Solutions Engineer", "Actuary"):
        assert map_role_or_goal((unsupported,)).state is GoalMappingState.UNSUPPORTED


def test_semantic_fingerprint_canonicalizes_set_like_context() -> None:
    first = ExploreContextValues(
        role_families=("ai", "product"),
        industries=("health", "technology"),
        opportunity_types=("job", "internship"),
        work_arrangements=("hybrid", "remote"),
        included_region_ids=("greater_boston", "greater_seattle"),
        excluded_region_ids=("greater_austin",),
    )
    reordered = ExploreContextValues(
        role_families=("product", "ai", "ai"),
        industries=("technology", "health"),
        opportunity_types=("internship", "job"),
        work_arrangements=("remote", "hybrid"),
        included_region_ids=("greater_seattle", "greater_boston"),
        excluded_region_ids=("greater_austin", "greater_austin"),
    )
    changed = reordered.model_copy(update={"industries": ("finance", "health")})
    kwargs = {
        "identity_version": 3,
        "consent": True,
        "personalization_state": ExplorePersonalizationState.PERSONALIZED,
    }
    assert context_fingerprint(effective=first, **kwargs) == context_fingerprint(
        effective=reordered, **kwargs
    )
    assert context_fingerprint(effective=first, **kwargs) != context_fingerprint(
        effective=changed, **kwargs
    )


def test_soft_geography_is_not_hard_scope_and_explicit_conflict_needs_input(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    _seed_identity(session)
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="geo_explore_user",
            career_identity_id="identity_explore_user",
            user_id="explore_user",
            fact_type="geographic_constraint",
            normalized_key="geo:boston",
            state="explicit",
            payload={"location": "Boston", "constraint_kind": "target"},
            provenance={},
        )
    )
    session.flush()
    service = _context_service(session)

    soft = service.build("explore_user")
    assert soft.effective_context.preferred_region_ids == ("greater_boston",)
    assert soft.effective_context.included_region_ids == ()
    assert any(item.field == "preferred_region_ids" for item in soft.unapplied_context)
    assert "preferred_region_ids" not in soft.applied_context
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    evaluated = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.70),
            )
        ),
        clock=lambda: NOW,
    ).evaluate("explore_user")
    assert all(
        market.state is not ExploreFitState.HARD_CONSTRAINT_EXCLUDED for market in evaluated.markets
    )

    session.add(
        CareerIdentityFact(
            career_identity_fact_id="geo_exclude_explore_user",
            career_identity_id="identity_explore_user",
            user_id="explore_user",
            fact_type="geographic_constraint",
            normalized_key="geo:exclude:seattle",
            state="explicit",
            payload={"location": "Seattle", "constraint_kind": "excluded"},
            provenance={},
        )
    )
    session.flush()
    excluded = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.70),
            )
        ),
        clock=lambda: NOW,
    ).evaluate("explore_user")
    assert (
        next(
            market for market in excluded.markets if market.region.region_id == "greater_seattle"
        ).state
        is ExploreFitState.HARD_CONSTRAINT_EXCLUDED
    )
    profile_scope = service.build("explore_user")
    assert "excluded_region_ids" in profile_scope.applied_context

    conflict = service.build(
        "explore_user",
        ExploreSessionOverrides(
            geographic_scope=GeographicScopeInput(
                region_refs=("Boston",),
                excluded_region_refs=("greater_boston",),
            )
        ),
    )
    assert conflict.personalization_state == "needs_input"
    assert any(
        item.code == "conflicting_geographic_constraints" for item in conflict.unsupported_context
    )


def test_explicit_goal_marks_superseded_role_context_unapplied(session: Session) -> None:
    _seed_identity(session)
    context = _context_service(session).build(
        "explore_user",
        ExploreSessionOverrides(goal="Product Management"),
    )
    assert context.supported_goal == "product_management"
    assert "goal" in context.applied_context
    assert "role_families" not in context.applied_context
    assert any(
        item.code == "role_families_overridden_by_explicit_goal"
        for item in context.unapplied_context
    )
    assert all(
        item.code != "role_families_overridden_by_explicit_goal"
        for item in context.unsupported_context
    )


def test_context_classification_separates_valid_unapplied_from_unsupported(
    session: Session,
) -> None:
    _seed_identity(session)
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="timing_explore_user",
            career_identity_id="identity_explore_user",
            user_id="explore_user",
            fact_type="timing_preference",
            normalized_key="timing:active_search",
            state="explicit",
            payload={"timing_type": "active_search", "urgency": "soon"},
            provenance={},
        )
    )
    session.flush()
    service = _context_service(session)

    supported = service.build(
        "explore_user",
        ExploreSessionOverrides(
            role_families=("Software Engineer",),
            industries=("Health Tech",),
            opportunity_types=("internship",),
            work_arrangements=("hybrid",),
        ),
    )
    assert {"goal", "role_families"}.issubset(supported.applied_context)
    assert {
        "industries",
        "opportunity_types",
        "career_stage",
        "timing",
        "work_arrangements",
    }.issubset({item.field for item in supported.unapplied_context})
    assert supported.unsupported_context == ()

    unsupported = service.build(
        "explore_user",
        ExploreSessionOverrides(
            goal="Actuary",
            industries=("Health Tech",),
        ),
    )
    assert unsupported.applied_context == ()
    assert "industries" in {item.field for item in unsupported.unapplied_context}
    assert "goal" in {item.field for item in unsupported.unsupported_context}
    assert "goal" not in {item.field for item in unsupported.unapplied_context}


def test_explicit_no_relocation_semantics_create_hard_geographic_scope(
    session: Session,
) -> None:
    _seed_regions(session)
    _seed_identity(session)
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="geo_no_relocation",
            career_identity_id="identity_explore_user",
            user_id="explore_user",
            fact_type="geographic_constraint",
            normalized_key="geo:no-relocation:boston",
            state="explicit",
            payload={
                "location": "Boston",
                "constraint_kind": "target",
                "relocation_willingness": "no",
            },
            provenance={},
        )
    )
    session.flush()
    context = _context_service(session).build("explore_user")
    assert context.effective_context.included_region_ids == ("greater_boston",)
    assert "included_region_ids" in context.applied_context
    assert context.effective_context.preferred_region_ids == ()


def test_fit_preserves_layer34_ranking_constraints_ties_and_abstention(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    fake = _FakeMarketIntelligence(
        (
            _FakeItem("boston", "Greater Boston", 0.80),
            _FakeItem(
                "seattle",
                "Greater Seattle",
                0.795,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
                abstention_reason="qualifying evidence is insufficient",
            ),
        )
    )
    service = ExploreFitService(session, market_intelligence=fake, clock=lambda: NOW)
    result = service.evaluate(
        "explicit_session_user",
        ExploreSessionOverrides(goal="software_engineering"),
    )

    assert result.authority == "explore_fit"
    assert result.ranking_universe.nationally_representative is False
    assert result.markets[0].fit_score == 0.80
    assert result.markets[0].fit_band == "strong_fit"
    assert result.markets[0].confidence == "high"
    assert result.markets[0].rank == 1
    assert result.markets[1].state is ExploreFitState.INSUFFICIENT_EVIDENCE
    assert result.markets[1].fit_score is None
    assert result.markets[1].rank is None

    constrained = service.evaluate(
        "explicit_session_user",
        ExploreSessionOverrides(
            goal="software_engineering",
            geographic_scope=GeographicScopeInput(region_refs=("boston",)),
        ),
    )
    assert constrained.markets[1].state is ExploreFitState.HARD_CONSTRAINT_EXCLUDED
    assert constrained.markets[1].rank is None
    assert constrained.ranking_universe.kind == "constrained_curated_markets"


def test_exact_ties_share_rank_and_near_ties_are_explicit(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    overrides = ExploreSessionOverrides(goal="software_engineering")

    tied = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.80),
            )
        ),
        clock=lambda: NOW,
    ).evaluate("explicit_session_user", overrides)
    assert [market.rank for market in tied.markets] == [1, 1]
    assert tied.markets[0].tied_region_ids == ("greater_seattle",)
    assert tied.markets[1].tied_region_ids == ("greater_boston",)

    near = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.795),
            )
        ),
        clock=lambda: NOW,
    ).evaluate("explicit_session_user", overrides)
    assert [market.rank for market in near.markets] == [1, 2]
    assert near.markets[0].near_tie_region_ids == ("greater_seattle",)
    assert "near-tie threshold" in " ".join(near.markets[0].material_limitations)


def test_near_tie_boundary_uses_layer34_rounding_semantics(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    assert scores_are_near_tie(0.80, 0.79)
    assert scores_are_near_tie(0.80, 0.79004)
    assert not scores_are_near_tie(0.80, 0.78994)

    def evaluate(second_score: float):
        return ExploreFitService(
            session,
            market_intelligence=_FakeMarketIntelligence(
                (
                    _FakeItem("boston", "Greater Boston", 0.80),
                    _FakeItem("seattle", "Greater Seattle", second_score),
                )
            ),
            clock=lambda: NOW,
        ).evaluate(
            "explicit_session_user",
            ExploreSessionOverrides(goal="software_engineering"),
        )

    assert evaluate(0.79).markets[0].near_tie_region_ids == ("greater_seattle",)
    assert evaluate(0.79004).markets[0].near_tie_region_ids == ("greater_seattle",)
    assert evaluate(0.78994).markets[0].near_tie_region_ids == ()


def test_general_fallback_honors_explicit_hard_geography(session: Session, monkeypatch) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    result = ExploreFitService(
        session,
        market_intelligence=_FakeGeneralMarketIntelligence(
            (
                _FakeProfile("boston", "Greater Boston"),
                _FakeProfile("seattle", "Greater Seattle"),
            )
        ),
        clock=lambda: NOW,
    ).evaluate(
        "general_user",
        ExploreSessionOverrides(geographic_scope=GeographicScopeInput(region_refs=("Boston",))),
    )
    by_region = {item.region.region_id: item for item in result.markets}
    assert by_region["greater_boston"].state is (ExploreFitState.GENERAL_MARKET_INTELLIGENCE)
    assert by_region["greater_seattle"].state is ExploreFitState.HARD_CONSTRAINT_EXCLUDED
    assert by_region["greater_seattle"].hard_constraint_reasons
    assert result.ranking_universe.region_ids == ("greater_boston",)


def test_known_unsupported_region_is_returned_and_detail_matches_list(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    session.add(
        Region(
            region_id="greater_denver",
            region_name="denver",
            display_name="Greater Denver",
            region_type="greater_region",
            public_slug="denver",
            primary_city="Denver",
            market_support_status="unsupported",
        )
    )
    session.add(
        RegionAlias(
            region_alias_id="denver_legacy_alias",
            region_id="greater_denver",
            alias="Denver Metro Legacy",
            normalized_alias="denver metro legacy",
            alias_type="legacy_id",
        )
    )
    session.flush()
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    service = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.70),
            )
        ),
        clock=lambda: NOW,
    )
    overrides = ExploreSessionOverrides(
        goal="software_engineering",
        geographic_scope=GeographicScopeInput(region_refs=("Denver",)),
    )
    result = service.evaluate("unsupported_region_user", overrides)
    denver = next(item for item in result.markets if item.region.region_id == "greater_denver")
    assert denver.state is ExploreFitState.UNSUPPORTED
    assert denver.fit_score is None
    assert denver.fit_band is None
    assert denver.rank is None
    assert denver.abstention_reason == "unsupported_market"
    detail_response, detail = service.market_detail("unsupported_region_user", "denver", overrides)
    assert detail is not None
    listed = next(
        item for item in detail_response.markets if item.region.region_id == "greater_denver"
    )
    assert detail.model_dump() == listed.model_dump()
    _, legacy_detail = service.market_detail(
        "unsupported_region_user", "Denver Metro Legacy", overrides
    )
    assert legacy_detail is not None
    assert legacy_detail.region.region_id == "greater_denver"

    general_service = ExploreFitService(
        session,
        market_intelligence=_FakeGeneralMarketIntelligence(
            (
                _FakeProfile("boston", "Greater Boston"),
                _FakeProfile("seattle", "Greater Seattle"),
            )
        ),
        clock=lambda: NOW,
    )
    general_overrides = ExploreSessionOverrides(
        geographic_scope=GeographicScopeInput(region_refs=("Denver",))
    )
    general = general_service.evaluate("general_unsupported_user", general_overrides)
    general_denver = next(
        item for item in general.markets if item.region.region_id == "greater_denver"
    )
    _, general_detail = general_service.market_detail(
        "general_unsupported_user", "greater_denver", general_overrides
    )
    assert general_denver.state is ExploreFitState.UNSUPPORTED
    assert general_detail is not None
    assert general_detail.model_dump() == general_denver.model_dump()


def test_structured_contradictions_propagate_through_list_and_detail(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    finding = ContradictionFinding(
        code=ContradictionCode.HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE,
        severity=ContradictionSeverity.BLOCKING,
        message="High confidence conflicts with abstention-level evidence.",
        evidence="The structured Layer 34 finding is blocking.",
        blocks_recommendation=True,
    )
    service = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem(
                    "boston",
                    "Greater Boston",
                    0.80,
                    contradiction_status=ContradictionStatus.BLOCKING,
                    contradictions=(finding,),
                    abstention_reason="Layer 34 contradiction blocks recommendation.",
                ),
                _FakeItem("seattle", "Greater Seattle", 0.70),
            )
        ),
        clock=lambda: NOW,
    )
    overrides = ExploreSessionOverrides(goal="software_engineering")
    response = service.evaluate("contradiction_user", overrides)
    listed = response.markets[0]
    _, detailed = service.market_detail("contradiction_user", "boston", overrides)
    assert listed.state is ExploreFitState.ABSTAINED
    assert listed.contradiction_status == "blocking"
    assert listed.contradiction_blocking is True
    assert listed.contradiction_findings[0]["code"] == ("high_confidence_insufficient_evidence")
    assert listed.contradiction_summary
    assert response.contradiction_status == "blocking"
    assert response.contradiction_blocking is True
    assert detailed is not None
    assert detailed.model_dump() == listed.model_dump()


def test_role_override_selects_governed_goal_without_score_bonus(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    fake = _FakeMarketIntelligence(
        (
            _FakeItem("boston", "Greater Boston", 0.80),
            _FakeItem("seattle", "Greater Seattle", 0.70),
        )
    )
    service = ExploreFitService(session, market_intelligence=fake, clock=lambda: NOW)
    software = service.evaluate(
        "explicit_session_user",
        ExploreSessionOverrides(role_families=("Software Engineer",)),
    )
    product = service.evaluate(
        "explicit_session_user",
        ExploreSessionOverrides(role_families=("Product Manager",)),
    )

    assert fake.goals == ["software_engineering", "product_management"]
    assert [item.fit_score for item in software.markets] == [0.80, 0.70]
    assert [item.fit_score for item in product.markets] == [0.80, 0.70]


def test_opportunity_volume_is_separate_and_cannot_change_fit(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    fake = _FakeMarketIntelligence(
        (
            _FakeItem("boston", "Greater Boston", 0.75),
            _FakeItem("seattle", "Greater Seattle", 0.70),
        )
    )
    service = ExploreFitService(session, market_intelligence=fake, clock=lambda: NOW)
    overrides = ExploreSessionOverrides(goal="software_engineering")
    before = service.evaluate("explicit_session_user", overrides)

    session.add_all(
        [_opportunity(f"boston_{index}", "greater_boston") for index in range(20)]
        + [_opportunity("seattle_1", "greater_seattle")]
    )
    session.flush()
    after = service.evaluate("explicit_session_user", overrides)

    before_fit = [(item.region.region_id, item.fit_score, item.rank) for item in before.markets]
    after_fit = [(item.region.region_id, item.fit_score, item.rank) for item in after.markets]
    assert after_fit == before_fit
    assert after.markets[0].opportunity_coverage.active_opportunity_count == 20
    assert after.markets[1].opportunity_coverage.active_opportunity_count == 1
    assert all(not item.opportunity_coverage.affects_explore_fit for item in after.markets)


def test_eight_market_evaluation_has_bounded_composition_queries(
    session: Session,
    monkeypatch,
) -> None:
    regions = []
    entries = {}
    items = []
    for index in range(8):
        region_id = f"market_region_{index}"
        market_key = f"market_{index}"
        regions.append(
            Region(
                region_id=region_id,
                region_name=market_key,
                display_name=f"Market {index}",
                region_type="metro",
                market_support_status="supported",
            )
        )
        entries[market_key] = SimpleNamespace(region_id=region_id)
        items.append(_FakeItem(market_key, f"Market {index}", 0.9 - index / 20))
    session.add_all(regions)
    session.flush()
    monkeypatch.setattr("backend.explore.service.load_market_registry", lambda: entries)
    statements: list[str] = []

    def track(_conn, _cursor, statement, _parameters, _context, _many):  # noqa: ANN001
        statements.append(statement)

    event.listen(session.bind, "before_cursor_execute", track)
    try:
        result = ExploreFitService(
            session,
            market_intelligence=_FakeMarketIntelligence(tuple(items)),
            clock=lambda: NOW,
        ).evaluate(
            "explicit_session_user",
            ExploreSessionOverrides(goal="software_engineering"),
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", track)

    assert len(result.markets) == 8
    assert [item.rank for item in result.markets] == list(range(1, 9))
    assert len(statements) <= 8


def test_real_eight_market_layer34_path_is_category_bounded(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=NOW.date()).ok
    assert run_all_curated_market_post_imports(session, as_of=NOW.date()).ok
    session.add(User(user_id="real_performance_user"))
    session.flush()
    statements: list[str] = []

    def track(_conn, _cursor, statement, _parameters, _context, _many):  # noqa: ANN001
        statements.append(statement)

    event.listen(session.bind, "before_cursor_execute", track)
    try:
        result = ExploreFitService(session, clock=lambda: NOW).evaluate(
            "real_performance_user",
            ExploreSessionOverrides(goal="software_engineering"),
            as_of=NOW.date(),
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", track)

    assert len(result.markets) == 8
    # The prior implementation executed 111 statements because it rebuilt each
    # market independently. The batched implementation has one bounded query
    # family per data category, plus Explore composition/measurement queries.
    assert len(statements) <= 45, statements
    assert max(Counter(statements).values()) < 8


def test_explore_api_requires_auth_and_does_not_echo_unconsented_facts(
    api_client,
    session: Session,
) -> None:
    assert api_client.get("/me/explore/context").status_code == 401
    headers = _auth_headers("auth0|explore_api")
    user_id = _current_user_id(api_client, "auth0|explore_api")
    session.add(
        CareerIdentity(
            career_identity_id="identity_explore_api",
            user_id=user_id,
            current_version=1,
            downstream_personalization_consent_granted=False,
        )
    )
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="private_role_explore_api",
            career_identity_id="identity_explore_api",
            user_id=user_id,
            fact_type="role_preference",
            normalized_key="private-role",
            state="explicit",
            payload={"role_title": "Private Secret Role"},
            provenance={},
        )
    )
    session.flush()

    response = api_client.get("/me/explore/context", headers=headers)
    assert response.status_code == 200
    text = json.dumps(response.json())
    assert "Private Secret Role" not in text
    assert response.json()["data"]["personalization_consent"] is False

    other_headers = _auth_headers("auth0|explore_api_other")
    other_user_id = _current_user_id(api_client, "auth0|explore_api_other")
    session.add(
        CareerIdentity(
            career_identity_id="identity_explore_api_other",
            user_id=other_user_id,
            current_version=1,
            downstream_personalization_consent_granted=False,
        )
    )
    session.flush()
    other = api_client.get("/me/explore/context", headers=other_headers)
    assert other.status_code == 200
    assert other.json()["data"]["career_identity_id"] == "identity_explore_api_other"
    assert (
        other.json()["data"]["career_identity_id"]
        != (response.json()["data"]["career_identity_id"])
    )


def test_explore_api_real_layer34_general_and_detail_contract(api_client) -> None:
    headers = _auth_headers("auth0|explore_real_facade")
    _current_user_id(api_client, "auth0|explore_real_facade")

    evaluated = api_client.post("/me/explore/markets", headers=headers, json={})
    assert evaluated.status_code == 200
    payload = evaluated.json()["data"]
    assert payload["authority"] == "explore_fit"
    assert payload["context"]["personalization_state"] == ("general_market_intelligence")
    assert len(payload["markets"]) == 8
    assert all(
        market["state"] in {"general_market_intelligence", "unsupported"}
        and market["fit_score"] is None
        and market["rank"] is None
        for market in payload["markets"]
    )

    detail = api_client.post(
        "/me/explore/markets/boston",
        headers=headers,
        json={},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["market"]["market_key"] == "boston"

    unknown = api_client.post(
        "/me/explore/markets/not-a-known-region",
        headers=headers,
        json={},
    )
    assert unknown.status_code == 404


def test_authority_dependency_graph_and_career_agent_adapter() -> None:
    service_text = Path("backend/explore/service.py").read_text()
    forbidden = (
        "backend.personalization",
        "backend.recommendations",
        "backend.user_intelligence",
        "backend.opportunities.routing",
        "backend.career_agent.service",
    )
    assert not any(name in service_text for name in forbidden)

    expected = SimpleNamespace(authority="explore_fit")

    class Stub:
        def evaluate(self, user_id, overrides, *, as_of=None):  # noqa: ANN001, ANN201
            assert user_id == "user"
            return expected

    assert CareerAgentAuthorityAdapter(Stub()).geographic_fit("user") is expected


@pytest.mark.parametrize("path", ("/career-agent/answers", "/me/career-agent/answers"))
@pytest.mark.parametrize(
    ("question_type", "expected_authority"),
    (
        (CareerAgentQuestionType.WHERE_SHOULD_I_APPLY, "layer38"),
        (CareerAgentQuestionType.CITY_FIT, "explore"),
        (CareerAgentQuestionType.COMPANIES_TO_WATCH, "unavailable"),
        (CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY, "explore"),
        (CareerAgentQuestionType.WHAT_SHOULD_I_DO_THIS_MONTH, "decision"),
    ),
)
def test_every_production_career_agent_question_type_is_explicitly_authoritative(
    api_client,
    monkeypatch,
    path: str,
    question_type: CareerAgentQuestionType,
    expected_authority: str,
) -> None:
    subject = f"auth0|career_agent_matrix_{path.split('/')[1]}_{question_type.value}"
    headers = _auth_headers(subject)
    _current_user_id(api_client, subject)
    calls = Counter()
    original_geographic_fit = CareerAgentAuthorityAdapter.geographic_fit

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        calls["legacy"] += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    def geographic_fit(self, user_id, overrides=None, *, as_of=None):  # noqa: ANN001, ANN201
        calls["explore"] += 1
        return original_geographic_fit(self, user_id, overrides, as_of=as_of)

    def current_job_matches(
        self,
        user_id,
        *,
        request_terms=(),
        limit=100,
        as_of=None,  # noqa: ANN001, ANN201
    ):
        calls["layer38"] += 1
        return ()

    def current_job_coverage(
        self,
        *,
        market_key,
        role_family,
        opportunity_type="*",
        as_of=None,  # noqa: ANN001, ANN201
    ):
        calls["layer38_coverage"] += 1
        return None

    def durable_decision(self, user_id):  # noqa: ANN001, ANN201
        calls["decision"] += 1
        return None, None, None

    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    monkeypatch.setattr(CareerAgentAuthorityAdapter, "geographic_fit", geographic_fit)
    monkeypatch.setattr(CareerAgentAuthorityAdapter, "current_job_matches", current_job_matches)
    monkeypatch.setattr(CareerAgentAuthorityAdapter, "current_job_coverage", current_job_coverage)
    monkeypatch.setattr(CareerAgentAuthorityAdapter, "durable_decision", durable_decision)

    response = api_client.post(
        path,
        headers=headers,
        json={
            "question_type": question_type.value,
            "target_role_families": ["software_engineering"],
            "include_forecasts": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["question_type"] == question_type.value
    assert calls["legacy"] == 0
    assert calls[expected_authority] == (0 if expected_authority == "unavailable" else 1)
    if expected_authority == "unavailable":
        assert "not yet available through the authoritative Career Agent path" in " ".join(
            response.json()["data"]["limitations"]
        )
        assert sum(calls.values()) == 0


def test_production_career_agent_unknown_question_fails_validation_without_legacy(
    api_client,
    monkeypatch,
) -> None:
    headers = _auth_headers("auth0|career_agent_unknown_question")
    _current_user_id(api_client, "auth0|career_agent_unknown_question")
    legacy_calls = 0

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        "/me/career-agent/answers",
        headers=headers,
        json={"question_type": "future_unassigned_question"},
    )

    assert response.status_code == 422
    assert legacy_calls == 0


@pytest.mark.parametrize("path", ("/career-agent/answers", "/me/career-agent/answers"))
def test_production_career_agent_geography_delegates_to_explore(
    api_client,
    monkeypatch,
    path: str,
) -> None:
    headers = _auth_headers("auth0|career_agent_explore_authority")
    _current_user_id(api_client, "auth0|career_agent_explore_authority")
    calls: list[str] = []
    legacy_calls = 0
    original = CareerAgentAuthorityAdapter.geographic_fit

    def spy(self, user_id, overrides=None, *, as_of=None):  # noqa: ANN001, ANN201
        calls.append(user_id)
        return original(self, user_id, overrides, as_of=as_of)

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    monkeypatch.setattr(CareerAgentAuthorityAdapter, "geographic_fit", spy)
    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        path,
        headers=headers,
        json={
            "question_type": "city_fit",
            "target_region_ids": ["greater_boston"],
            "target_role_families": ["software_engineering"],
            "include_forecasts": False,
        },
    )
    assert response.status_code == 200
    assert len(calls) == 1
    assert legacy_calls == 0
    assert "Explore Fit / Layer 34" in response.json()["data"]["summary"]


def test_production_career_agent_explore_failure_is_bounded_without_legacy(
    api_client,
    monkeypatch,
) -> None:
    headers = _auth_headers("auth0|career_agent_explore_failure")
    _current_user_id(api_client, "auth0|career_agent_explore_failure")
    legacy_calls = 0

    def failing_explore(self, user_id, overrides=None, *, as_of=None):  # noqa: ANN001, ANN201
        raise RuntimeError("forced Explore Fit failure")

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    monkeypatch.setattr(CareerAgentAuthorityAdapter, "geographic_fit", failing_explore)
    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        "/me/career-agent/answers",
        headers=headers,
        json={"question_type": "city_fit", "include_forecasts": False},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["recommendations"] == []
    assert "Explore Fit is temporarily unavailable" in " ".join(body["limitations"])
    assert legacy_calls == 0


def test_production_career_agent_job_question_uses_layer38_or_reports_coverage(
    api_client,
    monkeypatch,
) -> None:
    headers = _auth_headers("auth0|career_agent_jobs_authority")
    _current_user_id(api_client, "auth0|career_agent_jobs_authority")
    calls: list[str] = []

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        calls.append("legacy")
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    def matches(  # noqa: ANN001, ANN201
        self, user_id, *, request_terms=(), limit=100, as_of=None
    ):
        calls.append(f"matches:{user_id}:{limit}")
        assert "software_engineering" in request_terms
        return ()

    def coverage(  # noqa: ANN001, ANN201
        self, *, market_key, role_family, opportunity_type="*", as_of=None
    ):
        calls.append(f"coverage:{market_key}:{role_family}:{opportunity_type}")
        return SimpleNamespace(
            effective_status=SimpleNamespace(value="unsupported"),
            limitations=("No governed Layer 38 coverage contract is available.",),
        )

    monkeypatch.setattr(CareerAgentAuthorityAdapter, "current_job_matches", matches)
    monkeypatch.setattr(CareerAgentAuthorityAdapter, "current_job_coverage", coverage)
    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        "/me/career-agent/answers",
        headers=headers,
        json={
            "question_type": "where_should_i_apply",
            "target_region_ids": ["greater_boston"],
            "target_role_families": ["software_engineering"],
            "include_forecasts": False,
        },
    )
    assert response.status_code == 200
    assert any(item.startswith("matches:") for item in calls)
    assert any(item.startswith("coverage:") for item in calls)
    body = response.json()["data"]
    assert body["recommendations"] == []
    assert "no current jobs were invented" in " ".join(body["limitations"])
    assert "legacy" not in calls


def test_production_career_agent_next_step_uses_layer36_and_layer37(
    api_client,
    monkeypatch,
) -> None:
    headers = _auth_headers("auth0|career_agent_decision_authority")
    _current_user_id(api_client, "auth0|career_agent_decision_authority")
    legacy_calls = 0
    now = NOW
    decision = SimpleNamespace(
        decision_id="decision_authority",
        status="decided",
        title="Choose Boston product path",
        planned_review_at=now,
        updated_at=now,
    )
    recommendation = SimpleNamespace(
        summary="Layer 36 selected the recorded product path.",
        confidence="high",
        limitations=[],
    )
    review = SimpleNamespace(suggested_next_actions=["Review Layer 37 risk findings."])

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (decision, recommendation, review),
    )
    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        "/me/career-agent/answers",
        headers=headers,
        json={
            "question_type": "what_should_i_do_this_month",
            "include_forecasts": False,
        },
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["recommendations"][0]["recommendation_type"] == ("layer_36_durable_decision")
    assert body["recommendations"][0]["action"] == "Review Layer 37 risk findings."
    assert "Layer 36 durable Decision with Layer 37 analysis" in body["summary"]
    assert legacy_calls == 0


def test_production_career_agent_next_step_without_decision_does_not_rescore_markets(
    api_client,
    monkeypatch,
) -> None:
    headers = _auth_headers("auth0|career_agent_no_decision")
    _current_user_id(api_client, "auth0|career_agent_no_decision")
    legacy_calls = 0

    def forbidden_legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("production Career Agent route invoked the legacy scorer")

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (None, None, None),
    )
    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy_answer)
    response = api_client.post(
        "/me/career-agent/answers",
        headers=headers,
        json={
            "question_type": "what_should_i_do_this_month",
            "include_forecasts": False,
        },
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["recommendations"] == []
    assert "did not create a competing market recommendation" in " ".join(body["limitations"])
    assert legacy_calls == 0


def test_internal_legacy_career_agent_route_deliberately_invokes_legacy_service(
    api_client,
    monkeypatch,
) -> None:
    legacy_calls = 0
    original_answer = CareerAgentGroundingService.answer

    def legacy_answer(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        return original_answer(self, request, now=now)

    def forbidden_authoritative_answer(
        self,
        user_id,
        request,
        *,
        now=None,  # noqa: ANN001, ANN201
    ):
        raise AssertionError("internal legacy route invoked authoritative dispatch")

    monkeypatch.setattr(CareerAgentGroundingService, "answer", legacy_answer)
    monkeypatch.setattr(
        CareerAgentGroundingService,
        "answer_authoritative",
        forbidden_authoritative_answer,
    )
    response = api_client.post(
        "/internal/legacy/career-agent/answers",
        json={
            "question_type": "city_fit",
            "target_region_ids": ["missing_region"],
            "include_forecasts": False,
        },
    )

    assert response.status_code == 200
    assert legacy_calls == 1


def _authoritative_explore_response(*, markets: bool = True):  # noqa: ANN201
    market = SimpleNamespace(
        state=ExploreFitState.CONFIDENT,
        region=SimpleNamespace(
            region_id="greater_boston",
            display_name="Greater Boston",
        ),
        freshness="current",
        confidence="high",
        fit_score=0.81,
        fit_band="strong_fit",
        rank=1,
        market_coverage=SimpleNamespace(
            summary="Governed Layer 34 evidence.",
            evidence_areas_used=("hiring_activity",),
        ),
        material_limitations=(),
    )
    return SimpleNamespace(markets=(market,) if markets else (), limitations=())


def _authoritative_current_match():  # noqa: ANN201
    opportunity = SimpleNamespace(
        opportunity_id="current_opp_authority",
        company_name="Authority Company",
        original_title="Software Engineer I",
        role_family="software_engineering",
        market_id="greater_boston",
        freshness_state=SimpleNamespace(value="fresh"),
        last_observed_at=NOW,
        identity_confidence=SimpleNamespace(value="high"),
        provenance={"source_count": 1},
        application_url="https://example.com/apply/current-authority",
        source_url="https://example.com/jobs/current-authority",
    )
    return SimpleNamespace(
        opportunity=opportunity,
        match_score=0.9,
        strategic_relevance="high",
        contributing_factors=("Layer 38 governed match.",),
        limitations=(),
        warnings=(),
    )


def _regional_plan_request() -> CareerActionPlanRequest:
    return CareerActionPlanRequest(
        plan_type=CareerPlanType.REGIONAL_TARGETING_PLAN,
        career_agent_request=CareerAgentRequest(
            question_type=CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY,
            target_role_families=("software_engineering",),
            include_forecasts=False,
        ),
    )


@pytest.mark.parametrize(
    ("path", "payload", "authenticated"),
    (
        (
            "/career-agent/answers",
            {
                "question_type": "strongest_market_strategy",
                "target_role_families": ["software_engineering"],
                "include_forecasts": False,
            },
            True,
        ),
        (
            "/me/career-agent/answers",
            {
                "question_type": "strongest_market_strategy",
                "target_role_families": ["software_engineering"],
                "include_forecasts": False,
            },
            True,
        ),
        (
            "/career-agent/action-plans",
            _regional_plan_request().model_dump(mode="json"),
            False,
        ),
        (
            "/me/career-agent/action-plans",
            _regional_plan_request().model_dump(mode="json"),
            True,
        ),
        (
            "/me/career-agent/tools/preview",
            CareerAgentToolRequest(
                tool_type=CareerAgentToolType.REMINDER,
                career_agent_request=CareerAgentRequest(
                    question_type=CareerAgentQuestionType.CITY_FIT,
                    target_role_families=("software_engineering",),
                    include_forecasts=False,
                ),
            ).model_dump(mode="json"),
            True,
        ),
        (
            "/me/career-agent/tools/preview",
            CareerAgentToolRequest(
                tool_type=CareerAgentToolType.REMINDER,
                action_plan_request=_regional_plan_request(),
            ).model_dump(mode="json"),
            True,
        ),
    ),
)
def test_all_production_intelligence_routes_have_zero_legacy_calls(
    api_client,
    monkeypatch,
    path: str,
    payload: dict,
    authenticated: bool,
) -> None:
    legacy_calls = 0

    def forbidden_legacy(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("normal production route reached the legacy scorer")

    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy)
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (None, None, None),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "geographic_fit",
        lambda self, user_id, overrides=None, as_of=None: _authoritative_explore_response(),
    )
    headers = None
    if authenticated:
        subject = f"auth0|route_guard_{path.replace('/', '_')}"
        headers = _auth_headers(subject)
        _current_user_id(api_client, subject)

    response = api_client.post(path, headers=headers, json=payload)

    assert response.status_code == 200, response.text
    assert legacy_calls == 0


def test_action_plan_authority_modes_and_fail_closed_behavior(
    session: Session,
    monkeypatch,
) -> None:
    legacy_calls = 0

    def forbidden_legacy(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("action planning reached the legacy scorer")

    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy)
    service = CareerActionPlanningService(session)
    decision = SimpleNamespace(
        decision_id="decision_plan_authority",
        status="decided",
        title="Prioritize Boston",
        planned_review_at=NOW,
        updated_at=NOW,
    )
    recommendation = SimpleNamespace(
        summary="Layer 36 prioritizes the recorded Boston path.",
        confidence="high",
        limitations=[],
    )
    review = SimpleNamespace(suggested_next_actions=["Review Layer 37 risks."])
    decision_action = SimpleNamespace(
        action_id="decision_action_authority",
        title="Review Boston opportunities",
        description="Inspect covered Layer 38 opportunities for the recorded Decision.",
        updated_at=NOW,
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (decision, recommendation, review),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision_actions",
        lambda self, user_id, decision_id, limit=20: (decision_action,),
    )
    durable = service.generate_plan(_regional_plan_request(), user_id="planning_user", now=NOW)
    assert durable.evidence_refs[0].data_basis == "layer_36_durable_decision"
    assert {ref.data_basis for ref in durable.evidence_refs} == {
        "layer_36_durable_decision",
        "layer_36_durable_decision_action",
    }
    assert "Layer 37" in durable.steps[0].description

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (None, None, None),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "geographic_fit",
        lambda self, user_id, overrides=None, as_of=None: _authoritative_explore_response(),
    )
    explore = service.generate_plan(_regional_plan_request(), user_id="planning_user", now=NOW)
    assert explore.evidence_refs[0].data_basis == "layer_34_market_intelligence"

    current_request = CareerActionPlanRequest(
        plan_type=CareerPlanType.INTERNSHIP_APPLICATION_CALENDAR,
        career_agent_request=CareerAgentRequest(
            question_type=CareerAgentQuestionType.WHERE_SHOULD_I_APPLY,
            target_role_families=("software_engineering",),
            include_forecasts=False,
        ),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "current_job_matches",
        lambda self, user_id, request_terms=(), limit=100, as_of=None: (
            _authoritative_current_match(),
        ),
    )
    current = service.generate_plan(current_request, user_id="planning_user", now=NOW)
    assert current.evidence_refs[0].data_basis == "layer_38_current_opportunities"

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "geographic_fit",
        lambda self, user_id, overrides=None, as_of=None: _authoritative_explore_response(
            markets=False
        ),
    )
    with pytest.raises(CareerAgentGuardrailViolation, match="Action plan unavailable"):
        service.generate_plan(_regional_plan_request(), user_id="planning_user", now=NOW)

    def failing_plan_explore(  # noqa: ANN001, ANN201
        self, user_id, overrides=None, *, as_of=None
    ):
        raise RuntimeError("forced Explore planning dependency failure")

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "geographic_fit",
        failing_plan_explore,
    )
    with pytest.raises(CareerAgentGuardrailViolation, match="Explore Fit"):
        service.generate_plan(_regional_plan_request(), user_id="planning_user", now=NOW)

    def failing_decision(self, user_id):  # noqa: ANN001, ANN201
        raise RuntimeError("forced Layer 36/37 dependency failure")

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        failing_decision,
    )
    with pytest.raises(CareerAgentGuardrailViolation, match="Durable Decision"):
        service.generate_plan(_regional_plan_request(), user_id="planning_user", now=NOW)

    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (None, None, None),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "current_job_matches",
        lambda self, user_id, request_terms=(), limit=100, as_of=None: (),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "current_job_coverage",
        lambda self, market_key, role_family, opportunity_type="*", as_of=None: SimpleNamespace(
            effective_status=SimpleNamespace(value="unavailable"),
            limitations=("Layer 38 coverage dependency is unavailable.",),
        ),
    )
    with pytest.raises(CareerAgentGuardrailViolation, match="Layer 38"):
        service.generate_plan(current_request, user_id="planning_user", now=NOW)
    assert legacy_calls == 0


def test_tool_preview_authority_nested_planning_and_failures(
    session: Session,
    monkeypatch,
) -> None:
    session.add(User(user_id="tool_authority_user"))
    session.flush()
    legacy_calls = 0

    def forbidden_legacy(self, request, *, now=None):  # noqa: ANN001, ANN201
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("tool preview reached the legacy scorer")

    monkeypatch.setattr(CareerAgentGroundingService, "answer", forbidden_legacy)
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "durable_decision",
        lambda self, user_id: (None, None, None),
    )
    monkeypatch.setattr(
        CareerAgentAuthorityAdapter,
        "geographic_fit",
        lambda self, user_id, overrides=None, as_of=None: _authoritative_explore_response(),
    )
    service = CareerAgentToolService(session)
    direct = service.preview_tool(
        "tool_authority_user",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.REMINDER,
            career_agent_request=CareerAgentRequest(
                question_type=CareerAgentQuestionType.CITY_FIT,
                target_role_families=("software_engineering",),
                include_forecasts=False,
            ),
        ),
        now=NOW,
    )
    assert direct.source_answer_id is not None
    nested = service.preview_tool(
        "tool_authority_user",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.REMINDER,
            action_plan_request=_regional_plan_request(),
        ),
        now=NOW,
    )
    assert nested.source_plan_id is not None

    def failing_explore(self, user_id, overrides=None, *, as_of=None):  # noqa: ANN001, ANN201
        raise RuntimeError("forced Explore dependency failure")

    monkeypatch.setattr(CareerAgentAuthorityAdapter, "geographic_fit", failing_explore)
    with pytest.raises(CareerAgentGuardrailViolation, match="Tool preview unavailable"):
        service.preview_tool(
            "tool_authority_user",
            CareerAgentToolRequest(
                tool_type=CareerAgentToolType.REMINDER,
                career_agent_request=CareerAgentRequest(
                    question_type=CareerAgentQuestionType.CITY_FIT,
                    target_role_families=("software_engineering",),
                ),
            ),
            now=NOW,
        )
    with pytest.raises(CareerAgentGuardrailViolation, match="Tool preview unavailable"):
        service.preview_tool(
            "tool_authority_user",
            CareerAgentToolRequest(
                tool_type=CareerAgentToolType.REMINDER,
                career_agent_request=CareerAgentRequest(
                    question_type=CareerAgentQuestionType.COMPANIES_TO_WATCH,
                ),
            ),
            now=NOW,
        )
    assert legacy_calls == 0


def test_explore_records_only_high_value_privacy_safe_measurement(
    session: Session,
    monkeypatch,
) -> None:
    _seed_regions(session)
    session.add(User(user_id="measured_user"))
    session.flush()
    monkeypatch.setattr("backend.explore.service.load_market_registry", _registry)
    result = ExploreFitService(
        session,
        market_intelligence=_FakeMarketIntelligence(
            (
                _FakeItem("boston", "Greater Boston", 0.80),
                _FakeItem("seattle", "Greater Seattle", 0.70),
            )
        ),
        clock=lambda: NOW,
    ).evaluate(
        "measured_user",
        ExploreSessionOverrides(goal="software_engineering"),
    )

    events = session.query(ProductAnalyticsEvent).order_by(
        ProductAnalyticsEvent.created_at,
        ProductAnalyticsEvent.event_id,
    )
    rows = events.all()
    assert [row.event_type for row in rows] == [
        "explore_context_evaluated",
        "explore_fit_generated",
    ]
    serialized = json.dumps([row.payload for row in rows])
    assert result.context.context_fingerprint in serialized
    assert "resume" not in serialized


def test_session_override_request_contract_is_ephemeral() -> None:
    request = ExploreMarketsRequest(
        session_overrides=ExploreSessionOverrides(
            goal="software_engineering",
            industries=("AI",),
        )
    )
    assert request.session_overrides.industries == ("AI",)
