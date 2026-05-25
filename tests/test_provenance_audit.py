from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.provenance.audit import (
    PreparedValueAuditRecord,
    ProvenanceAuditCode,
    ProvenanceAuditFact,
    ProvenanceAuditService,
)
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
from seeds import mvp_seed

_NOW = datetime(2026, 5, 20, 12, tzinfo=UTC)


def _audit(session: Session) -> ProvenanceAuditService:
    return ProvenanceAuditService(session=session, clock=lambda: _NOW)


def _link(
    session: Session,
    *,
    fact_type: FactBindingType = FactBindingType.COMPANY,
    fact_id: str = "comp_real",
    link_id: str | None = None,
    source_id: str = "source_real",
    observation_id: str | None = None,
    observed_at: datetime = _NOW,
    source_data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
    observation_data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
    link_data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
    confidence: Confidence = Confidence.HIGH,
    observation_status: ObservationStatus = ObservationStatus.POSITIVE_OBSERVED,
) -> None:
    repository = ProvenanceRepository(session)
    service = ProvenanceService(repository)
    observation_id = observation_id or f"obs_{link_id or fact_id}_{source_id}"
    link_id = link_id or f"link_{fact_type.value}_{fact_id}_{source_id}"
    if repository.get_source_ref(source_id) is None:
        service.upsert_source_ref(
            SourceRefDefinition(
                source_id=source_id,
                source_type=SourceType.COMPANY_OFFICIAL,
                source_name=f"Source {source_id}",
                url_or_provider=f"https://{source_id}.example.test",
                collected_at=observed_at,
                observed_at=observed_at,
                license_or_terms_category=LicenseTermsCategory.PUBLIC,
                confidence=confidence,
                data_origin=source_data_origin,
                notes="test source",
            )
        )
    service.upsert_observation(
        SourceObservationDefinition(
            observation_id=observation_id,
            source_id=source_id,
            collected_at=observed_at,
            observed_at=observed_at,
            data_origin=observation_data_origin,
            observation_status=observation_status,
            confidence=confidence,
            notes="test observation",
        )
    )
    service.upsert_fact_source_link(
        FactSourceLinkDefinition(
            link_id=link_id,
            observation_id=observation_id,
            fact_type=fact_type,
            fact_id=fact_id,
            data_origin=link_data_origin,
            observation_status=observation_status,
            confidence=confidence,
            notes="test fact link",
        )
    )


def test_missing_provenance_emits_finding(session: Session) -> None:
    report = _audit(session).run_audit(
        expected_facts=[
            ProvenanceAuditFact(
                fact_type=FactBindingType.COMPANY,
                fact_id="comp_missing",
                data_origin=DataOrigin.REAL_OBSERVED,
            )
        ]
    )

    [finding] = report.findings
    assert finding.code is ProvenanceAuditCode.MISSING_PROVENANCE
    assert finding.severity.value == "error"
    assert finding.fact_type == FactBindingType.COMPANY.value
    assert finding.fact_id == "comp_missing"
    assert finding.explanation
    assert finding.remediation
    assert finding.blocks_real_data_trust is True


def test_stale_source_observation_emits_finding(session: Session) -> None:
    _link(
        session,
        fact_type=FactBindingType.COMPANY_REGION_HIRING,
        fact_id="hiring_real",
        observed_at=_NOW - timedelta(days=15),
    )

    report = _audit(session).run_audit()

    assert [finding.code for finding in report.findings] == [
        ProvenanceAuditCode.STALE_SOURCE_DATA
    ]
    assert report.findings[0].observation_id is not None
    assert report.findings[0].blocks_real_data_trust is True


def test_single_source_overreliance_emits_finding(session: Session) -> None:
    for index in range(3):
        _link(
            session,
            fact_type=FactBindingType.COMPANY,
            fact_id=f"comp_{index}",
            source_id="source_only",
            link_id=f"link_single_{index}",
        )

    report = _audit(session).run_audit()

    assert any(
        finding.code is ProvenanceAuditCode.SINGLE_SOURCE_OVERRELIANCE
        for finding in report.findings
    )
    finding = next(
        item
        for item in report.findings
        if item.code is ProvenanceAuditCode.SINGLE_SOURCE_OVERRELIANCE
    )
    assert finding.severity.value == "warning"
    assert finding.blocks_real_data_trust is False


def test_low_confidence_source_concentration_emits_finding(session: Session) -> None:
    for index in range(3):
        _link(
            session,
            fact_type=FactBindingType.REGION,
            fact_id=f"region_{index}",
            source_id=f"source_low_{index}",
            link_id=f"link_low_{index}",
            confidence=Confidence.LOW,
        )

    report = _audit(session).run_audit()

    finding = next(
        item
        for item in report.findings
        if item.code is ProvenanceAuditCode.LOW_CONFIDENCE_CONCENTRATION
    )
    assert finding.severity.value == "error"
    assert finding.blocks_real_data_trust is True


def test_seed_and_real_mixture_emits_finding(session: Session) -> None:
    _link(
        session,
        fact_type=FactBindingType.COMPANY,
        fact_id="comp_mixed",
        source_id="source_demo",
        link_id="link_demo_mixed",
        source_data_origin=DataOrigin.DEMO_SEED,
        observation_data_origin=DataOrigin.SYNTHETIC_OR_CURATED_DEMO,
        link_data_origin=DataOrigin.DEMO_SEED,
        observation_status=ObservationStatus.NOT_APPLICABLE,
        confidence=Confidence.UNKNOWN,
    )
    _link(
        session,
        fact_type=FactBindingType.COMPANY,
        fact_id="comp_mixed",
        source_id="source_real",
        link_id="link_real_mixed",
    )

    report = _audit(session).run_audit()

    finding = next(
        item for item in report.findings if item.code is ProvenanceAuditCode.SEED_REAL_MIXED
    )
    assert finding.severity.value == "critical"
    assert finding.blocks_real_data_trust is True


def test_unknown_converted_to_zero_emits_finding(session: Session) -> None:
    report = _audit(session).run_audit(
        prepared_values=[
            PreparedValueAuditRecord(
                fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
                fact_id="entry_1",
                field_name="internship_count_total",
                input_status=ObservationStatus.UNKNOWN,
                output_value=0,
                output_status=ObservationStatus.ZERO_OBSERVED,
            )
        ]
    )

    [finding] = report.findings
    assert finding.code is ProvenanceAuditCode.UNKNOWN_TREATED_AS_ZERO
    assert finding.blocks_real_data_trust is True


def test_clean_demo_seed_does_not_fail_real_market_audit(session: Session) -> None:
    mvp_seed.run_seed(session)

    report = ProvenanceAuditService(
        session=session,
        clock=lambda: datetime(2026, 5, 21, tzinfo=UTC),
    ).run_audit()

    assert report.findings == []
    assert report.blocking_findings_count == 0


def test_clean_real_observed_fact_with_provenance_has_no_missing_finding(
    session: Session,
) -> None:
    _link(session, fact_type=FactBindingType.COMPANY, fact_id="comp_real")

    report = _audit(session).run_audit(
        expected_facts=[
            ProvenanceAuditFact(
                fact_type=FactBindingType.COMPANY,
                fact_id="comp_real",
                data_origin=DataOrigin.REAL_OBSERVED,
            )
        ]
    )

    assert not any(
        finding.code is ProvenanceAuditCode.MISSING_PROVENANCE
        for finding in report.findings
    )


def test_finding_schema_includes_required_fields(session: Session) -> None:
    report = _audit(session).run_audit(
        expected_facts=[
            ProvenanceAuditFact(
                fact_type=FactBindingType.REGION,
                fact_id="region_missing",
                data_origin=DataOrigin.REAL_DERIVED,
            )
        ]
    )

    finding = report.findings[0]
    assert finding.code
    assert finding.severity
    assert finding.explanation
    assert finding.remediation
    assert isinstance(finding.blocks_real_data_trust, bool)
    assert report.summary_by_code[finding.code.value] == 1
    assert report.summary_by_severity[finding.severity.value] == 1
