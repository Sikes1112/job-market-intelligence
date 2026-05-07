"""Personalization scoring formulas.

Pure-function module. No DB access, no service imports, no upstream
business-layer imports. The functions below take stored canonical values as
plain arguments and return component scores in ``[0.0, 1.0]``.

Documented hierarchy:

* ``role_fit`` (35%) and ``industry_fit`` (30%) lead — together they are
  65% of the personal company score, so role+industry **must** weigh more
  than prestige+brand combined (35%);
* ``prestige_fit`` (20%) and ``brand_fit`` (15%) sit below role/industry.

Missing preferences are treated *neutrally* (component=0.5 when the user
expressed no opinion), never as a fake strong preference. Missing canonical
data (``role_family_summary=None``, no presence record, etc.) returns 0.0
for the affected component and is documented via warnings emitted by the
service layer.
"""

from __future__ import annotations

from typing import Any

from backend.personalization.types import PreferenceLevel

# Component weights. Must sum to 1.0; role+industry must exceed prestige+brand.
W_ROLE: float = 0.35
W_INDUSTRY: float = 0.30
W_PRESTIGE: float = 0.20
W_BRAND: float = 0.15

assert abs((W_ROLE + W_INDUSTRY + W_PRESTIGE + W_BRAND) - 1.0) < 1e-9
assert (W_ROLE + W_INDUSTRY) > (W_PRESTIGE + W_BRAND)

# A neutral component score when the user expressed no preference at all
# for that dimension.
_NEUTRAL: float = 0.5


def _clip01(value: float) -> float:
    if value <= 0:
        return 0.0
    if value >= 1:
        return 1.0
    return float(value)


# ---------------------------------------------------------------------------
# Role fit
# ---------------------------------------------------------------------------


def role_fit_component(
    *,
    role_targets: list[str],
    role_family_summary: dict[str, int] | None,
) -> tuple[float, list[str]]:
    """Fraction of postings (in ``role_family_summary``) that match the
    user's ``role_targets``, capped to ``[0, 1]``.

    Returns ``(score, notes)``. ``notes`` lists matched role-family keys.
    Empty role_targets → neutral 0.5 (no preference to score against).
    Missing role_family_summary → 0.0 with no notes (caller should warn).
    """
    if not role_targets:
        return _NEUTRAL, []
    if not role_family_summary:
        return 0.0, []
    targets = {t.strip().lower() for t in role_targets if t.strip()}
    if not targets:
        return _NEUTRAL, []

    total = sum(role_family_summary.values())
    if total <= 0:
        return 0.0, []

    matched = 0
    notes: list[str] = []
    for key, count in role_family_summary.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            continue
        if key.strip().lower() in targets:
            matched += count
            notes.append(f"role:{key}")
    return _clip01(matched / total), sorted(notes)


# ---------------------------------------------------------------------------
# Industry fit
# ---------------------------------------------------------------------------


def industry_fit_component(
    *,
    industry_preferences: list[str],
    sector_primary: str | None,
    sector_secondary: str | None,
) -> tuple[float, list[str]]:
    """Match the company's sectors against the user's industry preferences.

    Primary-sector match → 1.0; secondary-only match → 0.5; no match → 0.0.
    Empty industry_preferences → neutral 0.5.
    Both sectors missing → 0.0.
    """
    if not industry_preferences:
        return _NEUTRAL, []
    prefs = {p.strip().lower() for p in industry_preferences if p.strip()}
    if not prefs:
        return _NEUTRAL, []
    primary = sector_primary.strip().lower() if sector_primary else None
    secondary = sector_secondary.strip().lower() if sector_secondary else None
    notes: list[str] = []
    if primary and primary in prefs:
        notes.append(f"industry_primary:{sector_primary}")
        return 1.0, notes
    if secondary and secondary in prefs:
        notes.append(f"industry_secondary:{sector_secondary}")
        return 0.5, notes
    return 0.0, []


# ---------------------------------------------------------------------------
# Prestige fit
# ---------------------------------------------------------------------------


def _prestige_company_signal(
    prestige_score: float | None,
    is_major_tech: bool,
    is_mag7: bool,
) -> float:
    """Aggregate the company's prestige signals into a single ``[0, 1]`` value."""
    signal = 0.0
    if prestige_score is not None:
        signal = max(signal, _clip01(float(prestige_score)))
    if is_mag7:
        signal = max(signal, 1.0)
    elif is_major_tech:
        signal = max(signal, 0.7)
    return signal


def prestige_fit_component(
    *,
    preference: PreferenceLevel | None,
    prestige_score: float | None,
    is_major_tech: bool,
    is_mag7: bool,
) -> tuple[float, list[str]]:
    """Map (preference, company prestige signal) to a ``[0, 1]`` fit score.

    * ``preference`` ``None`` → neutral ``0.5``
    * ``high`` → fit equals the prestige signal directly
    * ``medium`` → fit ``= 0.5 + 0.5 * signal`` (mild reward, never negative)
    * ``low`` → fit ``= 1.0 - 0.5 * signal`` (mild de-emphasis of high-prestige)
    """
    signal = _prestige_company_signal(prestige_score, is_major_tech, is_mag7)
    notes: list[str] = []
    if is_mag7:
        notes.append("prestige:mag7")
    elif is_major_tech:
        notes.append("prestige:major_tech")
    if preference is None:
        return _NEUTRAL, notes
    if preference is PreferenceLevel.HIGH:
        return _clip01(signal), notes
    if preference is PreferenceLevel.MEDIUM:
        return _clip01(0.5 + 0.5 * signal), notes
    if preference is PreferenceLevel.LOW:
        return _clip01(1.0 - 0.5 * signal), notes
    return _NEUTRAL, notes


# ---------------------------------------------------------------------------
# Brand fit
# ---------------------------------------------------------------------------


def brand_fit_component(
    *,
    preference: PreferenceLevel | None,
    is_major_tech: bool,
    is_mag7: bool,
) -> tuple[float, list[str]]:
    """Map (preference, company brand recognition) to a ``[0, 1]`` fit score.

    Brand signal is binary-ish: Mag 7 → 1.0; major-tech → 0.5; else → 0.0.
    Mapping mirrors ``prestige_fit_component`` so the component vocabulary
    stays consistent.
    """
    signal = 0.0
    notes: list[str] = []
    if is_mag7:
        signal = 1.0
        notes.append("brand:mag7")
    elif is_major_tech:
        signal = 0.5
        notes.append("brand:major_tech")
    if preference is None:
        return _NEUTRAL, notes
    if preference is PreferenceLevel.HIGH:
        return _clip01(signal), notes
    if preference is PreferenceLevel.MEDIUM:
        return _clip01(0.5 + 0.5 * signal), notes
    if preference is PreferenceLevel.LOW:
        return _clip01(1.0 - 0.5 * signal), notes
    return _NEUTRAL, notes


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def personal_company_score(
    *,
    role_fit: float,
    industry_fit: float,
    prestige_fit: float,
    brand_fit: float,
) -> float:
    """Weighted sum of the four components. Bounded ``[0.0, 1.0]``."""
    return _clip01(
        W_ROLE * _clip01(role_fit)
        + W_INDUSTRY * _clip01(industry_fit)
        + W_PRESTIGE * _clip01(prestige_fit)
        + W_BRAND * _clip01(brand_fit)
    )


def personal_market_score(*, company_scores: list[float]) -> float:
    """Average of company-level personal scores; ``0.0`` when empty."""
    if not company_scores:
        return 0.0
    clipped = [_clip01(s) for s in company_scores]
    return _clip01(sum(clipped) / len(clipped))


def weights_snapshot() -> dict[str, Any]:
    """Diagnostic for tests / future audit reads — never mutated."""
    return {
        "role": W_ROLE,
        "industry": W_INDUSTRY,
        "prestige": W_PRESTIGE,
        "brand": W_BRAND,
    }
