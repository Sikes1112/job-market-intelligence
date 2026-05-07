"""Audit-domain enums.

Small, documented vocabularies. Anything outside these enums is rejected
by the Pydantic payload models in :mod:`backend.audit.payloads`.
"""

from __future__ import annotations

from enum import StrEnum


class AuditSeverity(StrEnum):
    """Severity ladder for individual findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class AuditCategory(StrEnum):
    """The five MVP integrity categories."""

    OVERRIDE_BALANCE = "override_balance"
    DOUBLE_COUNTING = "double_counting"
    PRESENCE_INFLATION = "presence_inflation"
    PERSONAL_OBJECTIVE_SEPARATION = "personal_objective_separation"
    OUTPUT_INTEGRITY = "output_integrity"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class AuditOverallStatus(StrEnum):
    """Audit-report-level status, derived deterministically from findings."""

    PASSED = "passed"        # zero findings
    WARNING = "warning"      # only low/medium findings
    FAILED = "failed"        # at least one high finding
    CRITICAL = "critical"    # at least one critical finding

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


def status_from_severities(severities: list[AuditSeverity]) -> AuditOverallStatus:
    """Map the worst severity in a finding list to the report-level status."""
    if not severities:
        return AuditOverallStatus.PASSED
    if AuditSeverity.CRITICAL in severities:
        return AuditOverallStatus.CRITICAL
    if AuditSeverity.HIGH in severities:
        return AuditOverallStatus.FAILED
    return AuditOverallStatus.WARNING


# Default override-ratio threshold beyond which a deterministic warning is
# emitted. Tested directly so the threshold can be tuned without surprise.
DEFAULT_OVERRIDE_RATIO_WARNING_THRESHOLD: float = 0.30
