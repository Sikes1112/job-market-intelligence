"""Persistence models for Layer 27 partner standards submissions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base

PARTNER_SUBMITTER_TYPE_SQL = (
    "'employer', "
    "'education_institution', "
    "'workforce_board', "
    "'data_vendor', "
    "'nonprofit_partner', "
    "'government_agency'"
)

PARTNER_VALIDATION_STATUS_SQL = (
    "'received', "
    "'validated', "
    "'rejected', "
    "'needs_review', "
    "'certified', "
    "'archived'"
)

SUBMISSION_REVIEW_LIFECYCLE_STATE_SQL = (
    "'submitted', "
    "'validation_failed', "
    "'validation_passed', "
    "'under_review', "
    "'needs_changes', "
    "'accepted_as_candidate', "
    "'rejected', "
    "'merged', "
    "'superseded', "
    "'withdrawn'"
)

CANDIDATE_FACT_STATE_SQL = (
    "'pending_review', "
    "'approved_for_merge', "
    "'rejected', "
    "'needs_correction', "
    "'conflict', "
    "'duplicate', "
    "'low_confidence', "
    "'escalated', "
    "'merged'"
)

CANDIDATE_REVIEW_DECISION_SQL = (
    "'approve_candidate', "
    "'reject_candidate', "
    "'request_changes', "
    "'mark_duplicate', "
    "'mark_low_confidence', "
    "'escalate', "
    "'merge_to_canonical', "
    "'resolve_conflicts', "
    "'approve_for_merge', "
    "'reject', "
    "'request_correction', "
    "'mark_conflict'"
)

CANDIDATE_TARGET_TYPE_SQL = (
    "'company', "
    "'region', "
    "'company_region_presence', "
    "'company_region_hiring', "
    "'unsupported'"
)

CANONICAL_MERGE_ACTION_SQL = "'create', 'noop'"
CANONICAL_MERGE_STATUS_SQL = "'preview_ready', 'blocked', 'merged'"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DataStandardPartnerSubmissionRecord(Base):
    """Stored external partner submission.

    This table is Layer 27 intake state only. It must not be interpreted as a
    canonical company, region, hiring, opportunity, recommendation, predictive,
    policy, career-agent, or market-score record.
    """

    __tablename__ = "data_standard_partner_submissions"
    __table_args__ = (
        CheckConstraint(
            f"submitter_type IN ({PARTNER_SUBMITTER_TYPE_SQL})",
            name="ck_data_standard_partner_submissions_submitter_type",
        ),
        CheckConstraint(
            f"validation_status IN ({PARTNER_VALIDATION_STATUS_SQL})",
            name="ck_data_standard_partner_submissions_validation_status",
        ),
        CheckConstraint(
            f"review_lifecycle_state IN ({SUBMISSION_REVIEW_LIFECYCLE_STATE_SQL})",
            name="ck_data_standard_partner_submissions_review_state",
        ),
        CheckConstraint(
            "schema_version = 'partner_submission_v1'",
            name="ck_data_standard_partner_submissions_schema_version",
        ),
        Index("ix_data_standard_partner_submissions_partner", "partner_id"),
        Index("ix_data_standard_partner_submissions_status", "validation_status"),
        Index(
            "ix_data_standard_partner_submissions_review_state",
            "review_lifecycle_state",
        ),
        Index("ix_data_standard_partner_submissions_submitted_at", "submitted_at"),
        Index("ix_data_standard_partner_submissions_created_at", "created_at"),
    )

    partner_submission_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    partner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    submitter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_lifecycle_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="submitted",
    )
    review_state_history_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    records_json: Mapped[list] = mapped_column(JSON, nullable=False)
    source_refs_json: Mapped[list] = mapped_column(JSON, nullable=False)
    freshness_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_errors_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_submission_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class DataStandardCandidateFactRecord(Base):
    """Candidate fact derived from one validated partner submission record.

    Candidate rows are review/merge inputs only. They do not write canonical
    market intelligence until the controlled merge service accepts them.
    """

    __tablename__ = "data_standard_candidate_facts"
    __table_args__ = (
        CheckConstraint(
            f"candidate_state IN ({CANDIDATE_FACT_STATE_SQL})",
            name="ck_data_standard_candidate_facts_state",
        ),
        CheckConstraint(
            "record_type IN ("
            "'company', "
            "'region', "
            "'early_career_program', "
            "'hiring_signal', "
            "'company_region_presence'"
            ")",
            name="ck_data_standard_candidate_facts_record_type",
        ),
        CheckConstraint(
            f"canonical_target_type IN ({CANDIDATE_TARGET_TYPE_SQL})",
            name="ck_data_standard_candidate_facts_target_type",
        ),
        CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_candidate_facts_no_ranking_influence",
        ),
        UniqueConstraint(
            "partner_submission_id",
            "record_id",
            name="uq_data_standard_candidate_facts_submission_record",
        ),
        Index(
            "ix_data_standard_candidate_facts_submission",
            "partner_submission_id",
        ),
        Index("ix_data_standard_candidate_facts_partner", "partner_id"),
        Index("ix_data_standard_candidate_facts_state", "candidate_state"),
        Index("ix_data_standard_candidate_facts_target", "canonical_target_type"),
        Index(
            "ix_data_standard_candidate_facts_target_id",
            "canonical_target_type",
            "canonical_target_id",
        ),
        Index("ix_data_standard_candidate_facts_created_at", "created_at"),
    )

    candidate_fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    partner_submission_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_partner_submissions.partner_submission_id"),
        nullable=False,
    )
    partner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    partner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    partner_verification_status: Mapped[str] = mapped_column(String(64), nullable=False)
    partner_trust_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    submitter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending_review",
    )
    canonical_target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_target_key_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fact_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_refs_json: Mapped[list] = mapped_column(JSON, nullable=False)
    freshness_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    provenance_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance_warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_record_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class DataStandardCandidateReviewRecord(Base):
    """Append-only reviewer decision for a candidate fact."""

    __tablename__ = "data_standard_candidate_reviews"
    __table_args__ = (
        CheckConstraint(
            f"decision IN ({CANDIDATE_REVIEW_DECISION_SQL})",
            name="ck_data_standard_candidate_reviews_decision",
        ),
        CheckConstraint(
            f"resulting_candidate_state IN ({CANDIDATE_FACT_STATE_SQL})",
            name="ck_data_standard_candidate_reviews_state",
        ),
        CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_candidate_reviews_no_ranking_influence",
        ),
        Index("ix_data_standard_candidate_reviews_candidate", "candidate_fact_id"),
        Index("ix_data_standard_candidate_reviews_submission", "partner_submission_id"),
        Index("ix_data_standard_candidate_reviews_decision", "decision"),
        Index("ix_data_standard_candidate_reviews_audit_event", "audit_event_id"),
        Index("ix_data_standard_candidate_reviews_reviewed_at", "reviewed_at"),
        Index("ix_data_standard_candidate_reviews_created_at", "created_at"),
    )

    candidate_review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_fact_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_candidate_facts.candidate_fact_id"),
        nullable=False,
    )
    partner_submission_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_partner_submissions.partner_submission_id"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    resulting_candidate_state: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(String(2048), nullable=False)
    decision_notes: Mapped[str] = mapped_column(Text, nullable=False)
    source_basis_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    before_after_diff_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    resolved_conflict_codes_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    audit_event_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("admin_event_logs.admin_event_id"),
        nullable=False,
    )
    provenance_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class DataStandardCanonicalMergeRecord(Base):
    """Append-only controlled merge record linking a candidate to canonical facts."""

    __tablename__ = "data_standard_canonical_merges"
    __table_args__ = (
        CheckConstraint(
            f"canonical_target_type IN ({CANDIDATE_TARGET_TYPE_SQL})",
            name="ck_data_standard_canonical_merges_target_type",
        ),
        CheckConstraint(
            f"merge_action IN ({CANONICAL_MERGE_ACTION_SQL})",
            name="ck_data_standard_canonical_merges_action",
        ),
        CheckConstraint(
            f"merge_status IN ({CANONICAL_MERGE_STATUS_SQL})",
            name="ck_data_standard_canonical_merges_status",
        ),
        CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_canonical_merges_no_ranking_influence",
        ),
        UniqueConstraint(
            "candidate_fact_id",
            name="uq_data_standard_canonical_merges_candidate",
        ),
        Index("ix_data_standard_canonical_merges_candidate", "candidate_fact_id"),
        Index("ix_data_standard_canonical_merges_submission", "partner_submission_id"),
        Index(
            "ix_data_standard_canonical_merges_target",
            "canonical_target_type",
            "canonical_target_id",
        ),
        Index("ix_data_standard_canonical_merges_audit_event", "audit_event_id"),
        Index(
            "ix_data_standard_canonical_merges_review_decision",
            "review_decision_id",
        ),
        Index("ix_data_standard_canonical_merges_merged_at", "merged_at"),
        Index("ix_data_standard_canonical_merges_created_at", "created_at"),
    )

    merge_record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_fact_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_candidate_facts.candidate_fact_id"),
        nullable=False,
    )
    partner_submission_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_partner_submissions.partner_submission_id"),
        nullable=False,
    )
    review_decision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("data_standard_candidate_reviews.candidate_review_id"),
        nullable=False,
    )
    canonical_target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    merge_action: Mapped[str] = mapped_column(String(32), nullable=False)
    merge_status: Mapped[str] = mapped_column(String(32), nullable=False)
    conflict_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflicts_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    canonical_before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    canonical_after_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    provenance_binding_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    invalidation_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    stale_output_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    audit_event_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("admin_event_logs.admin_event_id"),
        nullable=False,
    )
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    merged_by: Mapped[str] = mapped_column(String(128), nullable=False)
    merged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


def _prevent_data_standard_review_update(_mapper, _connection, target) -> None:  # noqa: ANN001
    raise ValueError(f"{target.__class__.__name__} records are append-only")


def _install_append_only_guards() -> None:
    for model in (
        DataStandardCandidateFactRecord,
        DataStandardCandidateReviewRecord,
        DataStandardCanonicalMergeRecord,
    ):
        event.listen(
            model,
            "before_update",
            _prevent_data_standard_review_update,
            propagate=True,
        )
        event.listen(
            model,
            "before_delete",
            _prevent_data_standard_review_update,
            propagate=True,
        )


_install_append_only_guards()
