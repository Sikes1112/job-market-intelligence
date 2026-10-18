"""Idempotent curated beta bootstrap and operator-readable quality gate."""

from __future__ import annotations

import argparse
import json
from datetime import date

from backend.config.settings import get_settings
from backend.current_opportunities.models import CurrentOpportunity, OpportunityDataSource
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
    validate_all_registered_market_datasets,
)
from backend.imports.registry import load_market_registry
from backend.market_intelligence.service import MarketIntelligenceService
from backend.operations.migrations import database_migration_status
from backend.shared.db import make_engine, make_session_factory, session_scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "bootstrap", "report"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    settings = get_settings()
    engine = make_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
    try:
        migration = database_migration_status(engine, settings.database_url)
        if migration.status != "current":
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "schema_not_current",
                        "schema": migration.as_dict(),
                    },
                    sort_keys=True,
                )
            )
            return 2
        validation = validate_all_registered_market_datasets(as_of=args.as_of)
        if not validation.ok and args.operation != "report":
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "reference_validation_failed",
                        "validation": _batch(validation),
                    },
                    sort_keys=True,
                )
            )
            return 2
        if args.operation == "validate":
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "as_of": args.as_of.isoformat(),
                        "validation": _batch(validation),
                    },
                    sort_keys=True,
                )
            )
            return 0

        factory = make_session_factory(engine)
        if args.operation == "bootstrap":
            with session_scope(factory) as session:
                imported = import_all_curated_market_datasets(session, as_of=args.as_of)
                refreshed = (
                    run_all_curated_market_post_imports(session, as_of=args.as_of)
                    if imported.ok
                    else None
                )
                if not imported.ok or refreshed is None or not refreshed.ok:
                    raise RuntimeError("curated beta bootstrap failed; transaction rolled back")

        with session_scope(factory) as session:
            report = _quality_report(
                session,
                as_of=args.as_of,
                reference_validation=_batch(validation),
                reference_validation_ok=validation.ok,
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "ready" else 2
    finally:
        engine.dispose()


def _quality_report(
    session,
    *,
    as_of: date,
    reference_validation: dict,
    reference_validation_ok: bool,
) -> dict:  # noqa: ANN001
    registry = load_market_registry()
    intelligence = MarketIntelligenceService(session)
    ranking = intelligence.ranking(as_of=as_of)
    ranked_by_market = {item.market_key: item for item in ranking.ranked_markets}
    markets = []
    for key, entry in registry.items():
        profile = intelligence.profile(key, as_of=as_of).as_dict()
        ranked = ranked_by_market.get(key)
        contradictions = ranked.contradictions if ranked is not None else ()
        markets.append(
            {
                "market_key": key,
                "region_id": entry.region_id,
                "display_name": entry.display_name,
                "support_state": entry.import_status,
                "coverage_state": entry.coverage_status,
                "confidence": profile.get("confidence"),
                "evidence_sufficiency": (
                    ranked.evidence_sufficiency.value if ranked is not None else "not_evaluated"
                ),
                "freshness": profile.get("freshness"),
                "fatal_contradiction": any(item.blocks_recommendation for item in contradictions),
                "display_metadata_present": bool(profile.get("market_name")),
            }
        )
    failures = [
        row["market_key"]
        for row in markets
        if row["support_state"] != "ready"
        or not row["display_metadata_present"]
        or row["fatal_contradiction"]
    ]
    return {
        "status": (
            "ready"
            if reference_validation_ok and len(markets) == 8 and not failures
            else "not_ready"
        ),
        "as_of": as_of.isoformat(),
        "reference_validation": reference_validation,
        "market_count": len(markets),
        "failed_markets": failures,
        "markets": markets,
        "current_opportunities": _current_opportunity_summary(session),
    }


def _current_opportunity_summary(session) -> dict:  # noqa: ANN001
    sources = session.query(OpportunityDataSource).filter_by(enabled=True).all()
    demo_sources = [
        source
        for source in sources
        if isinstance(source.refresh_config, dict)
        and (
            source.refresh_config.get("synthetic") is True
            or source.refresh_config.get("data_origin")
            in {"demo_seed", "synthetic_or_curated_demo"}
        )
    ]
    real_provider_count = len(sources) - len(demo_sources)
    opportunity_count = (
        session.query(CurrentOpportunity)
        .filter(CurrentOpportunity.canonical_status.in_(("active", "stale")))
        .count()
    )
    if real_provider_count and demo_sources:
        mode = "mixed"
        claim = "Inventory mixes synthetic demonstration and partial provider records."
    elif real_provider_count:
        mode = "real_provider"
        claim = "Observed provider records are partial, never exhaustive."
    elif demo_sources:
        mode = "synthetic_demo"
        claim = "Synthetic demonstration records are not live job openings."
    else:
        mode = "coverage_unavailable"
        claim = "No production-quality current-job provider is configured."
    return {
        "mode": mode,
        "enabled_provider_count": real_provider_count,
        "enabled_demo_source_count": len(demo_sources),
        "active_or_stale_count": opportunity_count,
        "claim": claim,
    }


def _batch(result) -> dict:  # noqa: ANN001
    return {
        "operation": result.operation,
        "markets_processed": list(result.markets_processed),
        "markets_succeeded": list(result.markets_succeeded),
        "markets_failed": list(result.markets_failed),
        "errors": [item.message for item in result.errors],
        "warnings": [item.message for item in result.warnings],
    }


if __name__ == "__main__":
    raise SystemExit(main())
