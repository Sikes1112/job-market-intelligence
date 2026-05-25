from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.ingestion.contracts import (
    ProvenanceAttachment,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalization import (
    conflicting_result,
    normalized_result,
    rejected_result,
    validate_raw_payload,
)
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import (
    CanonicalFactIntent,
    IngestionStatus,
    NormalizationStatus,
    fact_binding_type_for_intent,
    provenance_fact_type_for_intent,
)
from backend.provenance.models import FactSourceLink, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    ProvenanceFactType,
    SourceType,
)
from seeds import mvp_seed

_NOW = datetime(2026, 5, 20, 12, tzinfo=UTC)


def _service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _raw_definition(
    raw_record_id: str = "raw_1",
    *,
    intended_fact_type: CanonicalFactIntent | None = CanonicalFactIntent.HIRING,
) -> RawIntakeDefinition:
    return RawIntakeDefinition(
        raw_record_id=raw_record_id,
        provider_id="provider_test",
        source_type=SourceType.ATS_JOB_BOARD,
        source_name="Example ATS",
        url_or_provider="https://ats.example.test/job/123",
        external_entity_id="job_123",
        raw_payload=RawObservationPayload(
            body={
                "company": "Example",
                "region": "greater_boston",
                "active_postings": 3,
            }
        ),
        collected_at=_NOW,
        observed_at=_NOW,
        intended_fact_type=intended_fact_type,
    )


def _seed_provenance(session: Session) -> None:
    provenance = ProvenanceService(ProvenanceRepository(session))
    provenance.upsert_source_ref(
        SourceRefDefinition(
            source_id="source_ats",
            source_type=SourceType.ATS_JOB_BOARD,
            source_name="Example ATS",
            url_or_provider="https://ats.example.test",
            collected_at=_NOW,
            observed_at=_NOW,
            license_or_terms_category=LicenseTermsCategory.PUBLIC,
            confidence=Confidence.HIGH,
            data_origin=DataOrigin.REAL_OBSERVED,
            notes="test source",
        )
    )
    provenance.upsert_observation(
        SourceObservationDefinition(
            observation_id="observation_ats",
            source_id="source_ats",
            collected_at=_NOW,
            observed_at=_NOW,
            data_origin=DataOrigin.REAL_OBSERVED,
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            confidence=Confidence.HIGH,
            notes="test observation",
        )
    )


def test_raw_ingestion_records_can_be_created(session: Session) -> None:
    record = _service(session).create_raw_record(_raw_definition())

    fetched = session.get(RawIngestionRecord, "raw_1")
    assert fetched is record
    assert fetched.provider_id == "provider_test"
    assert fetched.source_type == SourceType.ATS_JOB_BOARD.value
    assert fetched.raw_payload["active_postings"] == 3
    assert fetched.normalization_status == NormalizationStatus.RAW_UNREVIEWED.value
    assert len(fetched.payload_checksum) == 64


def test_normalization_states_are_distinct() -> None:
    assert NormalizationStatus.values() == {
        "raw_unreviewed",
        "parsed",
        "normalized",
        "rejected",
        "conflicting",
        "requires_manual_review",
    }
    assert NormalizationStatus.RAW_UNREVIEWED is not NormalizationStatus.NORMALIZED
    assert NormalizationStatus.CONFLICTING is not NormalizationStatus.REJECTED


def test_provenance_references_can_attach_to_intake_records(
    session: Session,
) -> None:
    service = _service(session)
    service.create_raw_record(_raw_definition())
    _seed_provenance(session)

    record = service.attach_provenance(
        ProvenanceAttachment(
            raw_record_id="raw_1",
            source_id="source_ats",
            observation_id="observation_ats",
        )
    )

    assert record.source_id == "source_ats"
    assert record.observation_id == "observation_ats"
    assert record.source_ref.source_type == SourceType.ATS_JOB_BOARD.value


def test_raw_intake_does_not_automatically_become_canonical_fact(
    session: Session,
) -> None:
    service = _service(session)
    service.create_raw_record(_raw_definition())

    assert session.query(FactSourceLink).count() == 0
    with pytest.raises(ValueError, match="must be normalized"):
        service.propose_canonical_fact(raw_record_id="raw_1", fact_id="hiring_1")


def test_conflicting_intake_can_be_marked_safely(session: Session) -> None:
    service = _service(session)
    service.create_raw_record(_raw_definition())

    record = service.record_normalization_result(
        conflicting_result(
            raw_record_id="raw_1",
            parsing_notes="two source fields disagree",
            parsing_errors=("active_postings_conflict",),
        )
    )

    assert record.normalization_status == NormalizationStatus.CONFLICTING.value
    assert record.parsing_errors == ["active_postings_conflict"]
    with pytest.raises(ValueError, match="must be normalized"):
        service.propose_canonical_fact(raw_record_id="raw_1", fact_id="hiring_1")


def test_malformed_payloads_can_be_rejected(session: Session) -> None:
    with pytest.raises(ValueError, match="JSON object"):
        validate_raw_payload(["not", "an", "object"])

    service = _service(session)
    service.create_raw_record(_raw_definition())
    record = service.record_normalization_result(
        rejected_result(raw_record_id="raw_1", error="missing required company field")
    )

    assert record.normalization_status == NormalizationStatus.REJECTED.value
    assert record.ingestion_status == IngestionStatus.REJECTED.value
    assert record.parsing_errors == ["missing required company field"]


def test_canonical_fact_intent_categories_exist() -> None:
    assert CanonicalFactIntent.values() == {
        "company",
        "region",
        "presence",
        "hiring",
        "internships_coops",
        "early_career_programs",
        "score_input",
    }
    assert (
        fact_binding_type_for_intent(CanonicalFactIntent.INTERNSHIPS_COOPS)
        is FactBindingType.COMPANY_REGION_ENTRY_LEVEL
    )
    assert (
        provenance_fact_type_for_intent(CanonicalFactIntent.EARLY_CAREER_PROGRAMS)
        is ProvenanceFactType.EARLY_CAREER_PROGRAMS
    )


def test_layer3_provenance_vocabulary_integrates_with_fact_proposals(
    session: Session,
) -> None:
    service = _service(session)
    service.create_raw_record(
        _raw_definition(intended_fact_type=CanonicalFactIntent.PRESENCE)
    )
    _seed_provenance(session)
    service.attach_provenance(
        ProvenanceAttachment(
            raw_record_id="raw_1",
            source_id="source_ats",
            observation_id="observation_ats",
        )
    )
    service.record_normalization_result(
        normalized_result(
            raw_record_id="raw_1",
            intended_fact_type=CanonicalFactIntent.PRESENCE,
            normalized_payload={
                "company_id": "comp_example",
                "region_id": "greater_boston",
                "presence_status": "present",
            },
        )
    )

    proposal = service.propose_canonical_fact(
        raw_record_id="raw_1",
        fact_id="presence_comp_example_boston",
    )

    assert proposal.fact_type is FactBindingType.COMPANY_REGION_PRESENCE
    assert proposal.provenance_fact_type is ProvenanceFactType.COMPANY_PRESENCE
    assert proposal.source_id == "source_ats"
    assert proposal.observation_id == "observation_ats"


def test_demo_seed_path_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
    assert {link.data_origin for link in session.query(FactSourceLink).all()} == {
        DataOrigin.DEMO_SEED.value
    }
