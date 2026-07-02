from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.geography.models import Region
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.repository import InstitutionRepository
from backend.outputs.models import OutputMetadata
from backend.platform_intelligence.contributions import ContributionService
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    BenchmarkReport,
    BenchmarkReportRanking,
    ContributionEvidence,
    ContributionReview,
    DataContribution,
    MarketIndex,
    MarketIndexScore,
    MarketIndexVersion,
    MarketSnapshot,
    PredictiveSignal,
)
from backend.platform_intelligence.schemas import (
    ContributionEvidenceCreate,
    ContributionReviewDecision,
    ContributionReviewRequest,
    ContributionStatus,
    ContributionSubmissionRequest,
    ContributionType,
)
from backend.scoring.models import RegionMarketScore
from backend.users.models import (
    ExternalAuthIdentity,
    PersonalizedRecommendationSnapshot,
    User,
    UserProfile,
)

NOW = datetime(2026, 6, 17, 12, tzinfo=UTC)
ISSUER = "https://jmi.us.auth0.com/"


def _repo(session: Session) -> HistoryRepository:
    return HistoryRepository(session)


def _service(session: Session) -> ContributionService:
    return ContributionService(_repo(session), InstitutionRepository(session))


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": ISSUER,
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _seed_user_identity(
    session: Session,
    *,
    user_id: str,
    subject: str,
    admin_role: str | None = None,
) -> None:
    session.add(
        User(
            user_id=user_id,
            status="active",
            admin_role=admin_role,
        )
    )
    session.flush()
    session.add(
        ExternalAuthIdentity(
            external_identity_id=f"identity_{user_id}",
            user_id=user_id,
            provider="auth0",
            issuer=ISSUER,
            subject=subject,
            email=f"{user_id}@example.com",
            email_verified=True,
            last_seen_at=NOW,
        )
    )
    session.add(
        UserProfile(
            user_id=user_id,
            display_name=user_id,
            email=f"{user_id}@example.com",
        )
    )
    session.flush()


def _seed_region_company(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="comp_a",
            company_name="Company A",
            normalized_company_name="company a",
            eligibility_status="eligible",
            sector_primary="ai",
        )
    )
    session.flush()


def _seed_institution_member(
    session: Session,
    *,
    user_id: str,
    role: str = "ADVISOR",
) -> None:
    session.add(
        Organization(
            organization_id="org_career_center",
            name="Career Center",
            organization_type="career_center",
            status="active",
        )
    )
    session.flush()
    session.add(
        OrganizationMembership(
            organization_membership_id=f"membership_{user_id}",
            organization_id="org_career_center",
            user_id=user_id,
            role=role,
            status="active",
        )
    )
    session.flush()


def _basic_submission(**overrides) -> ContributionSubmissionRequest:
    payload = {
        "contribution_id": overrides.pop("contribution_id", "contribution_basic"),
        "target_type": "company",
        "target_id": "comp_a",
        "region_id": "greater_boston",
        "contribution_type": ContributionType.SOURCE_SUGGESTION,
        "structured_payload": {"suggested_source": "public careers page"},
        "summary": "Company source appears outdated.",
        "claimed_confidence": 0.7,
        "created_at": NOW,
        "evidence": (
            ContributionEvidenceCreate(
                evidence_type="url",
                url="https://example.edu/careers",
                description="Public careers page.",
            ),
        ),
    }
    payload.update(overrides)
    return ContributionSubmissionRequest(**payload)


def test_contribution_records_evidence_reviews_and_vocabularies(
    session: Session,
) -> None:
    _seed_region_company(session)
    service = _service(session)
    summary = service.submit_contribution(
        _basic_submission(),
        current_user_id="user_submitter",
    )

    assert summary.status == ContributionStatus.SUBMITTED
    assert session.execute(select(DataContribution)).scalars().all()
    assert session.execute(select(ContributionEvidence)).scalars().all()
    assert ContributionType.values() == {
        "verified_correction",
        "company_presence_update",
        "regional_employer_list",
        "career_center_intelligence",
        "internship_program_information",
        "role_access_feedback",
        "source_suggestion",
        "market_quality_feedback",
        "outdated_data_report",
    }
    assert ContributionStatus.values() == {
        "submitted",
        "needs_review",
        "verified",
        "rejected",
        "merged",
        "superseded",
    }
    with pytest.raises(ValidationError):
        ContributionSubmissionRequest(
            target_type="company",
            target_id="comp_a",
            contribution_type="fake_type",
            summary="Invalid",
        )
    with pytest.raises(ValidationError):
        ContributionEvidenceCreate(
            evidence_type="url",
            url="file:///private/token.txt",
        )
    for unsafe_url in (
        "http://10.0.0.5/internal",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/local",
        "https://internal.local/source",
    ):
        with pytest.raises(ValidationError):
            ContributionEvidenceCreate(
                evidence_type="url",
                url=unsafe_url,
            )

    review = service.review_contribution(
        summary.contribution_id,
        ContributionReviewRequest(
            review_decision=ContributionReviewDecision.NEEDS_REVIEW,
            review_notes="Internal triage note.",
            created_at=NOW,
        ),
        reviewer_id="reviewer_1",
    )
    assert review.resulting_status == ContributionStatus.NEEDS_REVIEW
    assert session.execute(select(ContributionReview)).scalars().all()


def test_authenticated_user_submission_is_safe_and_rejects_unsafe_evidence(
    api_client,
    session: Session,
) -> None:
    _seed_region_company(session)
    response = api_client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|submitter"),
        json={
            "target_type": "company",
            "target_id": "comp_a",
            "region_id": "greater_boston",
            "contribution_type": "outdated_data_report",
            "structured_payload": {"field": "hiring"},
            "summary": "Hiring data looks stale.",
            "claimed_confidence": 0.6,
            "evidence": [
                {
                    "evidence_type": "url",
                    "url": "https://example.com/public-job-board",
                    "description": "Public listing page.",
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["contribution_type"] == "outdated_data_report"
    assert "reviewer" not in json.dumps(data)
    assert "will not change published intelligence" in data["next_step_message"]
    row = session.execute(select(DataContribution)).scalar_one()
    assert row.contributor_type == "user"
    assert row.status == "submitted"

    unsafe = api_client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|submitter"),
        json={
            "target_type": "company",
            "target_id": "comp_a",
            "contribution_type": "source_suggestion",
            "summary": "Unsafe source.",
            "evidence": [
                {
                    "evidence_type": "url",
                    "url": "https://example.com/path?token=secret",
                }
            ],
        },
    )
    assert unsafe.status_code == 422
    assert session.query(DataContribution).count() == 1


def test_institution_contribution_types_require_scoped_membership(
    api_client,
    session: Session,
) -> None:
    _seed_region_company(session)
    _seed_user_identity(
        session,
        user_id="institution_user",
        subject="auth0|institution_user",
    )
    _seed_institution_member(session, user_id="institution_user")

    allowed = api_client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|institution_user"),
        json={
            "institution_id": "org_career_center",
            "target_type": "region",
            "target_id": "greater_boston",
            "region_id": "greater_boston",
            "contribution_type": "career_center_intelligence",
            "structured_payload": {"student_interest": "ai internships"},
            "summary": "Career center sees increased AI internship interest.",
        },
    )
    assert allowed.status_code == 200
    row = session.execute(select(DataContribution)).scalar_one()
    assert row.contributor_type == "institution"
    assert row.institution_id == "org_career_center"

    denied = api_client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|outside_user"),
        json={
            "institution_id": "org_career_center",
            "target_type": "region",
            "target_id": "greater_boston",
            "contribution_type": "regional_employer_list",
            "summary": "Not allowed.",
        },
    )
    assert denied.status_code == 403

    restricted_without_institution = api_client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|outside_user"),
        json={
            "target_type": "region",
            "target_id": "greater_boston",
            "contribution_type": "internship_program_information",
            "summary": "Missing institution.",
        },
    )
    assert restricted_without_institution.status_code == 403


def test_review_queue_and_lifecycle_are_permissioned_and_safe(
    api_client,
    session: Session,
) -> None:
    _seed_region_company(session)
    _seed_user_identity(
        session,
        user_id="reviewer",
        subject="auth0|reviewer",
        admin_role="data_reviewer",
    )
    service = _service(session)
    contribution_ids = []
    for idx, decision in enumerate(("verified", "rejected", "merged", "superseded")):
        summary = service.submit_contribution(
            _basic_submission(
                contribution_id=f"contribution_{decision}",
                summary=f"Contribution for {decision}",
            ),
            current_user_id=f"user_{idx}",
        )
        contribution_ids.append((summary.contribution_id, decision))

    assert api_client.get(
        "/platform/contributions/review",
        headers=_auth_headers("auth0|not_admin"),
    ).status_code == 403
    assert api_client.post(
        f"/platform/contributions/{contribution_ids[0][0]}/review",
        headers=_auth_headers("auth0|not_admin"),
        json={"review_decision": "verified"},
    ).status_code == 403

    queue = api_client.get(
        "/platform/contributions/review",
        headers=_auth_headers("auth0|reviewer"),
    )
    assert queue.status_code == 200
    assert len(queue.json()["data"]["contributions"]) == 4

    for contribution_id, decision in contribution_ids:
        response = api_client.post(
            f"/platform/contributions/{contribution_id}/review",
            headers=_auth_headers("auth0|reviewer"),
            json={
                "review_decision": decision,
                "review_notes": "internal reviewer note: do not expose",
                "canonical_update_candidate_created": decision in {"verified", "merged"},
                "refresh_task_created": decision == "merged",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["review_decision"] == decision
        assert data["resulting_status"] == decision
        assert "review_notes" not in json.dumps(data)

    statuses = {
        row.data_contribution_id: row.status
        for row in session.execute(select(DataContribution)).scalars()
    }
    assert statuses == dict(contribution_ids)
    rejected = session.get(DataContribution, "contribution_rejected")
    assert rejected is not None
    assert rejected.status == "rejected"
    reviews = session.execute(select(ContributionReview)).scalars().all()
    assert any(row.review_notes for row in reviews)


def test_contribution_submission_and_review_do_not_mutate_authority(
    session: Session,
) -> None:
    _seed_region_company(session)
    _seed_user_identity(session, user_id="authority_user", subject="auth0|authority")
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.61,
                early_career_accessibility_score=0.57,
                score_ruleset_version="canonical_v1",
            ),
            OutputMetadata(
                output_id="output_boston",
                output_type="region_output",
                subject_id="greater_boston",
                artifact_hash="stable-output",
            ),
            MarketSnapshot(
                market_snapshot_id="market_snap_authority",
                region_id="greater_boston",
                snapshot_date=date(2026, 1, 1),
                overall_score=0.50,
                created_at=NOW,
            ),
            MarketIndex(
                market_index_id="index_hidden",
                key="hidden_market_opportunity",
                name="Hidden Market Opportunity",
                description="Derived index.",
                status="active",
                created_at=NOW,
            ),
            MarketIndexVersion(
                market_index_version_id="index_hidden_v1",
                index_id="index_hidden",
                version="v1",
                formula_description="Public formula summary.",
                input_schema={},
                internal_weight_config={"secret_weight": 1.0},
                status="active",
                effective_date=date(2026, 1, 1),
                created_at=NOW,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            MarketIndexScore(
                market_index_score_id="index_score_boston",
                index_id="index_hidden",
                index_version_id="index_hidden_v1",
                region_id="greater_boston",
                score=0.71,
                rank=1,
                confidence_score=0.8,
                freshness_state="fresh",
                evidence_summary={"warnings": []},
                calculated_at=NOW,
                created_at=NOW,
            ),
            PredictiveSignal(
                predictive_signal_id="signal_boston",
                signal_type="emerging_market",
                target_type="region",
                target_id="greater_boston",
                region_id="greater_boston",
                signal_strength="weak",
                confidence_level="low",
                evidence_window_start=date(2026, 1, 1),
                evidence_window_end=date(2026, 3, 1),
                snapshot_count=3,
                minimum_snapshot_count_met=True,
                summary="Emerging signal.",
                warnings=[],
                status="active",
                created_at=NOW,
            ),
            BenchmarkReport(
                benchmark_report_id="report_boston",
                report_key="top_emerging_tech_markets",
                title="Top Emerging Tech Markets",
                report_period="2026-Q2",
                report_type="emerging_tech_markets",
                status="published",
                summary="Published report.",
                methodology_summary="Public methodology.",
                data_window_start=date(2026, 1, 1),
                data_window_end=date(2026, 3, 1),
                limitations=[],
                created_at=NOW,
                published_at=NOW,
            ),
            PersonalizedRecommendationSnapshot(
                recommendation_snapshot_id="rec_authority",
                user_id="authority_user",
                personalized_output={"ranked_regions": ["greater_boston"]},
                recommendation_version="rec_v1",
                source_version_bundle={"version": 1},
                objective_output_refs=[{"output_id": "output_boston"}],
                recommendation_inputs_hash="sha256:authority",
                generated_at=NOW,
            ),
        ]
    )
    session.flush()
    session.add(
        BenchmarkReportRanking(
            benchmark_report_ranking_id="report_rank_boston",
            report_id="report_boston",
            region_id="greater_boston",
            rank=1,
            score=0.82,
            index_score_id="index_score_boston",
            explanation="Published ranking.",
            warnings=[],
            confidence_score=0.8,
            freshness_state="fresh",
            created_at=NOW,
        )
    )
    session.flush()

    service = _service(session)
    submission = service.submit_contribution(
        _basic_submission(
            contribution_id="authority_contribution",
            contribution_type=ContributionType.VERIFIED_CORRECTION,
            structured_payload={"new_score": 0.99},
        ),
        current_user_id="authority_user",
    )
    service.review_contribution(
        submission.contribution_id,
        ContributionReviewRequest(
            review_decision=ContributionReviewDecision.VERIFIED,
            canonical_update_candidate_created=True,
            refresh_task_created=True,
            review_notes="Reviewed without mutating authority.",
            created_at=NOW,
        ),
        reviewer_id="reviewer",
    )

    assert session.get(RegionMarketScore, "score_boston").objective_opportunity_score == 0.61
    assert session.get(OutputMetadata, "output_boston").artifact_hash == "stable-output"
    assert session.get(MarketSnapshot, "market_snap_authority").overall_score == 0.50
    assert session.get(MarketIndexScore, "index_score_boston").score == 0.71
    assert session.get(PredictiveSignal, "signal_boston").status == "active"
    assert session.get(PredictiveSignal, "signal_boston").signal_strength == "weak"
    assert session.get(BenchmarkReport, "report_boston").status == "published"
    assert session.get(BenchmarkReportRanking, "report_rank_boston").score == 0.82
    recommendation = session.get(PersonalizedRecommendationSnapshot, "rec_authority")
    assert recommendation.personalized_output == {"ranked_regions": ["greater_boston"]}


def test_public_demo_denies_contribution_writes_but_keeps_safe_gets(
    session: Session,
) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo-contributions.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    denied = client.post(
        "/platform/contributions",
        headers=_auth_headers("auth0|public_demo_submitter"),
        json={
            "target_type": "company",
            "target_id": "comp_a",
            "contribution_type": "source_suggestion",
            "summary": "Not allowed in public demo.",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["type"] == "public_demo_read_only"
    review_queue = client.get(
        "/platform/contributions/review",
        headers=_auth_headers("auth0|public_demo_reviewer"),
    )
    assert review_queue.status_code == 403
    assert review_queue.json()["error"]["type"] == "public_demo_read_only"
    review_write = client.post(
        "/platform/contributions/contribution_1/review",
        headers=_auth_headers("auth0|public_demo_reviewer"),
        json={"review_decision": "verified"},
    )
    assert review_write.status_code == 403
    assert review_write.json()["error"]["type"] == "public_demo_read_only"
    assert session.query(DataContribution).count() == 0
    assert client.get("/platform/reports").status_code == 200
    assert client.get("/platform/indices").status_code == 200
