"""Authoritative Explore Fit composition over Layer 34 market evidence."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any, Protocol

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.career_identity.repository import CareerIdentityRepository
from backend.current_opportunities.models import (
    CurrentOpportunity,
    OpportunityCoverageContract,
)
from backend.explore.context import ExploreContextService
from backend.explore.schemas import (
    ExploreContext,
    ExploreFitResult,
    ExploreFitState,
    ExploreFitVersions,
    ExploreMarketsResponse,
    ExplorePersonalizationState,
    ExploreRegion,
    ExploreSessionOverrides,
    MarketEvidenceCoverage,
    OpportunityCoverage,
    RankingUniverse,
)
from backend.explore.shared_intelligence import SharedIntelligenceCoordinator
from backend.geography.models import Region, RegionStateMembership
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.imports.registry import load_market_registry
from backend.market_intelligence.calibration import scores_are_near_tie
from backend.market_intelligence.schemas import (
    ContradictionStatus,
    EvidenceSufficiency,
)
from backend.market_intelligence.service import MarketIntelligenceService
from backend.product_measurement.schemas import (
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
)
from backend.product_measurement.service import ProductMeasurementService

EXPLORE_FIT_ALGORITHM_VERSION = "explore_fit_v1"
MARKET_EVIDENCE_AUTHORITY_VERSION = "layer34_market_intelligence_34c"
FIT_CALIBRATION_VERSION = "explore_fit_bands_v1"

# Provisional presentation calibration over Layer 34's governed [0, 1] score.
# It never turns insufficient evidence into a score or a recommendation.
FIT_BAND_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.70, "strong_fit"),
    (0.50, "good_fit"),
    (0.00, "possible_fit"),
)


class _MarketIntelligence(Protocol):
    def ranking(self, *, goal: str, as_of: date | datetime | None = None) -> Any: ...

    def platform_summary(
        self,
        *,
        goal: str = "software_engineering",
        as_of: date | datetime | None = None,
    ) -> Any: ...


class ExploreFitService:
    """Compose user context and governed market evidence without rescoring it."""

    def __init__(
        self,
        session: Session,
        *,
        market_intelligence: _MarketIntelligence | None = None,
        shared_intelligence: SharedIntelligenceCoordinator | None = None,
        clock: callable | None = None,
    ) -> None:
        self._session = session
        self._region_repo = RegionRepository(session)
        self._context = ExploreContextService(
            CareerIdentityRepository(session),
            self._region_repo,
        )
        self._market_intelligence = market_intelligence or MarketIntelligenceService(session)
        self._shared_intelligence = shared_intelligence
        self._clock = clock or (lambda: datetime.now(UTC))

    def context(
        self,
        user_id: str,
        overrides: ExploreSessionOverrides | None = None,
    ) -> ExploreContext:
        return self._context.build(user_id, overrides)

    def evaluate(
        self,
        user_id: str,
        overrides: ExploreSessionOverrides | None = None,
        *,
        as_of: date | datetime | None = None,
    ) -> ExploreMarketsResponse:
        context = self.context(user_id, overrides)
        if (
            context.personalization_state
            in {
                ExplorePersonalizationState.PERSONALIZED,
            }
            and context.supported_goal
        ):
            response = self._personalized(context, as_of=as_of)
        else:
            response = self._general(context, as_of=as_of)
        self._record_measurement(user_id, response)
        return response

    def market_detail(
        self,
        user_id: str,
        market_ref: str,
        overrides: ExploreSessionOverrides | None = None,
        *,
        as_of: date | datetime | None = None,
    ) -> tuple[ExploreMarketsResponse, ExploreFitResult | None]:
        response = self.evaluate(user_id, overrides, as_of=as_of)
        normalized = market_ref.casefold().strip()
        resolution = GeographicResolver(self._region_repo).resolve(market_ref)
        resolved_region_id = resolution.region_id if resolution.resolved else None
        for market in response.markets:
            candidates = {
                market.market_key.casefold(),
                market.region.region_id.casefold(),
                (market.region.public_slug or "").casefold(),
            }
            if normalized in candidates or resolved_region_id == market.region.region_id:
                return response, market
        return response, None

    def selected_market_results(
        self,
        response: ExploreMarketsResponse,
        region_ids: tuple[str, ...],
    ) -> tuple[ExploreFitResult, ...]:
        """Return authoritative results for a canonical selected set without reevaluation.

        Known Regions outside the curated Layer 34 universe are represented as
        unsupported members instead of being silently dropped.
        """

        by_region = {market.region.region_id: market for market in response.markets}
        missing_ids = tuple(region_id for region_id in region_ids if region_id not in by_region)
        if missing_ids:
            metadata = self._region_metadata(missing_ids)
            opportunity = self._opportunity_coverage(
                missing_ids,
                goal=response.context.supported_goal,
                opportunity_types=response.context.effective_context.opportunity_types,
            )
            evidence_bundle = (
                response.markets[0].versions.market_evidence_bundle
                if response.markets
                else "sha256:" + ("0" * 64)
            )
            for index, region_id in enumerate(missing_ids, start=1):
                region = metadata.get(region_id)
                if region is None:
                    continue
                by_region[region_id] = self._unsupported_region_result(
                    region,
                    display_order=len(response.markets) + index,
                    context=response.context,
                    evidence_bundle=evidence_bundle,
                    opportunity=opportunity,
                )
        return tuple(by_region[region_id] for region_id in region_ids if region_id in by_region)

    def _personalized(
        self,
        context: ExploreContext,
        *,
        as_of: date | datetime | None,
    ) -> ExploreMarketsResponse:
        if self._shared_intelligence is None:
            ranking = self._market_intelligence.ranking(
                goal=context.supported_goal,
                as_of=as_of,
            )
        else:
            ranking = self._shared_intelligence.ranking(
                self._market_intelligence,
                goal=context.supported_goal,
                as_of=as_of,
            )
        entries = load_market_registry()
        region_ids_by_market = self._canonical_registry_regions(entries)
        region_ids = tuple(
            dict.fromkeys(
                region_ids_by_market[item.market_key]
                for item in ranking.ranked_markets
                if item.market_key in region_ids_by_market
            )
        )
        referenced_region_ids = _referenced_region_ids(context)
        all_region_ids = tuple(dict.fromkeys((*region_ids, *referenced_region_ids)))
        regions = self._region_metadata(all_region_ids)
        opportunity = self._opportunity_coverage(
            all_region_ids,
            goal=context.supported_goal,
            opportunity_types=context.effective_context.opportunity_types,
        )
        evidence_bundle = _evidence_bundle(ranking)
        ranking_contradiction = _contradiction_fields(ranking)
        drafts: list[dict[str, Any]] = []
        for item in ranking.ranked_markets:
            region_id = region_ids_by_market.get(item.market_key)
            if region_id is None:
                continue
            region = regions.get(region_id) or _missing_region(region_id, item.market_name)
            constraint_reasons = _hard_constraint_reasons(context, region)
            state, score, abstention = _fit_state(item, region, constraint_reasons)
            if ranking_contradiction["contradiction_blocking"] and state in {
                ExploreFitState.CONFIDENT,
                ExploreFitState.TENTATIVE,
            }:
                state = ExploreFitState.ABSTAINED
                score = None
                abstention = getattr(ranking, "abstention_reason", None) or (
                    "Layer 34 blocked the ranking because of a structured contradiction."
                )
            drafts.append(
                {
                    "item": item,
                    "region": region,
                    "state": state,
                    "score": score,
                    "abstention": abstention,
                    "constraint_reasons": constraint_reasons,
                    "contradiction": _contradiction_fields(
                        item,
                        *((ranking,) if ranking_contradiction["contradiction_blocking"] else ()),
                    ),
                }
            )
        evaluated_region_ids = {draft["region"].region_id for draft in drafts}
        additional_regions = tuple(
            regions[region_id]
            for region_id in referenced_region_ids
            if region_id in regions and region_id not in evaluated_region_ids
        )
        ranks = _eligible_ranks(drafts)
        score_regions = {
            draft["region"].region_id: draft["score"]
            for draft in drafts
            if draft["score"] is not None
            and draft["state"] in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
        }
        markets = tuple(
            self._personalized_result(
                draft,
                display_order=index,
                rank=ranks.get(draft["region"].region_id),
                score_regions=score_regions,
                context=context,
                evidence_bundle=evidence_bundle,
                opportunity=opportunity,
            )
            for index, draft in enumerate(drafts, start=1)
        )
        markets = (
            *markets,
            *(
                self._unsupported_region_result(
                    region,
                    display_order=len(markets) + index,
                    context=context,
                    evidence_bundle=evidence_bundle,
                    opportunity=opportunity,
                )
                for index, region in enumerate(additional_regions, start=1)
            ),
        )
        universe = _ranking_universe(context, tuple(market.region for market in markets))
        return ExploreMarketsResponse(
            context=context,
            ranking_universe=universe,
            markets=markets,
            evaluated_at=self._clock(),
            authority_version=EXPLORE_FIT_ALGORITHM_VERSION,
            **ranking_contradiction,
            limitations=tuple(dict.fromkeys((*context.limitations, *ranking.limitations))),
        )

    def _general(
        self,
        context: ExploreContext,
        *,
        as_of: date | datetime | None,
    ) -> ExploreMarketsResponse:
        if self._shared_intelligence is None:
            report = self._market_intelligence.platform_summary(as_of=as_of)
        else:
            report = self._shared_intelligence.platform_summary(
                self._market_intelligence,
                as_of=as_of,
            )
        entries = load_market_registry()
        region_ids_by_market = self._canonical_registry_regions(entries)
        region_ids = tuple(
            dict.fromkeys(
                region_ids_by_market[profile.market_key]
                for profile in report.profiles
                if profile.market_key in region_ids_by_market
            )
        )
        referenced_region_ids = _referenced_region_ids(context)
        all_region_ids = tuple(dict.fromkeys((*region_ids, *referenced_region_ids)))
        regions = self._region_metadata(all_region_ids)
        opportunity = self._opportunity_coverage(
            all_region_ids,
            goal=None,
            opportunity_types=context.effective_context.opportunity_types,
        )
        evidence_bundle = _evidence_bundle(report)
        report_contradiction = _contradiction_fields(report)
        markets: list[ExploreFitResult] = []
        for index, profile in enumerate(report.profiles, start=1):
            region_id = region_ids_by_market.get(profile.market_key)
            if region_id is None:
                continue
            region = regions.get(region_id) or _missing_region(
                region_id,
                profile.market_name,
            )
            limitations = tuple(dict.fromkeys((*profile.limitations, *context.limitations)))
            supported = region.market_support_status == "supported"
            constraint_reasons = _hard_constraint_reasons(context, region)
            if constraint_reasons:
                state = ExploreFitState.HARD_CONSTRAINT_EXCLUDED
                abstention_reason = "The market is outside the effective geographic scope."
            elif supported:
                state = ExploreFitState.GENERAL_MARKET_INTELLIGENCE
                abstention_reason = (
                    "Explore Context does not support a personalized governed goal; "
                    "this is general market intelligence, not your Fit."
                )
            else:
                state = ExploreFitState.UNSUPPORTED
                abstention_reason = (
                    "Canonical Region metadata does not mark this market as supported."
                )
            contradiction = _contradiction_fields(profile)
            markets.append(
                ExploreFitResult(
                    market_key=profile.market_key,
                    region=region,
                    state=state,
                    display_order=index,
                    confidence=profile.confidence.value,
                    evidence_sufficiency="not_personalized",
                    freshness=profile.freshness.value,
                    market_coverage=_profile_market_coverage(profile),
                    opportunity_coverage=opportunity.get(
                        region_id,
                        _empty_opportunity_coverage(),
                    ),
                    material_limitations=tuple(dict.fromkeys((*limitations, *constraint_reasons))),
                    abstention_reason=abstention_reason,
                    hard_constraint_reasons=constraint_reasons,
                    **contradiction,
                    evidence_hooks={
                        "market_intelligence_market_key": profile.market_key,
                        "supporting_metric_keys": tuple(sorted(profile.supporting_metrics)),
                    },
                    versions=_versions(context, evidence_bundle),
                )
            )
        evaluated_region_ids = {item.region.region_id for item in markets}
        for region_id in referenced_region_ids:
            if region_id in regions and region_id not in evaluated_region_ids:
                markets.append(
                    self._unsupported_region_result(
                        regions[region_id],
                        display_order=len(markets) + 1,
                        context=context,
                        evidence_bundle=evidence_bundle,
                        opportunity=opportunity,
                    )
                )
        universe = _ranking_universe(context, tuple(item.region for item in markets))
        return ExploreMarketsResponse(
            context=context,
            ranking_universe=universe,
            markets=tuple(markets),
            evaluated_at=self._clock(),
            authority_version=EXPLORE_FIT_ALGORITHM_VERSION,
            **report_contradiction,
            limitations=tuple(dict.fromkeys((*context.limitations, *report.limitations))),
        )

    def _personalized_result(
        self,
        draft: dict[str, Any],
        *,
        display_order: int,
        rank: int | None,
        score_regions: dict[str, float],
        context: ExploreContext,
        evidence_bundle: str,
        opportunity: dict[str, OpportunityCoverage],
    ) -> ExploreFitResult:
        item = draft["item"]
        region = draft["region"]
        score = draft["score"]
        tied = tuple(
            sorted(
                region_id
                for region_id, other_score in score_regions.items()
                if region_id != region.region_id and other_score == score
            )
        )
        near_ties = tuple(
            sorted(
                region_id
                for region_id, other_score in score_regions.items()
                if region_id != region.region_id
                and score is not None
                and scores_are_near_tie(other_score, score)
            )
        )
        limitations = tuple(
            dict.fromkeys(
                (
                    *item.limitations,
                    *draft["constraint_reasons"],
                    *(
                        ("This result is within Layer 34's near-tie threshold.",)
                        if near_ties
                        else ()
                    ),
                )
            )
        )
        return ExploreFitResult(
            market_key=item.market_key,
            region=region,
            state=draft["state"],
            fit_score=score,
            fit_band=_fit_band(score, item.evidence_sufficiency),
            rank=rank,
            display_order=display_order,
            tied_region_ids=tied,
            near_tie_region_ids=near_ties,
            primary_drivers=tuple(driver.as_dict() for driver in item.ranking_drivers),
            tradeoffs=tuple(item.weaknesses),
            confidence=item.confidence.value,
            evidence_sufficiency=item.evidence_sufficiency.value,
            freshness=item.freshness.value,
            market_coverage=_ranking_market_coverage(item),
            opportunity_coverage=opportunity.get(
                region.region_id,
                _empty_opportunity_coverage(),
            ),
            material_limitations=limitations,
            abstention_reason=draft["abstention"],
            hard_constraint_reasons=draft["constraint_reasons"],
            **draft["contradiction"],
            evidence_hooks={
                "market_intelligence_market_key": item.market_key,
                "driver_codes": tuple(driver.code for driver in item.ranking_drivers),
                "supporting_metric_keys": tuple(sorted(item.supporting_metrics)),
                "grounding": item.grounding.as_dict() if item.grounding else None,
            },
            versions=_versions(context, evidence_bundle),
        )

    def _unsupported_region_result(
        self,
        region: ExploreRegion,
        *,
        display_order: int,
        context: ExploreContext,
        evidence_bundle: str,
        opportunity: dict[str, OpportunityCoverage],
    ) -> ExploreFitResult:
        constraint_reasons = _hard_constraint_reasons(context, region)
        excluded = bool(
            region.region_id in context.effective_context.excluded_region_ids
            and region.region_id not in context.effective_context.included_region_ids
        )
        return ExploreFitResult(
            market_key=region.public_slug or region.region_id,
            region=region,
            state=(
                ExploreFitState.HARD_CONSTRAINT_EXCLUDED
                if excluded
                else ExploreFitState.UNSUPPORTED
            ),
            display_order=display_order,
            confidence="limited",
            evidence_sufficiency="not_supported",
            freshness="unknown",
            market_coverage=MarketEvidenceCoverage(
                summary="Layer 34 does not support this canonical Region.",
                evidence_areas_missing=("governed_market_profile",),
            ),
            opportunity_coverage=opportunity.get(
                region.region_id,
                _empty_opportunity_coverage(),
            ),
            material_limitations=(
                "This known canonical Region is outside the curated Layer 34 registry.",
                *constraint_reasons,
            ),
            abstention_reason=("hard_constraint_excluded" if excluded else "unsupported_market"),
            hard_constraint_reasons=constraint_reasons if excluded else (),
            versions=_versions(context, evidence_bundle),
        )

    def _region_metadata(
        self,
        region_ids: tuple[str, ...],
    ) -> dict[str, ExploreRegion]:
        if not region_ids:
            return {}
        rows = self._session.execute(
            select(Region).where(Region.region_id.in_(region_ids))
        ).scalars()
        state_rows = self._session.execute(
            select(
                RegionStateMembership.region_id,
                RegionStateMembership.state_code,
            )
            .where(RegionStateMembership.region_id.in_(region_ids))
            .order_by(
                RegionStateMembership.region_id,
                RegionStateMembership.state_code,
            )
        )
        states: dict[str, list[str]] = defaultdict(list)
        for region_id, state_code in state_rows:
            states[region_id].append(state_code)
        return {
            row.region_id: ExploreRegion(
                region_id=row.region_id,
                public_slug=row.public_slug,
                display_name=row.display_name,
                region_type=row.region_type,
                state_codes=tuple(states[row.region_id]),
                primary_city=row.primary_city,
                centroid=(
                    {
                        "latitude": row.centroid_latitude,
                        "longitude": row.centroid_longitude,
                    }
                    if row.centroid_latitude is not None and row.centroid_longitude is not None
                    else None
                ),
                focus_bounds=row.focus_bounds,
                market_support_status=row.market_support_status,
            )
            for row in rows
        }

    def _canonical_registry_regions(self, entries: dict[str, Any]) -> dict[str, str]:
        stored_ids = {entry.region_id for entry in entries.values()}
        identities = self._region_repo.current_output_identities(stored_ids)
        return {
            key: (identities.get(entry.region_id, {}).get("region_id") or entry.region_id)
            for key, entry in entries.items()
        }

    def _opportunity_coverage(
        self,
        region_ids: tuple[str, ...],
        *,
        goal: str | None,
        opportunity_types: tuple[str, ...],
    ) -> dict[str, OpportunityCoverage]:
        if not region_ids:
            return {}
        count_rows = self._session.execute(
            select(
                CurrentOpportunity.market_id,
                func.count(CurrentOpportunity.current_opportunity_id),
                func.sum(case((CurrentOpportunity.ranking_eligible.is_(True), 1), else_=0)),
                func.sum(case((CurrentOpportunity.freshness_state == "fresh", 1), else_=0)),
            )
            .where(
                CurrentOpportunity.market_id.in_(region_ids),
                CurrentOpportunity.canonical_status == "active",
            )
            .group_by(CurrentOpportunity.market_id)
        ).all()
        counts = {
            row[0]: (int(row[1] or 0), int(row[2] or 0), int(row[3] or 0)) for row in count_rows
        }
        contracts = self._session.execute(
            select(OpportunityCoverageContract).where(
                (OpportunityCoverageContract.market_id.in_(region_ids))
                | (OpportunityCoverageContract.market_key.in_(region_ids))
                | (OpportunityCoverageContract.market_key == "*")
            )
        ).scalars()
        role = _opportunity_role(goal)
        opportunity_type = opportunity_types[0] if len(opportunity_types) == 1 else "*"
        by_region: dict[str, OpportunityCoverage] = {}
        contracts_list = list(contracts)
        for region_id in region_ids:
            contract = _coverage_contract(
                contracts_list,
                region_id=region_id,
                role_family=role,
                opportunity_type=opportunity_type,
            )
            active, eligible, fresh = counts.get(region_id, (0, 0, 0))
            status = (
                contract.operator_override_status or contract.status
                if contract is not None
                else "unsupported"
            )
            limitations = (
                ()
                if contract is not None
                else ("No matching Layer 38 opportunity coverage contract exists.",)
            )
            by_region[region_id] = OpportunityCoverage(
                status=status,
                active_opportunity_count=active,
                ranking_eligible_opportunity_count=eligible,
                fresh_opportunity_count=fresh,
                rationale=contract.rationale if contract else None,
                limitations=limitations,
            )
        return by_region

    def _record_measurement(
        self,
        user_id: str,
        response: ExploreMarketsResponse,
    ) -> None:
        context = response.context
        measurement = ProductMeasurementService(self._session)
        shared = {
            "event_source": ProductEventSource.BACKEND,
            "career_identity_id": context.career_identity_id,
            "career_identity_version": context.career_identity_version,
            "product_surface": "explore",
        }
        measurement.best_effort_record_event(
            user_id,
            ProductEventCreate(
                event_type=ProductEventType.EXPLORE_CONTEXT_EVALUATED,
                payload={
                    "context_fingerprint": context.context_fingerprint,
                    "personalization_state": context.personalization_state.value,
                    "supported_goal": context.supported_goal,
                },
                **shared,
            ),
        )
        eligible_count = sum(
            market.state in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
            for market in response.markets
        )
        if context.personalization_state is ExplorePersonalizationState.UNSUPPORTED:
            outcome = ProductEventType.EXPLORE_CONTEXT_UNSUPPORTED
        elif context.personalization_state is ExplorePersonalizationState.PERSONALIZED:
            outcome = (
                ProductEventType.EXPLORE_FIT_GENERATED
                if eligible_count
                else ProductEventType.EXPLORE_FIT_ABSTAINED
            )
        else:
            return
        measurement.best_effort_record_event(
            user_id,
            ProductEventCreate(
                event_type=outcome,
                confidence_bucket=_response_confidence(response),
                recommendation_state=context.personalization_state.value,
                payload={
                    "context_fingerprint": context.context_fingerprint,
                    "supported_goal": context.supported_goal,
                    "market_count": len(response.markets),
                    "eligible_market_count": eligible_count,
                    "authority_version": response.authority_version,
                },
                **shared,
            ),
        )


def _fit_state(
    item: Any,
    region: ExploreRegion,
    constraint_reasons: tuple[str, ...],
) -> tuple[ExploreFitState, float | None, str | None]:
    if constraint_reasons:
        return (
            ExploreFitState.HARD_CONSTRAINT_EXCLUDED,
            None,
            "The market is outside the effective geographic scope.",
        )
    if region.market_support_status != "supported":
        return (
            ExploreFitState.UNSUPPORTED,
            None,
            "Canonical Region metadata does not mark this market as supported.",
        )
    if getattr(item, "contradiction_status", ContradictionStatus.CLEAR) is (
        ContradictionStatus.BLOCKING
    ):
        return (
            ExploreFitState.ABSTAINED,
            None,
            item.abstention_reason or "Layer 34 detected a blocking contradiction.",
        )
    if item.evidence_sufficiency in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
        EvidenceSufficiency.NOT_SUPPORTED,
    }:
        state = (
            ExploreFitState.UNSUPPORTED
            if item.evidence_sufficiency is EvidenceSufficiency.NOT_SUPPORTED
            else ExploreFitState.INSUFFICIENT_EVIDENCE
        )
        return state, None, item.abstention_reason
    if item.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        return ExploreFitState.TENTATIVE, item.score, None
    return ExploreFitState.CONFIDENT, item.score, None


def _eligible_ranks(drafts: list[dict[str, Any]]) -> dict[str, int]:
    eligible = [
        draft
        for draft in drafts
        if draft["state"] in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
        and draft["score"] is not None
    ]
    eligible.sort(key=lambda row: (-row["score"], row["region"].region_id))
    result: dict[str, int] = {}
    prior_score: float | None = None
    prior_rank = 0
    for position, row in enumerate(eligible, start=1):
        rank = prior_rank if prior_score == row["score"] else position
        result[row["region"].region_id] = rank
        prior_score = row["score"]
        prior_rank = rank
    return result


def _hard_constraint_reasons(
    context: ExploreContext,
    region: ExploreRegion,
) -> tuple[str, ...]:
    effective = context.effective_context
    reasons: list[str] = []
    if effective.included_region_ids and region.region_id not in effective.included_region_ids:
        reasons.append("Market is outside the effective included geographic scope.")
    if region.region_id in effective.excluded_region_ids:
        reasons.append("Market is explicitly excluded by the effective geographic scope.")
    return tuple(reasons)


def _referenced_region_ids(context: ExploreContext) -> tuple[str, ...]:
    effective = context.effective_context
    return tuple(
        dict.fromkeys(
            (
                *effective.preferred_region_ids,
                *effective.included_region_ids,
                *effective.excluded_region_ids,
            )
        )
    )


def _contradiction_fields(*values: Any) -> dict[str, Any]:
    statuses = tuple(
        getattr(
            getattr(value, "contradiction_status", ContradictionStatus.CLEAR),
            "value",
            str(getattr(value, "contradiction_status", ContradictionStatus.CLEAR)),
        )
        for value in values
    )
    all_findings = []
    for value in values:
        all_findings.extend(tuple(getattr(value, "contradictions", ()) or ()))
    public_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in all_findings:
        public = finding.as_dict() if hasattr(finding, "as_dict") else dict(finding)
        public_by_key.setdefault(
            (str(public.get("code")), str(public.get("evidence"))),
            public,
        )
    public_findings = tuple(public_by_key.values())
    blocking = ContradictionStatus.BLOCKING.value in statuses or any(
        bool(item.get("blocks_recommendation")) for item in public_findings
    )
    status = (
        ContradictionStatus.BLOCKING.value
        if blocking
        else ContradictionStatus.WARNINGS.value
        if public_findings or ContradictionStatus.WARNINGS.value in statuses
        else ContradictionStatus.CLEAR.value
    )
    summary = None
    if public_findings:
        messages = tuple(
            str(item.get("message")) for item in public_findings if item.get("message")
        )
        summary = " ".join(messages[:2]) or None
    return {
        "contradiction_status": status,
        "contradiction_findings": public_findings,
        "contradiction_blocking": blocking,
        "contradiction_summary": summary,
    }


def _fit_band(score: float | None, sufficiency: EvidenceSufficiency) -> str | None:
    if score is None:
        return None
    if sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        return "limited_evidence"
    for threshold, band in FIT_BAND_THRESHOLDS:
        if score >= threshold:
            return band
    raise AssertionError("fit band thresholds must cover zero")


def _ranking_market_coverage(item: Any) -> MarketEvidenceCoverage:
    grounding = item.grounding
    return MarketEvidenceCoverage(
        summary=grounding.coverage if grounding else "Coverage detail unavailable.",
        evidence_areas_used=grounding.evidence_areas_used if grounding else (),
        evidence_areas_missing=grounding.evidence_areas_missing if grounding else (),
    )


def _profile_market_coverage(profile: Any) -> MarketEvidenceCoverage:
    grounding = profile.grounding
    return MarketEvidenceCoverage(
        summary=profile.coverage_summary,
        evidence_areas_used=grounding.evidence_areas_used if grounding else (),
        evidence_areas_missing=grounding.evidence_areas_missing if grounding else (),
    )


def _ranking_universe(
    context: ExploreContext,
    regions: tuple[ExploreRegion, ...],
) -> RankingUniverse:
    constrained = bool(
        context.effective_context.included_region_ids
        or context.effective_context.excluded_region_ids
    )
    active = tuple(
        region.region_id
        for region in regions
        if region.market_support_status == "supported"
        and not _hard_constraint_reasons(context, region)
    )
    return RankingUniverse(
        kind="constrained_curated_markets" if constrained else "curated_supported_markets",
        label=(
            "Geographically constrained subset of the curated market universe"
            if constrained
            else "Current curated market universe"
        ),
        region_ids=active,
        market_count=len(active),
        nationally_representative=False,
    )


def _versions(context: ExploreContext, evidence_bundle: str) -> ExploreFitVersions:
    return ExploreFitVersions(
        algorithm_version=EXPLORE_FIT_ALGORITHM_VERSION,
        market_evidence_authority_version=MARKET_EVIDENCE_AUTHORITY_VERSION,
        market_evidence_bundle=evidence_bundle,
        calibration_version=FIT_CALIBRATION_VERSION,
        context_fingerprint=context.context_fingerprint,
        career_identity_version=context.career_identity_version,
    )


def _evidence_bundle(value: Any) -> str:
    payload = value.as_dict() if hasattr(value, "as_dict") else str(value)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _opportunity_role(goal: str | None) -> str:
    return {
        "software_engineering": "software_engineering",
        "product_management": "product",
        "ai_ml": "ai_cloud_adjacent",
        "cybersecurity": "cybersecurity",
        "data_science": "data_science",
    }.get(goal or "", "*")


def _coverage_contract(
    contracts: list[OpportunityCoverageContract],
    *,
    region_id: str,
    role_family: str,
    opportunity_type: str,
) -> OpportunityCoverageContract | None:
    priorities = (
        (region_id, role_family, opportunity_type),
        (region_id, role_family, "*"),
        (region_id, "*", opportunity_type),
        (region_id, "*", "*"),
        ("*", role_family, opportunity_type),
        ("*", role_family, "*"),
        ("*", "*", opportunity_type),
        ("*", "*", "*"),
    )
    for market, role, kind in priorities:
        for row in contracts:
            row_market = row.market_id or row.market_key
            if row_market == market and row.role_family == role and row.opportunity_type == kind:
                return row
    return None


def _empty_opportunity_coverage() -> OpportunityCoverage:
    return OpportunityCoverage(
        status="unsupported",
        active_opportunity_count=0,
        ranking_eligible_opportunity_count=0,
        fresh_opportunity_count=0,
        limitations=("No Layer 38 opportunity coverage is available.",),
    )


def _response_confidence(response: ExploreMarketsResponse) -> str:
    for market in response.markets:
        if market.state in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}:
            return market.confidence
    return "limited"


def _missing_region(region_id: str, display_name: str) -> ExploreRegion:
    return ExploreRegion(
        region_id=region_id,
        public_slug=None,
        display_name=display_name,
        region_type=None,
        market_support_status="unknown",
    )
