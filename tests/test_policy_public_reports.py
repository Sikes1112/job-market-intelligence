from __future__ import annotations

from sqlalchemy.orm import Session

from backend.policy.public_reports import (
    LAYER24_EARLY_CAREER_REPORT_ID,
    LAYER24_EARLY_CAREER_REPORT_TITLE,
    build_early_career_opportunity_report,
)
from backend.policy.service import PolicyIntelligenceService
from tests.policy_strategy_helpers import (
    NOW,
    seed_company_region_signal,
    seed_private_submission,
    seed_region,
)


def _seed_report_region(session: Session) -> None:
    seed_region(session, "policy_report_region", display_name="Policy Report Region")
    for index, postings in enumerate([70, 8, 8, 8, 8]):
        seed_company_region_signal(
            session,
            region_id="policy_report_region",
            company_id=f"policy_report_company_{index}",
            company_name=f"Policy Report Company {index}",
            sector="software" if index < 4 else "ai",
            active_postings=postings,
            internship_count=0,
            coop_count=0,
            entry_level_full_time_count=1 if index == 0 else 0,
            formal_program=False,
        )
    seed_private_submission(
        session,
        region_id="policy_report_region",
        employer_id="policy_report_company_0",
    )


def test_layer24_policy_report_uses_backend_workforce_payload(
    session: Session,
) -> None:
    _seed_report_region(session)
    dashboard = PolicyIntelligenceService(session).build_workforce_dashboard(
        "policy_report_region",
        now=NOW,
    )

    report = build_early_career_opportunity_report(dashboard, now=NOW)

    assert report.title == LAYER24_EARLY_CAREER_REPORT_TITLE
    assert report.slug == "layer-24-early-career-opportunity-policy-report-region"
    assert report.markets_covered[0].market_id == "policy_report_region"
    assert report.market_results[0].market_id == "policy_report_region"
    assert report.source_provenance_summary.data_basis == "public_safe_summary"
    assert report.source_provenance_summary.source_count == dashboard.source_summary.source_count
    assert report.confidence.value in {"low", "medium"}
    assert report.limitations
    assert report.warnings
    assert "backend workforce dashboard payload" in report.methodology_summary


def test_layer24_policy_report_api_exposes_public_report_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_report_region(session)

    response = api_client.get(
        f"/policy/regions/policy_report_region/reports/{LAYER24_EARLY_CAREER_REPORT_ID}"
    )

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["title"] == LAYER24_EARLY_CAREER_REPORT_TITLE
    assert data["methodology_summary"]
    assert data["limitations"]
    assert data["warnings"]
    assert data["source_provenance_summary"]["data_basis"] == "public_safe_summary"
    assert body["metadata"]["confidence"]["level"] == data["confidence"]
    assert body["metadata"]["freshness"]["freshness_status"] == data["freshness_status"]
    assert body["metadata"]["limitations"] == data["limitations"]
    assert body["metadata"]["public_safe"] is True


def test_layer24_policy_report_does_not_expose_private_fields(
    api_client,
    session: Session,
) -> None:
    _seed_report_region(session)

    response = api_client.get(
        f"/policy/regions/policy_report_region/reports/{LAYER24_EARLY_CAREER_REPORT_ID}"
    )

    assert response.status_code == 200
    serialized = str(response.json()).casefold()
    for token in (
        "private_reviewer_id",
        "private reviewer",
        "internal private review note",
        "private_submitter@example.com",
        "raw_submission_json",
        "reviewer_id",
        "review_note",
        "student_id",
        "user_id",
        "tax incentives",
        "will expand",
        "guaranteed",
    ):
        assert token not in serialized
