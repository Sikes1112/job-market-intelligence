from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.audit.payloads import (
    AuditFinding,
    AuditReport,
    AuditScope,
    summarize_findings,
)
from backend.audit.types import (
    AuditCategory,
    AuditOverallStatus,
    AuditSeverity,
)


def _finding(**overrides) -> AuditFinding:
    base = dict(
        finding_id="cat::scope::detail",
        severity=AuditSeverity.MEDIUM,
        category=AuditCategory.OVERRIDE_BALANCE,
        scope_type="company",
        scope_ref="comp_a",
        message="something",
    )
    base.update(overrides)
    return AuditFinding(**base)


# --- AuditFinding ---------------------------------------------------------


def test_finding_round_trip() -> None:
    f = _finding(evidence_refs=["row::1", "row::2"], recommendation="check it")
    dumped = f.model_dump()
    again = AuditFinding.model_validate(dumped)
    assert again == f


def test_finding_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        _finding(finding_id="")
    with pytest.raises(ValidationError):
        _finding(scope_type="   ")
    with pytest.raises(ValidationError):
        _finding(scope_ref="")
    with pytest.raises(ValidationError):
        _finding(message="")


def test_finding_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        AuditFinding.model_validate(
            {
                "finding_id": "x",
                "severity": "extreme",
                "category": "override_balance",
                "scope_type": "company",
                "scope_ref": "comp_a",
                "message": "m",
            }
        )


def test_finding_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuditFinding.model_validate(
            {
                "finding_id": "x",
                "severity": "low",
                "category": "override_balance",
                "scope_type": "c",
                "scope_ref": "c",
                "message": "m",
                "rogue": True,
            }
        )


# --- AuditScope -----------------------------------------------------------


def test_scope_default_is_empty() -> None:
    scope = AuditScope()
    assert scope.region_ids == []
    assert scope.company_ids == []


def test_scope_rejects_blank_entry() -> None:
    with pytest.raises(ValidationError):
        AuditScope(region_ids=["greater_boston", ""])


def test_scope_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuditScope.model_validate({"rogue": True})


# --- AuditReport ----------------------------------------------------------


def test_report_round_trip() -> None:
    findings = [_finding()]
    by_sev, by_cat = summarize_findings(findings)
    r = AuditReport(
        report_id="audit_1",
        generated_at=datetime(2026, 5, 7, tzinfo=UTC),
        overall_status=AuditOverallStatus.WARNING,
        findings=findings,
        summary_by_severity=by_sev,
        summary_by_category=by_cat,
    )
    again = AuditReport.model_validate(r.model_dump())
    assert again == r


def test_report_generated_at_must_be_aware() -> None:
    by_sev, by_cat = summarize_findings([])
    with pytest.raises(ValidationError):
        AuditReport(
            report_id="x",
            generated_at=datetime(2026, 5, 7),  # naive
            overall_status=AuditOverallStatus.PASSED,
            findings=[],
            summary_by_severity=by_sev,
            summary_by_category=by_cat,
        )


# --- summarize_findings ---------------------------------------------------


def test_summarize_includes_zero_for_unseen_buckets() -> None:
    by_sev, by_cat = summarize_findings([])
    assert set(by_sev.keys()) == AuditSeverity.values()
    assert set(by_cat.keys()) == AuditCategory.values()
    assert all(v == 0 for v in by_sev.values())
    assert all(v == 0 for v in by_cat.values())


def test_summarize_counts_per_bucket() -> None:
    findings = [
        _finding(severity=AuditSeverity.HIGH),
        _finding(severity=AuditSeverity.HIGH),
        _finding(
            severity=AuditSeverity.LOW,
            category=AuditCategory.PRESENCE_INFLATION,
        ),
    ]
    by_sev, by_cat = summarize_findings(findings)
    assert by_sev["high"] == 2
    assert by_sev["low"] == 1
    assert by_sev["critical"] == 0
    assert by_cat["override_balance"] == 2
    assert by_cat["presence_inflation"] == 1
