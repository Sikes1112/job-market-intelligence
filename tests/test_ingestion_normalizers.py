from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.ingestion.contracts import (
    ProvenanceAttachment,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.base import (
    NormalizerDiagnosticCode,
)
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import CanonicalFactIntent, NormalizationStatus
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
    SourceType,
)
from seeds import mvp_seed

_NOW = datetime(2026, 5, 21, 12, tzinfo=UTC)


def _service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _raw_definition(
    *,
    raw_record_id: str = "raw_manual_1",
    intent: CanonicalFactIntent,
    payload: dict,
) -> RawIntakeDefinition:
    return RawIntakeDefinition(
        raw_record_id=raw_record_id,
        provider_id="manual_research",
        source_type=SourceType.MANUAL_RESEARCH,
        source_name="Operator supplied observation",
        url_or_provider="manual://operator",
        external_entity_id=raw_record_id,
        raw_payload=RawObservationPayload(body=payload),
        collected_at=_NOW,
        observed_at=_NOW,
        intended_fact_type=intent,
        parsing_notes="manual test observation",
    )


def _store_raw(
    session: Session,
    *,
    intent: CanonicalFactIntent,
    payload: dict,
    raw_record_id: str = "raw_manual_1",
) -> RawIngestionRecord:
    return _service(session).create_raw_record(
        _raw_definition(
            raw_record_id=raw_record_id,
            intent=intent,
            payload=payload,
        )
    )


def _seed_provenance(session: Session) -> None:
    provenance = ProvenanceService(ProvenanceRepository(session))
    provenance.upsert_source_ref(
        SourceRefDefinition(
            source_id="source_manual",
            source_type=SourceType.MANUAL_RESEARCH,
            source_name="Reviewed manual source",
            url_or_provider="manual://operator",
            collected_at=_NOW,
            observed_at=_NOW,
            license_or_terms_category=LicenseTermsCategory.PUBLIC,
            confidence=Confidence.MEDIUM,
            data_origin=DataOrigin.MANUAL_REVIEWED,
            notes="reviewed source for normalizer test",
        )
    )
    provenance.upsert_observation(
        SourceObservationDefinition(
            observation_id="observation_manual",
            source_id="source_manual",
            collected_at=_NOW,
            observed_at=_NOW,
            data_origin=DataOrigin.MANUAL_REVIEWED,
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            confidence=Confidence.MEDIUM,
            notes="reviewed observation for normalizer test",
        )
    )


def test_normalizer_metadata_contract_exists() -> None:
    normalizer = ManualObservationNormalizer()

    assert normalizer.normalizer_name == "manual_observation"
    assert normalizer.supported_fact_intents == {
        CanonicalFactIntent.COMPANY,
        CanonicalFactIntent.REGION,
        CanonicalFactIntent.PRESENCE,
        CanonicalFactIntent.HIRING,
        CanonicalFactIntent.INTERNSHIPS_COOPS,
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        CanonicalFactIntent.SCORE_INPUT,
    }


def test_manual_company_observation_normalizes_required_fields(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example", "company_name": "Example"},
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.NORMALIZED
    assert result.observation is not None
    assert result.observation.normalized_fields["company_name"] == "Example"
    assert result.observation.proposed_fact_id == "comp_example"


def test_manual_region_observation_normalizes_required_fields(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.REGION,
        payload={"region_id": "greater_boston", "display_name": "Greater Boston"},
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.NORMALIZED
    assert result.observation is not None
    assert result.observation.normalized_fields["display_name"] == "Greater Boston"
    assert result.observation.proposed_fact_id == "greater_boston"


def test_manual_presence_observation_normalizes_required_fields(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.NORMALIZED
    assert result.observation is not None
    assert result.observation.normalized_fields["presence_status"] == "present"
    assert result.observation.proposed_fact_id == (
        "presence:comp_example:greater_boston"
    )


def test_manual_hiring_observation_preserves_unknown_vs_zero(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.HIRING,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "currently_hiring_flag": True,
            "active_posting_count_now": None,
            "hiring_program_count": 0,
        },
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.NORMALIZED
    assert result.observation is not None
    fields = result.observation.normalized_fields
    assert fields["active_posting_count_now"] is None
    assert fields["active_posting_count_now_status"] == ObservationStatus.UNKNOWN.value
    assert fields["posting_count_30d_status"] == ObservationStatus.NOT_COLLECTED.value
    assert fields["hiring_program_count"] is None
    assert fields["hiring_program_count_status"] == ObservationStatus.UNKNOWN.value
    assert any(
        item.code is NormalizerDiagnosticCode.ZERO_WITHOUT_OBSERVED_BASIS
        for item in result.diagnostics
    )


def test_internship_coop_and_early_career_preserve_uncertain_statuses(
    session: Session,
) -> None:
    internship_record = _store_raw(
        session,
        raw_record_id="raw_internship",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": None,
        },
    )
    early_record = _store_raw(
        session,
        raw_record_id="raw_early",
        intent=CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "entry_level_full_time_count": 4,
            "entry_level_full_time_count_freshness_status": "stale",
        },
    )

    internship = ManualObservationNormalizer().normalize(internship_record)
    early = ManualObservationNormalizer().normalize(early_record)

    assert internship.observation is not None
    assert internship.observation.normalized_fields["internship_count_status"] == (
        ObservationStatus.UNKNOWN.value
    )
    assert internship.observation.normalized_fields["coop_count_status"] == (
        ObservationStatus.NOT_COLLECTED.value
    )
    assert early.observation is not None
    assert early.observation.normalized_fields["entry_level_full_time_count"] is None
    assert early.observation.normalized_fields[
        "entry_level_full_time_count_status"
    ] == ObservationStatus.STALE.value


def test_explicit_observed_zero_becomes_zero_observed_only_with_basis(
    session: Session,
) -> None:
    without_basis = _store_raw(
        session,
        raw_record_id="raw_zero_without_basis",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
        },
    )
    with_basis = _store_raw(
        session,
        raw_record_id="raw_zero_with_basis",
        intent=CanonicalFactIntent.INTERNSHIPS_COOPS,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "internship_count": 0,
            "internship_count_observed_basis": True,
        },
    )

    unknown_zero = ManualObservationNormalizer().normalize(without_basis)
    observed_zero = ManualObservationNormalizer().normalize(with_basis)

    assert unknown_zero.observation is not None
    assert unknown_zero.observation.normalized_fields["internship_count"] is None
    assert unknown_zero.observation.normalized_fields["internship_count_status"] == (
        ObservationStatus.UNKNOWN.value
    )
    assert observed_zero.observation is not None
    assert observed_zero.observation.normalized_fields["internship_count"] == 0
    assert observed_zero.observation.normalized_fields["internship_count_status"] == (
        ObservationStatus.ZERO_OBSERVED.value
    )


def test_malformed_payload_produces_diagnostics_and_rejected_status(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.COMPANY,
        payload={"company_id": "comp_example"},
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.REJECTED
    assert result.has_errors is True
    assert any(
        item.code is NormalizerDiagnosticCode.MISSING_REQUIRED_FIELD
        for item in result.diagnostics
    )


def test_conflicting_payload_produces_conflicting_manual_review_status(
    session: Session,
) -> None:
    record = _store_raw(
        session,
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
            "conflicting": True,
        },
    )

    result = ManualObservationNormalizer().normalize(record)

    assert result.status is NormalizationStatus.CONFLICTING
    assert result.manual_review_required is True
    assert any(
        item.code is NormalizerDiagnosticCode.CONFLICTING_INPUT
        for item in result.diagnostics
    )


def test_normalizer_result_feeds_proposal_only_after_provenance_attachment(
    session: Session,
) -> None:
    _store_raw(
        session,
        intent=CanonicalFactIntent.PRESENCE,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
    )
    service = _service(session)
    result = service.normalize_raw_record(
        "raw_manual_1",
        normalizer=ManualObservationNormalizer(),
    )

    assert result.observation is not None
    with pytest.raises(ValueError, match="provenance attachment"):
        service.propose_canonical_fact(
            raw_record_id="raw_manual_1",
            fact_id=result.observation.proposed_fact_id or "presence_1",
        )

    _seed_provenance(session)
    service.attach_provenance(
        ProvenanceAttachment(
            raw_record_id="raw_manual_1",
            source_id="source_manual",
            observation_id="observation_manual",
        )
    )
    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id=result.observation.proposed_fact_id or "presence_1",
    )

    assert proposal.fact_type is FactBindingType.COMPANY_REGION_PRESENCE
    assert proposal.source_id == "source_manual"
    assert session.query(FactSourceLink).count() == 0


def test_normalization_does_not_create_canonical_facts_or_provenance_links(
    session: Session,
) -> None:
    _store_raw(
        session,
        intent=CanonicalFactIntent.HIRING,
        payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "currently_hiring_flag": False,
        },
    )

    _service(session).normalize_raw_record(
        "raw_manual_1",
        normalizer=ManualObservationNormalizer(),
    )

    assert session.query(RawIngestionRecord).count() == 1
    assert session.query(FactSourceLink).count() == 0
    assert session.query(SourceRef).count() == 0


def test_demo_seed_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
