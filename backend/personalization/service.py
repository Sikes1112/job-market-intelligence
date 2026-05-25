"""Personalization service.

Reads canonical truth + Slice 10 stored scores via *repositories only*
(no upstream services, no scoring formulas, no entry-level recompute).
Returns a :class:`PersonalizedDiscoveryResult` in memory — nothing is
persisted.

Architectural rules pinned by the layer-isolation test:

* Forbidden imports: ``backend.scoring.service``,
  ``backend.entry_level.scoring``, every ``*.service`` module,
  queue/worker/scheduler/invalidation/event-router runtime, FastAPI/
  Celery/Redis/HTTP/scraping/NLP/ML/chart libraries.
* Allowed imports: domain models, the four upstream repositories
  (``CompanyRepository``, ``HiringRepository``, ``EntryLevelRepository``,
  ``RegionScoreRepository``), the geography repository, and the
  personalization domain modules above.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.market_coverage import (
    CoverageMetadataPayload,
    CoverageTier,
    build_region_coverage_metadata,
)
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.personalization.controls import (
    SCORING_WEIGHT_KEYS,
    ScoringWeightKey,
    coerce_scoring_weights,
    normalize_weights,
    weighted_overlay_score,
)
from backend.personalization.exceptions import (
    MissingRegionForPersonalization,
)
from backend.personalization.payloads import (
    CanonicalDefaultScoreSummary,
    PersonalizedCompanyEntry,
    PersonalizedDiscoveryBody,
    PersonalizedDiscoveryResult,
    PersonalizedRegionEntry,
    ScoringPreviewComponent,
    ScoringPreviewRegion,
    ScoringPreviewRequest,
    ScoringPreviewResult,
    UserPreferences,
)
from backend.personalization.scoring import (
    brand_fit_component,
    industry_fit_component,
    personal_company_score,
    personal_market_score,
    prestige_fit_component,
    role_fit_component,
)
from backend.scoring.repository import RegionScoreRepository


def _hiring_by_region_company(
    rows: list[CompanyRegionHiring],
) -> dict[tuple[str, str], CompanyRegionHiring]:
    return {(h.region_id, h.company_id): h for h in rows}


def _warning(
    warning_code: str,
    *,
    message: str,
    scope_type: str,
    scope_ref: str,
    severity: str = "medium",
) -> dict:
    return {
        "warning_code": warning_code,
        "severity": severity,
        "message": message,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
    }


class PersonalizationService:
    """Stateless overlay scorer.

    Construction is cheap; build per-request from the FastAPI dependency
    layer (Slice 12 pattern).
    """

    def __init__(
        self,
        *,
        session: Session,
        region_repo: RegionRepository,
        score_repo: RegionScoreRepository,
    ) -> None:
        self._session = session
        self._region_repo = region_repo
        self._score_repo = score_repo

    def discover(self, prefs: UserPreferences) -> PersonalizedDiscoveryResult:
        warnings: list[dict] = []

        # Validate every requested region exists. Honest error rather than
        # silently dropping unknown ids.
        regions: list = []
        for rid in prefs.region_ids:
            row = self._region_repo.get(rid)
            if row is None:
                raise MissingRegionForPersonalization(rid)
            regions.append(row)

        company_entries: list[PersonalizedCompanyEntry] = []
        region_entries: list[PersonalizedRegionEntry] = []

        for region in regions:
            present_companies = self._score_repo.list_present_companies_for_region(
                region.region_id
            )
            hiring_rows = self._score_repo.list_hiring_for_region(region.region_id)
            entry_level_rows = self._score_repo.list_entry_level_for_region(
                region.region_id
            )
            score_row = self._score_repo.get_score_by_region(region.region_id)
            hiring_index = _hiring_by_region_company(hiring_rows)
            coverage = _coverage_for_region(
                present_company_count=len(present_companies),
                presence_record_count=len(present_companies),
                hiring_rows=hiring_rows,
                entry_level_rows=entry_level_rows,
                has_region_score=score_row is not None,
            )

            if not present_companies:
                warnings.append(
                    _warning(
                        "no_present_companies_for_region",
                        message=(
                            "No present companies are available for this region; "
                            "personalized company ranking may be empty."
                        ),
                        scope_type="region",
                        scope_ref=region.region_id,
                    )
                )

            per_region_company_scores: list[float] = []
            for company in present_companies:
                hiring = hiring_index.get((region.region_id, company.company_id))
                role_family_summary = (
                    hiring.role_family_summary if hiring is not None else None
                )
                if hiring is None or role_family_summary is None:
                    warnings.append(
                        _warning(
                            "missing_role_family_summary",
                            message=(
                                "Role-family hiring summary is missing for this "
                                "company-region pair; role fit used fallback inputs."
                            ),
                            scope_type="company_region_pair",
                            scope_ref=f"{company.company_id}::{region.region_id}",
                        )
                    )

                role_fit, role_notes = role_fit_component(
                    role_targets=prefs.role_targets,
                    role_family_summary=role_family_summary,
                )
                industry_fit, industry_notes = industry_fit_component(
                    industry_preferences=prefs.industry_preferences,
                    sector_primary=company.sector_primary,
                    sector_secondary=company.sector_secondary,
                )
                prestige_fit, prestige_notes = prestige_fit_component(
                    preference=prefs.prestige_preference,
                    prestige_score=company.prestige_score,
                    is_major_tech=company.is_major_tech,
                    is_mag7=company.is_mag7,
                )
                brand_fit, brand_notes = brand_fit_component(
                    preference=prefs.brand_preference,
                    is_major_tech=company.is_major_tech,
                    is_mag7=company.is_mag7,
                )
                composite = personal_company_score(
                    role_fit=role_fit,
                    industry_fit=industry_fit,
                    prestige_fit=prestige_fit,
                    brand_fit=brand_fit,
                )
                match_notes = sorted(
                    role_notes + industry_notes + prestige_notes + brand_notes
                )
                company_entries.append(
                    PersonalizedCompanyEntry(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        region_id=region.region_id,
                        region_display_name=region.display_name,
                        personal_company_score=composite,
                        role_fit=role_fit,
                        industry_fit=industry_fit,
                        prestige_fit=prestige_fit,
                        brand_fit=brand_fit,
                        match_notes=match_notes,
                    )
                )
                per_region_company_scores.append(composite)

            market_score = personal_market_score(
                company_scores=per_region_company_scores
            )
            objective = (
                score_row.objective_opportunity_score
                if score_row is not None
                else None
            )
            region_match_notes: list[str] = []
            if objective is None:
                warnings.append(
                    _warning(
                        "region_score_missing",
                        message=(
                            "Objective region score is missing; personalized "
                            "region ranking omits objective score context."
                        ),
                        scope_type="region",
                        scope_ref=region.region_id,
                    )
                )
                region_match_notes.append("region_score_missing")
            if coverage.tier in {CoverageTier.TIER_3, CoverageTier.TIER_4}:
                warnings.append(
                    _warning(
                        "region_coverage_not_confident",
                        message=(
                            f"Region {region.region_id!r} is {coverage.tier.value}; "
                            "personalized ranking should not be treated as a "
                            "confident recommendation."
                        ),
                        scope_type="region",
                        scope_ref=region.region_id,
                    )
                )
                region_match_notes.append("region_coverage_not_confident")
            region_entries.append(
                PersonalizedRegionEntry(
                    region_id=region.region_id,
                    display_name=region.display_name,
                    personal_market_score=market_score,
                    objective_opportunity_score=objective,
                    coverage=coverage,
                    match_notes=region_match_notes,
                )
            )

        # Ranking: highest first; deterministic tiebreak on id.
        ranked_regions = sorted(
            region_entries,
            key=lambda r: (-r.personal_market_score, r.region_id),
        )
        ranked_companies = sorted(
            company_entries,
            key=lambda c: (
                -c.personal_company_score,
                c.region_id,
                c.company_id,
            ),
        )[: prefs.limit]

        return PersonalizedDiscoveryResult(
            personalized=PersonalizedDiscoveryBody(
                ranked_regions=ranked_regions,
                ranked_companies=ranked_companies,
            ),
            warnings=warnings,
        )

    def scoring_preview(self, request: ScoringPreviewRequest) -> ScoringPreviewResult:
        """Preview personalized region scores without writing any rows."""

        weights = coerce_scoring_weights(request.scoring_weights)
        raw_weights = weights.as_dict()
        default_normalized = normalize_weights(weights)
        warnings: list[dict[str, Any]] = []
        regions: list[ScoringPreviewRegion] = []

        for region_id in request.region_ids:
            region = self._region_repo.get(region_id)
            if region is None:
                raise MissingRegionForPersonalization(region_id)

            score_row = self._score_repo.get_score_by_region(region.region_id)
            present_companies = self._score_repo.list_present_companies_for_region(
                region.region_id
            )
            hiring_rows = self._score_repo.list_hiring_for_region(region.region_id)
            entry_level_rows = self._score_repo.list_entry_level_for_region(
                region.region_id
            )
            coverage = _coverage_for_region(
                present_company_count=len(present_companies),
                presence_record_count=len(present_companies),
                hiring_rows=hiring_rows,
                entry_level_rows=entry_level_rows,
                has_region_score=score_row is not None,
            )

            components: dict[ScoringWeightKey, float | None] = {
                "entry_level_access": (
                    score_row.early_career_accessibility_score
                    if score_row is not None
                    else None
                ),
                "hiring_density": (
                    score_row.live_market_score if score_row is not None else None
                ),
                "prestige": _average_known(
                    [company.prestige_score for company in present_companies]
                ),
                "industry_fit": _region_industry_fit(
                    present_companies,
                    request.industry_interests or [],
                ),
                "role_fit": _region_role_fit(
                    hiring_rows,
                    request.role_interests or [],
                ),
            }
            overlay_score, effective_weights = weighted_overlay_score(
                components,
                weights,
            )
            omitted = [
                key
                for key in SCORING_WEIGHT_KEYS
                if components[key] is None and raw_weights[key] > 0
            ]
            for key in omitted:
                warnings.append(
                    _warning(
                        "scoring_preview_component_missing",
                        message=(
                            f"Personalized scoring preview omitted {key!r} for "
                            f"{region.region_id!r} because no structured value was "
                            "available."
                        ),
                        scope_type="region",
                        scope_ref=region.region_id,
                        severity="low",
                    )
                )

            regions.append(
                ScoringPreviewRegion(
                    region_id=region.region_id,
                    display_name=region.display_name,
                    canonical_default_scores=CanonicalDefaultScoreSummary(
                        objective_opportunity_score=(
                            score_row.objective_opportunity_score
                            if score_row is not None
                            else None
                        ),
                        raw_total_score=(
                            score_row.raw_total_score if score_row is not None else None
                        ),
                        early_career_accessibility_score=components[
                            "entry_level_access"
                        ],
                        live_market_score=components["hiring_density"],
                        score_ruleset_version=(
                            score_row.score_ruleset_version
                            if score_row is not None
                            else None
                        ),
                    ),
                    coverage=coverage,
                    personalized_overlay_score=overlay_score,
                    components={
                        key: ScoringPreviewComponent(
                            value=components[key],
                            raw_weight=raw_weights[key],
                            effective_weight=effective_weights[key],
                            status="used" if components[key] is not None else "missing",
                            evidence=_preview_evidence(
                                key,
                                score_id=(
                                    score_row.region_score_id
                                    if score_row is not None
                                    else None
                                ),
                                company_count=len(present_companies),
                                hiring_count=len(hiring_rows),
                                has_preferences=bool(
                                    request.role_interests
                                    if key == "role_fit"
                                    else request.industry_interests
                                ),
                            ),
                        )
                        for key in SCORING_WEIGHT_KEYS
                    },
                    omitted_components=omitted,
                )
            )

        return ScoringPreviewResult(
            scoring_weights=weights,
            normalized_weights=default_normalized,
            regions=regions,
            warnings=warnings,
        )

    # The presence query is encapsulated here so the service stays
    # repository-only with respect to upstream domains.
    def _present_pairs_for_region(self, region_id: str) -> list[Company]:
        from backend.presence.models import CompanyRegionPresence

        stmt = (
            select(Company)
            .join(CompanyRegionPresence, Company.company_id == CompanyRegionPresence.company_id)
            .where(
                CompanyRegionPresence.region_id == region_id,
                CompanyRegionPresence.presence_status == "present",
            )
            .order_by(Company.company_id)
        )
        return list(self._session.execute(stmt).scalars())


def _average_known(values: list[float | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    if not known:
        return None
    return max(0.0, min(1.0, sum(known) / len(known)))


def _coverage_for_region(
    *,
    present_company_count: int,
    presence_record_count: int,
    hiring_rows: list[CompanyRegionHiring],
    entry_level_rows: list[CompanyRegionEntryLevel],
    has_region_score: bool,
) -> CoverageMetadataPayload:
    freshness_expires_at = _min_freshness_expires_at(
        [row.freshness_expires_at for row in hiring_rows]
        + [row.freshness_expires_at for row in entry_level_rows]
    )
    is_stale = (
        freshness_expires_at is not None
        and _ensure_aware(freshness_expires_at) <= datetime.now(UTC)
    )
    return build_region_coverage_metadata(
        present_company_count=present_company_count,
        presence_record_count=presence_record_count,
        hiring_record_count=len(hiring_rows),
        entry_level_record_count=len(entry_level_rows),
        has_region_score=has_region_score,
        freshness_expires_at_known=freshness_expires_at is not None,
        freshness_is_stale=is_stale,
        source_evidence_loaded=False,
    )


def _min_freshness_expires_at(values: list[datetime | None]) -> datetime | None:
    non_null = [_ensure_aware(value) for value in values if value is not None]
    return min(non_null) if non_null else None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _region_industry_fit(
    companies: list[Company],
    industry_preferences: list[str],
) -> float | None:
    if not companies:
        return None
    scores = [
        industry_fit_component(
            industry_preferences=industry_preferences,
            sector_primary=company.sector_primary,
            sector_secondary=company.sector_secondary,
        )[0]
        for company in companies
    ]
    return _average_known(scores)


def _region_role_fit(
    hiring_rows: list[CompanyRegionHiring],
    role_interests: list[str],
) -> float | None:
    rows_with_summary = [
        row for row in hiring_rows if row.role_family_summary is not None
    ]
    if not rows_with_summary:
        return 0.5 if not role_interests and hiring_rows else None
    scores = [
        role_fit_component(
            role_targets=role_interests,
            role_family_summary=row.role_family_summary,
        )[0]
        for row in rows_with_summary
    ]
    return _average_known(scores)


def _preview_evidence(
    key: ScoringWeightKey,
    *,
    score_id: str | None,
    company_count: int,
    hiring_count: int,
    has_preferences: bool,
) -> list[str]:
    if key == "entry_level_access":
        if score_id is None:
            return []
        return [f"region_market_scores:{score_id}:early_career_accessibility_score"]
    if key == "hiring_density":
        return [f"region_market_scores:{score_id}:live_market_score"] if score_id else []
    if key == "prestige":
        return [f"companies:prestige_score:present_company_count={company_count}"]
    if key == "industry_fit":
        basis = "saved_industry_interests" if has_preferences else "neutral_no_industry_interests"
        return [f"companies:sector_fields:{basis}:present_company_count={company_count}"]
    if key == "role_fit":
        basis = "saved_role_interests" if has_preferences else "neutral_no_role_interests"
        return [f"company_region_hiring:role_family_summary:{basis}:hiring_rows={hiring_count}"]
    return []
