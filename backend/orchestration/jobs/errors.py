"""Job error/warning vocabularies and schemas.

Source: ``JOB_CONTRACT_SPEC.md`` §2.3, §17, §18, §20.

These are *contracts*, not handlers. Nothing in this module triggers retries,
escalates failures, or writes to the DB.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    PARSE_FAILURE = "PARSE_FAILURE"
    INTEGRITY_CHECK_FAILED = "INTEGRITY_CHECK_FAILED"
    TIMEOUT = "TIMEOUT"
    NO_MEANINGFUL_CHANGE = "NO_MEANINGFUL_CHANGE"
    INTERNAL_EXCEPTION = "INTERNAL_EXCEPTION"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


# JOB_CONTRACT_SPEC.md §20: codes that the runtime may safely retry without
# operator intervention. PARSE_FAILURE and INTERNAL_EXCEPTION are listed as
# "sometimes" in the spec — they are intentionally NOT in this set so callers
# must opt in deliberately.
RETRYABLE_ERROR_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.SOURCE_UNAVAILABLE,
        ErrorCode.RATE_LIMITED,
        ErrorCode.TIMEOUT,
    }
)


def is_retryable(error_code: ErrorCode | str) -> bool:
    return ErrorCode(error_code) in RETRYABLE_ERROR_CODES


class WarningSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class JobError(BaseModel):
    """Standard error schema (``JOB_CONTRACT_SPEC.md`` §18)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_code: ErrorCode
    error_message: str = Field(min_length=1)
    error_details: dict[str, Any] | None = None


class JobWarning(BaseModel):
    """Standard warning schema (``JOB_CONTRACT_SPEC.md`` §17).

    ``warning_code`` is intentionally a free-form string: each domain owns its
    own warning vocabulary. ``scope_type`` is similarly free-form here; the
    documented values (``company``, ``region``, ``company_region_pair``,
    ``comparison``) are conventions enforced by callers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    warning_code: str = Field(min_length=1)
    severity: WarningSeverity
    message: str = Field(min_length=1)
    scope_type: str | None = None
    scope_ref: str | None = None
