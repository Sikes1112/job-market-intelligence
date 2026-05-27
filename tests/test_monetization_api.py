from __future__ import annotations


def test_monetization_catalog_endpoints_are_read_only_and_public(api_client) -> None:
    for path, key in (
        ("/monetization/plans", "plans"),
        ("/monetization/features", "features"),
        ("/monetization/reports", "reports"),
    ):
        response = api_client.get(path)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["data"][key]


def test_monetization_access_preview_returns_central_decision(api_client) -> None:
    response = api_client.get(
        "/monetization/access-preview",
        params={
            "plan_key": "free",
            "feature_key": "full_report_generation",
        },
    )

    assert response.status_code == 200
    decision = response.json()["data"]["decision"]
    assert decision["allowed"] is False
    assert decision["plan_key"] == "free"
    assert decision["feature_key"] == "full_report_generation"
    assert decision["upgrade_plan_keys"]


def test_monetization_access_preview_reports_usage_remaining(api_client) -> None:
    response = api_client.get(
        "/monetization/access-preview",
        params={
            "plan_key": "free",
            "feature_key": "limited_comparisons",
            "used": 2,
        },
    )

    assert response.status_code == 200
    decision = response.json()["data"]["decision"]
    assert decision["allowed"] is True
    assert decision["usage_limit"]["limit"] == 3
    assert decision["remaining_usage"] == 1
