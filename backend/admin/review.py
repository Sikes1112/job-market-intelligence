"""Read-only admin data review and audit finding lifecycle services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.admin.models import AuditFindingReview
from backend.admin.repository import AdminEventLogRepository
from backend.admin.roles import AdminRole
from backend.admin.service import AdminEventLogInput, AdminEventLogService
from backend.audit.payloads import AuditFinding
from backend.audit.service import AuditService
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import SourceRef


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditFindingLifecycleState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


AUDIT_FINDING_TRANSITIONS: dict[
    AuditFindingLifecycleState, frozenset[AuditFindingLifecycleState]
] = {
    AuditFindingLifecycleState.OPEN: frozenset(
        {
            AuditFindingLifecycleState.ACKNOWLEDGED,
            AuditFindingLifecycleState.ESCALATED,
            AuditFindingLifecycleState.DISMISSED,
        }
    ),
    AuditFindingLifecycleState.ACKNOWLEDGED: frozenset(
        {
            AuditFindingLifecycleState.RESOLVED,
            AuditFindingLifecycleState.ESCALATED,
            AuditFindingLifecycleState.DISMISSED,
        }
    ),
    AuditFindingLifecycleState.ESCALATED: frozenset(
        {
            AuditFindingLifecycleState.ACKNOWLEDGED,
            AuditFindingLifecycleState.RESOLVED,
            AuditFindingLifecycleState.DISMISSED,
        }
    ),
    AuditFindingLifecycleState.RESOLVED: frozenset({AuditFindingLifecycleState.OPEN}),
    AuditFindingLifecycleState.DISMISSED: frozenset({AuditFindingLifecycleState.OPEN}),
}


class AuditFindingLifecycleError(ValueError):
    """Raised when a finding lifecycle transition is invalid."""


class AuditFindingNotFound(LookupError):
    """Raised when a lifecycle action references an unknown audit finding."""


class AuditFindingTransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1, max_length=255)
    target_state: AuditFindingLifecycleState
    reason: str = Field(min_length=1, max_length=2048)

    @field_validator("finding_id", "reason")
    @classmethod
    def _strings_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


@dataclass(frozen=True, slots=True)
class AuditFindingReviewView:
    finding_id: str
    review_state: AuditFindingLifecycleState
    current_finding: AuditFinding | None
    review: AuditFindingReview | None


class AdminReviewService:
    """Read-only review surface over market rows and audit findings."""

    def __init__(self, *, session: Session) -> None:
        self._session = session

    def list_companies(self, *, limit: int = 100) -> list[Company]:
        rows = self._session.execute(
            select(Company).order_by(Company.company_id).limit(limit)
        ).scalars()
        return list(rows)

    def get_company(self, company_id: str) -> Company | None:
        return self._session.get(Company, company_id)

    def list_presence(self, *, limit: int = 100) -> list[CompanyRegionPresence]:
        rows = self._session.execute(
            select(CompanyRegionPresence)
            .order_by(
                CompanyRegionPresence.company_id,
                CompanyRegionPresence.region_id,
                CompanyRegionPresence.presence_id,
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def get_presence(self, presence_id: str) -> CompanyRegionPresence | None:
        return self._session.get(CompanyRegionPresence, presence_id)

    def list_hiring(self, *, limit: int = 100) -> list[CompanyRegionHiring]:
        rows = self._session.execute(
            select(CompanyRegionHiring)
            .order_by(
                CompanyRegionHiring.company_id,
                CompanyRegionHiring.region_id,
                CompanyRegionHiring.hiring_id,
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def get_hiring(self, hiring_id: str) -> CompanyRegionHiring | None:
        return self._session.get(CompanyRegionHiring, hiring_id)

    def list_entry_level(self, *, limit: int = 100) -> list[CompanyRegionEntryLevel]:
        rows = self._session.execute(
            select(CompanyRegionEntryLevel)
            .order_by(
                CompanyRegionEntryLevel.company_id,
                CompanyRegionEntryLevel.region_id,
                CompanyRegionEntryLevel.entry_level_id,
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def get_entry_level(self, entry_level_id: str) -> CompanyRegionEntryLevel | None:
        return self._session.get(CompanyRegionEntryLevel, entry_level_id)

    def list_source_refs(self, *, limit: int = 100) -> list[SourceRef]:
        rows = self._session.execute(
            select(SourceRef).order_by(SourceRef.source_id).limit(limit)
        ).scalars()
        return list(rows)

    def get_source_ref(self, source_id: str) -> SourceRef | None:
        return self._session.get(SourceRef, source_id)

    def list_audit_findings(self, *, limit: int = 100) -> list[AuditFindingReviewView]:
        current = _current_findings_by_id(self._session)
        reviews = _reviews_by_id(self._session)
        finding_ids = sorted(
            set(current) | set(reviews),
            key=lambda finding_id: (
                current[finding_id].category.value if finding_id in current else "",
                finding_id,
            ),
        )
        return [
            _view_for(finding_id, current.get(finding_id), reviews.get(finding_id))
            for finding_id in finding_ids[:limit]
        ]

    def get_audit_finding(self, finding_id: str) -> AuditFindingReviewView | None:
        current = _current_findings_by_id(self._session)
        review = self._session.get(AuditFindingReview, finding_id)
        finding = current.get(finding_id)
        if finding is None and review is None:
            return None
        return _view_for(finding_id, finding, review)


class AuditFindingLifecycleService:
    """Controlled audit finding lifecycle transitions."""

    def __init__(
        self,
        *,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._now = clock or _utc_now
        self._event_log = AdminEventLogService(
            AdminEventLogRepository(session),
            clock=self._now,
        )

    def transition(
        self,
        transition: AuditFindingTransitionInput,
        *,
        actor: str,
        role: AdminRole,
        request_id: str | None = None,
    ) -> AuditFindingReviewView:
        finding = _current_findings_by_id(self._session).get(transition.finding_id)
        row = self._session.get(AuditFindingReview, transition.finding_id)
        if finding is None and row is None:
            raise AuditFindingNotFound(transition.finding_id)

        current_state = (
            AuditFindingLifecycleState(row.review_state)
            if row is not None
            else AuditFindingLifecycleState.OPEN
        )
        if transition.target_state not in AUDIT_FINDING_TRANSITIONS[current_state]:
            raise AuditFindingLifecycleError(
                f"invalid audit finding transition: "
                f"{current_state.value} -> {transition.target_state.value}"
            )

        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=UTC)

        if row is None:
            row = AuditFindingReview(
                finding_id=transition.finding_id,
                created_at=now,
                updated_at=now,
                last_transitioned_at=now,
            )
            self._session.add(row)

        _sync_finding_metadata(row, finding)
        before = _state_snapshot(row, state=current_state)

        row.review_state = transition.target_state.value
        row.updated_at = now
        row.last_transitioned_at = now
        row.last_transition_actor = actor
        row.last_transition_role = role.value
        row.last_transition_reason = transition.reason
        after = _state_snapshot(row, state=transition.target_state)

        self._session.flush()
        self._event_log.record_event(
            AdminEventLogInput(
                actor=actor,
                role=role,
                action="admin.audit_finding.lifecycle_transition",
                object_type="audit_finding",
                object_id=transition.finding_id,
                before_state=before,
                after_state=after,
                reason=transition.reason,
                request_id=request_id,
            )
        )
        return _view_for(transition.finding_id, finding, row)


def audit_finding_review_data(view: AuditFindingReviewView) -> dict[str, Any]:
    finding = view.current_finding
    review = view.review
    return {
        "finding_id": view.finding_id,
        "review_state": view.review_state.value,
        "is_current": finding is not None,
        "severity": (
            finding.severity.value
            if finding is not None
            else review.severity if review is not None else None
        ),
        "category": (
            finding.category.value
            if finding is not None
            else review.category if review is not None else None
        ),
        "scope_type": (
            finding.scope_type
            if finding is not None
            else review.scope_type if review is not None else None
        ),
        "scope_ref": (
            finding.scope_ref
            if finding is not None
            else review.scope_ref if review is not None else None
        ),
        "message": (
            finding.message
            if finding is not None
            else review.message if review is not None else None
        ),
        "evidence_refs": (
            list(finding.evidence_refs)
            if finding is not None
            else list(review.evidence_refs or []) if review is not None else []
        ),
        "recommendation": (
            finding.recommendation
            if finding is not None
            else review.recommendation if review is not None else None
        ),
        "last_transitioned_at": (
            _dt(review.last_transitioned_at) if review is not None else None
        ),
        "last_transition_actor": (
            review.last_transition_actor if review is not None else None
        ),
        "last_transition_role": review.last_transition_role if review is not None else None,
        "last_transition_reason": (
            review.last_transition_reason if review is not None else None
        ),
        "allowed_transitions": [
            state.value for state in sorted(
                AUDIT_FINDING_TRANSITIONS[view.review_state],
                key=lambda item: item.value,
            )
        ],
    }


def _current_findings_by_id(session: Session) -> dict[str, AuditFinding]:
    report = AuditService(session=session).run_audit()
    return {finding.finding_id: finding for finding in report.findings}


def _reviews_by_id(session: Session) -> dict[str, AuditFindingReview]:
    rows = session.execute(
        select(AuditFindingReview).order_by(AuditFindingReview.finding_id)
    ).scalars()
    return {row.finding_id: row for row in rows}


def _view_for(
    finding_id: str,
    finding: AuditFinding | None,
    review: AuditFindingReview | None,
) -> AuditFindingReviewView:
    state = (
        AuditFindingLifecycleState(review.review_state)
        if review is not None
        else AuditFindingLifecycleState.OPEN
    )
    return AuditFindingReviewView(
        finding_id=finding_id,
        review_state=state,
        current_finding=finding,
        review=review,
    )


def _sync_finding_metadata(row: AuditFindingReview, finding: AuditFinding | None) -> None:
    if finding is None:
        return
    row.category = finding.category.value
    row.severity = finding.severity.value
    row.scope_type = finding.scope_type
    row.scope_ref = finding.scope_ref
    row.message = finding.message
    row.evidence_refs = list(finding.evidence_refs)
    row.recommendation = finding.recommendation


def _state_snapshot(
    row: AuditFindingReview,
    *,
    state: AuditFindingLifecycleState,
) -> dict[str, Any]:
    return {
        "finding_id": row.finding_id,
        "review_state": state.value,
        "category": row.category,
        "severity": row.severity,
        "scope_type": row.scope_type,
        "scope_ref": row.scope_ref,
        "message": row.message,
        "last_transitioned_at": _dt(row.last_transitioned_at),
        "last_transition_actor": row.last_transition_actor,
        "last_transition_role": row.last_transition_role,
        "last_transition_reason": row.last_transition_reason,
    }


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None

