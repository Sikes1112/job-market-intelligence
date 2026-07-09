from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.data_standards.models import DataStandardCandidateFactRecord
from backend.data_standards.service import PARTNER_SCHEMA_VERSION, DataStandardsService
from backend.geography.models import Region
from backend.opportunities.models import Opportunity
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService
from backend.trust.models import (
    AutomatedRecheckJob,
    RiskRoutingDecision,
    TrustAssessment,
    UserReport,
)
from backend.trust.recheck import AutomatedRecheckService
from backend.trust.report_schemas import UserReportCreate
from backend.trust.reports import UserReportService, latest_report_recheck_status
from backend.trust.schemas import (
    AutomatedRecheckJobStatus,
    AutomatedRecheckOutcome,
    AutomatedRecheckPriority,
    AutomatedRecheckTriggerType,
    TrustAssessmentSubjectType,
    UserReportSeverity,
    UserReportStatus,
    UserReportType,
)

NOW = datetime(2026, 7, 8, 12, tzinfo=UTC)


def test_user_report_creates_append_only_signal_and_recheck_without_mutating_opportunity(
    session: Session,
) -> None:
    _seed_opportunity(session, partner_submitted=True)
    before_counts = _counts(session)
    before_payload = OpportunityService(
        OpportunityRepository(session)
    ).get_opportunity("opp_reported")

    result = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_reported",
            report_type=UserReportType.OUTDATED,
            severity=UserReportSeverity.MEDIUM,
            report_reason="Deadline may be stale.",
            source_surface="test",
        )
    )
    after_payload = OpportunityService(
        OpportunityRepository(session)
    ).get_opportunity("opp_reported")

    assert result.report.status is UserReportStatus.QUEUED_FOR_RECHECK
    assert result.recheck_job is not None
    assert result.recheck_job.trigger_type is AutomatedRecheckTriggerType.STALE_SOURCE
    assert result.recheck_job.priority is AutomatedRecheckPriority.MEDIUM
    assert result.status.recheck_status is AutomatedRecheckJobStatus.QUEUED
    assert "does not directly change rankings" in result.message
    assert _counts(session)["reports"] == before_counts["reports"] + 1
    assert _counts(session)["rechecks"] == before_counts["rechecks"] + 1
    assert after_payload.trust_tier == before_payload.trust_tier
    assert after_payload.risk_level == before_payload.risk_level
    assert after_payload.ranking_influence_allowed is False
    assert session.get(Opportunity, "opp_reported") is not None


def test_suspicious_ranking_and_spam_reports_map_to_safe_high_priority_rechecks(
    session: Session,
) -> None:
    suspicious = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="missing_visible_subject",
            report_type=UserReportType.SUSPICIOUS_RANKING,
            severity=UserReportSeverity.MEDIUM,
        )
    )
    spam = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="missing_visible_subject",
            report_type=UserReportType.SPAM,
            severity=UserReportSeverity.CRITICAL,
        )
    )

    assert suspicious.recheck_job is not None
    assert suspicious.recheck_job.trigger_type is (
        AutomatedRecheckTriggerType.SUSPICIOUS_RANKING
    )
    assert suspicious.recheck_job.priority is AutomatedRecheckPriority.HIGH
    assert spam.report.status is UserReportStatus.ESCALATED_EXCEPTION
    assert spam.recheck_job is not None
    assert spam.recheck_job.priority is AutomatedRecheckPriority.CRITICAL
    assert "approval" not in spam.message.lower()


def test_opportunity_recheck_runs_deterministic_services_and_persists_snapshots(
    session: Session,
) -> None:
    _seed_opportunity(session, partner_submitted=True)
    report = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_reported",
            report_type=UserReportType.EXPIRED_OPPORTUNITY,
        )
    )
    before_counts = _counts(session)
    assert report.recheck_job is not None

    result = AutomatedRecheckService(session, clock=lambda: NOW).run_recheck_job(
        report.recheck_job.automated_recheck_job_id
    )

    assert result.job.status is AutomatedRecheckJobStatus.COMPLETED
    assert result.job.outcome is AutomatedRecheckOutcome.RANKING_INFLUENCE_DENIED
    assert result.job.related_trust_assessment_id is not None
    assert result.job.related_risk_routing_decision_id is not None
    assert _counts(session)["trust_assessments"] == before_counts["trust_assessments"] + 1
    assert _counts(session)["risk_decisions"] == before_counts["risk_decisions"] + 1
    opportunity = OpportunityService(OpportunityRepository(session)).get_opportunity(
        "opp_reported"
    )
    assert opportunity.ranking_influence_allowed is False
    assert opportunity.trust_tier == "partner_submitted"


def test_data_standard_recheck_runs_deterministic_services(session: Session) -> None:
    candidate_id = _seed_data_standard_candidate(session)
    report = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
            subject_id=candidate_id,
            report_type=UserReportType.INCORRECT,
        )
    )
    assert report.recheck_job is not None

    result = AutomatedRecheckService(session, clock=lambda: NOW).run_recheck_job(
        report.recheck_job.automated_recheck_job_id
    )

    assert result.job.status is AutomatedRecheckJobStatus.COMPLETED
    assert result.job.related_trust_assessment_id is not None
    assert result.job.related_risk_routing_decision_id is not None
    assert result.job.outcome in {
        AutomatedRecheckOutcome.RANKING_INFLUENCE_ALLOWED,
        AutomatedRecheckOutcome.RANKING_INFLUENCE_DENIED,
    }
    assert session.get(DataStandardCandidateFactRecord, candidate_id) is not None


def test_unsupported_recheck_subject_skips_safely(session: Session) -> None:
    report = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.COMPANY_FACT,
            subject_id="company_fact_missing",
            report_type=UserReportType.OTHER,
        )
    )
    assert report.recheck_job is not None

    result = AutomatedRecheckService(session, clock=lambda: NOW).run_recheck_job(
        report.recheck_job.automated_recheck_job_id
    )

    assert result.job.status is AutomatedRecheckJobStatus.SKIPPED
    assert result.job.outcome is AutomatedRecheckOutcome.FAILED
    assert result.job.outcome_reason == "unsupported_subject_type"


def test_latest_report_recheck_status_is_public_safe(session: Session) -> None:
    result = UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_status",
            report_type=UserReportType.WRONG_REGION,
        )
    )

    status = latest_report_recheck_status(
        session,
        subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
        subject_id="opp_status",
    )

    assert status is not None
    assert status.latest_report_status is UserReportStatus.QUEUED_FOR_RECHECK
    assert status.recheck_status_label == "Recheck queued"
    assert result.report.report_reason is None
    assert "reviewer" not in status.model_dump_json()
    assert "admin" not in status.model_dump_json().lower()


def _seed_opportunity(session: Session, *, partner_submitted: bool) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Company(
                company_id="comp_reported",
                company_name="Reported Co",
                normalized_company_name="reported co",
                sector_primary="software",
            ),
        ]
    )
    session.flush()
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_reported",
            employer_id="comp_reported",
            employer_name="Reported Co",
            program_name="Reported Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students and recent graduates.",
            application_url="https://example.com/apply/report",
            source_url="https://example.com/source/report",
            source_type=(
                OpportunitySourceType.PARTNER_SUBMITTED
                if partner_submitted
                else OpportunitySourceType.EMPLOYER_OFFICIAL
            ),
            application_deadline=date(2099, 1, 1),
            trust_label=(
                OpportunityTrustLabel.PARTNER_SUBMITTED
                if partner_submitted
                else OpportunityTrustLabel.VERIFIED
            ),
            review_status=(
                OpportunityReviewStatus.PENDING_REVIEW
                if partner_submitted
                else OpportunityReviewStatus.APPROVED
            ),
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=partner_submitted,
                paid_partner=False,
                internal_review_notes="Internal report test note",
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )
    session.flush()


def _seed_data_standard_candidate(session: Session) -> str:
    service = DataStandardsService(session)
    service.create_submission(_submission())
    candidates = service.create_candidates_from_submission("sub_30d")
    return candidates.candidates[0].candidate_fact_id


def _submission() -> dict:
    return {
        "submission_id": "sub_30d",
        "partner_id": "partner_career_platform",
        "submitted_at": "2026-07-08T12:00:00Z",
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
            }
        ],
        "source_refs": [
            {
                "source_ref_id": "src_acme",
                "source_type": "employer_official",
                "url": "https://acme.example/careers",
                "collected_at": "2026-07-08T10:00:00Z",
                "license_or_terms_category": "partner_terms",
            }
        ],
        "freshness": {
            "freshness_status": "fresh",
            "observed_at": "2026-07-08T10:00:00Z",
            "freshness_expires_at": "2026-08-08T10:00:00Z",
        },
        "confidence": {
            "confidence_label": "high",
            "confidence_score": 0.91,
            "rationale": "Official source supplied by partner.",
        },
    }


def _counts(session: Session) -> dict[str, int]:
    return {
        "opportunities": session.scalar(select(func.count()).select_from(Opportunity))
        or 0,
        "reports": session.scalar(select(func.count()).select_from(UserReport)) or 0,
        "rechecks": session.scalar(select(func.count()).select_from(AutomatedRecheckJob))
        or 0,
        "trust_assessments": (
            session.scalar(select(func.count()).select_from(TrustAssessment)) or 0
        ),
        "risk_decisions": (
            session.scalar(select(func.count()).select_from(RiskRoutingDecision)) or 0
        ),
    }
