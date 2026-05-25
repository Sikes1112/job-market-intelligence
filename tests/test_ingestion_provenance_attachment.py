from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.ingestion.contracts import (
    IntakeProvenanceDefinition,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import CanonicalFactIntent, NormalizationStatus
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import ProvenanceService
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceAcceptability,
    SourceType,
)
from seeds import mvp_seed

_NOW = datetime(2026, 5, 21, 12, tzinfo=UTC)


def _ingestion_service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _provenance_service(session: Session) -> ProvenanceService:
    return ProvenanceService(ProvenanceRepository(session))


def _raw_definition(
    *,
    raw_record_id: str = "raw_manual_1",
    intent: CanonicalFactIntent = CanonicalFactIntent.PRESENCE,
    payload: dict | None = None,
) -> RawIntakeDefinition:
    return RawIntakeDefinition(
        raw_record_id=raw_record_id,
        provider_id="manual_research",
        source_type=SourceType.MANUAL_RESEARCH,
        source_name="Operator supplied observation",
        url_or_provider="manual://operator",
        external_entity_id=raw_record_id,
        raw_payload=RawObservationPayload(
            body=payload
            or {
                "company_id": "comp_example",
                "region_id": "greater_boston",
                "presence_status": "present",
            }
        ),
        collected_at=_NOW,
        observed_at=_NOW,
        intended_fact_type=intent,
        parsing_notes="manual intake note",
    )


def _store_raw(session: Session, **kwargs) -> RawIngestionRecord:
    return _ingestion_service(session).create_raw_record(_raw_definition(**kwargs))


def _normalize(
    session: Session,
    *,
    raw_record_id: str = "raw_manual_1",
) -> None:
    _ingestion_service(session).normalize_raw_record(
        raw_record_id,
        normalizer=ManualObservationNormalizer(),
    )


def _attachment_definition(
    *,
    raw_record_id: str = "raw_manual_1",
    source_type: SourceType = SourceType.COMPANY_OFFICIAL,
    source_id: str = "source_company_official",
    observation_id: str = "observation_company_official",
) -> IntakeProvenanceDefinition:
    return IntakeProvenanceDefinition(
        raw_record_id=raw_record_id,
        source_id=source_id,
        observation_id=observation_id,
        source_type=source_type,
        source_name="Example Careers",
        url_or_provider="https://example.test/careers",
        collected_at=_NOW,
        observed_at=_NOW,
        license_or_terms_category=LicenseTermsCategory.PUBLIC,
        confidence=Confidence.HIGH,
        data_origin=DataOrigin.REAL_OBSERVED,
        notes="operator reviewed source metadata",
    )


def test_cannot_attach_provenance_before_normalization(session: Session) -> None:
    _store_raw(session)

    with pytest.raises(ValueError, match="must be normalized"):
        _ingestion_service(session).attach_provenance_from_normalized_intake(
            _attachment_definition(),
            provenance_service=_provenance_service(session),
        )


def test_valid_normalized_manual_observation_can_attach_provenance(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)

    result = _ingestion_service(session).attach_provenance_from_normalized_intake(
        _attachment_definition(),
        provenance_service=_provenance_service(session),
    )

    assert result.source_ref_outcome == "created"
    assert result.observation_outcome == "created"
    assert result.manual_review_required is False

    record = session.get(RawIngestionRecord, "raw_manual_1")
    assert record is not None
    assert record.source_id == "source_company_official"
    assert record.observation_id == "observation_company_official"

    observation = session.get(SourceObservation, "observation_company_official")
    assert observation is not None
    assert observation.observation_status == ObservationStatus.POSITIVE_OBSERVED.value


def test_source_ref_and_observation_are_reused_idempotently(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)
    service = _ingestion_service(session)
    definition = _attachment_definition()

    first = service.attach_provenance_from_normalized_intake(
        definition,
        provenance_service=_provenance_service(session),
    )
    version_after_first = session.get(RawIngestionRecord, "raw_manual_1").version
    second = service.attach_provenance_from_normalized_intake(
        definition,
        provenance_service=_provenance_service(session),
    )
    version_after_second = session.get(RawIngestionRecord, "raw_manual_1").version

    assert first.source_ref_outcome == "created"
    assert first.observation_outcome == "created"
    assert second.source_ref_outcome == "unchanged"
    assert second.observation_outcome == "unchanged"
    assert version_after_second == version_after_first
    assert session.query(SourceRef).count() == 1
    assert session.query(SourceObservation).count() == 1


def test_llm_generated_source_is_rejected_as_factual_provenance(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)

    with pytest.raises(ValueError, match="disallowed"):
        _ingestion_service(session).attach_provenance_from_normalized_intake(
            _attachment_definition(source_type=SourceType.LLM_GENERATED),
            provenance_service=_provenance_service(session),
        )

    assert session.query(SourceRef).count() == 0
    assert session.query(SourceObservation).count() == 0


def test_disallowed_source_types_cannot_attach_as_trusted_provenance(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)

    with pytest.raises(ValueError, match="disallowed"):
        _ingestion_service(session).attach_provenance_from_normalized_intake(
            _attachment_definition(source_type=SourceType.UNKNOWN_SOURCE),
            provenance_service=_provenance_service(session),
        )

    assert session.query(SourceRef).count() == 0


def test_manual_review_required_input_remains_marked_and_reported(
    session: Session,
) -> None:
    _store_raw(
        session,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
            "requires_manual_review": True,
        },
    )
    _normalize(session)

    result = _ingestion_service(session).attach_provenance_from_normalized_intake(
        _attachment_definition(
            source_type=SourceType.MANUAL_RESEARCH,
            source_id="source_manual_research",
            observation_id="observation_manual_research",
        ),
        provenance_service=_provenance_service(session),
    )

    assert result.source_acceptability is SourceAcceptability.MANUAL_REVIEW_REQUIRED
    assert result.manual_review_required is True
    assert "manual_review_required" in result.warnings[0]
    source_ref = session.get(SourceRef, "source_manual_research")
    assert source_ref is not None
    assert "manual_review_required" in (source_ref.notes or "")
    assert (
        session.get(RawIngestionRecord, "raw_manual_1").normalization_status
        == NormalizationStatus.REQUIRES_MANUAL_REVIEW.value
    )


def test_normalized_without_provenance_cannot_produce_canonical_proposal(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)

    with pytest.raises(ValueError, match="provenance attachment"):
        _ingestion_service(session).propose_canonical_fact(
            raw_record_id="raw_manual_1",
            fact_id="presence:comp_example:greater_boston",
        )


def test_normalized_with_explicit_provenance_can_produce_proposal_object(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)
    service = _ingestion_service(session)
    service.attach_provenance_from_normalized_intake(
        _attachment_definition(),
        provenance_service=_provenance_service(session),
    )

    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    assert proposal.fact_type is FactBindingType.COMPANY_REGION_PRESENCE
    assert proposal.source_id == "source_company_official"
    assert proposal.observation_id == "observation_company_official"


def test_canonical_proposal_does_not_write_canonical_facts(session: Session) -> None:
    _store_raw(session)
    _normalize(session)
    service = _ingestion_service(session)
    service.attach_provenance_from_normalized_intake(
        _attachment_definition(),
        provenance_service=_provenance_service(session),
    )
    service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    assert session.query(FactSourceLink).count() == 0
    assert session.query(Company).count() == 0


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
