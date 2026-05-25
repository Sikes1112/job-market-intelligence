from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from backend.api.metadata import (
    ApiDataBasis,
    ApiFreshnessStatus,
    FreshnessSourceSummary,
    build_freshness_source_summary,
)
from backend.provenance.models import FactSourceLink
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)

NOW = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)


def _link(
    *,
    link_id: str = "link_1",
    source_id: str = "source_1",
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
    collected_at: datetime | None = None,
    confidence: Confidence = Confidence.HIGH,
    observation_status: ObservationStatus = ObservationStatus.POSITIVE_OBSERVED,
) -> FactSourceLink:
    collected = collected_at or datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    return FactSourceLink(
        link_id=link_id,
        observation_id=f"observation_{link_id}",
        source_id=source_id,
        fact_type=FactBindingType.COMPANY.value,
        fact_id="comp_example",
        fact_field=None,
        source_type=SourceType.COMPANY_OFFICIAL.value,
        source_name="Example official source",
        url_or_provider="https://example.test/careers",
        collected_at=collected,
        observed_at=collected,
        license_or_terms_category=LicenseTermsCategory.PUBLIC.value,
        confidence=confidence.value,
        data_origin=data_origin.value,
        observation_status=observation_status.value,
        notes=None,
    )


def test_layer5_metadata_vocabularies_are_stable() -> None:
    assert ApiFreshnessStatus.values() == {
        "fresh",
        "stale",
        "partial",
        "unknown",
        "seeded_demo",
    }
    assert ApiDataBasis.values() == {
        "seeded_demo",
        "real_imported",
        "mixed",
        "unknown",
    }


def test_seeded_demo_data_maps_to_seeded_demo_basis() -> None:
    summary = build_freshness_source_summary(
        [
            _link(
                data_origin=DataOrigin.DEMO_SEED,
                source_id="mvp_demo_seed",
            )
        ],
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )

    assert summary.data_basis is ApiDataBasis.SEEDED_DEMO
    assert summary.freshness_status is ApiFreshnessStatus.SEEDED_DEMO
    assert summary.source_count == 1
    assert summary.low_confidence_warning is not None
    assert "seeded demo" in summary.low_confidence_warning


def test_real_imported_source_backed_data_maps_to_real_imported() -> None:
    summary = build_freshness_source_summary(
        [_link()],
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )

    assert summary.data_basis is ApiDataBasis.REAL_IMPORTED
    assert summary.freshness_status is ApiFreshnessStatus.FRESH
    assert summary.source_count == 1
    assert summary.last_collected_at == datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    assert summary.low_confidence_warning is None


def test_missing_sources_map_conservatively_to_unknown() -> None:
    summary = build_freshness_source_summary(
        [],
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )

    assert summary.data_basis is ApiDataBasis.UNKNOWN
    assert summary.freshness_status is ApiFreshnessStatus.UNKNOWN
    assert summary.source_count == 0
    assert summary.last_collected_at is None
    assert summary.low_confidence_warning is not None


def test_freshness_status_is_not_invented_from_collected_at() -> None:
    summary = build_freshness_source_summary([_link()], now=NOW)

    assert summary.data_basis is ApiDataBasis.REAL_IMPORTED
    assert summary.last_collected_at == datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    assert summary.freshness_status is ApiFreshnessStatus.UNKNOWN
    assert summary.low_confidence_warning is not None


def test_mixed_evidence_maps_to_mixed_basis() -> None:
    summary = build_freshness_source_summary(
        [
            _link(link_id="link_demo", source_id="source_demo", data_origin=DataOrigin.DEMO_SEED),
            _link(
                link_id="link_real",
                source_id="source_real",
                data_origin=DataOrigin.REAL_OBSERVED,
            ),
        ],
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )

    assert summary.data_basis is ApiDataBasis.MIXED
    assert summary.source_count == 2
    assert summary.low_confidence_warning is not None


def test_stale_partial_unknown_and_low_confidence_warnings_are_exposed() -> None:
    stale = build_freshness_source_summary(
        [_link()],
        freshness_expires_at=NOW - timedelta(seconds=1),
        now=NOW,
    )
    partial = build_freshness_source_summary(
        [_link()],
        freshness_expires_at=NOW + timedelta(days=1),
        partial=True,
        now=NOW,
    )
    unknown = build_freshness_source_summary(
        [_link(data_origin=DataOrigin.UNKNOWN_ORIGIN)],
        now=NOW,
    )
    low_confidence = build_freshness_source_summary(
        [_link(confidence=Confidence.LOW)],
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )

    assert stale.freshness_status is ApiFreshnessStatus.STALE
    assert "stale" in (stale.low_confidence_warning or "")
    assert partial.freshness_status is ApiFreshnessStatus.PARTIAL
    assert "partial" in (partial.low_confidence_warning or "")
    assert unknown.data_basis is ApiDataBasis.UNKNOWN
    assert unknown.low_confidence_warning is not None
    assert low_confidence.freshness_status is ApiFreshnessStatus.FRESH
    assert "low confidence" in (low_confidence.low_confidence_warning or "")


def test_response_model_is_serializable_and_stable() -> None:
    summary = FreshnessSourceSummary(
        freshness_status=ApiFreshnessStatus.STALE,
        data_basis=ApiDataBasis.REAL_IMPORTED,
        last_collected_at=NOW,
        source_count=2,
        low_confidence_warning="Source freshness is stale.",
    )

    dumped = summary.model_dump(mode="json")
    assert set(dumped) == {
        "freshness_status",
        "data_basis",
        "last_collected_at",
        "source_count",
        "low_confidence_warning",
    }
    assert dumped["freshness_status"] == "stale"
    assert dumped["data_basis"] == "real_imported"
    assert dumped["last_collected_at"] == "2026-05-21T12:00:00Z"
    json.dumps(dumped)


def test_coverage_metadata_route_exposes_canonical_vocabulary(api_client) -> None:
    response = api_client.get("/metadata/coverage")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["heuristic"] is True
    assert data["quality_score_bounds"] == {"min": 0.0, "max": 1.0}
    assert data["score_components"] == [
        "company_coverage",
        "hiring_coverage",
        "entry_level_coverage",
        "freshness",
        "source_diversity",
        "confidence",
    ]
    assert [tier["tier"] for tier in data["coverage_tiers"]] == [
        "tier_1",
        "tier_2",
        "tier_3",
        "tier_4",
    ]
    assert {
        tier["tier"]: tier["should_rank_as_confident_recommendation"]
        for tier in data["coverage_tiers"]
    } == {
        "tier_1": True,
        "tier_2": False,
        "tier_3": False,
        "tier_4": False,
    }
    assert {item["sector"] for item in data["sector_coverage_categories"]} == {
        "ai",
        "cloud",
        "cybersecurity",
        "fintech",
        "healthtech",
        "edtech",
        "enterprise_saas",
        "public_sector_tech",
        "defense_tech",
        "consumer_tech",
    }
    assert [market["display_name"] for market in data["priority_markets"]][:4] == [
        "NYC",
        "Seattle",
        "Austin",
        "DC / NoVA",
    ]
