"""Layer 3D provenance audit checks.

The checks here are diagnostic only. They do not scrape, ingest, mutate
canonical truth, or block write paths.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.provenance.freshness import evaluate_fact_link_freshness
from backend.provenance.models import FactSourceLink
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import (
    DEMO_DATA_ORIGINS,
    REAL_DATA_ORIGINS,
    DataOrigin,
    FactBindingType,
    ObservationStatus,
    ProvenanceFactType,
)

SINGLE_SOURCE_OVERRELIANCE_FACT_THRESHOLD = 3
LOW_CONFIDENCE_CONCENTRATION_FACT_THRESHOLD = 3
LOW_CONFIDENCE_WARNING_RATIO = 0.50
LOW_CONFIDENCE_ERROR_RATIO = 0.80

_LOW_CONFIDENCE_VALUES = frozenset(
    {
        Confidence.LOW.value,
        Confidence.UNKNOWN.value,
        ObservationStatus.LOW_CONFIDENCE.value,
    }
)
_UNKNOWN_INPUT_STATUSES = frozenset(
    {
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.STALE,
    }
)


class ProvenanceAuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ProvenanceAuditCode(StrEnum):
    MISSING_PROVENANCE = "missing_provenance"
    STALE_SOURCE_DATA = "stale_source_data"
    SINGLE_SOURCE_OVERRELIANCE = "single_source_overreliance"
    LOW_CONFIDENCE_CONCENTRATION = "low_confidence_source_concentration"
    SEED_REAL_MIXED = "seed_data_mixed_with_real_data"
    UNKNOWN_TREATED_AS_ZERO = "unknown_values_treated_as_zero"
    SCORE_INPUT_FRESHNESS_CATEGORY_MISSING = "score_input_freshness_category_missing"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ProvenanceAuditFact(BaseModel):
    """Expected fact boundary for checks before origin is persisted everywhere."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_type: FactBindingType
    fact_id: str = Field(min_length=1)
    data_origin: DataOrigin


class PreparedValueAuditRecord(BaseModel):
    """Prepared output/input value to verify unknown values were not zeroed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_type: FactBindingType
    fact_id: str = Field(min_length=1)
    field_name: str | None = Field(default=None, min_length=1)
    input_status: ObservationStatus
    output_value: int | float | None = None
    output_status: ObservationStatus | None = None


class ProvenanceAuditFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    code: ProvenanceAuditCode
    severity: ProvenanceAuditSeverity
    fact_type: str | None = None
    fact_id: str | None = None
    source_id: str | None = None
    observation_id: str | None = None
    explanation: str = Field(min_length=1)
    remediation: str = Field(min_length=1)
    blocks_real_data_trust: bool

    @field_validator("finding_id", "explanation", "remediation")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ProvenanceAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    findings: list[ProvenanceAuditFinding] = Field(default_factory=list)
    summary_by_code: dict[str, int] = Field(default_factory=dict)
    summary_by_severity: dict[str, int] = Field(default_factory=dict)
    blocking_findings_count: int = 0

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProvenanceAuditService:
    def __init__(
        self,
        *,
        session: Session,
        clock: Callable[[], datetime] | None = None,
        single_source_fact_threshold: int = SINGLE_SOURCE_OVERRELIANCE_FACT_THRESHOLD,
        low_confidence_fact_threshold: int = LOW_CONFIDENCE_CONCENTRATION_FACT_THRESHOLD,
        low_confidence_warning_ratio: float = LOW_CONFIDENCE_WARNING_RATIO,
        low_confidence_error_ratio: float = LOW_CONFIDENCE_ERROR_RATIO,
    ) -> None:
        self._session = session
        self._now = clock or _utc_now
        self._single_source_fact_threshold = single_source_fact_threshold
        self._low_confidence_fact_threshold = low_confidence_fact_threshold
        self._low_confidence_warning_ratio = low_confidence_warning_ratio
        self._low_confidence_error_ratio = low_confidence_error_ratio

    def run_audit(
        self,
        *,
        expected_facts: Iterable[ProvenanceAuditFact] = (),
        prepared_values: Iterable[PreparedValueAuditRecord] = (),
        score_input_fact_types: Mapping[str, ProvenanceFactType | str] | None = None,
        include_demo_sources: bool = False,
    ) -> ProvenanceAuditReport:
        links = self._fact_source_links()
        real_links = [
            link for link in links if DataOrigin(link.data_origin) in REAL_DATA_ORIGINS
        ]
        scoped_links = links if include_demo_sources else real_links
        score_input_fact_types = score_input_fact_types or {}

        findings: list[ProvenanceAuditFinding] = []
        findings.extend(self._check_missing_provenance(expected_facts, links))
        findings.extend(self._check_stale_source_data(scoped_links, score_input_fact_types))
        findings.extend(self._check_single_source_overreliance(scoped_links))
        findings.extend(self._check_low_confidence_concentration(scoped_links))
        findings.extend(self._check_seed_real_mixture(links))
        findings.extend(self._check_unknown_treated_as_zero(prepared_values))

        findings = sorted(findings, key=lambda finding: finding.finding_id)
        return ProvenanceAuditReport(
            generated_at=self._now(),
            findings=findings,
            summary_by_code=_summary_by_code(findings),
            summary_by_severity=_summary_by_severity(findings),
            blocking_findings_count=sum(
                1 for finding in findings if finding.blocks_real_data_trust
            ),
        )

    def _fact_source_links(self) -> list[FactSourceLink]:
        rows = self._session.execute(
            select(FactSourceLink).order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.link_id,
            )
        )
        return list(rows.scalars())

    def _check_missing_provenance(
        self,
        expected_facts: Iterable[ProvenanceAuditFact],
        links: list[FactSourceLink],
    ) -> list[ProvenanceAuditFinding]:
        linked = {(link.fact_type, link.fact_id) for link in links}
        findings: list[ProvenanceAuditFinding] = []
        for fact in expected_facts:
            if fact.data_origin not in REAL_DATA_ORIGINS:
                continue
            key = (fact.fact_type.value, fact.fact_id)
            if key in linked:
                continue
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=(
                        f"provenance::missing::{fact.fact_type.value}::{fact.fact_id}"
                    ),
                    code=ProvenanceAuditCode.MISSING_PROVENANCE,
                    severity=ProvenanceAuditSeverity.ERROR,
                    fact_type=fact.fact_type.value,
                    fact_id=fact.fact_id,
                    explanation=(
                        f"real fact {fact.fact_type.value}:{fact.fact_id} has no "
                        "FactSourceLink"
                    ),
                    remediation=(
                        "Create a SourceRef, SourceObservation, and FactSourceLink "
                        "before trusting this real market fact."
                    ),
                    blocks_real_data_trust=True,
                )
            )
        return findings

    def _check_stale_source_data(
        self,
        links: list[FactSourceLink],
        score_input_fact_types: Mapping[str, ProvenanceFactType | str],
    ) -> list[ProvenanceAuditFinding]:
        findings: list[ProvenanceAuditFinding] = []
        for link in links:
            score_source_fact_type = _score_source_fact_type_for(
                link, score_input_fact_types
            )
            if link.fact_type == FactBindingType.SCORE_INPUT.value:
                if score_source_fact_type is None:
                    findings.append(
                        ProvenanceAuditFinding(
                            finding_id=f"provenance::score_input_freshness::{link.link_id}",
                            code=(
                                ProvenanceAuditCode.SCORE_INPUT_FRESHNESS_CATEGORY_MISSING
                            ),
                            severity=ProvenanceAuditSeverity.ERROR,
                            fact_type=link.fact_type,
                            fact_id=link.fact_id,
                            source_id=link.source_id,
                            observation_id=link.observation_id,
                            explanation=(
                                "score_input link does not declare the source fact "
                                "category needed for freshness evaluation"
                            ),
                            remediation=(
                                "Pass score_input_fact_types keyed by link_id or "
                                "fact_id, or store the source fact category before "
                                "trusting the score input."
                            ),
                            blocks_real_data_trust=True,
                        )
                    )
                    continue
            status = evaluate_fact_link_freshness(
                link,
                score_source_fact_type=score_source_fact_type,
                now=self._now(),
            )
            if status is not FreshnessStatus.STALE:
                continue
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=f"provenance::stale::{link.link_id}",
                    code=ProvenanceAuditCode.STALE_SOURCE_DATA,
                    severity=ProvenanceAuditSeverity.ERROR,
                    fact_type=link.fact_type,
                    fact_id=link.fact_id,
                    source_id=link.source_id,
                    observation_id=link.observation_id,
                    explanation=(
                        f"source observation {link.observation_id!r} for "
                        f"{link.fact_type}:{link.fact_id} is stale for its "
                        "freshness window"
                    ),
                    remediation=(
                        "Refresh the source observation or mark the linked fact "
                        "stale before using it as current real market evidence."
                    ),
                    blocks_real_data_trust=True,
                )
            )
        return findings

    def _check_single_source_overreliance(
        self, links: list[FactSourceLink]
    ) -> list[ProvenanceAuditFinding]:
        findings: list[ProvenanceAuditFinding] = []
        by_fact_type: dict[str, list[FactSourceLink]] = defaultdict(list)
        for link in links:
            by_fact_type[link.fact_type].append(link)
        for fact_type, rows in by_fact_type.items():
            fact_ids = {row.fact_id for row in rows}
            source_ids = {row.source_id for row in rows}
            if (
                len(fact_ids) < self._single_source_fact_threshold
                or len(source_ids) != 1
            ):
                continue
            [source_id] = list(source_ids)
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=f"provenance::single_source::{fact_type}::{source_id}",
                    code=ProvenanceAuditCode.SINGLE_SOURCE_OVERRELIANCE,
                    severity=ProvenanceAuditSeverity.WARNING,
                    fact_type=fact_type,
                    source_id=source_id,
                    explanation=(
                        f"{len(fact_ids)} {fact_type} facts rely on one source "
                        f"{source_id!r}"
                    ),
                    remediation=(
                        "Add independent corroborating sources before treating this "
                        "fact group as robust real-market coverage."
                    ),
                    blocks_real_data_trust=False,
                )
            )
        return findings

    def _check_low_confidence_concentration(
        self, links: list[FactSourceLink]
    ) -> list[ProvenanceAuditFinding]:
        findings: list[ProvenanceAuditFinding] = []
        by_fact_type: dict[str, list[FactSourceLink]] = defaultdict(list)
        for link in links:
            by_fact_type[link.fact_type].append(link)
        for fact_type, rows in by_fact_type.items():
            total = len({row.fact_id for row in rows})
            low_fact_ids = {
                row.fact_id for row in rows if row.confidence in _LOW_CONFIDENCE_VALUES
            }
            if total < self._low_confidence_fact_threshold or not low_fact_ids:
                continue
            ratio = len(low_fact_ids) / total
            if ratio < self._low_confidence_warning_ratio:
                continue
            severity = (
                ProvenanceAuditSeverity.ERROR
                if ratio >= self._low_confidence_error_ratio
                else ProvenanceAuditSeverity.WARNING
            )
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=f"provenance::low_confidence::{fact_type}",
                    code=ProvenanceAuditCode.LOW_CONFIDENCE_CONCENTRATION,
                    severity=severity,
                    fact_type=fact_type,
                    explanation=(
                        f"{len(low_fact_ids)}/{total} {fact_type} facts rely on "
                        f"low-confidence observations (ratio {ratio:.2f})"
                    ),
                    remediation=(
                        "Collect higher-confidence observations or mark the affected "
                        "facts low confidence before trusting this group."
                    ),
                    blocks_real_data_trust=severity is ProvenanceAuditSeverity.ERROR,
                )
            )
        return findings

    def _check_seed_real_mixture(
        self, links: list[FactSourceLink]
    ) -> list[ProvenanceAuditFinding]:
        findings: list[ProvenanceAuditFinding] = []
        by_fact: dict[tuple[str, str], list[FactSourceLink]] = defaultdict(list)
        for link in links:
            by_fact[(link.fact_type, link.fact_id)].append(link)
        for (fact_type, fact_id), rows in by_fact.items():
            origins = {DataOrigin(row.data_origin) for row in rows}
            if not (origins & DEMO_DATA_ORIGINS and origins & REAL_DATA_ORIGINS):
                continue
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=f"provenance::seed_real_mixed::{fact_type}::{fact_id}",
                    code=ProvenanceAuditCode.SEED_REAL_MIXED,
                    severity=ProvenanceAuditSeverity.CRITICAL,
                    fact_type=fact_type,
                    fact_id=fact_id,
                    explanation=(
                        f"{fact_type}:{fact_id} has both demo and real provenance "
                        "links"
                    ),
                    remediation=(
                        "Separate demo facts from real observed facts or remove demo "
                        "links from the real-market trust group."
                    ),
                    blocks_real_data_trust=True,
                )
            )
        return findings

    def _check_unknown_treated_as_zero(
        self,
        prepared_values: Iterable[PreparedValueAuditRecord],
    ) -> list[ProvenanceAuditFinding]:
        findings: list[ProvenanceAuditFinding] = []
        for record in prepared_values:
            if record.input_status not in _UNKNOWN_INPUT_STATUSES:
                continue
            output_is_zero = record.output_value == 0
            output_is_zero_observed = (
                record.output_status is ObservationStatus.ZERO_OBSERVED
            )
            if not output_is_zero and not output_is_zero_observed:
                continue
            field = record.field_name or "value"
            findings.append(
                ProvenanceAuditFinding(
                    finding_id=(
                        "provenance::unknown_zero::"
                        f"{record.fact_type.value}::{record.fact_id}::{field}"
                    ),
                    code=ProvenanceAuditCode.UNKNOWN_TREATED_AS_ZERO,
                    severity=ProvenanceAuditSeverity.ERROR,
                    fact_type=record.fact_type.value,
                    fact_id=record.fact_id,
                    explanation=(
                        f"{field} started as {record.input_status.value} but was "
                        "prepared as numeric zero or zero_observed"
                    ),
                    remediation=(
                        "Preserve unknown/not_collected/stale as null or a non-zero "
                        "status until an observed zero basis exists."
                    ),
                    blocks_real_data_trust=True,
                )
            )
        return findings


def _score_source_fact_type_for(
    link: FactSourceLink,
    score_input_fact_types: Mapping[str, ProvenanceFactType | str],
) -> ProvenanceFactType | str | None:
    return score_input_fact_types.get(link.link_id) or score_input_fact_types.get(
        link.fact_id
    )


def _summary_by_code(findings: list[ProvenanceAuditFinding]) -> dict[str, int]:
    counter = Counter(finding.code.value for finding in findings)
    return {code.value: counter.get(code.value, 0) for code in ProvenanceAuditCode}


def _summary_by_severity(findings: list[ProvenanceAuditFinding]) -> dict[str, int]:
    counter = Counter(finding.severity.value for finding in findings)
    return {
        severity.value: counter.get(severity.value, 0)
        for severity in ProvenanceAuditSeverity
    }
