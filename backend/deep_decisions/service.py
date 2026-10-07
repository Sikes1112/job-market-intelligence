"""Layer 37 deep decision intelligence service.

The service attaches deeper domain intelligence to the Layer 36 decision graph.
It deliberately produces shared factors instead of separate compensation,
company, education, relocation, or timing recommendation engines.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_decisions.models import (
    CareerApplication,
    CareerDecision,
    CareerOutcome,
    DecisionOption,
    DecisionRecommendation,
    DecisionVersion,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.companies.models import Company
from backend.deep_decisions.models import (
    AdvisoryFinding,
    DecisionFactor,
    LongitudinalContextSnapshot,
    RecommendationEvolution,
    StrategicCareerReview,
)
from backend.deep_decisions.repository import DeepDecisionRepository
from backend.deep_decisions.schemas import (
    AdvisoryFindingView,
    DecisionFactorView,
    DeepDecisionAnalysisRequest,
    DeepDecisionAnalysisView,
    FactorCategory,
    FactorConfidence,
    FactorDirection,
    FactorEvidenceKind,
    FactorFreshness,
    LongitudinalContextView,
    RecommendationEvolutionChangeType,
    RecommendationEvolutionView,
    StrategicCareerReviewView,
)
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.repository import UserRepository

DEFAULT_DOMAINS = frozenset(
    {
        "company",
        "compensation",
        "skill_gap",
        "education_roi",
        "relocation",
        "timing_pivot",
    }
)
TERMINAL_NEGATIVE_APPLICATION_STATES = {"rejected", "withdrawn", "declined"}
TERMINAL_POSITIVE_APPLICATION_STATES = {"offer", "accepted"}


class DeepDecisionNotFound(LookupError):
    pass


class DeepDecisionValidationError(ValueError):
    def __init__(self, message: str, *, code: str = "DEEP_DECISION_VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


class DeepDecisionService:
    def __init__(
        self,
        session: Session,
        repository: DeepDecisionRepository,
        decision_repository: CareerDecisionRepository,
        user_repository: UserRepository,
    ) -> None:
        self._session = session
        self._repo = repository
        self._decision_repo = decision_repository
        self._user_repo = user_repository
        self._geographic_resolver = GeographicResolver(RegionRepository(session))

    def generate_analysis(
        self,
        user_id: str,
        decision_id: str,
        request: DeepDecisionAnalysisRequest | None = None,
    ) -> DeepDecisionAnalysisView:
        self._ensure_user(user_id)
        decision = self._owned_decision(user_id, decision_id)
        request = request or DeepDecisionAnalysisRequest()
        domains = set(request.include_domains or DEFAULT_DOMAINS)
        unsupported = domains - DEFAULT_DOMAINS
        if unsupported:
            raise DeepDecisionValidationError(
                f"unsupported deep decision domain(s): {', '.join(sorted(unsupported))}",
                code="UNSUPPORTED_DEEP_DECISION_DOMAIN",
            )
        now = request.window_end or _now()
        window_start = request.window_start or (now - timedelta(days=90))
        options = self._decision_repo.list_options(decision.decision_id)
        recommendations = self._decision_repo.list_recommendations(decision.decision_id)
        versions = self._decision_repo.list_versions(decision.decision_id)
        applications = self._decision_repo.list_applications(
            user_id, decision_id=decision.decision_id, limit=500
        )
        outcomes = self._decision_repo.list_outcomes(
            user_id,
            decision_id=decision.decision_id,
            since=window_start,
            until=now,
            limit=500,
        )
        context = (
            self._decision_repo.get_context(decision.current_context_snapshot_id)
            if decision.current_context_snapshot_id
            else None
        )
        context_payload = deepcopy(context.context_payload) if context else {}

        factor_rows = self._produce_factors(
            user_id=user_id,
            decision=decision,
            options=options,
            current_recommendation=recommendations[0] if recommendations else None,
            context_payload=context_payload,
            context_snapshot_id=context.context_snapshot_id if context else None,
            domains=domains,
            now=now,
            applications=applications,
            outcomes=outcomes,
        )
        for row in factor_rows:
            self._repo.add(row)

        longitudinal = self._create_longitudinal_context(
            user_id=user_id,
            decision=decision,
            options=options,
            recommendations=recommendations,
            versions=versions,
            applications=applications,
            outcomes=outcomes,
            context_payload=context_payload,
            window_start=window_start,
            window_end=now,
        )
        self._repo.add(longitudinal)

        evolution = self._create_recommendation_evolution(
            user_id=user_id,
            decision=decision,
            recommendations=recommendations,
            versions=versions,
            factors=factor_rows,
            now=now,
        )
        if evolution is not None:
            self._repo.add(evolution)

        findings = self._produce_findings(
            user_id=user_id,
            decision=decision,
            options=options,
            recommendations=recommendations,
            applications=applications,
            outcomes=outcomes,
            context_payload=context_payload,
            factors=factor_rows,
            window_start=window_start,
            window_end=now,
        )
        for row in findings:
            self._repo.add(row)

        self._repo.flush()
        review = self._create_strategic_review(
            user_id=user_id,
            decision=decision,
            longitudinal=longitudinal,
            recommendations=recommendations,
            evolution=evolution,
            findings=findings,
            applications=applications,
            outcomes=outcomes,
            context_payload=context_payload,
            factors=factor_rows,
            window_start=window_start,
            window_end=now,
        )
        self._repo.add(review)
        self._repo.flush()

        return DeepDecisionAnalysisView(
            decision_id=decision.decision_id,
            factors=tuple(self._factor_view(row) for row in factor_rows),
            longitudinal_context=self._longitudinal_view(longitudinal),
            recommendation_evolution=self._evolution_view(evolution) if evolution else None,
            advisory_findings=tuple(self._finding_view(row) for row in findings),
            strategic_review=self._review_view(review),
        )

    def latest_analysis(self, user_id: str, decision_id: str) -> DeepDecisionAnalysisView:
        self._ensure_user(user_id)
        decision = self._owned_decision(user_id, decision_id)
        longitudinal = self._repo.latest_longitudinal_context(user_id, decision.decision_id)
        review = self._repo.latest_strategic_review(user_id, decision_id=decision.decision_id)
        if longitudinal is None or review is None:
            raise DeepDecisionNotFound("Deep decision analysis not found.")
        factors = self._repo.list_factors(user_id, decision.decision_id)
        evolution = self._repo.latest_evolution(user_id, decision.decision_id)
        findings = self._repo.list_findings(user_id, decision_id=decision.decision_id)
        return DeepDecisionAnalysisView(
            decision_id=decision.decision_id,
            factors=tuple(self._factor_view(row) for row in factors[:500]),
            longitudinal_context=self._longitudinal_view(longitudinal),
            recommendation_evolution=self._evolution_view(evolution) if evolution else None,
            advisory_findings=tuple(self._finding_view(row) for row in findings[:100]),
            strategic_review=self._review_view(review),
        )

    def list_strategic_reviews(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> tuple[StrategicCareerReviewView, ...]:
        self._ensure_user(user_id)
        if decision_id is not None:
            self._owned_decision(user_id, decision_id)
        return tuple(
            self._review_view(row)
            for row in self._repo.list_strategic_reviews(
                user_id, decision_id=decision_id, limit=limit
            )
        )

    def _produce_factors(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        options: list[DecisionOption],
        current_recommendation: DecisionRecommendation | None,
        context_payload: dict[str, Any],
        context_snapshot_id: str | None,
        domains: set[str],
        now: datetime,
        applications: list[CareerApplication],
        outcomes: list[CareerOutcome],
    ) -> list[DecisionFactor]:
        rows: list[DecisionFactor] = []
        for option in options:
            scenario = option.scenario or {}
            if "company" in domains:
                rows.extend(
                    self._company_factors(
                        user_id,
                        decision,
                        option,
                        scenario,
                        current_recommendation,
                        context_snapshot_id,
                        now,
                    )
                )
            if "compensation" in domains:
                rows.extend(
                    self._compensation_factors(
                        user_id,
                        decision,
                        option,
                        scenario,
                        current_recommendation,
                        context_snapshot_id,
                        now,
                    )
                )
            if "skill_gap" in domains:
                rows.extend(
                    self._skill_gap_factors(
                        user_id,
                        decision,
                        option,
                        scenario,
                        current_recommendation,
                        context_snapshot_id,
                        context_payload,
                        now,
                    )
                )
            if "education_roi" in domains:
                rows.extend(
                    self._education_factors(
                        user_id,
                        decision,
                        option,
                        scenario,
                        current_recommendation,
                        context_snapshot_id,
                        now,
                    )
                )
            if "relocation" in domains:
                rows.extend(
                    self._relocation_factors(
                        user_id,
                        decision,
                        option,
                        scenario,
                        current_recommendation,
                        context_snapshot_id,
                        now,
                    )
                )
        if "timing_pivot" in domains:
            rows.extend(
                self._timing_factors(
                    user_id,
                    decision,
                    current_recommendation,
                    context_snapshot_id,
                    now,
                    applications,
                    outcomes,
                )
            )
        return rows

    def _company_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        scenario: dict[str, Any],
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        now: datetime,
    ) -> list[DecisionFactor]:
        company_ids = _strings(
            scenario.get("company_ids") or scenario.get("companies") or scenario.get("company_id")
        )
        region_ids = _strings(
            scenario.get("region_ids") or scenario.get("regions") or scenario.get("location")
        )
        rows: list[DecisionFactor] = []
        if not company_ids:
            profile = _string(scenario.get("company_profile"))
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="company",
                    category=FactorCategory.UNCERTAINTY,
                    key="company_specific_evidence",
                    label="Company-specific evidence",
                    direction=FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.LOW if profile else FactorConfidence.UNKNOWN,
                    evidence_kind=FactorEvidenceKind.PROXY
                    if profile
                    else FactorEvidenceKind.UNAVAILABLE,
                    evidence_strength="weak" if profile else "unavailable",
                    explanation=(
                        "Company profile text is available, but no canonical company id "
                        "was supplied."
                        if profile
                        else "No company id is present in this scenario."
                    ),
                    caveats=(
                        "Do not infer workplace quality or sentiment without supported evidence.",
                    ),
                    raw_value={"company_profile": profile} if profile else None,
                    now=now,
                )
            )
            return rows
        for company_id in company_ids:
            company = self._session.get(Company, company_id)
            presence = self._company_presence(company_id, region_ids)
            hiring = self._company_hiring(company_id, region_ids)
            entry = self._company_entry(company_id, region_ids)
            evidence_count = int(bool(company)) + len(presence) + len(hiring) + len(entry)
            stale_sources = any(_is_stale(row, now) for row in [*hiring, *entry])
            confidence = FactorConfidence.MEDIUM if evidence_count >= 2 else FactorConfidence.LOW
            evidence_kind = (
                FactorEvidenceKind.DIRECT
                if evidence_count >= 2
                else FactorEvidenceKind.PROXY
                if evidence_count == 1
                else FactorEvidenceKind.UNAVAILABLE
            )
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="company",
                    category=FactorCategory.BENEFIT
                    if evidence_count
                    else FactorCategory.UNCERTAINTY,
                    key="company_evidence",
                    label=f"Company evidence for {company_id}",
                    direction=FactorDirection.POSITIVE
                    if evidence_count >= 2
                    else FactorDirection.UNKNOWN,
                    confidence=confidence if evidence_count else FactorConfidence.UNKNOWN,
                    evidence_kind=evidence_kind,
                    evidence_strength="moderate"
                    if evidence_count >= 2
                    else "weak"
                    if evidence_count == 1
                    else "unavailable",
                    source_type="company",
                    source_id=company_id,
                    normalized_value={
                        "presence_rows": len(presence),
                        "hiring_rows": len(hiring),
                        "entry_level_rows": len(entry),
                    },
                    explanation=(
                        "Canonical company, presence, hiring, or early-career evidence "
                        "supports this scenario."
                        if evidence_count
                        else "No canonical company evidence is available for this scenario."
                    ),
                    caveats=(
                        ()
                        if evidence_count >= 2
                        else ("Company fit is limited to unavailable or weak evidence.",)
                    ),
                    freshness_status=FactorFreshness.STALE
                    if stale_sources
                    else FactorFreshness.UNKNOWN,
                    now=now,
                )
            )
            rows.extend(
                self._role_family_company_factors(
                    user_id,
                    decision,
                    option,
                    recommendation,
                    context_snapshot_id,
                    company_id,
                    hiring,
                    now,
                )
            )
        return rows

    def _role_family_company_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        company_id: str,
        hiring: list[CompanyRegionHiring],
        now: datetime,
    ) -> list[DecisionFactor]:
        role_counts: Counter[str] = Counter()
        for row in hiring:
            summary = row.role_family_summary or {}
            if isinstance(summary, dict):
                role_counts.update({str(key): int(value or 0) for key, value in summary.items()})
        stale_sources = any(_is_stale(row, now) for row in hiring)
        if not role_counts:
            return [
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="company",
                    category=FactorCategory.UNCERTAINTY,
                    key="role_family_strength",
                    label=f"Role-family strength for {company_id}",
                    direction=FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.UNKNOWN,
                    evidence_kind=FactorEvidenceKind.UNAVAILABLE,
                    evidence_strength="unavailable",
                    source_type="company_region_hiring",
                    source_id=company_id,
                    explanation=(
                        "No role-family hiring summary is available for this company scenario."
                    ),
                    now=now,
                )
            ]
        return [
            self._factor(
                user_id=user_id,
                decision=decision,
                option=option,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="company",
                category=FactorCategory.BENEFIT,
                key="role_family_strength",
                label=f"Role-family strength for {company_id}",
                direction=FactorDirection.POSITIVE,
                confidence=FactorConfidence.MEDIUM,
                evidence_kind=FactorEvidenceKind.DERIVED,
                evidence_strength="moderate",
                source_type="company_region_hiring",
                source_id=company_id,
                normalized_value={"role_family_counts": dict(role_counts)},
                explanation=(
                    "Role-family concentration is derived from canonical company-region "
                    "hiring evidence."
                ),
                freshness_status=FactorFreshness.STALE
                if stale_sources
                else FactorFreshness.UNKNOWN,
                now=now,
            )
        ]

    def _compensation_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        scenario: dict[str, Any],
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        now: datetime,
    ) -> list[DecisionFactor]:
        known_values = {
            "base_salary": _number(scenario.get("base_salary")),
            "total_compensation": _number(scenario.get("total_compensation") or scenario.get("tc")),
            "compensation_target": _number(scenario.get("compensation_target")),
        }
        present = {key: value for key, value in known_values.items() if value is not None}
        rows: list[DecisionFactor] = []
        if not present:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="compensation",
                    category=FactorCategory.UNCERTAINTY,
                    key="compensation_evidence",
                    label="Compensation evidence",
                    direction=FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.UNKNOWN,
                    evidence_kind=FactorEvidenceKind.UNAVAILABLE,
                    evidence_strength="unavailable",
                    explanation=(
                        "No user-entered, sourced, or estimated compensation value is "
                        "present for this scenario."
                    ),
                    caveats=("Missing compensation is unknown, not negative evidence.",),
                    now=now,
                )
            )
            return rows
        source_kind = _string(scenario.get("compensation_source")) or "user_entered"
        evidence_kind = (
            FactorEvidenceKind.DIRECT if source_kind == "user_entered" else FactorEvidenceKind.PROXY
        )
        rows.append(
            self._factor(
                user_id=user_id,
                decision=decision,
                option=option,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="compensation",
                category=FactorCategory.BENEFIT,
                key="nominal_compensation",
                label="Nominal compensation",
                direction=FactorDirection.POSITIVE,
                confidence=FactorConfidence.MEDIUM
                if evidence_kind is FactorEvidenceKind.DIRECT
                else FactorConfidence.LOW,
                evidence_kind=evidence_kind,
                evidence_strength="moderate"
                if evidence_kind is FactorEvidenceKind.DIRECT
                else "weak",
                normalized_value=present,
                raw_value={"source": source_kind, "benefits": scenario.get("benefits")},
                explanation="Compensation is evaluated as one factor, not the whole decision.",
                caveats=(
                    ()
                    if scenario.get("benefits")
                    else ("Benefit data is missing or not quantified.",)
                ),
                now=now,
            )
        )
        values = list(present.values())
        if len(values) > 1 and max(values) - min(values) > 50_000:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="compensation",
                    category=FactorCategory.RISK,
                    key="conflicting_compensation_sources",
                    label="Conflicting compensation evidence",
                    direction=FactorDirection.NEGATIVE,
                    confidence=FactorConfidence.LOW,
                    evidence_kind=FactorEvidenceKind.CONFLICTING,
                    evidence_strength="conflicting",
                    normalized_value=present,
                    explanation=(
                        "Multiple compensation values differ materially; treat "
                        "compensation conclusions as uncertain."
                    ),
                    now=now,
                )
            )
        return rows

    def _skill_gap_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        scenario: dict[str, Any],
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        context_payload: dict[str, Any],
        now: datetime,
    ) -> list[DecisionFactor]:
        current_skills = _tokens(context_payload.get("skills"))
        target_skills = _tokens(
            scenario.get("required_skills")
            or scenario.get("target_skills")
            or scenario.get("skills")
            or scenario.get("skill_requirements")
        )
        if not target_skills:
            return [
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="skill_gap",
                    category=FactorCategory.UNCERTAINTY,
                    key="target_skill_evidence",
                    label="Target skill evidence",
                    direction=FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.UNKNOWN,
                    evidence_kind=FactorEvidenceKind.UNAVAILABLE,
                    evidence_strength="unavailable",
                    explanation="The scenario has no target skill requirements.",
                    now=now,
                )
            ]
        transferable = sorted(current_skills & target_skills)
        absent = sorted(target_skills - current_skills)
        return [
            self._factor(
                user_id=user_id,
                decision=decision,
                option=option,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="skill_gap",
                category=FactorCategory.BENEFIT if transferable else FactorCategory.UNCERTAINTY,
                key="transferable_skills",
                label="Transferable skills",
                direction=FactorDirection.POSITIVE if transferable else FactorDirection.UNKNOWN,
                confidence=FactorConfidence.MEDIUM if transferable else FactorConfidence.LOW,
                evidence_kind=FactorEvidenceKind.DIRECT
                if transferable
                else FactorEvidenceKind.UNAVAILABLE,
                evidence_strength="moderate" if transferable else "weak",
                normalized_value={"skills": transferable},
                explanation=(
                    "Career Identity skills overlap with target scenario requirements."
                    if transferable
                    else (
                        "No overlap is visible from Career Identity, but absence is not "
                        "confirmed lack."
                    )
                ),
                caveats=(() if current_skills else ("Career Identity skill evidence is sparse.",)),
                now=now,
            ),
            self._factor(
                user_id=user_id,
                decision=decision,
                option=option,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="skill_gap",
                category=FactorCategory.RISK if absent else FactorCategory.BENEFIT,
                key="likely_skill_gaps",
                label="Likely skill gaps",
                direction=FactorDirection.NEGATIVE if absent else FactorDirection.POSITIVE,
                confidence=FactorConfidence.LOW if absent else FactorConfidence.MEDIUM,
                evidence_kind=FactorEvidenceKind.INFERRED if absent else FactorEvidenceKind.DIRECT,
                evidence_strength="weak" if absent else "moderate",
                normalized_value={"skills": absent},
                explanation=(
                    "Target skills are not visible in Career Identity; this is a likely "
                    "gap, not a confirmed absence."
                    if absent
                    else (
                        "Visible Career Identity skills cover the supplied target skill "
                        "requirements."
                    )
                ),
                caveats=("Do not treat missing profile skills as confirmed lack.",)
                if absent
                else (),
                now=now,
            ),
        ]

    def _education_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        scenario: dict[str, Any],
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        now: datetime,
    ) -> list[DecisionFactor]:
        education_type = _string(scenario.get("education_type") or scenario.get("credential_type"))
        credential = _string(scenario.get("credential") or scenario.get("program_name"))
        cost = _number(
            scenario.get("education_cost") or scenario.get("program_cost") or scenario.get("cost")
        )
        months = _number(scenario.get("time_months") or scenario.get("duration_months"))
        skill_reduction = _strings(
            scenario.get("skills_taught") or scenario.get("skill_gap_reduction")
        )
        if not any((education_type, credential, cost, months, skill_reduction)):
            return []
        rows = [
            self._factor(
                user_id=user_id,
                decision=decision,
                option=option,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="education_roi",
                category=FactorCategory.COST if cost is not None else FactorCategory.UNCERTAINTY,
                key="education_cost",
                label="Education cost",
                direction=FactorDirection.NEGATIVE if cost else FactorDirection.UNKNOWN,
                confidence=FactorConfidence.MEDIUM
                if cost is not None
                else FactorConfidence.UNKNOWN,
                evidence_kind=FactorEvidenceKind.DIRECT
                if cost is not None
                else FactorEvidenceKind.UNAVAILABLE,
                evidence_strength="moderate" if cost is not None else "unavailable",
                normalized_value={"cost": cost} if cost is not None else None,
                raw_value={"education_type": education_type, "credential": credential},
                explanation=(
                    "Credential cost is considered alongside role fit, skill-gap "
                    "reduction, and opportunity cost."
                ),
                caveats=(
                    "High cost without supported upside should not be treated as "
                    "automatically worthwhile.",
                )
                if cost and cost > 20_000
                else (),
                now=now,
            )
        ]
        if months is not None:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="education_roi",
                    category=FactorCategory.TIME,
                    key="education_time",
                    label="Education time commitment",
                    direction=FactorDirection.NEGATIVE if months >= 6 else FactorDirection.MIXED,
                    confidence=FactorConfidence.MEDIUM,
                    evidence_kind=FactorEvidenceKind.DIRECT,
                    evidence_strength="moderate",
                    normalized_value={"months": months},
                    explanation="Time commitment and opportunity cost affect credential ROI.",
                    now=now,
                )
            )
        if skill_reduction:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="education_roi",
                    category=FactorCategory.BENEFIT,
                    key="skill_gap_reduction",
                    label="Skill-gap reduction",
                    direction=FactorDirection.POSITIVE,
                    confidence=FactorConfidence.LOW,
                    evidence_kind=FactorEvidenceKind.PROXY,
                    evidence_strength="weak",
                    normalized_value={"skills": skill_reduction},
                    explanation=(
                        "Program content may reduce stated target skill gaps, but "
                        "outcome evidence is not assumed."
                    ),
                    now=now,
                )
            )
        return rows

    def _relocation_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption,
        scenario: dict[str, Any],
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        now: datetime,
    ) -> list[DecisionFactor]:
        region_ids = _strings(
            scenario.get("region_ids") or scenario.get("regions") or scenario.get("location")
        )
        relocation = bool(scenario.get("relocation_required") or scenario.get("relocation"))
        remote = _string(scenario.get("work_arrangement")) == "remote"
        cost_of_living = _number(scenario.get("cost_of_living_index") or scenario.get("col_index"))
        if not region_ids and not relocation and not remote:
            return []
        rows: list[DecisionFactor] = []
        for region_reference in region_ids:
            geographic_resolution = self._geographic_resolver.resolve(region_reference)
            region_id = geographic_resolution.region_id
            score = (
                self._session.execute(
                    select(RegionMarketScore)
                    .where(RegionMarketScore.region_id == region_id)
                    .limit(1)
                ).scalar_one_or_none()
                if region_id is not None
                else None
            )
            region_exists = (
                region_id is not None and self._session.get(Region, region_id) is not None
            )
            factor_source_id = region_id or region_reference
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="relocation",
                    category=FactorCategory.BENEFIT if score else FactorCategory.UNCERTAINTY,
                    key="regional_market_opportunity",
                    label=f"Regional market opportunity for {region_reference}",
                    direction=FactorDirection.POSITIVE if score else FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.MEDIUM
                    if score
                    else FactorConfidence.LOW
                    if region_exists
                    else FactorConfidence.UNKNOWN,
                    evidence_kind=FactorEvidenceKind.DIRECT
                    if score
                    else FactorEvidenceKind.PROXY
                    if region_exists
                    else FactorEvidenceKind.UNAVAILABLE,
                    evidence_strength="moderate"
                    if score
                    else "weak"
                    if region_exists
                    else "unavailable",
                    source_type="region_market_score" if score else "region",
                    source_id=factor_source_id,
                    normalized_value={
                        "objective_opportunity_score": score.objective_opportunity_score,
                        "canonical_region_id": region_id,
                        "historical_region_reference": region_reference,
                    }
                    if score
                    else {
                        "canonical_region_id": region_id,
                        "historical_region_reference": region_reference,
                        "resolution_status": geographic_resolution.status,
                    },
                    explanation=(
                        "Relocation scenario references an existing regional market score."
                        if score
                        else (
                            "Regional evidence is sparse; relocation confidence should "
                            "remain limited."
                        )
                    ),
                    now=now,
                )
            )
        if relocation or cost_of_living is not None or remote:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=option,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="relocation",
                    category=FactorCategory.COST
                    if relocation or cost_of_living
                    else FactorCategory.REVERSIBILITY,
                    key="relocation_friction",
                    label="Relocation friction",
                    direction=FactorDirection.NEGATIVE
                    if relocation
                    else FactorDirection.POSITIVE
                    if remote
                    else FactorDirection.UNKNOWN,
                    confidence=FactorConfidence.MEDIUM
                    if relocation or remote
                    else FactorConfidence.LOW,
                    evidence_kind=FactorEvidenceKind.DIRECT
                    if relocation or remote
                    else FactorEvidenceKind.PROXY,
                    evidence_strength="moderate" if relocation or remote else "weak",
                    normalized_value={
                        "relocation_required": relocation,
                        "remote": remote,
                        "cost_of_living_index": cost_of_living,
                    },
                    explanation=(
                        "Relocation and remote constraints are evaluated as tradeoffs "
                        "with opportunity and compensation."
                    ),
                    caveats=("Cost-of-living evidence is missing or user-entered only.",)
                    if cost_of_living is None and relocation
                    else (),
                    now=now,
                )
            )
        return rows

    def _timing_factors(
        self,
        user_id: str,
        decision: CareerDecision,
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        now: datetime,
        applications: list[CareerApplication],
        outcomes: list[CareerOutcome],
    ) -> list[DecisionFactor]:
        negative_count = sum(
            1 for row in applications if row.status in TERMINAL_NEGATIVE_APPLICATION_STATES
        )
        positive_count = sum(
            1 for row in applications if row.status in TERMINAL_POSITIVE_APPLICATION_STATES
        )
        rows = [
            self._factor(
                user_id=user_id,
                decision=decision,
                option=None,
                recommendation=recommendation,
                context_snapshot_id=context_snapshot_id,
                domain="timing_pivot",
                category=FactorCategory.EVIDENCE_STRENGTH,
                key="application_sample_size",
                label="Application sample size",
                direction=FactorDirection.NEUTRAL
                if len(applications) >= 3
                else FactorDirection.UNKNOWN,
                confidence=FactorConfidence.MEDIUM
                if len(applications) >= 3
                else FactorConfidence.LOW,
                evidence_kind=FactorEvidenceKind.DIRECT
                if applications
                else FactorEvidenceKind.UNAVAILABLE,
                evidence_strength="moderate"
                if len(applications) >= 3
                else "weak"
                if applications
                else "unavailable",
                normalized_value={
                    "applications": len(applications),
                    "negative_terminal": negative_count,
                    "positive_terminal": positive_count,
                },
                explanation=(
                    "Application history is large enough for cautious timing and pivot review."
                    if len(applications) >= 3
                    else (
                        "Application history is too sparse for a strong timing or pivot conclusion."
                    )
                ),
                caveats=("No universal rejection threshold is treated as decisive.",),
                now=now,
            )
        ]
        if outcomes:
            rows.append(
                self._factor(
                    user_id=user_id,
                    decision=decision,
                    option=None,
                    recommendation=recommendation,
                    context_snapshot_id=context_snapshot_id,
                    domain="timing_pivot",
                    category=FactorCategory.BENEFIT if positive_count else FactorCategory.RISK,
                    key="recent_outcomes",
                    label="Recent outcomes",
                    direction=FactorDirection.POSITIVE if positive_count else FactorDirection.MIXED,
                    confidence=FactorConfidence.LOW,
                    evidence_kind=FactorEvidenceKind.DIRECT,
                    evidence_strength="weak",
                    normalized_value={"outcomes": len(outcomes)},
                    explanation=(
                        "Recent outcomes inform strategy review but do not automatically "
                        "redefine goals."
                    ),
                    now=now,
                )
            )
        return rows

    def _create_longitudinal_context(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        options: list[DecisionOption],
        recommendations: list[DecisionRecommendation],
        versions: list[DecisionVersion],
        applications: list[CareerApplication],
        outcomes: list[CareerOutcome],
        context_payload: dict[str, Any],
        window_start: datetime,
        window_end: datetime,
    ) -> LongitudinalContextSnapshot:
        prior_decisions = [
            row
            for row in self._decision_repo.list_decisions(user_id, limit=25)
            if row.decision_id != decision.decision_id
        ][:10]
        payload = {
            "explicit_intent": {
                "decision_title": decision.title,
                "decision_type": decision.decision_type,
                "priorities": deepcopy(decision.priorities or []),
                "constraints": deepcopy(decision.constraints or []),
                "role_preferences": deepcopy(context_payload.get("role_preferences")),
                "goals": deepcopy(context_payload.get("goals")),
            },
            "observed_behavior": {
                "applications": [_application_summary(row) for row in applications[:25]],
                "selected_option_id": decision.selected_option_id,
            },
            "prior_decisions": [
                {
                    "decision_id": row.decision_id,
                    "decision_type": row.decision_type,
                    "status": row.status,
                    "selected_option_id": row.selected_option_id,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in prior_decisions
            ],
            "system_recommendations": [
                _recommendation_summary(row) for row in recommendations[:10]
            ],
            "outcomes": [_outcome_summary(row) for row in outcomes[:25]],
            "decision_history": [
                {
                    "version_number": row.version_number,
                    "version_reason": row.version_reason,
                    "selected_option_id": row.selected_option_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in versions[-25:]
            ],
            "scenarios": [
                {
                    "option_id": row.option_id,
                    "title": row.title,
                    "status": row.status,
                    "scenario": deepcopy(row.scenario),
                }
                for row in options[:25]
            ],
        }
        evidence = {
            "bounded": True,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "record_limits": {
                "applications": 25,
                "outcomes": 25,
                "recommendations": 10,
                "decision_history": 25,
                "scenarios": 25,
                "prior_decisions": 10,
            },
            "safety": "Observed behavior is evidence and does not overwrite explicit intent.",
        }
        return LongitudinalContextSnapshot(
            longitudinal_context_id=_new_id("longitudinal_context"),
            user_id=user_id,
            decision_id=decision.decision_id,
            window_start=window_start,
            window_end=window_end,
            record_count=len(prior_decisions)
            + len(options)
            + len(recommendations)
            + len(versions)
            + len(applications)
            + len(outcomes),
            context_payload=payload,
            evidence_payload=evidence,
            generated_at=window_end,
        )

    def _create_recommendation_evolution(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        recommendations: list[DecisionRecommendation],
        versions: list[DecisionVersion],
        factors: list[DecisionFactor],
        now: datetime,
    ) -> RecommendationEvolution | None:
        if not recommendations:
            return None
        current = recommendations[0]
        previous = recommendations[1] if len(recommendations) > 1 else None
        changes: list[dict[str, Any]] = []
        change_type = RecommendationEvolutionChangeType.NONE
        confidence_before = previous.confidence if previous else None
        confidence_after = current.confidence
        if previous is None:
            changes.append(
                {"type": "initial", "message": "Only one recommendation snapshot exists."}
            )
            change_type = RecommendationEvolutionChangeType.NONE
        else:
            if previous.recommended_option_id != current.recommended_option_id:
                changes.append(
                    {
                        "type": "recommended_option_changed",
                        "before": previous.recommended_option_id,
                        "after": current.recommended_option_id,
                    }
                )
                change_type = RecommendationEvolutionChangeType.EVIDENCE_CHANGED
            if previous.confidence != current.confidence:
                changes.append(
                    {
                        "type": "confidence_changed",
                        "before": previous.confidence,
                        "after": current.confidence,
                    }
                )
                if change_type is RecommendationEvolutionChangeType.NONE:
                    change_type = RecommendationEvolutionChangeType.CONFIDENCE_CHANGED
            if previous.context_snapshot_id != current.context_snapshot_id:
                changes.append(
                    {
                        "type": "context_snapshot_changed",
                        "before": previous.context_snapshot_id,
                        "after": current.context_snapshot_id,
                    }
                )
                if _has_identity_update_after(versions, previous.generated_at):
                    change_type = RecommendationEvolutionChangeType.CAREER_IDENTITY_CHANGED
        stale_factor_count = sum(1 for factor in factors if factor.freshness_status == "stale")
        if stale_factor_count:
            changes.append({"type": "stale_evidence", "count": stale_factor_count})
            change_type = RecommendationEvolutionChangeType.STALE_PRIOR
        selected_differs = (
            decision.selected_option_id is not None
            and current.recommended_option_id is not None
            and decision.selected_option_id != current.recommended_option_id
        )
        if selected_differs:
            changes.append(
                {
                    "type": "user_choice_differs_from_recommendation",
                    "selected_option_id": decision.selected_option_id,
                    "recommended_option_id": current.recommended_option_id,
                }
            )
            if change_type is RecommendationEvolutionChangeType.NONE:
                change_type = RecommendationEvolutionChangeType.USER_CHANGED
        return RecommendationEvolution(
            evolution_id=_new_id("recommendation_evolution"),
            user_id=user_id,
            decision_id=decision.decision_id,
            previous_recommendation_id=previous.recommendation_id if previous else None,
            current_recommendation_id=current.recommendation_id,
            change_type=change_type.value,
            meaningful_changes=changes,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            evidence_basis={
                "uses_recommendation_snapshots": True,
                "prior_recommendations_are_not_independent_evidence": True,
            },
            uncertainty="low" if previous else "medium",
            explanation=(
                "Recommendation evolution compares persisted snapshots without treating "
                "repeated recommendations as new evidence."
            ),
            generated_at=now,
        )

    def _produce_findings(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        options: list[DecisionOption],
        recommendations: list[DecisionRecommendation],
        applications: list[CareerApplication],
        outcomes: list[CareerOutcome],
        context_payload: dict[str, Any],
        factors: list[DecisionFactor],
        window_start: datetime,
        window_end: datetime,
    ) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []
        role_preferences = _tokens(context_payload.get("role_preferences"))
        application_roles = _tokens([row.role_title for row in applications if row.role_title])
        if (
            role_preferences
            and application_roles
            and not (role_preferences & application_roles)
            and len(applications) >= 2
        ):
            findings.append(
                self._finding(
                    user_id=user_id,
                    decision=decision,
                    finding_type="stated_goal_behavior_mismatch",
                    severity="watch",
                    support_status="weakly_supported",
                    confidence="low",
                    uncertainty="medium",
                    window_start=window_start,
                    window_end=window_end,
                    affected_goal=", ".join(sorted(role_preferences)),
                    supporting_evidence=[
                        {"type": "explicit_intent", "role_preferences": sorted(role_preferences)},
                        {
                            "type": "observed_behavior",
                            "application_role_tokens": sorted(application_roles),
                        },
                    ],
                    counter_evidence=[],
                    explanation=(
                        "Observed applications differ from stated role preferences; "
                        "this is a strategy contradiction, not a rewrite of user intent."
                    ),
                    suggested_action=(
                        "Review whether the application mix still serves the stated target path."
                    ),
                )
            )
        rejection_count = sum(1 for row in applications if row.status == "rejected")
        if rejection_count >= 3:
            findings.append(
                self._finding(
                    user_id=user_id,
                    decision=decision,
                    finding_type="repeated_rejection_pattern",
                    severity="warning",
                    support_status="supported",
                    confidence="medium",
                    uncertainty="medium",
                    window_start=window_start,
                    window_end=window_end,
                    supporting_evidence=[
                        {"type": "application_status", "rejected_count": rejection_count}
                    ],
                    counter_evidence=[
                        {
                            "type": "sample_size_caveat",
                            "message": "No universal rejection threshold is decisive.",
                        }
                    ],
                    explanation=(
                        "Multiple rejected applications support reconsidering strategy, "
                        "positioning, or target fit."
                    ),
                    suggested_action=(
                        "Compare rejection pattern against skill-gap and target-market "
                        "factors before pivoting."
                    ),
                )
            )
        recommendation = recommendations[0] if recommendations else None
        if (
            recommendation is not None
            and decision.selected_option_id
            and recommendation.recommended_option_id
            and decision.selected_option_id != recommendation.recommended_option_id
        ):
            findings.append(
                self._finding(
                    user_id=user_id,
                    decision=decision,
                    finding_type="recommendation_repeatedly_ignored",
                    severity="info",
                    support_status="supported",
                    confidence="medium",
                    uncertainty="low",
                    window_start=window_start,
                    window_end=window_end,
                    supporting_evidence=[
                        {
                            "type": "choice_vs_recommendation",
                            "selected_option_id": decision.selected_option_id,
                            "recommended_option_id": recommendation.recommended_option_id,
                        }
                    ],
                    counter_evidence=[],
                    explanation=(
                        "The user selected a different option than the system "
                        "recommended. This is valid user agency and may reveal an "
                        "unstated priority."
                    ),
                    suggested_action=(
                        "Record the reason so future comparisons can separate system "
                        "fit from user preference."
                    ),
                )
            )
        comp_risk = [
            row
            for row in factors
            if row.domain == "compensation" and row.evidence_kind in {"unavailable", "conflicting"}
        ]
        relocation_risk = [
            row
            for row in factors
            if row.domain == "relocation" and row.evidence_strength in {"weak", "unavailable"}
        ]
        if comp_risk and relocation_risk:
            findings.append(
                self._finding(
                    user_id=user_id,
                    decision=decision,
                    finding_type="unrealistic_compensation_location_combination",
                    severity="watch",
                    support_status="weakly_supported",
                    confidence="low",
                    uncertainty="high",
                    window_start=window_start,
                    window_end=window_end,
                    supporting_evidence=[
                        {"type": "factor", "factor_id": row.factor_id, "domain": row.domain}
                        for row in [*comp_risk[:2], *relocation_risk[:2]]
                    ],
                    counter_evidence=[],
                    explanation=(
                        "Compensation or relocation assumptions rely on weak, missing, "
                        "or conflicting evidence."
                    ),
                    suggested_action=(
                        "Add concrete compensation and cost-of-living evidence before "
                        "relying on this scenario."
                    ),
                )
            )
        if len(applications) >= 3:
            regions = [row.region_id for row in applications if row.region_id]
            if regions and len(set(regions)) == 1:
                findings.append(
                    self._finding(
                        user_id=user_id,
                        decision=decision,
                        finding_type="low_diversity_application_strategy",
                        severity="watch",
                        support_status="weakly_supported",
                        confidence="low",
                        uncertainty="medium",
                        window_start=window_start,
                        window_end=window_end,
                        supporting_evidence=[
                            {
                                "type": "application_regions",
                                "regions": sorted(set(regions)),
                                "count": len(regions),
                            }
                        ],
                        counter_evidence=[],
                        explanation=(
                            "Application activity is concentrated in one region; this "
                            "may be intentional or may hide stronger adjacent markets."
                        ),
                        suggested_action=(
                            "Compare adjacent or remote scenarios before changing strategy."
                        ),
                    )
                )
        _ = options
        _ = outcomes
        return findings

    def _create_strategic_review(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        longitudinal: LongitudinalContextSnapshot,
        recommendations: list[DecisionRecommendation],
        evolution: RecommendationEvolution | None,
        findings: list[AdvisoryFinding],
        applications: list[CareerApplication],
        outcomes: list[CareerOutcome],
        context_payload: dict[str, Any],
        factors: list[DecisionFactor],
        window_start: datetime,
        window_end: datetime,
    ) -> StrategicCareerReview:
        confidence = (
            "medium"
            if factors and any(row.confidence in {"medium", "high"} for row in factors)
            else "low"
        )
        application_counts = Counter(row.status for row in applications)
        outcome_counts = Counter(row.outcome_type for row in outcomes)
        risk_factors = [
            {"factor_id": row.factor_id, "domain": row.domain, "label": row.label}
            for row in factors
            if row.category in {"risk", "uncertainty"}
            and row.direction in {"negative", "unknown", "mixed"}
        ][:10]
        suggested = [
            {"type": "finding", "message": row.suggested_action}
            for row in findings
            if row.suggested_action
        ]
        if not suggested and risk_factors:
            suggested.append(
                {
                    "type": "evidence_gap",
                    "message": "Clarify weak or missing evidence before changing strategy.",
                }
            )
        return StrategicCareerReview(
            strategic_review_id=_new_id("strategic_review"),
            user_id=user_id,
            decision_id=decision.decision_id,
            longitudinal_context_id=longitudinal.longitudinal_context_id,
            status="generated",
            window_start=window_start,
            window_end=window_end,
            goals={
                "decision_title": decision.title,
                "decision_type": decision.decision_type,
                "role_preferences": deepcopy(context_payload.get("role_preferences")),
                "goals": deepcopy(context_payload.get("goals")),
            },
            strategy_performance={
                "decision_status": decision.status,
                "selected_option_id": decision.selected_option_id,
                "recommendation_id": recommendations[0].recommendation_id
                if recommendations
                else None,
            },
            application_summary=dict(application_counts),
            outcome_summary=dict(outcome_counts),
            identity_changes=_identity_change_markers(recommendations),
            market_changes=[
                {"type": "factor", "domain": row.domain, "factor_id": row.factor_id}
                for row in factors
                if row.domain in {"company", "relocation"}
                and row.evidence_kind in {"direct", "derived"}
            ][:10],
            recommendation_changes=evolution.meaningful_changes if evolution else [],
            active_risks=risk_factors,
            blind_spots=[_finding_summary(row) for row in findings],
            suggested_next_actions=suggested[:10],
            confidence=confidence,
            uncertainty="medium"
            if any(row.confidence in {"low", "unknown"} for row in factors)
            else "low",
            generated_at=window_end,
        )

    def _factor(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        option: DecisionOption | None,
        recommendation: DecisionRecommendation | None,
        context_snapshot_id: str | None,
        domain: str,
        category: FactorCategory,
        key: str,
        label: str,
        direction: FactorDirection,
        confidence: FactorConfidence,
        evidence_kind: FactorEvidenceKind,
        evidence_strength: str,
        explanation: str,
        now: datetime,
        importance: int | None = None,
        uncertainty: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        normalized_value: dict[str, Any] | None = None,
        raw_value: dict[str, Any] | None = None,
        caveats: tuple[str, ...] = (),
        freshness_status: FactorFreshness = FactorFreshness.UNKNOWN,
        freshness_expires_at: datetime | None = None,
    ) -> DecisionFactor:
        return DecisionFactor(
            factor_id=_new_id("decision_factor"),
            user_id=user_id,
            decision_id=decision.decision_id,
            option_id=option.option_id if option else None,
            recommendation_id=recommendation.recommendation_id if recommendation else None,
            context_snapshot_id=context_snapshot_id,
            domain=domain,
            category=category.value,
            factor_key=key,
            label=label,
            normalized_value=deepcopy(normalized_value),
            raw_value=deepcopy(raw_value),
            direction=direction.value,
            importance=importance,
            confidence=confidence.value,
            uncertainty=uncertainty or _uncertainty_for_confidence(confidence),
            evidence_strength=evidence_strength,
            evidence_kind=evidence_kind.value,
            source_type=source_type,
            source_id=source_id,
            provenance={"generated_by": "layer_37_deep_decision_intelligence"},
            explanation=explanation,
            caveats=list(caveats),
            freshness_status=freshness_status.value,
            freshness_expires_at=freshness_expires_at,
            generated_at=now,
        )

    def _finding(
        self,
        *,
        user_id: str,
        decision: CareerDecision,
        finding_type: str,
        severity: str,
        support_status: str,
        confidence: str,
        uncertainty: str,
        window_start: datetime,
        window_end: datetime,
        supporting_evidence: list[dict[str, Any]],
        counter_evidence: list[dict[str, Any]],
        explanation: str,
        suggested_action: str | None,
        affected_goal: str | None = None,
    ) -> AdvisoryFinding:
        return AdvisoryFinding(
            advisory_finding_id=_new_id("advisory_finding"),
            user_id=user_id,
            decision_id=decision.decision_id,
            finding_type=finding_type,
            severity=severity,
            support_status=support_status,
            confidence=confidence,
            uncertainty=uncertainty,
            window_start=window_start,
            window_end=window_end,
            affected_goal=affected_goal,
            supporting_evidence=deepcopy(supporting_evidence),
            counter_evidence=deepcopy(counter_evidence),
            explanation=explanation,
            suggested_action=suggested_action,
            generated_at=window_end,
        )

    def _owned_decision(self, user_id: str, decision_id: str) -> CareerDecision:
        decision = self._decision_repo.get_decision(decision_id)
        if decision is None:
            raise DeepDecisionNotFound("Decision not found.")
        if decision.user_id != user_id:
            raise CrossUserAccessBlocked(user_id, decision.user_id)
        return decision

    def _ensure_user(self, user_id: str) -> None:
        if self._user_repo.get_user(user_id) is None:
            raise UserNotFound(user_id)

    def _company_presence(
        self,
        company_id: str,
        region_ids: list[str],
    ) -> list[CompanyRegionPresence]:
        stmt = select(CompanyRegionPresence).where(CompanyRegionPresence.company_id == company_id)
        if region_ids:
            stmt = stmt.where(CompanyRegionPresence.region_id.in_(region_ids))
        return list(self._session.execute(stmt.limit(25)).scalars())

    def _company_hiring(self, company_id: str, region_ids: list[str]) -> list[CompanyRegionHiring]:
        stmt = select(CompanyRegionHiring).where(CompanyRegionHiring.company_id == company_id)
        if region_ids:
            stmt = stmt.where(CompanyRegionHiring.region_id.in_(region_ids))
        return list(self._session.execute(stmt.limit(25)).scalars())

    def _company_entry(
        self, company_id: str, region_ids: list[str]
    ) -> list[CompanyRegionEntryLevel]:
        stmt = select(CompanyRegionEntryLevel).where(
            CompanyRegionEntryLevel.company_id == company_id
        )
        if region_ids:
            stmt = stmt.where(CompanyRegionEntryLevel.region_id.in_(region_ids))
        return list(self._session.execute(stmt.limit(25)).scalars())

    def _factor_view(self, row: DecisionFactor) -> DecisionFactorView:
        return DecisionFactorView(
            factor_id=row.factor_id,
            decision_id=row.decision_id,
            option_id=row.option_id,
            recommendation_id=row.recommendation_id,
            context_snapshot_id=row.context_snapshot_id,
            domain=row.domain,
            category=row.category,
            factor_key=row.factor_key,
            label=row.label,
            normalized_value=row.normalized_value,
            raw_value=row.raw_value,
            direction=row.direction,
            importance=row.importance,
            confidence=row.confidence,
            uncertainty=row.uncertainty,
            evidence_strength=row.evidence_strength,
            evidence_kind=row.evidence_kind,
            source_type=row.source_type,
            source_id=row.source_id,
            provenance=row.provenance,
            explanation=row.explanation,
            caveats=tuple(row.caveats or ()),
            freshness_status=row.freshness_status,
            freshness_expires_at=row.freshness_expires_at,
            generated_at=row.generated_at,
        )

    def _longitudinal_view(self, row: LongitudinalContextSnapshot) -> LongitudinalContextView:
        return LongitudinalContextView(
            longitudinal_context_id=row.longitudinal_context_id,
            decision_id=row.decision_id,
            window_start=row.window_start,
            window_end=row.window_end,
            record_count=row.record_count,
            context=row.context_payload,
            evidence=row.evidence_payload,
            generated_at=row.generated_at,
        )

    def _evolution_view(self, row: RecommendationEvolution) -> RecommendationEvolutionView:
        return RecommendationEvolutionView(
            evolution_id=row.evolution_id,
            decision_id=row.decision_id,
            previous_recommendation_id=row.previous_recommendation_id,
            current_recommendation_id=row.current_recommendation_id,
            change_type=row.change_type,
            meaningful_changes=tuple(row.meaningful_changes or ()),
            confidence_before=row.confidence_before,
            confidence_after=row.confidence_after,
            evidence_basis=row.evidence_basis,
            uncertainty=row.uncertainty,
            explanation=row.explanation,
            generated_at=row.generated_at,
        )

    def _finding_view(self, row: AdvisoryFinding) -> AdvisoryFindingView:
        return AdvisoryFindingView(
            advisory_finding_id=row.advisory_finding_id,
            decision_id=row.decision_id,
            finding_type=row.finding_type,
            severity=row.severity,
            support_status=row.support_status,
            confidence=row.confidence,
            uncertainty=row.uncertainty,
            window_start=row.window_start,
            window_end=row.window_end,
            affected_goal=row.affected_goal,
            supporting_evidence=tuple(row.supporting_evidence or ()),
            counter_evidence=tuple(row.counter_evidence or ()),
            explanation=row.explanation,
            suggested_action=row.suggested_action,
            acknowledged_at=row.acknowledged_at,
            dismissed_at=row.dismissed_at,
            generated_at=row.generated_at,
        )

    def _review_view(self, row: StrategicCareerReview) -> StrategicCareerReviewView:
        return StrategicCareerReviewView(
            strategic_review_id=row.strategic_review_id,
            decision_id=row.decision_id,
            longitudinal_context_id=row.longitudinal_context_id,
            status=row.status,
            window_start=row.window_start,
            window_end=row.window_end,
            goals=row.goals,
            strategy_performance=row.strategy_performance,
            application_summary=row.application_summary,
            outcome_summary=row.outcome_summary,
            identity_changes=tuple(row.identity_changes or ()),
            market_changes=tuple(row.market_changes or ()),
            recommendation_changes=tuple(row.recommendation_changes or ()),
            active_risks=tuple(row.active_risks or ()),
            blind_spots=tuple(row.blind_spots or ()),
            suggested_next_actions=tuple(row.suggested_next_actions or ()),
            confidence=row.confidence,
            uncertainty=row.uncertainty,
            generated_at=row.generated_at,
        )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _now() -> datetime:
    return datetime.now(UTC)


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for item in _strings(value):
        normalized = item.casefold().replace("_", " ").replace("-", " ")
        tokens.update(part for part in normalized.split() if part)
        if normalized:
            tokens.add(normalized)
    return tokens


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").replace("+", "").strip().casefold()
        multiplier = 1_000 if cleaned.endswith("k") else 1
        if cleaned.endswith("k"):
            cleaned = cleaned[:-1]
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
    return None


def _is_stale(row: Any, now: datetime) -> bool:
    expires_at = getattr(row, "freshness_expires_at", None)
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < now


def _uncertainty_for_confidence(confidence: FactorConfidence) -> str:
    if confidence is FactorConfidence.HIGH:
        return "low"
    if confidence is FactorConfidence.MEDIUM:
        return "medium"
    return "high"


def _application_summary(row: CareerApplication) -> dict[str, Any]:
    return {
        "application_id": row.application_id,
        "decision_id": row.decision_id,
        "option_id": row.option_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "role_title": row.role_title,
        "status": row.status,
        "updated_at": row.updated_at.isoformat(),
    }


def _outcome_summary(row: CareerOutcome) -> dict[str, Any]:
    return {
        "outcome_id": row.outcome_id,
        "decision_id": row.decision_id,
        "application_id": row.application_id,
        "outcome_type": row.outcome_type,
        "title": row.title,
        "occurred_at": row.occurred_at.isoformat(),
        "reflection_present": bool(row.reflection),
    }


def _recommendation_summary(row: DecisionRecommendation) -> dict[str, Any]:
    return {
        "recommendation_id": row.recommendation_id,
        "recommended_option_id": row.recommended_option_id,
        "status": row.recommendation_status,
        "confidence": row.confidence,
        "evidence_sufficiency": row.evidence_sufficiency,
        "context_snapshot_id": row.context_snapshot_id,
        "generated_at": row.generated_at.isoformat(),
    }


def _finding_summary(row: AdvisoryFinding) -> dict[str, Any]:
    return {
        "advisory_finding_id": row.advisory_finding_id,
        "finding_type": row.finding_type,
        "severity": row.severity,
        "support_status": row.support_status,
        "confidence": row.confidence,
        "suggested_action": row.suggested_action,
    }


def _identity_change_markers(recommendations: list[DecisionRecommendation]) -> list[dict[str, Any]]:
    context_ids = [row.context_snapshot_id for row in recommendations[:10]]
    if len(set(context_ids)) <= 1:
        return []
    return [{"type": "context_snapshot_changed", "context_snapshot_ids": context_ids}]


def _has_identity_update_after(versions: list[DecisionVersion], timestamp: datetime) -> bool:
    for row in versions:
        if row.created_at > timestamp and row.version_reason in {
            "updated",
            "reopened",
            "recommendation_generated",
        }:
            return True
    return False
