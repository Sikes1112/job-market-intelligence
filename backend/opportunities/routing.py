"""Route-first opportunity guidance for Layer 23C."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.matching import (
    OpportunityMatchResult,
    match_opportunity_to_route,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.route_schemas import (
    MatchedOpportunity,
    OpportunityRoute,
    OpportunityRouteConfidence,
    OpportunityRouteRequest,
    OpportunityRouteResponse,
    OpportunityRouteSourceSummary,
)
from backend.opportunities.schemas import OpportunityPayload
from backend.opportunities.service import OpportunityService
from backend.scoring.models import RegionMarketScore

MAX_CANDIDATE_OPPORTUNITIES = 1_000
MAX_MATCHED_OPPORTUNITIES_PER_ROUTE = 5


@dataclass(frozen=True, slots=True)
class _RegionIntelligence:
    requested_region: str
    display_region: str
    resolved_region_id: str | None
    market_fit_score: float
    region_fit_score: float
    source_count: int
    source_categories: tuple[str, ...]
    warnings: tuple[str, ...]


class OpportunityRouteService:
    """Generate route-first opportunity recommendations without score mutation."""

    def __init__(self, repository: OpportunityRepository) -> None:
        self._repo = repository
        self._opportunity_service = OpportunityService(repository)

    def generate_routes(
        self,
        request: OpportunityRouteRequest,
        *,
        now: datetime | None = None,
    ) -> OpportunityRouteResponse:
        now = now or datetime.now(UTC)
        opportunities = self._opportunity_service.list_opportunities(
            active=True,
            now=now,
            limit=MAX_CANDIDATE_OPPORTUNITIES,
        ).opportunities

        company_cache: dict[str, Company | None] = {}
        routes: list[OpportunityRoute] = []
        for target_region in request.target_regions:
            region_intelligence = self._region_intelligence(target_region)
            for target_role_family in request.target_role_families:
                matches = self._matches_for_route(
                    opportunities,
                    request=request,
                    target_region=target_region,
                    target_role_family=target_role_family,
                )
                route = self._route(
                    request=request,
                    region_intelligence=region_intelligence,
                    target_role_family=target_role_family,
                    matches=matches,
                    company_cache=company_cache,
                )
                routes.append(route)

        ranked_routes = sorted(
            routes,
            key=lambda route: (
                -route.overall_route_fit_score,
                route.target_region,
                route.target_role_family,
            ),
        )[: request.limit]
        return OpportunityRouteResponse(
            routes=tuple(ranked_routes),
            route_count=len(ranked_routes),
            route_generation_note=(
                "Routes are grouped strategic recommendations. Attached opportunities "
                "are subordinate evidence, not a flat listing feed."
            ),
            non_goal_disclosures=(
                "No scraping was performed.",
                "No application tracking, referral workflow, messaging, ATS state, "
                "or payment flow was created.",
                "Paid partner status does not boost route or opportunity fit scores.",
                "Opportunity routing does not mutate objective market, region, "
                "company, role-family, predictive, institutional, or benchmark scores.",
            ),
        )

    def _matches_for_route(
        self,
        opportunities: tuple[OpportunityPayload, ...],
        *,
        request: OpportunityRouteRequest,
        target_region: str,
        target_role_family: str,
    ) -> tuple[OpportunityMatchResult, ...]:
        matches = [
            match
            for opportunity in opportunities
            if (
                match := match_opportunity_to_route(
                    opportunity,
                    request,
                    target_region=target_region,
                    target_role_family=target_role_family,
                )
            )
            is not None
        ]
        return tuple(
            sorted(
                matches,
                key=lambda match: (
                    -match.fit_score,
                    match.opportunity.employer_name,
                    match.opportunity.program_name,
                    match.opportunity.id,
                ),
            )[:MAX_MATCHED_OPPORTUNITIES_PER_ROUTE]
        )

    def _route(
        self,
        *,
        request: OpportunityRouteRequest,
        region_intelligence: _RegionIntelligence,
        target_role_family: str,
        matches: tuple[OpportunityMatchResult, ...],
        company_cache: dict[str, Company | None],
    ) -> OpportunityRoute:
        matched_opportunities = tuple(
            self._matched_opportunity(match) for match in matches
        )
        recommended_company_types = self._recommended_company_types(
            matches,
            company_cache=company_cache,
        )
        company_type_fit_score = _company_type_fit_score(recommended_company_types, matches)
        role_family_fit_score = _role_family_fit_score(request, target_role_family)
        opportunity_fit_score = _average(match.fit_score for match in matches)
        overall_route_fit_score = _overall_route_fit_score(
            market_fit_score=region_intelligence.market_fit_score,
            region_fit_score=region_intelligence.region_fit_score,
            company_type_fit_score=company_type_fit_score,
            role_family_fit_score=role_family_fit_score,
            opportunity_fit_score=opportunity_fit_score,
        )
        warnings = _route_warnings(
            request=request,
            region_intelligence=region_intelligence,
            matches=matches,
        )
        disclosure = _partner_disclosure(matches)
        route_id = _route_id(region_intelligence.requested_region, target_role_family)
        return OpportunityRoute(
            route_id=route_id,
            route_title=(
                f"{region_intelligence.display_region} "
                f"{_display_label(target_role_family)} route"
            ),
            target_region=region_intelligence.requested_region,
            target_role_family=target_role_family,
            recommended_company_types=recommended_company_types,
            matched_opportunities=matched_opportunities,
            market_fit_score=region_intelligence.market_fit_score,
            region_fit_score=region_intelligence.region_fit_score,
            company_type_fit_score=company_type_fit_score,
            opportunity_fit_score=opportunity_fit_score,
            role_family_fit_score=role_family_fit_score,
            overall_route_fit_score=overall_route_fit_score,
            confidence=_confidence(
                region_intelligence=region_intelligence,
                matches=matches,
                include_unverified=request.include_unverified,
            ),
            explanation=_route_explanation(
                request=request,
                region_intelligence=region_intelligence,
                target_role_family=target_role_family,
                matches=matches,
            ),
            warnings=warnings,
            next_steps=_next_steps(matches=matches, constraints=request.constraints),
            source_summary=_source_summary(region_intelligence, matches),
            sponsored_or_partner_disclosure=disclosure,
        )

    def _matched_opportunity(self, match: OpportunityMatchResult) -> MatchedOpportunity:
        opportunity = match.opportunity
        region = _matched_region_label(opportunity, match.target_region)
        role_family = _matched_role_family(opportunity, match.target_role_family)
        return MatchedOpportunity(
            opportunity_id=opportunity.id,
            employer_name=opportunity.employer_name,
            program_name=opportunity.program_name,
            program_type=opportunity.program_type,
            region=region[0],
            metro=region[1],
            role_family=role_family,
            location_mode=opportunity.location_mode,
            trust_label=opportunity.trust_label,
            review_status=opportunity.review_status,
            expiration_state=opportunity.expiration_state,
            partner_submitted=opportunity.partner_submitted,
            paid_partner=opportunity.paid_partner,
            application_url=opportunity.application_url,
            source_url=opportunity.source_url,
            fit_score=match.fit_score,
            fit_explanation=match.explanation,
            warnings=match.warnings,
        )

    def _recommended_company_types(
        self,
        matches: tuple[OpportunityMatchResult, ...],
        *,
        company_cache: dict[str, Company | None],
    ) -> tuple[str, ...]:
        labels: list[str] = []
        for match in matches:
            opportunity = match.opportunity
            company = None
            if opportunity.employer_id is not None:
                if opportunity.employer_id not in company_cache:
                    company_cache[opportunity.employer_id] = self._repo.session.get(
                        Company,
                        opportunity.employer_id,
                    )
                company = company_cache[opportunity.employer_id]
            labels.append(_company_type_label(company, opportunity))
        if not labels:
            return ("source-checked early-career employers",)
        return tuple(sorted(dict.fromkeys(labels)))

    def _region_intelligence(self, requested_region: str) -> _RegionIntelligence:
        region = self._resolve_region(requested_region)
        resolved_region_id = region.region_id if region is not None else requested_region
        score = self._region_market_score(resolved_region_id)
        warnings: list[str] = []
        source_categories: list[str] = []
        source_count = 0
        if score is not None:
            market_fit = _score_value(score.objective_opportunity_score, fallback=0.55)
            region_fit = _score_value(
                score.early_career_accessibility_score,
                fallback=market_fit,
            )
            source_categories.append("region_market_scores")
            source_count += 1
        else:
            market_fit = 0.55
            region_fit = 0.55
            warnings.append(
                "No stored objective region score was found; route uses conservative "
                "default intelligence context."
            )

        return _RegionIntelligence(
            requested_region=requested_region,
            display_region=(
                region.display_name
                if region is not None
                else _display_label(requested_region)
            ),
            resolved_region_id=region.region_id if region is not None else None,
            market_fit_score=market_fit,
            region_fit_score=region_fit,
            source_count=source_count,
            source_categories=tuple(source_categories),
            warnings=tuple(warnings),
        )

    def _resolve_region(self, requested_region: str) -> Region | None:
        return self._repo.session.execute(
            select(Region)
            .where(
                (Region.region_id == requested_region)
                | (Region.region_name == requested_region)
                | (Region.display_name == requested_region)
            )
            .order_by(Region.region_id.asc())
            .limit(1)
        ).scalar_one_or_none()

    def _region_market_score(self, region_id: str) -> RegionMarketScore | None:
        return self._repo.session.execute(
            select(RegionMarketScore)
            .where(RegionMarketScore.region_id == region_id)
            .order_by(RegionMarketScore.region_score_id.asc())
            .limit(1)
        ).scalar_one_or_none()


def _matched_region_label(
    opportunity: OpportunityPayload,
    target_region: str,
) -> tuple[str, str | None]:
    target = _normalize(target_region)
    for binding in opportunity.region_bindings:
        values = (binding.region_id, binding.region_label, binding.metro_area)
        if any(_normalize(value) == target for value in values if value):
            return binding.region_label, binding.metro_area
    return opportunity.regions[0] if opportunity.regions else target_region, None


def _matched_role_family(
    opportunity: OpportunityPayload,
    target_role_family: str,
) -> str:
    target = _normalize(target_role_family)
    for binding in opportunity.role_family_bindings:
        if _normalize(binding.role_family) == target:
            return binding.role_family
    return opportunity.role_families[0] if opportunity.role_families else target_role_family


def _company_type_label(
    company: Company | None,
    opportunity: OpportunityPayload,
) -> str:
    if company is not None:
        if company.is_mag7:
            return "large platform employers"
        if company.is_major_tech:
            return "major technology employers"
        if company.sector_primary:
            return f"{_display_label(company.sector_primary)} employers"
        if company.public_or_private:
            return f"{_display_label(company.public_or_private)} employers"
    return f"{_display_label(opportunity.program_type.value)} sponsors"


def _company_type_fit_score(
    recommended_company_types: tuple[str, ...],
    matches: tuple[OpportunityMatchResult, ...],
) -> float:
    if not matches:
        return 0.55
    diversity_bonus = min(0.08, max(0, len(recommended_company_types) - 1) * 0.02)
    return round(min(0.85, 0.68 + diversity_bonus), 3)


def _role_family_fit_score(
    request: OpportunityRouteRequest,
    target_role_family: str,
) -> float:
    summary_tokens = _token_set(
        request.user_intent_summary or "",
        request.profile_summary or "",
        *request.skills,
        *request.background_tags,
    )
    target_tokens = _token_set(target_role_family)
    overlap = summary_tokens & target_tokens
    return round(min(0.95, 0.82 + len(overlap) * 0.03), 3)


def _overall_route_fit_score(
    *,
    market_fit_score: float,
    region_fit_score: float,
    company_type_fit_score: float,
    role_family_fit_score: float,
    opportunity_fit_score: float,
) -> float:
    return round(
        (market_fit_score * 0.3)
        + (region_fit_score * 0.2)
        + (company_type_fit_score * 0.15)
        + (role_family_fit_score * 0.2)
        + (opportunity_fit_score * 0.15),
        3,
    )


def _route_warnings(
    *,
    request: OpportunityRouteRequest,
    region_intelligence: _RegionIntelligence,
    matches: tuple[OpportunityMatchResult, ...],
) -> tuple[str, ...]:
    warnings = list(region_intelligence.warnings)
    if not matches:
        warnings.append(
            "No active verified or source-checked opportunity is currently attached to this route."
        )
    if request.include_unverified:
        warnings.append(
            "Unverified or partner-submitted opportunities may be included because "
            "include_unverified=true."
        )
    if any(match.opportunity.paid_partner for match in matches):
        warnings.append("Paid partner records are disclosed and receive no score boost.")
    if any(match.opportunity.partner_submitted for match in matches):
        warnings.append("Partner-submitted records remain labeled in matched programs.")
    if request.constraints:
        warnings.append(
            "User constraints are route caveats and do not override source "
            "verification or objective scores."
        )
    return tuple(dict.fromkeys(warnings))


def _partner_disclosure(matches: tuple[OpportunityMatchResult, ...]) -> str | None:
    if any(
        match.opportunity.partner_submitted or match.opportunity.paid_partner
        for match in matches
    ):
        return (
            "Some attached opportunities are partner-submitted or paid partner records. "
            "Disclosure is shown per program, and paid status does not affect scoring."
        )
    return None


def _confidence(
    *,
    region_intelligence: _RegionIntelligence,
    matches: tuple[OpportunityMatchResult, ...],
    include_unverified: bool,
) -> OpportunityRouteConfidence:
    has_market_source = region_intelligence.source_count > 0
    has_trusted_match = any(
        match.opportunity.trust_label.value in {"verified", "source_checked"}
        for match in matches
    )
    if has_market_source and has_trusted_match and not include_unverified:
        return OpportunityRouteConfidence.HIGH
    if has_market_source or has_trusted_match:
        return OpportunityRouteConfidence.MEDIUM
    return OpportunityRouteConfidence.LOW


def _route_explanation(
    *,
    request: OpportunityRouteRequest,
    region_intelligence: _RegionIntelligence,
    target_role_family: str,
    matches: tuple[OpportunityMatchResult, ...],
) -> str:
    intent = request.user_intent_summary or request.profile_summary or "the supplied profile"
    base = (
        f"This route connects {intent} to {_display_label(target_role_family)} "
        f"in {region_intelligence.display_region}. Market and region fit use stored "
        "intelligence scores as read-only context."
    )
    if matches:
        return (
            f"{base} {len(matches)} active opportunity record(s) attach as evidence "
            "after trust, expiration, region, and role-family checks."
        )
    return (
        f"{base} No active trusted opportunity is attached, so the route remains "
        "strategic guidance rather than a listing."
    )


def _next_steps(
    *,
    matches: tuple[OpportunityMatchResult, ...],
    constraints: tuple[str, ...],
) -> tuple[str, ...]:
    steps = [
        "Review the route explanation against your region, role-family, and location preferences.",
        "Compare the recommended company types with your target employer strategy.",
    ]
    if matches:
        steps.append(
            "Open matched program source pages manually and verify eligibility, "
            "deadline, and location details."
        )
    else:
        steps.append(
            "Use this route to focus market research while waiting for verified "
            "or source-checked programs to attach."
        )
    if constraints:
        steps.append("Validate personal constraints before treating any program as actionable.")
    steps.append("Do not treat paid or partner-submitted status as a quality signal.")
    return tuple(steps)


def _source_summary(
    region_intelligence: _RegionIntelligence,
    matches: tuple[OpportunityMatchResult, ...],
) -> OpportunityRouteSourceSummary:
    categories = list(region_intelligence.source_categories)
    opportunity_source_count = 0
    if matches:
        categories.extend(
            [
                "opportunity_records",
                "opportunity_sources",
                "review_derived_trust_state",
            ]
        )
        opportunity_source_count = sum(
            max(1, len(match.opportunity.sources)) for match in matches
        )
    return OpportunityRouteSourceSummary(
        data_basis="stored_market_intelligence_and_trusted_opportunity_records",
        source_categories=tuple(sorted(dict.fromkeys(categories))),
        source_count=region_intelligence.source_count + opportunity_source_count,
        notes=(
            "Objective intelligence scores are read-only context.",
            "Opportunity fit and route fit are Layer 23C outputs only.",
        ),
    )


def _score_value(value: float | None, *, fallback: float) -> float:
    if value is None:
        return fallback
    normalized = value / 100 if value > 1 else value
    return round(max(0.0, min(1.0, normalized)), 3)


def _average(values: object) -> float:
    materialized = tuple(float(value) for value in values)
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 3)


def _route_id(target_region: str, target_role_family: str) -> str:
    stable = uuid5(NAMESPACE_URL, f"opportunity-route:{target_region}:{target_role_family}")
    return f"route_{stable.hex[:16]}"


def _display_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _normalize(value: str | None) -> str:
    return " ".join(sorted(_token_set(value or "")))


def _token_set(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = value.replace("_", " ").replace("-", " ").lower()
        tokens.update(token for token in normalized.split() if token)
    return tokens
