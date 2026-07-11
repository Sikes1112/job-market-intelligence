from __future__ import annotations

import socket
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.nyc import import_nyc_dataset, run_nyc_post_import
from backend.outputs.comparison_output import canonical_comparison_id
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.provenance.models import FactSourceLink
from backend.scoring.models import RegionMarketScore
from backend.shared.provenance import ObservationStatus
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    TrustAssessment,
    UserReport,
)

AS_OF = date(2026, 7, 9)


def test_post_import_refresh_runs_and_rebuilds_nyc_outputs(
    session: Session,
) -> None:
    import_result = import_nyc_dataset(session, as_of=AS_OF)
    _seed_peer_region_score(session)

    result = run_nyc_post_import(
        session,
        as_of=AS_OF,
        comparison_region_ids=("greater_boston",),
    )

    assert import_result.ok
    assert result.ok
    assert result.status == "refreshed"
    assert result.counts["trust_assessments"].created == 13
    assert result.counts["risk_routing_decisions"].created == 13
    assert result.counts["region_scores"].created == 1
    assert result.counts["region_outputs"].created == 1
    assert result.counts["company_outputs"].created == 3
    assert result.counts["comparison_outputs"].created == 1

    assert session.query(TrustAssessment).count() == 13
    assert session.query(RiskRoutingDecision).count() == 13
    assert all(label.imported_data for label in result.trust_labels)
    assert all(label.source_backed for label in result.trust_labels)
    assert {label.freshness_label for label in result.trust_labels} == {"Fresh"}
    assert any(
        label.subject_id == "greater_nyc"
        and label.trust_label == "Verified"
        and label.ranking_influence_allowed
        for label in result.trust_labels
    )

    score = _nyc_score(session)
    assert score.structural_ecosystem_score is not None
    assert score.live_market_score is not None
    assert score.source_version_bundle["present_company_count"] == 3
    assert score.source_version_bundle["hiring_record_count"] == 3

    region_output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_nyc",
    )
    assert region_output.cached_payload["region"]["region_id"] == "greater_nyc"
    assert region_output.cached_payload["region"]["summary"]["present_company_count"] == 3
    assert region_output.cached_payload["region"]["scores"] is not None

    comparison_id = canonical_comparison_id("greater_nyc", "greater_boston")
    comparison = _output(
        session,
        output_type=OutputType.COMPARISON_OUTPUT,
        subject_id=comparison_id,
    )
    sides = {
        comparison.cached_payload["comparison"]["region_a"]["region_id"],
        comparison.cached_payload["comparison"]["region_b"]["region_id"],
    }
    assert "greater_nyc" in sides

    _assert_public_payload_safe(region_output.cached_payload)
    _assert_public_payload_safe(comparison.cached_payload)
    for label in result.trust_labels:
        _assert_public_payload_safe(label.as_dict())


def test_post_import_refresh_is_idempotent_and_deterministic(
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    _seed_peer_region_score(session)

    first = run_nyc_post_import(
        session,
        as_of=AS_OF,
        comparison_region_ids=("greater_boston",),
    )
    score_version = _nyc_score(session).version
    output_hash = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_nyc",
    ).artifact_hash
    second = run_nyc_post_import(
        session,
        as_of=AS_OF,
        comparison_region_ids=("greater_boston",),
    )

    assert first.ok and second.ok
    assert second.counts["trust_assessments"].unchanged == 13
    assert second.counts["risk_routing_decisions"].unchanged == 13
    assert second.counts["entry_level_scores"].unchanged == 3
    assert second.counts["region_scores"].unchanged == 1
    assert second.counts["region_outputs"].unchanged == 1
    assert second.counts["company_outputs"].unchanged == 3
    assert second.counts["comparison_outputs"].unchanged == 1
    assert _nyc_score(session).version == score_version
    assert (
        _output(
            session,
            output_type=OutputType.REGION_OUTPUT,
            subject_id="greater_nyc",
        ).artifact_hash
        == output_hash
    )
    assert [label.as_dict() for label in first.trust_labels] == [
        label.as_dict() for label in second.trust_labels
    ]


def test_ranking_ineligible_imported_hiring_does_not_affect_scores(
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    first = run_nyc_post_import(session, as_of=AS_OF)
    baseline_live_market = _nyc_score(session).live_market_score

    link = _fact_link(
        session,
        "company_region_hiring",
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    link.freshness_status = "stale"
    session.flush()

    second = run_nyc_post_import(session, as_of=AS_OF)
    score = _nyc_score(session)
    routing = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    region_output = _output(
        session,
        output_type=OutputType.REGION_OUTPUT,
        subject_id="greater_nyc",
    )
    hiring_ids = {
        item["company_id"]
        for item in region_output.cached_payload["region"]["top_companies_hiring"]
    }

    assert first.ok and second.ok
    assert routing.ranking_influence_allowed is False
    assert routing.trust_tier == "stale"
    assert score.source_version_bundle["hiring_record_count"] == 2
    assert score.live_market_score is not None
    assert baseline_live_market is not None
    assert score.live_market_score < baseline_live_market
    assert "cmp_hudson_applied_ai" not in hiring_ids
    assert any(
        label.subject_id == "hiring_cmp_hudson_applied_ai_greater_nyc"
        and label.freshness_label == "Stale source"
        and not label.ranking_influence_allowed
        for label in second.trust_labels
    )


def test_unknown_and_observed_zero_counts_survive_recompute(
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    result = run_nyc_post_import(session, as_of=AS_OF)

    assert result.ok
    score = _nyc_score(session)
    assert score.source_version_bundle["active_posting_count_status"] == "unknown"

    unknown_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_liberty_cyber_systems_greater_nyc",
    )
    zero_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_brooklyn_cloudworks_greater_nyc",
    )
    positive_hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    unknown_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_liberty_cyber_systems_greater_nyc",
    )
    zero_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_brooklyn_cloudworks_greater_nyc",
    )
    positive_entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_hudson_applied_ai_greater_nyc",
    )

    assert unknown_hiring.active_posting_count_now is None
    assert unknown_hiring.active_posting_count_now_status == ObservationStatus.UNKNOWN
    assert zero_hiring.active_posting_count_now == 0
    assert zero_hiring.active_posting_count_now_status == (
        ObservationStatus.ZERO_OBSERVED
    )
    assert positive_hiring.active_posting_count_now == 5
    assert positive_hiring.active_posting_count_now_status == (
        ObservationStatus.POSITIVE_OBSERVED
    )
    assert unknown_entry.internship_count is None
    assert unknown_entry.internship_count_status == ObservationStatus.UNKNOWN
    assert unknown_entry.entry_level_access_score is None
    assert zero_entry.internship_count == 0
    assert zero_entry.internship_count_status == ObservationStatus.ZERO_OBSERVED
    assert positive_entry.internship_count == 4
    assert positive_entry.internship_count_status == (
        ObservationStatus.POSITIVE_OBSERVED
    )
    assert positive_entry.entry_level_access_score is not None
    assert positive_entry.entry_level_access_score > 0


def test_stale_or_insufficient_provenance_is_denied_ranking(
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    link = _fact_link(
        session,
        "company_region_entry_level",
        "entry_cmp_hudson_applied_ai_greater_nyc",
    )
    link.source_type = "unknown_source"
    session.flush()

    result = run_nyc_post_import(session, as_of=AS_OF)
    routing = _latest_routing(
        session,
        subject_type="data_standard_fact",
        subject_id="entry_cmp_hudson_applied_ai_greater_nyc",
    )

    assert result.ok
    assert routing.ranking_influence_allowed is False
    assert routing.risk_level == "critical"
    assert routing.ranking_influence_decision == "denied"


def test_post_import_requires_no_network_or_manual_approval_workflows(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for curated refresh")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)
    import_nyc_dataset(session, as_of=AS_OF)

    result = run_nyc_post_import(session, as_of=AS_OF)

    assert result.ok
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def _seed_peer_region_score(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="Greater Boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        RegionMarketScore(
            region_score_id="rms_greater_boston",
            region_id="greater_boston",
            structural_ecosystem_score=0.2,
            live_market_score=0.2,
            objective_opportunity_score=0.2,
            raw_total_score=0.2,
            general_density_score=0.2,
            tech_market_density_score=0.2,
            early_career_accessibility_score=0.2,
            score_ruleset_version="peer_fixture",
            source_version_bundle={"fixture": "peer"},
        )
    )
    session.flush()


def _nyc_score(session: Session) -> RegionMarketScore:
    return session.execute(
        select(RegionMarketScore).where(RegionMarketScore.region_id == "greater_nyc")
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
