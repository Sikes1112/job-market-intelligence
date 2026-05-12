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

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.personalization.exceptions import (
    MissingRegionForPersonalization,
)
from backend.personalization.payloads import (
    PersonalizedCompanyEntry,
    PersonalizedDiscoveryBody,
    PersonalizedDiscoveryResult,
    PersonalizedRegionEntry,
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
            score_row = self._score_repo.get_score_by_region(region.region_id)
            hiring_index = _hiring_by_region_company(hiring_rows)

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
            region_entries.append(
                PersonalizedRegionEntry(
                    region_id=region.region_id,
                    display_name=region.display_name,
                    personal_market_score=market_score,
                    objective_opportunity_score=objective,
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
