from __future__ import annotations

import ast
import csv
import json
import shutil
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.imports.diagnostics import (
    build_refresh_readiness_reports,
    coverage_gaps_from_snapshot,
    dataset_health_from_snapshot,
    fact_health_from_snapshot,
    ranking_exclusions_from_snapshot,
    refresh_readiness_from_snapshot,
    source_aging_from_snapshot,
)
from backend.imports.diff import build_import_diff_preview
from backend.imports.operations import (
    build_all_market_operational_snapshots,
    build_market_operational_snapshot,
)
from backend.imports.schemas import (
    DiffRisk,
    MarketHealthStatus,
    OperationalSourceFreshnessStatus,
    RefreshReadinessStatus,
)
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.shared.provenance import ObservationStatus
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    TrustAssessment,
    UserReport,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPORT_ROOT = REPO_ROOT / "data" / "imports"
AS_OF = date(2026, 7, 9)
EXPECTED_MARKETS = {
    "nyc",
    "seattle",
    "san_francisco_bay_area",
    "boston",
    "washington_dc",
    "austin",
    "atlanta",
    "chicago",
}


def test_layer33_health_reports_all_eight_markets_are_deterministic(
    session: Session,
) -> None:
    _seed_all_markets(session)

    first = tuple(
        dataset_health_from_snapshot(snapshot).as_dict()
        for snapshot in build_all_market_operational_snapshots(session, as_of=AS_OF)
    )
    second = tuple(
        dataset_health_from_snapshot(snapshot).as_dict()
        for snapshot in build_all_market_operational_snapshots(session, as_of=AS_OF)
    )

    assert first == second
    assert {report["market_key"] for report in first} == EXPECTED_MARKETS
    assert any(report["health_status"] == MarketHealthStatus.HEALTHY for report in first)
    for report in first:
        counts = report["counts"]
        assert report["validation_ok"] is True
        assert counts["company_count"] == 3
        assert counts["source_count"] == 5
        assert counts["presence_fact_count"] == 3
        assert counts["hiring_fact_count"] == 3
        assert counts["entry_level_fact_count"] == 3
        assert counts["total_fact_count"] == 13
        assert counts["ranking_eligible_fact_count"] == 13
        assert counts["ranking_excluded_fact_count"] == 0
        assert counts["stale_source_count"] == 0
    assert any(report["counts"]["unknown_fact_count"] > 0 for report in first)
    assert any(report["counts"]["observed_zero_fact_count"] > 0 for report in first)
    assert len({report["counts"]["unknown_fact_count"] for report in first}) > 1
    assert len({report["counts"]["observed_zero_fact_count"] for report in first}) > 1


def test_batched_snapshots_are_semantically_identical_to_single_market_path(
    session: Session,
) -> None:
    _seed_all_markets(session)
    batched = {
        snapshot.market_key: snapshot
        for snapshot in build_all_market_operational_snapshots(session, as_of=AS_OF)
    }
    singles = {
        market_key: build_market_operational_snapshot(session, market_key, as_of=AS_OF)
        for market_key in sorted(EXPECTED_MARKETS)
    }

    def projection(snapshot) -> dict[str, Any]:  # noqa: ANN001
        return {
            "health": dataset_health_from_snapshot(snapshot).as_dict(),
            "source_aging": source_aging_from_snapshot(snapshot).as_dict(),
            "fact_health": fact_health_from_snapshot(snapshot).as_dict(),
            "coverage": coverage_gaps_from_snapshot(snapshot).as_dict(),
            "ranking": ranking_exclusions_from_snapshot(snapshot).as_dict(),
            "facts": tuple(
                (
                    fact.fact_type,
                    fact.fact_id,
                    fact.observation_status,
                    fact.freshness_status,
                    fact.confidence,
                    fact.source_ids,
                    fact.ranking_eligible,
                    fact.ranking_reason_codes,
                    fact.trust_tier,
                    fact.risk_level,
                    fact.count_statuses,
                )
                for fact in snapshot.facts
            ),
            "sources": tuple(
                (
                    source.source_id,
                    source.observed_date,
                    source.collected_date,
                    source.freshness_status,
                    source.confidence,
                    source.fact_refs,
                )
                for source in snapshot.sources
            ),
            "source_rows": snapshot.source_rows,
            "proposed_fact_source_ids": snapshot.proposed_fact_source_ids,
        }

    assert {key: projection(value) for key, value in batched.items()} == {
        key: projection(value) for key, value in singles.items()
    }


def test_layer33_health_precedence_validation_failure_wins(
    tmp_path: Path,
    session: Session,
) -> None:
    root = _copy_import_root(tmp_path)
    (root / "nyc" / "companies.csv").unlink()
    _update_source_ref(
        root / "nyc",
        "src_nyc_hiring_snapshot_2026_06",
        {"observed_at": "2024-01-01"},
    )

    snapshot = build_market_operational_snapshot(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    report = dataset_health_from_snapshot(snapshot)

    assert report.health_status is MarketHealthStatus.VALIDATION_FAILED
    assert report.missing_required_files == ("companies.csv",)
    assert report.recommended_next_action == "Fix curated source-file validation errors."


def test_layer33_source_aging_classifies_current_aging_stale_and_expired(
    session: Session,
) -> None:
    _seed_all_markets(session)
    _source(session, "src_nyc_company_roster_2026_06").observed_at = _dt(2025, 9, 15)
    _source(session, "src_nyc_presence_observation_2026_06").observed_at = _dt(2025, 6, 1)
    _source(session, "src_nyc_hiring_snapshot_2026_06").observed_at = _dt(2024, 1, 1)
    session.flush()

    report = source_aging_from_snapshot(
        build_market_operational_snapshot(session, "nyc", as_of=AS_OF)
    )
    statuses = {source.source_id: source.freshness_status for source in report.sources}

    assert statuses["src_nyc_region_fixture_2026_06"] is (OperationalSourceFreshnessStatus.CURRENT)
    assert statuses["src_nyc_company_roster_2026_06"] is (OperationalSourceFreshnessStatus.AGING)
    assert statuses["src_nyc_presence_observation_2026_06"] is (
        OperationalSourceFreshnessStatus.STALE
    )
    assert statuses["src_nyc_hiring_snapshot_2026_06"] is (OperationalSourceFreshnessStatus.EXPIRED)
    assert report.stale_source_count == 2
    assert report.aging_source_count == 1
    assert report.expired_source_count == 1
    assert report.oldest_source_age_days == (AS_OF - date(2024, 1, 1)).days
    assert report.important_stale_sources[0].fact_usage_count >= 1


def test_layer33_fact_health_preserves_unknown_zero_and_ranking_counts(
    session: Session,
) -> None:
    _seed_all_markets(session)

    report = fact_health_from_snapshot(
        build_market_operational_snapshot(session, "seattle", as_of=AS_OF)
    )
    by_fact = {finding.fact_id: finding for finding in report.findings}

    assert report.total_facts == 13
    assert report.ranking_eligible_facts == 13
    assert report.ranking_excluded_facts == 0
    assert report.unknown_facts > 0
    assert report.observed_zero_facts > 0
    assert (
        by_fact["hiring_cmp_sound_security_systems_greater_seattle"].observation_status
        == ObservationStatus.UNKNOWN
    )
    assert (
        by_fact["hiring_cmp_cascade_cloud_labs_greater_seattle"].observation_status
        == ObservationStatus.ZERO_OBSERVED
    )
    assert report.missing_useful_dimension_facts > 0


def test_layer33_coverage_gap_detection_reports_specific_actions(
    tmp_path: Path,
    session: Session,
) -> None:
    root = _copy_import_root(tmp_path)
    _rewrite_csv(root / "nyc" / "companies.csv", _read_csv(root / "nyc" / "companies.csv")[:1])
    for file_name in ("presence.csv", "hiring.csv", "entry_level.csv"):
        _rewrite_csv(root / "nyc" / file_name, _read_csv(root / "nyc" / file_name)[:1])

    snapshot = build_market_operational_snapshot(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    report = coverage_gaps_from_snapshot(snapshot)
    by_code = {gap.gap_code: gap for gap in report.gaps}

    assert by_code["too_few_companies"].severity == "critical"
    assert by_code["too_few_hiring_facts"].recommended_action == (
        "Refresh regional hiring counts for each curated company."
    )
    _seed_all_markets(session)
    seeded_report = coverage_gaps_from_snapshot(
        build_market_operational_snapshot(session, "nyc", as_of=AS_OF)
    )
    seeded_codes = {gap.gap_code for gap in seeded_report.gaps}
    assert "missing_30_day_hiring_counts" in seeded_codes
    assert "missing_90_day_hiring_counts" in seeded_codes


def test_layer33_ranking_diagnostics_use_actual_gate_and_public_reasons(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    unassessed = ranking_exclusions_from_snapshot(
        build_market_operational_snapshot(session, "nyc", as_of=AS_OF)
    )
    assert unassessed.excluded_fact_count == 13
    assert unassessed.insufficient_evidence_exclusion_count > 0

    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok
    link = _fact_link(
        session,
        "company_region_hiring",
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    link.freshness_status = "stale"
    session.flush()
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok

    stale_report = ranking_exclusions_from_snapshot(
        build_market_operational_snapshot(session, "nyc", as_of=AS_OF)
    )
    payload = stale_report.as_dict()

    assert stale_report.excluded_fact_count >= 1
    assert stale_report.stale_source_exclusion_count >= 1
    assert "hiring" in stale_report.affected_areas
    _assert_public_payload_safe(payload)


def test_layer33_refresh_readiness_all_statuses_are_reachable(
    tmp_path: Path,
    session: Session,
) -> None:
    _seed_all_markets(session)
    assert _readiness(session, "nyc") is RefreshReadinessStatus.READY

    _source(session, "src_nyc_hiring_snapshot_2026_06").observed_at = _dt(2024, 1, 1)
    session.flush()
    assert _readiness(session, "nyc") is RefreshReadinessStatus.NEEDS_SOURCE_REFRESH

    root = _copy_import_root(tmp_path)
    (root / "seattle" / "hiring.csv").unlink()
    validation_snapshot = build_market_operational_snapshot(
        session,
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    assert (
        refresh_readiness_from_snapshot(validation_snapshot).readiness_status
        is RefreshReadinessStatus.NEEDS_VALIDATION_FIX
    )

    presence = session.get(
        CompanyRegionPresence,
        "presence_cmp_cascade_cloud_labs_greater_seattle",
    )
    session.delete(presence)
    session.flush()
    assert _readiness(session, "seattle") is (RefreshReadinessStatus.NEEDS_COVERAGE_EXPANSION)

    for decision in _routing_rows(session, "atlanta")[:4]:
        decision.ranking_influence_allowed = False
        decision.ranking_influence_decision = "denied"
        decision.ranking_influence_reason = "test ranking review"
        decision.ranking_influence_reason_codes_json = [
            "low_confidence",
            "ranking_default_denied",
        ]
        decision.trust_tier = "low_confidence"
        decision.risk_level = "medium"
    session.flush()
    assert _readiness(session, "atlanta") is RefreshReadinessStatus.NEEDS_RANKING_REVIEW

    _source(session, "src_boston_hiring_2026_06").observed_at = _dt(2024, 1, 1)
    session.delete(session.get(CompanyRegionPresence, "presence_cmp_google_greater_boston"))
    session.flush()
    assert _readiness(session, "boston") is RefreshReadinessStatus.NOT_READY

    priorities = build_refresh_readiness_reports(session, as_of=AS_OF)
    assert [item.priority_score for item in priorities] == sorted(
        [item.priority_score for item in priorities],
        reverse=True,
    )


def test_layer33_diff_preview_detects_dangerous_semantic_changes(
    tmp_path: Path,
    session: Session,
) -> None:
    _seed_all_markets(session)
    root = _copy_import_root(tmp_path)
    _append_csv_row(
        root / "nyc" / "companies.csv",
        {
            "company_id": "cmp_new_ai_lab",
            "company_name": "New AI Lab",
            "sector": "ai",
            "public_or_private": "private",
            "website_domain": "newailab.example",
            "source_ref": "src_nyc_company_roster_2026_06",
        },
    )
    _update_csv_row(
        root / "nyc" / "companies.csv",
        0,
        {"company_name": "Hudson Applied AI Labs"},
    )
    _update_csv_row(
        root / "nyc" / "hiring.csv",
        1,
        {"active_posting_count": "", "active_posting_count_status": "unknown"},
    )
    _update_csv_row(
        root / "nyc" / "hiring.csv",
        2,
        {"active_posting_count": "0", "active_posting_count_status": "zero_observed"},
    )
    _remove_source_ref(root / "nyc", "src_nyc_entry_level_snapshot_2026_06")
    _update_source_ref(
        root / "nyc",
        "src_nyc_hiring_snapshot_2026_06",
        {"observed_at": "2024-01-01", "confidence": "low"},
    )
    preview = build_import_diff_preview(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    repeated = build_import_diff_preview(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    codes = {warning.code for warning in (*preview.warnings, *preview.blocking_issues)}

    assert preview.as_dict() == repeated.as_dict()
    assert preview.overall_diff_risk in {DiffRisk.HIGH, DiffRisk.BLOCKING}
    assert preview.summary_counts["companies_added"] == 1
    assert preview.summary_counts["companies_changed"] >= 1
    assert preview.summary_counts["source_references_absent_from_files"] >= 1
    assert preview.summary_counts["zero_to_unknown_changes"] >= 1
    assert preview.summary_counts["unknown_to_zero_changes"] >= 1
    assert "source_removed_still_used" in codes
    assert "fresh_source_becoming_stale" in codes
    assert "ranking_eligible_becoming_excluded" in codes
    assert "validation_failure_in_proposed_files" in codes


def test_layer33_diff_preview_detects_identity_region_cross_market_and_ranking_recovery(
    tmp_path: Path,
    session: Session,
) -> None:
    _seed_all_markets(session)
    decision = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    decision.ranking_influence_allowed = False
    decision.ranking_influence_decision = "denied"
    decision.ranking_influence_reason_codes_json = [
        "low_confidence",
        "ranking_default_denied",
    ]
    session.flush()

    root = _copy_import_root(tmp_path)
    regions = json.loads((root / "nyc" / "regions.json").read_text(encoding="utf-8"))
    regions[0]["region_id"] = "greater_seattle"
    (root / "nyc" / "regions.json").write_text(json.dumps(regions), encoding="utf-8")
    _update_csv_row(root / "nyc" / "companies.csv", 0, {"company_id": "cmp_hudson_new"})
    _update_csv_row(
        root / "nyc" / "presence.csv",
        0,
        {"source_ref": "src_seattle_presence_observation_2026_06"},
    )

    preview = build_import_diff_preview(
        session,
        "nyc",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    codes = {warning.code for warning in (*preview.warnings, *preview.blocking_issues)}

    assert "region_id_mismatch" in codes
    assert "company_id_identity_mismatch" in codes
    assert "cross_market_fact_leakage" in codes
    assert "ranking_excluded_becoming_eligible" in codes
    assert preview.overall_diff_risk is DiffRisk.BLOCKING


def test_layer33_reports_and_diff_are_read_only(
    tmp_path: Path,
    session: Session,
) -> None:
    _seed_all_markets(session)
    root = _copy_import_root(tmp_path)
    before_counts = _table_counts(session)
    before_files = _file_bytes(root / "nyc")

    for _ in range(2):
        snapshot = build_market_operational_snapshot(
            session,
            "nyc",
            registry_path=root / "markets.json",
            as_of=AS_OF,
        )
        dataset_health_from_snapshot(snapshot)
        source_aging_from_snapshot(snapshot)
        fact_health_from_snapshot(snapshot)
        coverage_gaps_from_snapshot(snapshot)
        ranking_exclusions_from_snapshot(snapshot)
        refresh_readiness_from_snapshot(snapshot)
        build_import_diff_preview(
            session,
            "nyc",
            registry_path=root / "markets.json",
            as_of=AS_OF,
        )

    assert _table_counts(session) == before_counts
    assert _file_bytes(root / "nyc") == before_files
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer33_api_routes_are_schema_shaped_and_public_safe(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)

    health = api_client.get("/markets/imported/health", params={"as_of": AS_OF.isoformat()})
    assert health.status_code == 200
    payload = health.json()["data"]
    assert payload["summary"]["registered_market_count"] == 8
    assert payload["summary"]["healthy_market_count"] >= 1
    assert payload["summary"]["markets_with_limited_coverage"] >= 1
    assert payload["summary"]["overall_health_status"] in {
        MarketHealthStatus.HEALTHY,
        MarketHealthStatus.LIMITED_COVERAGE,
        MarketHealthStatus.NEEDS_REFRESH,
        MarketHealthStatus.STALE_SOURCES,
        MarketHealthStatus.VALIDATION_FAILED,
        MarketHealthStatus.RANKING_LIMITED,
    }
    assert payload["summary"]["highest_priority_maintenance_market"] in EXPECTED_MARKETS
    assert len(payload["markets"]) == 8

    for market_key in sorted(EXPECTED_MARKETS):
        response = api_client.get(
            f"/markets/imported/{market_key}/health",
            params={"as_of": AS_OF.isoformat()},
        )
        assert response.status_code == 200
        assert response.json()["data"]["market_key"] == market_key

    for endpoint in (
        "health",
        "sources",
        "facts",
        "gaps",
        "ranking-diagnostics",
        "refresh-readiness",
        "diff-preview",
    ):
        response = api_client.get(
            f"/markets/imported/nyc/{endpoint}",
            params={"as_of": AS_OF.isoformat()},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        _assert_public_payload_safe(response.json())

    missing = api_client.get(
        "/markets/imported/not_registered/health",
        params={"as_of": AS_OF.isoformat()},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    _assert_public_payload_safe(payload)


def test_layer33_summary_and_payloads_do_not_leak_private_strings(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)

    response = api_client.get(
        "/markets/imported/nyc/ranking-diagnostics",
        params={"as_of": AS_OF.isoformat()},
    )
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)

    _assert_public_payload_safe(payload)
    forbidden_text = (
        "trust_assessment_id",
        "risk_routing_decision_id",
        "reporter_user_id",
        "reporter_session_id",
        "report_reason",
        "raw_internal_risk",
        "Traceback",
        str(REPO_ROOT),
    )
    assert all(token not in serialized for token in forbidden_text)


def test_layer33_boundaries_add_no_scraping_schedulers_or_approval_workflows(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for Layer 33 diagnostics")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)
    _seed_all_markets(session)

    snapshot = build_market_operational_snapshot(session, "nyc", as_of=AS_OF)
    assert dataset_health_from_snapshot(snapshot).validation_ok
    assert build_import_diff_preview(session, "nyc", as_of=AS_OF).validation_ok

    forbidden_imports = {
        "requests",
        "httpx",
        "selenium",
        "playwright",
        "apscheduler",
        "celery",
        "schedule",
    }
    for path in (
        REPO_ROOT / "backend" / "imports" / "operations.py",
        REPO_ROOT / "backend" / "imports" / "diagnostics.py",
        REPO_ROOT / "backend" / "imports" / "diff.py",
        REPO_ROOT / "backend" / "imports" / "schemas.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert forbidden_imports.isdisjoint(imported)

    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def _seed_all_markets(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok


def _readiness(session: Session, market_key: str) -> RefreshReadinessStatus:
    return refresh_readiness_from_snapshot(
        build_market_operational_snapshot(session, market_key, as_of=AS_OF)
    ).readiness_status


def _source(session: Session, source_id: str) -> SourceRef:
    return session.get(SourceRef, source_id)


def _fact_link(session: Session, fact_type: str, fact_id: str) -> FactSourceLink:
    return session.execute(
        select(FactSourceLink).where(
            FactSourceLink.fact_type == fact_type,
            FactSourceLink.fact_id == fact_id,
        )
    ).scalar_one()


def _latest_routing(
    session: Session,
    *,
    subject_type: str,
    subject_id: str,
) -> RiskRoutingDecision:
    return (
        session.execute(
            select(RiskRoutingDecision)
            .where(RiskRoutingDecision.subject_type == subject_type)
            .where(RiskRoutingDecision.subject_id == subject_id)
            .order_by(
                RiskRoutingDecision.decided_at.desc(),
                RiskRoutingDecision.risk_routing_decision_id.desc(),
            )
        )
        .scalars()
        .first()
    )


def _routing_rows(session: Session, market_key: str) -> list[RiskRoutingDecision]:
    prefix = f"src_{market_key}_"
    fact_ids = {
        row.fact_id
        for row in session.query(FactSourceLink).filter(FactSourceLink.source_id.like(f"{prefix}%"))
    }
    return list(
        session.execute(
            select(RiskRoutingDecision)
            .where(RiskRoutingDecision.subject_id.in_(sorted(fact_ids)))
            .order_by(RiskRoutingDecision.subject_id)
        ).scalars()
    )


def _copy_import_root(tmp_path: Path) -> Path:
    root = tmp_path / "imports"
    shutil.copytree(IMPORT_ROOT, root)
    return root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _rewrite_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv_row(path: Path, row: dict[str, str]) -> None:
    rows = _read_csv(path)
    rows.append(row)
    _rewrite_csv(path, rows)


def _update_csv_row(path: Path, row_index: int, updates: dict[str, str]) -> None:
    rows = _read_csv(path)
    rows[row_index].update(updates)
    _rewrite_csv(path, rows)


def _update_source_ref(dataset: Path, source_ref: str, updates: dict[str, str]) -> None:
    path = dataset / "source_refs.csv"
    rows = _read_csv(path)
    for row in rows:
        if row["source_ref"] == source_ref:
            row.update(updates)
            break
    else:
        raise AssertionError(f"source ref not found: {source_ref}")
    _rewrite_csv(path, rows)


def _remove_source_ref(dataset: Path, source_ref: str) -> None:
    path = dataset / "source_refs.csv"
    rows = [row for row in _read_csv(path) if row["source_ref"] != source_ref]
    _rewrite_csv(path, rows)


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
        "trust_assessments": session.query(TrustAssessment).count(),
        "risk_routing_decisions": session.query(RiskRoutingDecision).count(),
    }


def _file_bytes(path: Path) -> dict[str, bytes]:
    return {item.name: item.read_bytes() for item in sorted(path.iterdir()) if item.is_file()}


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def _assert_public_payload_safe(value: Any) -> None:
    forbidden_keys = {
        "assigned_owner",
        "exception_case_id",
        "fact_source_link_id",
        "internal_notes",
        "raw_internal_risk",
        "related_risk_routing_decision_id",
        "related_trust_assessment_id",
        "related_user_report_id",
        "report_reason",
        "reporter_session_id",
        "reporter_user_id",
        "risk_routing_decision_id",
        "source_ref_id",
        "trust_assessment_id",
        "user_report_id",
    }
    assert forbidden_keys.isdisjoint(_keys(value))


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
