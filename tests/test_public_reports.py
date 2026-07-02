from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.config.settings import Settings
from backend.public_reports import REQUIRED_PUBLIC_REPORT_SLUGS
from backend.public_reports.registry import get_public_report, list_public_reports
from backend.public_reports.schemas import PublicReportPayload

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


def test_public_report_registry_includes_required_templates() -> None:
    payload = list_public_reports()
    slugs = {report.slug for report in payload.reports}

    assert REQUIRED_PUBLIC_REPORT_SLUGS.issubset(slugs)


def test_every_public_report_has_required_public_metadata() -> None:
    payload = list_public_reports()

    for summary in payload.reports:
        report = get_public_report(summary.slug)
        assert report is not None
        assert report.report_id == f"public_report:{report.slug}"
        assert report.slug in REQUIRED_PUBLIC_REPORT_SLUGS
        assert report.methodology_summary
        assert report.limitations
        assert report.freshness_date
        assert report.freshness_status.value == "unknown"
        assert report.confidence.value == "low"
        assert report.warnings is not None
        assert report.source_provenance_summary.source_count >= 1
        assert report.markets_covered
        assert report.market_results
        assert all(result.result_type == "featured" for result in report.market_results)
        assert all(result.rank is None for result in report.market_results)
        assert report.suggested_citation.public_path == f"/reports/{report.slug}"
        assert report.suggested_citation.source_name == "Job Market Intelligence"
        assert report.share_summary.public_path == f"/reports/{report.slug}"
        assert "Low confidence" in report.share_summary.confidence_label
        assert "demo-safe" in report.source_authority.labels
        assert "low-confidence" in report.source_authority.labels
        assert report.institutional_cta.link_type == "public_page"


def test_invalid_or_missing_public_report_metadata_is_rejected() -> None:
    report = get_public_report("best-cities-early-career-ai-careers")
    assert report is not None
    raw = report.model_dump(mode="json")

    raw["methodology_summary"] = "   "
    with pytest.raises(ValidationError):
        PublicReportPayload.model_validate(raw)

    raw = report.model_dump(mode="json")
    del raw["confidence"]
    with pytest.raises(ValidationError):
        PublicReportPayload.model_validate(raw)

    raw = report.model_dump(mode="json")
    raw["slug"] = "Not Stable"
    with pytest.raises(ValidationError):
        PublicReportPayload.model_validate(raw)

    raw = report.model_dump(mode="json")
    raw["suggested_citation"]["public_path"] = "public_report:hidden"
    with pytest.raises(ValidationError):
        PublicReportPayload.model_validate(raw)


def test_public_report_payloads_do_not_expose_internal_only_fields() -> None:
    for summary in list_public_reports().reports:
        report = get_public_report(summary.slug)
        assert report is not None
        found = _find_forbidden_fields(report.model_dump(mode="json"))
        assert not found, {summary.slug: found}


def test_public_reports_preserve_public_safe_freshness_confidence_and_provenance() -> None:
    report = get_public_report("hidden-tech-hubs-new-graduates")
    assert report is not None

    assert report.freshness_status.value == "unknown"
    assert report.freshness_date.isoformat() == "2026-06-18"
    assert report.confidence.value == "low"
    assert report.source_provenance_summary.data_basis == "demo_template"
    assert "public priority-market vocabulary" in report.source_provenance_summary.source_categories
    assert (
        "No raw source references are exposed."
        in report.source_provenance_summary.provenance_notes
    )
    assert all(
        result.source_provenance_summary.data_basis == "demo_template"
        for result in report.market_results
    )


def test_public_report_citation_share_and_authority_are_public_safe() -> None:
    report = get_public_report("best-cities-early-career-ai-careers")
    assert report is not None

    citation = report.suggested_citation.model_dump(mode="json")
    assert set(citation) == {
        "source_name",
        "title",
        "period",
        "product_attribution",
        "public_path",
        "accessed_or_freshness_date",
    }
    assert citation["public_path"] == f"/reports/{report.slug}"
    assert "public_report:" not in " ".join(str(value) for value in citation.values())
    assert report.share_summary.warning.lower().startswith("demo-safe")
    assert report.source_authority.labels[:3] == (
        "demo-safe",
        "low-confidence",
        "methodology-backed",
    )
    assert report.institutional_cta.href.startswith("/")


def test_public_report_api_list_and_detail_routes(api_client: TestClient) -> None:
    list_response = api_client.get("/public/reports")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["status"] == "success"
    slugs = [report["slug"] for report in list_body["data"]["reports"]]
    assert "top-product-management-markets" in slugs

    detail_response = api_client.get("/public/reports/top-product-management-markets")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["slug"] == "top-product-management-markets"
    assert detail["methodology_summary"]
    assert detail["limitations"]
    assert detail["warnings"] is not None
    assert detail["confidence"] == "low"
    assert detail["source_provenance_summary"]["data_basis"] == "demo_template"
    assert detail["suggested_citation"]["public_path"] == (
        "/reports/top-product-management-markets"
    )
    assert detail["share_summary"]["warning"].startswith("Demo-safe")
    assert "demo-safe" in detail["source_authority"]["labels"]
    assert detail["institutional_cta"]["link_type"] == "public_page"


def test_public_report_api_unknown_slug_returns_safe_404(api_client: TestClient) -> None:
    response = api_client.get("/public/reports/not-a-report")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"
    assert "Public report not found" in body["error"]["message"]


def test_public_demo_allows_public_report_reads(session: Session) -> None:
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

    assert client.get("/public/reports").status_code == 200
    assert client.get("/public/reports/best-cities-early-career-ai-careers").status_code == 200
    denied = client.post("/public/reports", json={})
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
