"""Classification rule seam + a deterministic default implementation.

The rule interfaces are *seams*, not a scoring engine. Two pluggable
strategies live here:

* :class:`EligibilityRule` — decides whether a candidate company belongs in
  the universe and how confident the decision is.
* :class:`MajorTechRule` — decides whether the company carries the
  ``is_major_tech`` label.

The Mag 7 list is a configurable :class:`Mag7List` — admins can swap the
default seven without touching code.

The default implementations are deliberately boring. They consult the
documented in-scope / excluded sector sets and the configured Mag 7 list,
and return ``unknown`` confidence for missing inputs (honoring the
"never silently treat unknown as zero" rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from backend.companies.types import (
    EXCLUDED_SECTORS,
    IN_SCOPE_SECTORS,
    ClassificationConfidence,
    EligibilityStatus,
)

if TYPE_CHECKING:
    from backend.companies.service import CompanyDefinition


# Documented Magnificent 7 (as of writing). Admins can override the list at
# service construction. Names are normalized (lowercased, stripped) before
# comparison; the canonical form here is also lowercased.
DEFAULT_MAG7: frozenset[str] = frozenset(
    {
        "apple",
        "microsoft",
        "alphabet",
        "amazon",
        "nvidia",
        "meta",
        "tesla",
    }
)


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    status: EligibilityStatus
    score: float
    confidence: ClassificationConfidence


@dataclass(frozen=True, slots=True)
class MajorTechResult:
    is_major_tech: bool
    score: float


class EligibilityRule(Protocol):
    def evaluate(self, definition: CompanyDefinition) -> EligibilityResult: ...


class MajorTechRule(Protocol):
    def evaluate(
        self, definition: CompanyDefinition, *, is_mag7: bool
    ) -> MajorTechResult: ...


@dataclass(frozen=True, slots=True)
class Mag7List:
    """Configurable Mag 7 membership list.

    The list is normalized to lowercase. Membership tests normalize the
    candidate name the same way before comparing.
    """

    members: frozenset[str]

    @classmethod
    def default(cls) -> Mag7List:
        return cls(members=DEFAULT_MAG7)

    @classmethod
    def from_iterable(cls, names: object) -> Mag7List:
        return cls(members=frozenset(str(n).strip().lower() for n in names))  # type: ignore[arg-type]

    def is_mag7(self, normalized_name: str) -> bool:
        return normalized_name.strip().lower() in self.members


class DefaultEligibilityRule:
    """Boring default: in-scope sector → eligible; excluded sector → ineligible;
    no sector info → ineligible with ``unknown`` confidence; otherwise →
    ineligible with ``moderate`` confidence.

    The rule does *not* consult the Mag 7 list — the service short-circuits
    Mag 7 to ``eligible`` separately so callers can swap this rule without
    accidentally demoting Mag 7 companies.
    """

    def evaluate(self, definition: CompanyDefinition) -> EligibilityResult:
        sector = (definition.sector_primary or "").strip().lower()
        if not sector:
            return EligibilityResult(
                status=EligibilityStatus.INELIGIBLE,
                score=0.0,
                confidence=ClassificationConfidence.UNKNOWN,
            )
        if sector in EXCLUDED_SECTORS:
            return EligibilityResult(
                status=EligibilityStatus.INELIGIBLE,
                score=0.0,
                confidence=ClassificationConfidence.HIGH_CONFIDENCE,
            )
        if sector in IN_SCOPE_SECTORS:
            return EligibilityResult(
                status=EligibilityStatus.ELIGIBLE,
                score=0.8,
                confidence=ClassificationConfidence.HIGH_CONFIDENCE,
            )
        return EligibilityResult(
            status=EligibilityStatus.INELIGIBLE,
            score=0.0,
            confidence=ClassificationConfidence.MODERATE_CONFIDENCE,
        )


class DefaultMajorTechRule:
    """Boring default: Mag 7 membership implies major-tech.

    Anything outside the Mag 7 list is *not* labeled major-tech by this
    default. Real major-tech assessment requires signals (scale, recognition,
    seriousness) that a future slice will introduce; encoding fake signals
    here would be exactly the speculation Slice 6 is supposed to avoid.
    """

    def evaluate(
        self, definition: CompanyDefinition, *, is_mag7: bool
    ) -> MajorTechResult:
        del definition  # unused in the default rule
        if is_mag7:
            return MajorTechResult(is_major_tech=True, score=1.0)
        return MajorTechResult(is_major_tech=False, score=0.0)
