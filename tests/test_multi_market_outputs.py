from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    rebuild_all_curated_market_outputs,
)
from backend.imports.post_import import run_curated_market_post_import
from backend.outputs.comparison_output import canonical_comparison_id
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink
from backend.scoring.models import RegionMarketScore
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    UserReport,
)

AS_OF = date(2026, 7, 9)
REGION_BY_MARKET = {
    "nyc": "greater_nyc",
    "seattle": "greater_seattle",
    "san_francisco_bay_area": "sf_bay_area",
    "boston": "greater_boston",
    "washington_dc": "washington_dc",
    "austin": "austin",
    "atlanta": "atlanta",
    "chicago": "chicago",
}
ALL_REGION_IDS = set(REGION_BY_MARKET.values())


def test_bulk_output_rebuild_processes_all_registered_markets(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok

    result = rebuild_all_curated_market_outputs(session, as_of=AS_OF)

    assert result.ok
    assert set(result.markets_processed) == set(REGION_BY_MARKET)
    assert result.total_ranking_allowed == 104
    assert _output_count(session, OutputType.REGION_OUTPUT) == 8
    assert _output_count(session, OutputType.COMPANY_OUTPUT) == 14
    assert _output_count(session, OutputType.COMPARISON_OUTPUT) == 28
    for region_id in ALL_REGION_IDS:
        output = _output(
            session,
            output_type=OutputType.REGION_OUTPUT,
            subject_id=region_id,
        )
        assert output.cached_payload["region"]["region_id"] == region_id
        assert output.cached_payload["region"]["summary"]["present_company_count"] == 3
        assert output.cached_payload["region"]["import_metadata"][
            "imported_data_label"
        ] == "Demonstration data"


def test_bulk_output_rebuild_is_idempotent(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    first = rebuild_all_curated_market_outputs(session, as_of=AS_OF)
    hashes = {
        (row.output_type, row.subject_id): row.artifact_hash
        for row in session.query(OutputMetadata).all()
    }
    second = rebuild_all_curated_market_outputs(session, as_of=AS_OF)

    assert first.ok and second.ok
    assert second.total_created == 0
    assert second.total_unchanged > 0
    assert {
        (row.output_type, row.subject_id): row.artifact_hash
        for row in session.query(OutputMetadata).all()
    } == hashes


def test_comparison_outputs_include_multiple_imported_markets(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert rebuild_all_curated_market_outputs(session, as_of=AS_OF).ok

    comparison_id = canonical_comparison_id("sf_bay_area", "greater_nyc")
    comparison = _output(
        session,
        output_type=OutputType.COMPARISON_OUTPUT,
        subject_id=comparison_id,
    )
    sides = {
        comparison.cached_payload["comparison"]["region_a"]["region_id"],
        comparison.cached_payload["comparison"]["region_b"]["region_id"],
    }

    assert sides == {"sf_bay_area", "greater_nyc"}
    assert comparison.cached_payload["comparison"]["category_winners"]
    _assert_public_payload_safe(comparison.cached_payload)


def test_shared_companies_are_canonical_with_market_specific_facts(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok

    assert session.query(Company).filter_by(company_id="cmp_google").count() == 1
    google_presence = session.query(CompanyRegionPresence).filter_by(
        company_id="cmp_google"
    ).all()
    google_hiring = session.query(CompanyRegionHiring).filter_by(
        company_id="cmp_google"
    ).all()
    google_entry = session.query(CompanyRegionEntryLevel).filter_by(
        company_id="cmp_google"
    ).all()

    assert {row.region_id for row in google_presence} == {
        "sf_bay_area",
        "greater_boston",
        "austin",
        "chicago",
    }
    assert {row.region_id for row in google_hiring} == {
        "sf_bay_area",
        "greater_boston",
        "austin",
        "chicago",
    }
    assert {row.region_id for row in google_entry} == {
        "sf_bay_area",
        "greater_boston",
        "austin",
        "chicago",
    }
    assert _hiring(session, "cmp_google", "sf_bay_area").active_posting_count_now == 12
    assert _hiring(session, "cmp_google", "chicago").active_posting_count_now == 8


def test_region_specific_fact_source_links_do_not_cross_markets(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    region_to_market = {region_id: market for market, region_id in REGION_BY_MARKET.items()}

    for row in session.query(CompanyRegionHiring).all():
        expected_prefix = f"src_{region_to_market[row.region_id]}_"
        links = _fact_links(session, "company_region_hiring", row.hiring_id)
        assert links
        assert all(link.source_id.startswith(expected_prefix) for link in links)
    for row in session.query(CompanyRegionEntryLevel).all():
        expected_prefix = f"src_{region_to_market[row.region_id]}_"
        links = _fact_links(session, "company_region_entry_level", row.entry_level_id)
        assert links
        assert all(link.source_id.startswith(expected_prefix) for link in links)
    for row in session.query(CompanyRegionPresence).all():
        expected_prefix = f"src_{region_to_market[row.region_id]}_"
        links = _fact_links(session, "company_region_presence", row.presence_id)
        assert links
        assert all(link.source_id.startswith(expected_prefix) for link in links)


def test_ranking_ineligible_austin_fact_does_not_affect_nyc(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert rebuild_all_curated_market_outputs(session, as_of=AS_OF).ok
    nyc_score_before = _score(session, "greater_nyc").live_market_score

    link = _fact_link(
        session,
        "company_region_hiring",
        "hiring_cmp_google_austin",
    )
    link.freshness_status = "stale"
    session.flush()
    assert run_curated_market_post_import(session, "austin", as_of=AS_OF).ok

    austin_routing = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="hiring_cmp_google_austin",
    )
    nyc_score_after = _score(session, "greater_nyc").live_market_score
    austin_output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="austin",
    )
    austin_hiring_ids = {
        item["company_id"]
        for item in austin_output.cached_payload["region"]["top_companies_hiring"]
    }

    assert austin_routing.ranking_influence_allowed is False
    assert austin_routing.trust_tier == "stale"
    assert nyc_score_after == nyc_score_before
    assert "cmp_google" not in austin_hiring_ids


def test_output_payloads_preserve_unknown_and_zero_across_markets(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert rebuild_all_curated_market_outputs(session, as_of=AS_OF).ok

    observed_statuses: set[str] = set()
    entry_summary_statuses: set[str] = set()
    for region_id in ALL_REGION_IDS:
        payload = _output(
            session,
            output_type=OutputType.REGION_OUTPUT,
            subject_id=region_id,
        ).cached_payload
        hiring_statuses = {
            item["active_posting_count_now_status"]: item["active_posting_count_now"]
            for item in payload["region"]["top_companies_hiring"]
        }
        observed_statuses.update(hiring_statuses)
        if "zero_observed" in hiring_statuses:
            assert hiring_statuses["zero_observed"] == 0
        if "unknown" in hiring_statuses:
            assert hiring_statuses["unknown"] is None
        entry_summary = payload["region"]["entry_level_summary"]
        entry_summary_statuses.add(entry_summary["internship_count_total_status"])
        if entry_summary["internship_count_total_status"] == "unknown":
            assert entry_summary["internship_count_total"] is None
        _assert_public_payload_safe(payload)

    # The portfolio fixture deliberately varies its observation pattern rather
    # than repeating positive/zero/unknown in every market, while retaining all
    # three semantics across the seeded universe.
    assert {"positive_observed", "zero_observed", "unknown"} <= observed_statuses
    assert {"positive_observed", "unknown"} <= entry_summary_statuses


def test_bulk_output_rebuild_introduces_no_manual_approval_workflows(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok

    result = rebuild_all_curated_market_outputs(session, as_of=AS_OF)

    assert result.ok
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def _output_count(session: Session, output_type: OutputType) -> int:
    return session.query(OutputMetadata).filter_by(output_type=output_type.value).count()


def _output(
    session: Session,
    *,
    output_type: OutputType,
    subject_id: str,
) -> OutputMetadata:
    return session.execute(
        select(OutputMetadata).where(
            OutputMetadata.output_type == output_type.value,
            OutputMetadata.subject_id == subject_id,
        )
    ).scalar_one()


def _hiring(
    session: Session,
    company_id: str,
    region_id: str,
) -> CompanyRegionHiring:
    return session.execute(
        select(CompanyRegionHiring).where(
            CompanyRegionHiring.company_id == company_id,
            CompanyRegionHiring.region_id == region_id,
        )
    ).scalar_one()


def _score(session: Session, region_id: str) -> RegionMarketScore:
    return session.execute(
        select(RegionMarketScore).where(RegionMarketScore.region_id == region_id)
    ).scalar_one()


def _fact_link(
    session: Session,
    fact_type: str,
    fact_id: str,
) -> FactSourceLink:
    return session.execute(
        select(FactSourceLink).where(
            FactSourceLink.fact_type == fact_type,
            FactSourceLink.fact_id == fact_id,
        )
    ).scalar_one()


def _fact_links(
    session: Session,
    fact_type: str,
    fact_id: str,
) -> tuple[FactSourceLink, ...]:
    rows = session.execute(
        select(FactSourceLink).where(
            FactSourceLink.fact_type == fact_type,
            FactSourceLink.fact_id == fact_id,
        )
    ).scalars()
    return tuple(rows)


def _latest_routing(
    session: Session,
    *,
    subject_type: str,
    subject_id: str,
) -> RiskRoutingDecision:
    return session.execute(
        select(RiskRoutingDecision)
        .where(
            RiskRoutingDecision.subject_type == subject_type,
            RiskRoutingDecision.subject_id == subject_id,
        )
        .order_by(
            RiskRoutingDecision.decided_at.desc(),
            RiskRoutingDecision.risk_routing_decision_id.desc(),
        )
    ).scalars().first()


def _assert_public_payload_safe(value: Any) -> None:
    forbidden = {
        "internal_notes",
        "reporter_user_id",
        "reporter_session_id",
        "report_reason",
        "related_user_report_id",
        "assigned_owner",
        "exception_case_id",
        "risk_routing_decision_id",
        "trust_assessment_id",
        "raw_internal_risk",
    }
    assert forbidden.isdisjoint(_keys(value))


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_keys(item))
        return keys
    if isinstance(value, list | tuple):
        keys: set[str] = set()
        for item in value:
            keys.update(_keys(item))
        return keys
    return set()
