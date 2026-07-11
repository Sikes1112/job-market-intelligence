from __future__ import annotations

import socket
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.imports.post_import import run_curated_market_post_import
from backend.imports.service import import_curated_market_dataset
from backend.outputs.comparison_output import canonical_comparison_id
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.provenance.models import FactSourceLink
from backend.scoring.models import RegionMarketScore
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    TrustAssessment,
    UserReport,
)

AS_OF = date(2026, 7, 9)


def test_generic_post_import_refresh_works_for_nyc_and_seattle(
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "nyc", as_of=AS_OF).ok
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok

    nyc = run_curated_market_post_import(
        session,
        "nyc",
        as_of=AS_OF,
        comparison_region_ids=("greater_seattle",),
    )
    seattle = run_curated_market_post_import(
        session,
        "seattle",
        as_of=AS_OF,
        comparison_region_ids=("greater_nyc",),
    )

    assert nyc.ok and seattle.ok
    assert _score(session, "greater_nyc").source_version_bundle[
        "present_company_count"
    ] == 3
    assert _score(session, "greater_seattle").source_version_bundle[
        "present_company_count"
    ] == 3
    assert _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_nyc",
    ).cached_payload["region"]["import_metadata"]["imported_data_label"] == (
        "Real imported data"
    )
    seattle_output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_seattle",
    )
    assert seattle_output.cached_payload["region"]["region_id"] == "greater_seattle"
    assert seattle_output.cached_payload["region"]["import_metadata"][
        "source_label"
    ] == "Source-backed"

    comparison_id = canonical_comparison_id("greater_nyc", "greater_seattle")
    comparison = _output(
        session,
        output_type=OutputType.COMPARISON_OUTPUT,
        subject_id=comparison_id,
    )
    sides = {
        comparison.cached_payload["comparison"]["region_a"]["region_id"],
        comparison.cached_payload["comparison"]["region_b"]["region_id"],
    }
    assert sides == {"greater_nyc", "greater_seattle"}
    _assert_public_payload_safe(seattle_output.cached_payload)
    _assert_public_payload_safe(comparison.cached_payload)


def test_seattle_post_import_refresh_is_idempotent(session: Session) -> None:
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok

    first = run_curated_market_post_import(session, "seattle", as_of=AS_OF)
    score_version = _score(session, "greater_seattle").version
    output_hash = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_seattle",
    ).artifact_hash
    second = run_curated_market_post_import(session, "seattle", as_of=AS_OF)

    assert first.ok and second.ok
    assert first.counts["trust_assessments"].created == 13
    assert first.counts["risk_routing_decisions"].created == 13
    assert second.counts["trust_assessments"].unchanged == 13
    assert second.counts["risk_routing_decisions"].unchanged == 13
    assert second.counts["entry_level_scores"].unchanged == 3
    assert second.counts["region_scores"].unchanged == 1
    assert second.counts["region_outputs"].unchanged == 1
    assert second.counts["company_outputs"].unchanged == 3
    assert _score(session, "greater_seattle").version == score_version
    assert _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_seattle",
    ).artifact_hash == output_hash


def test_seattle_ranking_denial_does_not_change_nyc_score(
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "nyc", as_of=AS_OF).ok
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok
    assert run_curated_market_post_import(session, "nyc", as_of=AS_OF).ok
    assert run_curated_market_post_import(session, "seattle", as_of=AS_OF).ok
    nyc_score_before = _score(session, "greater_nyc").live_market_score

    link = _fact_link(
        session,
        "company_region_hiring",
        "hiring_cmp_hudson_applied_ai_greater_seattle",
    )
    link.freshness_status = "stale"
    session.flush()

    result = run_curated_market_post_import(session, "seattle", as_of=AS_OF)
    seattle_score = _score(session, "greater_seattle")
    seattle_routing = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="hiring_cmp_hudson_applied_ai_greater_seattle",
    )
    nyc_routing = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    seattle_output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_seattle",
    )
    seattle_hiring_ids = {
        item["company_id"]
        for item in seattle_output.cached_payload["region"]["top_companies_hiring"]
    }

    assert result.ok
    assert seattle_routing.ranking_influence_allowed is False
    assert seattle_routing.trust_tier == "stale"
    assert nyc_routing.ranking_influence_allowed is True
    assert _score(session, "greater_nyc").live_market_score == nyc_score_before
    assert seattle_score.source_version_bundle["hiring_record_count"] == 2
    assert "cmp_hudson_applied_ai" not in seattle_hiring_ids


def test_seattle_output_preserves_unknown_and_zero_semantics(
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok
    result = run_curated_market_post_import(session, "seattle", as_of=AS_OF)

    output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_seattle",
    ).cached_payload
    hiring = {
        row["company_id"]: row
        for row in output["region"]["top_companies_hiring"]
    }
    entry_summary = output["region"]["entry_level_summary"]

    assert result.ok
    assert hiring["cmp_cascade_cloud_labs"]["active_posting_count_now"] == 0
    assert hiring["cmp_cascade_cloud_labs"][
        "active_posting_count_now_status"
    ] == "zero_observed"
    assert hiring["cmp_sound_security_systems"]["active_posting_count_now"] is None
    assert hiring["cmp_sound_security_systems"][
        "active_posting_count_now_status"
    ] == "unknown"
    assert entry_summary["internship_count_total"] is None
    assert entry_summary["internship_count_total_status"] == "unknown"
    assert entry_summary["coop_count_total"] is None
    assert entry_summary["coop_count_total_status"] == "not_applicable"


def test_multi_market_public_payloads_do_not_leak_internal_fields(
    session: Session,
) -> None:
    assert import_curated_market_dataset(session, "nyc", as_of=AS_OF).ok
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok
    assert run_curated_market_post_import(
        session,
        "nyc",
        as_of=AS_OF,
        comparison_region_ids=("greater_seattle",),
    ).ok
    assert run_curated_market_post_import(
        session,
        "seattle",
        as_of=AS_OF,
        comparison_region_ids=("greater_nyc",),
    ).ok

    for output in session.query(OutputMetadata).all():
        _assert_public_payload_safe(output.cached_payload)
    assert session.query(TrustAssessment).count() > 0
    assert session.query(RiskRoutingDecision).count() > 0


def test_multi_market_post_import_uses_no_network_or_manual_approval(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for curated refresh")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)
    assert import_curated_market_dataset(session, "seattle", as_of=AS_OF).ok

    result = run_curated_market_post_import(session, "seattle", as_of=AS_OF)

    assert result.ok
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def _score(session: Session, region_id: str) -> RegionMarketScore:
    return session.execute(
        select(RegionMarketScore).where(RegionMarketScore.region_id == region_id)
    ).scalar_one()


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
