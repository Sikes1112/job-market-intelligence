"""Deterministic grounding service for Layer 26A career-agent answers."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_agent.authorities import CareerAgentAuthorityAdapter
from backend.career_agent.schemas import (
    CareerAgentAnswer,
    CareerAgentEvidenceRef,
    CareerAgentEvidenceType,
    CareerAgentFreshness,
    CareerAgentFreshnessStatus,
    CareerAgentGuardrailStatus,
    CareerAgentGuardrailViolation,
    CareerAgentPreferenceSnapshot,
    CareerAgentQuestionType,
    CareerAgentRecommendation,
    CareerAgentRequest,
    CareerAgentTargetType,
    CareerAgentUncertainty,
    validate_career_agent_answer,
)
from backend.companies.models import Company
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.explore.schemas import ExploreFitState, ExploreSessionOverrides
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import OpportunityPayload
from backend.opportunities.service import OpportunityService
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.predictive_exports import (
    export_predictive_observations,
)
from backend.predictive.contracts import PredictiveReportForecast
from backend.predictive.reports import PredictiveReportBuilder
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus, evaluate_freshness

FORECAST_WARNING = (
    "Forecast evidence is a bounded directional signal, not a certain outcome."
)
NO_OPENING_WARNING = (
    "No stored verified opportunity record is attached; verify current openings "
    "manually before treating this as an application target."
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _RegionContext:
    region: Region
    score: RegionMarketScore | None
    hiring_rows: tuple[CompanyRegionHiring, ...]
    entry_rows: tuple[CompanyRegionEntryLevel, ...]
    evidence_refs: tuple[CareerAgentEvidenceRef, ...]
    freshness: CareerAgentFreshness
    confidence: Confidence
    base_score: float


@dataclass(frozen=True, slots=True)
class _CompanyContext:
    company: Company
    presence_rows: tuple[CompanyRegionPresence, ...]
    hiring_rows: tuple[CompanyRegionHiring, ...]
    entry_rows: tuple[CompanyRegionEntryLevel, ...]
    evidence_refs: tuple[CareerAgentEvidenceRef, ...]
    freshness: CareerAgentFreshness
    confidence: Confidence
    base_score: float


@dataclass(frozen=True, slots=True)
class _ForecastEvidence:
    ref: CareerAgentEvidenceRef
    confidence: Confidence
    confidence_score: float | None
    uncertainty_level: str
    limitations: tuple[str, ...]


class CareerAgentGroundingService:
    """Build governed career-agent answers from structured platform data."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._opportunity_service = OpportunityService(OpportunityRepository(session))
        self._authority = CareerAgentAuthorityAdapter.for_session(session)

    def answer_authoritative(
        self,
        user_id: str,
        request: CareerAgentRequest,
        *,
        now: datetime | None = None,
    ) -> CareerAgentAnswer:
        """Answer redesigned individual flows through the owning authorities."""

        if request.question_type in {
            CareerAgentQuestionType.CITY_FIT,
            CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY,
        }:
            try:
                return self._geographic_authority_answer(user_id, request, now=now)
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception(
                    "Explore Fit authority failed for Career Agent question type %s",
                    request.question_type.value,
                )
                return self._authority_unavailable_answer(
                    request,
                    authority="Explore Fit / Layer 34",
                    limitation=(
                        "Explore Fit is temporarily unavailable through the authoritative "
                        "Career Agent path; legacy Career Agent scoring was not used."
                    ),
                    now=now,
                )
        if request.question_type is CareerAgentQuestionType.WHERE_SHOULD_I_APPLY:
            try:
                return self._current_job_authority_answer(user_id, request, now=now)
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception(
                    "Layer 38 authority failed for Career Agent question type %s",
                    request.question_type.value,
                )
                return self._authority_unavailable_answer(
                    request,
                    authority="Layer 38 Current Opportunities",
                    limitation=(
                        "Layer 38 current-job coverage is temporarily unavailable through "
                        "the authoritative Career Agent path; legacy opportunity or Career "
                        "Agent scoring was not used."
                    ),
                    now=now,
                )
        if request.question_type is CareerAgentQuestionType.WHAT_SHOULD_I_DO_THIS_MONTH:
            try:
                decision, recommendation, review = self._authority.durable_decision(user_id)
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception(
                    "Durable Decision authority failed for Career Agent question type %s",
                    request.question_type.value,
                )
                return self._authority_unavailable_answer(
                    request,
                    authority="Layer 36 durable Decision",
                    limitation=(
                        "Durable Decision context is temporarily unavailable through the "
                        "authoritative Career Agent path; no replacement recommendation or "
                        "legacy scoring was used."
                    ),
                    now=now,
                )
            if decision is not None:
                try:
                    return self._decision_authority_answer(
                        request,
                        decision=decision,
                        recommendation=recommendation,
                        review=review,
                        now=now,
                    )
                except CareerAgentGuardrailViolation:
                    raise
                except Exception:
                    logger.exception(
                        "Durable Decision response failed for Career Agent question type %s",
                        request.question_type.value,
                    )
                    return self._authority_unavailable_answer(
                        request,
                        authority="Layer 36 durable Decision",
                        limitation=(
                            "Durable Decision context could not be represented through the "
                            "authoritative Career Agent path; no replacement recommendation "
                            "or legacy scoring was used."
                        ),
                        now=now,
                    )
            generated_at = _aware(now or datetime.now(UTC))
            return _authoritative_answer(
                request,
                generated_at=generated_at,
                recommendations=(),
                authority="Layer 36 durable Decision",
                limitations=(
                    "No durable Layer 36 Decision exists; Career Agent did not create "
                    "a competing market recommendation.",
                ),
            )
        if request.question_type is CareerAgentQuestionType.COMPANIES_TO_WATCH:
            return self._authority_unavailable_answer(
                request,
                authority="Career Agent authoritative company routing",
                limitation=(
                    "This question is not yet available through the authoritative Career "
                    "Agent path; no governed company-ranking authority is assigned, and "
                    "legacy Career Agent scoring was not used."
                ),
                now=now,
            )

        return self._authority_unavailable_answer(
            request,
            authority="Career Agent authoritative routing",
            limitation=(
                f"Question type '{request.question_type.value}' has no assigned production "
                "authority; legacy Career Agent scoring was not used."
            ),
            now=now,
        )

    def answer_for_plan(
        self,
        user_id: str,
        request: CareerAgentRequest,
        *,
        now: datetime | None = None,
    ) -> CareerAgentAnswer:
        """Supply planning inputs from the owning authorities, never the legacy scorer.

        A durable Decision is the first planning authority. Without one, the
        caller must explicitly select either Explore Fit or Layer 38 by question
        type. Authority failures are returned as bounded, recommendation-free
        answers so planning cannot silently fall through to another scorer.
        """

        try:
            decision, recommendation, review = self._authority.durable_decision(user_id)
        except CareerAgentGuardrailViolation:
            raise
        except Exception:
            logger.exception("Durable Decision authority failed for action planning")
            return self._authority_unavailable_answer(
                request,
                authority="Layer 36 durable Decision",
                limitation=(
                    "Durable Decision context is temporarily unavailable for action "
                    "planning; no replacement recommendation or legacy scoring was used."
                ),
                now=now,
            )
        if decision is not None:
            try:
                actions = self._authority.durable_decision_actions(
                    user_id,
                    decision_id=decision.decision_id,
                    limit=request.limit,
                )
                return self._decision_authority_answer(
                    request,
                    decision=decision,
                    recommendation=recommendation,
                    review=review,
                    actions=actions,
                    now=now,
                )
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception("Durable Decision could not be adapted for action planning")
                return self._authority_unavailable_answer(
                    request,
                    authority="Layer 36 durable Decision",
                    limitation=(
                        "Durable Decision context could not be represented for action "
                        "planning; no replacement recommendation or legacy scoring was used."
                    ),
                    now=now,
                )

        if request.question_type is CareerAgentQuestionType.WHERE_SHOULD_I_APPLY:
            return self.answer_authoritative(user_id, request, now=now)
        if request.question_type in {
            CareerAgentQuestionType.CITY_FIT,
            CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY,
        }:
            try:
                return self._geographic_authority_answer(
                    user_id,
                    request,
                    now=now,
                    allow_general_context=True,
                )
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception("Explore Fit authority failed for action planning")
                return self._authority_unavailable_answer(
                    request,
                    authority="Explore Fit / Layer 34",
                    limitation=(
                        "Explore Fit is temporarily unavailable for action planning; "
                        "legacy Career Agent scoring was not used."
                    ),
                    now=now,
                )

        return self._authority_unavailable_answer(
            request,
            authority="Career Agent planning authority routing",
            limitation=(
                "The requested action plan has no assigned authoritative input; more "
                "Decision, Explore, or current-job context is required, and legacy "
                "Career Agent scoring was not used."
            ),
            now=now,
        )

    def answer_for_tool_preview(
        self,
        user_id: str,
        request: CareerAgentRequest,
        *,
        now: datetime | None = None,
    ) -> CareerAgentAnswer:
        """Ground a preview without turning Explore context into a new choice."""

        if request.question_type in {
            CareerAgentQuestionType.CITY_FIT,
            CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY,
        }:
            try:
                return self._geographic_authority_answer(
                    user_id,
                    request,
                    now=now,
                    allow_general_context=True,
                )
            except CareerAgentGuardrailViolation:
                raise
            except Exception:
                logger.exception("Explore Fit authority failed for tool preview")
                return self._authority_unavailable_answer(
                    request,
                    authority="Explore Fit / Layer 34",
                    limitation=(
                        "Explore Fit is temporarily unavailable for tool preview; "
                        "legacy Career Agent scoring was not used."
                    ),
                    now=now,
                )
        return self.answer_authoritative(user_id, request, now=now)

    def _authority_unavailable_answer(
        self,
        request: CareerAgentRequest,
        *,
        authority: str,
        limitation: str,
        now: datetime | None,
    ) -> CareerAgentAnswer:
        return _authoritative_answer(
            request,
            generated_at=_aware(now or datetime.now(UTC)),
            recommendations=(),
            authority=authority,
            limitations=(limitation,),
        )

    def _geographic_authority_answer(
        self,
        user_id: str,
        request: CareerAgentRequest,
        *,
        now: datetime | None,
        allow_general_context: bool = False,
    ) -> CareerAgentAnswer:
        generated_at = _aware(now or datetime.now(UTC))
        role_inputs = request.target_role_families or (
            (request.user_goal,) if request.user_goal else ()
        )
        response = self._authority.geographic_fit(
            user_id,
            ExploreSessionOverrides(role_families=role_inputs or None),
            as_of=generated_at,
        )
        requested_regions = _canonical_requested_regions(
            self._session,
            request.target_region_ids,
        )
        eligible_states = {ExploreFitState.CONFIDENT, ExploreFitState.TENTATIVE}
        if allow_general_context:
            eligible_states.update(
                {
                    ExploreFitState.GENERAL_MARKET_INTELLIGENCE,
                    ExploreFitState.INSUFFICIENT_EVIDENCE,
                    ExploreFitState.ABSTAINED,
                }
            )
        candidates = tuple(
            market
            for market in response.markets
            if market.state in eligible_states
            and (not requested_regions or market.region.region_id in requested_regions)
        )[: request.limit]
        recommendations: list[CareerAgentRecommendation] = []
        for market in candidates:
            freshness = _authority_freshness(
                market.freshness,
                data_basis="layer_34_market_intelligence",
            )
            confidence = _authority_confidence(market.confidence)
            ref = CareerAgentEvidenceRef(
                ref_id=f"explore_fit:{market.region.region_id}",
                evidence_type=CareerAgentEvidenceType.MARKET,
                entity_type="region",
                entity_id=market.region.region_id,
                label=f"{market.region.display_name} Explore Fit",
                summary=market.market_coverage.summary,
                data_basis="layer_34_market_intelligence",
                freshness_status=freshness.freshness_status,
                confidence_label=market.confidence,
                source_count=len(market.market_coverage.evidence_areas_used),
            )
            context_only = market.state not in {
                ExploreFitState.CONFIDENT,
                ExploreFitState.TENTATIVE,
            }
            recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id(
                        "career_rec", "explore_fit", market.region.region_id
                    ),
                    recommendation_type=(
                        "explore_market_context"
                        if context_only
                        else "explore_geographic_fit"
                    ),
                    rank=(
                        len(recommendations) + 1
                        if context_only
                        else market.rank or len(recommendations) + 1
                    ),
                    target_type=CareerAgentTargetType.REGION,
                    target_id=market.region.region_id,
                    title=(
                        f"{market.region.display_name} market context"
                        if context_only
                        else f"{market.region.display_name} geographic fit"
                    ),
                    summary=(
                        f"Explore reports {market.fit_band or market.state.value} from "
                        "governed Layer 34 market evidence."
                    ),
                    score=market.fit_score,
                    action=(
                        "Compare this market context without treating display order as a "
                        "personalized winner."
                        if context_only
                        else "Review Explore Fit drivers, tradeoffs, and evidence coverage."
                    ),
                    evidence_refs=(ref,),
                    freshness=freshness,
                    uncertainty=CareerAgentUncertainty(
                        confidence_level=confidence,
                        confidence_score=_confidence_score(confidence),
                        uncertainty_level=_uncertainty_level(
                            confidence, {freshness.freshness_status}
                        ),
                        reasons=(
                            "Uses authoritative Explore context without market rescoring.",
                        ),
                        limitations=market.material_limitations,
                    ),
                    limitations=market.material_limitations,
                )
            )
        limitations = list(response.limitations)
        if not recommendations:
            limitations.append(
                "Explore Fit did not return an eligible personalized geographic result."
            )
        return _authoritative_answer(
            request,
            generated_at=generated_at,
            recommendations=tuple(recommendations),
            authority="Explore Fit / Layer 34",
            limitations=tuple(dict.fromkeys(limitations)),
        )

    def _current_job_authority_answer(
        self,
        user_id: str,
        request: CareerAgentRequest,
        *,
        now: datetime | None,
    ) -> CareerAgentAnswer:
        generated_at = _aware(now or datetime.now(UTC))
        matches = self._authority.current_job_matches(
            user_id,
            request_terms=(
                *request.target_role_families,
                *request.target_region_ids,
                *((request.user_goal,) if request.user_goal else ()),
            ),
            limit=500,
            as_of=generated_at,
        )
        requested_regions = _canonical_requested_regions(
            self._session,
            request.target_region_ids,
        )
        requested_roles = {item.casefold() for item in request.target_role_families}
        selected = tuple(
            match
            for match in matches
            if (
                not requested_regions
                or match.opportunity.market_id in requested_regions
            )
            and (
                not requested_roles
                or match.opportunity.role_family.casefold() in requested_roles
            )
        )[: request.limit]
        recommendations: list[CareerAgentRecommendation] = []
        for match in selected:
            opportunity = match.opportunity
            freshness = _authority_freshness(
                opportunity.freshness_state.value,
                data_basis="layer_38_current_opportunities",
                observed_at=opportunity.last_observed_at,
            )
            confidence = _authority_confidence(opportunity.identity_confidence.value)
            ref = CareerAgentEvidenceRef(
                ref_id=f"current_opportunity:{opportunity.opportunity_id}",
                evidence_type=CareerAgentEvidenceType.OPPORTUNITY,
                entity_type="current_opportunity",
                entity_id=opportunity.opportunity_id,
                label=f"{opportunity.company_name}: {opportunity.original_title}",
                summary="Layer 38 active current-opportunity record.",
                data_basis="layer_38_current_opportunities",
                freshness_status=freshness.freshness_status,
                confidence_label=opportunity.identity_confidence.value,
                source_count=_provenance_source_count(opportunity.provenance),
                observed_at=opportunity.last_observed_at,
                public_url=opportunity.application_url or opportunity.source_url,
            )
            recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id(
                        "career_rec", "current_job", opportunity.opportunity_id
                    ),
                    recommendation_type="layer_38_current_job_match",
                    rank=len(recommendations) + 1,
                    target_type=CareerAgentTargetType.OPPORTUNITY,
                    target_id=opportunity.opportunity_id,
                    title=f"{opportunity.company_name}: {opportunity.original_title}",
                    summary=(
                        f"Layer 38 match relevance: {match.strategic_relevance}."
                    ),
                    score=match.match_score,
                    action="Verify the live source and application details before acting.",
                    evidence_refs=(ref,),
                    freshness=freshness,
                    uncertainty=CareerAgentUncertainty(
                        confidence_level=confidence,
                        confidence_score=_confidence_score(confidence),
                        uncertainty_level=_uncertainty_level(
                            confidence, {freshness.freshness_status}
                        ),
                        reasons=match.contributing_factors,
                        limitations=match.limitations,
                    ),
                    matched_opportunity_ids=(opportunity.opportunity_id,),
                    warnings=match.warnings,
                    limitations=match.limitations,
                )
            )
        limitations: list[str] = []
        if not recommendations:
            coverage_market = next(iter(requested_regions), "*")
            coverage_role = next(iter(request.target_role_families), "*")
            coverage = self._authority.current_job_coverage(
                market_key=coverage_market,
                role_family=coverage_role,
                as_of=generated_at,
            )
            status = coverage.effective_status.value if coverage is not None else "unavailable"
            limitations.append(
                "Layer 38 current-job coverage is "
                f"{status}; no current jobs were invented or substituted from legacy routes."
            )
            if coverage is not None:
                limitations.extend(coverage.limitations)
        return _authoritative_answer(
            request,
            generated_at=generated_at,
            recommendations=tuple(recommendations),
            authority="Layer 38 Current Opportunities",
            limitations=tuple(dict.fromkeys(limitations)),
        )

    def _decision_authority_answer(
        self,
        request: CareerAgentRequest,
        *,
        decision,
        recommendation,
        review,
        actions: tuple = (),
        now: datetime | None,
    ) -> CareerAgentAnswer:
        generated_at = _aware(now or datetime.now(UTC))
        summary = (
            recommendation.summary
            if recommendation is not None and recommendation.summary
            else f"Layer 36 decision status: {decision.status}."
        )
        action = None
        if review is not None and review.suggested_next_actions:
            action = str(review.suggested_next_actions[0])[:1024]
        elif decision.planned_review_at is not None:
            action = f"Review this decision at {decision.planned_review_at.date().isoformat()}."
        ref = CareerAgentEvidenceRef(
            ref_id=f"career_decision:{decision.decision_id}",
            evidence_type=CareerAgentEvidenceType.MARKET,
            entity_type="career_decision",
            entity_id=decision.decision_id,
            label=decision.title,
            summary=summary,
            data_basis="layer_36_durable_decision",
            freshness_status=CareerAgentFreshnessStatus.FRESH,
            confidence_label=(recommendation.confidence if recommendation else "unknown"),
            source_count=1 + int(review is not None),
            observed_at=decision.updated_at,
        )
        rec = CareerAgentRecommendation(
            recommendation_id=_stable_id(
                "career_rec", "durable_decision", decision.decision_id
            ),
            recommendation_type="layer_36_durable_decision",
            rank=1,
            target_type=CareerAgentTargetType.MONTHLY_ACTION,
            target_id=decision.decision_id,
            title=decision.title,
            summary=summary,
            action=action or "Review the durable decision and its recorded next steps.",
            evidence_refs=(ref,),
            freshness=_authority_freshness(
                "fresh", data_basis="layer_36_durable_decision", observed_at=decision.updated_at
            ),
            uncertainty=CareerAgentUncertainty(
                confidence_level=_authority_confidence(
                    recommendation.confidence if recommendation else "unknown"
                ),
                reasons=(
                    "Layer 36 owns the durable recommendation; Layer 37 supplies deeper analysis."
                ,),
                limitations=tuple(recommendation.limitations or ())
                if recommendation is not None
                else (),
            ),
            limitations=tuple(recommendation.limitations or ())
            if recommendation is not None
            else (),
        )
        action_recommendations: list[CareerAgentRecommendation] = []
        for index, decision_action in enumerate(actions, start=2):
            action_summary = str(
                decision_action.description
                or "Layer 36 action attached to the durable Decision."
            )[:1024]
            action_ref = CareerAgentEvidenceRef(
                ref_id=f"career_decision_action:{decision_action.action_id}",
                evidence_type=CareerAgentEvidenceType.MARKET,
                entity_type="career_decision_action",
                entity_id=decision_action.action_id,
                label=decision_action.title,
                summary=action_summary,
                data_basis="layer_36_durable_decision_action",
                freshness_status=CareerAgentFreshnessStatus.FRESH,
                confidence_label=(recommendation.confidence if recommendation else "unknown"),
                source_count=1,
                observed_at=decision_action.updated_at,
            )
            action_recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id(
                        "career_rec", "durable_decision_action", decision_action.action_id
                    ),
                    recommendation_type="layer_36_durable_decision_action",
                    rank=index,
                    target_type=CareerAgentTargetType.MONTHLY_ACTION,
                    target_id=decision_action.action_id,
                    title=decision_action.title,
                    summary=action_ref.summary,
                    action=decision_action.title,
                    evidence_refs=(action_ref,),
                    freshness=_authority_freshness(
                        "fresh",
                        data_basis="layer_36_durable_decision_action",
                        observed_at=decision_action.updated_at,
                    ),
                    uncertainty=CareerAgentUncertainty(
                        confidence_level=_authority_confidence(
                            recommendation.confidence if recommendation else "unknown"
                        ),
                        reasons=(
                            "Layer 36 owns this action under the durable Decision.",
                        ),
                    ),
                )
            )
        return _authoritative_answer(
            request,
            generated_at=generated_at,
            recommendations=(rec, *action_recommendations),
            authority=(
                "Layer 36 durable Decision with Layer 37 analysis"
                if review is not None
                else "Layer 36 durable Decision"
            ),
            limitations=(),
        )

    def answer(
        self,
        request: CareerAgentRequest,
        *,
        now: datetime | None = None,
    ) -> CareerAgentAnswer:
        generated_at = _aware(now or datetime.now(UTC))
        preferences = _preference_snapshot(request)
        regions = self._region_contexts(request.target_region_ids, now=generated_at)
        companies = self._company_contexts(
            company_ids=request.target_company_ids,
            region_ids=request.target_region_ids,
            now=generated_at,
        )
        forecasts_by_region, forecasts_by_company = self._forecast_evidence(
            request,
            regions=regions,
            companies=companies,
            generated_at=generated_at,
        )

        if request.question_type is CareerAgentQuestionType.WHERE_SHOULD_I_APPLY:
            recommendations = self._where_should_i_apply(
                request,
                regions=regions,
                companies=companies,
                forecasts_by_region=forecasts_by_region,
                preferences=preferences,
                now=generated_at,
            )
        elif request.question_type is CareerAgentQuestionType.CITY_FIT:
            recommendations = self._city_fit(
                request,
                regions=regions,
                forecasts_by_region=forecasts_by_region,
                preferences=preferences,
            )
        elif request.question_type is CareerAgentQuestionType.COMPANIES_TO_WATCH:
            recommendations = self._companies_to_watch(
                request,
                companies=companies,
                forecasts_by_company=forecasts_by_company,
                preferences=preferences,
            )
        elif request.question_type is CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY:
            recommendations = self._strongest_market_strategy(
                request,
                regions=regions,
                forecasts_by_region=forecasts_by_region,
                preferences=preferences,
            )
        else:
            recommendations = self._what_should_i_do_this_month(
                request,
                regions=regions,
                companies=companies,
                forecasts_by_region=forecasts_by_region,
                forecasts_by_company=forecasts_by_company,
                preferences=preferences,
                now=generated_at,
            )

        limitations = _answer_limitations(recommendations, regions, companies)
        answer_freshness = _aggregate_freshness(
            tuple(rec.freshness for rec in recommendations),
            fallback_source_count=sum(
                ref.source_count
                for rec in recommendations
                for ref in rec.evidence_refs
            ),
        )
        answer_uncertainty = _aggregate_uncertainty(
            tuple(rec.uncertainty for rec in recommendations)
        )
        guardrails = CareerAgentGuardrailStatus(
            passed=True,
            evidence_requirement_met=bool(recommendations)
            and all(rec.evidence_refs for rec in recommendations),
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for rec in recommendations
                    for warning in rec.warnings
                )
            ),
        )
        answer = CareerAgentAnswer(
            answer_id=_stable_id(
                "career_answer",
                request.question_type.value,
                generated_at.isoformat(),
                *(rec.recommendation_id for rec in recommendations),
            ),
            question_type=request.question_type,
            generated_at=generated_at,
            summary=_answer_summary(request.question_type, recommendations, limitations),
            recommendations=recommendations,
            freshness=answer_freshness,
            source_freshness=tuple(
                rec.freshness for rec in recommendations
            )
            or (answer_freshness,),
            uncertainty=answer_uncertainty,
            preference_snapshot=preferences,
            guardrails=guardrails,
            limitations=limitations,
        )
        validate_career_agent_answer(answer)
        return answer

    def _where_should_i_apply(
        self,
        request: CareerAgentRequest,
        *,
        regions: tuple[_RegionContext, ...],
        companies: tuple[_CompanyContext, ...],
        forecasts_by_region: dict[str, tuple[_ForecastEvidence, ...]],
        preferences: CareerAgentPreferenceSnapshot | None,
        now: datetime,
    ) -> tuple[CareerAgentRecommendation, ...]:
        opportunities = self._filtered_active_opportunities(request, now=now)
        region_by_id = {ctx.region.region_id: ctx for ctx in regions}
        company_by_id = {ctx.company.company_id: ctx for ctx in companies}
        recommendations: list[CareerAgentRecommendation] = []
        for opportunity in opportunities:
            refs = [self._opportunity_ref(opportunity)]
            region_ids = _opportunity_region_ids(opportunity)
            for region_id in region_ids:
                context = region_by_id.get(region_id)
                if context is not None:
                    refs.extend(context.evidence_refs[:2])
                    refs.extend(item.ref for item in forecasts_by_region.get(region_id, ())[:1])
                    break
            if opportunity.employer_id and opportunity.employer_id in company_by_id:
                refs.extend(company_by_id[opportunity.employer_id].evidence_refs[:2])
            freshness = _aggregate_freshness(
                tuple(_freshness_from_ref(ref) for ref in refs),
                fallback_source_count=sum(ref.source_count for ref in refs),
            )
            forecast_evidence = _forecast_from_refs(refs, forecasts_by_region)
            uncertainty = _uncertainty_from_evidence(
                refs,
                base_confidence=Confidence.HIGH,
                forecast_evidence=forecast_evidence,
            )
            warnings = _opportunity_warnings(opportunity)
            if forecast_evidence:
                warnings = (*warnings, FORECAST_WARNING)
            score = _bounded(
                0.72
                + _preference_boost(
                    target_id=opportunity.employer_id or opportunity.id,
                    region_ids=region_ids,
                    role_families=opportunity.role_families,
                    preferences=preferences,
                )
            )
            recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id("career_rec", "apply", opportunity.id),
                    recommendation_type="grounded_application_target",
                    rank=1,
                    target_type=CareerAgentTargetType.OPPORTUNITY,
                    target_id=opportunity.id,
                    title=f"{opportunity.employer_name}: {opportunity.program_name}",
                    summary=(
                        "This application target is backed by a stored active "
                        f"{opportunity.trust_label.value} opportunity record."
                    ),
                    score=score,
                    action=(
                        "Manually verify eligibility, deadline, location, and source page "
                        "before applying."
                    ),
                    evidence_refs=tuple(_dedupe_refs(refs)),
                    freshness=freshness,
                    uncertainty=uncertainty,
                    preference_alignment=_preference_alignment(
                        target_id=opportunity.employer_id or opportunity.id,
                        region_ids=region_ids,
                        role_families=opportunity.role_families,
                        preferences=preferences,
                    ),
                    matched_opportunity_ids=(opportunity.id,),
                    warnings=warnings,
                    limitations=_forecast_limitations(forecast_evidence),
                )
            )

        if recommendations:
            return _ranked(recommendations, limit=request.limit)

        fallback = self._city_fit(
            request,
            regions=regions,
            forecasts_by_region=forecasts_by_region,
            preferences=preferences,
            recommendation_type="application_market_focus",
            action=(
                "Use this as a market focus area, then verify active openings directly "
                "with employer or program sources."
            ),
            extra_warning=NO_OPENING_WARNING,
        )
        return fallback[: request.limit]

    def _city_fit(
        self,
        request: CareerAgentRequest,
        *,
        regions: tuple[_RegionContext, ...],
        forecasts_by_region: dict[str, tuple[_ForecastEvidence, ...]],
        preferences: CareerAgentPreferenceSnapshot | None,
        recommendation_type: str = "city_fit",
        action: str | None = None,
        extra_warning: str | None = None,
    ) -> tuple[CareerAgentRecommendation, ...]:
        recommendations: list[CareerAgentRecommendation] = []
        for context in regions:
            forecast_evidence = forecasts_by_region.get(context.region.region_id, ())
            refs = (*context.evidence_refs, *(item.ref for item in forecast_evidence[:1]))
            score = _bounded(
                context.base_score
                + _preference_boost(
                    target_id=context.region.region_id,
                    region_ids=(context.region.region_id,),
                    role_families=request.target_role_families,
                    preferences=preferences,
                )
            )
            warnings = list(context.freshness.warnings)
            limitations = list(_context_limitations(context.freshness, context.confidence))
            if forecast_evidence:
                warnings.append(FORECAST_WARNING)
                limitations.extend(_forecast_limitations(forecast_evidence))
            if extra_warning:
                warnings.append(extra_warning)
            recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id(
                        "career_rec",
                        recommendation_type,
                        context.region.region_id,
                    ),
                    recommendation_type=recommendation_type,
                    rank=1,
                    target_type=CareerAgentTargetType.REGION,
                    target_id=context.region.region_id,
                    title=f"{context.region.display_name} career fit",
                    summary=_region_summary(context),
                    score=score,
                    action=action
                    or "Compare this city against your role, location, and timing constraints.",
                    evidence_refs=tuple(_dedupe_refs(refs)),
                    freshness=_aggregate_freshness(
                        tuple(_freshness_from_ref(ref) for ref in refs),
                        fallback_source_count=sum(ref.source_count for ref in refs),
                    ),
                    uncertainty=_uncertainty_from_evidence(
                        refs,
                        base_confidence=context.confidence,
                        forecast_evidence=forecast_evidence,
                    ),
                    preference_alignment=_preference_alignment(
                        target_id=context.region.region_id,
                        region_ids=(context.region.region_id,),
                        role_families=request.target_role_families,
                        preferences=preferences,
                    ),
                    warnings=tuple(dict.fromkeys(warnings)),
                    limitations=tuple(dict.fromkeys(limitations)),
                )
            )
        return _ranked(recommendations, limit=request.limit)

    def _companies_to_watch(
        self,
        request: CareerAgentRequest,
        *,
        companies: tuple[_CompanyContext, ...],
        forecasts_by_company: dict[str, tuple[_ForecastEvidence, ...]],
        preferences: CareerAgentPreferenceSnapshot | None,
    ) -> tuple[CareerAgentRecommendation, ...]:
        recommendations: list[CareerAgentRecommendation] = []
        for context in companies:
            forecast_evidence = forecasts_by_company.get(context.company.company_id, ())
            refs = (*context.evidence_refs, *(item.ref for item in forecast_evidence[:1]))
            role_families = _company_role_families(context.hiring_rows)
            score = _bounded(
                context.base_score
                + _preference_boost(
                    target_id=context.company.company_id,
                    region_ids=tuple(row.region_id for row in context.presence_rows),
                    role_families=role_families,
                    preferences=preferences,
                )
            )
            warnings = list(context.freshness.warnings)
            limitations = list(_context_limitations(context.freshness, context.confidence))
            if forecast_evidence:
                warnings.append(FORECAST_WARNING)
                limitations.extend(_forecast_limitations(forecast_evidence))
            recommendations.append(
                CareerAgentRecommendation(
                    recommendation_id=_stable_id(
                        "career_rec",
                        "company_watch",
                        context.company.company_id,
                    ),
                    recommendation_type="company_watch",
                    rank=1,
                    target_type=CareerAgentTargetType.COMPANY,
                    target_id=context.company.company_id,
                    title=f"Watch {context.company.company_name}",
                    summary=_company_summary(context),
                    score=score,
                    action=(
                        "Track official career pages and compare any active roles "
                        "against the structured presence, hiring, and entry-level evidence."
                    ),
                    evidence_refs=tuple(_dedupe_refs(refs)),
                    freshness=_aggregate_freshness(
                        tuple(_freshness_from_ref(ref) for ref in refs),
                        fallback_source_count=sum(ref.source_count for ref in refs),
                    ),
                    uncertainty=_uncertainty_from_evidence(
                        refs,
                        base_confidence=context.confidence,
                        forecast_evidence=forecast_evidence,
                    ),
                    preference_alignment=_preference_alignment(
                        target_id=context.company.company_id,
                        region_ids=tuple(row.region_id for row in context.presence_rows),
                        role_families=role_families,
                        preferences=preferences,
                    ),
                    warnings=tuple(dict.fromkeys(warnings)),
                    limitations=tuple(dict.fromkeys(limitations)),
                )
            )
        return _ranked(recommendations, limit=request.limit)

    def _strongest_market_strategy(
        self,
        request: CareerAgentRequest,
        *,
        regions: tuple[_RegionContext, ...],
        forecasts_by_region: dict[str, tuple[_ForecastEvidence, ...]],
        preferences: CareerAgentPreferenceSnapshot | None,
    ) -> tuple[CareerAgentRecommendation, ...]:
        city_recommendations = self._city_fit(
            request,
            regions=regions,
            forecasts_by_region=forecasts_by_region,
            preferences=preferences,
            recommendation_type="market_strategy",
            action=(
                "Use this as a primary market lane, then validate company and "
                "opportunity specifics before acting."
            ),
        )
        return tuple(
            rec.model_copy(
                update={
                    "target_type": CareerAgentTargetType.MARKET_STRATEGY,
                    "title": f"Market strategy: {rec.title}",
                    "summary": (
                        f"{rec.summary} Treat this as strategic market guidance, "
                        "not as a claim that openings exist."
                    ),
                }
            )
            for rec in city_recommendations
        )

    def _what_should_i_do_this_month(
        self,
        request: CareerAgentRequest,
        *,
        regions: tuple[_RegionContext, ...],
        companies: tuple[_CompanyContext, ...],
        forecasts_by_region: dict[str, tuple[_ForecastEvidence, ...]],
        forecasts_by_company: dict[str, tuple[_ForecastEvidence, ...]],
        preferences: CareerAgentPreferenceSnapshot | None,
        now: datetime,
    ) -> tuple[CareerAgentRecommendation, ...]:
        recommendations: list[CareerAgentRecommendation] = []
        opportunities = self._where_should_i_apply(
            request.model_copy(update={"limit": 1}),
            regions=regions,
            companies=companies,
            forecasts_by_region=forecasts_by_region,
            preferences=preferences,
            now=now,
        )
        if opportunities:
            recommendations.append(
                _monthly_copy(
                    opportunities[0],
                    recommendation_type="monthly_verified_opportunity_check",
                    title="Verify one grounded opportunity first",
                    action=(
                        "Check eligibility, deadline, and location on the stored source "
                        "page before taking any application step."
                    ),
                )
            )
        city = self._city_fit(
            request.model_copy(update={"limit": 1}),
            regions=regions,
            forecasts_by_region=forecasts_by_region,
            preferences=preferences,
            recommendation_type="monthly_market_focus",
        )
        if city:
            recommendations.append(
                _monthly_copy(
                    city[0],
                    recommendation_type="monthly_market_focus",
                    title="Pick one market focus",
                    action=(
                        "Use the strongest grounded city fit to organize research and "
                        "avoid spreading effort across weak-evidence markets."
                    ),
                )
            )
        company = self._companies_to_watch(
            request.model_copy(update={"limit": 1}),
            companies=companies,
            forecasts_by_company=forecasts_by_company,
            preferences=preferences,
        )
        if company:
            recommendations.append(
                _monthly_copy(
                    company[0],
                    recommendation_type="monthly_company_watch",
                    title="Track one evidence-backed employer",
                    action=(
                        "Review official employer pages manually and compare any role "
                        "against the stored company evidence before prioritizing it."
                    ),
                )
            )
        return _ranked(recommendations, limit=request.limit)

    def _region_contexts(
        self,
        region_ids: Iterable[str],
        *,
        now: datetime,
    ) -> tuple[_RegionContext, ...]:
        resolver = GeographicResolver(RegionRepository(self._session))
        raw_requested = tuple(dict.fromkeys(region_ids))
        requested = tuple(
            dict.fromkeys(
                resolution.region_id
                for value in raw_requested
                if (resolution := resolver.resolve(value)).resolved
                and resolution.region_id is not None
            )
        )
        regions = tuple(RegionRepository(self._session).list())
        if raw_requested:
            regions = tuple(region for region in regions if region.region_id in requested)
        eligible_region_ids = ranking_eligible_fact_ids(
            self._session,
            "region",
            [region.region_id for region in regions],
        )
        regions = tuple(
            region for region in regions if region.region_id in eligible_region_ids
        )
        contexts: list[_RegionContext] = []
        for region in regions:
            score = self._session.execute(
                select(RegionMarketScore)
                .where(RegionMarketScore.region_id == region.region_id)
                .order_by(RegionMarketScore.region_score_id)
                .limit(1)
            ).scalar_one_or_none()
            hiring_rows = tuple(
                self._session.execute(
                    select(CompanyRegionHiring)
                    .where(CompanyRegionHiring.region_id == region.region_id)
                    .order_by(CompanyRegionHiring.company_id)
                ).scalars()
            )
            hiring_rows = self._ranking_eligible_rows(
                "company_region_hiring",
                hiring_rows,
                "hiring_id",
            )
            entry_rows = tuple(
                self._session.execute(
                    select(CompanyRegionEntryLevel)
                    .where(CompanyRegionEntryLevel.region_id == region.region_id)
                    .order_by(CompanyRegionEntryLevel.company_id)
                ).scalars()
            )
            entry_rows = self._ranking_eligible_rows(
                "company_region_entry_level",
                entry_rows,
                "entry_level_id",
            )
            freshness = _freshness_for_rows(
                (*(([score] if score is not None else [])), *hiring_rows, *entry_rows),
                data_basis="region_market_scores_and_canonical_market_rows",
                now=now,
            )
            confidence = _confidence_from_labels(
                *(
                    row.hiring_confidence
                    for row in hiring_rows
                    if row.hiring_confidence is not None
                ),
                *(
                    row.entry_level_confidence
                    for row in entry_rows
                    if row.entry_level_confidence is not None
                ),
            )
            evidence_refs = tuple(
                _dedupe_refs(
                    (
                        self._region_ref(region),
                        *(
                            (self._region_score_ref(region, score, freshness),)
                            if score is not None
                            else ()
                        ),
                    )
                )
            )
            contexts.append(
                _RegionContext(
                    region=region,
                    score=score,
                    hiring_rows=hiring_rows,
                    entry_rows=entry_rows,
                    evidence_refs=evidence_refs,
                    freshness=freshness,
                    confidence=confidence,
                    base_score=_region_base_score(score, hiring_rows, entry_rows),
                )
            )
        return tuple(
            sorted(
                contexts,
                key=lambda context: (-context.base_score, context.region.region_id),
            )
        )

    def _company_contexts(
        self,
        *,
        company_ids: Iterable[str],
        region_ids: Iterable[str],
        now: datetime,
    ) -> tuple[_CompanyContext, ...]:
        requested_companies = tuple(dict.fromkeys(company_ids))
        requested_regions = frozenset(region_ids)
        stmt = select(Company).order_by(Company.company_id)
        if requested_companies:
            stmt = stmt.where(Company.company_id.in_(requested_companies))
        companies = tuple(self._session.execute(stmt).scalars())
        eligible_company_ids = ranking_eligible_fact_ids(
            self._session,
            "company",
            [company.company_id for company in companies],
        )
        companies = tuple(
            company for company in companies if company.company_id in eligible_company_ids
        )
        contexts: list[_CompanyContext] = []
        for company in companies:
            presence_rows = self._rows_for_company(
                CompanyRegionPresence,
                company.company_id,
                requested_regions,
            )
            presence_rows = self._ranking_eligible_rows(
                "company_region_presence",
                presence_rows,
                "presence_id",
            )
            hiring_rows = self._rows_for_company(
                CompanyRegionHiring,
                company.company_id,
                requested_regions,
            )
            hiring_rows = self._ranking_eligible_rows(
                "company_region_hiring",
                hiring_rows,
                "hiring_id",
            )
            entry_rows = self._rows_for_company(
                CompanyRegionEntryLevel,
                company.company_id,
                requested_regions,
            )
            entry_rows = self._ranking_eligible_rows(
                "company_region_entry_level",
                entry_rows,
                "entry_level_id",
            )
            freshness = _freshness_for_rows(
                (*presence_rows, *hiring_rows, *entry_rows),
                data_basis="canonical_company_presence_hiring_entry_level",
                now=now,
            )
            confidence = _confidence_from_labels(
                company.classification_confidence,
                *(row.presence_confidence for row in presence_rows),
                *(row.hiring_confidence for row in hiring_rows),
                *(row.entry_level_confidence for row in entry_rows),
            )
            evidence_refs = _dedupe_refs(
                (
                    self._company_ref(company),
                    *(
                        (self._presence_ref(company, presence_rows[0], freshness),)
                        if presence_rows
                        else ()
                    ),
                    *(
                        (self._hiring_ref(company, hiring_rows[0], freshness),)
                        if hiring_rows
                        else ()
                    ),
                    *(
                        (self._entry_level_ref(company, entry_rows[0], freshness),)
                        if entry_rows
                        else ()
                    ),
                )
            )
            contexts.append(
                _CompanyContext(
                    company=company,
                    presence_rows=presence_rows,
                    hiring_rows=hiring_rows,
                    entry_rows=entry_rows,
                    evidence_refs=tuple(evidence_refs),
                    freshness=freshness,
                    confidence=confidence,
                    base_score=_company_base_score(company, presence_rows, hiring_rows, entry_rows),
                )
            )
        return tuple(
            sorted(
                contexts,
                key=lambda context: (-context.base_score, context.company.company_id),
            )
        )

    def _rows_for_company(
        self,
        model: type,
        company_id: str,
        region_ids: frozenset[str],
    ) -> tuple:
        stmt = select(model).where(model.company_id == company_id).order_by(model.region_id)
        if region_ids:
            stmt = stmt.where(model.region_id.in_(region_ids))
        return tuple(self._session.execute(stmt).scalars())

    def _ranking_eligible_rows(
        self,
        fact_type: str,
        rows: tuple,
        id_attr: str,
    ) -> tuple:
        eligible_ids = ranking_eligible_fact_ids(
            self._session,
            fact_type,
            [getattr(row, id_attr, None) for row in rows],
        )
        return tuple(row for row in rows if getattr(row, id_attr, None) in eligible_ids)

    def _forecast_evidence(
        self,
        request: CareerAgentRequest,
        *,
        regions: tuple[_RegionContext, ...],
        companies: tuple[_CompanyContext, ...],
        generated_at: datetime,
    ) -> tuple[
        dict[str, tuple[_ForecastEvidence, ...]],
        dict[str, tuple[_ForecastEvidence, ...]],
    ]:
        if not request.include_forecasts:
            return {}, {}
        observations = export_predictive_observations(
            HistoryRepository(self._session),
            region_ids=tuple(context.region.region_id for context in regions[:25]),
            company_ids=tuple(context.company.company_id for context in companies[:25]),
            limit_per_subject=500,
        )
        if not observations:
            return {}, {}
        report = PredictiveReportBuilder().build_report(
            observations,
            generated_at=generated_at,
            now=generated_at.date(),
        )
        by_region: dict[str, list[_ForecastEvidence]] = {}
        by_company: dict[str, list[_ForecastEvidence]] = {}
        for section in report.sections:
            for forecast in section.forecasts:
                evidence = _forecast_evidence_ref(forecast)
                region_id = forecast.affected_entity.region_id
                company_id = forecast.affected_entity.company_id
                if region_id:
                    by_region.setdefault(region_id, []).append(evidence)
                if company_id:
                    by_company.setdefault(company_id, []).append(evidence)
        return (
            {key: tuple(value) for key, value in by_region.items()},
            {key: tuple(value) for key, value in by_company.items()},
        )

    def _filtered_active_opportunities(
        self,
        request: CareerAgentRequest,
        *,
        now: datetime,
    ) -> tuple[OpportunityPayload, ...]:
        target_regions = frozenset(request.target_region_ids)
        target_roles = frozenset(request.target_role_families)
        preferred_program_types = frozenset(request.preferred_program_types)
        preferred_location_modes = frozenset(request.preferred_location_modes)
        opportunities = self._opportunity_service.list_active_verified_opportunities(
            now=now,
            limit=500,
        ).opportunities
        filtered = []
        for opportunity in opportunities:
            if target_regions and not (target_regions & set(_opportunity_region_ids(opportunity))):
                continue
            if target_roles and not (target_roles & set(opportunity.role_families)):
                continue
            if (
                preferred_program_types
                and opportunity.program_type.value not in preferred_program_types
            ):
                continue
            if (
                preferred_location_modes
                and opportunity.location_mode.value not in preferred_location_modes
            ):
                continue
            filtered.append(opportunity)
        return tuple(
            sorted(
                filtered,
                key=lambda opportunity: (
                    opportunity.application_deadline or date.max,
                    opportunity.employer_name,
                    opportunity.program_name,
                    opportunity.id,
                ),
            )
        )

    def _region_ref(self, region: Region) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"region:{region.region_id}",
            evidence_type=CareerAgentEvidenceType.REGION,
            entity_type="region",
            entity_id=region.region_id,
            label=region.display_name,
            summary=f"Canonical region metadata for {region.display_name}.",
            data_basis="canonical_region",
            freshness_status=CareerAgentFreshnessStatus.UNKNOWN,
            source_count=1,
            observed_at=_aware(getattr(region, "updated_at", None)),
        )

    def _region_score_ref(
        self,
        region: Region,
        score: RegionMarketScore,
        freshness: CareerAgentFreshness,
    ) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"region_score:{score.region_score_id}",
            evidence_type=CareerAgentEvidenceType.REGION_SCORE,
            entity_type="region_score",
            entity_id=score.region_score_id,
            label=f"{region.display_name} market score",
            summary=(
                "Stored region score with objective opportunity "
                f"{_score_label(score.objective_opportunity_score)} and early-career "
                f"access {_score_label(score.early_career_accessibility_score)}."
            ),
            data_basis="region_market_scores",
            freshness_status=freshness.freshness_status,
            confidence_label="structured_score",
            source_count=max(1, freshness.source_count),
            observed_at=_aware(getattr(score, "updated_at", None)),
        )

    def _company_ref(self, company: Company) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"company:{company.company_id}",
            evidence_type=CareerAgentEvidenceType.COMPANY,
            entity_type="company",
            entity_id=company.company_id,
            label=company.company_name,
            summary=(
                f"Canonical company metadata in sector {_display(company.sector_primary)} "
                f"with classification confidence {_display(company.classification_confidence)}."
            ),
            data_basis="canonical_company",
            freshness_status=CareerAgentFreshnessStatus.UNKNOWN,
            confidence_label=company.classification_confidence,
            source_count=1,
            observed_at=_aware(getattr(company, "updated_at", None)),
        )

    def _presence_ref(
        self,
        company: Company,
        row: CompanyRegionPresence,
        freshness: CareerAgentFreshness,
    ) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"presence:{row.presence_id}",
            evidence_type=CareerAgentEvidenceType.PRESENCE,
            entity_type="company_region_presence",
            entity_id=row.presence_id,
            label=f"{company.company_name} presence in {row.region_id}",
            summary=(
                f"Stored presence status {row.presence_status} with confidence "
                f"{_display(row.presence_confidence)}."
            ),
            data_basis="company_region_presence",
            freshness_status=freshness.freshness_status,
            confidence_label=row.presence_confidence,
            source_count=_source_count(row),
            observed_at=_aware(getattr(row, "updated_at", None)),
        )

    def _hiring_ref(
        self,
        company: Company,
        row: CompanyRegionHiring,
        freshness: CareerAgentFreshness,
    ) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"hiring:{row.hiring_id}",
            evidence_type=CareerAgentEvidenceType.HIRING,
            entity_type="company_region_hiring",
            entity_id=row.hiring_id,
            label=f"{company.company_name} hiring in {row.region_id}",
            summary=(
                f"Stored hiring row reports currently_hiring={row.currently_hiring_flag} "
                f"and active postings {_display(row.active_posting_count_now)}."
            ),
            data_basis="company_region_hiring",
            freshness_status=freshness.freshness_status,
            confidence_label=row.hiring_confidence,
            source_count=_source_count(row),
            observed_at=_aware(getattr(row, "updated_at", None)),
        )

    def _entry_level_ref(
        self,
        company: Company,
        row: CompanyRegionEntryLevel,
        freshness: CareerAgentFreshness,
    ) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"entry_level:{row.entry_level_id}",
            evidence_type=CareerAgentEvidenceType.ENTRY_LEVEL,
            entity_type="company_region_entry_level",
            entity_id=row.entry_level_id,
            label=f"{company.company_name} early-career access in {row.region_id}",
            summary=(
                "Stored entry-level row with internships "
                f"{_display(row.internship_count)}, co-ops {_display(row.coop_count)}, "
                f"and access score {_score_label(row.entry_level_access_score)}."
            ),
            data_basis="company_region_entry_level",
            freshness_status=freshness.freshness_status,
            confidence_label=row.entry_level_confidence,
            source_count=_source_count(row),
            observed_at=_aware(getattr(row, "updated_at", None)),
        )

    def _opportunity_ref(self, opportunity: OpportunityPayload) -> CareerAgentEvidenceRef:
        return CareerAgentEvidenceRef(
            ref_id=f"opportunity:{opportunity.id}",
            evidence_type=CareerAgentEvidenceType.OPPORTUNITY,
            entity_type="opportunity",
            entity_id=opportunity.id,
            label=f"{opportunity.employer_name}: {opportunity.program_name}",
            summary=(
                f"Stored active {opportunity.trust_label.value} opportunity record "
                f"for {opportunity.program_type.value}."
            ),
            data_basis="opportunity_records",
            freshness_status=(
                CareerAgentFreshnessStatus.FRESH
                if opportunity.expiration_state.value == "active"
                else CareerAgentFreshnessStatus.STALE
            ),
            confidence_label=opportunity.trust_label.value,
            source_count=max(1, len(opportunity.sources)),
            observed_at=_aware(opportunity.updated_at),
            public_url=opportunity.source_url,
        )


def _monthly_copy(
    recommendation: CareerAgentRecommendation,
    *,
    recommendation_type: str,
    title: str,
    action: str,
) -> CareerAgentRecommendation:
    return recommendation.model_copy(
        update={
            "recommendation_id": _stable_id(
                "career_rec",
                recommendation_type,
                recommendation.recommendation_id,
            ),
            "recommendation_type": recommendation_type,
            "target_type": CareerAgentTargetType.MONTHLY_ACTION,
            "title": title,
            "action": action,
        }
    )


def _forecast_evidence_ref(forecast: PredictiveReportForecast) -> _ForecastEvidence:
    freshness_status = _forecast_freshness_status(forecast)
    latest_observed = forecast.historical_depth.latest_observed_at
    ref = CareerAgentEvidenceRef(
        ref_id=f"forecast:{forecast.forecast_id}",
        evidence_type=CareerAgentEvidenceType.FORECAST,
        entity_type=forecast.affected_entity.entity_type.value,
        entity_id=forecast.affected_entity.entity_id,
        label=forecast.forecast_label,
        summary=forecast.safe_display_summary,
        data_basis=forecast.source_basis.data_basis,
        freshness_status=freshness_status,
        confidence_label=forecast.confidence.level.value,
        source_count=forecast.source_basis.source_count,
        observed_at=latest_observed,
    )
    return _ForecastEvidence(
        ref=ref,
        confidence=forecast.confidence.level,
        confidence_score=forecast.confidence.score,
        uncertainty_level=forecast.uncertainty.level,
        limitations=(
            *forecast.uncertainty.limitations,
            *forecast.uncertainty.known_uncertainties,
            FORECAST_WARNING,
        ),
    )


def _forecast_freshness_status(
    forecast: PredictiveReportForecast,
) -> CareerAgentFreshnessStatus:
    states = {state.casefold() for state in forecast.source_basis.freshness_states}
    if "stale" in states:
        return CareerAgentFreshnessStatus.STALE
    if "fresh" in states:
        return CareerAgentFreshnessStatus.FRESH
    if states:
        return CareerAgentFreshnessStatus.PARTIAL
    return CareerAgentFreshnessStatus.UNKNOWN


def _preference_snapshot(
    request: CareerAgentRequest,
) -> CareerAgentPreferenceSnapshot | None:
    snapshot = request.preference_snapshot
    if snapshot is None:
        if not (
            request.preferred_program_types
            or request.preferred_location_modes
        ):
            return None
        return CareerAgentPreferenceSnapshot(
            preferred_role_families=request.target_role_families,
            preferred_location_modes=request.preferred_location_modes,
            preferred_program_types=request.preferred_program_types,
        )
    return CareerAgentPreferenceSnapshot(
        preferred_region_ids=snapshot.preferred_region_ids,
        preferred_company_ids=snapshot.preferred_company_ids,
        preferred_role_families=tuple(
            dict.fromkeys((*snapshot.preferred_role_families, *request.target_role_families))
        ),
        preferred_location_modes=tuple(
            dict.fromkeys((*snapshot.preferred_location_modes, *request.preferred_location_modes))
        ),
        preferred_program_types=tuple(
            dict.fromkeys((*snapshot.preferred_program_types, *request.preferred_program_types))
        ),
        constraints=snapshot.constraints,
        preference_context=snapshot.preference_context,
    )


def _preference_boost(
    *,
    target_id: str,
    region_ids: Iterable[str],
    role_families: Iterable[str],
    preferences: CareerAgentPreferenceSnapshot | None,
) -> float:
    if preferences is None:
        return 0.0
    boost = 0.0
    if target_id in preferences.preferred_company_ids:
        boost += 0.06
    if target_id in preferences.preferred_region_ids:
        boost += 0.06
    if set(region_ids) & set(preferences.preferred_region_ids):
        boost += 0.04
    if set(role_families) & set(preferences.preferred_role_families):
        boost += 0.03
    return boost


def _preference_alignment(
    *,
    target_id: str,
    region_ids: Iterable[str],
    role_families: Iterable[str],
    preferences: CareerAgentPreferenceSnapshot | None,
) -> tuple[str, ...]:
    if preferences is None:
        return ()
    messages: list[str] = []
    if target_id in preferences.preferred_region_ids:
        messages.append("Matches a preferred region.")
    if target_id in preferences.preferred_company_ids:
        messages.append("Matches a preferred company.")
    if set(region_ids) & set(preferences.preferred_region_ids):
        messages.append("Includes one of the preferred regions.")
    if set(role_families) & set(preferences.preferred_role_families):
        messages.append("Matches a preferred role family.")
    if preferences.constraints:
        messages.append("User constraints are caveats, not source evidence.")
    return tuple(dict.fromkeys(messages))


def _region_base_score(
    score: RegionMarketScore | None,
    hiring_rows: tuple[CompanyRegionHiring, ...],
    entry_rows: tuple[CompanyRegionEntryLevel, ...],
) -> float:
    if score is None:
        return 0.35 + min(0.2, 0.02 * (len(hiring_rows) + len(entry_rows)))
    values = [
        _score_value(score.objective_opportunity_score, fallback=None),
        _score_value(score.early_career_accessibility_score, fallback=None),
        _score_value(score.live_market_score, fallback=None),
    ]
    present = [value for value in values if value is not None]
    if not present:
        return 0.45
    return _bounded(sum(present) / len(present))


def _company_base_score(
    company: Company,
    presence_rows: tuple[CompanyRegionPresence, ...],
    hiring_rows: tuple[CompanyRegionHiring, ...],
    entry_rows: tuple[CompanyRegionEntryLevel, ...],
) -> float:
    score = 0.25
    if company.eligibility_status == "eligible":
        score += 0.08
    if company.is_major_tech:
        score += 0.05
    if company.prestige_score is not None:
        score += min(0.1, _score_value(company.prestige_score, fallback=0.0) * 0.1)
    if any(row.presence_status == "present" for row in presence_rows):
        score += 0.14
    if any(row.currently_hiring_flag for row in hiring_rows):
        score += 0.17
    active_postings = sum(row.active_posting_count_now or 0 for row in hiring_rows)
    score += min(0.12, active_postings / 100)
    entry_scores = [
        _score_value(row.entry_level_access_score, fallback=None)
        for row in entry_rows
        if row.entry_level_access_score is not None
    ]
    if entry_scores:
        score += min(0.17, (sum(entry_scores) / len(entry_scores)) * 0.17)
    return _bounded(score)


def _region_summary(context: _RegionContext) -> str:
    if context.score is None:
        return (
            f"{context.region.display_name} has canonical region metadata but no stored "
            "region score, so fit is conservative."
        )
    return (
        f"{context.region.display_name} is supported by stored objective opportunity "
        f"{_score_label(context.score.objective_opportunity_score)} and early-career "
        f"access {_score_label(context.score.early_career_accessibility_score)}."
    )


def _company_summary(context: _CompanyContext) -> str:
    hiring_count = sum(row.active_posting_count_now or 0 for row in context.hiring_rows)
    entry_count = sum(row.internship_count or 0 for row in context.entry_rows)
    return (
        f"{context.company.company_name} is grounded by company metadata, "
        f"{len(context.presence_rows)} presence row(s), {len(context.hiring_rows)} "
        f"hiring row(s), {hiring_count} active posting count signals, and "
        f"{entry_count} internship count signals."
    )


def _opportunity_region_ids(opportunity: OpportunityPayload) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            binding.region_id or binding.region_label
            for binding in opportunity.region_bindings
            if binding.region_id or binding.region_label
        )
    )


def _company_role_families(rows: tuple[CompanyRegionHiring, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for row in rows:
        if not isinstance(row.role_family_summary, dict):
            continue
        for key, value in row.role_family_summary.items():
            if isinstance(key, str) and isinstance(value, int) and value > 0:
                values.append(key)
    return tuple(sorted(dict.fromkeys(values)))


def _opportunity_warnings(opportunity: OpportunityPayload) -> tuple[str, ...]:
    warnings: list[str] = []
    if opportunity.partner_submitted:
        warnings.append("Partner-submitted opportunity remains labeled as such.")
    if opportunity.paid_partner:
        warnings.append("Paid partner status is disclosed and does not boost ranking.")
    if opportunity.application_deadline is None and opportunity.expires_at is None:
        warnings.append("No application deadline or expiry timestamp is stored.")
    return tuple(warnings)


def _context_limitations(
    freshness: CareerAgentFreshness,
    confidence: Confidence,
) -> tuple[str, ...]:
    limitations: list[str] = []
    if freshness.freshness_status in {
        CareerAgentFreshnessStatus.STALE,
        CareerAgentFreshnessStatus.UNKNOWN,
        CareerAgentFreshnessStatus.PARTIAL,
    }:
        limitations.append(
            f"Freshness is {freshness.freshness_status.value}; verify before acting."
        )
    if confidence in {Confidence.LOW, Confidence.UNKNOWN}:
        limitations.append(
            f"Confidence is {confidence.value}; treat this as a weak signal."
        )
    return tuple(limitations)


def _forecast_limitations(
    forecast_evidence: Sequence[_ForecastEvidence],
) -> tuple[str, ...]:
    if not forecast_evidence:
        return ()
    limitations: list[str] = [FORECAST_WARNING]
    for evidence in forecast_evidence:
        limitations.extend(evidence.limitations)
    return tuple(dict.fromkeys(limitations))


def _uncertainty_from_evidence(
    refs: Sequence[CareerAgentEvidenceRef],
    *,
    base_confidence: Confidence,
    forecast_evidence: Sequence[_ForecastEvidence],
) -> CareerAgentUncertainty:
    confidence = base_confidence
    confidence_score: float | None = None
    limitations: list[str] = []
    reasons = [f"Uses {len(refs)} structured evidence reference(s)."]
    if forecast_evidence:
        weakest = min(
            (_confidence_rank(item.confidence), item.confidence)
            for item in forecast_evidence
        )[1]
        confidence = _min_confidence(confidence, weakest)
        scores = [
            item.confidence_score
            for item in forecast_evidence
            if item.confidence_score is not None
        ]
        confidence_score = min(scores) if scores else None
        limitations.extend(_forecast_limitations(forecast_evidence))
    else:
        confidence_score = _confidence_score(confidence)

    freshness_states = {ref.freshness_status for ref in refs}
    if CareerAgentFreshnessStatus.STALE in freshness_states:
        confidence = _min_confidence(confidence, Confidence.LOW)
        limitations.append("One or more evidence references are stale.")
    if CareerAgentFreshnessStatus.UNKNOWN in freshness_states:
        confidence = _min_confidence(confidence, Confidence.MEDIUM)
        limitations.append("One or more evidence references have unknown freshness.")

    return CareerAgentUncertainty(
        confidence_level=confidence,
        confidence_score=confidence_score,
        uncertainty_level=_uncertainty_level(confidence, freshness_states),
        reasons=tuple(dict.fromkeys(reasons)),
        limitations=tuple(dict.fromkeys(limitations)),
        forecast_based=bool(forecast_evidence),
        bounded=True,
    )


def _forecast_from_refs(
    refs: Sequence[CareerAgentEvidenceRef],
    forecasts_by_region: dict[str, tuple[_ForecastEvidence, ...]],
) -> tuple[_ForecastEvidence, ...]:
    forecast_ref_ids = {
        ref.ref_id
        for ref in refs
        if ref.evidence_type is CareerAgentEvidenceType.FORECAST
    }
    if not forecast_ref_ids:
        return ()
    found = []
    for forecasts in forecasts_by_region.values():
        for forecast in forecasts:
            if forecast.ref.ref_id in forecast_ref_ids:
                found.append(forecast)
    return tuple(found)


def _freshness_for_rows(
    rows: Iterable[object],
    *,
    data_basis: str,
    now: datetime,
) -> CareerAgentFreshness:
    row_tuple = tuple(row for row in rows if row is not None)
    expires_values = [
        _aware(getattr(row, "freshness_expires_at", None))
        for row in row_tuple
        if getattr(row, "freshness_expires_at", None) is not None
    ]
    updated_values = [
        _aware(getattr(row, "updated_at", None))
        for row in row_tuple
        if getattr(row, "updated_at", None) is not None
    ]
    source_count = sum(max(1, _source_count(row)) for row in row_tuple)
    warnings: list[str] = []
    if not row_tuple:
        status = CareerAgentFreshnessStatus.UNKNOWN
        warnings.append("No structured rows were available for freshness evaluation.")
    elif not expires_values:
        status = CareerAgentFreshnessStatus.UNKNOWN
        warnings.append("Freshness expiry is unknown for available evidence.")
    else:
        evaluated = [evaluate_freshness(value, now=now) for value in expires_values if value]
        if any(value is FreshnessStatus.STALE for value in evaluated):
            status = CareerAgentFreshnessStatus.STALE
            warnings.append("At least one evidence row is stale.")
        elif len(evaluated) < len(row_tuple):
            status = CareerAgentFreshnessStatus.PARTIAL
            warnings.append("Freshness coverage is partial.")
        else:
            status = CareerAgentFreshnessStatus.FRESH
    return CareerAgentFreshness(
        freshness_status=status,
        data_basis=data_basis,
        last_updated_at=max(updated_values) if updated_values else None,
        freshness_expires_at=min(expires_values) if expires_values else None,
        source_count=source_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _aggregate_freshness(
    freshness_rows: Sequence[CareerAgentFreshness],
    *,
    fallback_source_count: int = 0,
) -> CareerAgentFreshness:
    rows = tuple(freshness_rows)
    if not rows:
        return CareerAgentFreshness(
            freshness_status=CareerAgentFreshnessStatus.UNKNOWN,
            data_basis="unknown",
            source_count=fallback_source_count,
            warnings=("No source freshness metadata was available.",),
        )
    statuses = {row.freshness_status for row in rows}
    if CareerAgentFreshnessStatus.STALE in statuses:
        status = CareerAgentFreshnessStatus.STALE
    elif len(statuses) > 1 or CareerAgentFreshnessStatus.UNKNOWN in statuses:
        status = CareerAgentFreshnessStatus.PARTIAL
    else:
        status = next(iter(statuses))
    updated = [row.last_updated_at for row in rows if row.last_updated_at is not None]
    expires = [
        _freshness_expiry_datetime(row.freshness_expires_at)
        for row in rows
        if row.freshness_expires_at is not None
    ]
    warnings = tuple(dict.fromkeys(w for row in rows for w in row.warnings))
    return CareerAgentFreshness(
        freshness_status=status,
        data_basis="mixed_structured_platform_data",
        last_updated_at=max(updated) if updated else None,
        freshness_expires_at=min(expires) if expires else None,
        source_count=sum(row.source_count for row in rows) or fallback_source_count,
        warnings=warnings,
    )


def _freshness_from_ref(ref: CareerAgentEvidenceRef) -> CareerAgentFreshness:
    observed = ref.observed_at
    return CareerAgentFreshness(
        freshness_status=ref.freshness_status,
        data_basis=ref.data_basis,
        last_updated_at=_freshness_expiry_datetime(observed) if observed is not None else None,
        source_count=ref.source_count,
        warnings=(
            (f"Evidence freshness is {ref.freshness_status.value}.",)
            if ref.freshness_status
            in {
                CareerAgentFreshnessStatus.STALE,
                CareerAgentFreshnessStatus.UNKNOWN,
                CareerAgentFreshnessStatus.PARTIAL,
            }
            else ()
        ),
    )


def _aggregate_uncertainty(
    rows: Sequence[CareerAgentUncertainty],
) -> CareerAgentUncertainty:
    if not rows:
        return CareerAgentUncertainty(
            confidence_level=Confidence.UNKNOWN,
            uncertainty_level="high",
            reasons=("No grounded recommendations were produced.",),
            limitations=("Structured evidence was unavailable or insufficient.",),
        )
    confidence = min((row.confidence_level for row in rows), key=_confidence_rank)
    forecast_based = any(row.forecast_based for row in rows)
    scores = [row.confidence_score for row in rows if row.confidence_score is not None]
    return CareerAgentUncertainty(
        confidence_level=confidence,
        confidence_score=min(scores) if scores else _confidence_score(confidence),
        uncertainty_level=max(
            (row.uncertainty_level for row in rows),
            key={"low": 0, "medium": 1, "high": 2}.get,
        ),
        reasons=tuple(dict.fromkeys(reason for row in rows for reason in row.reasons)),
        limitations=tuple(
            dict.fromkeys(limit for row in rows for limit in row.limitations)
        ),
        forecast_based=forecast_based,
        bounded=True,
    )


def _answer_limitations(
    recommendations: tuple[CareerAgentRecommendation, ...],
    regions: tuple[_RegionContext, ...],
    companies: tuple[_CompanyContext, ...],
) -> tuple[str, ...]:
    limitations: list[str] = []
    if not recommendations:
        limitations.append(
            "No recommendation was returned because structured evidence was unavailable."
        )
    if not regions:
        limitations.append("No canonical region records matched the request.")
    if not companies:
        limitations.append("No canonical company records matched the request.")
    if any(
        rec.uncertainty.confidence_level in {Confidence.LOW, Confidence.UNKNOWN}
        for rec in recommendations
    ):
        limitations.append("Some recommendations are low or unknown confidence.")
    if any(
        rec.freshness.freshness_status is not CareerAgentFreshnessStatus.FRESH
        for rec in recommendations
    ):
        limitations.append("Some evidence is stale, partial, or has unknown freshness.")
    if any(rec.uncertainty.forecast_based for rec in recommendations):
        limitations.append(FORECAST_WARNING)
    return tuple(dict.fromkeys(limitations))


def _canonical_requested_regions(
    session: Session,
    region_refs: tuple[str, ...],
) -> tuple[str, ...]:
    resolver = GeographicResolver(RegionRepository(session))
    resolved: list[str] = []
    for region_ref in region_refs:
        resolution = resolver.resolve(region_ref)
        if resolution.resolved and resolution.region_id is not None:
            resolved.append(resolution.region_id)
    return tuple(dict.fromkeys(resolved))


def _authority_confidence(value: str) -> Confidence:
    return {
        "high": Confidence.HIGH,
        "medium": Confidence.MEDIUM,
        "moderate": Confidence.MEDIUM,
        "limited": Confidence.LOW,
        "low": Confidence.LOW,
    }.get(value.casefold(), Confidence.UNKNOWN)


def _provenance_source_count(provenance: dict) -> int:
    value = provenance.get("source_count", 1)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _authority_freshness(
    value: str,
    *,
    data_basis: str,
    observed_at: datetime | None = None,
) -> CareerAgentFreshness:
    status = {
        "fresh": CareerAgentFreshnessStatus.FRESH,
        "current": CareerAgentFreshnessStatus.FRESH,
        "stale": CareerAgentFreshnessStatus.STALE,
        "partial": CareerAgentFreshnessStatus.PARTIAL,
    }.get(value.casefold(), CareerAgentFreshnessStatus.UNKNOWN)
    return CareerAgentFreshness(
        freshness_status=status,
        data_basis=data_basis,
        last_updated_at=_aware(observed_at),
        source_count=1,
    )


def _authoritative_answer(
    request: CareerAgentRequest,
    *,
    generated_at: datetime,
    recommendations: tuple[CareerAgentRecommendation, ...],
    authority: str,
    limitations: tuple[str, ...],
) -> CareerAgentAnswer:
    fallback_freshness = CareerAgentFreshness(
        freshness_status=CareerAgentFreshnessStatus.UNKNOWN,
        data_basis="authoritative_coverage_state",
        source_count=0,
    )
    source_freshness = tuple(rec.freshness for rec in recommendations) or (
        fallback_freshness,
    )
    freshness = _aggregate_freshness(
        source_freshness,
        fallback_source_count=sum(item.source_count for item in source_freshness),
    )
    confidence = (
        min(
            (rec.uncertainty.confidence_level for rec in recommendations),
            key=_confidence_rank,
        )
        if recommendations
        else Confidence.UNKNOWN
    )
    uncertainty = CareerAgentUncertainty(
        confidence_level=confidence,
        confidence_score=_confidence_score(confidence),
        uncertainty_level=_uncertainty_level(
            confidence,
            {item.freshness_status for item in source_freshness},
        ),
        reasons=(f"Career Agent orchestrated the {authority} authority.",),
        limitations=limitations,
    )
    answer = CareerAgentAnswer(
        answer_id=_stable_id(
            "career_answer",
            request.question_type.value,
            authority,
            generated_at.isoformat(),
        ),
        question_type=request.question_type,
        generated_at=generated_at,
        summary=(
            f"{authority} supplied {len(recommendations)} grounded result(s)."
            if recommendations
            else f"{authority} supplied no eligible result; coverage limits are disclosed."
        ),
        recommendations=recommendations,
        freshness=freshness,
        source_freshness=source_freshness,
        uncertainty=uncertainty,
        preference_snapshot=_preference_snapshot(request),
        guardrails=CareerAgentGuardrailStatus(
            passed=True,
            evidence_requirement_met=bool(recommendations),
            warnings=limitations,
        ),
        limitations=limitations,
    )
    validate_career_agent_answer(answer)
    return answer


def _answer_summary(
    question_type: CareerAgentQuestionType,
    recommendations: tuple[CareerAgentRecommendation, ...],
    limitations: tuple[str, ...],
) -> str:
    if not recommendations:
        return (
            "I cannot make a grounded career-agent recommendation from the "
            "available structured platform evidence."
        )
    return (
        f"Grounded answer for {question_type.value}: {len(recommendations)} "
        "recommendation(s) are supported by structured platform evidence"
        f"{' with limitations disclosed' if limitations else ''}."
    )


def _ranked(
    recommendations: Sequence[CareerAgentRecommendation],
    *,
    limit: int,
) -> tuple[CareerAgentRecommendation, ...]:
    ordered = sorted(
        recommendations,
        key=lambda rec: (-(rec.score or 0.0), rec.title, rec.recommendation_id),
    )[:limit]
    return tuple(
        rec.model_copy(update={"rank": index})
        for index, rec in enumerate(ordered, start=1)
    )


def _dedupe_refs(
    refs: Iterable[CareerAgentEvidenceRef],
) -> tuple[CareerAgentEvidenceRef, ...]:
    deduped: dict[str, CareerAgentEvidenceRef] = {}
    for ref in refs:
        deduped.setdefault(ref.ref_id, ref)
    return tuple(deduped[key] for key in sorted(deduped))


def _source_count(row: object) -> int:
    source_refs = getattr(row, "source_refs", None)
    if isinstance(source_refs, dict):
        return 1 if source_refs else 0
    if isinstance(source_refs, list):
        return len(source_refs)
    return 0


def _confidence_from_labels(*labels: str | None) -> Confidence:
    cleaned = [label.casefold() for label in labels if label]
    if not cleaned:
        return Confidence.UNKNOWN
    if any("low" in label or "unknown" in label for label in cleaned):
        return Confidence.LOW
    if any("moderate" in label or "medium" in label or "override" in label for label in cleaned):
        return Confidence.MEDIUM
    return Confidence.HIGH


def _min_confidence(left: Confidence, right: Confidence) -> Confidence:
    return left if _confidence_rank(left) <= _confidence_rank(right) else right


def _confidence_rank(confidence: Confidence) -> int:
    return {
        Confidence.UNKNOWN: 0,
        Confidence.LOW: 1,
        Confidence.MEDIUM: 2,
        Confidence.HIGH: 3,
    }[confidence]


def _confidence_score(confidence: Confidence) -> float:
    return {
        Confidence.HIGH: 0.86,
        Confidence.MEDIUM: 0.68,
        Confidence.LOW: 0.42,
        Confidence.UNKNOWN: 0.25,
    }[confidence]


def _uncertainty_level(
    confidence: Confidence,
    freshness_states: set[CareerAgentFreshnessStatus],
) -> Literal["low", "medium", "high"]:
    if confidence in {Confidence.LOW, Confidence.UNKNOWN}:
        return "high"
    if freshness_states & {
        CareerAgentFreshnessStatus.STALE,
        CareerAgentFreshnessStatus.UNKNOWN,
        CareerAgentFreshnessStatus.PARTIAL,
    }:
        return "medium"
    return "low"


def _score_value(value: float | None, *, fallback: float | None) -> float | None:
    if value is None:
        return fallback
    normalized = value / 100 if value > 1 else value
    return _bounded(normalized)


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _score_label(value: float | None) -> str:
    normalized = _score_value(value, fallback=None)
    if normalized is None:
        return "unknown"
    return f"{round(normalized * 100)}%"


def _display(value: object) -> str:
    if value is None:
        return "unknown"
    return str(value).replace("_", " ")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _freshness_expiry_datetime(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _aware(value)
    return datetime.combine(value, time.max, tzinfo=UTC)


def _stable_id(prefix: str, *parts: str) -> str:
    stable = uuid5(NAMESPACE_URL, ":".join((prefix, *parts)))
    return f"{prefix}_{stable.hex[:16]}"
