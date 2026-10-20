"""Eight-market portfolio demonstration extension.

This composes existing curated-import, post-import, opportunity, Career
Identity, personalization, and Decision services. It is not a parallel fixture
writer and performs no external I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.imports.result import CuratedMarketBatchResult
from seeds.mvp_seed import (
    SeedResult,
    close_opportunity_scenarios,
    seed_opportunity_scenarios,
)
from seeds.opportunity_data import (
    DEMO_CLOSED_RUN_ID,
    DEMO_OPPORTUNITY_SCENARIOS,
    DEMO_PORTFOLIO_RUN_ID,
    MARKET_LABELS,
    demo_observed_at,
)
from seeds.reviewer_scenarios import ReviewerScenarioResult, seed_reviewer_scenarios


@dataclass(frozen=True, slots=True)
class PortfolioSeedResult:
    seed: SeedResult
    imported: CuratedMarketBatchResult
    refreshed: CuratedMarketBatchResult
    reviewer: ReviewerScenarioResult | None


def run_portfolio_seed(
    session: Session,
    seed_result: SeedResult,
    *,
    as_of: date,
    demo_now: datetime | None = None,
    include_reviewer: bool = True,
) -> PortfolioSeedResult:
    """Extend a completed MVP seed into the complete eight-market demo."""

    imported = import_all_curated_market_datasets(session, as_of=as_of)
    if not imported.ok:
        raise RuntimeError("portfolio market import failed")
    refreshed = run_all_curated_market_post_imports(session, as_of=as_of)
    if not refreshed.ok:
        raise RuntimeError("portfolio market post-import refresh failed")

    observed_at = demo_observed_at(demo_now)
    seed_opportunity_scenarios(
        session,
        seed_result,
        scenarios=DEMO_OPPORTUNITY_SCENARIOS,
        market_ids=set(MARKET_LABELS),
        run_id=DEMO_PORTFOLIO_RUN_ID,
        observed_at=observed_at,
    )
    close_opportunity_scenarios(
        session,
        seed_result,
        scenarios=DEMO_OPPORTUNITY_SCENARIOS,
        run_id=DEMO_CLOSED_RUN_ID,
        observed_at=observed_at,
    )
    reviewer = seed_reviewer_scenarios(session) if include_reviewer else None
    return PortfolioSeedResult(
        seed=seed_result,
        imported=imported,
        refreshed=refreshed,
        reviewer=reviewer,
    )
