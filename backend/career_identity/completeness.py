from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.career_identity.schemas import (
    CareerCompletenessState,
    CareerFactState,
    CareerFactType,
    CareerSufficiencyState,
)

SECTION_WEIGHTS: dict[str, int] = {
    "background": 25,
    "skills": 20,
    "goals": 15,
    "role_preferences": 15,
    "location_work": 15,
    "constraints_timing": 10,
}

SECTION_FACT_TYPES: dict[str, frozenset[CareerFactType]] = {
    "background": frozenset(
        {
            CareerFactType.EDUCATION,
            CareerFactType.EXPERIENCE,
            CareerFactType.PROJECT,
            CareerFactType.CREDENTIAL,
        }
    ),
    "skills": frozenset({CareerFactType.SKILL}),
    "goals": frozenset({CareerFactType.CAREER_GOAL}),
    "role_preferences": frozenset(
        {CareerFactType.ROLE_PREFERENCE, CareerFactType.INDUSTRY_PREFERENCE}
    ),
    "location_work": frozenset(
        {
            CareerFactType.GEOGRAPHIC_CONSTRAINT,
            CareerFactType.WORK_ARRANGEMENT_PREFERENCE,
        }
    ),
    "constraints_timing": frozenset(
        {CareerFactType.COMPENSATION_CONSTRAINT, CareerFactType.TIMING_PREFERENCE}
    ),
}

REQUIRED_SUFFICIENCY_SECTIONS = frozenset(
    {"background", "skills", "goals", "role_preferences", "location_work"}
)


def evaluate_career_identity(
    identity: CareerIdentity,
    facts: list[CareerIdentityFact],
) -> dict[str, Any]:
    by_section: dict[str, list[CareerIdentityFact]] = defaultdict(list)
    for fact in facts:
        fact_type = CareerFactType(fact.fact_type)
        for section, fact_types in SECTION_FACT_TYPES.items():
            if fact_type in fact_types:
                by_section[section].append(fact)

    section_results: dict[str, dict[str, Any]] = {}
    total_score = 0
    missing_reason_codes: list[str] = []
    weak_reason_codes: list[str] = []
    actionable_categories: list[str] = []

    for section, weight in SECTION_WEIGHTS.items():
        section_facts = by_section.get(section, [])
        strong_facts = [
            fact
            for fact in section_facts
            if fact.state in {CareerFactState.EXPLICIT.value, CareerFactState.CONFIRMED.value}
        ]
        imported_or_inferred = [
            fact
            for fact in section_facts
            if fact.state in {CareerFactState.IMPORTED.value, CareerFactState.INFERRED.value}
        ]
        if strong_facts:
            section_score = weight
            status = "present"
        elif imported_or_inferred:
            section_score = max(1, weight // 2)
            status = "weak"
            weak_reason_codes.append(f"weak_{section}")
            actionable_categories.append(section)
        else:
            section_score = 0
            status = "missing"
            missing_reason_codes.append(f"missing_{section}")
            actionable_categories.append(section)
        total_score += section_score
        section_results[section] = {
            "status": status,
            "score": section_score,
            "weight": weight,
            "fact_count": len(section_facts),
            "strong_fact_count": len(strong_facts),
            "reason_code": f"{status}_{section}",
        }

    if total_score == 0:
        completeness_state = CareerCompletenessState.EMPTY
    elif total_score < 35:
        completeness_state = CareerCompletenessState.MINIMAL
    elif total_score < 80:
        completeness_state = CareerCompletenessState.PARTIAL
    else:
        completeness_state = CareerCompletenessState.COMPLETE

    present_sections = {
        section
        for section, result in section_results.items()
        if result["status"] in {"present", "weak"}
    }
    strong_sufficient_sections = {
        section
        for section, result in section_results.items()
        if result["status"] == "present"
    }
    sufficient = (
        REQUIRED_SUFFICIENCY_SECTIONS.issubset(present_sections)
        and len(strong_sufficient_sections & REQUIRED_SUFFICIENCY_SECTIONS) >= 3
        and total_score >= 60
    )
    sufficiency_state = (
        CareerSufficiencyState.SUFFICIENT
        if sufficient
        else CareerSufficiencyState.INSUFFICIENT
    )
    if not sufficient:
        for section in sorted(REQUIRED_SUFFICIENCY_SECTIONS - present_sections):
            code = f"insufficient_missing_{section}"
            if code not in missing_reason_codes:
                missing_reason_codes.append(code)
        if len(strong_sufficient_sections & REQUIRED_SUFFICIENCY_SECTIONS) < 3:
            weak_reason_codes.append("insufficient_confirmed_or_explicit_signal")

    return {
        "identity_version": identity.current_version,
        "overall_score": total_score,
        "score_basis": "weighted_section_presence_v1",
        "completeness_state": completeness_state.value,
        "sufficiency_state": sufficiency_state.value,
        "sections": section_results,
        "missing_reason_codes": tuple(dict.fromkeys(missing_reason_codes)),
        "weak_reason_codes": tuple(dict.fromkeys(weak_reason_codes)),
        "actionable_categories": tuple(dict.fromkeys(actionable_categories)),
        "sufficient": sufficient,
    }

