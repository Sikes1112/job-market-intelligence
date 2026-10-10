"""Service layer for Layer 38A production-current opportunities."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import select

from backend.career_decisions.models import CareerDecision, DecisionOption
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.companies.models import Company
from backend.current_opportunities.adapters import OpportunityAcquisitionAdapter
from backend.current_opportunities.identity import (
    canonical_identity_keys_for_row,
    evidence_id,
    link_id,
    resolve_current_opportunity_identity,
    source_identity_key,
)
from backend.current_opportunities.models import (
    CurrentOpportunity,
    CurrentOpportunityIdentityEvidence,
    CurrentOpportunitySourceLink,
    OpportunityAcquisitionRun,
    OpportunityCoverageContract,
    OpportunityDataSource,
    OpportunityPromotionReceipt,
    OpportunitySourceObservation,
)
from backend.current_opportunities.normalization import normalize_opportunity_payload
from backend.current_opportunities.pursuit_scope import (
    PursuitOpportunityScope,
    PursuitOpportunityScopeError,
    pursuit_opportunity_scope,
)
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    AcquisitionRecordStatus,
    AcquisitionRunStatus,
    AllowedUseClassification,
    ConfidenceLevel,
    CoveragePayload,
    CoverageStatus,
    CurrentOpportunityPayload,
    DiagnosticPayload,
    DiagnosticSeverity,
    FreshnessState,
    IdentityResolutionStatus,
    LicenseTermsClassification,
    LocationResolutionStatus,
    NormalizationStatus,
    NormalizedOpportunity,
    OpportunityCoverageInput,
    OpportunityMatchPayload,
    OpportunityStatus,
    RefreshRunPayload,
    RetryClassification,
    SourceOperationalStatus,
    SourceRegistryInput,
    SourceTrustClassification,
)
from backend.deep_decisions.models import StrategicCareerReview
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver


class CurrentOpportunityError(ValueError):
    pass


class OpportunitySourceNotFound(KeyError):
    pass


class CurrentOpportunityNotFound(KeyError):
    pass


MAX_OPPORTUNITY_LIST_CANDIDATES = 10000
OPPORTUNITY_LIST_SCAN_WINDOW = 500
OPPORTUNITY_LIST_MIN_SCAN_WINDOW = 100


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _opportunity_list_scan_window(*, limit: int, offset: int) -> int:
    requested_span = max(limit, offset + limit)
    return min(
        MAX_OPPORTUNITY_LIST_CANDIDATES,
        max(OPPORTUNITY_LIST_MIN_SCAN_WINDOW, min(OPPORTUNITY_LIST_SCAN_WINDOW, requested_span)),
    )


@dataclass(frozen=True, slots=True)
class RefreshSourcesResult:
    runs: tuple[RefreshRunPayload, ...]


class CurrentOpportunityService:
    def __init__(self, repository: CurrentOpportunityRepository) -> None:
        self._repo = repository

    def upsert_source(self, request: SourceRegistryInput) -> OpportunityDataSource:
        existing = self._repo.get_source(request.source_id)
        resolver = GeographicResolver(RegionRepository(self._repo.session))
        supported_markets = []
        for value in request.supported_markets:
            resolution = resolver.resolve(value) if value != "*" else None
            supported_markets.append(
                resolution.region_id if resolution is not None and resolution.resolved else value
            )
        supported_markets = list(dict.fromkeys(supported_markets))
        values = {
            "provider": request.provider,
            "display_name": request.display_name,
            "source_type": request.source_type.value,
            "acquisition_method": request.acquisition_method.value,
            "enabled": request.enabled,
            "allowed_use": request.allowed_use.value,
            "license_terms": request.license_terms.value,
            "trust_classification": request.trust.value,
            "freshness_sla_hours": request.freshness_sla_hours,
            "supported_domains": list(request.supported_domains),
            "supported_markets": supported_markets,
            "supported_opportunity_types": [
                item.value for item in request.supported_opportunity_types
            ],
            "retention_classification": request.retention_classification,
            "ranking_use_allowed": request.ranking_use_allowed,
            "display_use_allowed": request.display_use_allowed,
            "refresh_config": dict(request.refresh_config),
            "provenance_requirements": list(request.provenance_requirements),
            "operational_status": request.operational_status.value,
        }
        if existing is None:
            row = OpportunityDataSource(source_id=request.source_id, **values)
            self._repo.add(row)
            self._repo.flush()
            return row
        for key, value in values.items():
            setattr(existing, key, value)
        self._repo.flush()
        return existing

    def upsert_coverage(self, request: OpportunityCoverageInput) -> OpportunityCoverageContract:
        resolver = GeographicResolver(RegionRepository(self._repo.session))
        market_id_resolution = (
            resolver.resolve(request.market_id) if request.market_id is not None else None
        )
        market_key_resolution = (
            resolver.resolve(request.market_key) if request.market_key != "*" else None
        )
        canonical_market_id = (
            market_id_resolution.region_id
            if market_id_resolution is not None and market_id_resolution.resolved
            else (
                market_key_resolution.region_id
                if request.market_id is None
                and market_key_resolution is not None
                and market_key_resolution.resolved
                else None
            )
        )
        if request.market_id is not None and canonical_market_id is None:
            raise CurrentOpportunityError(
                f"coverage market_id does not resolve canonically: {request.market_id!r}"
            )
        opportunity_type = (
            request.opportunity_type.value
            if hasattr(request.opportunity_type, "value")
            else str(request.opportunity_type)
        )
        canonical_market_key = (
            market_key_resolution.region_id
            if market_key_resolution is not None and market_key_resolution.resolved
            else request.market_key
        )
        row = self._repo.get_coverage(
            market_key=canonical_market_key,
            role_family=request.role_family,
            opportunity_type=opportunity_type,
        )
        values = {
            "market_key": canonical_market_key,
            "market_id": canonical_market_id,
            "market_label": request.market_label,
            "role_family": request.role_family,
            "opportunity_type": opportunity_type,
            "status": request.status.value,
            "rationale": request.rationale,
            "source_basis": dict(request.source_basis),
            "minimum_expected_sources": request.minimum_expected_sources,
            "freshness_max_age_hours": request.freshness_max_age_hours,
            "last_evaluated_at": request.last_evaluated_at,
            "operator_override_status": (
                request.operator_override_status.value
                if request.operator_override_status is not None
                else None
            ),
        }
        if row is None:
            row = OpportunityCoverageContract(coverage_id=request.coverage_id, **values)
            self._repo.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self._repo.flush()
        return row

    def refresh_source(
        self,
        adapter: OpportunityAcquisitionAdapter,
        *,
        run_id: str | None = None,
        idempotency_key: str | None = None,
        trigger_type: str = "manual",
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> RefreshRunPayload:
        source = self._repo.get_source(adapter.source_id)
        if source is None:
            raise OpportunitySourceNotFound(adapter.source_id)
        started_at = now or _utc_now()
        run_id = run_id or _stable_id("opp_run", adapter.source_id, started_at.isoformat())
        idempotency_key = idempotency_key or f"{adapter.source_id}:{run_id}"
        existing_run = self._repo.get_run_by_idempotency_key(idempotency_key)
        if existing_run is not None:
            return self._run_payload(existing_run)

        run = OpportunityAcquisitionRun(
            run_id=run_id,
            source_id=source.source_id,
            idempotency_key=idempotency_key,
            status=AcquisitionRunStatus.RUNNING.value,
            trigger_type=trigger_type,
            requested_by=requested_by,
            started_at=started_at,
            retry_classification=RetryClassification.NONE.value,
            failure_details={},
            warnings=[],
        )
        self._repo.add(run)
        self._repo.flush()

        governance_issue = _source_governance_issue(source, for_refresh=True)
        if governance_issue is not None:
            run.status = AcquisitionRunStatus.REJECTED.value
            run.completed_at = started_at
            run.failure_details = {"reason": governance_issue}
            run.rejected_count = 1
            self._repo.flush()
            return self._run_payload(run)

        try:
            result = adapter.acquire(
                run_id=run.run_id,
                checkpoint=source.refresh_config.get("checkpoint")
                if isinstance(source.refresh_config, dict)
                else None,
            )
        except Exception as exc:
            run.status = AcquisitionRunStatus.FAILED.value
            run.completed_at = _utc_now()
            run.retry_classification = RetryClassification.RETRYABLE.value
            run.failure_count = 1
            run.failure_details = {
                "error": type(exc).__name__,
                "message": str(exc),
            }
            run.next_retry_at = run.completed_at + _bounded_backoff(run.retry_count)
            self._repo.flush()
            return self._run_payload(run)

        warnings = list(result.warnings)
        counts = {
            "acquired": len(result.records),
            "normalized": 0,
            "promoted": 0,
            "duplicates": 0,
            "rejected": 0,
            "failures": 0,
            "created": 0,
            "updated": 0,
            "closed": 0,
        }
        diff_events: list[dict[str, Any]] = []
        semantic_warnings: list[str] = []

        try:
            with self._repo.session.begin_nested():
                context = _NormalizationContext.from_session(self._repo.session)
                for record in result.records:
                    event = self._process_record(
                        source,
                        run,
                        record,
                        context,
                        semantic_warnings,
                    )
                    diff_events.append(event)
                    counts[event["count_bucket"]] += 1
                    if event.get("normalized"):
                        counts["normalized"] += 1
                    if event.get("promoted"):
                        counts["promoted"] += 1
                    if event.get("warning"):
                        warnings.append(str(event["warning"]))
                self._repo.add(
                    OpportunityPromotionReceipt(
                        promotion_receipt_id=_stable_id("opp_promo", run.run_id),
                        run_id=run.run_id,
                        source_id=source.source_id,
                        status=result.status.value,
                        diff_summary={"changes": diff_events},
                        semantic_warnings=semantic_warnings,
                        promoted_count=counts["promoted"],
                        duplicate_count=counts["duplicates"],
                        rejected_count=counts["rejected"],
                        created_count=counts["created"],
                        updated_count=counts["updated"],
                        closed_count=counts["closed"],
                    )
                )
        except Exception as exc:
            run.status = AcquisitionRunStatus.FAILED.value
            run.completed_at = _utc_now()
            run.retry_classification = RetryClassification.TERMINAL.value
            run.failure_count = 1
            run.failure_details = {
                "stage": "promotion",
                "error": type(exc).__name__,
                "message": str(exc),
            }
            self._repo.flush()
            return self._run_payload(run)

        run.status = _run_status(result.status, counts["failures"])
        run.completed_at = _utc_now()
        run.cursor = result.cursor
        run.checkpoint = dict(result.checkpoint)
        run.retry_classification = result.retry_classification.value
        run.acquired_count = counts["acquired"]
        run.normalized_count = counts["normalized"]
        run.promoted_count = counts["promoted"]
        run.duplicate_count = counts["duplicates"]
        run.rejected_count = counts["rejected"]
        run.warning_count = len(warnings) + len(semantic_warnings)
        run.failure_count = counts["failures"]
        run.failure_details = dict(result.failure_details)
        run.warnings = warnings + semantic_warnings
        if result.retry_classification is RetryClassification.RETRYABLE:
            run.next_retry_at = run.completed_at + _bounded_backoff(run.retry_count)
        self._repo.flush()
        return self._run_payload(run)

    def refresh_sources(
        self,
        adapters: tuple[OpportunityAcquisitionAdapter, ...],
        *,
        now: datetime | None = None,
    ) -> RefreshSourcesResult:
        runs: list[RefreshRunPayload] = []
        for adapter in adapters:
            try:
                runs.append(self.refresh_source(adapter, now=now))
            except OpportunitySourceNotFound:
                continue
        return RefreshSourcesResult(runs=tuple(runs))

    def list_opportunities(
        self,
        *,
        market: str | None = None,
        role_family: str | None = None,
        opportunity_type: str | None = None,
        work_arrangement: str | None = None,
        include_ineligible: bool = False,
        limit: int = 100,
        offset: int = 0,
        now: datetime | None = None,
    ) -> tuple[CurrentOpportunityPayload, ...]:
        if market is not None:
            resolution = GeographicResolver(RegionRepository(self._repo.session)).resolve(market)
            if not resolution.resolved:
                return ()
            market = resolution.region_id
        coverage_rows = _coverage_rows_by_market(self._repo.list_coverage_contracts())
        selected: list[CurrentOpportunityPayload] = []
        visible_seen = 0
        scanned = 0
        candidate_offset = 0
        window_size = _opportunity_list_scan_window(limit=limit, offset=offset)
        now_value = now or _utc_now()

        while scanned < MAX_OPPORTUNITY_LIST_CANDIDATES and len(selected) < limit:
            candidate_limit = min(window_size, MAX_OPPORTUNITY_LIST_CANDIDATES - scanned)
            rows = self._repo.list_opportunities(
                market=market,
                role_family=role_family,
                opportunity_type=opportunity_type,
                work_arrangement=work_arrangement,
                ranking_eligible=None if include_ineligible else True,
                status=None if include_ineligible else OpportunityStatus.ACTIVE.value,
                limit=candidate_limit,
                offset=candidate_offset,
            )
            if not rows:
                break

            scanned += len(rows)
            candidate_offset += len(rows)
            chunk_payloads, visible_seen = self._visible_opportunity_payloads(
                rows,
                offset=offset,
                limit=limit - len(selected),
                visible_seen=visible_seen,
                now=now_value,
                coverage_rows=coverage_rows,
            )
            selected.extend(chunk_payloads)

            if len(rows) < candidate_limit:
                break

        return tuple(selected)

    def _list_opportunity_context(
        self,
        rows: list[CurrentOpportunity],
    ) -> tuple[
        dict[str, list[CurrentOpportunitySourceLink]],
        dict[str, list[CurrentOpportunitySourceLink]],
        dict[str, OpportunityDataSource],
        dict[str, dict[str, str | None]],
    ]:
        row_ids = [row.current_opportunity_id for row in rows]
        active_links_by_row = self._repo.list_source_links_for_opportunities(
            row_ids, active_only=True
        )
        all_links_by_row = self._repo.list_source_links_for_opportunities(row_ids)
        source_ids: set[str] = set()
        for link_group in active_links_by_row.values():
            source_ids.update(link.source_id for link in link_group)
        for link_group in all_links_by_row.values():
            source_ids.update(link.source_id for link in link_group)
        return (
            active_links_by_row,
            all_links_by_row,
            self._repo.list_sources_by_ids(source_ids),
            RegionRepository(self._repo.session).current_output_identities(
                {row.market_id for row in rows if row.market_id is not None}
            ),
        )

    def _visible_opportunity_payloads(
        self,
        rows: list[CurrentOpportunity],
        *,
        offset: int,
        limit: int,
        visible_seen: int,
        now: datetime,
        coverage_rows: Mapping[tuple[str, str, str], OpportunityCoverageContract],
    ) -> tuple[list[CurrentOpportunityPayload], int]:
        (
            active_links_by_row,
            all_links_by_row,
            source_rows,
            market_identities,
        ) = self._list_opportunity_context(rows)
        selected: list[CurrentOpportunityPayload] = []
        for row in rows:
            if not _row_display_allowed(
                self._repo,
                row,
                active_links=active_links_by_row.get(row.current_opportunity_id, []),
                source_rows=source_rows,
            ):
                continue
            if visible_seen >= offset:
                selected.append(
                    self._opportunity_payload(
                        row,
                        now=now,
                        active_links=active_links_by_row.get(row.current_opportunity_id, []),
                        links=all_links_by_row.get(row.current_opportunity_id, []),
                        source_rows=source_rows,
                        coverage_rows=coverage_rows,
                        market_identities=market_identities,
                    )
                )
                if len(selected) >= limit:
                    break
            visible_seen += 1
        return selected, visible_seen

    def get_opportunity(
        self,
        opportunity_id: str,
        *,
        now: datetime | None = None,
        require_display: bool = False,
    ) -> CurrentOpportunityPayload:
        row = self._repo.get_opportunity(opportunity_id)
        if row is None or (require_display and not _row_display_allowed(self._repo, row)):
            raise CurrentOpportunityNotFound(opportunity_id)
        return self._opportunity_payload(row, now=now)

    def authorize_geography_correction(
        self,
        identity_evidence_id: str,
        *,
        corrected_region: str,
        reason: str,
        operator_id: str,
        reviewed_at: datetime | None = None,
    ) -> CurrentOpportunity:
        """Approve one recorded resolved-A → resolved-B geography conflict."""

        evidence = self._repo.get_identity_evidence(identity_evidence_id)
        if evidence is None:
            raise CurrentOpportunityNotFound(identity_evidence_id)
        if evidence.geography_review_status == "approved":
            raise CurrentOpportunityError("geography conflict has already been approved")
        candidate_region_id = evidence.geography_candidate_region_id
        previous_region_id = evidence.geography_previous_region_id
        if candidate_region_id is None or previous_region_id is None:
            conflict_warning = next(
                (
                    warning
                    for warning in evidence.warnings
                    if warning.startswith("resolved_geography_conflict:")
                ),
                None,
            )
            if conflict_warning is None:
                raise CurrentOpportunityError(
                    "identity evidence is not a resolved geography conflict"
                )
            _prefix, previous_region_id, candidate_region_id = conflict_warning.split(":", 2)

        resolution = GeographicResolver(RegionRepository(self._repo.session)).require(
            corrected_region
        )
        assert resolution.region_id is not None
        if resolution.region_id != candidate_region_id:
            raise CurrentOpportunityError(
                "authorized correction must match the conflict candidate Region"
            )
        opportunity = self._repo.get_opportunity(evidence.current_opportunity_id)
        if opportunity is None:
            raise CurrentOpportunityNotFound(evidence.current_opportunity_id)
        if opportunity.market_id != previous_region_id:
            raise CurrentOpportunityError(
                "geography conflict is stale because canonical Region has changed"
            )

        identity_key, duplicate_key = canonical_identity_keys_for_row(
            opportunity,
            market_id=resolution.region_id,
            provider_record_id=evidence.provider_record_id,
        )
        identity_owner = self._repo.get_opportunity_by_identity_key(identity_key)
        if identity_owner is not None and identity_owner is not opportunity:
            raise CurrentOpportunityError(
                "corrected geography would collide with another canonical opportunity"
            )

        now = reviewed_at or _utc_now()
        opportunity.market_id = resolution.region_id
        opportunity.market_label = resolution.display_name
        opportunity.location_resolution_status = LocationResolutionStatus.RESOLVED.value
        opportunity.location_resolution_source = "authorized_correction"
        opportunity.canonical_identity_key = identity_key
        opportunity.duplicate_group_key = duplicate_key
        opportunity.canonical_updated_at = now
        opportunity.warnings = _append_unique(
            opportunity.warnings,
            f"authorized_geography_correction:{previous_region_id}:{resolution.region_id}",
        )

        evidence.geography_review_status = "approved"
        evidence.geography_previous_region_id = previous_region_id
        evidence.geography_candidate_region_id = candidate_region_id
        evidence.geography_corrected_region_id = resolution.region_id
        evidence.geography_reviewed_by = operator_id
        evidence.geography_reviewed_at = now
        evidence.geography_review_reason = reason.strip()
        _recompute_opportunity_policy(self._repo, opportunity, now=now)
        self._repo.flush()
        return opportunity

    def pending_geography_conflicts(self, *, limit: int = 100) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "identity_evidence_id": evidence.identity_evidence_id,
                "opportunity_id": evidence.current_opportunity_id,
                "source_id": evidence.source_id,
                "provider_record_id": evidence.provider_record_id,
                "previous_region_id": evidence.geography_previous_region_id,
                "candidate_region_id": evidence.geography_candidate_region_id,
                "review_status": evidence.geography_review_status,
                "created_at": evidence.created_at.isoformat(),
            }
            for evidence in self._repo.list_pending_geography_conflicts(limit=limit)
        )

    def list_refresh_runs(
        self,
        *,
        source_id: str | None = None,
        limit: int = 100,
    ) -> tuple[RefreshRunPayload, ...]:
        return tuple(
            self._run_payload(row)
            for row in self._repo.latest_runs(source_id=source_id, limit=limit)
        )

    def strategic_matches(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        request_terms: tuple[str, ...] = (),
        limit: int = 20,
        now: datetime | None = None,
        include_ineligible: bool = True,
    ) -> tuple[OpportunityMatchPayload, ...]:
        scope = (
            self.pursuit_scope(user_id, decision_id, require_selected=False)
            if decision_id is not None
            else None
        )
        identity_terms = _career_identity_terms(self._repo.session, user_id)
        decision_terms = _decision_terms(self._repo.session, user_id, decision_id)
        strategy_terms = _strategy_terms(self._repo.session, user_id, decision_id)
        desired = identity_terms | decision_terms | strategy_terms
        desired.update(_tokens(" ".join(request_terms)))
        rows = self._repo.list_opportunities(
            market=scope.market_id if scope else None,
            role_family=(
                scope.role_families[0]
                if scope is not None and len(scope.role_families) == 1
                else None
            ),
            opportunity_type=(
                scope.opportunity_types[0]
                if scope is not None and len(scope.opportunity_types) == 1
                else None
            ),
            work_arrangement=(
                scope.work_arrangements[0]
                if scope is not None and len(scope.work_arrangements) == 1
                else None
            ),
            ranking_eligible=None if include_ineligible else True,
            limit=500,
        )
        matches: list[OpportunityMatchPayload] = []
        for row in rows:
            if scope is not None and not scope.allows(row):
                continue
            if not _row_display_allowed(self._repo, row):
                continue
            payload = self._opportunity_payload(row, now=now)
            score, factors = _score_match(payload, desired)
            if score <= 0 and payload.ranking_eligible:
                continue
            if not payload.ranking_eligible:
                score = min(score, 0.19)
            matches.append(
                OpportunityMatchPayload(
                    opportunity=payload,
                    match_score=round(score, 3),
                    strategic_relevance=_relevance(score, payload.ranking_eligible),
                    contributing_factors=tuple(factors),
                    warnings=payload.warnings,
                    limitations=(
                        *payload.coverage_limitations,
                        *payload.ranking_ineligible_reasons,
                    ),
                    ranking_eligible=payload.ranking_eligible,
                )
            )
        matches.sort(
            key=lambda item: (
                item.ranking_eligible,
                item.match_score,
                item.opportunity.last_observed_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        return tuple(matches[:limit])

    def pursuit_scope(
        self,
        user_id: str,
        decision_id: str,
        *,
        require_selected: bool = True,
    ) -> PursuitOpportunityScope:
        """Resolve one owned Decision's frozen selected-option opportunity scope."""

        decision = self._repo.session.get(CareerDecision, decision_id)
        if decision is None or decision.user_id != user_id:
            raise CurrentOpportunityNotFound(decision_id)
        if decision.selected_option_id is None:
            if not require_selected:
                return PursuitOpportunityScope()
            raise CurrentOpportunityError("pursuit does not have a selected option")
        selected = self._repo.session.get(DecisionOption, decision.selected_option_id)
        if selected is None:
            raise CurrentOpportunityError("pursuit selected option is unavailable")
        try:
            return pursuit_opportunity_scope(decision, selected)
        except PursuitOpportunityScopeError as exc:
            raise CurrentOpportunityError(str(exc)) from exc

    def coverage(
        self,
        *,
        market_key: str,
        role_family: str,
        opportunity_type: str,
        now: datetime | None = None,
    ) -> CoveragePayload:
        if market_key != "*":
            resolution = GeographicResolver(RegionRepository(self._repo.session)).resolve(
                market_key
            )
            if resolution.resolved and resolution.region_id is not None:
                market_key = resolution.region_id
        return _coverage_payload(
            self._repo.get_coverage(
                market_key=market_key,
                role_family=role_family,
                opportunity_type=opportunity_type,
            ),
            market_key=market_key,
            role_family=role_family,
            opportunity_type=opportunity_type,
            now=now or _utc_now(),
        )

    def diagnostics(self, *, now: datetime | None = None) -> tuple[DiagnosticPayload, ...]:
        now = now or _utc_now()
        diagnostics: list[DiagnosticPayload] = []
        sources = self._repo.list_sources()
        opportunities = self._repo.list_opportunities(limit=10000)
        last_observed_by_source: dict[str, datetime] = {}
        for row in opportunities:
            for link in self._repo.list_source_links(row.current_opportunity_id, active_only=True):
                if link.last_observed_at is None:
                    continue
                current = last_observed_by_source.get(link.source_id)
                if current is None or link.last_observed_at > current:
                    last_observed_by_source[link.source_id] = link.last_observed_at
        for source in sources:
            latest = self._repo.latest_runs(source_id=source.source_id, limit=3)
            last_observed_at = last_observed_by_source.get(source.source_id)
            source_age = _age_hours(last_observed_at, now) if last_observed_at else None
            latest_run_at = latest[0].completed_at or latest[0].started_at if latest else None
            if not source.enabled:
                diagnostics.append(
                    _diagnostic(
                        "disabled_source",
                        DiagnosticSeverity.WARNING,
                        f"Source {source.source_id} is disabled.",
                        {"source_id": source.source_id},
                        {"operational_status": source.operational_status},
                    )
                )
            if source_age is None or source_age > source.freshness_sla_hours:
                diagnostics.append(
                    _diagnostic(
                        "stale_source",
                        DiagnosticSeverity.WARNING,
                        f"Source {source.source_id} has stale or unknown observations.",
                        {"source_id": source.source_id},
                        {
                            "age_hours": source_age,
                            "sla_hours": source.freshness_sla_hours,
                            "last_observed_at": last_observed_at.isoformat()
                            if last_observed_at
                            else None,
                            "latest_run_at": latest_run_at.isoformat() if latest_run_at else None,
                        },
                    )
                )
            failed = [
                run
                for run in latest
                if run.status
                in {AcquisitionRunStatus.FAILED.value, AcquisitionRunStatus.PARTIAL_FAILURE.value}
            ]
            if failed:
                diagnostics.append(
                    _diagnostic(
                        "failed_refresh",
                        DiagnosticSeverity.WARNING,
                        f"Source {source.source_id} has failed refreshes.",
                        {"source_id": source.source_id},
                        {"failed_run_ids": [run.run_id for run in failed]},
                    )
                )
            if len(failed) >= 2:
                diagnostics.append(
                    _diagnostic(
                        "repeated_refresh_failures",
                        DiagnosticSeverity.BLOCKING,
                        f"Source {source.source_id} has repeated refresh failures.",
                        {"source_id": source.source_id},
                        {"failed_count": len(failed)},
                    )
                )
        if not sources:
            diagnostics.append(
                _diagnostic(
                    "missing_expected_sources",
                    DiagnosticSeverity.BLOCKING,
                    "No governed current-opportunity sources are configured.",
                    {"scope": "system"},
                    {},
                )
            )
        eligible = [row for row in opportunities if row.ranking_eligible]
        if opportunities and not eligible:
            diagnostics.append(
                _diagnostic(
                    "ranking_degradation_no_eligible_opportunities",
                    DiagnosticSeverity.BLOCKING,
                    "Canonical opportunities exist but none are ranking eligible.",
                    {"scope": "current_opportunities"},
                    {"canonical_count": len(opportunities)},
                )
            )
        concentration: dict[str, int] = {}
        for row in opportunities:
            for link in self._repo.list_source_links(row.current_opportunity_id, active_only=True):
                concentration[link.source_id] = concentration.get(link.source_id, 0) + 1
        if eligible and concentration:
            top_count = max(concentration.values())
            if top_count / max(1, sum(concentration.values())) > 0.8:
                diagnostics.append(
                    _diagnostic(
                        "source_concentration",
                        DiagnosticSeverity.WARNING,
                        "Current opportunity coverage is concentrated in one source.",
                        {"scope": "current_opportunities"},
                        {"source_counts": concentration},
                    )
                )
        for row in opportunities:
            if row.freshness_state == FreshnessState.STALE.value:
                diagnostics.append(
                    _diagnostic(
                        "stale_canonical_opportunity",
                        DiagnosticSeverity.WARNING,
                        f"Opportunity {row.current_opportunity_id} is stale.",
                        {"opportunity_id": row.current_opportunity_id},
                        {
                            "last_observed_at": row.last_observed_at.isoformat()
                            if row.last_observed_at
                            else None
                        },
                    )
                )
            coverage = self.coverage(
                market_key=row.market_id or "*",
                role_family=row.role_family,
                opportunity_type=row.opportunity_type,
                now=now,
            )
            if coverage.effective_status == CoverageStatus.UNSUPPORTED:
                diagnostics.append(
                    _diagnostic(
                        "unsupported_coverage",
                        DiagnosticSeverity.INFO,
                        "Coverage is explicitly unsupported; absence is not exhaustive.",
                        {
                            "market": row.market_id or row.market_label,
                            "role_family": row.role_family,
                            "opportunity_type": row.opportunity_type,
                        },
                        {},
                    )
                )
        covered_scopes = self._repo.list_coverage_contracts()
        for coverage in covered_scopes:
            if coverage.status in {CoverageStatus.LIMITED.value, CoverageStatus.EXPERIMENTAL.value}:
                diagnostics.append(
                    _diagnostic(
                        "low_coverage",
                        DiagnosticSeverity.WARNING,
                        "Coverage contract is not production-ready.",
                        {
                            "market_key": coverage.market_key,
                            "role_family": coverage.role_family,
                            "opportunity_type": coverage.opportunity_type,
                        },
                        {"status": coverage.status},
                    )
                )
            if coverage.status == CoverageStatus.UNSUPPORTED.value:
                diagnostics.append(
                    _diagnostic(
                        "market_or_role_gap",
                        DiagnosticSeverity.INFO,
                        "Coverage contract is unsupported for this scope.",
                        {
                            "market_key": coverage.market_key,
                            "role_family": coverage.role_family,
                            "opportunity_type": coverage.opportunity_type,
                        },
                        {},
                    )
                )
        return tuple(diagnostics)

    def _process_record(
        self,
        source: OpportunityDataSource,
        run: OpportunityAcquisitionRun,
        record: Any,
        context: _NormalizationContext,
        semantic_warnings: list[str],
    ) -> dict[str, Any]:
        observation_id = _observation_id(
            source.source_id,
            run.run_id,
            record.provider_record_id,
            record.raw_payload,
        )
        payload_hash = _payload_hash(record.raw_payload)
        if self._repo.get_observation_for_run_record(
            source_id=source.source_id,
            run_id=run.run_id,
            provider_record_id=record.provider_record_id,
        ):
            return {
                "change_type": "duplicate_observation",
                "provider_record_id": record.provider_record_id,
                "count_bucket": "duplicates",
                "normalized": False,
                "promoted": False,
            }

        if record.status is AcquisitionRecordStatus.MALFORMED:
            self._repo.add(
                OpportunitySourceObservation(
                    source_observation_id=observation_id,
                    source_id=source.source_id,
                    run_id=run.run_id,
                    provider_record_id=record.provider_record_id,
                    provider_record_key=source_identity_key(
                        source.source_id, record.provider_record_id
                    ),
                    cursor=record.cursor,
                    raw_payload=record.raw_payload,
                    payload_hash=payload_hash,
                    source_values={},
                    normalized_payload=None,
                    record_status=record.status.value,
                    normalization_status=NormalizationStatus.INVALID.value,
                    validation_errors=[record.error_code or "malformed_provider_payload"],
                    observed_at=record.observed_at,
                    collected_at=record.collected_at,
                )
            )
            self._repo.flush()
            return {
                "change_type": "rejected_malformed",
                "provider_record_id": record.provider_record_id,
                "count_bucket": "rejected",
                "normalized": False,
                "promoted": False,
            }

        if record.status is AcquisitionRecordStatus.REMOVED:
            observation = OpportunitySourceObservation(
                source_observation_id=observation_id,
                source_id=source.source_id,
                run_id=run.run_id,
                provider_record_id=record.provider_record_id,
                provider_record_key=source_identity_key(
                    source.source_id, record.provider_record_id
                ),
                cursor=record.cursor,
                raw_payload=record.raw_payload,
                payload_hash=payload_hash,
                source_values={},
                normalized_payload=None,
                record_status=record.status.value,
                normalization_status=NormalizationStatus.WARNING.value,
                validation_errors=[],
                observed_at=record.observed_at,
                collected_at=record.collected_at,
            )
            self._repo.add(observation)
            self._repo.flush()
            link = self._repo.get_source_link(
                source_id=source.source_id,
                provider_record_id=record.provider_record_id,
            )
            if link is None:
                return {
                    "change_type": "removed_unknown_record",
                    "provider_record_id": record.provider_record_id,
                    "count_bucket": "rejected",
                    "normalized": False,
                    "promoted": False,
                    "warning": "removed_record_without_existing_link",
                }
            link.active = False
            link.latest_observation_id = observation_id
            link.last_collected_at = record.collected_at
            self._repo.flush()
            opportunity = self._repo.get_opportunity(link.current_opportunity_id)
            if opportunity is not None and not self._repo.list_source_links(
                opportunity.current_opportunity_id,
                active_only=True,
            ):
                _retire_if_unsupported(
                    self._repo,
                    opportunity,
                    now=record.collected_at,
                    reason="closed_or_removed",
                )
                return {
                    "change_type": "closed_removed_opportunity",
                    "provider_record_id": record.provider_record_id,
                    "opportunity_id": opportunity.current_opportunity_id,
                    "count_bucket": "closed",
                    "normalized": False,
                    "promoted": True,
                }
            return {
                "change_type": "source_record_removed",
                "provider_record_id": record.provider_record_id,
                "count_bucket": "updated",
                "normalized": False,
                "promoted": True,
            }

        try:
            normalized = normalize_opportunity_payload(
                record.raw_payload,
                provider_record_id=record.provider_record_id,
                companies_by_name=context.companies_by_name,
                geographic_resolver=context.geographic_resolver,
            )
        except Exception as exc:
            self._repo.add(
                OpportunitySourceObservation(
                    source_observation_id=observation_id,
                    source_id=source.source_id,
                    run_id=run.run_id,
                    provider_record_id=record.provider_record_id,
                    provider_record_key=source_identity_key(
                        source.source_id, record.provider_record_id
                    ),
                    cursor=record.cursor,
                    raw_payload=record.raw_payload,
                    payload_hash=payload_hash,
                    source_values={},
                    normalized_payload=None,
                    record_status=record.status.value,
                    normalization_status=NormalizationStatus.INVALID.value,
                    validation_errors=[str(exc)],
                    observed_at=record.observed_at,
                    collected_at=record.collected_at,
                )
            )
            return {
                "change_type": "normalization_failed",
                "provider_record_id": record.provider_record_id,
                "count_bucket": "rejected",
                "normalized": False,
                "promoted": False,
            }

        observation = OpportunitySourceObservation(
            source_observation_id=observation_id,
            source_id=source.source_id,
            run_id=run.run_id,
            provider_record_id=record.provider_record_id,
            provider_record_key=source_identity_key(source.source_id, record.provider_record_id),
            cursor=record.cursor,
            raw_payload=record.raw_payload,
            payload_hash=payload_hash,
            source_values=normalized.source_values,
            normalized_payload=normalized.model_dump(mode="json"),
            record_status=record.status.value,
            normalization_status=(
                NormalizationStatus.WARNING.value
                if normalized.normalization_warnings
                else NormalizationStatus.VALID.value
            ),
            validation_errors=list(normalized.normalization_warnings),
            observed_at=record.observed_at,
            collected_at=record.collected_at,
        )
        self._repo.add(observation)
        self._repo.flush()

        if normalized.normalization_confidence in {ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN}:
            semantic_warnings.extend(normalized.normalization_warnings)

        resolution = resolve_current_opportunity_identity(
            self._repo,
            normalized,
            source_id=source.source_id,
        )
        semantic_warnings.extend(resolution.warnings)
        opportunity = resolution.existing
        change_type = "updated_opportunity"
        count_bucket = "updated"
        if opportunity is None:
            opportunity = _new_current_opportunity(
                normalized,
                resolution.opportunity_id,
                identity_key=resolution.identity_key,
                duplicate_group_key=resolution.duplicate_group_key,
                identity_confidence=resolution.confidence,
                observed_at=record.observed_at,
                collected_at=record.collected_at,
            )
            self._repo.add(opportunity)
            change_type = "new_opportunity"
            count_bucket = "created"
        else:
            changes = _apply_canonical_diff(
                opportunity,
                normalized,
                observed_at=record.observed_at,
                collected_at=record.collected_at,
            )
            if (
                "market_id" in changes
                and normalized.market_id is not None
                and opportunity.market_id == normalized.market_id
            ):
                identity_owner = self._repo.get_opportunity_by_identity_key(resolution.identity_key)
                if identity_owner is None or identity_owner is opportunity:
                    opportunity.canonical_identity_key = resolution.identity_key
                    opportunity.duplicate_group_key = resolution.duplicate_group_key
                else:
                    semantic_warnings.append(
                        "canonical_identity_upgrade_conflict:"
                        f"{identity_owner.current_opportunity_id}"
                    )
            if resolution.status is IdentityResolutionStatus.CROSS_SOURCE_DUPLICATE:
                count_bucket = "duplicates"
                change_type = "cross_source_duplicate_linked"
            if "application_url" in changes:
                semantic_warnings.append("application_route_changed")
            if "compensation" in changes:
                semantic_warnings.append("compensation_changed")
            if "company" in changes or "normalized_title" in changes:
                semantic_warnings.append("identity_semantic_change")
            opportunity.warnings = _append_many(opportunity.warnings or [], resolution.warnings)

        link = self._repo.get_source_link(
            source_id=source.source_id,
            provider_record_id=record.provider_record_id,
        )
        previous_linked_opportunity_id = link.current_opportunity_id if link is not None else None
        if link is None:
            self._repo.add(
                CurrentOpportunitySourceLink(
                    current_opportunity_source_link_id=link_id(
                        source.source_id, record.provider_record_id
                    ),
                    current_opportunity_id=opportunity.current_opportunity_id,
                    source_id=source.source_id,
                    provider_record_id=record.provider_record_id,
                    latest_observation_id=observation.source_observation_id,
                    source_identity_key=source_identity_key(
                        source.source_id, record.provider_record_id
                    ),
                    first_observed_at=record.observed_at,
                    last_observed_at=record.observed_at,
                    last_collected_at=record.collected_at,
                    active=True,
                    payload_hash=payload_hash,
                    application_url=normalized.application_url,
                    identity_confidence=resolution.confidence.value,
                )
            )
        else:
            link.current_opportunity_id = opportunity.current_opportunity_id
            link.latest_observation_id = observation.source_observation_id
            link.last_observed_at = record.observed_at
            link.last_collected_at = record.collected_at
            link.active = True
            link.payload_hash = payload_hash
            link.application_url = normalized.application_url
            link.identity_confidence = resolution.confidence.value

        self._repo.flush()
        if (
            previous_linked_opportunity_id is not None
            and previous_linked_opportunity_id != opportunity.current_opportunity_id
        ):
            previous_opportunity = self._repo.get_opportunity(previous_linked_opportunity_id)
            if previous_opportunity is not None:
                _retire_if_unsupported(
                    self._repo,
                    previous_opportunity,
                    now=record.collected_at,
                    reason="source_link_reassigned",
                )

        geography_conflict = next(
            (
                warning
                for warning in resolution.warnings
                if warning.startswith("resolved_geography_conflict:")
            ),
            None,
        )
        geography_previous_region_id: str | None = None
        geography_candidate_region_id: str | None = None
        if geography_conflict is not None:
            (
                _prefix,
                geography_previous_region_id,
                geography_candidate_region_id,
            ) = geography_conflict.split(":", 2)
        self._repo.add(
            CurrentOpportunityIdentityEvidence(
                identity_evidence_id=evidence_id(
                    observation.source_observation_id,
                    opportunity.current_opportunity_id,
                ),
                current_opportunity_id=opportunity.current_opportunity_id,
                source_observation_id=observation.source_observation_id,
                source_id=source.source_id,
                provider_record_id=record.provider_record_id,
                resolution_status=resolution.status.value,
                identity_key=resolution.identity_key,
                duplicate_group_key=resolution.duplicate_group_key,
                confidence=resolution.confidence.value,
                evidence_payload={
                    "company_name": normalized.company_name,
                    "normalized_title": normalized.normalized_title,
                    "market": normalized.market_id or normalized.market_label,
                    "application_host": normalized.application_host,
                },
                warnings=list(resolution.warnings),
                geography_review_status="pending" if geography_conflict else None,
                geography_previous_region_id=geography_previous_region_id,
                geography_candidate_region_id=geography_candidate_region_id,
            )
        )
        self._repo.flush()
        _recompute_opportunity_policy(self._repo, opportunity, now=record.collected_at)
        return {
            "change_type": change_type,
            "provider_record_id": record.provider_record_id,
            "opportunity_id": opportunity.current_opportunity_id,
            "count_bucket": count_bucket,
            "normalized": True,
            "promoted": True,
            "warnings": (*normalized.normalization_warnings, *resolution.warnings),
        }

    def _opportunity_payload(
        self,
        row: CurrentOpportunity,
        *,
        now: datetime | None = None,
        active_links: list[CurrentOpportunitySourceLink] | None = None,
        links: list[CurrentOpportunitySourceLink] | None = None,
        source_rows: Mapping[str, OpportunityDataSource] | None = None,
        coverage_rows: Mapping[tuple[str, str, str], OpportunityCoverageContract] | None = None,
        market_identities: Mapping[str, Mapping[str, str | None]] | None = None,
    ) -> CurrentOpportunityPayload:
        prefetched_market = (
            market_identities.get(row.market_id)
            if market_identities is not None and row.market_id is not None
            else None
        )
        market_resolution = None
        if prefetched_market is None and row.market_id is not None:
            market_resolution = GeographicResolver(RegionRepository(self._repo.session)).resolve(
                row.market_id
            )
        output_market_id = row.market_id
        output_market_label = row.market_label
        output_market_public_slug = None
        if prefetched_market is not None:
            output_market_id = prefetched_market["region_id"]
            output_market_label = prefetched_market["display_name"] or row.market_label
            output_market_public_slug = prefetched_market["public_slug"]
        elif market_resolution is not None and market_resolution.resolved:
            output_market_id = market_resolution.region_id
            output_market_label = market_resolution.display_name
            output_market_public_slug = market_resolution.public_slug
        _recompute_opportunity_policy(
            self._repo,
            row,
            now=now or _utc_now(),
            active_links=active_links,
            source_rows=source_rows,
            coverage_rows=coverage_rows,
        )
        coverage = _coverage_payload(
            _coverage_for_row(
                self._repo,
                row,
                coverage_rows=coverage_rows,
            ),
            market_key=row.market_id or "*",
            role_family=row.role_family,
            opportunity_type=row.opportunity_type,
            now=now or _utc_now(),
        )
        links = (
            links if links is not None else self._repo.list_source_links(row.current_opportunity_id)
        )
        if source_rows is None:
            source_rows = self._repo.list_sources_by_ids({link.source_id for link in links})
        provenance_sources = []
        for link in links:
            source = source_rows.get(link.source_id)
            provenance_sources.append(
                {
                    "source_id": link.source_id,
                    "provider_record_id": link.provider_record_id,
                    "first_observed_at": link.first_observed_at.isoformat()
                    if link.first_observed_at
                    else None,
                    "last_observed_at": link.last_observed_at.isoformat()
                    if link.last_observed_at
                    else None,
                    "last_collected_at": link.last_collected_at.isoformat()
                    if link.last_collected_at
                    else None,
                    "active": link.active,
                    "source_trust": source.trust_classification if source else "unknown",
                    "display_use_allowed": bool(source.display_use_allowed) if source else False,
                    "ranking_use_allowed": bool(source.ranking_use_allowed) if source else False,
                }
            )
        return CurrentOpportunityPayload(
            opportunity_id=row.current_opportunity_id,
            company_id=row.company_id,
            company_name=row.company_name,
            original_title=row.original_title,
            normalized_title=row.normalized_title,
            role_family=row.role_family,
            seniority_level=row.seniority_level,
            market_id=output_market_id,
            market_public_slug=output_market_public_slug,
            original_market_id=(row.market_id if output_market_id != row.market_id else None),
            market_label=output_market_label,
            location_text=row.location_text,
            location_resolution_status=row.location_resolution_status,
            location_resolution_source=row.location_resolution_source,
            work_arrangement=row.work_arrangement,
            compensation_min=row.compensation_min,
            compensation_max=row.compensation_max,
            compensation_currency=row.compensation_currency,
            compensation_interval=row.compensation_interval,
            employment_type=row.employment_type,
            opportunity_type=row.opportunity_type,
            posting_date=row.posting_date,
            closing_date=row.closing_date,
            application_url=row.application_url,
            source_url=row.source_url,
            description_text=row.description_text,
            skills=tuple(row.skills or []),
            requirements=tuple(row.requirements or []),
            status=row.canonical_status,
            freshness_state=row.freshness_state,
            freshness_age_hours=_age_hours(row.last_observed_at, now or _utc_now()),
            first_observed_at=row.first_observed_at,
            last_observed_at=row.last_observed_at,
            last_collected_at=row.last_collected_at,
            canonical_updated_at=row.canonical_updated_at,
            normalization_confidence=row.normalization_confidence,
            identity_confidence=row.identity_confidence,
            ranking_eligible=row.ranking_eligible,
            ranking_ineligible_reasons=tuple(row.ranking_ineligible_reasons or []),
            coverage_status=coverage.effective_status,
            coverage_limitations=coverage.limitations,
            provenance={
                "sources": provenance_sources,
                "source_count": row.source_count,
                "identity_key": row.canonical_identity_key,
                "duplicate_group_key": row.duplicate_group_key,
                **(
                    {"original_market_id": row.market_id}
                    if output_market_id != row.market_id
                    else {}
                ),
            },
            warnings=tuple(row.warnings or []),
        )

    def _run_payload(self, row: OpportunityAcquisitionRun) -> RefreshRunPayload:
        return RefreshRunPayload(
            run_id=row.run_id,
            source_id=row.source_id,
            status=row.status,
            acquired_count=row.acquired_count,
            normalized_count=row.normalized_count,
            promoted_count=row.promoted_count,
            duplicate_count=row.duplicate_count,
            rejected_count=row.rejected_count,
            warning_count=row.warning_count,
            failure_count=row.failure_count,
            started_at=row.started_at,
            completed_at=row.completed_at,
            warnings=tuple(row.warnings or []),
            failure_details=row.failure_details or {},
        )


@dataclass(frozen=True, slots=True)
class _NormalizationContext:
    companies_by_name: dict[str, Company]
    geographic_resolver: GeographicResolver

    @classmethod
    def from_session(cls, session) -> _NormalizationContext:  # noqa: ANN001
        companies = list(session.execute(select(Company)).scalars())
        companies_by_name = {_norm(company.company_name): company for company in companies}
        companies_by_name.update(
            {_norm(company.normalized_company_name): company for company in companies}
        )
        return cls(
            companies_by_name=companies_by_name,
            geographic_resolver=GeographicResolver(RegionRepository(session)),
        )


def _new_current_opportunity(
    normalized: NormalizedOpportunity,
    opportunity_id: str,
    *,
    identity_key: str,
    duplicate_group_key: str,
    identity_confidence: ConfidenceLevel,
    observed_at: datetime | None,
    collected_at: datetime,
) -> CurrentOpportunity:
    now = collected_at
    return CurrentOpportunity(
        current_opportunity_id=opportunity_id,
        canonical_identity_key=identity_key,
        duplicate_group_key=duplicate_group_key,
        company_id=normalized.company_id,
        company_name=normalized.company_name or "Unknown company",
        original_title=normalized.original_title or "Unknown title",
        normalized_title=normalized.normalized_title or "unknown title",
        role_family=normalized.role_family,
        seniority_level=normalized.seniority_level,
        market_id=normalized.market_id,
        market_label=normalized.market_label,
        location_text=normalized.location_text,
        location_resolution_status=normalized.location_resolution_status.value,
        location_resolution_source=normalized.location_resolution_source,
        work_arrangement=normalized.work_arrangement.value,
        compensation_min=normalized.compensation_min,
        compensation_max=normalized.compensation_max,
        compensation_currency=normalized.compensation_currency,
        compensation_interval=normalized.compensation_interval.value,
        employment_type=normalized.employment_type.value,
        opportunity_type=normalized.opportunity_type.value,
        posting_date=normalized.posting_date,
        closing_date=normalized.closing_date,
        application_url=normalized.application_url,
        application_host=normalized.application_host,
        source_url=normalized.source_url,
        description_text=normalized.description_text,
        skills=list(normalized.skills),
        requirements=list(normalized.requirements),
        source_values=normalized.source_values,
        normalization_confidence=normalized.normalization_confidence.value,
        identity_confidence=identity_confidence.value,
        canonical_status=OpportunityStatus.ACTIVE.value,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        last_collected_at=collected_at,
        canonical_updated_at=now,
        freshness_state=FreshnessState.UNKNOWN.value,
        ranking_eligible=False,
        ranking_ineligible_reasons=["policy_not_evaluated"],
        warnings=list(normalized.normalization_warnings),
        source_count=0,
    )


def _apply_canonical_diff(
    row: CurrentOpportunity,
    normalized: NormalizedOpportunity,
    *,
    observed_at: datetime | None,
    collected_at: datetime,
) -> set[str]:
    changed: set[str] = set()
    geography_updates: dict[str, object]
    if row.market_id is None:
        geography_updates = {
            "market_id": normalized.market_id,
            "location_resolution_status": normalized.location_resolution_status.value,
            "location_resolution_source": normalized.location_resolution_source,
        }
    elif normalized.market_id == row.market_id:
        geography_updates = {
            "market_id": row.market_id,
            "location_resolution_status": normalized.location_resolution_status.value,
            "location_resolution_source": normalized.location_resolution_source,
        }
    else:
        # A weaker observation, or a confidently resolved different geography,
        # is evidence—not authority to erase/reassign canonical identity.  The
        # raw observation remains preserved and resolution warnings trigger
        # review through the existing identity evidence stream.
        geography_updates = {
            "market_id": row.market_id,
            "location_resolution_status": row.location_resolution_status,
            "location_resolution_source": row.location_resolution_source,
        }
    updates = {
        "company_id": normalized.company_id,
        "company_name": normalized.company_name or row.company_name,
        "original_title": normalized.original_title or row.original_title,
        "normalized_title": normalized.normalized_title or row.normalized_title,
        "role_family": normalized.role_family,
        "seniority_level": normalized.seniority_level,
        "market_label": normalized.market_label,
        "location_text": normalized.location_text,
        "work_arrangement": normalized.work_arrangement.value,
        "compensation_min": normalized.compensation_min,
        "compensation_max": normalized.compensation_max,
        "compensation_currency": normalized.compensation_currency,
        "compensation_interval": normalized.compensation_interval.value,
        "employment_type": normalized.employment_type.value,
        "opportunity_type": normalized.opportunity_type.value,
        "posting_date": normalized.posting_date,
        "closing_date": normalized.closing_date,
        "application_url": normalized.application_url,
        "application_host": normalized.application_host,
        "source_url": normalized.source_url,
        "description_text": normalized.description_text,
        "skills": list(normalized.skills),
        "requirements": list(normalized.requirements),
        "source_values": normalized.source_values,
        "normalization_confidence": normalized.normalization_confidence.value,
        **geography_updates,
    }
    for key, value in updates.items():
        if key == "company_id" and value is None:
            continue
        if getattr(row, key) != value:
            setattr(row, key, value)
            if key in {
                "compensation_min",
                "compensation_max",
                "compensation_currency",
                "compensation_interval",
            }:
                changed.add("compensation")
            else:
                changed.add(key)
    row.last_observed_at = _max_dt(row.last_observed_at, observed_at)
    row.last_collected_at = _max_dt(row.last_collected_at, collected_at) or collected_at
    row.canonical_status = OpportunityStatus.ACTIVE.value
    row.canonical_updated_at = collected_at
    row.warnings = _append_many(row.warnings or [], normalized.normalization_warnings)
    return changed


def _retire_if_unsupported(
    repo: CurrentOpportunityRepository,
    row: CurrentOpportunity,
    *,
    now: datetime,
    reason: str,
) -> None:
    """Close a canonical row after its final active source link moves away."""

    if repo.list_source_links(row.current_opportunity_id, active_only=True):
        return
    row.canonical_status = OpportunityStatus.CLOSED.value
    row.warnings = _append_unique(row.warnings, reason)
    row.canonical_updated_at = now
    _recompute_opportunity_policy(repo, row, now=now, active_links=[])


def _coverage_rows_by_market(
    rows: list[OpportunityCoverageContract],
) -> dict[tuple[str, str, str], OpportunityCoverageContract]:
    result = {(row.market_key, row.role_family, row.opportunity_type): row for row in rows}
    for row in rows:
        if row.market_id is not None:
            result.setdefault((row.market_id, row.role_family, row.opportunity_type), row)
    return result


def _coverage_for_row(
    repo: CurrentOpportunityRepository,
    row: CurrentOpportunity,
    *,
    coverage_rows: Mapping[tuple[str, str, str], OpportunityCoverageContract] | None = None,
) -> OpportunityCoverageContract | None:
    market_key = row.market_id or "*"
    if coverage_rows is None:
        return repo.get_coverage(
            market_key=market_key,
            role_family=row.role_family,
            opportunity_type=row.opportunity_type,
        )
    for scope in (
        (market_key, row.role_family, row.opportunity_type),
        (market_key, row.role_family, "*"),
        (market_key, "*", row.opportunity_type),
        (market_key, "*", "*"),
        ("*", row.role_family, row.opportunity_type),
        ("*", row.role_family, "*"),
        ("*", "*", row.opportunity_type),
        ("*", "*", "*"),
    ):
        coverage = coverage_rows.get(scope)
        if coverage is not None:
            return coverage
    return None


def _recompute_opportunity_policy(
    repo: CurrentOpportunityRepository,
    row: CurrentOpportunity,
    *,
    now: datetime,
    active_links: list[CurrentOpportunitySourceLink] | None = None,
    source_rows: Mapping[str, OpportunityDataSource] | None = None,
    coverage_rows: Mapping[tuple[str, str, str], OpportunityCoverageContract] | None = None,
) -> None:
    active_links = (
        active_links
        if active_links is not None
        else repo.list_source_links(row.current_opportunity_id, active_only=True)
    )
    row.source_count = len(active_links)
    freshness_state = _freshness_state(
        row.last_observed_at,
        active_links,
        repo,
        now,
        source_rows=source_rows,
    )
    row.freshness_state = freshness_state.value
    if (
        row.canonical_status != OpportunityStatus.CLOSED.value
        and freshness_state is FreshnessState.STALE
    ):
        row.canonical_status = OpportunityStatus.STALE.value
    if row.canonical_status == OpportunityStatus.STALE.value and freshness_state in {
        FreshnessState.FRESH,
        FreshnessState.AGING,
    }:
        row.canonical_status = OpportunityStatus.ACTIVE.value

    reasons: list[str] = []
    if row.canonical_status != OpportunityStatus.ACTIVE.value:
        reasons.append("not_active_current_opportunity")
    if freshness_state in {FreshnessState.STALE, FreshnessState.UNKNOWN}:
        reasons.append(f"freshness_{freshness_state.value}")
    if row.normalization_confidence not in {
        ConfidenceLevel.HIGH.value,
        ConfidenceLevel.MEDIUM.value,
    }:
        reasons.append("normalization_confidence_too_low")
    if row.identity_confidence not in {ConfidenceLevel.HIGH.value, ConfidenceLevel.MEDIUM.value}:
        reasons.append("identity_confidence_too_low")
    coverage = _coverage_payload(
        _coverage_for_row(repo, row, coverage_rows=coverage_rows),
        market_key=row.market_id or "*",
        role_family=row.role_family,
        opportunity_type=row.opportunity_type,
        now=now,
    )
    if coverage.effective_status not in {CoverageStatus.PRODUCTION_READY, CoverageStatus.LIMITED}:
        reasons.append(f"coverage_{coverage.effective_status.value}")
    if not active_links:
        reasons.append("no_active_source_links")

    source_ok = False
    for link in active_links:
        source = (
            source_rows.get(link.source_id)
            if source_rows is not None
            else repo.get_source(link.source_id)
        )
        if source is None:
            continue
        issue = _source_governance_issue(source, for_refresh=False)
        if issue is not None:
            reasons.append(issue)
            continue
        if not _source_supports_row(source, row):
            reasons.append("source_scope_not_supported")
            continue
        source_ok = True
    if not source_ok:
        reasons.append("no_ranking_eligible_source")
    row.ranking_ineligible_reasons = tuple(sorted(set(reasons)))
    row.ranking_eligible = not reasons
    repo.flush()


def _source_governance_issue(source: OpportunityDataSource, *, for_refresh: bool) -> str | None:
    if not source.enabled:
        return "source_disabled"
    if source.operational_status != SourceOperationalStatus.ENABLED.value:
        return f"source_{source.operational_status}"
    if source.allowed_use in {
        AllowedUseClassification.UNKNOWN.value,
        AllowedUseClassification.PROHIBITED.value,
    }:
        return "source_allowed_use_not_permitted"
    if source.license_terms in {
        LicenseTermsClassification.UNKNOWN.value,
        LicenseTermsClassification.PROHIBITED.value,
    }:
        return "source_license_not_permitted"
    if for_refresh:
        return None
    if source.allowed_use == AllowedUseClassification.INTERNAL_ONLY.value:
        return "source_allowed_use_not_permitted"
    if not source.display_use_allowed:
        return "source_display_not_permitted"
    if not source.ranking_use_allowed:
        return "source_ranking_not_permitted"
    if source.trust_classification in {
        SourceTrustClassification.UNKNOWN.value,
        SourceTrustClassification.UNTRUSTED.value,
    }:
        return "source_trust_not_sufficient"
    return None


def _source_display_issue(source: OpportunityDataSource) -> str | None:
    if not source.enabled:
        return "source_disabled"
    if source.operational_status != SourceOperationalStatus.ENABLED.value:
        return f"source_{source.operational_status}"
    if source.allowed_use in {
        AllowedUseClassification.UNKNOWN.value,
        AllowedUseClassification.PROHIBITED.value,
        AllowedUseClassification.INTERNAL_ONLY.value,
    }:
        return "source_allowed_use_not_displayable"
    if source.license_terms in {
        LicenseTermsClassification.UNKNOWN.value,
        LicenseTermsClassification.PROHIBITED.value,
    }:
        return "source_license_not_displayable"
    if not source.display_use_allowed:
        return "source_display_not_permitted"
    return None


def _row_display_allowed(
    repo: CurrentOpportunityRepository,
    row: CurrentOpportunity,
    *,
    active_links: list[CurrentOpportunitySourceLink] | None = None,
    source_rows: Mapping[str, OpportunityDataSource] | None = None,
) -> bool:
    active_links = (
        active_links
        if active_links is not None
        else repo.list_source_links(row.current_opportunity_id, active_only=True)
    )
    if row.canonical_status not in {
        OpportunityStatus.ACTIVE.value,
        OpportunityStatus.STALE.value,
    }:
        return False
    for link in active_links:
        source = (
            source_rows.get(link.source_id)
            if source_rows is not None
            else repo.get_source(link.source_id)
        )
        if source is None:
            continue
        if _source_display_issue(source) is None and _source_supports_row(source, row):
            return True
    return False


def _source_supports_row(source: OpportunityDataSource, row: CurrentOpportunity) -> bool:
    markets = set(source.supported_markets or [])
    types = set(source.supported_opportunity_types or [])
    market = row.market_id
    if markets and (market is None or market not in markets):
        return False
    if types and row.opportunity_type not in types:
        return False
    return True


def _freshness_state(
    last_observed_at: datetime | None,
    links: list[CurrentOpportunitySourceLink],
    repo: CurrentOpportunityRepository,
    now: datetime,
    *,
    source_rows: Mapping[str, OpportunityDataSource] | None = None,
) -> FreshnessState:
    if last_observed_at is None:
        return FreshnessState.UNKNOWN
    if not links:
        return FreshnessState.STALE
    best_sla = None
    for link in links:
        source = (
            source_rows.get(link.source_id)
            if source_rows is not None
            else repo.get_source(link.source_id)
        )
        if source is not None:
            best_sla = max(best_sla or 0, source.freshness_sla_hours)
    if best_sla is None:
        return FreshnessState.UNKNOWN
    age = _age_hours(last_observed_at, now)
    if age is None:
        return FreshnessState.UNKNOWN
    if age <= best_sla:
        return FreshnessState.FRESH
    if age <= int(best_sla * 1.5):
        return FreshnessState.AGING
    return FreshnessState.STALE


def _coverage_payload(
    row: OpportunityCoverageContract | None,
    *,
    market_key: str,
    role_family: str,
    opportunity_type: str,
    now: datetime,
) -> CoveragePayload:
    if row is None:
        return CoveragePayload(
            market_key=market_key,
            role_family=role_family,
            opportunity_type=opportunity_type,
            status=CoverageStatus.UNSUPPORTED,
            effective_status=CoverageStatus.UNSUPPORTED,
            rationale="No explicit current-opportunity coverage contract exists for this scope.",
            limitations=("unknown combinations fail closed",),
            source_basis={},
            minimum_expected_sources=0,
            freshness_max_age_hours=None,
            last_evaluated_at=None,
        )
    base_status = CoverageStatus(row.operator_override_status or row.status)
    limitations: list[str] = []
    effective = base_status
    if base_status is CoverageStatus.UNSUPPORTED:
        limitations.append("unsupported coverage does not imply no opportunities exist")
    elif base_status is CoverageStatus.LIMITED:
        limitations.append("result set is partial and must not be treated as exhaustive")
    elif base_status is CoverageStatus.EXPERIMENTAL:
        limitations.append("experimental coverage is not ranking eligible by default")
    if row.freshness_max_age_hours and row.last_evaluated_at:
        age = _age_hours(row.last_evaluated_at, now)
        if age is not None and age > row.freshness_max_age_hours:
            limitations.append("coverage evaluation is stale")
            if effective is CoverageStatus.PRODUCTION_READY:
                effective = CoverageStatus.LIMITED
    return CoveragePayload(
        market_key=row.market_key,
        role_family=row.role_family,
        opportunity_type=row.opportunity_type,
        status=CoverageStatus(row.status),
        effective_status=effective,
        rationale=row.rationale,
        limitations=tuple(limitations),
        source_basis=row.source_basis or {},
        minimum_expected_sources=row.minimum_expected_sources,
        freshness_max_age_hours=row.freshness_max_age_hours,
        last_evaluated_at=row.last_evaluated_at,
    )


def _career_identity_terms(session, user_id: str) -> set[str]:  # noqa: ANN001
    identity = session.execute(
        select(CareerIdentity).where(CareerIdentity.user_id == user_id)
    ).scalar_one_or_none()
    if identity is None or not identity.downstream_personalization_consent_granted:
        return set()
    facts = list(
        session.execute(
            select(CareerIdentityFact).where(
                CareerIdentityFact.career_identity_id == identity.career_identity_id
            )
        ).scalars()
    )
    terms: set[str] = set()
    for fact in facts:
        terms.add(_norm(fact.normalized_key))
        terms.add(_norm(fact.fact_type))
        if isinstance(fact.payload, dict):
            for value in fact.payload.values():
                if isinstance(value, str):
                    terms.update(_tokens(value))
                elif isinstance(value, list):
                    terms.update(_tokens(" ".join(str(item) for item in value)))
    return terms


def _decision_terms(session, user_id: str, decision_id: str | None) -> set[str]:  # noqa: ANN001
    stmt = select(CareerDecision).where(CareerDecision.user_id == user_id)
    if decision_id is not None:
        stmt = stmt.where(CareerDecision.decision_id == decision_id)
    decisions = list(session.execute(stmt.limit(20)).scalars())
    terms: set[str] = set()
    for decision in decisions:
        terms.update(_tokens(decision.title))
        if decision.description:
            terms.update(_tokens(decision.description))
        terms.update(_tokens(json.dumps(decision.priorities or [])))
        terms.update(_tokens(json.dumps(decision.constraints or [])))
    return terms


def _strategy_terms(session, user_id: str, decision_id: str | None) -> set[str]:  # noqa: ANN001
    stmt = select(StrategicCareerReview).where(StrategicCareerReview.user_id == user_id)
    if decision_id is not None:
        stmt = stmt.where(StrategicCareerReview.decision_id == decision_id)
    review = session.execute(
        stmt.order_by(StrategicCareerReview.generated_at.desc()).limit(1)
    ).scalar_one_or_none()
    if review is None:
        return set()
    return _tokens(
        " ".join(
            [
                json.dumps(review.goals or {}),
                json.dumps(review.strategy_performance or {}),
                json.dumps(review.suggested_next_actions or []),
                json.dumps(review.active_risks or []),
                json.dumps(review.blind_spots or []),
            ]
        )
    )


def _score_match(
    payload: CurrentOpportunityPayload, desired_terms: set[str]
) -> tuple[float, list[str]]:
    factors: list[str] = []
    score = 0.0
    opportunity_terms = _tokens(
        " ".join(
            [
                payload.company_name,
                payload.normalized_title,
                payload.role_family,
                payload.market_id or "",
                payload.market_label or "",
                payload.location_text or "",
                payload.description_text or "",
                " ".join(payload.skills),
                " ".join(payload.requirements),
            ]
        )
    )
    overlap = desired_terms & opportunity_terms
    if payload.role_family in desired_terms or _norm(payload.role_family) in desired_terms:
        score += 0.3
        factors.append("role fit")
    if (
        payload.market_id is not None
        and {
            payload.market_id,
            _norm(payload.market_id),
        }
        & desired_terms
    ):
        score += 0.2
        factors.append("location fit")
    if overlap:
        score += min(0.25, len(overlap) * 0.04)
        factors.append("career identity and decision term overlap")
    if payload.ranking_eligible:
        score += 0.15
        factors.append("current and ranking eligible")
    if payload.freshness_state is FreshnessState.FRESH:
        score += 0.1
        factors.append("fresh source observation")
    if payload.coverage_status is CoverageStatus.PRODUCTION_READY:
        score += 0.08
        factors.append("production-ready coverage")
    elif payload.coverage_status is CoverageStatus.LIMITED:
        score += 0.03
        factors.append("limited coverage")
    return min(score, 1.0), factors


def _relevance(score: float, ranking_eligible: bool) -> str:
    if not ranking_eligible:
        return "not_rankable"
    if score >= 0.7:
        return "direct_fit"
    if score >= 0.35:
        return "adjacent_fit"
    return "weak_fit"


def _run_status(status: AcquisitionRunStatus, failure_count: int) -> str:
    if status is AcquisitionRunStatus.FAILED:
        return AcquisitionRunStatus.FAILED.value
    if failure_count:
        return AcquisitionRunStatus.PARTIAL_FAILURE.value
    return AcquisitionRunStatus.COMPLETED.value


def _bounded_backoff(retry_count: int) -> timedelta:
    return timedelta(minutes=min(60, 5 * (2 ** max(0, retry_count))))


def _payload_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(body.encode("utf-8")).hexdigest()


def _observation_id(
    source_id: str, run_id: str, provider_record_id: str, payload: dict[str, Any]
) -> str:
    return _stable_id("opp_obs", source_id, run_id, provider_record_id, _payload_hash(payload))


def _stable_id(prefix: str, *parts: str) -> str:
    seed = "|".join(parts)
    return prefix + "_" + sha256(seed.encode("utf-8")).hexdigest()[:24]


def _age_hours(value: datetime | None, now: datetime) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return max(0, int((now - value).total_seconds() // 3600))


def _max_dt(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    if left.tzinfo is None:
        left = left.replace(tzinfo=UTC)
    if right.tzinfo is None:
        right = right.replace(tzinfo=UTC)
    return max(left, right)


def _append_unique(values: list | tuple, value: str) -> list[str]:
    return _append_many(values, (value,))


def _append_many(values: list | tuple, additions: tuple[str, ...]) -> list[str]:
    output = [str(item) for item in values]
    for item in additions:
        if item not in output:
            output.append(item)
    return output


def _diagnostic(
    code: str,
    severity: DiagnosticSeverity,
    message: str,
    scope: dict[str, Any],
    evidence: dict[str, Any],
) -> DiagnosticPayload:
    return DiagnosticPayload(
        code=code,
        severity=severity,
        message=message,
        scope=scope,
        evidence=evidence,
    )


def _tokens(value: str) -> set[str]:
    cleaned = _norm(value)
    return {token for token in cleaned.split() if len(token) > 2}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).lower().replace("-", " ").replace("_", " ").split())
