"""Bounded in-app alert generation and user relevance service."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.alerts.models import AlertEvent, UserAlert
from backend.alerts.repository import AlertRepository


class AlertEventType(StrEnum):
    NEW_HIRING_ACTIVITY = "new_hiring_activity"
    ENTRY_LEVEL_SIGNAL_CHANGED = "entry_level_signal_changed"
    COMPANY_EXPANDED_IN_REGION = "company_expanded_in_region"
    REGION_SCORE_CHANGED = "region_score_changed"
    INTERNSHIP_WINDOW_OPENED = "internship_window_opened"


class AlertRelevanceReason(StrEnum):
    SAVED_COMPANY = "saved_company"
    SAVED_REGION = "saved_region"
    SAVED_COMPARISON = "saved_comparison"
    SAVED_ROLE_FAMILY = "saved_role_family"
    PREFERRED_REGION = "preferred_region"
    ROLE_INTEREST = "role_interest"


class AlertNotFound(LookupError):
    pass


class AlertBoundaryError(ValueError):
    pass


SAFE_ALERT_CHANGE_FIELDS: frozenset[str] = frozenset(
    {
        "active_posting_count_now",
        "coop_count",
        "currently_hiring_flag",
        "entry_level_access_score",
        "entry_level_full_time_count",
        "formal_early_career_program_flag",
        "internship_count",
        "objective_opportunity_score",
        "presence_status",
        "recurring_internship_signal",
        "score_ruleset_version",
    }
)

SAFE_ALERT_SUMMARY_FIELDS: frozenset[str] = frozenset(
    {
        "basis",
        "changed_fields",
        "company_id",
        "delta",
        "field",
        "region_id",
        "role_family",
        "source_ref_count",
    }
)

UNSAFE_ALERT_KEY_PARTS: tuple[str, ...] = (
    "companies",
    "companydetail",
    "evidence",
    "marketoutput",
    "outputpayload",
    "provenance",
    "regiondetail",
    "regions",
    "sourcesummary",
)


class AlertChangeInput(BaseModel):
    """Safe system-level change contract for creating one alert event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: AlertEventType
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    role_family: str | None = Field(default=None, min_length=1, max_length=64)
    previous_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    change_summary: dict[str, Any] | None = None
    freshness_status: str | None = Field(default=None, max_length=32)
    freshness_observed_at: datetime | None = None
    freshness_expires_at: datetime | None = None
    source_refs: list[str] = Field(default_factory=list)
    change_basis_refs: list[str] = Field(default_factory=list)
    detection_basis: str = Field(min_length=1, max_length=128)

    @field_validator("company_id", "region_id", "role_family", "freshness_status")
    @classmethod
    def _strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("string fields must not be blank")
        return stripped

    @field_validator("source_refs", "change_basis_refs")
    @classmethod
    def _refs_must_be_non_empty(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("alert refs must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("freshness_observed_at", "freshness_expires_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("alert freshness timestamps must be timezone-aware")
        return value

    @field_validator("previous_value", "new_value")
    @classmethod
    def _values_must_be_safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        _validate_safe_mapping(value, allowed_keys=SAFE_ALERT_CHANGE_FIELDS)
        return value

    @field_validator("change_summary")
    @classmethod
    def _summary_must_be_safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        _validate_safe_mapping(value, allowed_keys=SAFE_ALERT_SUMMARY_FIELDS)
        return value

    @model_validator(mode="after")
    def _event_scope_must_match_type(self) -> AlertChangeInput:
        if self.event_type in {
            AlertEventType.NEW_HIRING_ACTIVITY,
            AlertEventType.ENTRY_LEVEL_SIGNAL_CHANGED,
            AlertEventType.COMPANY_EXPANDED_IN_REGION,
            AlertEventType.INTERNSHIP_WINDOW_OPENED,
        } and (not self.company_id or not self.region_id):
            raise ValueError("company-region alert events require company_id and region_id")
        if self.event_type is AlertEventType.REGION_SCORE_CHANGED and not self.region_id:
            raise ValueError("region score alert events require region_id")
        if not self.source_refs and not self.change_basis_refs:
            raise ValueError("alert events require source_refs or change_basis_refs")
        return self


class StructuredAlertState(BaseModel):
    """Current/previous structured facts used for safe partial detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    role_family: str | None = Field(default=None, min_length=1, max_length=64)
    values: dict[str, Any]
    freshness_status: str | None = Field(default=None, max_length=32)
    freshness_observed_at: datetime | None = None
    freshness_expires_at: datetime | None = None
    source_refs: list[str] = Field(default_factory=list)
    change_basis_refs: list[str] = Field(default_factory=list)
    detection_basis: str = Field(default="structured_refreshable_state", max_length=128)

    @field_validator("values")
    @classmethod
    def _values_must_be_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_mapping(value, allowed_keys=SAFE_ALERT_CHANGE_FIELDS)
        return value

    @field_validator("source_refs", "change_basis_refs")
    @classmethod
    def _refs_must_be_non_empty(cls, value: list[str]) -> list[str]:
        return AlertChangeInput._refs_must_be_non_empty(value)


class AlertService:
    def __init__(self, repository: AlertRepository) -> None:
        self._repo = repository

    def create_event(self, change: AlertChangeInput) -> AlertEvent:
        row = AlertEvent(
            alert_event_id=_new_alert_event_id(),
            event_type=change.event_type.value,
            company_id=change.company_id,
            region_id=change.region_id,
            role_family=change.role_family,
            previous_value=deepcopy(change.previous_value),
            new_value=deepcopy(change.new_value),
            change_summary=deepcopy(change.change_summary),
            freshness_status=change.freshness_status,
            freshness_observed_at=change.freshness_observed_at,
            freshness_expires_at=change.freshness_expires_at,
            source_refs=list(change.source_refs),
            change_basis_refs=list(change.change_basis_refs),
            detection_basis=change.detection_basis,
        )
        self._repo.add_event(row)
        self._repo.flush()
        return row

    def detect_changes_from_structured_states(
        self,
        *,
        previous: StructuredAlertState | None,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        """Return events only when an explicit previous state exists.

        A single current row is not enough to infer a market change, so this
        method returns no events instead of fabricating alert history.
        """

        if previous is None:
            return []

        changes: list[AlertChangeInput] = []
        changes.extend(self._detect_presence_change(previous, current))
        changes.extend(self._detect_hiring_change(previous, current))
        changes.extend(self._detect_entry_level_change(previous, current))
        changes.extend(self._detect_region_score_change(previous, current))
        changes.extend(self._detect_internship_window(previous, current))
        return changes

    def create_events_from_structured_states(
        self,
        *,
        previous: StructuredAlertState | None,
        current: StructuredAlertState,
    ) -> list[AlertEvent]:
        rows: list[AlertEvent] = []
        for change in self.detect_changes_from_structured_states(
            previous=previous,
            current=current,
        ):
            rows.append(self.create_event(change))
        return rows

    def materialize_user_alerts_for_event(self, event: AlertEvent) -> list[UserAlert]:
        created: list[UserAlert] = []
        seen_users: set[str] = set()
        for artifact in self._repo.list_relevance_artifacts_for_event(event):
            if artifact.user_id in seen_users:
                continue
            reason = _relevance_reason_for_artifact(event, artifact.artifact_type)
            if reason is None:
                continue
            alert = self._create_user_alert_if_missing(
                user_id=artifact.user_id,
                event=event,
                reason=reason,
                artifact_id=artifact.saved_artifact_id,
                artifact_type=artifact.artifact_type,
                artifact_ref=artifact.artifact_ref,
            )
            if alert is not None:
                created.append(alert)
            seen_users.add(artifact.user_id)

        for profile in self._repo.list_preference_profiles_for_event(event):
            if profile.user_id in seen_users:
                continue
            reason = _relevance_reason_for_preference(event, profile)
            if reason is None:
                continue
            alert = self._create_user_alert_if_missing(
                user_id=profile.user_id,
                event=event,
                reason=reason,
                artifact_id=None,
                artifact_type=None,
                artifact_ref=None,
            )
            if alert is not None:
                created.append(alert)
            seen_users.add(profile.user_id)

        self._repo.flush()
        return created

    def list_user_alerts(
        self,
        user_id: str,
        *,
        include_dismissed: bool = False,
        limit: int = 100,
    ) -> list[tuple[UserAlert, AlertEvent]]:
        return self._repo.list_user_alerts(
            user_id=user_id,
            include_dismissed=include_dismissed,
            limit=limit,
        )

    def mark_read(self, *, user_id: str, user_alert_id: str) -> UserAlert:
        row = self._owned_user_alert(user_id=user_id, user_alert_id=user_alert_id)
        if not row.is_read:
            row.is_read = True
            row.read_at = datetime.now(UTC)
        self._repo.flush()
        return row

    def dismiss(self, *, user_id: str, user_alert_id: str) -> UserAlert:
        row = self._owned_user_alert(user_id=user_id, user_alert_id=user_alert_id)
        if not row.dismissed:
            row.dismissed = True
            row.dismissed_at = datetime.now(UTC)
        if not row.is_read:
            row.is_read = True
            row.read_at = row.dismissed_at
        self._repo.flush()
        return row

    def delete_user_alerts_for_user(self, user_id: str) -> int:
        count = self._repo.delete_user_alerts_for_user(user_id)
        self._repo.flush()
        return count

    def _create_user_alert_if_missing(
        self,
        *,
        user_id: str,
        event: AlertEvent,
        reason: AlertRelevanceReason,
        artifact_id: str | None,
        artifact_type: str | None,
        artifact_ref: str | None,
    ) -> UserAlert | None:
        existing = self._repo.get_user_alert_for_event(
            user_id=user_id,
            alert_event_id=event.alert_event_id,
        )
        if existing is not None:
            return None
        row = UserAlert(
            user_alert_id=_new_user_alert_id(),
            user_id=user_id,
            alert_event_id=event.alert_event_id,
            relevance_reason=reason.value,
            relevance_artifact_id=artifact_id,
            relevance_artifact_type=artifact_type,
            relevance_artifact_ref=artifact_ref,
        )
        self._repo.add_user_alert(row)
        return row

    def _owned_user_alert(self, *, user_id: str, user_alert_id: str) -> UserAlert:
        row = self._repo.get_user_alert(user_alert_id)
        if row is None or row.user_id != user_id:
            raise AlertNotFound(user_alert_id)
        return row

    def _detect_presence_change(
        self,
        previous: StructuredAlertState,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        if previous.values.get("presence_status") == current.values.get("presence_status"):
            return []
        if current.values.get("presence_status") != "present":
            return []
        return [
            _change(
                AlertEventType.COMPANY_EXPANDED_IN_REGION,
                previous,
                current,
                fields=("presence_status",),
            )
        ]

    def _detect_hiring_change(
        self,
        previous: StructuredAlertState,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        prev_hiring = bool(previous.values.get("currently_hiring_flag"))
        curr_hiring = bool(current.values.get("currently_hiring_flag"))
        prev_count = _number(previous.values.get("active_posting_count_now"))
        curr_count = _number(current.values.get("active_posting_count_now"))
        if curr_hiring and (not prev_hiring or curr_count > prev_count):
            return [
                _change(
                    AlertEventType.NEW_HIRING_ACTIVITY,
                    previous,
                    current,
                    fields=("currently_hiring_flag", "active_posting_count_now"),
                )
            ]
        return []

    def _detect_entry_level_change(
        self,
        previous: StructuredAlertState,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        fields = (
            "entry_level_access_score",
            "internship_count",
            "coop_count",
            "entry_level_full_time_count",
            "formal_early_career_program_flag",
            "recurring_internship_signal",
        )
        changed = tuple(
            field
            for field in fields
            if previous.values.get(field) != current.values.get(field)
        )
        if not changed:
            return []
        return [
            _change(
                AlertEventType.ENTRY_LEVEL_SIGNAL_CHANGED,
                previous,
                current,
                fields=changed,
            )
        ]

    def _detect_region_score_change(
        self,
        previous: StructuredAlertState,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        if previous.values.get("objective_opportunity_score") == current.values.get(
            "objective_opportunity_score"
        ):
            return []
        return [
            _change(
                AlertEventType.REGION_SCORE_CHANGED,
                previous,
                current,
                fields=("objective_opportunity_score", "score_ruleset_version"),
            )
        ]

    def _detect_internship_window(
        self,
        previous: StructuredAlertState,
        current: StructuredAlertState,
    ) -> list[AlertChangeInput]:
        prev_count = _number(previous.values.get("internship_count")) + _number(
            previous.values.get("coop_count")
        )
        curr_count = _number(current.values.get("internship_count")) + _number(
            current.values.get("coop_count")
        )
        if prev_count <= 0 and curr_count > 0:
            return [
                _change(
                    AlertEventType.INTERNSHIP_WINDOW_OPENED,
                    previous,
                    current,
                    fields=("internship_count", "coop_count"),
                )
            ]
        return []


def alert_event_data(row: AlertEvent) -> dict[str, Any]:
    return {
        "alert_event_id": row.alert_event_id,
        "event_type": row.event_type,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "role_family": row.role_family,
        "previous_value": deepcopy(row.previous_value),
        "new_value": deepcopy(row.new_value),
        "change_summary": deepcopy(row.change_summary),
        "freshness_status": row.freshness_status,
        "freshness_observed_at": _dt(row.freshness_observed_at),
        "freshness_expires_at": _dt(row.freshness_expires_at),
        "source_refs": list(row.source_refs or []),
        "change_basis_refs": list(row.change_basis_refs or []),
        "detection_basis": row.detection_basis,
        "created_at": _dt(row.created_at),
    }


def user_alert_data(row: UserAlert, event: AlertEvent) -> dict[str, Any]:
    return {
        "user_alert_id": row.user_alert_id,
        "user_id": row.user_id,
        "alert_event_id": row.alert_event_id,
        "is_read": row.is_read,
        "dismissed": row.dismissed,
        "read_at": _dt(row.read_at),
        "dismissed_at": _dt(row.dismissed_at),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
        "relevance": {
            "reason": row.relevance_reason,
            "artifact_id": row.relevance_artifact_id,
            "artifact_type": row.relevance_artifact_type,
            "artifact_ref": row.relevance_artifact_ref,
        },
        "event": alert_event_data(event),
    }


def _change(
    event_type: AlertEventType,
    previous: StructuredAlertState,
    current: StructuredAlertState,
    *,
    fields: tuple[str, ...],
) -> AlertChangeInput:
    changed_fields = [
        field for field in fields if previous.values.get(field) != current.values.get(field)
    ]
    previous_value = {
        field: previous.values.get(field)
        for field in changed_fields
        if field in previous.values
    }
    new_value = {
        field: current.values.get(field)
        for field in changed_fields
        if field in current.values
    }
    delta: float | None = None
    if len(changed_fields) == 1:
        field = changed_fields[0]
        previous_number = _number_or_none(previous.values.get(field))
        current_number = _number_or_none(current.values.get(field))
        if previous_number is not None and current_number is not None:
            delta = current_number - previous_number
    return AlertChangeInput(
        event_type=event_type,
        company_id=current.company_id,
        region_id=current.region_id,
        role_family=current.role_family,
        previous_value=previous_value,
        new_value=new_value,
        change_summary={
            "changed_fields": changed_fields,
            "delta": delta,
            "source_ref_count": len(current.source_refs),
        },
        freshness_status=current.freshness_status,
        freshness_observed_at=current.freshness_observed_at,
        freshness_expires_at=current.freshness_expires_at,
        source_refs=current.source_refs,
        change_basis_refs=current.change_basis_refs,
        detection_basis=current.detection_basis,
    )


def _relevance_reason_for_artifact(
    event: AlertEvent,
    artifact_type: str,
) -> AlertRelevanceReason | None:
    if artifact_type == "company" and event.company_id:
        return AlertRelevanceReason.SAVED_COMPANY
    if artifact_type == "region" and event.region_id:
        return AlertRelevanceReason.SAVED_REGION
    if artifact_type == "comparison" and event.region_id:
        return AlertRelevanceReason.SAVED_COMPARISON
    if artifact_type == "role_family" and event.role_family:
        return AlertRelevanceReason.SAVED_ROLE_FAMILY
    return None


def _relevance_reason_for_preference(
    event: AlertEvent,
    profile: Any,
) -> AlertRelevanceReason | None:
    if event.region_id and event.region_id in (profile.preferred_regions or []):
        return AlertRelevanceReason.PREFERRED_REGION
    if event.role_family and event.role_family in (profile.role_interests or []):
        return AlertRelevanceReason.ROLE_INTEREST
    return None


def _validate_safe_mapping(value: Mapping[str, Any], *, allowed_keys: frozenset[str]) -> None:
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("alert change metadata keys must be non-empty strings")
        normalized = _normalize_key(key)
        if key not in allowed_keys:
            raise ValueError(f"alert change metadata field {key!r} is not allowed")
        if any(part in normalized for part in UNSAFE_ALERT_KEY_PARTS):
            raise AlertBoundaryError("alert change metadata must not copy market payloads")
        _validate_safe_json_value(item)


def _validate_safe_json_value(value: Any) -> None:
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list):
        for item in value:
            _validate_safe_json_value(item)
        return
    raise ValueError("alert change metadata values must be JSON primitives or lists")


def _normalize_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _number(value: Any) -> float:
    converted = _number_or_none(value)
    return converted if converted is not None else 0.0


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _new_alert_event_id() -> str:
    return f"alert_event_{uuid4().hex[:48]}"


def _new_user_alert_id() -> str:
    return f"user_alert_{uuid4().hex[:49]}"
