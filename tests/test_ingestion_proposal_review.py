from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.contracts import (
    CanonicalFactProposal,
    IntakeProvenanceDefinition,
    ProposalReviewDecision,
    ProvenanceAttachment,
    RawIntakeDefinition,
    RawObservationPayload,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.service import IngestionService
from backend.ingestion.status import CanonicalFactIntent, ProposalReviewStatus
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.scoring.models import RegionMarketScore
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


def _ingestion_service(session: Session) -> IngestionService:
    return IngestionService(IngestionRepository(session))


def _provenance_service(session: Session) -> ProvenanceService:
    return ProvenanceService(ProvenanceRepository(session))


def _raw_definition(
    *,
    raw_record_id: str = "raw_manual_1",
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
        intended_fact_type=CanonicalFactIntent.PRESENCE,
        parsing_notes="manual intake note",
    )


def _store_raw(session: Session, **kwargs) -> RawIngestionRecord:
    return _ingestion_service(session).create_raw_record(_raw_definition(**kwargs))


def _normalize(session: Session, raw_record_id: str = "raw_manual_1") -> None:
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


def _attach(session: Session, **kwargs) -> None:
    _ingestion_service(session).attach_provenance_from_normalized_intake(
        _attachment_definition(**kwargs),
        provenance_service=_provenance_service(session),
    )


def _approval(note: str = "operator approved source link") -> ProposalReviewDecision:
    return ProposalReviewDecision(
        status=ProposalReviewStatus.APPROVED_FOR_LINKING,
        reviewer_note=note,
    )


def _proposal_from_record(
    session: Session,
    *,
    raw_record_id: str = "raw_manual_1",
    fact_id: str = "presence:comp_example:greater_boston",
) -> CanonicalFactProposal:
    record = session.get(RawIngestionRecord, raw_record_id)
    assert record is not None
    assert record.normalized_payload is not None
    assert record.intended_fact_type is not None
    assert record.source_id is not None
    assert record.observation_id is not None
    return CanonicalFactProposal.from_intake(
        raw_record_id=record.raw_record_id,
        intent=CanonicalFactIntent(record.intended_fact_type),
        fact_id=fact_id,
        normalized_payload=record.normalized_payload,
        source_id=record.source_id,
        observation_id=record.observation_id,
    )


def _manual_proposal(
    *,
    raw_record_id: str = "raw_manual_1",
    source_id: str = "source_missing",
    observation_id: str = "observation_missing",
) -> CanonicalFactProposal:
    return CanonicalFactProposal.from_intake(
        raw_record_id=raw_record_id,
        intent=CanonicalFactIntent.PRESENCE,
        fact_id="presence:comp_example:greater_boston",
        normalized_payload={
            "company_id": "comp_example",
            "region_id": "greater_boston",
            "presence_status": "present",
        },
        source_id=source_id,
        observation_id=observation_id,
    )


def test_cannot_approve_link_proposal_without_normalization(
    session: Session,
) -> None:
    _store_raw(session)

    with pytest.raises(ValueError, match="must be normalized"):
        _ingestion_service(session).review_and_link_canonical_fact_proposal(
            _manual_proposal(),
            _approval(),
            provenance_service=_provenance_service(session),
        )


def test_cannot_approve_link_proposal_without_provenance_attachment(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)

    with pytest.raises(ValueError, match="provenance attachment"):
        _ingestion_service(session).review_and_link_canonical_fact_proposal(
            _manual_proposal(),
            _approval(),
            provenance_service=_provenance_service(session),
        )


def test_valid_attached_proposal_creates_fact_source_link(session: Session) -> None:
    _store_raw(session)
    _normalize(session)
    _attach(session)
    service = _ingestion_service(session)
    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    result = service.review_and_link_canonical_fact_proposal(
        proposal,
        _approval(),
        provenance_service=_provenance_service(session),
    )

    assert result.approval_status is ProposalReviewStatus.LINKED_TO_SOURCE
    assert result.fact_source_link_id is not None
    assert result.fact_source_link_outcome == "created"
    assert result.canonical_domain_mutated is False
    link = session.get(FactSourceLink, result.fact_source_link_id)
    assert link is not None
    assert link.fact_type == FactBindingType.COMPANY_REGION_PRESENCE.value
    assert link.observation_id == "observation_company_official"


def test_repeated_approval_is_idempotent(session: Session) -> None:
    _store_raw(session)
    _normalize(session)
    _attach(session)
    service = _ingestion_service(session)
    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )
    decision = _approval()

    first = service.review_and_link_canonical_fact_proposal(
        proposal,
        decision,
        provenance_service=_provenance_service(session),
    )
    version_after_first = session.get(FactSourceLink, first.fact_source_link_id).version
    second = service.review_and_link_canonical_fact_proposal(
        proposal,
        decision,
        provenance_service=_provenance_service(session),
    )
    version_after_second = session.get(FactSourceLink, second.fact_source_link_id).version

    assert first.fact_source_link_outcome == "created"
    assert second.fact_source_link_outcome == "unchanged"
    assert first.fact_source_link_id == second.fact_source_link_id
    assert version_after_second == version_after_first
    assert session.query(FactSourceLink).count() == 1


def test_rejected_proposal_creates_no_fact_source_link(session: Session) -> None:
    _store_raw(session)
    _normalize(session)
    _attach(session)
    proposal = _ingestion_service(session).propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    result = _ingestion_service(session).review_and_link_canonical_fact_proposal(
        proposal,
        ProposalReviewDecision(
            status=ProposalReviewStatus.REJECTED,
            reviewer_note="source did not support proposed fact",
        ),
        provenance_service=_provenance_service(session),
    )

    assert result.approval_status is ProposalReviewStatus.REJECTED
    assert result.fact_source_link_id is None
    assert session.query(FactSourceLink).count() == 0


def test_manual_review_required_proposal_does_not_silently_approve(
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
    _attach(
        session,
        source_type=SourceType.MANUAL_RESEARCH,
        source_id="source_manual_review",
        observation_id="observation_manual_review",
    )
    proposal = _proposal_from_record(session)

    result = _ingestion_service(session).review_and_link_canonical_fact_proposal(
        proposal,
        _approval(),
        provenance_service=_provenance_service(session),
    )

    assert result.approval_status is ProposalReviewStatus.REQUIRES_MANUAL_REVIEW
    assert "manual_review_required_before_linking" in result.diagnostics
    assert session.query(FactSourceLink).count() == 0


def test_manual_review_override_with_note_can_link_source(session: Session) -> None:
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
    _attach(
        session,
        source_type=SourceType.MANUAL_RESEARCH,
        source_id="source_manual_review",
        observation_id="observation_manual_review",
    )
    proposal = _proposal_from_record(session)

    result = _ingestion_service(session).review_and_link_canonical_fact_proposal(
        proposal,
        ProposalReviewDecision(
            status=ProposalReviewStatus.APPROVED_FOR_LINKING,
            reviewer_note="operator reviewed manual source evidence",
            override_manual_review=True,
        ),
        provenance_service=_provenance_service(session),
    )

    assert result.approval_status is ProposalReviewStatus.LINKED_TO_SOURCE
    assert "manual_review_override_recorded" in result.diagnostics
    link = session.get(FactSourceLink, result.fact_source_link_id)
    assert link is not None
    assert "manual_review_override_recorded" in (link.notes or "")


def test_disallowed_source_proposal_fails_without_link(session: Session) -> None:
    _store_raw(session)
    _normalize(session)
    provenance = _provenance_service(session)
    provenance.upsert_source_ref(
        SourceRefDefinition(
            source_id="source_llm",
            source_type=SourceType.LLM_GENERATED,
            source_name="LLM generated note",
            url_or_provider="llm://local-note",
            collected_at=_NOW,
            observed_at=_NOW,
            license_or_terms_category=LicenseTermsCategory.PROHIBITED,
            confidence=Confidence.LOW,
            data_origin=DataOrigin.REAL_OBSERVED,
            notes="not factual source evidence",
        )
    )
    provenance.upsert_observation(
        SourceObservationDefinition(
            observation_id="observation_llm",
            source_id="source_llm",
            collected_at=_NOW,
            observed_at=_NOW,
            data_origin=DataOrigin.REAL_OBSERVED,
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            confidence=Confidence.LOW,
            notes="not factual source evidence",
        )
    )
    service = _ingestion_service(session)
    service.attach_provenance(
        ProvenanceAttachment(
            raw_record_id="raw_manual_1",
            source_id="source_llm",
            observation_id="observation_llm",
        )
    )
    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    result = service.review_and_link_canonical_fact_proposal(
        proposal,
        _approval(),
        provenance_service=provenance,
    )

    assert result.approval_status is ProposalReviewStatus.FAILED
    assert "source_type_disallowed:llm_generated" in result.diagnostics
    assert session.query(FactSourceLink).count() == 0


def test_linking_does_not_mutate_canonical_domain_scoring_or_outputs(
    session: Session,
) -> None:
    _store_raw(session)
    _normalize(session)
    _attach(session)
    service = _ingestion_service(session)
    proposal = service.propose_canonical_fact(
        raw_record_id="raw_manual_1",
        fact_id="presence:comp_example:greater_boston",
    )

    service.review_and_link_canonical_fact_proposal(
        proposal,
        _approval(),
        provenance_service=_provenance_service(session),
    )

    assert session.query(Company).count() == 0
    assert session.query(Region).count() == 0
    assert session.query(CompanyRegionPresence).count() == 0
    assert session.query(CompanyRegionHiring).count() == 0
    assert session.query(CompanyRegionEntryLevel).count() == 0
    assert session.query(RegionMarketScore).count() == 0
    assert session.query(OutputMetadata).count() == 0


def test_demo_seed_behavior_remains_unaffected(session: Session) -> None:
    mvp_seed.run_seed(session)

    assert session.query(RawIngestionRecord).count() == 0
    source_ref = session.get(SourceRef, "mvp_demo_seed")
    assert source_ref is not None
    assert source_ref.data_origin == DataOrigin.DEMO_SEED.value
