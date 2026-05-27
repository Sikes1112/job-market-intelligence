from __future__ import annotations

from backend.monetization.features import FeatureBoundary, feature_definition
from backend.monetization.reports import ReportProductKey, report_product_definitions


def test_required_report_products_exist_with_preview_and_sections() -> None:
    reports = {report.report_key: report for report in report_product_definitions()}

    assert set(reports) == {
        ReportProductKey.PERSONALIZED_MARKET_STRATEGY_REPORT,
        ReportProductKey.REGION_COMPARISON_REPORT,
        ReportProductKey.COMPANY_GEOGRAPHY_REPORT,
        ReportProductKey.EARLY_CAREER_OPPORTUNITY_REPORT,
    }
    for report in reports.values():
        assert report.display_name
        assert report.intended_segments
        assert report.free_preview_available
        assert report.preview_feature_key is not None
        assert report.included_sections
        assert report.exportable


def test_report_catalog_maps_full_reports_to_paid_entitlement_features() -> None:
    for report in report_product_definitions():
        assert report.paid_full_report_required
        for feature_key in report.paid_full_report_feature_keys:
            assert feature_definition(feature_key).boundary is FeatureBoundary.PAID


def test_report_previews_use_free_features() -> None:
    for report in report_product_definitions():
        assert report.preview_feature_key is not None
        assert feature_definition(report.preview_feature_key).boundary is FeatureBoundary.FREE

