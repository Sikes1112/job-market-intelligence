from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.ingestion.adapters.base import (
    AdapterDiagnosticCode,
    AdapterResultStatus,
)
from backend.ingestion.adapters.manual import ManualResearchAdapter
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import CanonicalFactIntent
from backend.provenance.models import FactSourceLink, SourceRef
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    SourceAcceptability,
    SourceType,
)
from seeds import mvp_seed

_NOW = datetime(2026, 5, 20, 12, tzinfo=UTC)


def _manual_input(**overrides):
    payload = {
        "raw_record_id": "manual_raw_1",
        "provider_id": "ops_research",
        "source_name": "Operator-reviewed company careers page",
        "url_or_provider": "https://example.test/careers",
        "source_type": SourceType.MANUAL_RESEARCH,
        "observed_at": _NOW,
        "collected_at": _NOW,
        "intended_fact_type": CanonicalFactIntent.HIRING,
        "external_entity_id": "example-careers",
        "raw_payload": {
            "company_name": "Example",
            "region_id": "greater_boston",
            "active_posting_count_now": 3,
        },
        "notes": "operator supplied observation",
        "confidence": Confidence.MEDIUM,
        "license_or_terms_category": LicenseTermsCategory.PUBLIC,
    }
    payload.update(overrides)
    return payload


def test_base_adapter_contract_exposes_metadata() -> None:
    adapter = ManualResearchAdapter()

    assert adapter.adapter_name == "manual_research"
    assert adapter.source_type is SourceType.MANUAL_RESEARCH
    assert CanonicalFactIntent.HIRING in adapter.supported_fact_intents


def test_manual_adapter_accepts_valid_operator_supplied_observation() -> None:
    result = ManualResearchAdapter().prepare(_manual_input())

    assert result.status is AdapterResultStatus.SUCCESS
    assert result.usable_as_raw_intake is True
    assert result.source_metadata is not None
    assert result.source_metadata.confidence is Confidence.MEDIUM
    assert (
        result.source_metadata.license_or_terms_category
        is LicenseTermsCategory.PUBLIC
    )
    [definition] = result.raw_intake_definitions
    assert definition.source_type is SourceType.MANUAL_RESEARCH
    assert definition.intended_fact_type is CanonicalFactIntent.HIRING
    assert definition.raw_payload.body["active_posting_count_now"] == 3


def test_manual_adapter_rejects_llm_generated_factual_evidence() -> None:
    result = ManualResearchAdapter().prepare(
        _manual_input(source_type=SourceType.LLM_GENERATED)
    )

    assert result.status is AdapterResultStatus.FAILED
    assert result.raw_intake_definitions == ()
    assert any(
        diagnostic.code is AdapterDiagnosticCode.SOURCE_DISALLOWED
        for diagnostic in result.diagnostics
    )


def test_manual_adapter_flags_manual_review_required() -> None:
    result = ManualResearchAdapter().prepare(_manual_input())

    assert result.source_metadata is not None
    assert (
        result.source_metadata.default_acceptability
        is SourceAcceptability.MANUAL_REVIEW_REQUIRED
    )
    assert any(
        diagnostic.code is AdapterDiagnosticCode.MANUAL_REVIEW_REQUIRED
        for diagnostic in result.diagnostics
    )


def test_adapter_output_can_be_stored_as_raw_ingestion_record(
    session: Session,
) -> None:
    result = ManualResearchAdapter().prepare(_manual_input())
    service = IngestionService(IngestionRepository(session))

    [record] = service.create_raw_records_from_adapter_result(result)

    fetched = session.get(RawIngestionRecord, record.raw_record_id)
    assert fetched is not None
    assert fetched.source_type == SourceType.MANUAL_RESEARCH.value
    assert fetched.raw_payload["company_name"] == "Example"


def test_stored_adapter_intake_does_not_create_canonical_facts(
    session: Session,
) -> None:
    result = ManualResearchAdapter().prepare(_manual_input())
    IngestionService(IngestionRepository(session)).create_raw_records_from_adapter_result(
        result
    )

    assert session.query(RawIngestionRecord).count() == 1
    assert session.query(FactSourceLink).count() == 0
    with pytest.raises(ValueError, match="must be normalized"):
        IngestionService(IngestionRepository(session)).propose_canonical_fact(
            raw_record_id="manual_raw_1",
            fact_id="hiring_1",
        )


def test_malformed_manual_input_produces_diagnostics() -> None:
    payload = _manual_input()
    del payload["source_name"]

    result = ManualResearchAdapter().prepare(payload)

    assert result.status is AdapterResultStatus.FAILED
    assert result.raw_intake_definitions == ()
    assert any(
        diagnostic.code is AdapterDiagnosticCode.INPUT_MALFORMED
        for diagnostic in result.diagnostics
    )


def test_supported_fact_intents_cover_required_categories() -> None:
    assert ManualResearchAdapter().supported_fact_intents == {
        CanonicalFactIntent.COMPANY,
        CanonicalFactIntent.REGION,
        CanonicalFactIntent.PRESENCE,
        CanonicalFactIntent.HIRING,
        CanonicalFactIntent.INTERNSHIPS_COOPS,
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        CanonicalFactIntent.SCORE_INPUT,
    }


def test_manual_adapter_intents_map_to_layer3_fact_bindings() -> None:
    result = ManualResearchAdapter().prepare(
        _manual_input(intended_fact_type=CanonicalFactIntent.PRESENCE)
    )

    [definition] = result.raw_intake_definitions
    assert definition.intended_fact_type is CanonicalFactIntent.PRESENCE
    assert FactBindingType.COMPANY_REGION_PRESENCE.value == "company_region_presence"


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
