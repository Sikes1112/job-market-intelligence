"""Layer 30D deterministic automated recheck execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.data_standards.schemas import CandidateFactPayload
from backend.data_standards.service import CandidateFactNotFound, DataStandardsService
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.service import OpportunityNotFound, OpportunityService
from backend.trust.adapters import DataStandardsTrustAdapter, OpportunityTrustAdapter
from backend.trust.models import AutomatedRecheckJob
from backend.trust.report_schemas import RecheckRunResult
from backend.trust.reports import (
    AutomatedRecheckJobNotFound,
    AutomatedRecheckRepository,
    automated_recheck_job_payload,
    report_recheck_status_from_rows,
)
from backend.trust.repository import TrustAssessmentRepository
from backend.trust.risk import RiskRoutingService
from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    TrustAssessmentSubjectType,
    TrustSubjectMetadata,
    TrustTier,
)
from backend.trust.service import TrustAssessmentService


class AutomatedRecheckService:
    """Run deterministic trust/risk recomputation for queued recheck jobs."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jobs = AutomatedRecheckRepository(session)
        self._trust_repo = TrustAssessmentRepository(session)

    def run_recheck_job(self, job_id: str) -> RecheckRunResult:
        job = self._jobs.get_job(job_id)
        if job is None:
            raise AutomatedRecheckJobNotFound(job_id)

        now = self._clock()
        job.status = AutomatedRecheckJobStatus.RUNNING.value
        job.started_at = now
        job.attempts += 1
        job.updated_at = now
        self._session.flush()

        try:
            subject = self._subject_metadata(job)
        except UnsupportedRecheckSubject:
            return self._skip_job(job, reason="unsupported_subject_type")
        except (OpportunityNotFound, CandidateFactNotFound):
            return self._skip_job(job, reason="subject_not_found")

        assessment = TrustAssessmentService(clock=self._clock).assess(subject)
        trust_row = self._trust_repo.add_assessment(assessment)
        routing = RiskRoutingService(clock=self._clock).decide(assessment, subject)
        routing_row = self._trust_repo.add_routing_decision(
            routing,
            trust_assessment_id=trust_row.trust_assessment_id,
        )
        completed_at = self._clock()
        job.status = AutomatedRecheckJobStatus.COMPLETED.value
        job.completed_at = completed_at
        job.related_trust_assessment_id = trust_row.trust_assessment_id
        job.related_risk_routing_decision_id = routing_row.risk_routing_decision_id
        job.outcome = _outcome_for_recheck(
            trust_tier=assessment.trust_tier,
            ranking_influence_allowed=routing.ranking_influence_allowed,
        ).value
        job.outcome_reason = (
            "Deterministic Layer 30A/30B recheck completed without mutating "
            "canonical source data."
        )
        job.updated_at = completed_at
        self._session.flush()
        from backend.trust.exceptions import ExceptionWorkflowService

        ExceptionWorkflowService(
            self._session,
            clock=self._clock,
        ).maybe_create_exception_from_recheck(job)
        return RecheckRunResult(
            job=automated_recheck_job_payload(job),
            status=report_recheck_status_from_rows(report=None, job=job),
            message="Automated recheck completed through deterministic trust/risk services.",
        )

    def _subject_metadata(self, job: AutomatedRecheckJob) -> TrustSubjectMetadata:
        subject_type = TrustAssessmentSubjectType(job.subject_type)
        if subject_type is TrustAssessmentSubjectType.OPPORTUNITY:
            payload = OpportunityService(
                OpportunityRepository(self._session)
            ).get_opportunity(job.subject_id)
            return OpportunityTrustAdapter.from_payload(payload)
        if subject_type is TrustAssessmentSubjectType.DATA_STANDARD_FACT:
            detail = DataStandardsService(self._session).candidate_detail(job.subject_id)
            candidate = CandidateFactPayload.model_validate(detail["candidate"])
            return DataStandardsTrustAdapter.from_candidate_payload(candidate)
        raise UnsupportedRecheckSubject(job.subject_type)

    def _skip_job(self, job: AutomatedRecheckJob, *, reason: str) -> RecheckRunResult:
        completed_at = self._clock()
        job.status = AutomatedRecheckJobStatus.SKIPPED.value
        job.completed_at = completed_at
        job.outcome = AutomatedRecheckOutcome.FAILED.value
        job.outcome_reason = reason
        job.last_error = reason
        job.updated_at = completed_at
        self._session.flush()
        from backend.trust.exceptions import ExceptionWorkflowService

        ExceptionWorkflowService(
            self._session,
            clock=self._clock,
        ).maybe_create_exception_from_recheck(job)
        return RecheckRunResult(
            job=automated_recheck_job_payload(job),
            status=report_recheck_status_from_rows(report=None, job=job),
            message="Automated recheck skipped safely.",
        )


class UnsupportedRecheckSubject(Exception):
    pass


def _outcome_for_recheck(
    *,
    trust_tier: TrustTier,
    ranking_influence_allowed: bool,
) -> AutomatedRecheckOutcome:
    if trust_tier is TrustTier.BLOCKED:
        return AutomatedRecheckOutcome.BLOCKED
    if trust_tier is TrustTier.QUARANTINED:
        return AutomatedRecheckOutcome.QUARANTINED
    if trust_tier is TrustTier.LOW_CONFIDENCE:
        return AutomatedRecheckOutcome.STILL_LOW_CONFIDENCE
    if ranking_influence_allowed:
        return AutomatedRecheckOutcome.RANKING_INFLUENCE_ALLOWED
    return AutomatedRecheckOutcome.RANKING_INFLUENCE_DENIED
