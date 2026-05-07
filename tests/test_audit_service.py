"""End-to-end audit service tests.

The service reads ORM rows directly via the test session and produces an
in-memory ``AuditReport``. It must not mutate any canonical or output rows.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.audit.payloads import AuditScope
from backend.audit.service import AuditService
from backend.audit.types import AuditOverallStatus
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _service(session: Session, *, when: datetime | None = None) -> AuditService:
    if when is None:
        when = datetime(2026, 5, 7, 12, tzinfo=UTC)
    return AuditService(session=session, clock=lambda: when)


def _seed_clean(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()


# --- clean dataset --------------------------------------------------------


def test_audit_clean_dataset_passes(session: Session) -> None:
    _seed_clean(session)
    report = _service(session).run_audit()
    assert report.overall_status is AuditOverallStatus.PASSED
    assert report.findings == []
    assert report.summary_by_severity["high"] == 0
    assert report.summary_by_severity["critical"] == 0


def test_audit_includes_scope_counts(session: Session) -> None:
    _seed_clean(session)
    report = _service(session).run_audit()
    assert report.scopes_checked["companies_examined"] == 1
    assert report.scopes_checked["presence_examined"] == 0


# --- override balance ----------------------------------------------------


def test_audit_flags_override_without_reason(session: Session) -> None:
    session.add(
        Company(
            company_id="comp_a",
            company_name="A",
            normalized_company_name="a",
            eligibility_status="override_included",
            eligibility_override_flag=True,
            eligibility_override_reason=None,
        )
    )
    session.flush()
    report = _service(session).run_audit()
    assert report.overall_status is AuditOverallStatus.FAILED
    assert any(
        "override_balance::comp_a::missing_reason" in f.finding_id
        for f in report.findings
    )


# --- presence inflation ---------------------------------------------------


def test_audit_flags_presence_inflation(session: Session) -> None:
    session.add(
        Region(
            region_id="r1",
            region_name="r1",
            display_name="R1",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="c1",
            company_name="C1",
            normalized_company_name="c1",
            eligibility_status="eligible",
        )
    )
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id="p1",
            company_id="c1",
            region_id="r1",
            presence_status="present",
            presence_basis="insufficient_evidence",
            office_evidence_flag=False,
            operations_evidence_flag=False,
            hiring_evidence_flag=False,
        )
    )
    session.flush()
    report = _service(session).run_audit()
    assert report.overall_status is AuditOverallStatus.FAILED


# --- personal/objective separation ----------------------------------------


def test_audit_flags_personalized_output_persistence(session: Session) -> None:
    session.add(
        OutputMetadata(
            output_id="o_personalized",
            output_type="personalized_output",
            subject_id="user_xyz",
        )
    )
    session.flush()
    report = _service(session).run_audit()
    assert report.overall_status is AuditOverallStatus.CRITICAL
    assert any(
        f.category.value == "personal_objective_separation"
        for f in report.findings
    )


# --- output integrity -----------------------------------------------------


def test_audit_flags_noncanonical_comparison_subject_id(
    session: Session,
) -> None:
    row = OutputMetadata(
        output_id="o1",
        output_type="comparison_output",
        subject_id="z__a",  # noncanonical
        artifact_hash="abc",
    )
    row.state = "fresh"
    session.add(row)
    session.flush()
    report = _service(session).run_audit()
    assert any(
        "noncanonical_subject_id" in f.finding_id for f in report.findings
    )


# --- determinism ---------------------------------------------------------


def test_audit_findings_are_deterministically_ordered(session: Session) -> None:
    session.add_all(
        [
            Company(
                company_id=cid,
                company_name=cid,
                normalized_company_name=cid,
                eligibility_status="override_included",
                eligibility_override_flag=True,
                eligibility_override_reason=None,
            )
            for cid in ("c_z", "c_a", "c_m")
        ]
    )
    session.flush()
    a = _service(session).run_audit()
    b = _service(session).run_audit()
    assert [f.finding_id for f in a.findings] == [f.finding_id for f in b.findings]


# --- non-mutation ---------------------------------------------------------


def test_audit_does_not_mutate_canonical_rows(session: Session) -> None:
    region = Region(
        region_id="greater_boston",
        region_name="greater_boston",
        display_name="Greater Boston",
        region_type="greater_region",
    )
    company = Company(
        company_id="comp_a",
        company_name="A",
        normalized_company_name="a",
        eligibility_status="eligible",
    )
    session.add_all([region, company])
    session.flush()
    presence = CompanyRegionPresence(
        presence_id="p_a",
        company_id="comp_a",
        region_id="greater_boston",
        presence_status="present",
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
    )
    hiring = CompanyRegionHiring(
        hiring_id="h_a", company_id="comp_a", region_id="greater_boston"
    )
    entry_level = CompanyRegionEntryLevel(
        entry_level_id="e_a", company_id="comp_a", region_id="greater_boston"
    )
    score = RegionMarketScore(
        region_score_id="rms_b",
        region_id="greater_boston",
        score_ruleset_version="marketscore_v1",
    )
    om = OutputMetadata(
        output_id="o1",
        output_type="region_output",
        subject_id="greater_boston",
        artifact_hash="abc",
    )
    session.add_all([presence, hiring, entry_level, score, om])
    session.flush()

    region_v = region.version
    company_v = company.version
    presence_v = presence.version
    hiring_v = hiring.version
    entry_level_v = entry_level.version
    score_v = score.version
    om_v = om.version

    _service(session).run_audit()

    for obj, before in (
        (region, region_v),
        (company, company_v),
        (presence, presence_v),
        (hiring, hiring_v),
        (entry_level, entry_level_v),
        (score, score_v),
        (om, om_v),
    ):
        session.refresh(obj)
        assert obj.version == before


def test_audit_scope_filters_companies(session: Session) -> None:
    session.add_all(
        [
            Company(
                company_id="c_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="override_included",
                eligibility_override_flag=True,
                eligibility_override_reason=None,
            ),
            Company(
                company_id="c_b",
                company_name="B",
                normalized_company_name="b",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    report = _service(session).run_audit(AuditScope(company_ids=["c_b"]))
    # Only c_b examined → no override-balance findings.
    assert report.scopes_checked["companies_examined"] == 1
    assert report.findings == []
