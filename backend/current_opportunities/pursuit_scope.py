"""Authoritative Layer 36 pursuit scope for Layer 38 opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.career_decisions.models import CareerDecision, DecisionOption


class PursuitOpportunityScopeError(ValueError):
    """The selected Decision context cannot define an opportunity scope."""


@dataclass(frozen=True, slots=True)
class PursuitOpportunityScope:
    """Frozen, explicitly supported opportunity filters from a selected Decision option.

    A canonical market is a hard boundary for location Decisions. Other fields only
    become hard filters when the Decision option or a hard Decision constraint names
    the corresponding Layer 38 field explicitly.
    """

    market_id: str | None = None
    role_families: tuple[str, ...] = ()
    opportunity_types: tuple[str, ...] = ()
    work_arrangements: tuple[str, ...] = ()
    satisfiable: bool = True

    def allows(self, opportunity: Any) -> bool:
        if not self.satisfiable:
            return False
        if self.market_id is not None and opportunity.market_id != self.market_id:
            return False
        if self.role_families and opportunity.role_family not in self.role_families:
            return False
        if self.opportunity_types and opportunity.opportunity_type not in self.opportunity_types:
            return False
        return not (
            self.work_arrangements and opportunity.work_arrangement not in self.work_arrangements
        )


def pursuit_opportunity_scope(
    decision: CareerDecision,
    selected_option: DecisionOption,
) -> PursuitOpportunityScope:
    """Build the shared pursuit scope without consulting mutable Profile state."""

    if (
        selected_option.decision_id != decision.decision_id
        or selected_option.user_id != decision.user_id
        or selected_option.option_id != decision.selected_option_id
    ):
        raise PursuitOpportunityScopeError("selected option does not belong to the pursuit")

    scenario = selected_option.scenario or {}
    market_id = None
    if decision.decision_type == "location_choice":
        market_id = _first_value(scenario, "region_id", "region_ids")
        if market_id is None:
            raise PursuitOpportunityScopeError(
                "a location pursuit requires a canonical selected market"
            )

    explicit = {
        "role_families": _values(scenario, "role_family", "role_families"),
        "opportunity_types": _values(scenario, "opportunity_type", "opportunity_types"),
        "work_arrangements": _values(scenario, "work_arrangement", "work_arrangements"),
    }
    constraint_fields = {
        "role_family": "role_families",
        "opportunity_type": "opportunity_types",
        "work_arrangement": "work_arrangements",
    }
    satisfiable = True
    for constraint in decision.constraints or []:
        if not isinstance(constraint, dict) or not constraint.get("hard", True):
            continue
        destination = constraint_fields.get(str(constraint.get("field") or ""))
        if destination is None or str(constraint.get("operator") or "equals") not in {
            "equals",
            "in",
        }:
            continue
        constraint_values = _as_values(constraint.get("value"))
        merged = _merge_values(explicit[destination], constraint_values)
        if explicit[destination] and constraint_values and not merged:
            satisfiable = False
        explicit[destination] = merged

    return PursuitOpportunityScope(
        market_id=market_id,
        role_families=explicit["role_families"],
        opportunity_types=explicit["opportunity_types"],
        work_arrangements=explicit["work_arrangements"],
        satisfiable=satisfiable,
    )


def _first_value(payload: dict[str, Any], singular: str, plural: str) -> str | None:
    values = _values(payload, singular, plural)
    return values[0] if values else None


def _values(payload: dict[str, Any], singular: str, plural: str) -> tuple[str, ...]:
    value = payload.get(singular)
    if value is None:
        value = payload.get(plural)
    return _as_values(value)


def _as_values(value: Any) -> tuple[str, ...]:
    raw = value if isinstance(value, (list, tuple, set)) else (value,)
    return tuple(
        dict.fromkeys(str(item).strip() for item in raw if item is not None and str(item).strip())
    )


def _merge_values(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    if not left:
        return right
    if not right:
        return left
    return tuple(value for value in left if value in set(right))
