"""Normalization helpers and density formulas.

Pure functions over scalar inputs. No DB access, no service imports.

Per ``DATA_MODEL.md`` §8:
* normalized views must remain *separate* from raw component scores;
* the system must not collapse all scores into one opaque denominator.

The two density helpers (:func:`general_density_score` and
:func:`tech_market_density_score`) are *not* the final true-density
formulas the docs describe (those need external denominators like metro
size or tech workforce, deferred post-MVP). They are deterministic
saturation-capped aggregates that give callers separate views — *general*
captures all sectors, *tech* captures major-tech only — without faking
external data.
"""

from __future__ import annotations


def saturate(value: int | float, cap: int | float) -> float:
    """Clamp ``value`` to ``[0, cap]`` and return ``value / cap`` as a float.

    ``cap`` must be strictly positive. ``value <= 0`` returns ``0.0``;
    ``value >= cap`` returns ``1.0``.
    """
    if cap <= 0:
        raise ValueError(f"cap must be positive, got {cap!r}")
    if value <= 0:
        return 0.0
    if value >= cap:
        return 1.0
    return float(value) / float(cap)


def general_density_score(
    *,
    eligible_count: int,
    total_active_postings: int,
    cap_eligible: int,
    cap_postings: int,
) -> float:
    """All-sector opportunity-density view, saturation-capped.

    Returns a 0–1 number that responds to both eligible-company breadth and
    total-posting volume. Equal weighting of the two saturation-capped
    components keeps the formula audit-friendly.
    """
    return 0.5 * saturate(eligible_count, cap_eligible) + 0.5 * saturate(
        total_active_postings, cap_postings
    )


def tech_market_density_score(
    *,
    major_tech_company_count: int,
    major_tech_active_postings: int,
    cap_major_companies: int,
    cap_major_postings: int,
) -> float:
    """Tech-only opportunity-density view, saturation-capped.

    Restricts inputs to major-tech companies (and their postings) so this
    view stays distinct from the general density above.
    """
    return 0.5 * saturate(
        major_tech_company_count, cap_major_companies
    ) + 0.5 * saturate(major_tech_active_postings, cap_major_postings)


def raw_total_score(
    *,
    structural_ecosystem: float,
    live_market: float,
    objective_opportunity: float,
    w_structural: float,
    w_live: float,
    w_objective: float,
) -> float:
    """Weighted sum of the three top-level aggregates."""
    total = (
        structural_ecosystem * w_structural
        + live_market * w_live
        + objective_opportunity * w_objective
    )
    return min(max(total, 0.0), 1.0)
