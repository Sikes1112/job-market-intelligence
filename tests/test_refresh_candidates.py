from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.refresh_quality.candidate_detection import (
    detect_refresh_candidates,
    hiring_count_snapshot_from_record,
    source_refs_from_payload,
)
from backend.refresh_quality.models import (
    RefreshCandidateReason,
    RefreshFactSnapshot,
    SourceRefreshTargetType,
)

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _fact(**overrides) -> RefreshFactSnapshot:
    base = {
        "entity_type": "company_region",
        "entity_id": "company_a::boston",
        "fact_type": "hiring_count",
        "fact_id": "fact_a",
        "current_value": 12,
        "last_updated_at": NOW,
        "freshness_expires_at": NOW + timedelta(days=1),
        "confidence": "high_confidence",
        "source_refs": ("source_a",),
    }
    base.update(overrides)
    return RefreshFactSnapshot(**base)


def test_refresh_candidate_reason_vocabulary_is_complete() -> None:
    assert RefreshCandidateReason.values() == {
        "stale_hiring_count",
        "expired_internship_data",
        "old_company_region_presence_data",
        "low_confidence_source_fact",
        "missing_source_fact",
        "stale_entry_level_signal",
        "coverage_gap",
    }


def test_detects_all_required_refresh_candidate_reasons() -> None:
    facts = [
        _fact(
            fact_id="hiring_stale",
            freshness_expires_at=NOW - timedelta(seconds=1),
            current_value=8,
        ),
        _fact(
            fact_id="internship_expired",
            fact_type="internship_data",
            last_updated_at=NOW - timedelta(days=121),
            freshness_expires_at=None,
            current_value={"internship_count": 2},
            recommended_source_type=SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE,
        ),
        _fact(
            fact_id="presence_old",
            fact_type="company_region_presence",
            last_updated_at=NOW - timedelta(days=181),
            freshness_expires_at=None,
            current_value="present",
        ),
        _fact(
            fact_id="low_confidence",
            fact_type="source_fact",
            confidence="low_confidence",
            freshness_expires_at=None,
        ),
        _fact(
            fact_id="missing_source",
            fact_type="source_fact",
            source_refs=(),
            evidence_context={},
            freshness_expires_at=None,
        ),
        _fact(
            fact_id="entry_level_stale",
            fact_type="entry_level_signal",
            freshness_expires_at=NOW - timedelta(days=1),
            current_value=43.0,
        ),
        _fact(
            fact_id="coverage_gap",
            fact_type="market_coverage",
            coverage_score=25.0,
            current_value={"coverage_tier": "tier_4"},
            freshness_expires_at=None,
        ),
    ]

    candidates = detect_refresh_candidates(facts, now=NOW)
    by_reason = {candidate.reason: candidate for candidate in candidates}

    assert set(by_reason) == set(RefreshCandidateReason)
    assert (
        by_reason[RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA]
        .recommended_source_type
        is SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    )
    missing = by_reason[RefreshCandidateReason.MISSING_SOURCE_FACT]
    assert missing.current_value == 12
    assert missing.last_updated_at == NOW
    assert missing.confidence == "high_confidence"
    assert missing.candidate_key.startswith("refresh_candidate:missing_source_fact:")


def test_detection_is_stable_and_does_not_flag_fresh_sourced_facts() -> None:
    fresh = _fact()

    assert detect_refresh_candidates([fresh], now=NOW) == []

    stale = _fact(freshness_expires_at=NOW - timedelta(seconds=1))
    first = detect_refresh_candidates([stale], now=NOW)
    second = detect_refresh_candidates([stale], now=NOW)

    assert [candidate.candidate_key for candidate in first] == [
        candidate.candidate_key for candidate in second
    ]


def test_source_refs_from_existing_payload_shapes() -> None:
    payload = [
        {"source_id": "source_a", "fact_source_link_id": "link_a"},
        {"source_ids": ["source_b", "source_a"]},
        "source_c",
    ]

    assert source_refs_from_payload(payload) == (
        "source_a",
        "link_a",
        "source_b",
        "source_c",
    )


def test_hiring_snapshot_from_record_uses_existing_read_metadata_only() -> None:
    record = SimpleNamespace(
        hiring_id="hiring_1",
        company_id="company_a",
        region_id="boston",
        active_posting_count_now=6,
        updated_at=NOW - timedelta(days=20),
        freshness_expires_at=NOW - timedelta(days=1),
        hiring_confidence="moderate_confidence",
        source_refs={"source_ids": ["source_hiring"]},
    )

    snapshot = hiring_count_snapshot_from_record(record)

    assert snapshot.entity_type == "company_region"
    assert snapshot.entity_id == "company_a::boston"
    assert snapshot.current_value == 6
    assert snapshot.source_refs == ("source_hiring",)
    assert snapshot.recommended_source_type is SourceRefreshTargetType.COMPANY_CAREERS_PAGE
