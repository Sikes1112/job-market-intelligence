"""Controlled tradeoff generation for ranked recommendations.

Tradeoffs in this module are derived only from resolved score components,
existing explanation warnings/manual-verification items, or explicitly marked
heuristic proxy signals. The module does not create market narratives.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.recommendations.goal_modes import RecommendationScoreComponent
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationImportance,
    RecommendationTradeoff,
    RecommendationTradeoffCategory,
)


class TradeoffSignalStatus(StrEnum):
    USED = "used"
    MISSING = "missing"
    PROXY = "proxy"


class TradeoffSignal(BaseModel):
    """Component snapshot consumed by controlled tradeoff rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    status: TradeoffSignalStatus
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    is_proxy: bool = False
    inferred: bool = False

    @model_validator(mode="after")
    def _signal_is_traceable(self) -> TradeoffSignal:
        if self.status is TradeoffSignalStatus.MISSING:
            if self.value is not None:
                raise ValueError("missing tradeoff signals cannot carry values")
            return self
        if self.value is None:
            raise ValueError("used tradeoff signals must carry bounded values")
        if self.status is TradeoffSignalStatus.PROXY and not self.is_proxy:
            raise ValueError("proxy tradeoff signals must be marked proxy")
        if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis:
            if not self.inferred or not self.is_proxy:
                raise ValueError("heuristic tradeoff signals must be proxy/inferred")
        structured_basis = [
            basis
            for basis in self.evidence_basis
            if basis
            not in {
                RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
                RecommendationEvidenceBasis.MISSING_DATA,
                RecommendationEvidenceBasis.USER_PREFERENCE,
            }
        ]
        if structured_basis and not self.evidence_refs:
            raise ValueError("structured tradeoff signals require evidence references")
        return self


def generate_controlled_tradeoffs(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
    *,
    explanation: RecommendationExplanation | None = None,
    final_score: float | None = None,
) -> tuple[RecommendationTradeoff, ...]:
    """Generate bounded tradeoffs from resolved score-component signals."""

    tradeoffs: list[RecommendationTradeoff] = []
    _append_if_supported(
        tradeoffs,
        _broad_opportunity_competition_tradeoff(signals),
    )
    _append_if_supported(
        tradeoffs,
        _ai_cloud_narrow_universe_tradeoff(signals),
    )
    _append_if_supported(
        tradeoffs,
        _underrated_prestige_tradeoff(signals),
    )
    _append_if_supported(
        tradeoffs,
        _lower_competition_role_volume_tradeoff(signals),
    )
    _append_if_supported(
        tradeoffs,
        _prestige_entry_access_tradeoff(signals),
    )
    _append_if_supported(
        tradeoffs,
        _data_quality_tradeoff(signals, final_score=final_score),
    )
    _append_if_supported(
        tradeoffs,
        _manual_verification_tradeoff(signals, explanation=explanation),
    )
    return tuple(_dedupe_tradeoffs(tradeoffs))


def _broad_opportunity_competition_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
) -> RecommendationTradeoff | None:
    density = signals.get(RecommendationScoreComponent.COMPANY_DENSITY)
    lower_competition = signals.get(RecommendationScoreComponent.LOWER_COMPETITION_PROXY)
    if not (_high(density) and _low(lower_competition)):
        return None
    return _tradeoff(
        RecommendationTradeoffCategory.OPPORTUNITY_VS_COMPETITION,
        "Broad opportunity but competition risk",
        "Company-density evidence is strong enough to support broad opportunity.",
        (
            "The lower-competition proxy is weak, so competition risk remains an "
            "explicitly inferred caveat."
        ),
        (density, lower_competition),
        importance=RecommendationImportance.HIGH,
        inferred=True,
    )


def _ai_cloud_narrow_universe_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
) -> RecommendationTradeoff | None:
    ai_cloud = signals.get(RecommendationScoreComponent.AI_CLOUD_CONCENTRATION)
    density = signals.get(RecommendationScoreComponent.COMPANY_DENSITY)
    if not (_high(ai_cloud) and _low(density)):
        return None
    return _tradeoff(
        RecommendationTradeoffCategory.AI_CLOUD_CONCENTRATION_VS_COMPANY_UNIVERSE,
        "AI/cloud concentration but narrower company universe",
        "AI/cloud concentration is strong within the available structured signals.",
        "Company-density evidence is weaker, so the actionable company universe may be narrow.",
        (ai_cloud, density),
        importance=RecommendationImportance.MEDIUM,
        inferred=bool(ai_cloud and ai_cloud.is_proxy),
    )


def _underrated_prestige_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
) -> RecommendationTradeoff | None:
    lower_competition = signals.get(RecommendationScoreComponent.LOWER_COMPETITION_PROXY)
    density = signals.get(RecommendationScoreComponent.COMPANY_DENSITY)
    prestige = signals.get(RecommendationScoreComponent.PRESTIGE_DENSITY)
    if not (_high(lower_competition) and _not_low(density) and _low(prestige)):
        return None
    return _tradeoff(
        RecommendationTradeoffCategory.GROWTH_VS_PRESTIGE_DENSITY,
        "Underrated-market proxy but weaker prestige density",
        "Lower-competition and company-density signals support a proxy underrated-market thesis.",
        "Prestige-density evidence is weaker, so brand concentration is not the strength.",
        (lower_competition, density, prestige),
        importance=RecommendationImportance.MEDIUM,
        inferred=True,
    )


def _lower_competition_role_volume_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
) -> RecommendationTradeoff | None:
    lower_competition = signals.get(RecommendationScoreComponent.LOWER_COMPETITION_PROXY)
    density = signals.get(RecommendationScoreComponent.COMPANY_DENSITY)
    diversity = signals.get(RecommendationScoreComponent.ROLE_DIVERSITY)
    if not _high(lower_competition):
        return None
    if not (_low(density) or _low(diversity)):
        return None
    negative = (
        "Company-density evidence is weaker, so fewer total roles may be available."
        if _low(density)
        else "Role-diversity evidence is weaker, so the available role set may be narrower."
    )
    return _tradeoff(
        RecommendationTradeoffCategory.LOWER_COMPETITION_VS_ROLE_VOLUME,
        "Lower competition proxy but fewer total roles",
        "The lower-competition component is favorable, but it is explicitly a proxy.",
        negative,
        (lower_competition, density if _low(density) else diversity),
        importance=RecommendationImportance.MEDIUM,
        inferred=True,
    )


def _prestige_entry_access_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
) -> RecommendationTradeoff | None:
    prestige = signals.get(RecommendationScoreComponent.PRESTIGE_DENSITY)
    entry = signals.get(RecommendationScoreComponent.ENTRY_LEVEL_ACCESS)
    if not (_high(prestige) and _low(entry)):
        return None
    return _tradeoff(
        RecommendationTradeoffCategory.PRESTIGE_VS_ENTRY_LEVEL_ACCESS,
        "High prestige but weaker entry-level access",
        "Prestige-density evidence is strong.",
        "Entry-level access evidence is weaker and should not be treated as solved.",
        (prestige, entry),
        importance=RecommendationImportance.HIGH,
        inferred=False,
    )


def _data_quality_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
    *,
    final_score: float | None,
) -> RecommendationTradeoff | None:
    quality_signals = tuple(
        signal
        for signal in (
            signals.get(RecommendationScoreComponent.MARKET_COVERAGE),
            signals.get(RecommendationScoreComponent.CONFIDENCE),
            signals.get(RecommendationScoreComponent.FRESHNESS),
        )
        if signal is not None
    )
    weak_quality = tuple(
        signal
        for signal in quality_signals
        if signal.status is TradeoffSignalStatus.MISSING or _low(signal)
    )
    if not weak_quality:
        return None
    strong_signal = any(
        _high(signal)
        for component, signal in signals.items()
        if component
        not in {
            RecommendationScoreComponent.MARKET_COVERAGE,
            RecommendationScoreComponent.CONFIDENCE,
            RecommendationScoreComponent.FRESHNESS,
        }
    )
    if not strong_signal and (final_score is None or final_score < 0.55):
        return None
    return _tradeoff(
        RecommendationTradeoffCategory.DATA_QUALITY,
        "Good fit but evidence quality needs checking",
        "At least one fit component is strong under the selected profile.",
        (
            "Coverage, confidence, freshness, or missing-data evidence should be "
            "verified before acting."
        ),
        weak_quality,
        importance=RecommendationImportance.HIGH,
        inferred=False,
        allow_missing_basis=True,
    )


def _manual_verification_tradeoff(
    signals: Mapping[RecommendationScoreComponent, TradeoffSignal],
    *,
    explanation: RecommendationExplanation | None,
) -> RecommendationTradeoff | None:
    if explanation is None or not explanation.manual_verification:
        return None
    if not any(_high(signal) for signal in signals.values()):
        return None
    refs = tuple(
        ref
        for item in explanation.manual_verification
        for ref in item.evidence_refs
    )
    basis = tuple(
        dict.fromkeys(
            basis
            for item in explanation.manual_verification
            for basis in item.evidence_basis
        )
    ) or (RecommendationEvidenceBasis.MISSING_DATA,)
    category = (
        ManualVerificationCategory.LOCATION_REQUIREMENTS
        if any(
            item.verification_category is ManualVerificationCategory.LOCATION_REQUIREMENTS
            for item in explanation.manual_verification
        )
        else ManualVerificationCategory.SOURCE_CONFIRMATION
    )
    label = (
        "Good fit but location requirements need verification"
        if category is ManualVerificationCategory.LOCATION_REQUIREMENTS
        else "Good fit but manual verification remains"
    )
    return RecommendationTradeoff(
        tradeoff_category=RecommendationTradeoffCategory.DATA_QUALITY,
        label=label,
        positive_side="The ranked explanation includes favorable structured signals.",
        negative_side="Manual verification items remain attached to this recommendation.",
        importance=RecommendationImportance.MEDIUM,
        evidence_strength=(
            RecommendationEvidenceStrength.MISSING
            if basis == (RecommendationEvidenceBasis.MISSING_DATA,)
            else RecommendationEvidenceStrength.MODERATE
        ),
        evidence_basis=basis,
        evidence_refs=refs,
    )


def _tradeoff(
    category: RecommendationTradeoffCategory,
    label: str,
    positive: str,
    negative: str,
    signals: tuple[TradeoffSignal | None, ...],
    *,
    importance: RecommendationImportance,
    inferred: bool,
    allow_missing_basis: bool = False,
) -> RecommendationTradeoff | None:
    relevant = tuple(signal for signal in signals if signal is not None)
    refs = tuple(
        ref
        for signal in relevant
        for ref in signal.evidence_refs
    )
    basis = _basis_for_tradeoff(
        relevant,
        refs,
        inferred=inferred,
        allow_missing=allow_missing_basis,
    )
    if not basis:
        return None
    return RecommendationTradeoff(
        tradeoff_category=category,
        label=label,
        positive_side=positive,
        negative_side=negative,
        importance=importance,
        evidence_strength=(
            RecommendationEvidenceStrength.INFERRED
            if inferred
            else RecommendationEvidenceStrength.MODERATE
        ),
        evidence_basis=basis,
        support=(
            RecommendationClaimSupport.INFERRED
            if inferred
            else RecommendationClaimSupport.DIRECT
        ),
        evidence_refs=_refs_allowed_by_basis(refs, basis),
    )


def _basis_for_tradeoff(
    signals: tuple[TradeoffSignal, ...],
    refs: tuple[RecommendationEvidenceReference, ...],
    *,
    inferred: bool,
    allow_missing: bool,
) -> tuple[RecommendationEvidenceBasis, ...]:
    basis: set[RecommendationEvidenceBasis] = {ref.basis for ref in refs}
    if inferred:
        basis.add(RecommendationEvidenceBasis.HEURISTIC_INFERENCE)
    if allow_missing and any(
        signal.status is TradeoffSignalStatus.MISSING for signal in signals
    ):
        basis.add(RecommendationEvidenceBasis.MISSING_DATA)
    if not basis and inferred:
        basis.add(RecommendationEvidenceBasis.HEURISTIC_INFERENCE)
    return tuple(sorted(basis, key=lambda item: item.value))


def _refs_allowed_by_basis(
    refs: tuple[RecommendationEvidenceReference, ...],
    basis: tuple[RecommendationEvidenceBasis, ...],
) -> tuple[RecommendationEvidenceReference, ...]:
    basis_set = set(basis)
    deduped: dict[tuple[str, str | None], RecommendationEvidenceReference] = {}
    for ref in refs:
        if ref.basis not in basis_set:
            continue
        deduped[(ref.basis.value, ref.reference_id or ref.label)] = ref
    return tuple(deduped[key] for key in sorted(deduped))


def _append_if_supported(
    tradeoffs: list[RecommendationTradeoff],
    tradeoff: RecommendationTradeoff | None,
) -> None:
    if tradeoff is not None:
        tradeoffs.append(tradeoff)


def _dedupe_tradeoffs(
    tradeoffs: list[RecommendationTradeoff],
) -> tuple[RecommendationTradeoff, ...]:
    deduped: dict[RecommendationTradeoffCategory, RecommendationTradeoff] = {}
    for tradeoff in tradeoffs:
        deduped.setdefault(tradeoff.tradeoff_category, tradeoff)
    return tuple(deduped.values())


def _high(signal: TradeoffSignal | None) -> bool:
    return bool(
        signal is not None
        and signal.value is not None
        and signal.status is not TradeoffSignalStatus.MISSING
        and signal.value >= 0.7
    )


def _not_low(signal: TradeoffSignal | None) -> bool:
    return bool(
        signal is not None
        and signal.value is not None
        and signal.status is not TradeoffSignalStatus.MISSING
        and signal.value > 0.35
    )


def _low(signal: TradeoffSignal | None) -> bool:
    return bool(
        signal is not None
        and (
            signal.status is TradeoffSignalStatus.MISSING
            or (signal.value is not None and signal.value <= 0.35)
        )
    )
