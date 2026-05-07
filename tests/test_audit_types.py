from backend.audit.types import (
    DEFAULT_OVERRIDE_RATIO_WARNING_THRESHOLD,
    AuditCategory,
    AuditOverallStatus,
    AuditSeverity,
    status_from_severities,
)


def test_severity_vocabulary_is_small() -> None:
    assert AuditSeverity.values() == {"low", "medium", "high", "critical"}


def test_category_vocabulary_is_documented() -> None:
    assert AuditCategory.values() == {
        "override_balance",
        "double_counting",
        "presence_inflation",
        "personal_objective_separation",
        "output_integrity",
    }


def test_overall_status_vocabulary() -> None:
    assert AuditOverallStatus.values() == {
        "passed",
        "warning",
        "failed",
        "critical",
    }


def test_status_passed_when_no_findings() -> None:
    assert status_from_severities([]) is AuditOverallStatus.PASSED


def test_status_warning_for_low_or_medium_only() -> None:
    assert (
        status_from_severities([AuditSeverity.LOW]) is AuditOverallStatus.WARNING
    )
    assert (
        status_from_severities([AuditSeverity.LOW, AuditSeverity.MEDIUM])
        is AuditOverallStatus.WARNING
    )


def test_status_failed_when_any_high() -> None:
    assert (
        status_from_severities([AuditSeverity.LOW, AuditSeverity.HIGH])
        is AuditOverallStatus.FAILED
    )


def test_status_critical_when_any_critical() -> None:
    assert (
        status_from_severities([AuditSeverity.HIGH, AuditSeverity.CRITICAL])
        is AuditOverallStatus.CRITICAL
    )


def test_default_override_ratio_threshold_is_documented() -> None:
    assert DEFAULT_OVERRIDE_RATIO_WARNING_THRESHOLD == 0.30
