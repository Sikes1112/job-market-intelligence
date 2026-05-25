"""Manual observation normalizers for Layer 4 raw intake."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.ingestion.contracts import RawIntakeDefinition
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.base import (
    NormalizedObservation,
    NormalizerDiagnostic,
    NormalizerDiagnosticCode,
    NormalizerDiagnosticSeverity,
    NormalizerResult,
)
from backend.ingestion.status import CanonicalFactIntent, NormalizationStatus
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import ObservationStatus
from backend.shared.value_semantics import CountSemantics, classify_count

_COUNT_FIELDS_BY_INTENT: dict[CanonicalFactIntent, tuple[str, ...]] = {
    CanonicalFactIntent.HIRING: (
        "active_posting_count_now",
        "posting_count_30d",
        "posting_count_90d",
        "hiring_program_count",
    ),
    CanonicalFactIntent.INTERNSHIPS_COOPS: (
        "internship_count",
        "coop_count",
    ),
    CanonicalFactIntent.EARLY_CAREER_PROGRAMS: (
        "entry_level_full_time_count",
    ),
}

_REQUIRED_FIELDS_BY_INTENT: dict[CanonicalFactIntent, tuple[str, ...]] = {
    CanonicalFactIntent.COMPANY: ("company_id", "company_name"),
    CanonicalFactIntent.REGION: ("region_id", "display_name"),
    CanonicalFactIntent.PRESENCE: ("company_id", "region_id", "presence_status"),
    CanonicalFactIntent.HIRING: ("company_id", "region_id", "currently_hiring_flag"),
    CanonicalFactIntent.INTERNSHIPS_COOPS: ("company_id", "region_id"),
    CanonicalFactIntent.EARLY_CAREER_PROGRAMS: ("company_id", "region_id"),
    CanonicalFactIntent.SCORE_INPUT: ("score_input_name", "source_fact_category"),
}


class ManualObservationNormalizer:
    normalizer_name = "manual_observation"
    supported_fact_intents = frozenset(CanonicalFactIntent)

    def normalize(self, raw_record: object | Mapping[str, Any]) -> NormalizerResult:
        try:
            raw = _coerce_raw_record(raw_record)
        except ValueError as exc:
            return _rejected_result(
                raw_record_id="unknown",
                normalizer_name=self.normalizer_name,
                message=str(exc),
            )

        if raw.intent is None:
            return _rejected_result(
                raw_record_id=raw.raw_record_id,
                normalizer_name=self.normalizer_name,
                message="raw record is missing intended_fact_type",
            )
        if raw.intent not in self.supported_fact_intents:
            return _rejected_result(
                raw_record_id=raw.raw_record_id,
                normalizer_name=self.normalizer_name,
                message=f"unsupported fact intent: {raw.intent.value}",
            )
        if not isinstance(raw.payload, dict):
            return _rejected_result(
                raw_record_id=raw.raw_record_id,
                normalizer_name=self.normalizer_name,
                message="raw payload must be a dictionary",
            )

        if _payload_is_conflicting(raw.payload):
            return NormalizerResult(
                normalizer_name=self.normalizer_name,
                raw_record_id=raw.raw_record_id,
                status=NormalizationStatus.CONFLICTING,
                diagnostics=(
                    NormalizerDiagnostic(
                        code=NormalizerDiagnosticCode.CONFLICTING_INPUT,
                        severity=NormalizerDiagnosticSeverity.ERROR,
                        message="manual payload contains conflicting input markers",
                    ),
                    NormalizerDiagnostic(
                        code=NormalizerDiagnosticCode.MANUAL_REVIEW_REQUIRED,
                        severity=NormalizerDiagnosticSeverity.WARNING,
                        message="conflicting manual payload requires review",
                    ),
                ),
                manual_review_required=True,
                notes=raw.notes,
            )

        missing = [
            field
            for field in _REQUIRED_FIELDS_BY_INTENT[raw.intent]
            if field not in raw.payload or raw.payload[field] in ("", None)
        ]
        if missing:
            return NormalizerResult(
                normalizer_name=self.normalizer_name,
                raw_record_id=raw.raw_record_id,
                status=NormalizationStatus.REJECTED,
                diagnostics=tuple(
                    NormalizerDiagnostic(
                        code=NormalizerDiagnosticCode.MISSING_REQUIRED_FIELD,
                        severity=NormalizerDiagnosticSeverity.ERROR,
                        field_name=field,
                        message=f"missing required field {field!r}",
                    )
                    for field in missing
                ),
                notes=raw.notes,
            )

        fields = {
            key: value
            for key, value in raw.payload.items()
            if not _is_semantics_control_key(key)
        }
        diagnostics: list[NormalizerDiagnostic] = []
        count_statuses: list[ObservationStatus] = []
        for field_name in _COUNT_FIELDS_BY_INTENT.get(raw.intent, ()):
            semantics, field_diagnostics = _normalize_count_field(
                raw.payload, field_name
            )
            fields[field_name] = semantics.value
            fields[f"{field_name}_status"] = semantics.status.value
            count_statuses.append(semantics.status)
            diagnostics.extend(field_diagnostics)

        manual_review_required = bool(raw.payload.get("requires_manual_review", False))
        if manual_review_required:
            diagnostics.append(
                NormalizerDiagnostic(
                    code=NormalizerDiagnosticCode.MANUAL_REVIEW_REQUIRED,
                    severity=NormalizerDiagnosticSeverity.WARNING,
                    message="manual payload requested review before trust",
                )
            )
        diagnostics.append(
            NormalizerDiagnostic(
                code=NormalizerDiagnosticCode.RAW_INTAKE_ONLY,
                severity=NormalizerDiagnosticSeverity.INFO,
                message="normalization produces proposal data only",
            )
        )

        observation_status = _observation_status_for(raw.intent, count_statuses)
        observation = NormalizedObservation(
            raw_record_id=raw.raw_record_id,
            intended_fact_type=raw.intent,
            normalized_fields=fields,
            observation_status=observation_status,
            confidence=raw.confidence,
            proposed_fact_id=_proposed_fact_id(raw.intent, fields),
            notes=raw.notes,
        )
        return NormalizerResult(
            normalizer_name=self.normalizer_name,
            raw_record_id=raw.raw_record_id,
            status=(
                NormalizationStatus.REQUIRES_MANUAL_REVIEW
                if manual_review_required
                else NormalizationStatus.NORMALIZED
            ),
            observation=observation,
            diagnostics=tuple(diagnostics),
            manual_review_required=manual_review_required,
            notes=raw.notes,
        )


class _RawRecordView:
    def __init__(
        self,
        *,
        raw_record_id: str,
        payload: dict[str, Any],
        intent: CanonicalFactIntent | None,
        notes: str | None,
        confidence: Confidence,
    ) -> None:
        self.raw_record_id = raw_record_id
        self.payload = payload
        self.intent = intent
        self.notes = notes
        self.confidence = confidence


def _coerce_raw_record(raw_record: object | Mapping[str, Any]) -> _RawRecordView:
    if isinstance(raw_record, RawIngestionRecord):
        return _RawRecordView(
            raw_record_id=raw_record.raw_record_id,
            payload=raw_record.raw_payload,
            intent=(
                CanonicalFactIntent(raw_record.intended_fact_type)
                if raw_record.intended_fact_type
                else None
            ),
            notes=raw_record.parsing_notes,
            confidence=_confidence_from_payload(raw_record.raw_payload),
        )
    if isinstance(raw_record, RawIntakeDefinition):
        return _RawRecordView(
            raw_record_id=raw_record.raw_record_id,
            payload=raw_record.raw_payload.body,
            intent=raw_record.intended_fact_type,
            notes=raw_record.parsing_notes,
            confidence=_confidence_from_payload(raw_record.raw_payload.body),
        )
    if isinstance(raw_record, Mapping):
        raw_record_id = raw_record.get("raw_record_id")
        payload = raw_record.get("raw_payload")
        raw_intent = raw_record.get("intended_fact_type")
        if not isinstance(raw_record_id, str) or not raw_record_id:
            raise ValueError("raw record mapping requires raw_record_id")
        if not isinstance(payload, dict):
            raise ValueError("raw record mapping requires raw_payload dictionary")
        intent = (
            raw_intent
            if isinstance(raw_intent, CanonicalFactIntent)
            else CanonicalFactIntent(raw_intent)
            if raw_intent is not None
            else None
        )
        return _RawRecordView(
            raw_record_id=raw_record_id,
            payload=payload,
            intent=intent,
            notes=raw_record.get("notes") if isinstance(raw_record.get("notes"), str) else None,
            confidence=_confidence_from_payload(payload),
        )
    raise ValueError("normalizer input must be a raw ingestion record or mapping")


def _confidence_from_payload(payload: Mapping[str, Any]) -> Confidence:
    value = payload.get("confidence")
    if value is None:
        return Confidence.UNKNOWN
    if isinstance(value, Confidence):
        return value
    return Confidence(value)


def _payload_is_conflicting(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("conflicting")
        or payload.get("conflict")
        or payload.get("conflict_notes")
    )


def _normalize_count_field(
    payload: Mapping[str, Any],
    field_name: str,
) -> tuple[CountSemantics, tuple[NormalizerDiagnostic, ...]]:
    diagnostics: list[NormalizerDiagnostic] = []
    if field_name not in payload:
        return (
            classify_count(None, collected=False),
            (
                NormalizerDiagnostic(
                    code=NormalizerDiagnosticCode.UNKNOWN_VALUE,
                    severity=NormalizerDiagnosticSeverity.WARNING,
                    field_name=field_name,
                    message=f"{field_name!r} was not collected",
                ),
            ),
        )

    value = payload[field_name]
    collected = bool(payload.get(f"{field_name}_collected", True))
    freshness_status = (
        FreshnessStatus.STALE
        if payload.get(f"{field_name}_stale")
        or payload.get(f"{field_name}_freshness_status") == FreshnessStatus.STALE.value
        else FreshnessStatus.FRESH
    )
    observed_basis = payload.get(f"{field_name}_observed_basis")
    if observed_basis is None:
        observed_basis = value is not None and value != 0
        if value == 0:
            diagnostics.append(
                NormalizerDiagnostic(
                    code=NormalizerDiagnosticCode.ZERO_WITHOUT_OBSERVED_BASIS,
                    severity=NormalizerDiagnosticSeverity.WARNING,
                    field_name=field_name,
                    message=(
                        f"{field_name!r} was zero without an explicit observed basis"
                    ),
                )
            )

    try:
        semantics = classify_count(
            value,
            observed_basis=bool(observed_basis),
            collected=collected,
            freshness_status=freshness_status,
        )
    except ValueError as exc:
        return (
            CountSemantics(value=None, status=ObservationStatus.UNKNOWN),
            (
                NormalizerDiagnostic(
                    code=NormalizerDiagnosticCode.MALFORMED_PAYLOAD,
                    severity=NormalizerDiagnosticSeverity.ERROR,
                    field_name=field_name,
                    message=str(exc),
                ),
            ),
        )
    if semantics.status in {
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.STALE,
    }:
        diagnostics.append(
            NormalizerDiagnostic(
                code=NormalizerDiagnosticCode.UNKNOWN_VALUE,
                severity=NormalizerDiagnosticSeverity.WARNING,
                field_name=field_name,
                message=(
                    f"{field_name!r} normalized as {semantics.status.value}, "
                    "not zero"
                ),
            )
        )
    return semantics, tuple(diagnostics)


def _observation_status_for(
    intent: CanonicalFactIntent,
    count_statuses: list[ObservationStatus],
) -> ObservationStatus:
    if not count_statuses:
        return ObservationStatus.POSITIVE_OBSERVED
    for status in (
        ObservationStatus.STALE,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.UNKNOWN,
    ):
        if status in count_statuses:
            return status
    if any(status is ObservationStatus.POSITIVE_OBSERVED for status in count_statuses):
        return ObservationStatus.POSITIVE_OBSERVED
    return ObservationStatus.ZERO_OBSERVED


def _proposed_fact_id(
    intent: CanonicalFactIntent,
    fields: Mapping[str, Any],
) -> str | None:
    if intent is CanonicalFactIntent.COMPANY:
        return _string_field(fields, "company_id")
    if intent is CanonicalFactIntent.REGION:
        return _string_field(fields, "region_id")
    if intent in {
        CanonicalFactIntent.PRESENCE,
        CanonicalFactIntent.HIRING,
        CanonicalFactIntent.INTERNSHIPS_COOPS,
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
    }:
        company_id = _string_field(fields, "company_id")
        region_id = _string_field(fields, "region_id")
        if company_id and region_id:
            return f"{intent.value}:{company_id}:{region_id}"
    if intent is CanonicalFactIntent.SCORE_INPUT:
        return _string_field(fields, "score_input_name")
    return None


def _string_field(fields: Mapping[str, Any], key: str) -> str | None:
    value = fields.get(key)
    return value if isinstance(value, str) and value else None


def _is_semantics_control_key(key: str) -> bool:
    return key.endswith(
        (
            "_observed_basis",
            "_collected",
            "_stale",
            "_freshness_status",
        )
    ) or key in {
        "conflict",
        "conflicting",
        "conflict_notes",
        "requires_manual_review",
    }


def _rejected_result(
    *,
    raw_record_id: str,
    normalizer_name: str,
    message: str,
) -> NormalizerResult:
    return NormalizerResult(
        normalizer_name=normalizer_name,
        raw_record_id=raw_record_id,
        status=NormalizationStatus.REJECTED,
        diagnostics=(
            NormalizerDiagnostic(
                code=NormalizerDiagnosticCode.MALFORMED_PAYLOAD,
                severity=NormalizerDiagnosticSeverity.ERROR,
                message=message,
            ),
        ),
    )
