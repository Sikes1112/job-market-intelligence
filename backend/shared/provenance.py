"""Layer 3A provenance policy vocabulary.

This module is intentionally limited to canonical terms and conservative
freshness expectations. It does not create provenance tables, ingestion logic,
audit enforcement, or scoring behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class DataOrigin(_Vocabulary):
    DEMO_SEED = "demo_seed"
    SYNTHETIC_OR_CURATED_DEMO = "synthetic_or_curated_demo"
    REAL_OBSERVED = "real_observed"
    REAL_DERIVED = "real_derived"
    MANUAL_REVIEWED = "manual_reviewed"
    UNKNOWN_ORIGIN = "unknown_origin"


class ObservationStatus(_Vocabulary):
    UNKNOWN = "unknown"
    ZERO_OBSERVED = "zero_observed"
    POSITIVE_OBSERVED = "positive_observed"
    NOT_APPLICABLE = "not_applicable"
    NOT_COLLECTED = "not_collected"
    STALE = "stale"
    CONFLICTING = "conflicting"
    LOW_CONFIDENCE = "low_confidence"


class SourceType(_Vocabulary):
    COMPANY_OFFICIAL = "company_official"
    ATS_JOB_BOARD = "ats_job_board"
    GOVERNMENT_PUBLIC_DATA = "government_public_data"
    UNIVERSITY_OR_COOP_BOARD = "university_or_coop_board"
    REGIONAL_ECONOMIC_DATASET = "regional_economic_dataset"
    REPUTABLE_THIRD_PARTY_AGGREGATOR = "reputable_third_party_aggregator"
    MANUAL_RESEARCH = "manual_research"
    USER_SUBMITTED = "user_submitted"
    LLM_GENERATED = "llm_generated"
    UNKNOWN_SOURCE = "unknown_source"


class SourceAcceptability(_Vocabulary):
    ALLOWED = "allowed"
    ALLOWED_WITH_CAUTION = "allowed_with_caution"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    DISALLOWED = "disallowed"


class LicenseTermsCategory(_Vocabulary):
    PUBLIC = "public"
    PERMISSIVE = "permissive"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"
    PROHIBITED = "prohibited"


class FreshnessCategory(_Vocabulary):
    FAST_CHANGING = "fast_changing"
    SEASONAL = "seasonal"
    MEDIUM_CHANGING = "medium_changing"
    SLOW_CHANGING = "slow_changing"


class ProvenanceFactType(_Vocabulary):
    COMPANY_UNIVERSE = "company_universe"
    COMPANY_PRESENCE = "company_presence"
    HIRING_COUNTS = "hiring_counts"
    INTERNSHIPS_COOPS = "internships_coops"
    EARLY_CAREER_PROGRAMS = "early_career_programs"
    REGION_METADATA = "region_metadata"


class FactBindingType(_Vocabulary):
    COMPANY = "company"
    REGION = "region"
    COMPANY_REGION_PRESENCE = "company_region_presence"
    COMPANY_REGION_HIRING = "company_region_hiring"
    COMPANY_REGION_ENTRY_LEVEL = "company_region_entry_level"
    SCORE_INPUT = "score_input"


@dataclass(frozen=True, slots=True)
class FreshnessWindow:
    """Conservative age threshold for treating a fact as current."""

    category: FreshnessCategory
    max_age_days: int


DEMO_DATA_ORIGINS: frozenset[DataOrigin] = frozenset(
    {
        DataOrigin.DEMO_SEED,
        DataOrigin.SYNTHETIC_OR_CURATED_DEMO,
    }
)

REAL_DATA_ORIGINS: frozenset[DataOrigin] = frozenset(
    {
        DataOrigin.REAL_OBSERVED,
        DataOrigin.REAL_DERIVED,
        DataOrigin.MANUAL_REVIEWED,
    }
)

SOURCE_TYPE_DEFAULT_ACCEPTABILITY: Mapping[SourceType, SourceAcceptability] = (
    MappingProxyType(
        {
            SourceType.COMPANY_OFFICIAL: SourceAcceptability.ALLOWED,
            SourceType.ATS_JOB_BOARD: SourceAcceptability.ALLOWED,
            SourceType.GOVERNMENT_PUBLIC_DATA: SourceAcceptability.ALLOWED,
            SourceType.UNIVERSITY_OR_COOP_BOARD: SourceAcceptability.ALLOWED,
            SourceType.REGIONAL_ECONOMIC_DATASET: SourceAcceptability.ALLOWED,
            SourceType.REPUTABLE_THIRD_PARTY_AGGREGATOR: (
                SourceAcceptability.ALLOWED_WITH_CAUTION
            ),
            SourceType.MANUAL_RESEARCH: SourceAcceptability.MANUAL_REVIEW_REQUIRED,
            SourceType.USER_SUBMITTED: SourceAcceptability.MANUAL_REVIEW_REQUIRED,
            SourceType.LLM_GENERATED: SourceAcceptability.DISALLOWED,
            SourceType.UNKNOWN_SOURCE: SourceAcceptability.DISALLOWED,
        }
    )
)

FRESHNESS_WINDOWS: Mapping[ProvenanceFactType, FreshnessWindow] = MappingProxyType(
    {
        ProvenanceFactType.COMPANY_UNIVERSE: FreshnessWindow(
            category=FreshnessCategory.SLOW_CHANGING,
            max_age_days=180,
        ),
        ProvenanceFactType.COMPANY_PRESENCE: FreshnessWindow(
            category=FreshnessCategory.SLOW_CHANGING,
            max_age_days=180,
        ),
        ProvenanceFactType.HIRING_COUNTS: FreshnessWindow(
            category=FreshnessCategory.FAST_CHANGING,
            max_age_days=14,
        ),
        ProvenanceFactType.INTERNSHIPS_COOPS: FreshnessWindow(
            category=FreshnessCategory.SEASONAL,
            max_age_days=120,
        ),
        ProvenanceFactType.EARLY_CAREER_PROGRAMS: FreshnessWindow(
            category=FreshnessCategory.MEDIUM_CHANGING,
            max_age_days=90,
        ),
        ProvenanceFactType.REGION_METADATA: FreshnessWindow(
            category=FreshnessCategory.SLOW_CHANGING,
            max_age_days=365,
        ),
    }
)
