"""Repository helpers for explicit trust assessment persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.trust.models import RiskRoutingDecision, TrustAssessment
from backend.trust.schemas import (
    EvidenceRequirementResult,
    RankingInfluenceDecision,
    RankingInfluenceReasonCode,
    RiskLevel,
    RiskRoutingDecisionResult,
    RiskRoutingReasonCode,
    RoutingOutcome,
    TrustAssessmentResult,
    TrustAssessmentSubjectType,
    TrustTier,
    TrustWarning,
)

TrustUpsertOutcome = Literal["created", "updated", "unchanged"]


class TrustAssessmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_assessment(
        self,
        result: TrustAssessmentResult,
        *,
        trust_assessment_id: str | None = None,
    ) -> TrustAssessment:
        row = TrustAssessment(
            trust_assessment_id=trust_assessment_id or f"trust_{uuid4().hex}",
            subject_type=result.subject_type.value,
            subject_id=result.subject_id,
            trust_tier=result.trust_tier.value,
            assessment_source=result.assessment_source,
            assessment_version=result.assessment_version,
            evidence_requirements_met_json=_requirements_json(
                result.evidence_requirements_met
            ),
            evidence_requirements_missing_json=_requirements_json(
                result.evidence_requirements_missing
            ),
            evidence_requirements_failed_json=_requirements_json(
                result.evidence_requirements_failed
            ),
            evidence_requirements_not_applicable_json=_requirements_json(
                result.evidence_requirements_not_applicable
            ),
            warnings_json=_warnings_json(result.warnings),
            reasons_json=list(result.reasons),
            ranking_influence_allowed=result.ranking_influence_allowed,
            assessed_at=result.assessed_at,
            expires_at=result.expires_at,
            next_assessment_at=result.next_assessment_at,
        )
        self._session.add(row)
        return row

    def upsert_assessment(
        self,
        result: TrustAssessmentResult,
        *,
        trust_assessment_id: str,
    ) -> tuple[TrustAssessment, TrustUpsertOutcome]:
        payload = _assessment_payload(result)
        row = self._session.get(TrustAssessment, trust_assessment_id)
        if row is None:
            row = TrustAssessment(
                trust_assessment_id=trust_assessment_id,
                **payload,
            )
            self._session.add(row)
            return row, "created"
        if _row_matches(row, payload):
            return row, "unchanged"
        _apply_payload(row, payload)
        return row, "updated"

    def latest_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
    ) -> TrustAssessmentResult | None:
        subject_value = (
            subject_type.value
            if isinstance(subject_type, TrustAssessmentSubjectType)
            else subject_type
        )
        row = self._session.execute(
            select(TrustAssessment)
            .where(
                TrustAssessment.subject_type == subject_value,
                TrustAssessment.subject_id == subject_id,
            )
            .order_by(
                TrustAssessment.assessed_at.desc(),
                TrustAssessment.trust_assessment_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return assessment_from_row(row)

    def add_routing_decision(
        self,
        result: RiskRoutingDecisionResult,
        *,
        risk_routing_decision_id: str | None = None,
        trust_assessment_id: str | None = None,
    ) -> RiskRoutingDecision:
        row = RiskRoutingDecision(
            risk_routing_decision_id=(
                risk_routing_decision_id or f"risk_route_{uuid4().hex}"
            ),
            subject_type=result.subject_type.value,
            subject_id=result.subject_id,
            trust_assessment_id=trust_assessment_id,
            trust_tier=result.trust_tier.value,
            risk_level=result.risk_level.value,
            routing_outcome=result.routing_outcome.value,
            routing_reasons_json=[code.value for code in result.routing_reasons],
            ranking_influence_decision=result.ranking_influence_decision.value,
            ranking_influence_allowed=result.ranking_influence_allowed,
            ranking_influence_reason=result.ranking_influence_reason,
            ranking_influence_reason_codes_json=[
                code.value for code in result.ranking_influence_reason_codes
            ],
            evidence_requirements_met_json=_requirements_json(
                result.evidence_requirements_met
            ),
            evidence_requirements_missing_json=_requirements_json(
                result.evidence_requirements_missing
            ),
            evidence_requirements_failed_json=_requirements_json(
                result.evidence_requirements_failed
            ),
            warnings_json=_warnings_json(result.warnings),
            decision_source=result.decision_source,
            decision_version=result.decision_version,
            decided_at=result.decided_at,
            expires_at=result.expires_at,
        )
        self._session.add(row)
        return row

    def upsert_routing_decision(
        self,
        result: RiskRoutingDecisionResult,
        *,
        risk_routing_decision_id: str,
        trust_assessment_id: str | None = None,
    ) -> tuple[RiskRoutingDecision, TrustUpsertOutcome]:
        payload = _routing_payload(
            result,
            trust_assessment_id=trust_assessment_id,
        )
        row = self._session.get(RiskRoutingDecision, risk_routing_decision_id)
        if row is None:
            row = RiskRoutingDecision(
                risk_routing_decision_id=risk_routing_decision_id,
                **payload,
            )
            self._session.add(row)
            return row, "created"
        if _row_matches(row, payload):
            return row, "unchanged"
        _apply_payload(row, payload)
        return row, "updated"

    def latest_routing_for_subject(
        self,
        *,
        subject_type: TrustAssessmentSubjectType | str,
        subject_id: str,
    ) -> RiskRoutingDecisionResult | None:
        subject_value = (
            subject_type.value
            if isinstance(subject_type, TrustAssessmentSubjectType)
            else subject_type
        )
        row = self._session.execute(
            select(RiskRoutingDecision)
            .where(
                RiskRoutingDecision.subject_type == subject_value,
                RiskRoutingDecision.subject_id == subject_id,
            )
            .order_by(
                RiskRoutingDecision.decided_at.desc(),
                RiskRoutingDecision.risk_routing_decision_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return routing_decision_from_row(row)


def assessment_from_row(row: TrustAssessment) -> TrustAssessmentResult:
    return TrustAssessmentResult(
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        trust_tier=TrustTier(row.trust_tier),
        assessment_source=row.assessment_source,
        assessment_version=row.assessment_version,
        evidence_requirements_met=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_met_json
        ),
        evidence_requirements_missing=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_missing_json
        ),
        evidence_requirements_failed=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_failed_json
        ),
        evidence_requirements_not_applicable=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_not_applicable_json
        ),
        warnings=tuple(TrustWarning.model_validate(item) for item in row.warnings_json),
        reasons=tuple(str(item) for item in row.reasons_json),
        ranking_influence_allowed=row.ranking_influence_allowed,
        assessed_at=_aware(row.assessed_at),
        expires_at=_aware(row.expires_at),
        next_assessment_at=_aware(row.next_assessment_at),
    )


def routing_decision_from_row(row: RiskRoutingDecision) -> RiskRoutingDecisionResult:
    return RiskRoutingDecisionResult(
        subject_type=TrustAssessmentSubjectType(row.subject_type),
        subject_id=row.subject_id,
        trust_tier=TrustTier(row.trust_tier),
        risk_level=RiskLevel(row.risk_level),
        routing_outcome=RoutingOutcome(row.routing_outcome),
        routing_reasons=tuple(
            RiskRoutingReasonCode(item) for item in row.routing_reasons_json
        ),
        ranking_influence_decision=RankingInfluenceDecision(
            row.ranking_influence_decision
        ),
        ranking_influence_allowed=row.ranking_influence_allowed,
        ranking_influence_reason=row.ranking_influence_reason,
        ranking_influence_reason_codes=tuple(
            RankingInfluenceReasonCode(item)
            for item in row.ranking_influence_reason_codes_json
        ),
        evidence_requirements_met=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_met_json
        ),
        evidence_requirements_missing=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_missing_json
        ),
        evidence_requirements_failed=tuple(
            EvidenceRequirementResult.model_validate(item)
            for item in row.evidence_requirements_failed_json
        ),
        warnings=tuple(TrustWarning.model_validate(item) for item in row.warnings_json),
        decision_source=row.decision_source,
        decision_version=row.decision_version,
        decided_at=_aware(row.decided_at),
        expires_at=_aware(row.expires_at),
    )


def _requirements_json(items: tuple[EvidenceRequirementResult, ...]) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


def _warnings_json(items: tuple[TrustWarning, ...]) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


def _assessment_payload(result: TrustAssessmentResult) -> dict[str, Any]:
    return {
        "subject_type": result.subject_type.value,
        "subject_id": result.subject_id,
        "trust_tier": result.trust_tier.value,
        "assessment_source": result.assessment_source,
        "assessment_version": result.assessment_version,
        "evidence_requirements_met_json": _requirements_json(
            result.evidence_requirements_met
        ),
        "evidence_requirements_missing_json": _requirements_json(
            result.evidence_requirements_missing
        ),
        "evidence_requirements_failed_json": _requirements_json(
            result.evidence_requirements_failed
        ),
        "evidence_requirements_not_applicable_json": _requirements_json(
            result.evidence_requirements_not_applicable
        ),
        "warnings_json": _warnings_json(result.warnings),
        "reasons_json": list(result.reasons),
        "ranking_influence_allowed": result.ranking_influence_allowed,
        "assessed_at": result.assessed_at,
        "expires_at": result.expires_at,
        "next_assessment_at": result.next_assessment_at,
    }


def _routing_payload(
    result: RiskRoutingDecisionResult,
    *,
    trust_assessment_id: str | None,
) -> dict[str, Any]:
    return {
        "subject_type": result.subject_type.value,
        "subject_id": result.subject_id,
        "trust_assessment_id": trust_assessment_id,
        "trust_tier": result.trust_tier.value,
        "risk_level": result.risk_level.value,
        "routing_outcome": result.routing_outcome.value,
        "routing_reasons_json": [code.value for code in result.routing_reasons],
        "ranking_influence_decision": result.ranking_influence_decision.value,
        "ranking_influence_allowed": result.ranking_influence_allowed,
        "ranking_influence_reason": result.ranking_influence_reason,
        "ranking_influence_reason_codes_json": [
            code.value for code in result.ranking_influence_reason_codes
        ],
        "evidence_requirements_met_json": _requirements_json(
            result.evidence_requirements_met
        ),
        "evidence_requirements_missing_json": _requirements_json(
            result.evidence_requirements_missing
        ),
        "evidence_requirements_failed_json": _requirements_json(
            result.evidence_requirements_failed
        ),
        "warnings_json": _warnings_json(result.warnings),
        "decision_source": result.decision_source,
        "decision_version": result.decision_version,
        "decided_at": result.decided_at,
        "expires_at": result.expires_at,
    }


def _row_matches(
    row: TrustAssessment | RiskRoutingDecision,
    payload: dict[str, Any],
) -> bool:
    return all(_values_equal(getattr(row, key), value) for key, value in payload.items())


def _apply_payload(
    row: TrustAssessment | RiskRoutingDecision,
    payload: dict[str, Any],
) -> None:
    for key, value in payload.items():
        setattr(row, key, value)


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        return _aware(left) == _aware(right)
    return left == right


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
