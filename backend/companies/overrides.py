"""Override decision input shape.

The ``override_ledger`` table from ``DATA_MODEL.md`` §11 is intentionally
deferred for MVP. The MVP note in §11 says override fields on ``companies``
are sufficient — :class:`Override` carries the rationale that gets stamped
onto ``Company.eligibility_override_reason`` (with
``Company.eligibility_override_flag = True``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Override(BaseModel):
    """An admin's declaration that a company should be included despite the
    default eligibility rule rejecting (or being uncertain about) it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(min_length=1)
    decided_by: str | None = None

    @field_validator("reason")
    @classmethod
    def _reason_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("override reason must not be whitespace")
        return value
