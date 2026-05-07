"""Direct tests of the per-category check functions."""

from __future__ import annotations

from backend.audit.checks import (
    check_double_counting,
    check_output_integrity,
    check_override_balance,
    check_personal_objective_separation,
    check_presence_inflation,
)
from backend.audit.types import AuditCategory, AuditSeverity
from backend.companies.models import Company
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

# --- override balance -----------------------------------------------------


def _company(**overrides) -> Company:
    base = dict(
        company_id="c1",
        company_name="C1",
        normalized_company_name="c1",
        eligibility_status="eligible",
    )
    base.update(overrides)
    return Company(**base)


def test_override_balance_clean_dataset_no_findings() -> None:
    findings = check_override_balance([_company()])
    assert findings == []


def test_override_included_without_reason_is_flagged() -> None:
    company = _company(
        eligibility_status="override_included",
        eligibility_override_flag=True,
        eligibility_override_reason=None,
    )
    findings = check_override_balance([company])
    codes = {f.finding_id for f in findings}
    assert "override_balance::c1::missing_reason" in codes
    [f] = [f for f in findings if "missing_reason" in f.finding_id]
    assert f.severity is AuditSeverity.HIGH


def test_override_included_with_blank_reason_is_flagged() -> None:
    company = _company(
        eligibility_status="override_included",
        eligibility_override_flag=True,
        eligibility_override_reason="   ",
    )
    findings = check_override_balance([company])
    assert any("missing_reason" in f.finding_id for f in findings)


def test_inconsistent_status_without_flag_is_flagged() -> None:
    company = _company(
        eligibility_status="override_included",
        eligibility_override_flag=False,
        eligibility_override_reason="reason",
    )
    findings = check_override_balance([company])
    assert any("flag_inconsistent" in f.finding_id for f in findings)


def test_orphan_flag_without_status_is_flagged() -> None:
    company = _company(
        eligibility_status="eligible",
        eligibility_override_flag=True,
    )
    findings = check_override_balance([company])
    assert any("orphan_flag" in f.finding_id for f in findings)


def test_override_ratio_warning_uses_documented_threshold() -> None:
    # 2 of 3 override-included → ratio 0.667 > default 0.30.
    companies = [
        _company(
            company_id="a",
            eligibility_status="override_included",
            eligibility_override_flag=True,
            eligibility_override_reason="r",
        ),
        _company(
            company_id="b",
            eligibility_status="override_included",
            eligibility_override_flag=True,
            eligibility_override_reason="r",
        ),
        _company(company_id="c"),
    ]
    findings = check_override_balance(companies)
    assert any("ratio_warning" in f.finding_id for f in findings)


def test_override_ratio_warning_threshold_is_tunable() -> None:
    """If the threshold is set above the actual ratio, no ratio warning."""
    companies = [
        _company(
            company_id="a",
            eligibility_status="override_included",
            eligibility_override_flag=True,
            eligibility_override_reason="r",
        ),
        _company(company_id="b"),
    ]
    findings = check_override_balance(
        companies, ratio_warning_threshold=0.99
    )
    assert not any("ratio_warning" in f.finding_id for f in findings)


# --- double-counting ------------------------------------------------------


def test_double_counting_clean_dataset_no_findings() -> None:
    findings = check_double_counting(
        presence_rows=[],
        hiring_rows=[],
        entry_level_rows=[],
        score_rows=[],
        output_metadata_rows=[],
    )
    assert findings == []


def test_double_counting_detects_duplicate_logical_scopes() -> None:
    """Simulate duplicate rows in memory (DB unique constraints prevent
    them in real schema) so the check has something to flag."""
    duplicates = [
        CompanyRegionPresence(
            presence_id="p1",
            company_id="c1",
            region_id="r1",
            presence_status="present",
        ),
        CompanyRegionPresence(
            presence_id="p2",
            company_id="c1",
            region_id="r1",
            presence_status="present",
        ),
    ]
    findings = check_double_counting(
        presence_rows=duplicates,
        hiring_rows=[],
        entry_level_rows=[],
        score_rows=[],
        output_metadata_rows=[],
    )
    assert any("double_counting::presence::c1::r1" in f.finding_id for f in findings)
    [f] = [f for f in findings if "presence::c1::r1" in f.finding_id]
    assert f.severity is AuditSeverity.CRITICAL
    assert f.category is AuditCategory.DOUBLE_COUNTING


def test_double_counting_detects_duplicate_score_rows() -> None:
    duplicates = [
        RegionMarketScore(region_score_id="rms_a", region_id="r1"),
        RegionMarketScore(region_score_id="rms_b", region_id="r1"),
    ]
    findings = check_double_counting(
        presence_rows=[],
        hiring_rows=[],
        entry_level_rows=[],
        score_rows=duplicates,
        output_metadata_rows=[],
    )
    assert any(
        "double_counting::region_market_scores::r1" in f.finding_id for f in findings
    )


def test_double_counting_detects_duplicate_output_metadata() -> None:
    duplicates = [
        OutputMetadata(
            output_id="o1",
            output_type="region_output",
            subject_id="greater_boston",
        ),
        OutputMetadata(
            output_id="o2",
            output_type="region_output",
            subject_id="greater_boston",
        ),
    ]
    findings = check_double_counting(
        presence_rows=[],
        hiring_rows=[],
        entry_level_rows=[],
        score_rows=[],
        output_metadata_rows=duplicates,
    )
    assert any(
        "output_metadata::region_output::greater_boston" in f.finding_id
        for f in findings
    )


# --- presence inflation ---------------------------------------------------


def test_presence_inflation_clean_present_record_no_findings() -> None:
    p = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
        presence_confidence="high_confidence",
    )
    assert check_presence_inflation([p]) == []


def test_presence_inflation_present_with_insufficient_basis_flagged() -> None:
    p = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
        presence_basis="insufficient_evidence",
    )
    findings = check_presence_inflation([p])
    assert any("insufficient_basis" in f.finding_id for f in findings)


def test_presence_inflation_present_with_no_evidence_flagged() -> None:
    p = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
        presence_basis="office_plus_operations",
        office_evidence_flag=False,
        operations_evidence_flag=False,
        hiring_evidence_flag=False,
    )
    findings = check_presence_inflation([p])
    assert any("no_evidence" in f.finding_id for f in findings)


def test_presence_inflation_low_confidence_flagged_medium() -> None:
    p = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
        presence_confidence="low_confidence",
    )
    findings = check_presence_inflation([p])
    [f] = [f for f in findings if "low_confidence" in f.finding_id]
    assert f.severity is AuditSeverity.MEDIUM


def test_presence_inflation_skips_non_present_rows() -> None:
    p = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="uncertain",
        presence_basis="insufficient_evidence",
    )
    assert check_presence_inflation([p]) == []


# --- personal/objective separation ----------------------------------------


def test_personal_objective_separation_clean() -> None:
    rows = [
        OutputMetadata(
            output_id="o1",
            output_type="region_output",
            subject_id="greater_boston",
        )
    ]
    assert check_personal_objective_separation(rows) == []


def test_personal_objective_separation_flags_personalized_output_rows() -> None:
    rows = [
        OutputMetadata(
            output_id="o_personalized_1",
            output_type="personalized_output",
            subject_id="user_session_xyz",
        )
    ]
    findings = check_personal_objective_separation(rows)
    assert len(findings) == 1
    assert findings[0].severity is AuditSeverity.CRITICAL
    assert findings[0].category is AuditCategory.PERSONAL_OBJECTIVE_SEPARATION


# --- output integrity -----------------------------------------------------


def test_output_integrity_clean() -> None:
    rows = [
        OutputMetadata(
            output_id="o1",
            output_type="region_output",
            subject_id="greater_boston",
            artifact_hash="abc",
        )
    ]
    rows[0].state = "fresh"
    assert check_output_integrity(rows) == []


def test_output_integrity_flags_missing_hash_for_fresh() -> None:
    row = OutputMetadata(
        output_id="o1",
        output_type="region_output",
        subject_id="greater_boston",
    )
    row.state = "fresh"
    row.artifact_hash = None
    findings = check_output_integrity([row])
    assert any("missing_artifact_hash" in f.finding_id for f in findings)


def test_output_integrity_flags_noncanonical_comparison_subject_id() -> None:
    row = OutputMetadata(
        output_id="o1",
        output_type="comparison_output",
        # Not min__max — "z" > "a" so canonical would be "a__z".
        subject_id="z__a",
        artifact_hash="abc",
    )
    row.state = "fresh"
    findings = check_output_integrity([row])
    assert any("noncanonical_subject_id" in f.finding_id for f in findings)


def test_output_integrity_accepts_canonical_comparison_subject_id() -> None:
    row = OutputMetadata(
        output_id="o1",
        output_type="comparison_output",
        subject_id="greater_boston__greater_sf",
        artifact_hash="abc",
    )
    row.state = "fresh"
    findings = check_output_integrity([row])
    assert not any("noncanonical_subject_id" in f.finding_id for f in findings)


def test_output_integrity_skips_personalized_output_rows() -> None:
    """Personalized output rows are flagged by the separation check —
    output integrity intentionally skips them so they aren't double-flagged."""
    row = OutputMetadata(
        output_id="o1",
        output_type="personalized_output",
        subject_id="x",
    )
    row.state = "fresh"
    row.artifact_hash = None
    assert check_output_integrity([row]) == []
