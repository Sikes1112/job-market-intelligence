"""Career-goal definitions for market intelligence scoring."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from backend.market_intelligence.schemas import (
    CareerGoal,
    CareerGoalDefinition,
    EvidenceBasis,
    EvidenceCategoryLabel,
    GoalEvidenceClassification,
    IntelligenceConfidence,
)


def _labels(*items: tuple[str, str]) -> tuple[EvidenceCategoryLabel, ...]:
    return tuple(EvidenceCategoryLabel(code=code, label=label) for code, label in items)


def _label_text(
    labels: tuple[EvidenceCategoryLabel, ...],
    categories: tuple[str, ...],
) -> tuple[str, ...]:
    by_code = {label.code: label.label for label in labels}
    return tuple(by_code[category] for category in categories)


SOFTWARE_ENGINEERING_LABELS = _labels(
    ("hiring_activity", "Engineering-relevant hiring evidence"),
    ("tech_signal", "Technical employer and density evidence"),
    ("early_career", "Entry-level technical pathway evidence"),
    ("internship", "Technical internship evidence"),
    ("employer_presence", "Broad employer diversity proxy"),
)

PRODUCT_MANAGEMENT_LABELS = _labels(
    ("product_activity", "Product role-family hiring evidence"),
    ("formal_programs", "Generic formal early-career program proxy"),
    ("early_career", "Early-career accessibility proxy"),
    ("employer_presence", "Broad employer ecosystem proxy"),
)

AI_ML_LABELS = _labels(
    ("ai_cloud_activity", "AI/cloud role-family hiring evidence"),
    ("ai_cloud_employers", "AI/cloud employer evidence"),
    ("internship", "AI-relevant internship evidence"),
    ("tech_signal", "Advanced-technology ecosystem proxy"),
)

CYBERSECURITY_LABELS = _labels(
    ("cybersecurity_activity", "Cybersecurity role-family hiring evidence"),
    ("cybersecurity_employers", "Cybersecurity employer evidence"),
    ("hiring_activity", "Broad hiring activity proxy"),
    ("early_career", "Security-accessible entry-level proxy"),
)

DATA_SCIENCE_LABELS = _labels(
    ("data_science_role_activity", "Data-science role-family hiring evidence"),
    ("data_science_internship", "Data-science internship evidence"),
    ("ai_cloud_activity", "AI/cloud adjacent proxy"),
    ("product_activity", "Product analytics proxy"),
    ("tech_signal", "Technical ecosystem proxy"),
    ("early_career", "Early-career accessibility proxy"),
    ("hiring_activity", "Broad hiring activity proxy"),
)


GOAL_DEFINITIONS = MappingProxyType(
    {
        CareerGoal.SOFTWARE_ENGINEERING: CareerGoalDefinition(
            goal=CareerGoal.SOFTWARE_ENGINEERING,
            label="Software engineering",
            description=(
                "Favor markets with technical hiring evidence, technical employer "
                "signals, internships, and entry-level pathways."
            ),
            direct_signals=_label_text(
                SOFTWARE_ENGINEERING_LABELS,
                (
                    "hiring_activity",
                    "tech_signal",
                    "early_career",
                    "internship",
                ),
            ),
            direct_evidence_categories=(
                "hiring_activity",
                "tech_signal",
                "early_career",
                "internship",
            ),
            proxy_evidence_categories=("employer_presence",),
            minimum_direct_evidence=2,
            minimum_total_evidence=3,
            proxy_only_confidence_cap=IntelligenceConfidence.LOW,
            unsupported_conditions=(
                "No ranking-eligible technical hiring, internship, or entry-level "
                "pathway evidence is available.",
            ),
            weighting_rationale=(
                "Observed hiring carries the largest weight, while technical employer "
                "signals and early-career pathways must outweigh broad employer counts."
            ),
            public_safe_labels=SOFTWARE_ENGINEERING_LABELS,
        ),
        CareerGoal.PRODUCT_MANAGEMENT: CareerGoalDefinition(
            goal=CareerGoal.PRODUCT_MANAGEMENT,
            label="Product management",
            description=(
                "Favor markets with product role-family evidence, while treating "
                "generic program pathways and employer breadth as secondary proxies."
            ),
            direct_signals=_label_text(
                PRODUCT_MANAGEMENT_LABELS,
                ("product_activity",),
            ),
            direct_evidence_categories=("product_activity",),
            proxy_evidence_categories=(
                "formal_programs",
                "early_career",
                "employer_presence",
            ),
            minimum_direct_evidence=1,
            minimum_total_evidence=2,
            proxy_only_confidence_cap=IntelligenceConfidence.LOW,
            unsupported_conditions=(
                "No product role-family hiring evidence is available.",
                "Generic formal early-career program evidence is proxy evidence "
                "unless a product-specific canonical program fact is available.",
            ),
            weighting_rationale=(
                "Product role-family activity is weighted ahead of broad employer "
                "counts and generic early-career programs so non-product signals "
                "cannot satisfy direct evidence for this goal."
            ),
            public_safe_labels=PRODUCT_MANAGEMENT_LABELS,
        ),
        CareerGoal.AI_ML: CareerGoalDefinition(
            goal=CareerGoal.AI_ML,
            label="AI/ML",
            description=(
                "Favor markets with AI/cloud role activity, AI/cloud employers, "
                "and internships, with generic technical density as a proxy."
            ),
            direct_signals=_label_text(
                AI_ML_LABELS,
                ("ai_cloud_activity", "ai_cloud_employers", "internship"),
            ),
            direct_evidence_categories=(
                "ai_cloud_activity",
                "ai_cloud_employers",
                "internship",
            ),
            proxy_evidence_categories=("tech_signal",),
            minimum_direct_evidence=1,
            minimum_total_evidence=2,
            proxy_only_confidence_cap=IntelligenceConfidence.LOW,
            unsupported_conditions=(
                "No AI/cloud role-family evidence, AI/cloud employer evidence, "
                "or AI-relevant internship evidence is available.",
            ),
            weighting_rationale=(
                "Direct AI/cloud activity and employers dominate; broader technology "
                "density only supports the ranking as a proxy."
            ),
            public_safe_labels=AI_ML_LABELS,
        ),
        CareerGoal.CYBERSECURITY: CareerGoalDefinition(
            goal=CareerGoal.CYBERSECURITY,
            label="Cybersecurity",
            description=(
                "Favor markets with cybersecurity role-family and employer evidence, "
                "using broad hiring and entry-level access only as support."
            ),
            direct_signals=_label_text(
                CYBERSECURITY_LABELS,
                ("cybersecurity_activity", "cybersecurity_employers"),
            ),
            direct_evidence_categories=(
                "cybersecurity_activity",
                "cybersecurity_employers",
            ),
            proxy_evidence_categories=("hiring_activity", "early_career"),
            minimum_direct_evidence=1,
            minimum_total_evidence=2,
            proxy_only_confidence_cap=IntelligenceConfidence.LOW,
            unsupported_conditions=(
                "No cybersecurity role-family evidence or cybersecurity employer "
                "evidence is available.",
            ),
            weighting_rationale=(
                "Security-specific activity and employer presence carry most of the "
                "weight; broad hiring and early-career data are secondary proxies."
            ),
            public_safe_labels=CYBERSECURITY_LABELS,
        ),
        CareerGoal.DATA_SCIENCE: CareerGoalDefinition(
            goal=CareerGoal.DATA_SCIENCE,
            label="Data science",
            description=(
                "Use adjacent AI/cloud, product, technical, and early-career signals "
                "while explicitly limiting confidence because direct data-science "
                "role-family evidence is not collected."
            ),
            direct_signals=_label_text(
                DATA_SCIENCE_LABELS,
                ("data_science_role_activity", "data_science_internship"),
            ),
            direct_evidence_categories=(
                "data_science_role_activity",
                "data_science_internship",
            ),
            proxy_evidence_categories=(
                "ai_cloud_activity",
                "product_activity",
                "tech_signal",
                "early_career",
                "hiring_activity",
            ),
            minimum_direct_evidence=1,
            minimum_total_evidence=3,
            proxy_only_confidence_cap=IntelligenceConfidence.LIMITED,
            unsupported_conditions=(
                "The current canonical model does not collect direct data-science "
                "role-family evidence.",
                "Proxy-only adjacent AI, product, technical, and broad hiring "
                "evidence cannot support an authoritative data-science ranking.",
            ),
            weighting_rationale=(
                "Every currently scorable data-science component is a proxy; the "
                "definition preserves this limitation instead of treating adjacent "
                "AI or product evidence as direct role evidence."
            ),
            public_safe_labels=DATA_SCIENCE_LABELS,
            limitations=(
                "Direct data-science role-family facts are not collected in the "
                "current curated datasets.",
            ),
        ),
    }
)


GOAL_COMPONENT_WEIGHTS: Mapping[CareerGoal, Mapping[str, float]] = MappingProxyType(
    {
        CareerGoal.SOFTWARE_ENGINEERING: MappingProxyType(
            {
                "hiring_activity": 0.35,
                "tech_signal": 0.20,
                "early_career": 0.20,
                "internship": 0.10,
                "employer_presence": 0.15,
            }
        ),
        CareerGoal.PRODUCT_MANAGEMENT: MappingProxyType(
            {
                "product_activity": 0.40,
                "formal_programs": 0.25,
                "early_career": 0.20,
                "employer_presence": 0.15,
            }
        ),
        CareerGoal.AI_ML: MappingProxyType(
            {
                "ai_cloud_activity": 0.40,
                "ai_cloud_employers": 0.30,
                "tech_signal": 0.15,
                "internship": 0.15,
            }
        ),
        CareerGoal.CYBERSECURITY: MappingProxyType(
            {
                "cybersecurity_activity": 0.40,
                "cybersecurity_employers": 0.30,
                "hiring_activity": 0.15,
                "early_career": 0.15,
            }
        ),
        CareerGoal.DATA_SCIENCE: MappingProxyType(
            {
                "ai_cloud_activity": 0.30,
                "product_activity": 0.20,
                "tech_signal": 0.20,
                "early_career": 0.20,
                "hiring_activity": 0.10,
            }
        ),
    }
)


def career_goal_definitions() -> tuple[CareerGoalDefinition, ...]:
    return tuple(GOAL_DEFINITIONS[goal] for goal in CareerGoal)


def career_goal_definition(goal: CareerGoal | str) -> CareerGoalDefinition:
    return GOAL_DEFINITIONS[CareerGoal(goal)]


def goal_component_weights(goal: CareerGoal | str) -> Mapping[str, float]:
    return GOAL_COMPONENT_WEIGHTS[CareerGoal(goal)]


def classify_goal_evidence(
    goal: CareerGoal | str,
    evidence_categories: Iterable[str],
) -> GoalEvidenceClassification:
    selected_goal = CareerGoal(goal)
    definition = career_goal_definition(selected_goal)
    supplied = frozenset(evidence_categories)
    direct_lookup = frozenset(definition.direct_evidence_categories)
    proxy_lookup = frozenset(definition.proxy_evidence_categories)
    direct = tuple(
        category
        for category in definition.direct_evidence_categories
        if category in supplied
    )
    proxy = tuple(
        category
        for category in definition.proxy_evidence_categories
        if category in supplied
    )
    missing_direct = tuple(
        category
        for category in definition.direct_evidence_categories
        if category not in supplied
    )
    unknown = tuple(sorted(supplied - direct_lookup - proxy_lookup))
    total = len(direct) + len(proxy)
    return GoalEvidenceClassification(
        goal=selected_goal,
        evidence_basis=_evidence_basis(direct, proxy),
        direct_evidence_categories=direct,
        proxy_evidence_categories=proxy,
        missing_direct_evidence_categories=missing_direct,
        unknown_evidence_categories=unknown,
        direct_evidence_count=len(direct),
        proxy_evidence_count=len(proxy),
        total_evidence_count=total,
        minimum_direct_evidence=definition.minimum_direct_evidence,
        minimum_total_evidence=definition.minimum_total_evidence,
        meets_minimum_direct_evidence=(
            len(direct) >= definition.minimum_direct_evidence
        ),
        meets_minimum_total_evidence=total >= definition.minimum_total_evidence,
        proxy_only_confidence_cap=definition.proxy_only_confidence_cap,
        unsupported_conditions=definition.unsupported_conditions,
    )


def public_evidence_label(goal: CareerGoal | str, category: str) -> str:
    definition = career_goal_definition(goal)
    for label in definition.public_safe_labels:
        if label.code == category:
            return label.label
    return category.replace("_", " ")


def coerce_goal(goal: CareerGoal | str) -> CareerGoal:
    return CareerGoal(goal)


def _evidence_basis(
    direct: tuple[str, ...],
    proxy: tuple[str, ...],
) -> EvidenceBasis:
    if direct and proxy:
        return EvidenceBasis.DIRECT_AND_PROXY
    if direct:
        return EvidenceBasis.DIRECT
    if proxy:
        return EvidenceBasis.PROXY
    return EvidenceBasis.NO_QUALIFYING_EVIDENCE
