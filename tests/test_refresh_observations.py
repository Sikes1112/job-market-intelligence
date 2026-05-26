from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.refresh_quality.models import (
    LegalTermsPosture,
    QualitySeverity,
    RefreshCandidate,
    RefreshCandidateReason,
    SourceRefreshTargetType,
)
from backend.refresh_quality.observations import (
    CandidateObservationStatus,
    make_candidate_observation,
    observation_from_candidate_and_queue,
)
from backend.refresh_quality.source_queue import queue_item_from_candidate

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _candidate() -> RefreshCandidate:
    return RefreshCandidate(
        candidate_key="candidate_a",
        entity_type="company_region",
        entity_id="company_a::boston",
        fact_type="hiring_count",
        reason=RefreshCandidateReason.STALE_HIRING_COUNT,
        severity=QualitySeverity.MEDIUM,
        explanation="stale hiring count",
        current_value=10,
        confidence="moderate_confidence",
        recommended_source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
    )


def test_candidate_observation_status_values_are_documented() -> None:
    assert CandidateObservationStatus.values() == {
        "PENDING_VALIDATION",
        "VALIDATED",
        "NEEDS_MORE_EVIDENCE",
        "REJECTED",
        "APPROVED_FOR_HANDOFF",
    }


def test_make_candidate_observation_preserves_required_context() -> None:
    observation = make_candidate_observation(
        refresh_candidate_key="candidate_a",
        queue_item_id="queue_a",
        entity_type="company_region",
        entity_id="company_a::boston",
        fact_type="hiring_count",
        previous_value=8,
        current_value=10,
        proposed_value=11,
        source_evidence_ref="source_obs_a",
        source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
        legal_terms_posture=LegalTermsPosture.UNKNOWN,
        confidence="moderate_confidence",
        explanation="new reviewed evidence",
        observed_at=NOW,
    )

    assert observation.observation_id.startswith("candidate_observation:")
    assert observation.refresh_candidate_key == "candidate_a"
    assert observation.queue_item_id == "queue_a"
    assert observation.current_value == 10
    assert observation.proposed_value == 11
    assert observation.source_evidence_ref == "source_obs_a"
    assert observation.observation_status is CandidateObservationStatus.PENDING_VALIDATION


def test_observation_from_candidate_and_queue_requires_linked_records() -> None:
    candidate = _candidate()
    queue_item = queue_item_from_candidate(candidate)

    observation = observation_from_candidate_and_queue(
        candidate=candidate,
        queue_item=queue_item,
        proposed_value=12,
        source_evidence_ref="source_obs_hiring",
        explanation="candidate source checked manually",
        observed_at=NOW,
    )

    assert observation.refresh_candidate_key == candidate.candidate_key
    assert observation.queue_item_id == queue_item.queue_item_id
    assert observation.current_value == candidate.current_value
    assert observation.source_type is SourceRefreshTargetType.COMPANY_CAREERS_PAGE

    unlinked_queue = queue_item.model_copy(update={"candidate_key": "other"})
    with pytest.raises(ValueError, match="queue item must link"):
        observation_from_candidate_and_queue(
            candidate=candidate,
            queue_item=unlinked_queue,
            proposed_value=12,
            source_evidence_ref="source_obs_hiring",
            explanation="bad link",
        )


def test_candidate_observation_rejects_naive_observed_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_candidate_observation(
            entity_type="company_region",
            entity_id="company_a::boston",
            fact_type="hiring_count",
            proposed_value=12,
            source_evidence_ref="source_obs_hiring",
            source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
            legal_terms_posture=LegalTermsPosture.UNKNOWN,
            explanation="bad timestamp",
            observed_at=datetime(2026, 5, 26, 12),
        )
