"""Layer 4A ingestion status vocabulary.

The values here describe pre-canonical intake and normalization state only.
They do not authorize creation of trusted market facts.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType

from backend.shared.provenance import FactBindingType, ProvenanceFactType


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class IngestionStatus(_Vocabulary):
    RECEIVED = "received"
    STORED = "stored"
    REJECTED = "rejected"


class NormalizationStatus(_Vocabulary):
    RAW_UNREVIEWED = "raw_unreviewed"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    REJECTED = "rejected"
    CONFLICTING = "conflicting"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"


class CanonicalFactIntent(_Vocabulary):
    COMPANY = "company"
    REGION = "region"
    PRESENCE = "presence"
    HIRING = "hiring"
    INTERNSHIPS_COOPS = "internships_coops"
    EARLY_CAREER_PROGRAMS = "early_career_programs"
    SCORE_INPUT = "score_input"


class ProposalReviewStatus(_Vocabulary):
    PROPOSED = "proposed"
    APPROVED_FOR_LINKING = "approved_for_linking"
    REJECTED = "rejected"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"
    LINKED_TO_SOURCE = "linked_to_source"
    FAILED = "failed"


class CanonicalWriteOperationType(_Vocabulary):
    CREATE = "create"
    UPDATE = "update"
    NO_OP = "no_op"
    REJECT = "reject"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"


class CanonicalWritePlanStatus(_Vocabulary):
    PLANNED = "planned"
    NO_OP = "no_op"
    REJECTED = "rejected"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class CanonicalWriteExecutionStatus(_Vocabulary):
    EXECUTED = "executed"
    NO_OP = "no_op"
    ALREADY_APPLIED = "already_applied"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    FAILED = "failed"


class PostWriteRefreshTargetType(_Vocabulary):
    REGION_SCORE = "region_score"
    COMPANY_SCORE = "company_score"
    REGION_OUTPUT = "region_output"
    COMPANY_OUTPUT = "company_output"
    COMPARISON_OUTPUT = "comparison_output"
    CONTEXTUAL_OUTPUT = "contextual_output"
    PROVENANCE_AUDIT = "provenance_audit"
    UNKNOWN_OR_UNSUPPORTED = "unknown_or_unsupported"


class PostWriteRefreshPlanStatus(_Vocabulary):
    PLANNED = "planned"
    NO_OP = "no_op"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class PostWriteRefreshExecutionStatus(_Vocabulary):
    EXECUTED = "executed"
    PARTIAL = "partial"
    NO_OP = "no_op"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ManualIngestionRunMode(_Vocabulary):
    DRY_RUN_ONLY = "dry_run_only"
    LINK_ONLY = "link_only"
    EXECUTE_WRITE_WITH_APPROVAL = "execute_write_with_approval"
    EXECUTE_WRITE_AND_REFRESH_WITH_APPROVAL = (
        "execute_write_and_refresh_with_approval"
    )


class ManualIngestionRunStatus(_Vocabulary):
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    STOPPED = "stopped"
    FAILED = "failed"


INTENT_BINDING_TYPES = MappingProxyType(
    {
        CanonicalFactIntent.COMPANY: FactBindingType.COMPANY,
        CanonicalFactIntent.REGION: FactBindingType.REGION,
        CanonicalFactIntent.PRESENCE: FactBindingType.COMPANY_REGION_PRESENCE,
        CanonicalFactIntent.HIRING: FactBindingType.COMPANY_REGION_HIRING,
        CanonicalFactIntent.INTERNSHIPS_COOPS: (
            FactBindingType.COMPANY_REGION_ENTRY_LEVEL
        ),
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS: (
            FactBindingType.COMPANY_REGION_ENTRY_LEVEL
        ),
        CanonicalFactIntent.SCORE_INPUT: FactBindingType.SCORE_INPUT,
    }
)

INTENT_PROVENANCE_FACT_TYPES = MappingProxyType(
    {
        CanonicalFactIntent.COMPANY: ProvenanceFactType.COMPANY_UNIVERSE,
        CanonicalFactIntent.REGION: ProvenanceFactType.REGION_METADATA,
        CanonicalFactIntent.PRESENCE: ProvenanceFactType.COMPANY_PRESENCE,
        CanonicalFactIntent.HIRING: ProvenanceFactType.HIRING_COUNTS,
        CanonicalFactIntent.INTERNSHIPS_COOPS: ProvenanceFactType.INTERNSHIPS_COOPS,
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS: (
            ProvenanceFactType.EARLY_CAREER_PROGRAMS
        ),
        CanonicalFactIntent.SCORE_INPUT: ProvenanceFactType.HIRING_COUNTS,
    }
)


def fact_binding_type_for_intent(intent: CanonicalFactIntent) -> FactBindingType:
    return INTENT_BINDING_TYPES[intent]


def provenance_fact_type_for_intent(
    intent: CanonicalFactIntent,
) -> ProvenanceFactType:
    return INTENT_PROVENANCE_FACT_TYPES[intent]
