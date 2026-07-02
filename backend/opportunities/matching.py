"""Deterministic opportunity matching helpers for Layer 23C routing."""

from __future__ import annotations

from dataclasses import dataclass
from re import split

from backend.opportunities.route_schemas import OpportunityRouteRequest
from backend.opportunities.schemas import (
    OpportunityExpirationState,
    OpportunityPayload,
    OpportunityReviewStatus,
    OpportunityTrustLabel,
)

TRUSTED_ROUTE_LABELS = frozenset(
    {
        OpportunityTrustLabel.VERIFIED,
        OpportunityTrustLabel.SOURCE_CHECKED,
    }
)
UNVERIFIED_ROUTE_LABELS = frozenset(
    {
        OpportunityTrustLabel.UNVERIFIED,
        OpportunityTrustLabel.PARTNER_SUBMITTED,
    }
)


@dataclass(frozen=True, slots=True)
class OpportunityMatchResult:
    opportunity: OpportunityPayload
    target_region: str
    target_role_family: str
    fit_score: float
    explanation: str
    warnings: tuple[str, ...]


def is_route_eligible_opportunity(
    opportunity: OpportunityPayload,
    *,
    include_unverified: bool,
    trust_preferences: tuple[OpportunityTrustLabel, ...] = (),
) -> bool:
    """Return whether an opportunity may be considered for active routing."""

    if opportunity.expiration_state == OpportunityExpirationState.EXPIRED:
        return False
    if opportunity.trust_label in {
        OpportunityTrustLabel.EXPIRED,
        OpportunityTrustLabel.REJECTED,
    }:
        return False
    if opportunity.review_status in {
        OpportunityReviewStatus.EXPIRED,
        OpportunityReviewStatus.REJECTED,
    }:
        return False

    allowed_labels = set(TRUSTED_ROUTE_LABELS)
    if include_unverified:
        allowed_labels.update(UNVERIFIED_ROUTE_LABELS)
    if trust_preferences:
        allowed_labels &= set(trust_preferences)
    return opportunity.trust_label in allowed_labels


def match_opportunity_to_route(
    opportunity: OpportunityPayload,
    request: OpportunityRouteRequest,
    *,
    target_region: str,
    target_role_family: str,
) -> OpportunityMatchResult | None:
    """Score one opportunity against one strategic route target."""

    if not is_route_eligible_opportunity(
        opportunity,
        include_unverified=request.include_unverified,
        trust_preferences=request.opportunity_trust_preferences,
    ):
        return None

    region_points = _region_match_points(opportunity, target_region)
    role_points = _role_match_points(opportunity, target_role_family)
    if region_points <= 0 or role_points <= 0:
        return None

    program_points = _program_type_points(opportunity, request)
    location_points = _location_mode_points(opportunity, request)
    seniority_points = _seniority_points(opportunity, request)
    trust_points = _trust_points(opportunity)
    background_points = _background_points(opportunity, request, target_role_family)

    score = _clamp01(
        region_points
        + role_points
        + program_points
        + location_points
        + seniority_points
        + trust_points
        + background_points
    )
    return OpportunityMatchResult(
        opportunity=opportunity,
        target_region=target_region,
        target_role_family=target_role_family,
        fit_score=round(score, 3),
        explanation=_fit_explanation(
            opportunity,
            region_points=region_points,
            role_points=role_points,
            program_points=program_points,
            location_points=location_points,
            seniority_points=seniority_points,
            trust_points=trust_points,
            background_points=background_points,
        ),
        warnings=_match_warnings(opportunity),
    )


def _region_match_points(opportunity: OpportunityPayload, target_region: str) -> float:
    target = _normalize(target_region)
    for binding in opportunity.region_bindings:
        values = (
            binding.region_id,
            binding.region_label,
            binding.metro_area,
        )
        if any(_normalize(value) == target for value in values if value):
            return 0.25
    if any(_normalize(region) == target for region in opportunity.regions):
        return 0.22
    return 0.0


def _role_match_points(opportunity: OpportunityPayload, target_role_family: str) -> float:
    target = _normalize(target_role_family)
    for binding in opportunity.role_family_bindings:
        if _normalize(binding.role_family) == target:
            return 0.2
        if binding.role_family_label and _normalize(binding.role_family_label) == target:
            return 0.18
    if any(_normalize(role_family) == target for role_family in opportunity.role_families):
        return 0.18
    return 0.0


def _program_type_points(
    opportunity: OpportunityPayload,
    request: OpportunityRouteRequest,
) -> float:
    if not request.preferred_program_types:
        return 0.05
    if opportunity.program_type in request.preferred_program_types:
        return 0.1
    return 0.0


def _location_mode_points(
    opportunity: OpportunityPayload,
    request: OpportunityRouteRequest,
) -> float:
    if not request.preferred_location_modes:
        return 0.04
    if opportunity.location_mode in request.preferred_location_modes:
        return 0.1
    if opportunity.location_mode.value == "mixed":
        return 0.06
    return 0.0


def _seniority_points(
    opportunity: OpportunityPayload,
    request: OpportunityRouteRequest,
) -> float:
    if request.experience_level.value == "unknown":
        return 0.04
    if opportunity.seniority_level == request.experience_level:
        return 0.07
    if opportunity.seniority_level.value == "unknown":
        return 0.02
    return 0.0


def _trust_points(opportunity: OpportunityPayload) -> float:
    if opportunity.trust_label == OpportunityTrustLabel.VERIFIED:
        return 0.25
    if opportunity.trust_label == OpportunityTrustLabel.SOURCE_CHECKED:
        return 0.22
    if opportunity.trust_label == OpportunityTrustLabel.PARTNER_SUBMITTED:
        return 0.12
    if opportunity.trust_label == OpportunityTrustLabel.UNVERIFIED:
        return 0.06
    return 0.0


def _background_points(
    opportunity: OpportunityPayload,
    request: OpportunityRouteRequest,
    target_role_family: str,
) -> float:
    request_tokens = _tokens(
        (
            request.user_intent_summary or "",
            request.profile_summary or "",
            target_role_family,
            *request.skills,
            *request.background_tags,
        )
    )
    if not request_tokens:
        return 0.0

    opportunity_tokens = _tokens(
        (
            opportunity.employer_name,
            opportunity.program_name,
            opportunity.eligibility_summary or "",
            *opportunity.role_families,
        )
    )
    overlap = request_tokens & opportunity_tokens
    return min(0.03, len(overlap) * 0.01)


def _fit_explanation(
    opportunity: OpportunityPayload,
    *,
    region_points: float,
    role_points: float,
    program_points: float,
    location_points: float,
    seniority_points: float,
    trust_points: float,
    background_points: float,
) -> str:
    reasons = []
    if region_points:
        reasons.append("region binding")
    if role_points:
        reasons.append("role-family binding")
    if program_points >= 0.1:
        reasons.append("preferred program type")
    if location_points >= 0.1:
        reasons.append("preferred location mode")
    if seniority_points >= 0.07:
        reasons.append("seniority match")
    if trust_points >= 0.22:
        reasons.append(f"{opportunity.trust_label.value} trust")
    elif trust_points:
        reasons.append(f"{opportunity.trust_label.value} label")
    if background_points:
        reasons.append("background tag overlap")
    return "Fit is based on " + ", ".join(reasons) + "."


def _match_warnings(opportunity: OpportunityPayload) -> tuple[str, ...]:
    warnings: list[str] = []
    if opportunity.trust_label == OpportunityTrustLabel.UNVERIFIED:
        warnings.append(
            "Unverified opportunity included only because include_unverified=true."
        )
    if opportunity.trust_label == OpportunityTrustLabel.PARTNER_SUBMITTED:
        warnings.append(
            "Partner-submitted opportunity is labeled and should be source-checked."
        )
    if opportunity.trust_label == OpportunityTrustLabel.SOURCE_CHECKED:
        warnings.append("Source-checked opportunity is not the same as employer-verified.")
    if opportunity.partner_submitted:
        warnings.append("Partner-submitted metadata is preserved in this route.")
    if opportunity.paid_partner:
        warnings.append("Paid partner relationship disclosed; paid status did not affect fit.")
    warnings.append("Manual next step only; no application tracking was created.")
    return tuple(dict.fromkeys(warnings))


def _tokens(values: tuple[str, ...]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(
            token
            for token in split(r"[^a-z0-9]+", value.lower())
            if len(token) > 1
        )
    return tokens


def _normalize(value: str | None) -> str:
    return " ".join(sorted(_tokens((value or "",))))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
