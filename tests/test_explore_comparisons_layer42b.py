from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from backend.career_decisions.models import CareerDecision
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.current_opportunities.models import CurrentOpportunity
from backend.explore.comparison_service import ExploreComparisonService
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.explore.schemas import (
    ExploreComparisonRequest,
    ExploreSessionOverrides,
    GeographicScopeInput,
    PrioritizeExploreComparisonRequest,
    SaveExploreComparisonRequest,
)
from backend.explore.service import ExploreFitService
from backend.geography.models import Region
from backend.market_intelligence.schemas import (
    ContradictionCode,
    ContradictionFinding,
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceSufficiency,
    IntelligenceConfidence,
    IntelligenceFreshness,
    RankingDriver,
)
from backend.product_measurement.models import ProductAnalyticsEvent, ProductUserVisit
from backend.users.models import User
from backend.users.repository import UserRepository
from backend.users.service import UserPersonalizationPersistenceService
from tests.test_api_user_routes import _auth_headers, _current_user_id

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)

MARKETS = (
    ("boston", "greater_boston", "boston", "Greater Boston"),
    ("nyc", "greater_nyc", "new-york", "Greater New York"),
    ("sf", "sf_bay_area", "san-francisco-bay-area", "San Francisco Bay Area"),
    ("seattle", "greater_seattle", "seattle", "Greater Seattle"),
)


@dataclass(frozen=True)
class FakeItem:
    market_key: str
    market_name: str
    score: float
    driver_code: str
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.COMPARISON_READY
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH
    freshness: IntelligenceFreshness = IntelligenceFreshness.CURRENT
    contradiction_status: ContradictionStatus = ContradictionStatus.CLEAR
    abstention_reason: str | None = None
    limitations: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ("A governed tradeoff is present.",)
    contradictions: tuple[ContradictionFinding, ...] = ()
    grounding: Any = None

    @property
    def ranking_drivers(self) -> tuple[RankingDriver, ...]:
        return (
            RankingDriver(
                code=self.driver_code,
                label=self.driver_code.replace("_", " ").title(),
                contribution=self.score,
                evidence=f"Governed {self.driver_code.replace('_', ' ')} evidence.",
            ),
        )

    @property
    def supporting_metrics(self) -> dict[str, Any]:
        return {"ranking_eligible_fact_count": 4, "unknown_fact_count": 0}


class FakeRanking:
    def __init__(self, items: tuple[FakeItem, ...]) -> None:
        self.ranked_markets = items
        self.limitations = ()
        self.contradictions = tuple(finding for item in items for finding in item.contradictions)
        self.contradiction_status = (
            ContradictionStatus.BLOCKING
            if any(item.contradiction_status is ContradictionStatus.BLOCKING for item in items)
            else ContradictionStatus.CLEAR
        )
        self.abstention_reason = (
            "Blocking governed contradiction."
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


class FakeMarketIntelligence:
    def __init__(self, items: tuple[FakeItem, ...]) -> None:
        self.items = items
        self.calls = 0

    def ranking(self, *, goal: str, as_of=None):  # noqa: ANN001, ANN201
        self.calls += 1
        return FakeRanking(self.items)


def _items(
    scores: tuple[float, float, float, float] = (0.80, 0.72, 0.65, 0.58),
) -> tuple[FakeItem, ...]:
    drivers = ("ai_employer_strength", "employer_breadth", "hiring_breadth", "entry_access")
    return tuple(
        FakeItem(market_key, name, score, driver)
        for (market_key, _region_id, _slug, name), score, driver in zip(
            MARKETS, scores, drivers, strict=True
        )
    )


def _seed_user_identity(session: Session, user_id: str) -> None:
    session.add(User(user_id=user_id))
    session.flush()
    session.add(
        CareerIdentity(
            career_identity_id=f"identity_{user_id}",
            user_id=user_id,
            current_version=1,
            downstream_personalization_consent_granted=True,
        )
    )
    session.add(
        CareerIdentityFact(
            career_identity_fact_id=f"role_{user_id}",
            career_identity_id=f"identity_{user_id}",
            user_id=user_id,
            fact_type="role_preference",
            normalized_key="role:software",
            state="explicit",
            payload={"role_title": "Software Engineer", "preference_kind": "preferred"},
            provenance={},
        )
    )
    session.flush()


def _seed_user_and_regions(session: Session, *, user_id: str = "compare_user") -> None:
    _seed_user_identity(session, user_id)
    for _market_key, region_id, slug, display_name in MARKETS:
        session.add(
            Region(
                region_id=region_id,
                region_name=slug,
                display_name=display_name,
                region_type="greater_region",
                public_slug=slug,
                primary_city=display_name.replace("Greater ", ""),
                market_support_status="supported",
            )
        )
    session.flush()


def _service(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    items: tuple[FakeItem, ...],
) -> tuple[ExploreComparisonService, FakeMarketIntelligence]:
    monkeypatch.setattr(
        "backend.explore.service.load_market_registry",
        lambda: {
            market_key: type("Entry", (), {"region_id": region_id})()
            for market_key, region_id, _slug, _name in MARKETS
        },
    )
    intelligence = FakeMarketIntelligence(items)
    fit = ExploreFitService(session, market_intelligence=intelligence, clock=lambda: NOW)
    return ExploreComparisonService(session, fit_service=fit, clock=lambda: NOW), intelligence


def _request(*refs: str) -> ExploreComparisonRequest:
    return ExploreComparisonRequest(
        market_refs=refs,
        session_overrides={"goal": "software_engineering"},
    )


def test_true_n_way_comparison_is_order_invariant_and_supports_two_three_four(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    service, intelligence = _service(session, monkeypatch, _items())

    for evaluation_number, refs in enumerate(
        (
            ("boston", "new-york"),
            ("boston", "new-york", "san-francisco-bay-area"),
            ("boston", "new-york", "san-francisco-bay-area", "seattle"),
        ),
        start=1,
    ):
        result = service.compare("compare_user", _request(*refs))
        assert len(result.compared_markets) == len(refs)
        assert result.winner_region_ids == ("greater_boston",)
        assert intelligence.calls == evaluation_number

    forward = service.compare("compare_user", _request("boston", "new-york", "seattle"))
    reverse = service.compare("compare_user", _request("seattle", "new-york", "boston"))
    assert forward.comparison_identity == reverse.comparison_identity
    assert forward.recommendation_state == reverse.recommendation_state
    assert forward.winner_region_ids == reverse.winner_region_ids
    assert [item.fit.region.region_id for item in forward.compared_markets] != [
        item.fit.region.region_id for item in reverse.compared_markets
    ]


def test_governed_near_tie_exact_tie_and_abstention(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    near_service, _ = _service(session, monkeypatch, _items((0.80, 0.795, 0.65, 0.58)))
    near = near_service.compare("compare_user", _request("boston", "new-york", "seattle"))
    assert near.recommendation_state == "near_tie"
    assert set(near.winner_region_ids) == {"greater_boston", "greater_nyc"}

    exact_service, _ = _service(session, monkeypatch, _items((0.80, 0.80, 0.65, 0.58)))
    exact = exact_service.compare("compare_user", _request("boston", "new-york"))
    assert exact.recommendation_state == "exact_tie"
    assert exact.tied_region_ids == ("greater_boston", "greater_nyc")

    insufficient_items = tuple(
        replace(item, evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT_EVIDENCE)
        for item in _items()
    )
    insufficient_service, _ = _service(session, monkeypatch, insufficient_items)
    insufficient = insufficient_service.compare("compare_user", _request("boston", "new-york"))
    assert insufficient.recommendation_state == "insufficient_evidence"
    assert insufficient.winner_region_ids == ()
    assert insufficient.abstained is True

    finding = ContradictionFinding(
        code=ContradictionCode.HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE,
        severity=ContradictionSeverity.BLOCKING,
        message="Conflicting governed evidence.",
        evidence="Fixture contradiction.",
        blocks_recommendation=True,
    )
    contradiction_items = (
        replace(
            _items()[0],
            contradiction_status=ContradictionStatus.BLOCKING,
            contradictions=(finding,),
            abstention_reason="Blocking contradiction.",
        ),
        *_items()[1:],
    )
    blocked_service, _ = _service(session, monkeypatch, contradiction_items)
    blocked = blocked_service.compare("compare_user", _request("boston", "new-york"))
    assert blocked.recommendation_state == "blocking_contradiction"
    assert blocked.winner_region_ids == ()


def test_known_unsupported_and_hard_excluded_members_are_never_silently_dropped(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    session.add(
        Region(
            region_id="greater_austin",
            region_name="austin",
            display_name="Greater Austin",
            region_type="greater_region",
            public_slug="austin",
            market_support_status="unsupported",
        )
    )
    session.flush()
    service, _ = _service(session, monkeypatch, _items())

    unsupported = service.compare("compare_user", _request("boston", "austin"))
    assert unsupported.recommendation_state == "unsupported_member"
    assert unsupported.winner_region_ids == ()
    assert [market.fit.state for market in unsupported.compared_markets] == [
        "confident",
        "unsupported",
    ]

    outside = service.compare(
        "compare_user",
        ExploreComparisonRequest(
            market_refs=("boston", "new-york"),
            session_overrides=ExploreSessionOverrides(
                goal="software_engineering",
                geographic_scope=GeographicScopeInput(excluded_region_refs=("new-york",)),
            ),
        ),
    )
    assert outside.recommendation_state == "outside_constraints"
    assert outside.winner_region_ids == ()
    assert outside.abstained is True

    with pytest.raises(ValueError, match="unique canonical Regions"):
        service.compare("compare_user", _request("boston", "greater_boston"))


def test_opportunity_inventory_changes_only_supporting_coverage(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    service, _ = _service(session, monkeypatch, _items())
    before = service.compare("compare_user", _request("boston", "new-york"))
    session.add(
        CurrentOpportunity(
            current_opportunity_id="opp_boston_1",
            canonical_identity_key="fixture:boston:1",
            duplicate_group_key="fixture:boston",
            company_name="Example Co",
            original_title="Software Engineer",
            normalized_title="Software Engineer",
            role_family="software_engineering",
            seniority_level="entry_level",
            market_id="greater_boston",
            location_resolution_status="resolved",
            work_arrangement="hybrid",
            compensation_interval="unknown",
            employment_type="full_time",
            opportunity_type="job",
            normalization_confidence="high",
            identity_confidence="high",
            canonical_status="active",
            canonical_updated_at=NOW,
            freshness_state="fresh",
            ranking_eligible=True,
            source_count=1,
        )
    )
    session.flush()
    after = service.compare("compare_user", _request("boston", "new-york"))
    assert after.recommendation_state == before.recommendation_state
    assert after.winner_region_ids == before.winner_region_ids
    assert after.comparison_identity == before.comparison_identity
    assert after.opportunity_coverage["greater_boston"].active_opportunity_count == 1


def test_save_is_immutable_and_does_not_create_decision(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    service, _ = _service(session, monkeypatch, _items())
    live = service.compare("compare_user", _request("boston", "new-york"))
    saved = service.save(
        "compare_user",
        SaveExploreComparisonRequest(
            market_refs=("boston", "new-york"),
            session_overrides={"goal": "software_engineering"},
            comparison_identity=live.comparison_identity,
        ),
    )
    repeated = service.save(
        "compare_user",
        SaveExploreComparisonRequest(
            market_refs=("boston", "new-york"),
            session_overrides={"goal": "software_engineering"},
            comparison_identity=live.comparison_identity,
        ),
    )
    assert repeated.comparison_id == saved.comparison_id
    assert session.query(ExploreComparisonSnapshot).count() == 1
    assert session.query(CareerDecision).count() == 0

    changed_service, _ = _service(session, monkeypatch, _items((0.70, 0.82, 0.65, 0.58)))
    current = changed_service.compare("compare_user", _request("boston", "new-york"))
    historical = changed_service.get_saved("compare_user", saved.comparison_id)
    assert current.winner_region_ids == ("greater_nyc",)
    assert historical.result.winner_region_ids == ("greater_boston",)
    assert historical.result.comparison_identity == live.comparison_identity


def test_prioritize_creates_layer36_decision_preserves_override_and_is_duplicate_safe(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_user_and_regions(session)
    service, _ = _service(session, monkeypatch, _items())
    live = service.compare("compare_user", _request("boston", "new-york", "seattle"))
    saved = service.save(
        "compare_user",
        SaveExploreComparisonRequest(
            market_refs=("boston", "new-york", "seattle"),
            session_overrides={"goal": "software_engineering"},
            comparison_identity=live.comparison_identity,
        ),
    )
    request = PrioritizeExploreComparisonRequest(
        comparison_id=saved.comparison_id,
        selected_market_ref="new-york",
    )
    prioritized = service.prioritize("compare_user", request)
    repeated = service.prioritize("compare_user", request)

    assert prioritized.created is True
    assert repeated.created is False
    assert repeated.decision_id == prioritized.decision_id
    assert session.query(CareerDecision).count() == 1
    decision = session.get(CareerDecision, prioritized.decision_id)
    assert decision is not None and decision.status == "decided"
    provenance = session.query(ExploreDecisionProvenance).one()
    assert provenance.system_recommended_region_ids == ["greater_boston"]
    assert provenance.user_selected_region_id == "greater_nyc"
    assert provenance.choice_matches_recommendation is False
    assert (
        prioritized.decision["recommendation"]["recommended_option_id"]
        != decision.selected_option_id
    )
    event_types = {row.event_type for row in session.query(ProductAnalyticsEvent).all()}
    assert {
        "comparison_saved",
        "prioritize_initiated",
        "prioritize_completed",
        "comparison_recommendation_overridden",
    } <= event_types


def test_deactivation_removes_prioritized_comparison_measurement_graph_without_cross_user_damage(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_a = "comparison_privacy_a"
    user_b = "comparison_privacy_b"
    _seed_user_and_regions(session, user_id=user_a)
    _seed_user_identity(session, user_b)
    service, _ = _service(session, monkeypatch, _items())

    saved_by_user: dict[str, ExploreComparisonSnapshot] = {}
    decision_by_user: dict[str, str] = {}
    for user_id in (user_a, user_b):
        live = service.compare(user_id, _request("boston", "new-york"))
        saved = service.save(
            user_id,
            SaveExploreComparisonRequest(
                market_refs=("boston", "new-york"),
                session_overrides={"goal": "software_engineering"},
                comparison_identity=live.comparison_identity,
            ),
        )
        prioritized = service.prioritize(
            user_id,
            PrioritizeExploreComparisonRequest(
                comparison_id=saved.comparison_id,
                selected_market_ref="new-york",
            ),
        )
        saved_by_user[user_id] = saved
        decision_by_user[user_id] = prioritized.decision_id

    session.flush()
    for user_id in (user_a, user_b):
        event = (
            session.query(ProductAnalyticsEvent)
            .filter_by(user_id=user_id)
            .order_by(ProductAnalyticsEvent.created_at)
            .first()
        )
        assert event is not None
        session.add(
            ProductUserVisit(
                visit_id=f"visit_{user_id}",
                user_id=user_id,
                product_surface="explore_comparison",
                returned_event_id=event.event_id,
            )
        )
    session.flush()

    privacy = UserPersonalizationPersistenceService(UserRepository(session))
    exported = privacy.export_user_data(user_a)
    assert exported["explore_comparisons"]["snapshots"][0]["comparison_id"] == (
        saved_by_user[user_a].comparison_id
    )
    assert (
        exported["explore_comparisons"]["decision_provenance"][0]["decision_id"]
        == (decision_by_user[user_a])
    )

    result = privacy.deactivate_user_account(user_a)
    session.flush()
    assert result.user_status == "deactivated"
    assert session.get(User, user_a).status == "deactivated"
    assert session.query(ProductAnalyticsEvent).filter_by(user_id=user_a).count() == 0
    assert session.query(ProductUserVisit).filter_by(user_id=user_a).count() == 0
    assert session.query(ExploreComparisonSnapshot).filter_by(user_id=user_a).count() == 0
    assert session.query(ExploreDecisionProvenance).filter_by(user_id=user_a).count() == 0
    assert session.query(CareerDecision).filter_by(user_id=user_a).count() == 0

    assert session.get(User, user_b).status == "active"
    assert session.query(ProductAnalyticsEvent).filter_by(user_id=user_b).count() > 0
    assert session.query(ProductUserVisit).filter_by(user_id=user_b).count() == 1
    assert session.get(ExploreComparisonSnapshot, saved_by_user[user_b].comparison_id) is not None
    assert session.get(CareerDecision, decision_by_user[user_b]) is not None
    assert session.query(ExploreDecisionProvenance).filter_by(user_id=user_b).count() == 1


def test_saved_comparison_auth_and_ownership(
    api_client, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers_a = _auth_headers("auth0|comparison-a")
    headers_b = _auth_headers("auth0|comparison-b")
    assert api_client.get("/me", headers=headers_a).status_code == 200
    user_a = _current_user_id(api_client, "auth0|comparison-a")
    for _market_key, region_id, slug, display_name in MARKETS:
        session.add(
            Region(
                region_id=region_id,
                region_name=slug,
                display_name=display_name,
                region_type="greater_region",
                public_slug=slug,
                market_support_status="supported",
            )
        )
    session.add(
        CareerIdentity(
            career_identity_id="identity_api_comparison",
            user_id=user_a,
            current_version=1,
            downstream_personalization_consent_granted=True,
        )
    )
    session.add(
        CareerIdentityFact(
            career_identity_fact_id="role_api_comparison",
            career_identity_id="identity_api_comparison",
            user_id=user_a,
            fact_type="role_preference",
            normalized_key="role:software",
            state="explicit",
            payload={"role_title": "Software Engineer", "preference_kind": "preferred"},
            provenance={},
        )
    )
    session.flush()
    service, _ = _service(session, monkeypatch, _items())
    live = service.compare(user_a, _request("boston", "new-york"))
    saved = service.save(
        user_a,
        SaveExploreComparisonRequest(
            market_refs=("boston", "new-york"),
            session_overrides={"goal": "software_engineering"},
            comparison_identity=live.comparison_identity,
        ),
    )

    assert (
        api_client.get(
            f"/me/explore/comparisons/{saved.comparison_id}", headers=headers_a
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            f"/me/explore/comparisons/{saved.comparison_id}", headers=headers_b
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/me/explore/prioritize",
            headers=headers_b,
            json={"comparison_id": saved.comparison_id, "selected_market_ref": "boston"},
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/me/explore/comparisons",
            json={
                "market_refs": ["boston", "new-york"],
                "comparison_identity": live.comparison_identity,
            },
        ).status_code
        == 401
    )
