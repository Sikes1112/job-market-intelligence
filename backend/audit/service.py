"""Audit service.

Orchestrates the per-category checks against canonical truth + output
metadata. Returns an in-memory :class:`AuditReport`. **Mutates nothing.**

The service intentionally reads ORM rows directly via SQLAlchemy and does
**not** import any upstream service module. Layer isolation is pinned by
``test_layer_isolation_slice16.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.audit.checks import (
    check_double_counting,
    check_output_integrity,
    check_override_balance,
    check_personal_objective_separation,
    check_presence_inflation,
)
from backend.audit.payloads import (
    AuditFinding,
    AuditReport,
    AuditScope,
    summarize_findings,
)
from backend.audit.types import status_from_severities
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditService:
    """Synchronous, in-memory audit runner."""

    def __init__(
        self,
        *,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._now = clock or _utc_now

    def run_audit(self, scope: AuditScope | None = None) -> AuditReport:
        scope = scope or AuditScope()
        findings: list[AuditFinding] = []

        companies = self._companies(scope)
        presence_rows = self._presence_rows(scope)
        hiring_rows = self._hiring_rows(scope)
        entry_level_rows = self._entry_level_rows(scope)
        score_rows = self._score_rows(scope)
        output_rows = self._output_metadata_rows()

        findings.extend(check_override_balance(companies))
        findings.extend(
            check_double_counting(
                presence_rows=presence_rows,
                hiring_rows=hiring_rows,
                entry_level_rows=entry_level_rows,
                score_rows=score_rows,
                output_metadata_rows=output_rows,
            )
        )
        findings.extend(check_presence_inflation(presence_rows))
        findings.extend(check_personal_objective_separation(output_rows))
        findings.extend(check_output_integrity(output_rows))

        # Deterministic ordering for stable test assertions.
        findings = sorted(findings, key=lambda f: (f.category.value, f.finding_id))
        severities = [f.severity for f in findings]
        overall = status_from_severities(severities)
        by_severity, by_category = summarize_findings(findings)

        generated_at = self._now()
        report_id = f"audit_{int(generated_at.timestamp())}"
        return AuditReport(
            report_id=report_id,
            generated_at=generated_at,
            overall_status=overall,
            findings=findings,
            summary_by_severity=by_severity,
            summary_by_category=by_category,
            scopes_checked={
                "companies_examined": len(companies),
                "presence_examined": len(presence_rows),
                "hiring_examined": len(hiring_rows),
                "entry_level_examined": len(entry_level_rows),
                "scores_examined": len(score_rows),
                "output_metadata_examined": len(output_rows),
                "filter_region_ids": list(scope.region_ids),
                "filter_company_ids": list(scope.company_ids),
            },
        )

    # --- read-only data access ------------------------------------------

    def _companies(self, scope: AuditScope) -> list[Company]:
        stmt = select(Company)
        if scope.company_ids:
            stmt = stmt.where(Company.company_id.in_(scope.company_ids))
        stmt = stmt.order_by(Company.company_id)
        return list(self._session.execute(stmt).scalars())

    def _presence_rows(self, scope: AuditScope) -> list[CompanyRegionPresence]:
        stmt = select(CompanyRegionPresence)
        if scope.region_ids:
            stmt = stmt.where(CompanyRegionPresence.region_id.in_(scope.region_ids))
        if scope.company_ids:
            stmt = stmt.where(
                CompanyRegionPresence.company_id.in_(scope.company_ids)
            )
        stmt = stmt.order_by(
            CompanyRegionPresence.company_id, CompanyRegionPresence.region_id
        )
        return list(self._session.execute(stmt).scalars())

    def _hiring_rows(self, scope: AuditScope) -> list[CompanyRegionHiring]:
        stmt = select(CompanyRegionHiring)
        if scope.region_ids:
            stmt = stmt.where(CompanyRegionHiring.region_id.in_(scope.region_ids))
        if scope.company_ids:
            stmt = stmt.where(CompanyRegionHiring.company_id.in_(scope.company_ids))
        stmt = stmt.order_by(
            CompanyRegionHiring.company_id, CompanyRegionHiring.region_id
        )
        return list(self._session.execute(stmt).scalars())

    def _entry_level_rows(self, scope: AuditScope) -> list[CompanyRegionEntryLevel]:
        stmt = select(CompanyRegionEntryLevel)
        if scope.region_ids:
            stmt = stmt.where(
                CompanyRegionEntryLevel.region_id.in_(scope.region_ids)
            )
        if scope.company_ids:
            stmt = stmt.where(
                CompanyRegionEntryLevel.company_id.in_(scope.company_ids)
            )
        stmt = stmt.order_by(
            CompanyRegionEntryLevel.company_id,
            CompanyRegionEntryLevel.region_id,
        )
        return list(self._session.execute(stmt).scalars())

    def _score_rows(self, scope: AuditScope) -> list[RegionMarketScore]:
        stmt = select(RegionMarketScore)
        if scope.region_ids:
            stmt = stmt.where(RegionMarketScore.region_id.in_(scope.region_ids))
        stmt = stmt.order_by(RegionMarketScore.region_id)
        return list(self._session.execute(stmt).scalars())

    def _output_metadata_rows(self) -> list[OutputMetadata]:
        stmt = select(OutputMetadata).order_by(
            OutputMetadata.output_type, OutputMetadata.subject_id
        )
        return list(self._session.execute(stmt).scalars())
