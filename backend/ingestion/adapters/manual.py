"""Manual research adapter for operator-supplied raw observations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from backend.ingestion.adapters.base import (
    AdapterDiagnostic,
    AdapterDiagnosticCode,
    AdapterDiagnosticSeverity,
    AdapterResult,
    AdapterResultStatus,
    AdapterRunMetadata,
    AdapterSourceMetadata,
)
from backend.ingestion.contracts import RawIntakeDefinition, RawObservationPayload
from backend.ingestion.status import CanonicalFactIntent
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    SOURCE_TYPE_DEFAULT_ACCEPTABILITY,
    LicenseTermsCategory,
    SourceAcceptability,
    SourceType,
)


class ManualResearchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_record_id: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(default="manual_research", min_length=1, max_length=128)
    source_name: str = Field(min_length=1, max_length=255)
    url_or_provider: str = Field(min_length=1, max_length=1024)
    source_type: SourceType = SourceType.MANUAL_RESEARCH
    observed_at: datetime | None = None
    collected_at: datetime
    intended_fact_type: CanonicalFactIntent
    external_entity_id: str | None = Field(default=None, min_length=1, max_length=128)
    raw_payload: dict[str, Any]
    notes: str | None = Field(default=None, max_length=2048)
    confidence: Confidence = Confidence.UNKNOWN
    license_or_terms_category: LicenseTermsCategory = LicenseTermsCategory.UNKNOWN

    @field_validator("observed_at", "collected_at")
    @classmethod
    def _timestamps_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("manual research timestamps must be timezone-aware")
        return value


class ManualResearchAdapter:
    adapter_name = "manual_research"
    source_type = SourceType.MANUAL_RESEARCH
    supported_fact_intents = frozenset(CanonicalFactIntent)

    def prepare(
        self, observation: ManualResearchObservation | Mapping[str, Any] | object
    ) -> AdapterResult:
        try:
            parsed = _parse_observation(observation)
        except ValueError as exc:
            return _failed_result(
                message=str(exc),
                adapter_name=self.adapter_name,
            )

        source_metadata = AdapterSourceMetadata.from_source(
            source_type=parsed.source_type,
            source_name=parsed.source_name,
            url_or_provider=parsed.url_or_provider,
            license_or_terms_category=parsed.license_or_terms_category,
            confidence=parsed.confidence,
            notes=parsed.notes,
        )
        diagnostics = _source_policy_diagnostics(source_metadata)
        if any(
            diagnostic.severity is AdapterDiagnosticSeverity.ERROR
            for diagnostic in diagnostics
        ):
            return AdapterResult(
                status=AdapterResultStatus.FAILED,
                raw_intake_definitions=(),
                diagnostics=diagnostics,
                source_metadata=source_metadata,
                run_metadata=AdapterRunMetadata(
                    adapter_name=self.adapter_name,
                    collected_at=parsed.collected_at,
                    observation_count=0,
                ),
            )

        if not parsed.raw_payload:
            return AdapterResult(
                status=AdapterResultStatus.NO_OBSERVATIONS,
                raw_intake_definitions=(),
                diagnostics=(
                    *diagnostics,
                    AdapterDiagnostic(
                        code=AdapterDiagnosticCode.NO_OBSERVATIONS,
                        severity=AdapterDiagnosticSeverity.INFO,
                        message="manual observation contained no payload fields",
                    ),
                ),
                source_metadata=source_metadata,
                run_metadata=AdapterRunMetadata(
                    adapter_name=self.adapter_name,
                    collected_at=parsed.collected_at,
                    observation_count=0,
                ),
            )

        try:
            definition = RawIntakeDefinition(
                raw_record_id=parsed.raw_record_id,
                provider_id=parsed.provider_id,
                source_type=parsed.source_type,
                source_name=parsed.source_name,
                url_or_provider=parsed.url_or_provider,
                external_entity_id=parsed.external_entity_id,
                raw_payload=RawObservationPayload(body=parsed.raw_payload),
                collected_at=parsed.collected_at,
                observed_at=parsed.observed_at,
                intended_fact_type=parsed.intended_fact_type,
                parsing_notes=parsed.notes,
            )
        except (ValueError, ValidationError) as exc:
            return _failed_result(
                message=f"manual observation failed raw intake validation: {exc}",
                adapter_name=self.adapter_name,
                source_metadata=source_metadata,
            )
        return AdapterResult(
            status=AdapterResultStatus.SUCCESS,
            raw_intake_definitions=(definition,),
            diagnostics=(
                *diagnostics,
                AdapterDiagnostic(
                    code=AdapterDiagnosticCode.RAW_INTAKE_ONLY,
                    severity=AdapterDiagnosticSeverity.INFO,
                    message=(
                        "manual adapter output is raw intake only and does not "
                        "create trusted canonical facts"
                    ),
                ),
            ),
            source_metadata=source_metadata,
            run_metadata=AdapterRunMetadata(
                adapter_name=self.adapter_name,
                collected_at=parsed.collected_at,
                observation_count=1,
            ),
        )


def _parse_observation(
    observation: ManualResearchObservation | Mapping[str, Any] | object,
) -> ManualResearchObservation:
    if isinstance(observation, ManualResearchObservation):
        return observation
    if not isinstance(observation, Mapping):
        raise ValueError("manual observation input must be a mapping")
    try:
        return ManualResearchObservation.model_validate(dict(observation))
    except ValidationError as exc:
        raise ValueError(
            f"manual observation failed validation: {exc.error_count()} error(s)"
        ) from exc


def _source_policy_diagnostics(
    source_metadata: AdapterSourceMetadata,
) -> tuple[AdapterDiagnostic, ...]:
    acceptability = SOURCE_TYPE_DEFAULT_ACCEPTABILITY[source_metadata.source_type]
    if acceptability is SourceAcceptability.DISALLOWED:
        return (
            AdapterDiagnostic(
                code=AdapterDiagnosticCode.SOURCE_DISALLOWED,
                severity=AdapterDiagnosticSeverity.ERROR,
                message=(
                    f"source type {source_metadata.source_type.value!r} is "
                    "disallowed as factual market evidence"
                ),
            ),
        )
    if acceptability is SourceAcceptability.MANUAL_REVIEW_REQUIRED:
        return (
            AdapterDiagnostic(
                code=AdapterDiagnosticCode.MANUAL_REVIEW_REQUIRED,
                severity=AdapterDiagnosticSeverity.WARNING,
                message=(
                    f"source type {source_metadata.source_type.value!r} requires "
                    "manual review metadata before factual trust"
                ),
            ),
        )
    if acceptability is SourceAcceptability.ALLOWED_WITH_CAUTION:
        return (
            AdapterDiagnostic(
                code=AdapterDiagnosticCode.ALLOWED_WITH_CAUTION,
                severity=AdapterDiagnosticSeverity.WARNING,
                message=(
                    f"source type {source_metadata.source_type.value!r} is "
                    "allowed only with provenance caution"
                ),
            ),
        )
    return ()


def _failed_result(
    *,
    message: str,
    adapter_name: str,
    source_metadata: AdapterSourceMetadata | None = None,
) -> AdapterResult:
    return AdapterResult(
        status=AdapterResultStatus.FAILED,
        diagnostics=(
            AdapterDiagnostic(
                code=AdapterDiagnosticCode.INPUT_MALFORMED,
                severity=AdapterDiagnosticSeverity.ERROR,
                message=message,
            ),
        ),
        source_metadata=source_metadata,
        run_metadata=AdapterRunMetadata(adapter_name=adapter_name),
    )
