from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.provenance.exceptions import ProvenanceBindingRequired
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    FactSourceLinkDefinition,
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

_NOW = datetime(2026, 5, 20, 12, tzinfo=UTC)


def _service(session: Session) -> ProvenanceService:
    return ProvenanceService(ProvenanceRepository(session))


def _source_ref_definition(
    source_id: str = "source_company_official",
    *,
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
) -> SourceRefDefinition:
    return SourceRefDefinition(
        source_id=source_id,
        source_type=SourceType.COMPANY_OFFICIAL,
        source_name="Example Careers",
        url_or_provider="https://example.test/careers",
        collected_at=_NOW,
        observed_at=_NOW,
        license_or_terms_category=LicenseTermsCategory.PUBLIC,
        confidence=Confidence.HIGH,
        data_origin=data_origin,
        notes="Structured test source.",
    )


def _observation_definition(
    source_id: str = "source_company_official",
    observation_id: str = "observation_company_official",
    *,
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
) -> SourceObservationDefinition:
    return SourceObservationDefinition(
        observation_id=observation_id,
        source_id=source_id,
        collected_at=_NOW,
        observed_at=_NOW,
        data_origin=data_origin,
        observation_status=ObservationStatus.POSITIVE_OBSERVED,
        confidence=Confidence.HIGH,
        notes="Observed a test fact.",
    )


def _seed_observation(
    session: Session,
    *,
    source_id: str = "source_company_official",
    observation_id: str = "observation_company_official",
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
) -> tuple[ProvenanceService, SourceObservation]:
    service = _service(session)
    service.upsert_source_ref(
        _source_ref_definition(source_id=source_id, data_origin=data_origin)
    )
    observation, _ = service.upsert_observation(
        _observation_definition(
            source_id=source_id,
            observation_id=observation_id,
            data_origin=data_origin,
        )
    )
    return service, observation


def test_provenance_tables_can_be_created(session: Session) -> None:
    inspector = inspect(session.bind)
    assert {
        "source_refs",
        "source_observations",
        "fact_source_links",
    }.issubset(set(inspector.get_table_names()))


def test_source_ref_stores_required_fields(session: Session) -> None:
    service = _service(session)
    source_ref = service.create_source_ref(_source_ref_definition())

    fetched = session.get(SourceRef, source_ref.source_id)
    assert fetched is not None
    assert fetched.source_type == SourceType.COMPANY_OFFICIAL.value
    assert fetched.source_name == "Example Careers"
    assert fetched.url_or_provider == "https://example.test/careers"
    assert fetched.collected_at == _NOW
    assert fetched.observed_at == _NOW
    assert fetched.license_or_terms_category == LicenseTermsCategory.PUBLIC.value
    assert fetched.confidence == Confidence.HIGH.value
    assert fetched.notes == "Structured test source."


def test_source_observation_references_source_ref(session: Session) -> None:
    _, observation = _seed_observation(session)

    fetched = session.get(SourceObservation, observation.observation_id)
    assert fetched is not None
    assert fetched.source_id == "source_company_official"
    assert fetched.source_ref.source_id == "source_company_official"
    assert fetched.source_name == "Example Careers"
    assert fetched.collected_at == _NOW
    assert fetched.observed_at == _NOW


def test_fact_source_link_binds_required_fact_types(session: Session) -> None:
    service, observation = _seed_observation(session)
    fact_ids = {
        FactBindingType.COMPANY: "comp_example",
        FactBindingType.REGION: "region_example",
        FactBindingType.COMPANY_REGION_PRESENCE: "presence_example",
        FactBindingType.COMPANY_REGION_HIRING: "hiring_example",
        FactBindingType.COMPANY_REGION_ENTRY_LEVEL: "entry_level_example",
        FactBindingType.SCORE_INPUT: "score_input_example",
    }

    for fact_type, fact_id in fact_ids.items():
        link = service.create_fact_source_link(
            FactSourceLinkDefinition(
                link_id=f"link_{fact_type.value}",
                observation_id=observation.observation_id,
                fact_type=fact_type,
                fact_id=fact_id,
                fact_field="test_field",
                data_origin=DataOrigin.REAL_OBSERVED,
                observation_status=ObservationStatus.POSITIVE_OBSERVED,
                confidence=Confidence.HIGH,
                notes="Binding test fact to a source observation.",
            )
        )
        assert link.observation_id == observation.observation_id
        assert link.source_id == observation.source_id

    rows = session.query(FactSourceLink).all()
    assert {row.fact_type for row in rows} == {
        fact_type.value for fact_type in fact_ids
    }


def test_seed_demo_facts_can_be_labeled_separately_from_real_observed(
    session: Session,
) -> None:
    service = _service(session)
    service.upsert_source_ref(
        SourceRefDefinition(
            source_id="demo_source",
            source_type=SourceType.MANUAL_RESEARCH,
            source_name="Demo source",
            url_or_provider="seeds.mvp_data",
            collected_at=_NOW,
            observed_at=_NOW,
            license_or_terms_category=LicenseTermsCategory.PERMISSIVE,
            confidence=Confidence.UNKNOWN,
            data_origin=DataOrigin.DEMO_SEED,
            notes="synthetic_or_curated_demo; not factual public market coverage.",
        )
    )
    demo_observation, _ = service.upsert_observation(
        SourceObservationDefinition(
            observation_id="demo_observation",
            source_id="demo_source",
            collected_at=_NOW,
            observed_at=_NOW,
            data_origin=DataOrigin.SYNTHETIC_OR_CURATED_DEMO,
            observation_status=ObservationStatus.NOT_APPLICABLE,
            confidence=Confidence.UNKNOWN,
            notes="synthetic_or_curated_demo; not factual public market coverage.",
        )
    )
    demo_link = service.create_fact_source_link(
        FactSourceLinkDefinition(
            link_id="demo_company_link",
            observation_id=demo_observation.observation_id,
            fact_type=FactBindingType.COMPANY,
            fact_id="comp_demo",
            data_origin=DataOrigin.DEMO_SEED,
            observation_status=ObservationStatus.NOT_APPLICABLE,
            confidence=Confidence.UNKNOWN,
            notes="synthetic_or_curated_demo; not factual public market coverage.",
        )
    )

    service, real_observation = _seed_observation(
        session,
        source_id="real_source",
        observation_id="real_observation",
        data_origin=DataOrigin.REAL_OBSERVED,
    )
    real_link = service.create_fact_source_link(
        FactSourceLinkDefinition(
            link_id="real_company_link",
            observation_id=real_observation.observation_id,
            fact_type=FactBindingType.COMPANY,
            fact_id="comp_real",
            data_origin=DataOrigin.REAL_OBSERVED,
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            confidence=Confidence.HIGH,
            notes="Real observed test fact.",
        )
    )

    assert demo_link.data_origin == DataOrigin.DEMO_SEED.value
    assert demo_observation.data_origin == DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
    assert "not factual public market coverage" in (demo_link.notes or "")
    assert real_link.data_origin == DataOrigin.REAL_OBSERVED.value
    assert demo_link.data_origin != real_link.data_origin


def test_real_observed_facts_require_provenance_binding_at_service_boundary(
    session: Session,
) -> None:
    service = _service(session)

    with pytest.raises(ProvenanceBindingRequired):
        service.create_fact_source_link(
            FactSourceLinkDefinition(
                link_id="missing_real_observation",
                observation_id=None,
                fact_type=FactBindingType.COMPANY,
                fact_id="comp_real",
                data_origin=DataOrigin.REAL_OBSERVED,
                observation_status=ObservationStatus.POSITIVE_OBSERVED,
                confidence=Confidence.HIGH,
            )
        )
