from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.refresh_quality.models import (
    LegalTermsPosture,
    QualitySeverity,
    RefreshCandidate,
    RefreshCandidateReason,
    SourceRefreshQueueStatus,
    SourceRefreshTargetType,
)
from backend.refresh_quality.source_queue import (
    queue_item_from_candidate,
    queue_items_from_candidates,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "backend" / "refresh_quality"
NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _candidate(**overrides) -> RefreshCandidate:
    base = {
        "candidate_key": "candidate_a",
        "entity_type": "company_region",
        "entity_id": "company_a::boston",
        "fact_type": "internship_data",
        "reason": RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA,
        "severity": QualitySeverity.HIGH,
        "explanation": "expired internship data",
        "current_value": {"internship_count": 3},
        "recommended_source_type": SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE,
    }
    base.update(overrides)
    return RefreshCandidate(**base)


def test_queue_vocabulary_contains_required_source_targets_and_postures() -> None:
    assert SourceRefreshTargetType.values() == {
        "company_page",
        "company_careers_page",
        "public_job_board",
        "government_open_dataset",
        "university_coop_public_employer_list",
        "company_internship_page",
        "manual_research_required",
    }
    assert LegalTermsPosture.values() == {
        "MANUAL_ONLY",
        "PUBLIC_DATASET_ALLOWED",
        "TERMS_REVIEW_REQUIRED",
        "DISALLOWED",
        "UNKNOWN",
    }


def test_queue_item_preserves_candidate_link_and_review_policy() -> None:
    item = queue_item_from_candidate(_candidate(), created_at=NOW)

    assert item.queue_item_id.startswith("source_refresh_queue:")
    assert item.candidate_key == "candidate_a"
    assert item.entity_type == "company_region"
    assert item.entity_id == "company_a::boston"
    assert item.source_type is SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    assert item.priority.value == "high"
    assert item.legal_terms_posture is LegalTermsPosture.UNKNOWN
    assert item.status is SourceRefreshQueueStatus.PENDING_REVIEW
    assert item.created_at == NOW
    assert "not executable scraping" in item.explanation


def test_manual_research_candidate_becomes_manual_only_work_item() -> None:
    candidate = _candidate(
        candidate_key="candidate_missing",
        reason=RefreshCandidateReason.MISSING_SOURCE_FACT,
        severity=QualitySeverity.HIGH,
        recommended_source_type=SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED,
    )

    item = queue_item_from_candidate(candidate)

    assert item.source_type is SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    assert item.legal_terms_posture is LegalTermsPosture.MANUAL_ONLY
    assert item.status is SourceRefreshQueueStatus.MANUAL_ONLY


def test_public_dataset_targets_are_marked_allowed_but_not_executed() -> None:
    item = queue_item_from_candidate(
        _candidate(candidate_key="candidate_dataset"),
        source_type=SourceRefreshTargetType.GOVERNMENT_OPEN_DATASET,
    )

    assert item.legal_terms_posture is LegalTermsPosture.PUBLIC_DATASET_ALLOWED
    assert item.status is SourceRefreshQueueStatus.PENDING_REVIEW


def test_public_job_board_requires_terms_review_posture() -> None:
    item = queue_item_from_candidate(
        _candidate(candidate_key="candidate_job_board"),
        source_type=SourceRefreshTargetType.PUBLIC_JOB_BOARD,
    )

    assert item.legal_terms_posture is LegalTermsPosture.TERMS_REVIEW_REQUIRED
    assert item.status is SourceRefreshQueueStatus.TERMS_REVIEW_REQUIRED

    with pytest.raises(ValueError, match="cannot be treated as public datasets"):
        queue_item_from_candidate(
            _candidate(candidate_key="candidate_bad_job_board"),
            source_type=SourceRefreshTargetType.PUBLIC_JOB_BOARD,
            legal_terms_posture=LegalTermsPosture.PUBLIC_DATASET_ALLOWED,
        )


def test_queue_items_from_candidates_are_deterministic() -> None:
    candidates = [
        _candidate(candidate_key="candidate_b"),
        _candidate(candidate_key="candidate_a"),
    ]

    first = queue_items_from_candidates(candidates, created_at=NOW)
    second = queue_items_from_candidates(reversed(candidates), created_at=NOW)

    assert [item.queue_item_id for item in first] == [
        item.queue_item_id for item in second
    ]


def test_refresh_quality_package_has_no_execution_or_network_imports() -> None:
    forbidden_fragments = (
        "requests",
        "httpx",
        "urllib",
        "selenium",
        "playwright",
        "bs4",
        "scrapy",
        "sqlalchemy",
        "OutputAssemblyService",
        "OutputCacheRepository",
        "RegionScoringService",
        "QueueService",
        "RefreshQueueAdapter",
        "make_refresh_job_request",
        "backend.outputs.invalidation",
        "OutputCacheInvalidationService",
    )
    violations: dict[str, list[str]] = {}
    for path in PACKAGE_ROOT.glob("*.py"):
        text = path.read_text()
        bad = [fragment for fragment in forbidden_fragments if fragment in text]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations, violations
