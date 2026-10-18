"""Layer 31C post-import trust, scoring, and output refresh."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.scoring import compute_entry_level_access_score
from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.imports.provenance import (
    ALLOWED_LICENSE_OR_TERMS_CATEGORIES,
    ALLOWED_SOURCE_TYPES,
    IMPORT_STALENESS_DAYS,
)
from backend.imports.result import (
    CuratedImportDiagnostic,
    CuratedMarketPostImportResult,
    CuratedTrustLabel,
    ImportWriteCounts,
    empty_post_import_counts,
)
from backend.imports.service import (
    _entry_level_id,
    _hiring_groups,
    _hiring_id,
    _load_dataset,
    _presence_id,
    _resolve_dataset_and_validate,
)
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.provenance.models import FactSourceLink
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.shared.versioning import next_version
from backend.trust.explanations import TrustExplanationService
from backend.trust.repository import TrustAssessmentRepository
from backend.trust.risk import RiskRoutingService
from backend.trust.schemas import TrustAssessmentSubjectType, TrustSubjectMetadata
from backend.trust.service import TrustAssessmentService

_Outcome = Literal["created", "updated", "unchanged", "skipped", "failed"]

_SUBJECT_TYPE_BY_FACT_TYPE: dict[FactBindingType, TrustAssessmentSubjectType] = {
    FactBindingType.COMPANY: TrustAssessmentSubjectType.COMPANY_FACT,
    FactBindingType.REGION: TrustAssessmentSubjectType.REGION_FACT,
    FactBindingType.COMPANY_REGION_PRESENCE: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
    FactBindingType.COMPANY_REGION_HIRING: TrustAssessmentSubjectType.DATA_STANDARD_FACT,
    FactBindingType.COMPANY_REGION_ENTRY_LEVEL: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
}

_MODEL_BY_FACT_TYPE = {
    FactBindingType.COMPANY: Company,
    FactBindingType.REGION: Region,
    FactBindingType.COMPANY_REGION_PRESENCE: CompanyRegionPresence,
    FactBindingType.COMPANY_REGION_HIRING: CompanyRegionHiring,
    FactBindingType.COMPANY_REGION_ENTRY_LEVEL: CompanyRegionEntryLevel,
}

_OBSERVED_COUNT_STATUSES = {
    ObservationStatus.ZERO_OBSERVED.value,
    ObservationStatus.POSITIVE_OBSERVED.value,
}
_BLOCKING_UNKNOWN_STATUSES = {
    ObservationStatus.UNKNOWN.value,
    ObservationStatus.NOT_COLLECTED.value,
}


@dataclass(frozen=True, slots=True)
class _ImportedFact:
    fact_type: FactBindingType
    fact_id: str
    region_id: str | None = None

    @property
    def subject_type(self) -> TrustAssessmentSubjectType:
        return _SUBJECT_TYPE_BY_FACT_TYPE[self.fact_type]


@dataclass(frozen=True, slots=True)
class _TrustEvaluation:
    fact: _ImportedFact
    metadata: TrustSubjectMetadata
    source_backed: bool
    data_origin: str
    demonstration_data: bool


def run_curated_market_post_import(
    session: Session,
    market_key_or_dataset_dir: str | Path,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
    comparison_region_ids: Sequence[str] = (),
) -> CuratedMarketPostImportResult:
    """Refresh trust, scores, and outputs for an imported curated dataset."""

    dataset_path, validation = _resolve_dataset_and_validate(
        market_key_or_dataset_dir,
        registry_path=registry_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )
    if not validation.ok:
        return CuratedMarketPostImportResult(
            ok=False,
            status="validation_failed",
            dataset_path=str(dataset_path),
            validation=validation,
            counts=empty_post_import_counts(),
        )

    now = _coerce_now(as_of)
    counts = _mutable_counts()
    diagnostics: list[CuratedImportDiagnostic] = []
    labels: list[CuratedTrustLabel] = []

    try:
        dataset = _load_dataset(dataset_path)
        facts = _imported_facts(dataset)
        missing = _missing_canonical_facts(session, facts)
        if missing:
            return CuratedMarketPostImportResult(
                ok=False,
                status="canonical_records_missing",
                dataset_path=str(dataset_path),
                validation=validation,
                counts=_freeze_counts(counts),
                diagnostics=tuple(missing),
            )

        with session.begin_nested():
            evaluations = _evaluate_trust_and_risk(
                session,
                facts,
                now=now,
                counts=counts,
            )
            session.flush()
            labels.extend(_trust_labels(evaluations, session=session))
            _recompute_entry_level_scores(session, facts, counts=counts)
            _recompute_region_scores(session, facts, counts=counts)
            _rebuild_outputs(
                session,
                dataset,
                now=now,
                comparison_region_ids=comparison_region_ids,
                counts=counts,
                diagnostics=diagnostics,
            )
    except Exception as exc:
        return CuratedMarketPostImportResult(
            ok=False,
            status="failed",
            dataset_path=str(dataset_path),
            validation=validation,
            counts=_freeze_counts(counts),
            trust_labels=tuple(labels),
            diagnostics=(
                CuratedImportDiagnostic(
                    code="post_import_refresh_failed",
                    message=str(exc),
                    stage="post_import_refresh",
                ),
            ),
        )

    return CuratedMarketPostImportResult(
        ok=True,
        status="refreshed",
        dataset_path=str(dataset_path),
        validation=validation,
        counts=_freeze_counts(counts),
        trust_labels=tuple(labels),
        diagnostics=tuple(diagnostics),
    )


def _imported_facts(dataset) -> tuple[_ImportedFact, ...]:
    facts: list[_ImportedFact] = []
    for region in sorted(dataset.regions, key=lambda item: item["region_id"]):
        facts.append(
            _ImportedFact(
                fact_type=FactBindingType.REGION,
                fact_id=region["region_id"],
                region_id=region["region_id"],
            )
        )
    for company in sorted(dataset.companies, key=lambda item: item["company_id"]):
        facts.append(
            _ImportedFact(
                fact_type=FactBindingType.COMPANY,
                fact_id=company["company_id"],
            )
        )
    for presence in sorted(
        dataset.presence,
        key=lambda item: (item["region_id"], item["company_id"]),
    ):
        facts.append(
            _ImportedFact(
                fact_type=FactBindingType.COMPANY_REGION_PRESENCE,
                fact_id=_presence_id(presence["company_id"], presence["region_id"]),
                region_id=presence["region_id"],
            )
        )
    for group in _hiring_groups(dataset.hiring):
        facts.append(
            _ImportedFact(
                fact_type=FactBindingType.COMPANY_REGION_HIRING,
                fact_id=_hiring_id(group.company_id, group.region_id),
                region_id=group.region_id,
            )
        )
    for entry in sorted(
        dataset.entry_level,
        key=lambda item: (item["region_id"], item["company_id"]),
    ):
        facts.append(
            _ImportedFact(
                fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
                fact_id=_entry_level_id(entry["company_id"], entry["region_id"]),
                region_id=entry["region_id"],
            )
        )
    return tuple(facts)


def _missing_canonical_facts(
    session: Session,
    facts: Iterable[_ImportedFact],
) -> tuple[CuratedImportDiagnostic, ...]:
    diagnostics: list[CuratedImportDiagnostic] = []
    for fact in facts:
        model = _MODEL_BY_FACT_TYPE[fact.fact_type]
        if session.get(model, fact.fact_id) is None:
            diagnostics.append(
                CuratedImportDiagnostic(
                    code="missing_canonical_fact",
                    message=(
                        f"canonical {fact.fact_type.value} fact is missing: "
                        f"{fact.fact_id}"
                    ),
                    stage="post_import_preflight",
                )
            )
    return tuple(diagnostics)


def _evaluate_trust_and_risk(
    session: Session,
    facts: Iterable[_ImportedFact],
    *,
    now: datetime,
    counts: dict[str, dict[str, int]],
) -> tuple[_TrustEvaluation, ...]:
    trust_repo = TrustAssessmentRepository(session)
    trust_service = TrustAssessmentService(clock=lambda: now)
    risk_service = RiskRoutingService(clock=lambda: now)
    evaluations: list[_TrustEvaluation] = []

    for fact in facts:
        links = _fact_links(session, fact)
        data_origins = {link.data_origin for link in links if link.data_origin}
        demonstration_data = data_origins == {
            DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
        }
        data_origin = (
            next(iter(data_origins))
            if len(data_origins) == 1
            else "mixed" if data_origins else DataOrigin.UNKNOWN_ORIGIN.value
        )
        metadata = _trust_subject_metadata(fact, links)
        assessment = trust_service.assess(metadata)
        trust_id = _trust_assessment_id(fact)
        _, trust_outcome = trust_repo.upsert_assessment(
            assessment,
            trust_assessment_id=trust_id,
        )
        _record(counts, "trust_assessments", trust_outcome)

        routing = risk_service.decide(assessment, metadata)
        _, routing_outcome = trust_repo.upsert_routing_decision(
            routing,
            risk_routing_decision_id=_risk_routing_decision_id(fact),
            trust_assessment_id=trust_id,
        )
        _record(counts, "risk_routing_decisions", routing_outcome)
        evaluations.append(
            _TrustEvaluation(
                fact=fact,
                metadata=metadata,
                source_backed=bool(links),
                data_origin=data_origin,
                demonstration_data=demonstration_data,
            )
        )
    return tuple(evaluations)


def _fact_links(session: Session, fact: _ImportedFact) -> tuple[FactSourceLink, ...]:
    rows = session.execute(
        select(FactSourceLink)
        .where(
            FactSourceLink.fact_type == fact.fact_type.value,
            FactSourceLink.fact_id == fact.fact_id,
        )
        .order_by(FactSourceLink.source_id, FactSourceLink.link_id)
    ).scalars()
    return tuple(rows)


def _trust_subject_metadata(
    fact: _ImportedFact,
    links: tuple[FactSourceLink, ...],
) -> TrustSubjectMetadata:
    freshness = _aggregate_freshness(links)
    source_allowed = bool(links) and all(_link_source_allowed(link) for link in links)
    observation_date_valid = bool(links) and all(link.observed_at for link in links)
    confidence = _aggregate_confidence(links)
    independently_verified = (
        source_allowed
        and observation_date_valid
        and freshness == FreshnessStatus.FRESH.value
        and confidence in {"high", "medium"}
    )
    warnings = ["curated_import_source_backed"] if links else ["curated_import_unsourced"]
    if freshness == FreshnessStatus.STALE.value:
        warnings.append("curated_import_source_stale")
    return TrustSubjectMetadata(
        subject_type=fact.subject_type,
        subject_id=fact.fact_id,
        valid_fields=True,
        source_count=len(links),
        source_present=bool(links),
        source_allowed=source_allowed,
        freshness_status=freshness,
        observation_date_valid=observation_date_valid,
        confidence_label=confidence,
        duplicate_detected=False,
        conflict_detected=False,
        independent_verification=independently_verified,
        self_promotional=False,
        corroboration_count=None,
        claim_type_allowed=True,
        ranking_influence_allowed=False,
        stale=freshness == FreshnessStatus.STALE.value,
        verification_status="verified" if independently_verified else None,
        quality_label="public_source_verified" if independently_verified else None,
        trust_label="verified" if independently_verified else None,
        warnings=tuple(warnings),
        metadata={
            "import_layer": "31C",
            "imported_data": True,
            "source_backed": bool(links),
            "fact_type": fact.fact_type.value,
        },
    )


def _link_source_allowed(link: FactSourceLink) -> bool:
    try:
        source_type = SourceType(link.source_type)
        license_category = LicenseTermsCategory(link.license_or_terms_category)
    except ValueError:
        return False
    return (
        source_type in ALLOWED_SOURCE_TYPES
        and license_category in ALLOWED_LICENSE_OR_TERMS_CATEGORIES
    )


def _aggregate_freshness(links: tuple[FactSourceLink, ...]) -> str:
    if not links:
        return FreshnessStatus.UNKNOWN.value
    statuses = {link.freshness_status for link in links if link.freshness_status}
    if FreshnessStatus.STALE.value in statuses:
        return FreshnessStatus.STALE.value
    if statuses == {FreshnessStatus.FRESH.value}:
        return FreshnessStatus.FRESH.value
    return FreshnessStatus.UNKNOWN.value


def _aggregate_confidence(links: tuple[FactSourceLink, ...]) -> str:
    if not links:
        return "unknown"
    values = {link.confidence for link in links if link.confidence}
    if "low" in values:
        return "low"
    if values == {"high"}:
        return "high"
    if "medium" in values:
        return "medium"
    return "unknown"


def _trust_labels(
    evaluations: Iterable[_TrustEvaluation],
    *,
    session: Session,
) -> tuple[CuratedTrustLabel, ...]:
    repo = TrustAssessmentRepository(session)
    explainer = TrustExplanationService()
    labels: list[CuratedTrustLabel] = []
    for evaluation in evaluations:
        fact = evaluation.fact
        assessment = repo.latest_for_subject(
            subject_type=fact.subject_type,
            subject_id=fact.fact_id,
        )
        routing = repo.latest_routing_for_subject(
            subject_type=fact.subject_type,
            subject_id=fact.fact_id,
        )
        explanation = explainer.explain(
            assessment=assessment,
            routing=routing,
            subject_type=fact.subject_type,
            subject_id=fact.fact_id,
        )
        labels.append(
            CuratedTrustLabel(
                subject_type=fact.subject_type.value,
                subject_id=fact.fact_id,
                trust_tier=explanation.trust_tier.value,
                trust_label=(
                    "Demonstration only"
                    if evaluation.demonstration_data
                    else explanation.trust_label
                ),
                freshness_label=(
                    (
                        "Demonstration snapshot (stale)"
                        if evaluation.metadata.freshness_status
                        == FreshnessStatus.STALE.value
                        else "Demonstration snapshot"
                    )
                    if evaluation.demonstration_data
                    else _freshness_label(evaluation.metadata.freshness_status)
                ),
                risk_label=explanation.risk_label,
                ranking_influence_label=(
                    "Demo ranking only"
                    if evaluation.demonstration_data
                    and explanation.ranking_influence_allowed
                    else explanation.ranking_influence_label
                ),
                ranking_influence_allowed=explanation.ranking_influence_allowed,
                imported_data=True,
                source_backed=evaluation.source_backed,
                data_origin=evaluation.data_origin,
                demonstration_data=evaluation.demonstration_data,
            )
        )
    return tuple(labels)


def _recompute_entry_level_scores(
    session: Session,
    facts: Iterable[_ImportedFact],
    *,
    counts: dict[str, dict[str, int]],
) -> None:
    entry_ids = [
        fact.fact_id
        for fact in facts
        if fact.fact_type is FactBindingType.COMPANY_REGION_ENTRY_LEVEL
    ]
    eligible_ids = ranking_eligible_fact_ids(
        session,
        FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value,
        entry_ids,
        allow_legacy_unassessed=False,
    )
    rows = session.execute(
        select(CompanyRegionEntryLevel)
        .where(CompanyRegionEntryLevel.entry_level_id.in_(entry_ids))
        .order_by(CompanyRegionEntryLevel.entry_level_id)
    ).scalars()
    for row in rows:
        if row.entry_level_id not in eligible_ids:
            _record(counts, "entry_level_scores", "skipped")
            continue
        score, confidence = _status_aware_entry_level_score(row)
        if (
            row.entry_level_access_score == score
            and row.entry_level_confidence == confidence.value
        ):
            _record(counts, "entry_level_scores", "unchanged")
            continue
        row.entry_level_access_score = score
        row.entry_level_confidence = confidence.value
        row.version = next_version(row.version)
        _record(counts, "entry_level_scores", "updated")
    session.flush()


def _status_aware_entry_level_score(
    row: CompanyRegionEntryLevel,
) -> tuple[float | None, EntryLevelConfidence]:
    statuses = (
        row.internship_count_status,
        row.coop_count_status,
        row.entry_level_full_time_count_status,
    )
    if any(status in _BLOCKING_UNKNOWN_STATUSES for status in statuses):
        return None, EntryLevelConfidence.UNKNOWN

    recurrence = (
        StudentSeasonRecurrenceSignal(row.student_season_recurrence_signal)
        if row.student_season_recurrence_signal
        else None
    )
    result = compute_entry_level_access_score(
        internship_count=(
            row.internship_count
            if row.internship_count_status in _OBSERVED_COUNT_STATUSES
            else None
        ),
        coop_count=(
            row.coop_count if row.coop_count_status in _OBSERVED_COUNT_STATUSES else None
        ),
        entry_level_full_time_count=(
            row.entry_level_full_time_count
            if row.entry_level_full_time_count_status in _OBSERVED_COUNT_STATUSES
            else None
        ),
        formal_early_career_program_flag=row.formal_early_career_program_flag,
        student_season_recurrence_signal=recurrence,
    )
    return result.score, result.confidence


def _recompute_region_scores(
    session: Session,
    facts: Iterable[_ImportedFact],
    *,
    counts: dict[str, dict[str, int]],
) -> None:
    region_ids = sorted(
        {
            fact.region_id
            for fact in facts
            if fact.fact_type is FactBindingType.REGION and fact.region_id is not None
        }
    )
    eligible_ids = ranking_eligible_fact_ids(
        session,
        FactBindingType.REGION.value,
        region_ids,
        allow_legacy_unassessed=False,
    )
    scorer = RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    )
    for region_id in region_ids:
        if region_id not in eligible_ids:
            _record(counts, "region_scores", "skipped")
            continue
        _, outcome = scorer.upsert_for_recompute(region_id)
        _record(counts, "region_scores", outcome)


def _rebuild_outputs(
    session: Session,
    dataset,
    *,
    now: datetime,
    comparison_region_ids: Sequence[str],
    counts: dict[str, dict[str, int]],
    diagnostics: list[CuratedImportDiagnostic],
) -> None:
    output_service = _output_service(session)

    def now_fn() -> datetime:
        return now

    region_ids = sorted(region["region_id"] for region in dataset.regions)
    company_ids = sorted(company["company_id"] for company in dataset.companies)

    for region_id in region_ids:
        _, _, outcome = output_service.build_region(region_id, now=now_fn)
        _record(counts, "region_outputs", outcome)
    for company_id in company_ids:
        _, _, outcome = output_service.build_company(company_id, now=now_fn)
        _record(counts, "company_outputs", outcome)
    for region_id in region_ids:
        for peer_id in sorted(set(comparison_region_ids)):
            if peer_id == region_id:
                _record(counts, "comparison_outputs", "skipped")
                continue
            try:
                _, _, outcome = output_service.build_comparison(
                    region_id,
                    peer_id,
                    now=now_fn,
                )
            except Exception as exc:
                _record(counts, "comparison_outputs", "failed")
                diagnostics.append(
                    CuratedImportDiagnostic(
                        code="warning_comparison_output_skipped",
                        message=str(exc),
                        stage="output_rebuild",
                    )
                )
                continue
            _record(counts, "comparison_outputs", outcome)


def _output_service(session: Session) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _coerce_now(value: date | datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _freshness_label(value: str | None) -> str:
    if value == FreshnessStatus.FRESH.value:
        return "Fresh"
    if value == FreshnessStatus.STALE.value:
        return "Stale source"
    return "Freshness unknown"


def _trust_assessment_id(fact: _ImportedFact) -> str:
    return f"l31c_trust_{_digest(f'{fact.subject_type.value}:{fact.fact_id}')}"


def _risk_routing_decision_id(fact: _ImportedFact) -> str:
    return f"l31c_risk_{_digest(f'{fact.subject_type.value}:{fact.fact_id}')}"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def _mutable_counts() -> dict[str, dict[str, int]]:
    return {
        key: {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "failed": 0}
        for key in empty_post_import_counts()
    }


def _record(counts: dict[str, dict[str, int]], key: str, outcome: _Outcome) -> None:
    counts[key][outcome] += 1


def _freeze_counts(counts: dict[str, dict[str, int]]) -> dict[str, ImportWriteCounts]:
    return {
        key: ImportWriteCounts(
            created=value["created"],
            updated=value["updated"],
            unchanged=value["unchanged"],
            skipped=value["skipped"],
            failed=value["failed"],
        )
        for key, value in counts.items()
    }
