"""Authoritative N-way Explore comparison, immutable saves, and Prioritize bridge."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ConfidenceLevel,
    ExploreComparisonDecisionSeed,
)
from backend.career_decisions.schemas import (
    EvidenceSufficiency as DecisionEvidenceSufficiency,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.explore.repository import ExploreComparisonRepository
from backend.explore.schemas import (
    ComparisonCompanyEvidence,
    ComparisonFactor,
    ExploreComparisonMarket,
    ExploreComparisonRecommendationState,
    ExploreComparisonRequest,
    ExploreComparisonResult,
    ExploreFitResult,
    ExploreFitState,
    PrioritizedExploreDecision,
    PrioritizeExploreComparisonRequest,
    SavedExploreComparisonSummary,
    SavedExploreComparisonView,
    SaveExploreComparisonRequest,
)
from backend.explore.service import ExploreFitService
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.market_intelligence.calibration import scores_are_near_tie
from backend.presence.models import CompanyRegionPresence
from backend.product_measurement.schemas import (
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
)
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.repository import UserRepository


class ExploreComparisonValidationError(ValueError):
    pass


class ExploreComparisonNotFound(LookupError):
    pass


class ExploreComparisonService:
    """Compose comparisons from one Explore Fit evaluation; never rescore markets."""

    def __init__(
        self,
        session: Session,
        *,
        fit_service: ExploreFitService | None = None,
        clock: callable | None = None,
    ) -> None:
        self._session = session
        self._repo = ExploreComparisonRepository(session)
        self._regions = RegionRepository(session)
        self._fit = fit_service or ExploreFitService(session)
        self._measurement = ProductMeasurementService(session)
        self._clock = clock or (lambda: datetime.now(UTC))

    def compare(
        self,
        user_id: str,
        request: ExploreComparisonRequest,
        *,
        as_of: date | datetime | None = None,
    ) -> ExploreComparisonResult:
        region_ids = self._resolve_region_ids(request.market_refs)
        response = self._fit.evaluate(user_id, request.session_overrides, as_of=as_of)
        fits = self._fit.selected_market_results(response, region_ids)
        if len(fits) != len(region_ids):
            raise ExploreComparisonValidationError("one or more comparison markets are unavailable")
        result = self._compose(response, fits)
        self._record(
            user_id,
            ProductEventType.COMPARISON_GENERATED,
            result,
            payload={"selected_region_ids": sorted(region_ids)},
        )
        return result

    def save(
        self,
        user_id: str,
        request: SaveExploreComparisonRequest,
        *,
        as_of: date | datetime | None = None,
    ) -> SavedExploreComparisonView:
        self._repo.serialize_user_writes(user_id)
        result = self.compare(
            user_id,
            ExploreComparisonRequest(
                market_refs=request.market_refs,
                session_overrides=request.session_overrides,
            ),
            as_of=as_of,
        )
        if result.comparison_identity != request.comparison_identity:
            raise ExploreComparisonValidationError(
                "comparison is stale; run it again before saving"
            )
        row = self._persist_snapshot(user_id, result, saved=True)
        self._record(
            user_id,
            ProductEventType.COMPARISON_SAVED,
            result,
            payload={"comparison_id": row.comparison_id},
        )
        return self._saved_view(row)

    def list_saved(
        self, user_id: str, *, limit: int = 100
    ) -> tuple[SavedExploreComparisonSummary, ...]:
        return tuple(
            self._saved_summary(row) for row in self._repo.list_saved(user_id, limit=limit)
        )

    def get_saved(self, user_id: str, comparison_id: str) -> SavedExploreComparisonView:
        row = self._owned_snapshot(user_id, comparison_id)
        if row.saved_at is None:
            raise ExploreComparisonNotFound(comparison_id)
        return self._saved_view(row)

    def prioritize(
        self,
        user_id: str,
        request: PrioritizeExploreComparisonRequest,
        *,
        as_of: date | datetime | None = None,
    ) -> PrioritizedExploreDecision:
        self._repo.serialize_user_writes(user_id)
        if request.comparison_id:
            snapshot = self._owned_snapshot(user_id, request.comparison_id)
            result = ExploreComparisonResult.model_validate(snapshot.snapshot_payload)
        else:
            if len(request.market_refs) < 2 or request.comparison_identity is None:
                raise ExploreComparisonValidationError(
                    "live prioritization requires 2-4 markets and comparison identity"
                )
            result = self.compare(
                user_id,
                ExploreComparisonRequest(
                    market_refs=request.market_refs,
                    session_overrides=request.session_overrides,
                ),
                as_of=as_of,
            )
            if result.comparison_identity != request.comparison_identity:
                raise ExploreComparisonValidationError(
                    "comparison is stale; run it again before prioritizing"
                )
            snapshot = self._persist_snapshot(user_id, result, saved=False)

        selected_region_id = self._resolve_region_ids((request.selected_market_ref,))[0]
        market_by_region = {
            market.fit.region.region_id: market for market in result.compared_markets
        }
        selected = market_by_region.get(selected_region_id)
        if selected is None:
            raise ExploreComparisonValidationError(
                "prioritized market must be a member of the comparison"
            )
        if selected.fit.state is ExploreFitState.HARD_CONSTRAINT_EXCLUDED:
            raise ExploreComparisonValidationError(
                "market is outside current search constraints; adjust Explore context first"
            )

        market_set_fingerprint = _market_set_fingerprint(tuple(market_by_region))
        equivalent = self._repo.find_active_equivalent_decision(
            user_id=user_id,
            context_fingerprint=result.context_fingerprint,
            market_set_fingerprint=market_set_fingerprint,
            selected_region_id=selected_region_id,
        )
        decision_service = self._decision_service()
        if equivalent is not None:
            provenance, decision = equivalent
            view = decision_service.decision_view(user_id, decision.decision_id)
            return PrioritizedExploreDecision(
                decision_id=decision.decision_id,
                comparison_id=provenance.comparison_id,
                selected_region_id=selected_region_id,
                system_recommended_region_ids=tuple(provenance.system_recommended_region_ids or []),
                choice_matches_recommendation=provenance.choice_matches_recommendation,
                created=False,
                decision=view.model_dump(mode="json"),
            )

        self._record(
            user_id,
            ProductEventType.PRIORITIZE_INITIATED,
            result,
            payload={
                "comparison_id": snapshot.comparison_id,
                "selected_region_id": selected_region_id,
            },
        )
        recommended = tuple(result.winner_region_ids)
        choice_matches = selected_region_id in recommended if recommended else None
        decision_view = decision_service.create_from_explore_comparison(
            user_id,
            ExploreComparisonDecisionSeed(
                comparison_id=snapshot.comparison_id,
                context_fingerprint=result.context_fingerprint,
                comparison_identity=result.comparison_identity,
                recommendation_state=result.recommendation_state.value,
                recommendation_summary=result.recommendation_summary,
                confidence=_decision_confidence(result.confidence),
                evidence_sufficiency=_decision_sufficiency(result),
                system_recommended_region_ids=recommended,
                selected_region_id=selected_region_id,
                market_options=tuple(
                    {
                        "region_id": market.fit.region.region_id,
                        "public_slug": market.fit.region.public_slug,
                        "display_name": market.fit.region.display_name,
                        "fit_state": market.fit.state.value,
                        "fit_score": market.fit.fit_score,
                        "fit_band": market.fit.fit_band,
                        "comparison_rank": market.comparison_rank,
                    }
                    for market in result.compared_markets
                ),
                comparison_payload={
                    "comparison_id": snapshot.comparison_id,
                    "comparison_identity": result.comparison_identity,
                    "recommendation_state": result.recommendation_state.value,
                    "winner_region_ids": list(result.winner_region_ids),
                    "tied_region_ids": list(result.tied_region_ids),
                    "near_tie_region_ids": list(result.near_tie_region_ids),
                    "context_fingerprint": result.context_fingerprint,
                },
                evidence_payload={
                    "authority": result.authority,
                    "algorithm_version": result.algorithm_version,
                    "evidence_authority_version": result.evidence_authority_version,
                    "evidence_bundle": result.evidence_bundle,
                    "calibration_version": result.calibration_version,
                    "differentiating_factors": [
                        item.model_dump(mode="json") for item in result.differentiating_factors
                    ],
                },
                limitations=result.limitations,
                generated_at=result.generated_at,
            ),
        )
        provenance = ExploreDecisionProvenance(
            provenance_id=_new_id("explore_provenance"),
            user_id=user_id,
            decision_id=decision_view.decision_id,
            comparison_id=snapshot.comparison_id,
            context_fingerprint=result.context_fingerprint,
            market_set_fingerprint=market_set_fingerprint,
            system_recommendation_state=result.recommendation_state.value,
            system_recommended_region_ids=list(recommended),
            user_selected_region_id=selected_region_id,
            choice_matches_recommendation=choice_matches,
            created_at=self._clock(),
        )
        self._repo.add(provenance)
        self._repo.flush()
        decision_view = decision_service.decision_view(user_id, decision_view.decision_id)
        self._record(
            user_id,
            ProductEventType.PRIORITIZE_COMPLETED,
            result,
            decision_id=decision_view.decision_id,
            payload={
                "comparison_id": snapshot.comparison_id,
                "selected_region_id": selected_region_id,
                "choice_matches_recommendation": choice_matches,
            },
        )
        if choice_matches is False:
            self._record(
                user_id,
                ProductEventType.COMPARISON_RECOMMENDATION_OVERRIDDEN,
                result,
                decision_id=decision_view.decision_id,
                payload={
                    "comparison_id": snapshot.comparison_id,
                    "selected_region_id": selected_region_id,
                    "system_recommended_region_ids": list(recommended),
                },
            )
        return PrioritizedExploreDecision(
            decision_id=decision_view.decision_id,
            comparison_id=snapshot.comparison_id,
            selected_region_id=selected_region_id,
            system_recommended_region_ids=recommended,
            choice_matches_recommendation=choice_matches,
            created=True,
            decision=decision_view.model_dump(mode="json"),
        )

    def _compose(
        self, response: Any, fits: tuple[ExploreFitResult, ...]
    ) -> ExploreComparisonResult:
        ranks = _comparison_ranks(fits)
        state, winners, tied, near, abstention = _recommendation(fits)
        companies = self._company_evidence(tuple(fit.region.region_id for fit in fits))
        shared_strengths, differentiators = _factor_analysis(fits)
        shared_weaknesses = _shared_weaknesses(fits)
        missing = {
            fit.region.region_id: tuple(fit.market_coverage.evidence_areas_missing)
            for fit in fits
            if fit.market_coverage.evidence_areas_missing
        }
        comparison_markets = tuple(
            ExploreComparisonMarket(
                fit=fit,
                comparison_rank=ranks.get(fit.region.region_id),
                key_advantages=_market_advantages(fit, shared_strengths),
                key_tradeoffs=_market_tradeoffs(fit),
                confidence_caveat=_confidence_caveat(fit),
                missing_evidence=tuple(fit.market_coverage.evidence_areas_missing),
                company_evidence=companies.get(fit.region.region_id, ()),
            )
            for fit in fits
        )
        confidence = _comparison_confidence(fits)
        summary = _recommendation_summary(state, fits, winners, differentiators, confidence)
        first_versions = fits[0].versions
        substantive = {
            "selected_region_ids": sorted(fit.region.region_id for fit in fits),
            "context_fingerprint": response.context.context_fingerprint,
            "algorithm_version": first_versions.algorithm_version,
            "evidence_authority_version": first_versions.market_evidence_authority_version,
            "evidence_bundle": first_versions.market_evidence_bundle,
            "calibration_version": first_versions.calibration_version,
            "fit": sorted(
                (
                    {
                        "region_id": fit.region.region_id,
                        "state": fit.state.value,
                        "score": fit.fit_score,
                        "band": fit.fit_band,
                        "confidence": fit.confidence,
                        "sufficiency": fit.evidence_sufficiency,
                        "contradiction": fit.contradiction_status,
                    }
                    for fit in fits
                ),
                key=lambda item: item["region_id"],
            ),
            "recommendation_state": state.value,
            "winner_region_ids": sorted(winners),
        }
        identity = _stable_hash(substantive)
        findings = _unique_findings(fits)
        return ExploreComparisonResult(
            comparison_identity=identity,
            compared_markets=comparison_markets,
            recommendation_state=state,
            recommendation_summary=summary,
            winner_region_ids=winners,
            tied_region_ids=tied,
            near_tie_region_ids=near,
            abstained=state
            in {
                ExploreComparisonRecommendationState.INSUFFICIENT_EVIDENCE,
                ExploreComparisonRecommendationState.BLOCKING_CONTRADICTION,
                ExploreComparisonRecommendationState.UNSUPPORTED_MEMBER,
                ExploreComparisonRecommendationState.OUTSIDE_CONSTRAINTS,
            },
            abstention_reason=abstention,
            differentiating_factors=differentiators,
            shared_strengths=shared_strengths,
            shared_weaknesses=shared_weaknesses,
            confidence=confidence,
            contradiction_state=(
                "blocking"
                if any(fit.contradiction_blocking for fit in fits)
                else "warnings"
                if findings
                else "clear"
            ),
            contradiction_findings=findings,
            missing_evidence=missing,
            market_coverage={fit.region.region_id: fit.market_coverage for fit in fits},
            opportunity_coverage={fit.region.region_id: fit.opportunity_coverage for fit in fits},
            context_fingerprint=response.context.context_fingerprint,
            effective_context=response.context.effective_context,
            algorithm_version=first_versions.algorithm_version,
            evidence_authority_version=first_versions.market_evidence_authority_version,
            evidence_bundle=first_versions.market_evidence_bundle,
            calibration_version=first_versions.calibration_version,
            generated_at=response.evaluated_at,
            limitations=tuple(
                dict.fromkeys(
                    (
                        *response.limitations,
                        (
                            "Current opportunity and company evidence do not affect "
                            "Fit, rank, or recommendation."
                        ),
                    )
                )
            ),
        )

    def _resolve_region_ids(self, refs: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(refs) <= 4:
            raise ExploreComparisonValidationError("comparison requires 2-4 markets")
        resolver = GeographicResolver(self._regions)
        region_ids: list[str] = []
        for ref in refs:
            result = resolver.resolve(ref)
            if not result.resolved or result.region_id is None:
                raise ExploreComparisonValidationError(f"unknown comparison market: {ref!r}")
            region_ids.append(result.region_id)
        if len(set(region_ids)) != len(region_ids):
            raise ExploreComparisonValidationError(
                "comparison markets must be unique canonical Regions"
            )
        return tuple(region_ids)

    def _company_evidence(
        self, region_ids: tuple[str, ...]
    ) -> dict[str, tuple[ComparisonCompanyEvidence, ...]]:
        hiring_rows = self._session.execute(
            select(CompanyRegionHiring, Company)
            .join(Company, Company.company_id == CompanyRegionHiring.company_id)
            .where(
                CompanyRegionHiring.region_id.in_(region_ids),
                CompanyRegionHiring.currently_hiring_flag.is_(True),
            )
            .order_by(
                CompanyRegionHiring.region_id,
                CompanyRegionHiring.active_posting_count_now.desc().nullslast(),
                Company.company_name,
            )
        ).all()
        by_region: dict[str, list[ComparisonCompanyEvidence]] = defaultdict(list)
        for hiring, company in hiring_rows:
            if len(by_region[hiring.region_id]) >= 3:
                continue
            by_region[hiring.region_id].append(
                ComparisonCompanyEvidence(
                    company_id=company.company_id,
                    company_name=company.company_name,
                    evidence_kind="current_hiring",
                    active_posting_count=hiring.active_posting_count_now,
                    confidence=hiring.hiring_confidence,
                )
            )
        missing = tuple(region_id for region_id in region_ids if not by_region[region_id])
        if missing:
            presence_rows = self._session.execute(
                select(CompanyRegionPresence, Company)
                .join(Company, Company.company_id == CompanyRegionPresence.company_id)
                .where(
                    CompanyRegionPresence.region_id.in_(missing),
                    CompanyRegionPresence.presence_status.in_(("present", "confirmed")),
                )
                .order_by(CompanyRegionPresence.region_id, Company.company_name)
            ).all()
            for presence, company in presence_rows:
                if len(by_region[presence.region_id]) >= 3:
                    continue
                by_region[presence.region_id].append(
                    ComparisonCompanyEvidence(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        evidence_kind="presence",
                        confidence=presence.presence_confidence,
                    )
                )
        return {region_id: tuple(items) for region_id, items in by_region.items()}

    def _persist_snapshot(
        self, user_id: str, result: ExploreComparisonResult, *, saved: bool
    ) -> ExploreComparisonSnapshot:
        existing = self._repo.get_by_identity(user_id, result.comparison_identity)
        if existing is not None:
            if saved and existing.saved_at is None:
                existing.saved_at = self._clock()
                self._repo.flush()
            return existing
        row = ExploreComparisonSnapshot(
            comparison_id=_new_id("explore_comparison"),
            user_id=user_id,
            snapshot_schema_version=1,
            comparison_identity=result.comparison_identity,
            selected_region_ids=[market.fit.region.region_id for market in result.compared_markets],
            selected_public_slugs=[
                market.fit.region.public_slug or market.fit.region.region_id
                for market in result.compared_markets
            ],
            context_fingerprint=result.context_fingerprint,
            effective_context_summary=result.effective_context.model_dump(mode="json"),
            recommendation_state=result.recommendation_state.value,
            winner_region_ids=list(result.winner_region_ids),
            tie_region_ids=list(result.tied_region_ids),
            confidence=result.confidence,
            algorithm_version=result.algorithm_version,
            evidence_authority_version=result.evidence_authority_version,
            evidence_bundle=result.evidence_bundle,
            calibration_version=result.calibration_version,
            snapshot_payload=result.model_dump(mode="json"),
            recommendation_summary=result.recommendation_summary,
            generated_at=result.generated_at,
            saved_at=self._clock() if saved else None,
            created_at=self._clock(),
        )
        self._repo.add(row)
        self._repo.flush()
        return row

    def _owned_snapshot(self, user_id: str, comparison_id: str) -> ExploreComparisonSnapshot:
        row = self._repo.get(comparison_id)
        if row is None or row.user_id != user_id:
            raise ExploreComparisonNotFound(comparison_id)
        return row

    def _saved_summary(self, row: ExploreComparisonSnapshot) -> SavedExploreComparisonSummary:
        result = ExploreComparisonResult.model_validate(row.snapshot_payload)
        names = tuple(market.fit.region.display_name for market in result.compared_markets)
        return SavedExploreComparisonSummary(
            comparison_id=row.comparison_id,
            selected_region_ids=tuple(row.selected_region_ids or []),
            selected_public_slugs=tuple(row.selected_public_slugs or []),
            market_names=names,
            context_fingerprint=row.context_fingerprint,
            context_summary=_context_summary(result),
            recommendation_state=row.recommendation_state,
            recommendation_summary=row.recommendation_summary,
            winner_region_ids=tuple(row.winner_region_ids or []),
            confidence=row.confidence,
            generated_at=row.generated_at,
            saved_at=row.saved_at,
        )

    def _saved_view(self, row: ExploreComparisonSnapshot) -> SavedExploreComparisonView:
        summary = self._saved_summary(row)
        return SavedExploreComparisonView(
            **summary.model_dump(),
            result=ExploreComparisonResult.model_validate(row.snapshot_payload),
        )

    def _decision_service(self) -> CareerDecisionService:
        return CareerDecisionService(
            CareerDecisionRepository(self._session),
            CareerIdentityRepository(self._session),
            UserRepository(self._session),
            self._regions,
            CompanyRepository(self._session),
            RegionScoreRepository(self._session),
            self._measurement,
        )

    def _record(
        self,
        user_id: str,
        event_type: ProductEventType,
        result: ExploreComparisonResult,
        *,
        decision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._measurement.best_effort_record_event(
            user_id,
            ProductEventCreate(
                event_type=event_type,
                event_source=ProductEventSource.BACKEND,
                decision_id=decision_id,
                career_identity_version=(
                    result.compared_markets[0].fit.versions.career_identity_version
                    if result.compared_markets
                    else None
                ),
                confidence_bucket=result.confidence,
                recommendation_state=result.recommendation_state.value,
                product_surface="explore_comparison",
                payload={
                    "comparison_identity": result.comparison_identity,
                    "context_fingerprint": result.context_fingerprint,
                    "market_count": len(result.compared_markets),
                    **(payload or {}),
                },
            ),
        )


def _comparison_ranks(fits: tuple[ExploreFitResult, ...]) -> dict[str, int]:
    eligible = sorted(
        (
            fit
            for fit in fits
            if fit.state in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
            and fit.fit_score is not None
        ),
        key=lambda fit: (-float(fit.fit_score), fit.region.region_id),
    )
    ranks: dict[str, int] = {}
    prior_score: float | None = None
    prior_rank = 0
    for position, fit in enumerate(eligible, start=1):
        rank = prior_rank if fit.fit_score == prior_score else position
        ranks[fit.region.region_id] = rank
        prior_score = fit.fit_score
        prior_rank = rank
    return ranks


def _recommendation(
    fits: tuple[ExploreFitResult, ...],
) -> tuple[
    ExploreComparisonRecommendationState,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    str | None,
]:
    if any(fit.state is ExploreFitState.UNSUPPORTED for fit in fits):
        return (
            ExploreComparisonRecommendationState.UNSUPPORTED_MEMBER,
            (),
            (),
            (),
            "A selected known Region is outside the supported Layer 34 comparison universe.",
        )
    if any(fit.state is ExploreFitState.HARD_CONSTRAINT_EXCLUDED for fit in fits):
        return (
            ExploreComparisonRecommendationState.OUTSIDE_CONSTRAINTS,
            (),
            (),
            (),
            "A selected market is outside the effective Explore constraints.",
        )
    if any(fit.contradiction_blocking or fit.state is ExploreFitState.ABSTAINED for fit in fits):
        return (
            ExploreComparisonRecommendationState.BLOCKING_CONTRADICTION,
            (),
            (),
            (),
            "Blocking governed evidence prevents a fair recommendation.",
        )
    eligible = sorted(
        (
            fit
            for fit in fits
            if fit.state in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
            and fit.fit_score is not None
        ),
        key=lambda fit: (-float(fit.fit_score), fit.region.region_id),
    )
    if len(eligible) < 2:
        return (
            ExploreComparisonRecommendationState.INSUFFICIENT_EVIDENCE,
            (),
            (),
            (),
            "We do not have enough comparable governed evidence to distinguish these markets.",
        )
    top_score = eligible[0].fit_score
    assert top_score is not None
    tied = tuple(sorted(fit.region.region_id for fit in eligible if fit.fit_score == top_score))
    near = tuple(
        sorted(
            fit.region.region_id
            for fit in eligible
            if fit.fit_score is not None
            and (fit.fit_score == top_score or scores_are_near_tie(fit.fit_score, top_score))
        )
    )
    if len(tied) > 1:
        return ExploreComparisonRecommendationState.EXACT_TIE, tied, tied, near, None
    if len(near) > 1:
        return ExploreComparisonRecommendationState.NEAR_TIE, near, (), near, None
    return (
        ExploreComparisonRecommendationState.CLEAR_RECOMMENDATION,
        (eligible[0].region.region_id,),
        (),
        (),
        None,
    )


def _factor_analysis(
    fits: tuple[ExploreFitResult, ...],
) -> tuple[tuple[ComparisonFactor, ...], tuple[ComparisonFactor, ...]]:
    drivers: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for fit in fits:
        for driver in fit.primary_drivers:
            code = str(driver.get("code") or driver.get("label") or "governed_factor")
            drivers[code][fit.region.region_id] = driver
    shared: list[ComparisonFactor] = []
    differentiators: list[ComparisonFactor] = []
    all_ids = {fit.region.region_id for fit in fits}
    names = {fit.region.region_id: fit.region.display_name for fit in fits}
    for code, by_region in sorted(drivers.items()):
        label = str(next(iter(by_region.values())).get("label") or code.replace("_", " ").title())
        contributions = {
            region_id: float(driver.get("contribution") or 0.0)
            for region_id, driver in by_region.items()
        }
        evidence = tuple(
            dict.fromkeys(
                str(driver.get("evidence"))
                for driver in by_region.values()
                if driver.get("evidence")
            )
        )
        if set(by_region) == all_ids and len(set(contributions.values())) <= 1:
            shared.append(
                ComparisonFactor(
                    code=code,
                    label=label,
                    summary=f"All selected markets share comparable {label.lower()} evidence.",
                    region_ids=tuple(sorted(all_ids)),
                    evidence=evidence[:3],
                )
            )
            continue
        strongest_value = max(contributions.values())
        strongest = tuple(
            sorted(
                region_id for region_id, value in contributions.items() if value == strongest_value
            )
        )
        strongest_names = ", ".join(names[region_id] for region_id in strongest)
        differentiators.append(
            ComparisonFactor(
                code=code,
                label=label,
                summary=(
                    f"{strongest_names} has the strongest governed "
                    f"{label.lower()} signal in this set."
                ),
                region_ids=strongest,
                evidence=evidence[:3],
            )
        )
    differentiators.sort(
        key=lambda factor: (
            -max(
                (
                    float(drivers[factor.code][region_id].get("contribution") or 0.0)
                    for region_id in drivers[factor.code]
                ),
                default=0.0,
            ),
            factor.code,
        )
    )
    return tuple(shared[:4]), tuple(differentiators[:5])


def _shared_weaknesses(fits: tuple[ExploreFitResult, ...]) -> tuple[ComparisonFactor, ...]:
    missing_counts = Counter(
        area for fit in fits for area in fit.market_coverage.evidence_areas_missing
    )
    shared = [area for area, count in missing_counts.items() if count == len(fits)]
    return tuple(
        ComparisonFactor(
            code=f"missing_{area}",
            label=area.replace("_", " ").title(),
            summary=f"All selected markets are missing {area.replace('_', ' ')} evidence.",
            region_ids=tuple(sorted(fit.region.region_id for fit in fits)),
        )
        for area in sorted(shared)[:4]
    )


def _market_advantages(
    fit: ExploreFitResult, shared: tuple[ComparisonFactor, ...]
) -> tuple[str, ...]:
    shared_codes = {factor.code for factor in shared}
    advantages = [
        str(driver.get("evidence") or driver.get("label"))
        for driver in fit.primary_drivers
        if str(driver.get("code")) not in shared_codes
        and (driver.get("evidence") or driver.get("label"))
    ]
    if not advantages:
        advantages = [
            str(driver.get("evidence") or driver.get("label"))
            for driver in fit.primary_drivers
            if driver.get("evidence") or driver.get("label")
        ]
    return tuple(dict.fromkeys(advantages))[:2]


def _market_tradeoffs(fit: ExploreFitResult) -> tuple[str, ...]:
    values = tuple(
        dict.fromkeys(
            (
                *fit.tradeoffs,
                *fit.hard_constraint_reasons,
                *(fit.material_limitations[:1]),
            )
        )
    )
    return values[:2] or ("No distinct governed tradeoff was returned.",)


def _confidence_caveat(fit: ExploreFitResult) -> str:
    if fit.state is ExploreFitState.TENTATIVE:
        return "Fit is tentative because governed evidence is limited."
    if fit.market_coverage.evidence_areas_missing:
        return "Some governed evidence areas are missing."
    return f"{fit.confidence.replace('_', ' ').title()} confidence from governed market evidence."


def _comparison_confidence(fits: tuple[ExploreFitResult, ...]) -> str:
    values = {fit.confidence.casefold() for fit in fits}
    if any(
        fit.state not in {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE} for fit in fits
    ) or values & {"low", "limited", "unknown"}:
        return "limited"
    if values == {"high"} and all(fit.state is ExploreFitState.CONFIDENT for fit in fits):
        return "high"
    return "moderate"


def _recommendation_summary(
    state: ExploreComparisonRecommendationState,
    fits: tuple[ExploreFitResult, ...],
    winners: tuple[str, ...],
    differentiators: tuple[ComparisonFactor, ...],
    confidence: str,
) -> str:
    names = {fit.region.region_id: fit.region.display_name for fit in fits}
    if state is ExploreComparisonRecommendationState.CLEAR_RECOMMENDATION:
        opening = f"{names[winners[0]]} is the best-supported market for this search."
    elif state is ExploreComparisonRecommendationState.NEAR_TIE:
        opening = (
            f"{' and '.join(names[item] for item in winners)} are effectively tied for this search."
        )
    elif state is ExploreComparisonRecommendationState.EXACT_TIE:
        opening = f"{' and '.join(names[item] for item in winners)} are tied under governed Fit."
    elif state is ExploreComparisonRecommendationState.BLOCKING_CONTRADICTION:
        opening = "Conflicting governed evidence prevents a recommendation."
    elif state is ExploreComparisonRecommendationState.UNSUPPORTED_MEMBER:
        opening = "This comparison is blocked because a selected market is unsupported."
    elif state is ExploreComparisonRecommendationState.OUTSIDE_CONSTRAINTS:
        opening = (
            "This comparison is blocked because a selected market is outside current constraints."
        )
    else:
        opening = "We do not have enough reliable evidence to recommend one market over the others."
    why = (
        differentiators[0].summary
        if differentiators
        else "The governed factors are materially similar or incomplete."
    )
    return (
        f"{opening} {why} Comparison confidence is {confidence}; current jobs "
        "and company counts did not affect this result."
    )


def _unique_findings(fits: tuple[ExploreFitResult, ...]) -> tuple[dict[str, Any], ...]:
    findings: dict[str, dict[str, Any]] = {}
    for fit in fits:
        for finding in fit.contradiction_findings:
            key = json.dumps(finding, sort_keys=True, default=str)
            findings.setdefault(key, finding)
    return tuple(findings[key] for key in sorted(findings))


def _decision_confidence(value: str) -> ConfidenceLevel:
    return {
        "high": ConfidenceLevel.HIGH,
        "moderate": ConfidenceLevel.MEDIUM,
        "limited": ConfidenceLevel.LOW,
    }.get(value, ConfidenceLevel.UNKNOWN)


def _decision_sufficiency(result: ExploreComparisonResult) -> DecisionEvidenceSufficiency:
    if result.recommendation_state is ExploreComparisonRecommendationState.UNSUPPORTED_MEMBER:
        return DecisionEvidenceSufficiency.NOT_SUPPORTED
    if result.abstained:
        return DecisionEvidenceSufficiency.INSUFFICIENT_EVIDENCE
    if any(market.fit.state is ExploreFitState.TENTATIVE for market in result.compared_markets):
        return DecisionEvidenceSufficiency.LIMITED_EVIDENCE
    return DecisionEvidenceSufficiency.COMPARISON_READY


def _context_summary(result: ExploreComparisonResult) -> str:
    goal = result.effective_context.goal
    if goal:
        return goal.replace("_", " ").title()
    roles = result.effective_context.role_families
    return (
        ", ".join(item.replace("_", " ").title() for item in roles[:2])
        or "General market intelligence"
    )


def _market_set_fingerprint(region_ids: tuple[str, ...]) -> str:
    return _stable_hash({"region_ids": sorted(region_ids)})


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
