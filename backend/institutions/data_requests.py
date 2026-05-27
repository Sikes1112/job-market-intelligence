"""Institutional data export/deletion request records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InstitutionalDataRequestType(StrEnum):
    ORGANIZATION_EXPORT = "organization_export"
    ORGANIZATION_DELETION = "organization_deletion"
    STUDENT_EXPORT = "student_export"
    STUDENT_DELETION = "student_deletion"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InstitutionalDataRequestSubjectType(StrEnum):
    ORGANIZATION = "organization"
    STUDENT = "student"


class InstitutionalDataRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELED = "canceled"


class InstitutionalDataRequestCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_type: InstitutionalDataRequestType
    subject_type: InstitutionalDataRequestSubjectType | None = None
    subject_user_id: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=1024)
    metadata: dict[str, Any] | None = None

    @field_validator("subject_user_id", "reason")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="before")
    @classmethod
    def _default_subject_type(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("subject_type") is not None:
            return data
        request_type = data.get("request_type")
        subject_type = (
            InstitutionalDataRequestSubjectType.ORGANIZATION
            if request_type
            in {
                InstitutionalDataRequestType.ORGANIZATION_EXPORT,
                InstitutionalDataRequestType.ORGANIZATION_EXPORT.value,
                InstitutionalDataRequestType.ORGANIZATION_DELETION,
                InstitutionalDataRequestType.ORGANIZATION_DELETION.value,
            }
            else InstitutionalDataRequestSubjectType.STUDENT
        )
        return {**data, "subject_type": subject_type}


class InstitutionalDataRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_request_id: str
    organization_id: str
    requester_user_id: str
    request_type: InstitutionalDataRequestType
    subject_type: InstitutionalDataRequestSubjectType
    subject_user_id: str | None = None
    status: InstitutionalDataRequestStatus
    reason: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    execution_note: str


class InstitutionalDataRequestListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_requests: list[InstitutionalDataRequestPayload] = Field(default_factory=list)
