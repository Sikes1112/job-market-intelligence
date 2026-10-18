from __future__ import annotations

import shutil
import socket
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.nyc import import_nyc_dataset
from backend.imports.service import import_curated_market_dataset
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.shared.provenance import ObservationStatus

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPORT_ROOT = REPO_ROOT / "data" / "imports"
AS_OF = date(2026, 7, 9)


def test_nyc_imports_through_generic_market_key(session: Session) -> None:
    result = import_curated_market_dataset(session, "nyc", as_of=AS_OF)

    assert result.ok
    assert result.dataset_path.endswith("data/imports/nyc")
    assert result.counts["regions"].created == 1
    assert session.get(Region, "greater_nyc") is not None


def test_seattle_imports_through_generic_market_key(session: Session) -> None:
    result = import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    assert result.ok
    assert result.dataset_path.endswith("data/imports/seattle")
    assert result.counts["regions"].created == 1
    assert result.counts["companies"].created == 3
    assert result.counts["presence"].created == 3
    assert session.get(Region, "greater_seattle") is not None


def test_nyc_wrapper_still_uses_registered_generic_path(session: Session) -> None:
    result = import_nyc_dataset(session, as_of=AS_OF)

    assert result.ok
    assert result.dataset_path.endswith("data/imports/nyc")
    assert session.get(Region, "greater_nyc") is not None


def test_seattle_has_no_custom_importer_module() -> None:
    assert not (REPO_ROOT / "backend" / "imports" / "seattle.py").exists()


def test_nyc_and_seattle_import_into_same_canonical_db(
    session: Session,
) -> None:
    nyc = import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    seattle = import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    assert nyc.ok and seattle.ok
    assert _table_counts(session) == {
        "regions": 2,
        "companies": 5,
        "presence": 6,
        "hiring": 6,
        "entry_level": 6,
        "source_refs": 10,
        "source_observations": 10,
        "fact_source_links": 26,
    }
    assert _count_company(session, "cmp_hudson_applied_ai") == 1
    assert session.get(Company, "cmp_hudson_applied_ai").company_name == (
        "Hudson Applied AI"
    )


def test_market_specific_presence_hiring_and_entry_facts_remain_separate(
    session: Session,
) -> None:
    import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    nyc_presence = session.get(
        CompanyRegionPresence,
        "presence_cmp_hudson_applied_ai_greater_nyc",
    )
    seattle_presence = session.get(
        CompanyRegionPresence,
        "presence_cmp_hudson_applied_ai_greater_seattle",
    )
    nyc_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    seattle_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_hudson_applied_ai_greater_seattle",
    )
    nyc_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_hudson_applied_ai_greater_nyc",
    )
    seattle_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_hudson_applied_ai_greater_seattle",
    )

    assert nyc_presence is not None
    assert seattle_presence is not None
    assert nyc_presence.region_id == "greater_nyc"
    assert seattle_presence.region_id == "greater_seattle"
    assert nyc_hiring.active_posting_count_now == 9
    assert seattle_hiring.active_posting_count_now == 2
    assert nyc_entry.internship_count == 7
    assert seattle_entry.internship_count == 1


def test_fact_source_links_do_not_cross_link_between_markets(
    session: Session,
) -> None:
    import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    seattle_fact_ids = {
        "greater_seattle",
        "presence_cmp_hudson_applied_ai_greater_seattle",
        "hiring_cmp_hudson_applied_ai_greater_seattle",
        "entry_cmp_hudson_applied_ai_greater_seattle",
    }
    links = session.execute(
        select(FactSourceLink).where(FactSourceLink.fact_id.in_(seattle_fact_ids))
    ).scalars()

    assert links
    assert all(link.source_id.startswith("src_seattle_") for link in links)
    assert all(not link.source_id.startswith("src_nyc_") for link in links)


def test_repeated_multi_market_import_is_idempotent(session: Session) -> None:
    import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    import_curated_market_dataset(session, "seattle", as_of=AS_OF)
    counts = _table_counts(session)

    second_nyc = import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    second_seattle = import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    assert second_nyc.ok and second_seattle.ok
    assert second_nyc.counts["regions"].unchanged == 1
    assert second_seattle.counts["regions"].unchanged == 1
    assert second_nyc.counts["companies"].unchanged == 3
    assert second_seattle.counts["companies"].unchanged == 3
    assert _table_counts(session) == counts


def test_seattle_validation_failure_does_not_corrupt_nyc_state(
    tmp_path: Path,
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "nyc", as_of=AS_OF).ok
    before = _table_counts(session)
    root = _copy_import_root(tmp_path)
    (root / "seattle" / "companies.csv").unlink()

    result = import_curated_market_dataset(
        session,
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert not result.ok
    assert result.status == "validation_failed"
    assert _table_counts(session) == before
    assert session.get(Region, "greater_nyc") is not None
    assert session.get(Region, "greater_seattle") is None


def test_nyc_validation_failure_does_not_corrupt_seattle_state(
    tmp_path: Path,
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok
    before = _table_counts(session)
    root = _copy_import_root(tmp_path)
    (root / "nyc" / "hiring.csv").unlink()

    result = import_curated_market_dataset(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert not result.ok
    assert result.status == "validation_failed"
    assert _table_counts(session) == before
    assert session.get(Region, "greater_seattle") is not None
    assert session.get(Region, "greater_nyc") is None


def test_unknown_and_observed_zero_values_survive_across_markets(
    session: Session,
) -> None:
    import_curated_market_dataset(session, "nyc", as_of=AS_OF)
    import_curated_market_dataset(session, "seattle", as_of=AS_OF)

    unknown_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_sound_security_systems_greater_seattle",
    )
    zero_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_cascade_cloud_labs_greater_seattle",
    )
    unknown_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_sound_security_systems_greater_seattle",
    )
    zero_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_cascade_cloud_labs_greater_seattle",
    )

    assert unknown_hiring.active_posting_count_now is None
    assert unknown_hiring.active_posting_count_now_status == ObservationStatus.UNKNOWN
    assert zero_hiring.active_posting_count_now == 0
    assert zero_hiring.active_posting_count_now_status == (
        ObservationStatus.ZERO_OBSERVED
    )
    assert unknown_entry.internship_count is None
    assert unknown_entry.internship_count_status == ObservationStatus.UNKNOWN
    assert zero_entry.internship_count == 0
    assert zero_entry.internship_count_status == ObservationStatus.ZERO_OBSERVED


def test_multi_market_import_requires_no_network(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for curated imports")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)

    assert import_curated_market_dataset(session, "nyc", as_of=AS_OF).ok
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok


def _copy_import_root(tmp_path: Path) -> Path:
    root = tmp_path / "imports"
    shutil.copytree(IMPORT_ROOT, root)
    return root


def _count_company(session: Session, company_id: str) -> int:
    return session.query(Company).filter(Company.company_id == company_id).count()


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
