from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog
from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.data_standards.models import (
    DataStandardCandidateFactRecord,
    DataStandardCandidateReviewRecord,
    DataStandardCanonicalMergeRecord,
    DataStandardPartnerSubmissionRecord,
)
from backend.data_standards.schemas import (
    CandidateReviewRequest,
    CanonicalMergeRequest,
    SubmissionReviewLifecycleState,
)
from backend.data_standards.service import (
    PARTNER_SCHEMA_VERSION,
    CandidateReviewWorkflowError,
    CanonicalMergeBlocked,
    DataStandardsService,
    PartnerSubmissionReviewLifecycleError,
    PartnerSubmissionValidationFailed,
)
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.users.models import User

NOW = datetime(2026, 7, 1, 12, tzinfo=UTC)

CANONICAL_TABLES = (
    "companies",
    "regions",
    "company_region_presence",
    "company_region_hiring",
    "region_market_scores",
    "source_refs",
    "source_observations",
    "fact_source_links",
    "admin_event_logs",
)


def _submission(
    submission_id: str = "sub_layer28",
    *,
    partner_id: str = "partner_career_platform",
) -> dict[str, Any]:
    return {
        "submission_id": submission_id,
        "partner_id": partner_id,
        "submitted_at": "2026-07-01T12:00:00Z",
        "schema_version": PARTNER_SCHEMA_VERSION,
        "submitter_type": "employer",
        "records": [
            {
                "record_id": "rec_company",
                "record_type": "company",
                "payload": {
                    "company_name": "Acme AI",
                    "company_website": "https://acme.example",
                    "sector_primary": "software",
                },
                "source_ref_ids": ["src_acme"],
            },
            {
                "record_id": "rec_region",
                "record_type": "region",
                "payload": {
                    "region_name": "Greater Boston",
                    "country_code": "US",
                    "region_type": "metro",
                },
                "source_ref_ids": ["src_acme"],
            },
        ],
        "source_refs": [
            {
                "source_ref_id": "src_acme",
                "source_type": "employer_official",
                "url": "https://acme.example/careers",
                "collected_at": "2026-07-01T10:00:00Z",
                "license_or_terms_category": "partner_terms",
            }
        ],
        "freshness": {
            "freshness_status": "fresh",
            "observed_at": "2026-07-01T10:00:00Z",
            "freshness_expires_at": "2026-08-01T10:00:00Z",
        },
        "confidence": {
            "confidence_label": "high",
            "confidence_score": 0.91,
            "rationale": "Official source supplied by partner.",
        },
    }


def _hiring_submission(
    submission_id: str,
    *,
    partner_id: str = "partner_career_platform",
    company_name: str = "Partner Co",
    region_name: str = "Greater Boston",
    active_posting_count_now: int = 40,
    freshness_status: str = "fresh",
) -> dict[str, Any]:
    return {
        "submission_id": submission_id,
        "partner_id": partner_id,
        "submitted_at": "2026-07-01T12:00:00Z",
        "schema_version": PARTNER_SCHEMA_VERSION,
        "submitter_type": "data_vendor",
        "records": [
            {
                "record_id": "rec_hiring",
                "record_type": "hiring_signal",
                "payload": {
                    "company_name": company_name,
                    "region_name": region_name,
                    "signal_type": "active_postings",
                    "observed_at": "2026-07-01T10:00:00Z",
                    "active_posting_count_now": active_posting_count_now,
                },
                "source_ref_ids": ["src_acme"],
            }
        ],
        "source_refs": [
            {
                "source_ref_id": "src_acme",
                "source_type": "employer_official",
                "url": "https://acme.example/careers",
                "collected_at": "2026-07-01T10:00:00Z",
                "license_or_terms_category": "partner_terms",
            }
        ],
        "freshness": {
            "freshness_status": freshness_status,
            "observed_at": "2026-07-01T10:00:00Z",
            "freshness_expires_at": "2026-08-01T10:00:00Z",
        },
        "confidence": {
            "confidence_label": "high",
            "confidence_score": 0.91,
            "rationale": "Official source supplied by partner.",
        },
    }


def _counts(session: Session) -> dict[str, int]:
    return {
        table_name: session.execute(
            text(f"select count(*) from {table_name}")
        ).scalar_one()
        for table_name in CANONICAL_TABLES
    }


def _service_with_candidates(
    session: Session,
    submission_id: str = "sub_layer28",
) -> tuple[DataStandardsService, str]:
    service = DataStandardsService(session)
    service.create_submission(_submission(submission_id))
    candidates = service.create_candidates_from_submission(submission_id).candidates
    company_candidate = next(
        candidate for candidate in candidates if candidate.record_id == "rec_company"
    )
    return service, company_candidate.candidate_fact_id


def _review_request(
    decision: str = "approve_candidate",
    *,
    reviewer_id: str = "reviewer_28",
    reason: str = "Layer 28 source and partner context checked.",
    reviewed_at: datetime = NOW,
    source_basis: dict[str, Any] | None = None,
    before_after_diff: dict[str, Any] | None = None,
) -> CandidateReviewRequest:
    return CandidateReviewRequest(
        decision=decision,
        reviewer_id=reviewer_id,
        reviewer_name="Layer Reviewer",
        reason=reason,
        decision_notes="Source and partner context checked.",
        source_basis=source_basis
        or {
            "source_ref_ids": ["src_acme"],
            "license_or_terms_category": "partner_terms",
        },
        before_after_diff=before_after_diff or {},
        reviewed_at=reviewed_at,
    )


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _assign_role(
    api_client: TestClient,
    session: Session,
    role: AdminRole | None,
    *,
    subject: str,
) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if role is not None else None
    session.flush()
    return headers, user_id


def test_validation_to_candidate_creation_isolated_from_canonical_tables(
    session: Session,
) -> None:
    service = DataStandardsService(session)
    service.create_submission(_submission())
    before = _counts(session)

    candidates = service.create_candidates_from_submission("sub_layer28")
    after = _counts(session)

    assert after == before
    assert len(candidates.candidates) == 2
    company_candidate = next(
        candidate for candidate in candidates.candidates if candidate.record_id == "rec_company"
    )
    assert company_candidate.candidate_state == "pending_review"
    assert company_candidate.canonical_target_type == "company"
    assert company_candidate.provenance.partner.partner_id == "partner_career_platform"
    assert company_candidate.provenance.partner.trust_tier == "tier_3_verified_platform"
    assert company_candidate.provenance.source_refs[0].source_ref_id == "src_acme"
    assert company_candidate.provenance.provenance_complete is True
    assert company_candidate.provenance.ranking_influence_allowed is False
    assert session.query(DataStandardCandidateFactRecord).count() == 2


def test_submission_lifecycle_states_and_candidate_creation_guard(
    session: Session,
) -> None:
    required = {
        "submitted",
        "validation_failed",
        "validation_passed",
        "under_review",
        "needs_changes",
        "accepted_as_candidate",
        "rejected",
        "merged",
        "superseded",
        "withdrawn",
    }
    assert required == {state.value for state in SubmissionReviewLifecycleState}

    service = DataStandardsService(session)
    service.create_submission(_submission("sub_layer28_lifecycle"))
    row = session.get(DataStandardPartnerSubmissionRecord, "sub_layer28_lifecycle")
    assert row is not None
    assert row.review_lifecycle_state == "validation_passed"
    with pytest.raises(PartnerSubmissionReviewLifecycleError):
        service.transition_submission_lifecycle(
            "sub_layer28_lifecycle",
            "merged",
            actor="reviewer_28",
            reason="invalid direct merge",
        )

    before = _counts(session)
    service.create_candidates_from_submission("sub_layer28_lifecycle")
    after = _counts(session)
    assert after == before
    assert row.review_lifecycle_state == "accepted_as_candidate"
    assert any(
        entry["state"] == "accepted_as_candidate"
        for entry in row.review_state_history_json
    )

    template = _submission("sub_template")
    blocked_states = [
        ("sub_submitted_only", "received", "submitted"),
        ("sub_validation_failed", "rejected", "validation_failed"),
        ("sub_rejected", "validated", "rejected"),
        ("sub_withdrawn", "validated", "withdrawn"),
        ("sub_superseded", "validated", "superseded"),
    ]
    for submission_id, validation_status, lifecycle_state in blocked_states:
        session.add(
            DataStandardPartnerSubmissionRecord(
                partner_submission_id=submission_id,
                partner_id=template["partner_id"],
                submitted_at=NOW,
                schema_version=PARTNER_SCHEMA_VERSION,
                submitter_type=template["submitter_type"],
                validation_status=validation_status,
                review_lifecycle_state=lifecycle_state,
                review_state_history_json=[
                    {
                        "state": lifecycle_state,
                        "actor": "fixture",
                        "reason": "blocked state fixture",
                        "at": NOW.isoformat(),
                    }
                ],
                records_json=template["records"],
                source_refs_json=template["source_refs"],
                freshness_json=template["freshness"],
                confidence_json=template["confidence"],
                warnings_json=[],
                validation_errors_json=[],
                raw_submission_json=template,
            )
        )
    session.flush()
    for submission_id, _validation_status, _lifecycle_state in blocked_states:
        with pytest.raises(PartnerSubmissionReviewLifecycleError):
            service.create_candidates_from_submission(submission_id)


def test_partner_permissions_block_unallowed_candidate_creation(
    session: Session,
) -> None:
    payload = _submission(
        "sub_layer28_permission",
        partner_id="partner_state_university",
    )
    before = _counts(session)

    result = DataStandardsService().validate_submission(payload)

    assert result.validation_status.value == "rejected"
    assert "partner_submission_type_not_permitted" in {
        error.code for error in result.errors
    }
    with pytest.raises(PartnerSubmissionValidationFailed):
        DataStandardsService(session).create_submission(payload)
    assert _counts(session) == before


def test_reviewer_decision_records_state_without_canonical_mutation(
    session: Session,
) -> None:
    service, candidate_id = _service_with_candidates(session)
    before = _counts(session)

    review = service.review_candidate_fact(
        candidate_id,
        _review_request(),
    )
    after = _counts(session)

    assert {
        table: count
        for table, count in after.items()
        if table != "admin_event_logs"
    } == {
        table: count
        for table, count in before.items()
        if table != "admin_event_logs"
    }
    assert after["admin_event_logs"] == before["admin_event_logs"] + 1
    assert review.resulting_candidate_state == "approved_for_merge"
    assert review.audit_event_id
    assert review.reason == "Layer 28 source and partner context checked."
    review_row = session.query(DataStandardCandidateReviewRecord).one()
    assert review_row.reviewer_id == "reviewer_28"
    assert review_row.audit_event_id == review.audit_event_id
    assert review_row.provenance_snapshot_json["source_refs"][0]["source_ref_id"] == (
        "src_acme"
    )
    assert review_row.ranking_influence_allowed is False
    candidate = next(
        item
        for item in service.list_candidates_for_submission("sub_layer28").candidates
        if item.candidate_fact_id == candidate_id
    )
    assert candidate.candidate_state == "approved_for_merge"


def test_reviewer_actions_require_context_create_audit_and_block_merge(
    session: Session,
) -> None:
    service, candidate_id = _service_with_candidates(session, "sub_layer28_review_context")

    with pytest.raises(ValueError):
        CandidateReviewRequest(
            decision="approve_candidate",
            reviewer_id="reviewer_28",
            decision_notes="missing reason",
            source_basis={"source_ref_ids": ["src_acme"]},
        )
    with pytest.raises(ValueError):
        CandidateReviewRequest(
            decision="approve_candidate",
            reviewer_id="reviewer_28",
            reason="missing source basis",
            decision_notes="notes",
            source_basis={},
        )

    for decision in ("mark_duplicate", "mark_low_confidence", "escalate"):
        review = service.review_candidate_fact(
            candidate_id,
            _review_request(
                decision,
                reason=f"{decision} requires explicit resolution.",
                before_after_diff={
                    "before": {"state": "pending_review"},
                    "after": {"decision": decision},
                },
            ),
        )
        assert review.audit_event_id
        preview = service.preview_canonical_merge(candidate_id)
        assert preview.can_merge is False
        assert "candidate_not_approved_for_merge" in preview.blockers

    assert session.query(AdminEventLog).count() == 3


def test_controlled_merge_binds_provenance_audits_and_keeps_ranking_false(
    session: Session,
) -> None:
    session.add(
        Region(
            region_id="seed_region",
            region_name="seed_region",
            display_name="Seed Region",
            region_type="metro",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id="score_seed",
            region_id="seed_region",
            objective_opportunity_score=0.72,
            early_career_accessibility_score=0.64,
            score_ruleset_version="canonical_v1",
        )
    )
    session.flush()
    service, candidate_id = _service_with_candidates(session, "sub_layer28_merge")
    service.review_candidate_fact(
        candidate_id,
        _review_request(),
    )

    preview = service.preview_canonical_merge(candidate_id)
    result = service.merge_candidate_fact(
        candidate_id,
        CanonicalMergeRequest(
            merged_by="admin_28",
            reason="Reviewed candidate passed controlled merge.",
            merged_at=NOW,
        ),
    )

    assert preview.can_merge is True
    assert preview.action == "create"
    assert result.status == "merged"
    assert result.action == "create"
    assert result.ranking_influence_allowed is False
    assert session.get(Company, preview.canonical_target_id).company_name == "Acme AI"
    assert session.query(SourceRef).count() == 1
    assert session.query(SourceObservation).count() == 1
    assert session.query(FactSourceLink).count() == 1
    assert session.query(AdminEventLog).count() == 2
    merge_row = session.query(DataStandardCanonicalMergeRecord).one()
    assert merge_row.ranking_influence_allowed is False
    assert merge_row.review_decision_id
    assert merge_row.provenance_binding_json["review_decision_id"] == (
        merge_row.review_decision_id
    )
    score = session.get(RegionMarketScore, "score_seed")
    assert score.objective_opportunity_score == 0.72
    assert score.early_career_accessibility_score == 0.64
    merged_candidate = next(
        item
        for item in service.list_candidates_for_submission(
            "sub_layer28_merge"
        ).candidates
        if item.candidate_fact_id == candidate_id
    )
    assert merged_candidate.candidate_state == "merged"


def test_conflict_detection_blocks_false_integration_merge(session: Session) -> None:
    service, candidate_id = _service_with_candidates(session, "sub_layer28_conflict")
    candidate = session.get(DataStandardCandidateFactRecord, candidate_id)
    assert candidate is not None
    session.add(
        Company(
            company_id=candidate.canonical_target_id,
            company_name="Different Company",
            normalized_company_name="different company",
            sector_primary="finance",
        )
    )
    session.flush()
    service.review_candidate_fact(
        candidate_id,
        _review_request(),
    )

    preview = service.preview_canonical_merge(candidate_id)

    assert preview.can_merge is False
    assert {conflict.code for conflict in preview.conflicts} == {
        "canonical_value_mismatch",
    }
    with pytest.raises(CanonicalMergeBlocked):
        service.merge_candidate_fact(
            candidate_id,
            CanonicalMergeRequest(
                merged_by="admin_28",
                reason="Should be blocked.",
                merged_at=NOW,
            ),
        )
    assert session.query(AdminEventLog).count() == 1
    assert session.get(Company, candidate.canonical_target_id).company_name == (
        "Different Company"
    )


def test_provenance_completeness_is_enforced_before_approval_and_merge(
    session: Session,
) -> None:
    service = DataStandardsService(session)
    service.create_submission(_submission("sub_layer28_incomplete"))
    row = DataStandardCandidateFactRecord(
        candidate_fact_id="candidate_incomplete",
        partner_submission_id="sub_layer28_incomplete",
        partner_id="partner_acme_employer",
        partner_name="Acme Employer Programs",
        partner_type="employer",
        partner_verification_status="unverified",
        partner_trust_tier="tier_4_limited_partner",
        submitter_type="employer",
        submitted_at=NOW,
        record_id="rec_incomplete",
        record_type="company",
        candidate_state="pending_review",
        canonical_target_type="company",
        canonical_target_id="company_incomplete",
        canonical_target_key_json={"normalized_company_name": "incomplete"},
        fact_payload_json={
            "company_id": "company_incomplete",
            "company_name": "Incomplete",
            "normalized_company_name": "incomplete",
        },
        source_refs_json=[],
        freshness_json={"freshness_status": "fresh"},
        confidence_json={"confidence_label": "high"},
        provenance_complete=False,
        provenance_warnings_json=["source_refs_missing"],
        raw_record_json={"record_id": "rec_incomplete", "record_type": "company"},
        ranking_influence_allowed=False,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(row)
    session.flush()

    with pytest.raises(CandidateReviewWorkflowError):
        service.review_candidate_fact(
            "candidate_incomplete",
            _review_request(),
        )
    preview = service.preview_canonical_merge("candidate_incomplete")
    assert preview.can_merge is False
    assert "provenance_incomplete" in preview.blockers
    assert session.get(Company, "company_incomplete") is None


def test_missing_license_terms_blocks_approval_until_reviewer_source_basis(
    session: Session,
) -> None:
    payload = _submission("sub_layer28_missing_license")
    payload["source_refs"][0].pop("license_or_terms_category")
    service = DataStandardsService(session)
    service.create_submission(payload)
    candidate = next(
        item
        for item in service.create_candidates_from_submission(
            "sub_layer28_missing_license"
        ).candidates
        if item.record_id == "rec_company"
    )

    with pytest.raises(CandidateReviewWorkflowError):
        service.review_candidate_fact(
            candidate.candidate_fact_id,
            _review_request(
                source_basis={"source_ref_ids": ["src_acme"]},
            ),
        )

    review = service.review_candidate_fact(
        candidate.candidate_fact_id,
        _review_request(
            source_basis={
                "source_ref_ids": ["src_acme"],
                "license_or_terms_category": "reviewed_partner_terms",
            },
        ),
    )
    preview = service.preview_canonical_merge(candidate.candidate_fact_id)
    assert review.resulting_candidate_state == "approved_for_merge"
    assert "license_or_terms_category_missing" not in preview.blockers


def test_stale_lower_trust_and_numeric_conflicts_require_explicit_resolution(
    session: Session,
) -> None:
    service = DataStandardsService(session)
    service.create_submission(
        _hiring_submission(
            "sub_layer28_conflict_complete",
            partner_id="partner_acme_employer",
            active_posting_count_now=40,
            freshness_status="stale",
        )
    )
    candidate = service.create_candidates_from_submission(
        "sub_layer28_conflict_complete"
    ).candidates[0]
    row = session.get(DataStandardCandidateFactRecord, candidate.candidate_fact_id)
    assert row is not None
    payload = row.fact_payload_json
    session.add_all(
        [
            Company(
                company_id=payload["company_id"],
                company_name=payload["company_name"],
                normalized_company_name=payload["company_name"].casefold(),
            ),
            Region(
                region_id=payload["region_id"],
                region_name=payload["region_name"].casefold().replace(" ", "_"),
                display_name=payload["region_name"],
                region_type="metro",
            ),
            CompanyRegionHiring(
                hiring_id=row.canonical_target_id,
                company_id=payload["company_id"],
                region_id=payload["region_id"],
                currently_hiring_flag=True,
                active_posting_count_now=5,
            ),
            SourceRef(
                source_id="source_existing_hiring",
                source_type="public_agency",
                source_name="Public Agency",
                url_or_provider="https://agency.example/hiring",
                collected_at=NOW,
                observed_at=NOW,
                license_or_terms_category="public",
                confidence="high",
                data_origin="real_observed",
            ),
            SourceObservation(
                observation_id="obs_existing_hiring",
                source_id="source_existing_hiring",
                source_type="public_agency",
                source_name="Public Agency",
                url_or_provider="https://agency.example/hiring",
                collected_at=NOW,
                observed_at=NOW,
                license_or_terms_category="public",
                confidence="high",
                data_origin="real_observed",
                observation_status="active",
            ),
            FactSourceLink(
                link_id="fsl_existing_hiring",
                observation_id="obs_existing_hiring",
                source_id="source_existing_hiring",
                fact_type="company_region_hiring",
                fact_id=row.canonical_target_id,
                source_type="public_agency",
                source_name="Public Agency",
                url_or_provider="https://agency.example/hiring",
                collected_at=NOW,
                observed_at=NOW,
                license_or_terms_category="public",
                confidence="high",
                data_origin="real_observed",
                observation_status="active",
            ),
        ]
    )
    session.flush()
    service.review_candidate_fact(row.candidate_fact_id, _review_request())

    blocked = service.preview_canonical_merge(row.candidate_fact_id)
    conflict_codes = {conflict.code for conflict in blocked.conflicts}
    assert {
        "stale_source",
        "lower_trust_source_conflict",
        "numeric_mismatch",
    }.issubset(conflict_codes)
    assert blocked.can_merge is False
    assert "unresolved_conflicts" in blocked.blockers

    service.review_candidate_fact(
        row.candidate_fact_id,
        _review_request(
            "resolve_conflicts",
            reason="Reviewer accepted stale/lower-trust/count conflict as documented.",
            reviewed_at=NOW.replace(minute=1),
            source_basis={
                "source_ref_ids": ["src_acme"],
                "license_or_terms_category": "partner_terms",
                "resolved_conflict_codes": sorted(conflict_codes),
            },
            before_after_diff={
                "before": {"blockers": blocked.blockers},
                "after": {"resolved_conflict_codes": sorted(conflict_codes)},
            },
        ),
    )
    resolved = service.preview_canonical_merge(row.candidate_fact_id)
    assert resolved.can_merge is True
    assert "unresolved_conflicts" not in resolved.blockers
    result = service.merge_candidate_fact(
        row.candidate_fact_id,
        CanonicalMergeRequest(
            merged_by="admin_28",
            reason="Resolved conflicts through explicit review.",
            merged_at=NOW,
        ),
    )
    assert result.status == "merged"
    assert session.query(DataStandardCanonicalMergeRecord).one().conflict_detected is True
    assert session.query(AdminEventLog).count() == 3


def test_partner_origin_merged_hiring_is_excluded_from_recomputed_scores_by_default(
    session: Session,
) -> None:
    service = DataStandardsService(session)
    service.create_submission(
        _hiring_submission(
            "sub_layer28_ranking_gate",
            company_name="Partner Ranking Co",
            region_name="Ranking Region",
            active_posting_count_now=40,
        )
    )
    candidate = service.create_candidates_from_submission(
        "sub_layer28_ranking_gate"
    ).candidates[0]
    row = session.get(DataStandardCandidateFactRecord, candidate.candidate_fact_id)
    assert row is not None
    payload = row.fact_payload_json
    session.add_all(
        [
            Region(
                region_id=payload["region_id"],
                region_name="ranking_region",
                display_name="Ranking Region",
                region_type="metro",
            ),
            Company(
                company_id="company_existing_ranking",
                company_name="Existing Ranking Co",
                normalized_company_name="existing ranking co",
                eligibility_status="eligible",
            ),
            Company(
                company_id=payload["company_id"],
                company_name=payload["company_name"],
                normalized_company_name=payload["company_name"].casefold(),
            ),
            CompanyRegionHiring(
                hiring_id="hiring_existing_ranking",
                company_id="company_existing_ranking",
                region_id=payload["region_id"],
                currently_hiring_flag=True,
                active_posting_count_now=5,
            ),
        ]
    )
    session.flush()

    scorer = RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    )
    before = scorer.compute_scores(payload["region_id"])
    service.review_candidate_fact(row.candidate_fact_id, _review_request())
    service.merge_candidate_fact(
        row.candidate_fact_id,
        CanonicalMergeRequest(
            merged_by="admin_28",
            reason="Merge partner hiring with no ranking influence.",
            merged_at=NOW,
        ),
    )
    after = scorer.compute_scores(payload["region_id"])

    assert before.source_version_bundle["hiring_record_count"] == 1
    assert after.source_version_bundle["hiring_record_count"] == 1
    assert after.live_market_score == before.live_market_score
    assert session.query(DataStandardCanonicalMergeRecord).one().ranking_influence_allowed is False


def test_data_standard_review_and_merge_routes_require_admin_roles(
    api_client: TestClient,
    session: Session,
) -> None:
    ordinary_headers, _ordinary_id = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|layer28_ordinary",
    )
    reviewer_headers, _reviewer_id = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|layer28_reviewer",
    )
    admin_headers, _admin_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|layer28_merge_admin",
    )
    create = api_client.post(
        "/data-standards/partner-submissions",
        json=_submission("sub_layer28_auth"),
    )
    assert create.status_code == 200

    denied = api_client.post(
        "/data-standards/partner-submissions/sub_layer28_auth/candidates",
        headers=ordinary_headers,
    )
    assert denied.status_code == 403

    candidates = api_client.post(
        "/data-standards/partner-submissions/sub_layer28_auth/candidates",
        headers=reviewer_headers,
    )
    assert candidates.status_code == 200
    candidate_id = candidates.json()["data"]["candidates"][0]["candidate_fact_id"]

    denied_review = api_client.post(
        f"/data-standards/candidates/{candidate_id}/review",
        headers=ordinary_headers,
        json={
            "decision": "approve_candidate",
            "reviewer_id": "reviewer_api",
            "reason": "ordinary user should not review",
            "decision_notes": "ordinary user should not review",
            "source_basis": {
                "source_ref_ids": ["src_acme"],
                "license_or_terms_category": "partner_terms",
            },
        },
    )
    assert denied_review.status_code == 403

    allowed_review = api_client.post(
        f"/data-standards/candidates/{candidate_id}/review",
        headers=reviewer_headers,
        json={
            "decision": "approve_candidate",
            "reviewer_id": "reviewer_api",
            "reason": "reviewer can approve candidate",
            "decision_notes": "source basis reviewed",
            "source_basis": {
                "source_ref_ids": ["src_acme"],
                "license_or_terms_category": "partner_terms",
            },
        },
    )
    assert allowed_review.status_code == 200

    denied_merge = api_client.post(
        f"/data-standards/candidates/{candidate_id}/merge",
        headers=reviewer_headers,
        json={"merged_by": "reviewer_api", "reason": "reviewer cannot merge"},
    )
    assert denied_merge.status_code == 403
    allowed_preview = api_client.post(
        f"/data-standards/candidates/{candidate_id}/merge-preview",
        headers=reviewer_headers,
    )
    assert allowed_preview.status_code == 200
    allowed_merge = api_client.post(
        f"/data-standards/candidates/{candidate_id}/merge",
        headers=admin_headers,
        json={"merged_by": "admin_api", "reason": "admin controlled merge"},
    )
    assert allowed_merge.status_code == 200


def test_layer_28_api_executes_review_preview_merge_path(
    api_client: TestClient,
    session: Session,
) -> None:
    admin_headers, _admin_user_id = _assign_role(
        api_client,
        session,
        AdminRole.ADMIN,
        subject="auth0|layer28_admin",
    )
    create = api_client.post(
        "/data-standards/partner-submissions",
        json=_submission("sub_layer28_api"),
    )
    candidates = api_client.post(
        "/data-standards/partner-submissions/sub_layer28_api/candidates",
        headers=admin_headers,
    )
    candidate_id = next(
        candidate["candidate_fact_id"]
        for candidate in candidates.json()["data"]["candidates"]
        if candidate["record_id"] == "rec_company"
    )
    review = api_client.post(
        f"/data-standards/candidates/{candidate_id}/review",
        headers=admin_headers,
        json={
            "decision": "approve_candidate",
            "reviewer_id": "reviewer_api",
            "reason": "API reviewer approved source basis.",
            "decision_notes": "Reviewed source refs and provenance.",
            "source_basis": {
                "source_ref_ids": ["src_acme"],
                "license_or_terms_category": "partner_terms",
            },
            "reviewed_at": "2026-07-01T12:00:00Z",
        },
    )
    preview = api_client.post(
        f"/data-standards/candidates/{candidate_id}/merge-preview",
        headers=admin_headers,
    )
    merge = api_client.post(
        f"/data-standards/candidates/{candidate_id}/merge",
        headers=admin_headers,
        json={
            "merged_by": "admin_api",
            "reason": "API-controlled merge.",
            "merged_at": "2026-07-01T12:00:00Z",
        },
    )

    assert create.status_code == 200
    assert candidates.status_code == 200
    assert review.status_code == 200
    assert review.json()["data"]["ranking_influence_allowed"] is False
    assert preview.status_code == 200
    assert preview.json()["data"]["can_merge"] is True
    assert merge.status_code == 200
    assert merge.json()["data"]["status"] == "merged"
    assert merge.json()["data"]["ranking_influence_allowed"] is False
    assert session.get(Company, preview.json()["data"]["canonical_target_id"]) is not None
    assert session.query(AdminEventLog).count() == 2
