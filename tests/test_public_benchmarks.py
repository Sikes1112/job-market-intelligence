from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.config.settings import Settings
from backend.public_benchmarks import REQUIRED_PUBLIC_BENCHMARK_SLUGS
from backend.public_benchmarks.registry import (
    get_public_benchmark,
    list_public_benchmarks,
)
from backend.public_benchmarks.schemas import PublicBenchmarkPayload

INTERNAL_ONLY_FIELDS = {
    "source_id",
    "source_ids",
    "raw_source_refs",
    "internal_formula_weights",
    "formula_weights",
    "review_notes",
    "admin_metadata",
    "private_metadata",
    "index_score_id",
    "benchmark_score",
    "recommendation_score",
    "score",
}


def test_public_benchmark_registry_includes_required_templates() -> None:
    payload = list_public_benchmarks()
    slugs = {benchmark.slug for benchmark in payload.benchmarks}

    assert REQUIRED_PUBLIC_BENCHMARK_SLUGS.issubset(slugs)


def test_every_public_benchmark_has_required_public_metadata() -> None:
    payload = list_public_benchmarks()

    for summary in payload.benchmarks:
        benchmark = get_public_benchmark(summary.slug)
        assert benchmark is not None
        assert benchmark.benchmark_id == f"public_benchmark:{benchmark.slug}"
        assert benchmark.slug in REQUIRED_PUBLIC_BENCHMARK_SLUGS
        assert benchmark.methodology_summary
        assert benchmark.limitations
        assert benchmark.freshness_date
        assert benchmark.freshness_status.value == "unknown"
        assert benchmark.confidence.value == "low"
        assert benchmark.warnings is not None
        assert benchmark.source_provenance_summary.source_count >= 1
        assert benchmark.market_results
        assert all(result.result_type == "featured" for result in benchmark.market_results)
        assert all(result.rank is None for result in benchmark.market_results)
        assert all(result.explanation for result in benchmark.market_results)
        assert all(result.warnings for result in benchmark.market_results)
        assert benchmark.suggested_citation.public_path == f"/benchmarks/{benchmark.slug}"
        assert benchmark.suggested_citation.source_name == "Job Market Intelligence"
        assert benchmark.share_summary.public_path == f"/benchmarks/{benchmark.slug}"
        assert "Low confidence" in benchmark.share_summary.confidence_label
        assert "demo-safe" in benchmark.source_authority.labels
        assert "low-confidence" in benchmark.source_authority.labels
        assert benchmark.institutional_cta.link_type == "public_page"


def test_public_benchmark_score_and_subscore_bounds_are_enforced() -> None:
    benchmark = get_public_benchmark("early-career-tech-access-index")
    assert benchmark is not None
    raw = benchmark.model_dump(mode="json")

    raw["market_results"][0]["score_display"]["value"] = 101
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    raw["market_results"][0]["subscores"][0]["value"] = -1
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)


def test_invalid_or_missing_public_benchmark_metadata_is_rejected() -> None:
    benchmark = get_public_benchmark("ai-career-geography-index")
    assert benchmark is not None
    raw = benchmark.model_dump(mode="json")

    raw["methodology_summary"] = "   "
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    del raw["limitations"]
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    raw["confidence"] = "certain"
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    raw["freshness_status"] = "freshish"
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    raw["slug"] = "Not Stable"
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    raw["share_summary"]["public_path"] = "public_benchmark:hidden"
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)


def test_extra_and_internal_only_public_benchmark_fields_are_rejected() -> None:
    benchmark = get_public_benchmark("product-career-market-index")
    assert benchmark is not None
    raw = benchmark.model_dump(mode="json")
    raw["internal_formula_weights"] = {"hidden": 1.0}

    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    for summary in list_public_benchmarks().benchmarks:
        payload = get_public_benchmark(summary.slug)
        assert payload is not None
        found = _find_forbidden_fields(payload.model_dump(mode="json"))
        assert not found, {summary.slug: found}


def test_every_market_result_has_explanation_and_warning_fields() -> None:
    benchmark = get_public_benchmark("early-career-tech-access-index")
    assert benchmark is not None
    raw = benchmark.model_dump(mode="json")

    raw["market_results"][0]["explanation"] = "   "
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)

    raw = benchmark.model_dump(mode="json")
    del raw["market_results"][0]["warnings"]
    with pytest.raises(ValidationError):
        PublicBenchmarkPayload.model_validate(raw)


def test_low_confidence_demo_safe_benchmark_data_is_labeled_clearly() -> None:
    benchmark = get_public_benchmark("ai-career-geography-index")
    assert benchmark is not None

    assert benchmark.confidence.value == "low"
    assert benchmark.source_provenance_summary.data_basis == "demo_template"
    assert any("demo-safe" in warning for warning in benchmark.warnings)
    assert any("not production" in warning for warning in benchmark.warnings)
    assert all(result.confidence.value == "low" for result in benchmark.market_results)
    assert all(
        result.source_provenance_summary.data_basis == "demo_template"
        for result in benchmark.market_results
    )
    assert all(
        "demo" in result.score_display.display_value.lower()
        for result in benchmark.market_results
    )
    assert all(
        any("not production" in warning for warning in result.warnings)
        for result in benchmark.market_results
    )


def test_public_benchmark_citation_share_and_authority_are_public_safe() -> None:
    benchmark = get_public_benchmark("early-career-tech-access-index")
    assert benchmark is not None

    citation = benchmark.suggested_citation.model_dump(mode="json")
    assert set(citation) == {
        "source_name",
        "title",
        "period",
        "product_attribution",
        "public_path",
        "accessed_or_freshness_date",
    }
    assert citation["public_path"] == f"/benchmarks/{benchmark.slug}"
    assert "public_benchmark:" not in " ".join(str(value) for value in citation.values())
    assert benchmark.share_summary.warning.lower().startswith("demo-safe")
    assert benchmark.source_authority.labels[:3] == (
        "demo-safe",
        "low-confidence",
        "methodology-backed",
    )
    assert benchmark.institutional_cta.href.startswith("/")


def test_public_benchmark_api_list_and_detail_routes(api_client: TestClient) -> None:
    list_response = api_client.get("/public/benchmarks")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["status"] == "success"
    slugs = [benchmark["slug"] for benchmark in list_body["data"]["benchmarks"]]
    assert "product-career-market-index" in slugs

    detail_response = api_client.get("/public/benchmarks/product-career-market-index")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["slug"] == "product-career-market-index"
    assert detail["methodology_summary"]
    assert detail["limitations"]
    assert detail["warnings"] is not None
    assert detail["confidence"] == "low"
    assert detail["market_results"][0]["score_display"]["display_value"]
    assert detail["market_results"][0]["subscores"]
    assert detail["source_provenance_summary"]["data_basis"] == "demo_template"
    assert detail["suggested_citation"]["public_path"] == (
        "/benchmarks/product-career-market-index"
    )
    assert detail["share_summary"]["warning"].startswith("Demo-safe")
    assert "demo-safe" in detail["source_authority"]["labels"]
    assert detail["institutional_cta"]["link_type"] == "public_page"


def test_public_benchmark_api_unknown_slug_returns_safe_404(
    api_client: TestClient,
) -> None:
    response = api_client.get("/public/benchmarks/not-a-benchmark")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"
    assert "Public benchmark not found" in body["error"]["message"]


def test_public_demo_allows_public_benchmark_reads(session: Session) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///explicit-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    assert client.get("/public/benchmarks").status_code == 200
    assert client.get("/public/benchmarks/early-career-tech-access-index").status_code == 200
    denied = client.post("/public/benchmarks", json={})
    assert denied.status_code == 403
    assert denied.json()["error"]["type"] == "public_demo_read_only"


def _find_forbidden_fields(value: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in INTERNAL_ONLY_FIELDS:
                found.append(child_path)
            found.extend(_find_forbidden_fields(child, child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_fields(child, f"{path}[{index}]"))
    return found
