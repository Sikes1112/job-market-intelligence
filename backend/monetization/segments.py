"""Audience and buyer segmentation for the monetization foundation.

Audience segments describe the people receiving guidance. Buyer segments
describe institutional purchasers. Keeping those concepts separate prevents
license metadata from becoming a proxy for recommendation behavior.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class SegmentCategory(_Vocabulary):
    AUDIENCE = "audience"
    BUYER = "buyer"


class AudienceSegmentKey(_Vocabulary):
    STUDENTS = "students"
    EARLY_CAREER_JOB_SEEKERS = "early_career_job_seekers"
    RELOCATION_CANDIDATES = "relocation_candidates"
    PARENTS_ADVISORS = "parents_advisors"


class BuyerSegmentKey(_Vocabulary):
    CAREER_CENTERS = "career_centers"
    BOOTCAMPS = "bootcamps"
    UNIVERSITIES = "universities"
    WORKFORCE_BOARDS = "workforce_boards"


class SegmentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: AudienceSegmentKey | BuyerSegmentKey
    category: SegmentCategory
    label: str = Field(min_length=1, max_length=96)
    description: str = Field(min_length=1, max_length=320)
    use_cases: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("label", "description")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _clean_required_string(value, "segment metadata")

    @field_validator("use_cases")
    @classmethod
    def _use_cases_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "segment use case") for item in value)


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    return stripped


_AUDIENCE_SEGMENTS: dict[AudienceSegmentKey, SegmentDefinition] = {
    AudienceSegmentKey.STUDENTS: SegmentDefinition(
        key=AudienceSegmentKey.STUDENTS,
        category=SegmentCategory.AUDIENCE,
        label="Students",
        description=(
            "Undergraduate, graduate, community-college, and certificate learners "
            "using market evidence to plan internships, first jobs, and locations."
        ),
        use_cases=(
            "Compare early-career access across regions.",
            "Turn broad interests into a practical market shortlist.",
            "Prepare advising conversations with evidence-backed tradeoffs.",
        ),
    ),
    AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS: SegmentDefinition(
        key=AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
        category=SegmentCategory.AUDIENCE,
        label="Early-career job seekers",
        description=(
            "Recent graduates and first-to-third-job seekers who need durable "
            "market guidance before investing time in applications or relocation."
        ),
        use_cases=(
            "Prioritize markets with stronger entry-level access signals.",
            "Build a target-company and region watchlist.",
            "Understand caveats before committing to a search strategy.",
        ),
    ),
    AudienceSegmentKey.RELOCATION_CANDIDATES: SegmentDefinition(
        key=AudienceSegmentKey.RELOCATION_CANDIDATES,
        category=SegmentCategory.AUDIENCE,
        label="Relocation candidates",
        description=(
            "People deciding whether a move is worth the opportunity tradeoff, "
            "including candidates comparing unfamiliar markets."
        ),
        use_cases=(
            "Compare regions before planning visits or applications.",
            "Identify fallback markets with credible evidence.",
            "Evaluate company geography without relying on anecdotes.",
        ),
    ),
    AudienceSegmentKey.PARENTS_ADVISORS: SegmentDefinition(
        key=AudienceSegmentKey.PARENTS_ADVISORS,
        category=SegmentCategory.AUDIENCE,
        label="Parents and advisors",
        description=(
            "Family members, mentors, and advisors supporting someone else's "
            "market decision without needing private recommendation internals."
        ),
        use_cases=(
            "Review plain-language market tradeoffs.",
            "Support school and career-center advising conversations.",
            "Help validate whether a plan is evidence-backed and realistic.",
        ),
    ),
}

_BUYER_SEGMENTS: dict[BuyerSegmentKey, SegmentDefinition] = {
    BuyerSegmentKey.CAREER_CENTERS: SegmentDefinition(
        key=BuyerSegmentKey.CAREER_CENTERS,
        category=SegmentCategory.BUYER,
        label="Career centers",
        description=(
            "Career-services teams buying access so students can explore markets "
            "and advisors can support evidence-based search planning."
        ),
        use_cases=(
            "Provide licensed student access.",
            "Standardize market-guidance conversations.",
            "Support advising without reading private recommendation internals.",
        ),
    ),
    BuyerSegmentKey.BOOTCAMPS: SegmentDefinition(
        key=BuyerSegmentKey.BOOTCAMPS,
        category=SegmentCategory.BUYER,
        label="Bootcamps",
        description=(
            "Career-transition programs that need practical market targeting for "
            "cohorts entering new technical or adjacent roles."
        ),
        use_cases=(
            "Guide cohorts toward realistic target markets.",
            "Create reusable market strategy templates.",
            "Support placement teams with reportable market evidence.",
        ),
    ),
    BuyerSegmentKey.UNIVERSITIES: SegmentDefinition(
        key=BuyerSegmentKey.UNIVERSITIES,
        category=SegmentCategory.BUYER,
        label="Universities",
        description=(
            "Institutional purchasers serving multiple schools, departments, or "
            "student populations with governed access and advising workflows."
        ),
        use_cases=(
            "License broad student access.",
            "Support school-specific career programs.",
            "Review aggregate, privacy-preserving usage signals.",
        ),
    ),
    BuyerSegmentKey.WORKFORCE_BOARDS: SegmentDefinition(
        key=BuyerSegmentKey.WORKFORCE_BOARDS,
        category=SegmentCategory.BUYER,
        label="Workforce boards",
        description=(
            "Public or nonprofit workforce organizations helping job seekers make "
            "regional opportunity decisions with evidence rather than hype."
        ),
        use_cases=(
            "Support regional job-seeker guidance.",
            "Compare opportunity across local and neighboring markets.",
            "Publish workforce-program guidance without payment-provider coupling.",
        ),
    ),
}

AUDIENCE_SEGMENTS = MappingProxyType(_AUDIENCE_SEGMENTS)
BUYER_SEGMENTS = MappingProxyType(_BUYER_SEGMENTS)


def audience_segment_definitions() -> tuple[SegmentDefinition, ...]:
    return tuple(AUDIENCE_SEGMENTS[key] for key in AudienceSegmentKey)


def buyer_segment_definitions() -> tuple[SegmentDefinition, ...]:
    return tuple(BUYER_SEGMENTS[key] for key in BuyerSegmentKey)


def segment_definition(
    key: AudienceSegmentKey | BuyerSegmentKey | str,
) -> SegmentDefinition:
    if isinstance(key, AudienceSegmentKey):
        return AUDIENCE_SEGMENTS[key]
    if isinstance(key, BuyerSegmentKey):
        return BUYER_SEGMENTS[key]

    value = str(key)
    if value in AudienceSegmentKey.values():
        return AUDIENCE_SEGMENTS[AudienceSegmentKey(value)]
    if value in BuyerSegmentKey.values():
        return BUYER_SEGMENTS[BuyerSegmentKey(value)]
    raise ValueError(f"Unknown monetization segment: {value!r}")

