"""Career Identity to Explore Context adaptation and fingerprinting."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.career_identity.repository import CareerIdentityRepository
from backend.explore.schemas import (
    ExploreContext,
    ExploreContextItem,
    ExploreContextValues,
    ExplorePersonalizationState,
    ExploreSessionOverrides,
    GoalMappingState,
)
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.market_intelligence.schemas import CareerGoal

# v2 makes set-like context fields order- and duplicate-invariant. Keeping the
# old version label would make identical v1 payloads reproduce different hashes.
FINGERPRINT_VERSION = "explore_context_v2"

_GOAL_ALIASES: dict[CareerGoal, frozenset[str]] = {
    CareerGoal.SOFTWARE_ENGINEERING: frozenset(
        {
            "software engineering",
            "software engineer",
            "swe",
            "backend engineer",
            "frontend engineer",
        }
    ),
    CareerGoal.PRODUCT_MANAGEMENT: frozenset(
        {"product management", "product manager", "technical product manager"}
    ),
    CareerGoal.AI_ML: frozenset(
        {
            "ai",
            "ai ml",
            "ml",
            "machine learning",
            "machine learning engineer",
            "ml engineer",
            "ai engineer",
            "artificial intelligence",
        }
    ),
    CareerGoal.CYBERSECURITY: frozenset(
        {
            "cybersecurity",
            "cyber security",
            "security",
            "security engineer",
            "information security",
        }
    ),
    CareerGoal.DATA_SCIENCE: frozenset({"data science", "data scientist"}),
}


@dataclass(frozen=True, slots=True)
class GoalMapping:
    state: GoalMappingState
    goal: CareerGoal | None
    candidates: tuple[CareerGoal, ...] = ()


class ExploreContextService:
    def __init__(
        self,
        career_identity_repository: CareerIdentityRepository,
        region_repository: RegionRepository,
    ) -> None:
        self._identity_repo = career_identity_repository
        self._region_repo = region_repository

    def build(
        self,
        user_id: str,
        overrides: ExploreSessionOverrides | None = None,
    ) -> ExploreContext:
        overrides = overrides or ExploreSessionOverrides()
        identity = self._identity_repo.get_identity_for_user(user_id)
        consent = bool(identity and identity.downstream_personalization_consent_granted)
        facts = (
            self._identity_repo.list_facts(identity.career_identity_id)
            if identity is not None and consent
            else []
        )
        defaults, unsupported, default_goal_inputs = self._profile_defaults(facts)
        override_values, override_unsupported = self._override_values(overrides)
        unsupported.extend(override_unsupported)
        effective = _overlay(defaults, override_values, overrides)

        if overrides.goal is not None:
            mapping_inputs = (overrides.goal,)
        elif overrides.role_families is not None:
            mapping_inputs = effective.role_families
        else:
            mapping_inputs = tuple((*default_goal_inputs, *effective.role_families))
        mapping = map_role_or_goal(mapping_inputs)
        supported_goal = mapping.goal.value if mapping.goal else None
        if overrides.goal is not None:
            override_values = override_values.model_copy(update={"goal": supported_goal})
        elif overrides.role_families is None:
            defaults = defaults.model_copy(update={"goal": supported_goal})
        effective = effective.model_copy(update={"goal": supported_goal})
        unapplied = list(_unapplied_evidence_dimensions(effective))

        role_families_applied = (
            overrides.goal is None and mapping.goal is not None and bool(effective.role_families)
        )
        if overrides.goal is not None and effective.role_families:
            unapplied.append(
                ExploreContextItem(
                    code="role_families_overridden_by_explicit_goal",
                    field="role_families",
                    source="effective_context",
                    reason=(
                        "An explicit governed goal superseded role-family inference; "
                        "role families did not influence this Fit result."
                    ),
                )
            )
        if effective.preferred_region_ids:
            unapplied.append(
                _unapplied(
                    "preferred_geography_market_fit_unavailable",
                    "preferred_region_ids",
                    "effective_context",
                )
            )

        geographic_conflicts = tuple(
            sorted(set(effective.included_region_ids).intersection(effective.excluded_region_ids))
        )
        if geographic_conflicts:
            unsupported.append(
                ExploreContextItem(
                    code="conflicting_geographic_constraints",
                    field="geographic_scope",
                    source="effective_context",
                    reason=(
                        "The same canonical Region is both included and excluded; "
                        "the conflict requires explicit correction."
                    ),
                )
            )

        explicit_supported = mapping.goal is not None and bool(
            overrides.goal is not None or overrides.role_families is not None
        )
        if geographic_conflicts:
            state = ExplorePersonalizationState.NEEDS_INPUT
        elif mapping.state is GoalMappingState.AMBIGUOUS:
            state = ExplorePersonalizationState.NEEDS_INPUT
            unsupported.append(
                ExploreContextItem(
                    code="multiple_supported_goal_mappings",
                    field="goal",
                    source="effective_context",
                    reason="Multiple governed goals match; an explicit goal is required.",
                )
            )
        elif mapping.state is GoalMappingState.UNSUPPORTED:
            state = ExplorePersonalizationState.UNSUPPORTED
            unsupported.append(
                ExploreContextItem(
                    code="unsupported_role_or_goal",
                    field="goal",
                    source="effective_context",
                    reason="No governed Layer 34 goal maps to the supplied role context.",
                )
            )
        elif mapping.state is GoalMappingState.MISSING:
            state = (
                ExplorePersonalizationState.NEEDS_INPUT
                if identity is not None and consent
                else ExplorePersonalizationState.GENERAL_MARKET_INTELLIGENCE
            )
        elif consent or explicit_supported:
            state = ExplorePersonalizationState.PERSONALIZED
        else:
            state = ExplorePersonalizationState.GENERAL_MARKET_INTELLIGENCE

        limitations = _context_limitations(
            identity,
            consent,
            mapping,
            unapplied,
            unsupported,
        )
        applied_fields: list[str] = []
        if effective.goal:
            applied_fields.append("goal")
        if role_families_applied:
            applied_fields.append("role_families")
        for field in ("included_region_ids", "excluded_region_ids"):
            if getattr(effective, field):
                applied_fields.append(field)
        applied = tuple(applied_fields)
        fingerprint = context_fingerprint(
            identity_version=identity.current_version if identity else None,
            consent=consent,
            effective=effective,
            personalization_state=state,
        )
        return ExploreContext(
            career_identity_id=identity.career_identity_id if identity else None,
            career_identity_version=identity.current_version if identity else None,
            personalization_consent=consent,
            profile_defaults=defaults,
            session_overrides=override_values,
            effective_context=effective,
            context_fingerprint=fingerprint,
            fingerprint_version=FINGERPRINT_VERSION,
            personalization_state=state,
            supported_goal=supported_goal,
            goal_mapping_state=mapping.state,
            applied_context=applied,
            unapplied_context=tuple(unapplied),
            unsupported_context=tuple(unsupported),
            limitations=limitations,
        )

    def _profile_defaults(
        self,
        facts: list[CareerIdentityFact],
    ) -> tuple[ExploreContextValues, list[ExploreContextItem], tuple[str, ...]]:
        roles: list[str] = []
        industries: list[str] = []
        opportunity_types: list[str] = []
        seniorities: list[str] = []
        arrangements: list[str] = []
        included: list[str] = []
        preferred: list[str] = []
        excluded: list[str] = []
        timing: list[str] = []
        goal_inputs: list[str] = []
        unsupported: list[ExploreContextItem] = []
        resolver = GeographicResolver(self._region_repo)
        for fact in facts:
            payload = fact.payload or {}
            if fact.fact_type == "career_goal":
                if isinstance(payload.get("description"), str):
                    goal_inputs.append(payload["description"])
            elif fact.fact_type == "role_preference":
                if payload.get("preference_kind") == "excluded":
                    unsupported.append(
                        _unsupported("excluded_role", "role_families", "career_identity")
                    )
                    continue
                for key in ("function", "role_title"):
                    roles.extend(_tokens(payload.get(key)))
                opportunity_types.extend(_tokens(payload.get("employment_type")))
                seniorities.extend(_tokens(payload.get("seniority")))
            elif fact.fact_type == "industry_preference":
                if payload.get("preference_kind") == "preferred":
                    industries.extend(_tokens(payload.get("industry")))
                elif payload.get("preference_kind") == "excluded":
                    unsupported.append(
                        _unsupported("excluded_industry", "industries", "career_identity")
                    )
            elif fact.fact_type == "work_arrangement_preference":
                if payload.get("willingness") in {"yes", "preferred", "required"}:
                    arrangements.extend(_tokens(payload.get("arrangement")))
                else:
                    unsupported.append(
                        _unsupported(
                            "unapplied_work_exclusion", "work_arrangements", "career_identity"
                        )
                    )
            elif fact.fact_type == "geographic_constraint":
                raw = payload.get("location")
                if raw is None:
                    unsupported.append(
                        _unsupported(
                            "remote_geography_unapplied", "geographic_scope", "career_identity"
                        )
                    )
                    continue
                resolution = resolver.resolve(raw)
                if not resolution.resolved or resolution.region_id is None:
                    unsupported.append(
                        _unsupported("unresolved_geography", "geographic_scope", "career_identity")
                    )
                    continue
                kind = payload.get("constraint_kind")
                if kind == "excluded":
                    excluded.append(resolution.region_id)
                elif kind in {"target", "acceptable"}:
                    if payload.get("relocation_willingness") == "no":
                        included.append(resolution.region_id)
                    else:
                        preferred.append(resolution.region_id)
                else:
                    unsupported.append(
                        _unsupported(
                            "geographic_constraint_not_modeled",
                            "geographic_scope",
                            "career_identity",
                        )
                    )
            elif fact.fact_type == "timing_preference":
                timing_type = payload.get("timing_type")
                urgency = payload.get("urgency")
                if isinstance(timing_type, str):
                    timing.append(
                        f"{_normalize(timing_type)}:{_normalize(urgency)}"
                        if isinstance(urgency, str)
                        else _normalize(timing_type)
                    )
            elif fact.fact_type == "compensation_constraint":
                unsupported.append(
                    _unsupported("compensation_not_modeled", "compensation", "career_identity")
                )

        flat_roles = _unique(_flatten(roles))
        career_stage = _unique(_flatten(seniorities))
        if len(career_stage) > 1:
            unsupported.append(
                _unsupported("multiple_career_stages", "career_stage", "career_identity")
            )
        return (
            ExploreContextValues(
                role_families=flat_roles,
                industries=_unique(_flatten(industries)),
                opportunity_types=_unique(_flatten(opportunity_types)),
                career_stage=career_stage[0] if len(career_stage) == 1 else None,
                work_arrangements=_unique(_flatten(arrangements)),
                preferred_region_ids=_unique(preferred),
                included_region_ids=_unique(included),
                excluded_region_ids=_unique(excluded),
                timing=_unique(timing),
            ),
            unsupported,
            tuple(goal_inputs),
        )

    def _override_values(
        self,
        overrides: ExploreSessionOverrides,
    ) -> tuple[ExploreContextValues, list[ExploreContextItem]]:
        included: list[str] = []
        excluded: list[str] = []
        unsupported: list[ExploreContextItem] = []
        if overrides.geographic_scope is not None:
            resolver = GeographicResolver(self._region_repo)
            for raw, bucket in (
                *((item, included) for item in overrides.geographic_scope.region_refs),
                *((item, excluded) for item in overrides.geographic_scope.excluded_region_refs),
            ):
                resolution = resolver.resolve(raw)
                if resolution.resolved and resolution.region_id is not None:
                    bucket.append(resolution.region_id)
                else:
                    unsupported.append(
                        _unsupported("unresolved_geography", "geographic_scope", "session_override")
                    )
        return (
            ExploreContextValues(
                goal=_normalize(overrides.goal) if overrides.goal else None,
                role_families=_normalize_values(overrides.role_families),
                industries=_normalize_values(overrides.industries),
                opportunity_types=_normalize_values(overrides.opportunity_types),
                work_arrangements=_normalize_values(overrides.work_arrangements),
                included_region_ids=_unique(included),
                excluded_region_ids=_unique(excluded),
            ),
            unsupported,
        )


def map_role_or_goal(values: Iterable[str]) -> GoalMapping:
    values = tuple(_normalize(value) for value in values if _normalize(value))
    if not values:
        return GoalMapping(GoalMappingState.MISSING, None)
    matches: set[CareerGoal] = set()
    for value in values:
        try:
            matches.add(CareerGoal(value.replace(" ", "_")))
            continue
        except ValueError:
            pass
        for goal, aliases in _GOAL_ALIASES.items():
            if any(_alias_matches(alias, value) for alias in aliases):
                matches.add(goal)
    ordered = tuple(goal for goal in CareerGoal if goal in matches)
    if len(ordered) == 1:
        return GoalMapping(GoalMappingState.SUPPORTED, ordered[0], ordered)
    if len(ordered) > 1:
        return GoalMapping(GoalMappingState.AMBIGUOUS, None, ordered)
    return GoalMapping(GoalMappingState.UNSUPPORTED, None)


def context_fingerprint(
    *,
    identity_version: int | None,
    consent: bool,
    effective: ExploreContextValues,
    personalization_state: ExplorePersonalizationState,
) -> str:
    semantic = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "career_identity_version": identity_version,
        "personalization_consent": consent,
        "personalization_state": personalization_state.value,
        "effective_context": _canonical_context_payload(effective),
    }
    encoded = json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    return f"{FINGERPRINT_VERSION}:{hashlib.sha256(encoded).hexdigest()}"


def _overlay(
    defaults: ExploreContextValues,
    override_values: ExploreContextValues,
    raw_overrides: ExploreSessionOverrides,
) -> ExploreContextValues:
    update: dict[str, object] = {}
    for field in ("role_families", "industries", "opportunity_types", "work_arrangements"):
        if getattr(raw_overrides, field) is not None:
            update[field] = getattr(override_values, field)
    if raw_overrides.goal is not None:
        update["goal"] = override_values.goal
    if raw_overrides.geographic_scope is not None:
        update["included_region_ids"] = override_values.included_region_ids
        update["excluded_region_ids"] = override_values.excluded_region_ids
    return defaults.model_copy(update=update)


def _context_limitations(
    identity: CareerIdentity | None,
    consent: bool,
    mapping: GoalMapping,
    unapplied: list[ExploreContextItem],
    unsupported: list[ExploreContextItem],
) -> tuple[str, ...]:
    limitations: list[str] = []
    if identity is None:
        limitations.append(
            "No Career Identity exists; only explicit session context can personalize Fit."
        )
    elif not consent:
        limitations.append(
            "Career Identity personalization consent is not granted; profile facts "
            "were not read or applied."
        )
    if mapping.state is GoalMappingState.MISSING:
        limitations.append(
            "A supported role or goal is needed before the product can call market "
            "intelligence your Fit."
        )
    elif mapping.state is GoalMappingState.AMBIGUOUS:
        limitations.append(
            "The role context maps to multiple governed goals; choose one explicitly."
        )
    elif mapping.state is GoalMappingState.UNSUPPORTED:
        limitations.append(
            "The requested role or goal is outside current governed market intelligence."
        )
    if unapplied:
        limitations.append(
            "Some valid context is retained for display or filtering but does not "
            "change Explore Fit."
        )
    if unsupported:
        limitations.append(
            "Some requested context could not be interpreted or supported by the "
            "current Explore contract."
        )
    return tuple(dict.fromkeys(limitations))


def _alias_matches(alias: str, value: str) -> bool:
    normalized_alias = _normalize(alias)
    if value == normalized_alias:
        return True
    return bool(re.search(rf"\b{re.escape(normalized_alias)}\b", value))


def _tokens(value: object) -> list[str]:
    return [_normalize(value)] if isinstance(value, str) and _normalize(value) else []


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _normalize_values(values: tuple[str, ...] | None) -> tuple[str, ...]:
    return _unique(_normalize(value) for value in values or ())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _canonical_context_payload(effective: ExploreContextValues) -> dict[str, object]:
    payload = effective.model_dump(mode="json")
    set_like_fields = (
        "role_families",
        "industries",
        "opportunity_types",
        "work_arrangements",
        "preferred_region_ids",
        "included_region_ids",
        "excluded_region_ids",
        "timing",
    )
    for field in set_like_fields:
        values = payload.get(field) or []
        payload[field] = sorted(set(values))
    return payload


def _flatten(values: Iterable[object]) -> Iterable[str]:
    for value in values:
        if isinstance(value, str):
            yield value
        elif isinstance(value, Iterable):
            for nested in value:
                if isinstance(nested, str):
                    yield nested


def _unsupported(code: str, field: str, source: str) -> ExploreContextItem:
    return ExploreContextItem(
        code=code,
        field=field,
        source=source,
        reason="This input is not supported by the current Explore context contract.",
    )


def _unapplied(code: str, field: str, source: str) -> ExploreContextItem:
    return ExploreContextItem(
        code=code,
        field=field,
        source=source,
        reason=(
            "This valid context is retained for display or filtering but does not "
            "change Explore Fit."
        ),
    )


def _unapplied_evidence_dimensions(
    effective: ExploreContextValues,
) -> tuple[ExploreContextItem, ...]:
    fields = (
        ("industries", effective.industries),
        ("opportunity_types", effective.opportunity_types),
        ("career_stage", effective.career_stage),
        ("work_arrangements", effective.work_arrangements),
        ("timing", effective.timing),
    )
    return tuple(
        _unapplied(f"{field}_market_evidence_unavailable", field, "effective_context")
        for field, value in fields
        if value not in (None, (), [])
    )
