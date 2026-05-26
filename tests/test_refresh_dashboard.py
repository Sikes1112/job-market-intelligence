from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backend.refresh_quality.approval import prepare_approved_canonical_update_handoff
from backend.refresh_quality.audit import (
    audit_record_for_handoff,
    audit_record_for_review,
    audit_record_for_validation,
)
from backend.refresh_quality.dashboard import build_refresh_dashboard_payload
from backend.refresh_quality.models import (
    LegalTermsPosture,
    QualityRegressionSnapshot,
    QualitySeverity,
    RefreshCandidate,
    RefreshCandidateReason,
    SourceRefreshTargetType,
)
from backend.refresh_quality.observations import make_candidate_observation
from backend.refresh_quality.regression_detection import detect_quality_regressions
from backend.refresh_quality.review import (
    HumanReviewDecision,
    record_human_review_decision,
)
from backend.refresh_quality.source_queue import queue_item_from_candidate
from backend.refresh_quality.validation import validate_candidate_observation

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "backend" / "refresh_quality"
NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _candidate(**overrides) -> RefreshCandidate:
    base = {
        "candidate_key": "candidate_stale",
        "entity_type": "company_region",
        "entity_id": "company_a::boston",
        "fact_type": "hiring_count",
        "reason": RefreshCandidateReason.STALE_HIRING_COUNT,
        "severity": QualitySeverity.MEDIUM,
        "explanation": "stale",
        "current_value": 10,
        "recommended_source_type": SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
    }
    base.update(overrides)
    return RefreshCandidate(**base)


def test_dashboard_payload_summarizes_refresh_quality_sections() -> None:
    stale_candidate = _candidate()
    low_confidence_candidate = _candidate(
        candidate_key="candidate_low_conf",
        reason=RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT,
        fact_type="source_fact",
        severity=QualitySeverity.MEDIUM,
    )
    coverage_gap_candidate = _candidate(
        candidate_key="candidate_gap",
        entity_type="region",
        entity_id="boston",
        reason=RefreshCandidateReason.COVERAGE_GAP,
        fact_type="market_coverage",
        severity=QualitySeverity.HIGH,
    )
    queue_item = queue_item_from_candidate(stale_candidate)
    observation = make_candidate_observation(
        refresh_candidate_key=stale_candidate.candidate_key,
        queue_item_id=queue_item.queue_item_id,
        entity_type="company_region",
        entity_id="company_a::boston",
        fact_type="hiring_count",
        current_value=10,
        proposed_value=12,
        source_evidence_ref="source_obs_a",
        source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
        legal_terms_posture=LegalTermsPosture.PUBLIC_DATASET_ALLOWED,
        confidence="high_confidence",
        explanation="manual review",
        observed_at=NOW,
    )
    validation = validate_candidate_observation(observation, now=NOW)
    review = record_human_review_decision(
        observation=observation,
        validation=validation,
        decision=HumanReviewDecision.APPROVED,
        reviewer_id="admin_1",
        reviewer_note="approve",
        reviewed_at=NOW,
    )
    handoff = prepare_approved_canonical_update_handoff(
        observation=observation,
        validation=validation,
        review=review,
    )
    rejected = record_human_review_decision(
        observation=observation,
        validation=validation,
        decision=HumanReviewDecision.REJECTED,
        reviewer_id="admin_2",
        reviewer_note="reject duplicate",
        reviewed_at=NOW,
    )
    policy_observation = make_candidate_observation(
        entity_type="company_region",
        entity_id="company_b::boston",
        fact_type="hiring_count",
        current_value=5,
        proposed_value=7,
        source_evidence_ref="source_disallowed",
        source_type=SourceRefreshTargetType.PUBLIC_JOB_BOARD,
        legal_terms_posture=LegalTermsPosture.DISALLOWED,
        confidence="high_confidence",
        explanation="policy blocked",
        observed_at=NOW,
    )
    policy_validation = validate_candidate_observation(policy_observation, now=NOW)
    policy_review = record_human_review_decision(
        observation=policy_observation,
        validation=policy_validation,
        decision=HumanReviewDecision.POLICY_BLOCKED,
        reviewer_id="admin_3",
        reviewer_note="terms disallow",
        reviewed_at=NOW,
    )
    regressions = detect_quality_regressions(
        [
            QualityRegressionSnapshot(
                entity_type="company_region",
                entity_id="company_a::boston",
                refresh_failure_count=3,
                previous_coverage_gap_count=1,
                current_coverage_gap_count=2,
            )
        ],
        now=NOW,
    )
    audit_records = [
        audit_record_for_validation(
            observation=observation,
            validation=validation,
            timestamp=NOW,
        ),
        audit_record_for_review(
            observation=policy_observation,
            validation=policy_validation,
            review=policy_review,
            timestamp=NOW,
        ),
        audit_record_for_handoff(
            observation=observation,
            validation=validation,
            review=review,
            handoff=handoff,
            timestamp=NOW,
        ),
    ]

    dashboard = build_refresh_dashboard_payload(
        candidates=[stale_candidate, low_confidence_candidate, coverage_gap_candidate],
        queue_items=[queue_item],
        regressions=regressions,
        observations=[observation, policy_observation],
        validations=[validation, policy_validation],
        reviews=[review, rejected, policy_review],
        handoffs=[handoff],
        audit_records=audit_records,
        generated_at=NOW,
    )

    assert dashboard.generated_at == NOW
    assert dashboard.summary_counts["stale_companies"] == 1
    assert dashboard.summary_counts["low_confidence_facts"] == 1
    assert dashboard.summary_counts["coverage_gaps"] == 2
    assert dashboard.summary_counts["failed_refresh_jobs"] == 1
    assert dashboard.summary_counts["refresh_queue_items"] == 1
    assert dashboard.summary_counts["approved_update_handoffs"] == 1
    assert dashboard.summary_counts["rejected_observations"] == 1
    assert dashboard.summary_counts["policy_blocked_observations"] == 2
    assert dashboard.summary_counts["quality_regressions"] == 2
    assert dashboard.audit_warnings


def test_refresh_quality_package_has_no_forbidden_batch2_imports() -> None:
    forbidden_fragments = (
        "requests",
        "httpx",
        "urllib",
        "selenium",
        "playwright",
        "bs4",
        "scrapy",
        "sqlalchemy",
        "backend.api",
        "APIRouter",
        "FastAPI",
        "backend.refresh.scheduler",
        "backend.refresh.runner",
        "backend.orchestration.workers",
        "backend.outputs.service",
        "backend.outputs.invalidation",
        "backend.scoring.service",
        "backend.scoring.repository",
        "backend.companies.repository",
        "backend.geography.repository",
        "backend.presence.repository",
        "backend.hiring.repository",
        "backend.entry_level.repository",
        "OutputAssemblyService",
        "OutputCacheRepository",
        "RegionScoringService",
        "RefreshQueueAdapter",
        "make_refresh_job_request",
    )
    violations: dict[str, list[str]] = {}
    for path in PACKAGE_ROOT.glob("*.py"):
        text = path.read_text()
        bad = [fragment for fragment in forbidden_fragments if fragment in text]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations, violations
