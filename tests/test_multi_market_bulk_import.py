from __future__ import annotations

import shutil
import socket
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
    validate_all_registered_market_datasets,
)
from backend.imports.contracts import REQUIRED_DATASET_FILES
from backend.imports.registry import load_market_registry
from backend.imports.service import import_curated_market_dataset
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.trust.models import RiskRoutingDecision, TrustAssessment

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPORT_ROOT = REPO_ROOT / "data" / "imports"
REGISTRY_PATH = IMPORT_ROOT / "markets.json"
AS_OF = date(2026, 7, 9)
ADDED_MARKETS = {
    "san_francisco_bay_area",
    "boston",
    "washington_dc",
    "austin",
    "atlanta",
    "chicago",
}
ALL_MARKETS = {
    "nyc",
    "seattle",
    *ADDED_MARKETS,
}


def test_all_registered_market_datasets_validate() -> None:
    result = validate_all_registered_market_datasets(
        registry_path=REGISTRY_PATH,
        as_of=AS_OF,
    )

    assert result.ok
    assert set(result.markets_processed) == ALL_MARKETS
    assert set(result.markets_succeeded) == ALL_MARKETS
    assert result.markets_failed == ()


def test_all_added_market_datasets_use_six_file_contract() -> None:
    registry = load_market_registry(REGISTRY_PATH)

    for market_key in ADDED_MARKETS:
        dataset_path = registry[market_key].dataset_path
        assert {path.name for path in dataset_path.iterdir() if path.is_file()} == set(
            REQUIRED_DATASET_FILES
        )


def test_added_markets_import_through_generic_function(session: Session) -> None:
    for market_key in sorted(ADDED_MARKETS):
        result = import_curated_market_dataset(session, market_key, as_of=AS_OF)
        assert result.ok, market_key

    assert session.query(Region).count() == len(ADDED_MARKETS)
    assert session.query(CompanyRegionPresence).count() == len(ADDED_MARKETS) * 3
    assert session.query(CompanyRegionHiring).count() == len(ADDED_MARKETS) * 3
    assert session.query(CompanyRegionEntryLevel).count() == len(ADDED_MARKETS) * 3


def test_bulk_import_processes_all_registered_markets(session: Session) -> None:
    result = import_all_curated_market_datasets(
        session,
        registry_path=REGISTRY_PATH,
        as_of=AS_OF,
    )

    assert result.ok
    assert set(result.markets_processed) == ALL_MARKETS
    assert result.markets_failed == ()
    assert result.total_created > 0
    assert _table_counts(session) == {
        "regions": 8,
        "companies": 14,
        "presence": 24,
        "hiring": 24,
        "entry_level": 24,
        "source_refs": 40,
        "source_observations": 40,
        "fact_source_links": 104,
    }


def test_bulk_import_is_idempotent(session: Session) -> None:
    first = import_all_curated_market_datasets(session, as_of=AS_OF)
    counts = _table_counts(session)
    second = import_all_curated_market_datasets(session, as_of=AS_OF)

    assert first.ok and second.ok
    assert second.total_created == 0
    assert second.total_updated == 0
    assert second.total_unchanged > first.total_unchanged
    assert _table_counts(session) == counts


def test_bulk_post_import_refresh_processes_all_registered_markets(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok

    result = run_all_curated_market_post_imports(session, as_of=AS_OF)

    assert result.ok
    assert set(result.markets_processed) == ALL_MARKETS
    assert result.markets_failed == ()
    assert result.total_ranking_allowed == 104
    assert result.total_ranking_denied == 0
    assert session.query(TrustAssessment).count() == 94
    assert session.query(RiskRoutingDecision).count() == 94


def test_bulk_post_import_refresh_is_idempotent(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    first = run_all_curated_market_post_imports(session, as_of=AS_OF)
    trust_count = session.query(TrustAssessment).count()
    routing_count = session.query(RiskRoutingDecision).count()
    second = run_all_curated_market_post_imports(session, as_of=AS_OF)

    assert first.ok and second.ok
    assert second.total_created == 0
    assert second.total_unchanged > 0
    assert session.query(TrustAssessment).count() == trust_count
    assert session.query(RiskRoutingDecision).count() == routing_count


def test_bulk_import_failure_in_one_market_does_not_corrupt_others(
    tmp_path: Path,
    session: Session,
) -> None:
    root = _copy_import_root(tmp_path)
    (root / "boston" / "hiring.csv").unlink()

    result = import_all_curated_market_datasets(
        session,
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert not result.ok
    assert result.markets_failed == ("boston",)
    assert set(result.markets_succeeded) == ALL_MARKETS - {"boston"}
    assert session.get(Region, "greater_boston") is None
    assert session.query(CompanyRegionPresence).filter_by(region_id="greater_boston").count() == 0
    assert session.query(CompanyRegionHiring).filter_by(region_id="greater_boston").count() == 0
    assert session.query(CompanyRegionEntryLevel).filter_by(region_id="greater_boston").count() == 0
    assert session.get(Region, "sf_bay_area") is not None
    assert session.get(Region, "chicago") is not None


def test_bulk_import_requires_no_network(session: Session, monkeypatch) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for curated imports")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)

    result = import_all_curated_market_datasets(session, as_of=AS_OF)

    assert result.ok
    assert session.query(Region).count() == len(ALL_MARKETS)


def _copy_import_root(tmp_path: Path) -> Path:
    root = tmp_path / "imports"
    shutil.copytree(IMPORT_ROOT, root)
    return root


def _table_counts(session: Session) -> dict[str, int]:
    return {
        "regions": session.query(Region).count(),
        "companies": session.query(Company).count(),
        "presence": session.query(CompanyRegionPresence).count(),
        "hiring": session.query(CompanyRegionHiring).count(),
        "entry_level": session.query(CompanyRegionEntryLevel).count(),
        "source_refs": session.query(SourceRef).count(),
        "source_observations": session.query(SourceObservation).count(),
        "fact_source_links": session.query(FactSourceLink).count(),
    }
