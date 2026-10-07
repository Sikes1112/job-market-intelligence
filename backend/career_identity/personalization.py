"""Career Identity adapter for personalized discovery.

The existing personalization engine accepts an in-memory ``UserPreferences``
payload. Layer 35 makes Career Identity authoritative for the authenticated
user-facing career facts, so this adapter converts the canonical identity into
that existing payload shape without making the recommendation engine own user
profile state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import CareerFactType
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.personalization.payloads import UserPreferences


@dataclass(frozen=True, slots=True)
class CareerIdentityPersonalizationResult:
    preferences: UserPreferences
    metadata: dict[str, object] = field(default_factory=dict)


def build_personalization_from_career_identity(
    *,
    current_user_id: str,
    base_preferences: UserPreferences,
    career_identity_repo: CareerIdentityRepository,
    region_repo: RegionRepository,
) -> CareerIdentityPersonalizationResult:
    """Overlay canonical Career Identity onto existing personalization input.

    Career Identity wins for overlapping Layer-35 preference semantics when the
    user has granted downstream personalization consent. If the user has no
    identity or has not granted consent, the existing request-scoped payload is
    preserved so legacy callers and anonymous discovery behavior keep working.
    """

    identity = career_identity_repo.get_identity_for_user(current_user_id)
    if identity is None:
        return CareerIdentityPersonalizationResult(
            preferences=base_preferences,
            metadata={"source": "request", "career_identity_applied": False},
        )

    if not identity.downstream_personalization_consent_granted:
        return CareerIdentityPersonalizationResult(
            preferences=base_preferences,
            metadata={
                "source": "request",
                "career_identity_applied": False,
                "career_identity_version": identity.current_version,
                "reason": "downstream_personalization_consent_not_granted",
            },
        )

    facts = career_identity_repo.list_facts(identity.career_identity_id)
    role_targets, excluded_roles = _role_targets(facts)
    industries, excluded_industries = _industry_preferences(facts)
    region_ids, excluded_regions, geographic_resolutions = _region_ids(
        identity, facts, base_preferences, region_repo
    )

    effective_role_targets = role_targets or list(base_preferences.role_targets)
    effective_industries = industries or list(base_preferences.industry_preferences)
    if excluded_roles:
        excluded_role_set = {_normalize_token(item) for item in excluded_roles}
        effective_role_targets = [
            item
            for item in effective_role_targets
            if _normalize_token(item) not in excluded_role_set
        ]
    if excluded_industries:
        excluded_industry_set = {_normalize_token(item) for item in excluded_industries}
        effective_industries = [
            item
            for item in effective_industries
            if _normalize_token(item) not in excluded_industry_set
        ]

    preferences = base_preferences.model_copy(
        update={
            "role_targets": _unique(effective_role_targets),
            "industry_preferences": _unique(effective_industries),
            "region_ids": _unique(region_ids),
        }
    )
    return CareerIdentityPersonalizationResult(
        preferences=preferences,
        metadata={
            "source": "career_identity",
            "career_identity_applied": True,
            "career_identity_version": identity.current_version,
            "role_targets": preferences.role_targets,
            "industry_preferences": preferences.industry_preferences,
            "region_ids": preferences.region_ids,
            "excluded_roles": _unique(excluded_roles),
            "excluded_industries": _unique(excluded_industries),
            "excluded_region_ids": _unique(excluded_regions),
            "geographic_resolutions": geographic_resolutions,
            "skills_count": _fact_count(facts, CareerFactType.SKILL),
            "experience_count": _fact_count(facts, CareerFactType.EXPERIENCE),
        },
    )


def _role_targets(facts: list[CareerIdentityFact]) -> tuple[list[str], list[str]]:
    preferred: list[str] = []
    excluded: list[str] = []
    for fact in facts:
        if fact.fact_type != CareerFactType.ROLE_PREFERENCE.value:
            continue
        payload = fact.payload or {}
        targets = [
            _role_token(payload.get("function")),
            _role_token(payload.get("role_title")),
            _role_token(payload.get("employment_type")),
        ]
        bucket = excluded if payload.get("preference_kind") == "excluded" else preferred
        bucket.extend(item for item in targets if item)
    return _unique(preferred), _unique(excluded)


def _industry_preferences(facts: list[CareerIdentityFact]) -> tuple[list[str], list[str]]:
    preferred: list[str] = []
    excluded: list[str] = []
    for fact in facts:
        if fact.fact_type != CareerFactType.INDUSTRY_PREFERENCE.value:
            continue
        payload = fact.payload or {}
        industry = _normalize_token(payload.get("industry"))
        if not industry:
            continue
        if payload.get("preference_kind") == "excluded":
            excluded.append(industry)
        elif payload.get("preference_kind") == "preferred":
            preferred.append(industry)
    return _unique(preferred), _unique(excluded)


def _region_ids(
    identity: CareerIdentity,
    facts: list[CareerIdentityFact],
    base_preferences: UserPreferences,
    region_repo: RegionRepository,
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    preferred: list[str] = []
    excluded: list[str] = []
    resolutions: list[dict[str, object]] = []
    resolver = GeographicResolver(region_repo)
    for fact in facts:
        if fact.fact_type != CareerFactType.GEOGRAPHIC_CONSTRAINT.value:
            continue
        payload = fact.payload or {}
        raw_location = payload.get("location")
        resolution = resolver.resolve(raw_location)
        resolutions.append(
            {
                "fact_id": fact.career_identity_fact_id,
                "raw_location": raw_location,
                "status": resolution.status,
                "region_id": resolution.region_id,
                "public_slug": resolution.public_slug,
                "resolution_source": resolution.resolution_source,
                "market_support_status": resolution.market_support_status,
                "candidate_region_ids": list(resolution.candidate_region_ids),
            }
        )
        if not resolution.resolved or resolution.region_id is None:
            continue
        region_id = resolution.region_id
        if payload.get("constraint_kind") == "excluded":
            excluded.append(region_id)
        elif payload.get("constraint_kind") in {"target", "acceptable"}:
            preferred.append(region_id)

    candidates = preferred or list(base_preferences.region_ids)
    excluded_set = set(excluded)
    filtered = [region_id for region_id in candidates if region_id not in excluded_set]
    if not filtered:
        filtered = list(base_preferences.region_ids)
    return filtered, excluded, resolutions


def _role_token(value: object) -> str | None:
    token = _normalize_token(value)
    if not token:
        return None
    return token.replace(" ", "_")


def _normalize_token(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().replace("-", " ").split())


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _fact_count(facts: list[CareerIdentityFact], fact_type: CareerFactType) -> int:
    return sum(1 for fact in facts if fact.fact_type == fact_type.value)
