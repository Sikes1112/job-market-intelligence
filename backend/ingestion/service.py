"""Layer 4A raw ingestion service.

This service stores raw intake, records normalization status, attaches
existing provenance, and emits canonical fact proposals. It never writes
trusted canonical market facts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.ingestion.adapters.base import AdapterResult, AdapterResultStatus
from backend.ingestion.adapters.manual import ManualResearchAdapter
from backend.ingestion.contracts import (
    CanonicalFactProposal,
    CanonicalWriteDiagnostic,
    CanonicalWriteExecutionDecision,
    CanonicalWriteExecutionDiagnostic,
    CanonicalWriteExecutionResult,
    CanonicalWriteOperation,
    CanonicalWritePlan,
    IntakeProvenanceAttachmentResult,
    IntakeProvenanceDefinition,
    ManualIngestionRunDiagnostic,
    ManualIngestionRunRequest,
    ManualIngestionRunResult,
    ManualIngestionStepResult,
    NormalizationResult,
    PostWriteRefreshDiagnostic,
    PostWriteRefreshExecutionDecision,
    PostWriteRefreshExecutionDiagnostic,
    PostWriteRefreshExecutionResult,
    PostWriteRefreshPlan,
    PostWriteRefreshTarget,
    PostWriteRefreshTargetExecutionResult,
    ProposalReviewDecision,
    ProposalReviewResult,
    ProvenanceAttachment,
    RawIntakeDefinition,
)
from backend.ingestion.models import RawIngestionRecord
from backend.ingestion.normalization import payload_checksum
from backend.ingestion.normalizers.base import NormalizerResult, SourceNormalizer
from backend.ingestion.normalizers.manual import ManualObservationNormalizer
from backend.ingestion.repository import IngestionRepository
from backend.ingestion.status import (
    CanonicalFactIntent,
    CanonicalWriteExecutionStatus,
    CanonicalWriteOperationType,
    CanonicalWritePlanStatus,
    IngestionStatus,
    ManualIngestionRunMode,
    ManualIngestionRunStatus,
    NormalizationStatus,
    PostWriteRefreshExecutionStatus,
    PostWriteRefreshPlanStatus,
    PostWriteRefreshTargetType,
    ProposalReviewStatus,
)
from backend.outputs.exceptions import MissingCompanyForOutput, MissingRegionForOutput
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.provenance.service import (
    FactSourceLinkDefinition,
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.scoring.exceptions import MissingRegionForScoring
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    SOURCE_TYPE_DEFAULT_ACCEPTABILITY,
    DataOrigin,
    LicenseTermsCategory,
    ObservationStatus,
    SourceAcceptability,
    SourceType,
)
from backend.shared.versioning import next_version


class IngestionService:
    def __init__(self, repository: IngestionRepository) -> None:
        self._repo = repository

    def create_raw_record(self, definition: RawIntakeDefinition) -> RawIngestionRecord:
        record = RawIngestionRecord(
            raw_record_id=definition.raw_record_id,
            provider_id=definition.provider_id,
            source_type=definition.source_type.value,
            source_name=definition.source_name,
            url_or_provider=definition.url_or_provider,
            external_entity_id=definition.external_entity_id,
            raw_payload=definition.raw_payload.body,
            normalized_payload=None,
            payload_checksum=payload_checksum(definition.raw_payload.body),
            schema_version=definition.schema_version,
            collected_at=definition.collected_at,
            observed_at=definition.observed_at,
            ingestion_status=definition.ingestion_status.value,
            normalization_status=definition.normalization_status.value,
            intended_fact_type=(
                definition.intended_fact_type.value
                if definition.intended_fact_type is not None
                else None
            ),
            source_id=definition.source_id,
            observation_id=definition.observation_id,
            parsing_notes=definition.parsing_notes,
            parsing_errors=None,
        )
        self._repo.add_raw_record(record)
        self._repo.flush()
        return record

    def create_raw_records_from_adapter_result(
        self, result: AdapterResult
    ) -> list[RawIngestionRecord]:
        """Store adapter output as raw intake only.

        This method does not normalize, attach provenance, create fact-source
        links, or write canonical truth rows.
        """
        if result.status is AdapterResultStatus.FAILED:
            raise ValueError("failed adapter result cannot be stored")
        records: list[RawIngestionRecord] = []
        for definition in result.raw_intake_definitions:
            records.append(self.create_raw_record(definition))
        return records

    def run_manual_ingestion(
        self,
        request: ManualIngestionRunRequest,
        *,
        provenance_service: ProvenanceService,
        adapter: ManualResearchAdapter | None = None,
        normalizer: SourceNormalizer | None = None,
    ) -> ManualIngestionRunResult:
        """Run the bounded manual ingestion flow with visible trust gates.

        The default mode stops before proposal review/linking and never writes
        canonical facts or refreshes downstream artifacts. Write and refresh
        execution only occur when the request mode permits them and the caller
        supplies the matching approval decision.
        """
        adapter = adapter or ManualResearchAdapter()
        normalizer = normalizer or ManualObservationNormalizer()
        diagnostics: list[ManualIngestionRunDiagnostic] = []
        steps: list[ManualIngestionStepResult] = []

        adapter_result = adapter.prepare(request.manual_observation)
        _manual_step(
            steps,
            "adapter",
            adapter_result.status.value,
            payload=adapter_result,
        )
        if not adapter_result.usable_as_raw_intake:
            diagnostics.append(
                _manual_diag(
                    "adapter_output_not_usable",
                    "Manual adapter output was not usable as raw intake.",
                    stage="adapter",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.FAILED,
                adapter_result=adapter_result,
                steps=steps,
                diagnostics=diagnostics,
            )

        raw_records: list[RawIngestionRecord] = []
        for definition in adapter_result.raw_intake_definitions:
            existing = self._repo.get_raw_record(definition.raw_record_id)
            if existing is not None:
                raw_records.append(existing)
                diagnostics.append(
                    _manual_diag(
                        "raw_record_reused",
                        "Existing raw ingestion record reused for deterministic orchestration.",
                        stage="raw_intake",
                    )
                )
                continue
            raw_records.append(self.create_raw_record(definition))
        raw_record_ids = tuple(record.raw_record_id for record in raw_records)
        _manual_step(steps, "raw_intake", "stored", payload=raw_record_ids)
        if len(raw_records) != 1:
            diagnostics.append(
                _manual_diag(
                    "single_observation_required",
                    "Manual ingestion orchestration expects exactly one raw record.",
                    stage="raw_intake",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                steps=steps,
                diagnostics=diagnostics,
            )
        raw_record = raw_records[0]

        normalization_result = self.normalize_raw_record(
            raw_record.raw_record_id,
            normalizer=normalizer,
        )
        _manual_step(
            steps,
            "normalization",
            normalization_result.status.value,
            payload=normalization_result,
        )
        if normalization_result.manual_review_required:
            diagnostics.append(
                _manual_diag(
                    "manual_review_required",
                    "Normalizer marked this observation as requiring manual review.",
                    stage="normalization",
                )
            )
        if normalization_result.status not in {
            NormalizationStatus.NORMALIZED,
            NormalizationStatus.REQUIRES_MANUAL_REVIEW,
        }:
            diagnostics.append(
                _manual_diag(
                    "normalization_not_usable",
                    "Normalization did not produce proposal-ready data.",
                    stage="normalization",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                steps=steps,
                diagnostics=diagnostics,
            )

        try:
            attachment_result = self.attach_provenance_from_normalized_intake(
                _intake_provenance_definition_from_manual_run(
                    request,
                    raw_record=raw_record,
                    normalization_result=normalization_result,
                ),
                provenance_service=provenance_service,
            )
        except ValueError as exc:
            diagnostics.append(
                _manual_diag(
                    "provenance_attachment_failed",
                    str(exc),
                    stage="provenance_attachment",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                steps=steps,
                diagnostics=diagnostics,
            )
        _manual_step(
            steps,
            "provenance_attachment",
            attachment_result.observation_outcome,
            payload=attachment_result,
        )
        if attachment_result.manual_review_required:
            diagnostics.append(
                _manual_diag(
                    "manual_review_required",
                    "Provenance attachment preserved manual-review-required state.",
                    stage="provenance_attachment",
                )
            )

        fact_id = (
            request.requested_fact_id
            or (
                normalization_result.observation.proposed_fact_id
                if normalization_result.observation is not None
                else None
            )
            or raw_record.raw_record_id
        )
        try:
            proposal = self.propose_canonical_fact(
                raw_record_id=raw_record.raw_record_id,
                fact_id=fact_id,
            )
        except (KeyError, ValueError) as exc:
            diagnostics.append(
                _manual_diag(
                    "proposal_failed",
                    str(exc),
                    stage="proposal",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                steps=steps,
                diagnostics=diagnostics,
            )
        _manual_step(steps, "proposal", "proposed", payload=proposal)

        if request.mode is ManualIngestionRunMode.DRY_RUN_ONLY:
            diagnostics.append(
                _manual_diag(
                    "dry_run_stopped_before_linking",
                    "Dry-run mode stops before proposal review/linking.",
                    stage="proposal_review",
                )
            )
            return _manual_run_result(
                request,
                status=_manual_completed_status(diagnostics),
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                steps=steps,
                diagnostics=diagnostics,
            )

        if request.review_decision is None:
            diagnostics.append(
                _manual_diag(
                    "review_decision_required",
                    "Manual ingestion cannot link a proposal without an explicit review decision.",
                    stage="proposal_review",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                steps=steps,
                diagnostics=diagnostics,
            )

        review_result = self.review_and_link_canonical_fact_proposal(
            proposal,
            request.review_decision,
            provenance_service=provenance_service,
        )
        _manual_step(
            steps,
            "proposal_review",
            review_result.approval_status.value,
            payload=review_result,
        )
        if review_result.approval_status is not ProposalReviewStatus.LINKED_TO_SOURCE:
            diagnostics.append(
                _manual_diag(
                    "proposal_not_linked",
                    "Proposal review did not create a source link.",
                    stage="proposal_review",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                steps=steps,
                diagnostics=diagnostics,
            )

        write_plan = self.plan_canonical_fact_write(proposal, review_result)
        _manual_step(steps, "write_plan", write_plan.status.value, payload=write_plan)

        if request.mode is ManualIngestionRunMode.LINK_ONLY:
            return _manual_run_result(
                request,
                status=_manual_completed_status(diagnostics),
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                write_plan=write_plan,
                steps=steps,
                diagnostics=diagnostics,
            )

        if request.write_execution_decision is None:
            diagnostics.append(
                _manual_diag(
                    "write_execution_decision_required",
                    "Canonical write execution requires an explicit write approval decision.",
                    stage="write_execution",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                write_plan=write_plan,
                steps=steps,
                diagnostics=diagnostics,
            )

        write_execution_result = self.execute_canonical_write_plan(
            write_plan,
            request.write_execution_decision,
        )
        _manual_step(
            steps,
            "write_execution",
            write_execution_result.status.value,
            payload=write_execution_result,
        )
        if write_execution_result.status is not CanonicalWriteExecutionStatus.EXECUTED:
            diagnostics.append(
                _manual_diag(
                    "write_not_executed",
                    "Canonical write execution did not mutate a canonical row.",
                    stage="write_execution",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                write_plan=write_plan,
                write_execution_result=write_execution_result,
                steps=steps,
                diagnostics=diagnostics,
            )

        refresh_plan = self.plan_post_write_refresh(write_execution_result)
        _manual_step(
            steps,
            "refresh_plan",
            refresh_plan.status.value,
            payload=refresh_plan,
        )
        if request.mode is ManualIngestionRunMode.EXECUTE_WRITE_WITH_APPROVAL:
            return _manual_run_result(
                request,
                status=_manual_completed_status(diagnostics),
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                write_plan=write_plan,
                write_execution_result=write_execution_result,
                refresh_plan=refresh_plan,
                steps=steps,
                diagnostics=diagnostics,
            )

        if request.refresh_execution_decision is None:
            diagnostics.append(
                _manual_diag(
                    "refresh_execution_decision_required",
                    "Refresh execution requires a separate explicit refresh approval decision.",
                    stage="refresh_execution",
                )
            )
            return _manual_run_result(
                request,
                status=ManualIngestionRunStatus.STOPPED,
                adapter_result=adapter_result,
                raw_records_created=raw_record_ids,
                normalization_result=normalization_result,
                provenance_attachment_result=attachment_result,
                canonical_proposal=proposal,
                proposal_review_result=review_result,
                write_plan=write_plan,
                write_execution_result=write_execution_result,
                refresh_plan=refresh_plan,
                steps=steps,
                diagnostics=diagnostics,
            )

        refresh_decision = _refresh_decision_for_generated_plan(
            request.refresh_execution_decision,
            refresh_plan=refresh_plan,
            write_plan=write_plan,
            diagnostics=diagnostics,
        )
        refresh_execution_result = self.execute_post_write_refresh_plan(
            refresh_plan,
            refresh_decision,
        )
        _manual_step(
            steps,
            "refresh_execution",
            refresh_execution_result.status.value,
            payload=refresh_execution_result,
        )
        return _manual_run_result(
            request,
            status=_manual_completed_status(diagnostics),
            adapter_result=adapter_result,
            raw_records_created=raw_record_ids,
            normalization_result=normalization_result,
            provenance_attachment_result=attachment_result,
            canonical_proposal=proposal,
            proposal_review_result=review_result,
            write_plan=write_plan,
            write_execution_result=write_execution_result,
            refresh_plan=refresh_plan,
            refresh_execution_result=refresh_execution_result,
            steps=steps,
            diagnostics=diagnostics,
        )

    def attach_provenance(
        self, attachment: ProvenanceAttachment
    ) -> RawIngestionRecord:
        record = self._require_record(attachment.raw_record_id)
        if self._repo.get_source_ref(attachment.source_id) is None:
            raise KeyError(f"source ref not found: {attachment.source_id}")
        if self._repo.get_observation(attachment.observation_id) is None:
            raise KeyError(f"source observation not found: {attachment.observation_id}")
        if (
            record.source_id == attachment.source_id
            and record.observation_id == attachment.observation_id
        ):
            return record

        record.source_id = attachment.source_id
        record.observation_id = attachment.observation_id
        record.version = next_version(record.version)
        self._repo.flush()
        return record

    def record_normalization_result(
        self, result: NormalizationResult
    ) -> RawIngestionRecord:
        record = self._require_record(result.raw_record_id)
        record.normalization_status = result.status.value
        record.normalized_payload = result.normalized_payload
        record.intended_fact_type = (
            result.intended_fact_type.value
            if result.intended_fact_type is not None
            else record.intended_fact_type
        )
        record.parsing_notes = result.parsing_notes
        record.parsing_errors = (
            list(result.parsing_errors) if result.parsing_errors else None
        )
        if result.status is NormalizationStatus.REJECTED:
            record.ingestion_status = IngestionStatus.REJECTED.value
        elif record.ingestion_status == IngestionStatus.RECEIVED.value:
            record.ingestion_status = IngestionStatus.STORED.value
        record.version = next_version(record.version)
        self._repo.flush()
        return record

    def normalize_raw_record(
        self,
        raw_record_id: str,
        *,
        normalizer: SourceNormalizer,
    ) -> NormalizerResult:
        """Normalize raw intake and store the normalization result only."""
        record = self._require_record(raw_record_id)
        result = normalizer.normalize(record)
        self.record_normalization_result(result.to_normalization_result())
        return result

    def attach_provenance_from_normalized_intake(
        self,
        definition: IntakeProvenanceDefinition,
        *,
        provenance_service: ProvenanceService,
    ) -> IntakeProvenanceAttachmentResult:
        """Create/reuse provenance records and attach them to normalized intake.

        This method is explicit by design: adapters and normalizers never call it
        implicitly, and it still does not create canonical facts.
        """
        record = self._require_record(definition.raw_record_id)
        if record.normalization_status not in {
            NormalizationStatus.NORMALIZED.value,
            NormalizationStatus.REQUIRES_MANUAL_REVIEW.value,
        }:
            raise ValueError("raw intake must be normalized before provenance attachment")
        if record.normalized_payload is None:
            raise ValueError("normalized intake requires normalized_payload")

        acceptability = SOURCE_TYPE_DEFAULT_ACCEPTABILITY[definition.source_type]
        if (
            definition.source_type is SourceType.LLM_GENERATED
            or acceptability is SourceAcceptability.DISALLOWED
        ):
            raise ValueError(
                f"source type {definition.source_type.value!r} is disallowed "
                "as factual provenance"
            )

        manual_review_required = (
            acceptability is SourceAcceptability.MANUAL_REVIEW_REQUIRED
            or _normalization_manual_review_required(record.normalized_payload)
            or record.normalization_status
            == NormalizationStatus.REQUIRES_MANUAL_REVIEW.value
        )
        warnings: list[str] = []
        if manual_review_required:
            warnings.append(
                "manual_review_required: provenance attached but not fully trusted"
            )
        if acceptability is SourceAcceptability.ALLOWED_WITH_CAUTION:
            warnings.append("source_allowed_with_caution")

        collected_at = definition.collected_at or record.collected_at
        observed_at = (
            definition.observed_at
            or record.observed_at
            or definition.collected_at
            or record.collected_at
        )
        observation_status = (
            definition.observation_status
            or _normalization_observation_status(record.normalized_payload)
            or ObservationStatus.UNKNOWN
        )
        notes = _attachment_notes(
            definition.notes,
            record.parsing_notes,
            manual_review_required=manual_review_required,
        )

        _, source_outcome = provenance_service.upsert_source_ref(
            SourceRefDefinition(
                source_id=definition.source_id,
                source_type=definition.source_type,
                source_name=definition.source_name,
                url_or_provider=definition.url_or_provider,
                collected_at=collected_at,
                observed_at=observed_at,
                license_or_terms_category=definition.license_or_terms_category,
                confidence=definition.confidence,
                data_origin=definition.data_origin,
                notes=notes,
            )
        )
        _, observation_outcome = provenance_service.upsert_observation(
            SourceObservationDefinition(
                observation_id=definition.observation_id,
                source_id=definition.source_id,
                collected_at=collected_at,
                observed_at=observed_at,
                data_origin=definition.data_origin,
                observation_status=observation_status,
                confidence=definition.confidence,
                notes=notes,
            )
        )
        self.attach_provenance(
            ProvenanceAttachment(
                raw_record_id=definition.raw_record_id,
                source_id=definition.source_id,
                observation_id=definition.observation_id,
            )
        )
        return IntakeProvenanceAttachmentResult(
            raw_record_id=definition.raw_record_id,
            source_id=definition.source_id,
            observation_id=definition.observation_id,
            source_ref_outcome=source_outcome,
            observation_outcome=observation_outcome,
            source_acceptability=acceptability,
            manual_review_required=manual_review_required,
            warnings=tuple(warnings),
        )

    def propose_canonical_fact(
        self,
        *,
        raw_record_id: str,
        fact_id: str,
        fact_field: str | None = None,
    ) -> CanonicalFactProposal:
        record = self._require_record(raw_record_id)
        if record.normalization_status != NormalizationStatus.NORMALIZED.value:
            raise ValueError("raw intake must be normalized before fact proposal")
        if record.normalized_payload is None:
            raise ValueError("normalized fact proposal requires normalized_payload")
        if record.intended_fact_type is None:
            raise ValueError("normalized fact proposal requires intended_fact_type")
        if record.source_id is None or record.observation_id is None:
            raise ValueError("canonical fact proposals require provenance attachment")

        return CanonicalFactProposal.from_intake(
            raw_record_id=record.raw_record_id,
            intent=CanonicalFactIntent(record.intended_fact_type),
            fact_id=fact_id,
            fact_field=fact_field,
            normalized_payload=record.normalized_payload,
            source_id=record.source_id,
            observation_id=record.observation_id,
        )

    def review_and_link_canonical_fact_proposal(
        self,
        proposal: CanonicalFactProposal,
        decision: ProposalReviewDecision,
        *,
        provenance_service: ProvenanceService,
    ) -> ProposalReviewResult:
        """Review a provenance-attached proposal and optionally link its source.

        Approval creates or reuses a FactSourceLink only. It does not write
        canonical company, region, presence, hiring, entry-level, score, output,
        job, or refresh rows.
        """
        record = self._require_record(proposal.raw_record_id)
        if record.normalization_status not in {
            NormalizationStatus.NORMALIZED.value,
            NormalizationStatus.REQUIRES_MANUAL_REVIEW.value,
        }:
            raise ValueError("raw intake must be normalized before proposal review")
        if record.normalized_payload is None:
            raise ValueError("proposal review requires normalized_payload")
        if record.source_id is None or record.observation_id is None:
            raise ValueError("proposal review requires provenance attachment")
        if proposal.source_id != record.source_id:
            raise ValueError("proposal source_id does not match raw intake")
        if proposal.observation_id != record.observation_id:
            raise ValueError("proposal observation_id does not match raw intake")
        if record.intended_fact_type is None:
            raise ValueError("proposal review requires intended_fact_type")
        if proposal.intent is not CanonicalFactIntent(record.intended_fact_type):
            raise ValueError("proposal intent does not match raw intake")
        if proposal.normalized_payload != record.normalized_payload:
            raise ValueError("proposal payload does not match normalized intake")

        observation = self._repo.get_observation(proposal.observation_id)
        if observation is None:
            raise KeyError(f"source observation not found: {proposal.observation_id}")

        diagnostics: list[str] = []
        if decision.status is ProposalReviewStatus.REJECTED:
            diagnostics.append("proposal_rejected_by_reviewer")
            return _proposal_review_result(
                proposal,
                decision,
                status=ProposalReviewStatus.REJECTED,
                diagnostics=diagnostics,
            )
        if decision.status is not ProposalReviewStatus.APPROVED_FOR_LINKING:
            diagnostics.append(f"unsupported_review_status:{decision.status.value}")
            return _proposal_review_result(
                proposal,
                decision,
                status=ProposalReviewStatus.FAILED,
                diagnostics=diagnostics,
            )

        source_type = SourceType(observation.source_type)
        acceptability = SOURCE_TYPE_DEFAULT_ACCEPTABILITY[source_type]
        if (
            source_type is SourceType.LLM_GENERATED
            or acceptability is SourceAcceptability.DISALLOWED
        ):
            diagnostics.append(f"source_type_disallowed:{source_type.value}")
            return _proposal_review_result(
                proposal,
                decision,
                status=ProposalReviewStatus.FAILED,
                diagnostics=diagnostics,
            )
        if acceptability is SourceAcceptability.ALLOWED_WITH_CAUTION:
            diagnostics.append("source_allowed_with_caution")

        manual_review_required = _proposal_manual_review_required(
            record,
            source_type=source_type,
            observation_notes=observation.notes,
        )
        has_manual_review_override = (
            decision.override_manual_review and decision.reviewer_note is not None
        )
        if manual_review_required and not has_manual_review_override:
            diagnostics.append("manual_review_required_before_linking")
            return _proposal_review_result(
                proposal,
                decision,
                status=ProposalReviewStatus.REQUIRES_MANUAL_REVIEW,
                diagnostics=diagnostics,
                manual_review_required=True,
            )
        if manual_review_required:
            diagnostics.append("manual_review_override_recorded")

        link_id = _proposal_fact_source_link_id(proposal)
        _, outcome = provenance_service.upsert_fact_source_link(
            FactSourceLinkDefinition(
                link_id=link_id,
                observation_id=proposal.observation_id,
                fact_type=proposal.fact_type,
                fact_id=proposal.fact_id,
                fact_field=proposal.fact_field,
                data_origin=DataOrigin(observation.data_origin),
                observation_status=ObservationStatus(observation.observation_status),
                confidence=Confidence(observation.confidence),
                notes=_proposal_review_notes(
                    decision.reviewer_note,
                    manual_review_override=manual_review_required,
                ),
            )
        )
        return _proposal_review_result(
            proposal,
            decision,
            status=ProposalReviewStatus.LINKED_TO_SOURCE,
            diagnostics=diagnostics,
            fact_source_link_id=link_id,
            fact_source_link_outcome=outcome,
            manual_review_required=manual_review_required,
        )

    def plan_canonical_fact_write(
        self,
        proposal: CanonicalFactProposal,
        review_result: ProposalReviewResult,
    ) -> CanonicalWritePlan:
        """Build a dry-run canonical write plan for a source-linked proposal.

        The returned plan is descriptive only. It does not write canonical
        domain rows, create provenance links, trigger scores, or rebuild
        outputs.
        """
        record = self._require_record(proposal.raw_record_id)
        if record.normalization_status not in {
            NormalizationStatus.NORMALIZED.value,
            NormalizationStatus.REQUIRES_MANUAL_REVIEW.value,
        }:
            raise ValueError("raw intake must be normalized before write planning")
        if record.normalized_payload is None:
            raise ValueError("write planning requires normalized_payload")
        if record.source_id is None or record.observation_id is None:
            raise ValueError("write planning requires provenance attachment")
        _validate_proposal_matches_record(proposal, record)

        if review_result.raw_record_id != proposal.raw_record_id:
            raise ValueError("review result raw_record_id does not match proposal")
        if review_result.proposed_fact_id != proposal.fact_id:
            raise ValueError("review result proposed_fact_id does not match proposal")
        if review_result.fact_type is not proposal.fact_type:
            raise ValueError("review result fact_type does not match proposal")
        if review_result.source_id != proposal.source_id:
            raise ValueError("review result source_id does not match proposal")
        if review_result.observation_id != proposal.observation_id:
            raise ValueError("review result observation_id does not match proposal")

        base_diagnostics: list[CanonicalWriteDiagnostic] = []
        observation = self._repo.get_observation(proposal.observation_id)
        confidence = (
            Confidence(observation.confidence)
            if observation is not None
            else Confidence.UNKNOWN
        )
        observation_status = (
            ObservationStatus(observation.observation_status)
            if observation is not None
            else ObservationStatus.UNKNOWN
        )

        if review_result.approval_status is ProposalReviewStatus.REJECTED:
            base_diagnostics.append(
                _write_diag(
                    "proposal_rejected",
                    "Rejected proposals cannot be planned for canonical writes.",
                )
            )
            return _write_plan(
                proposal,
                status=CanonicalWritePlanStatus.REJECTED,
                target_entity_type=_target_entity_type_for(proposal.intent),
                provenance_link_id=review_result.fact_source_link_id,
                confidence=confidence,
                observation_status=observation_status,
                diagnostics=base_diagnostics,
            )

        if (
            review_result.approval_status is not ProposalReviewStatus.LINKED_TO_SOURCE
            or review_result.fact_source_link_id is None
        ):
            base_diagnostics.append(
                _write_diag(
                    "proposal_not_source_linked",
                    "Canonical write planning requires an approved source-linked proposal.",
                )
            )
            return _write_plan(
                proposal,
                status=CanonicalWritePlanStatus.FAILED,
                target_entity_type=_target_entity_type_for(proposal.intent),
                confidence=confidence,
                observation_status=observation_status,
                diagnostics=base_diagnostics,
            )

        link = self._repo.get_fact_source_link(review_result.fact_source_link_id)
        if link is None:
            base_diagnostics.append(
                _write_diag(
                    "fact_source_link_not_found",
                    "The approved proposal link does not exist.",
                )
            )
            return _write_plan(
                proposal,
                status=CanonicalWritePlanStatus.FAILED,
                target_entity_type=_target_entity_type_for(proposal.intent),
                provenance_link_id=review_result.fact_source_link_id,
                confidence=confidence,
                observation_status=observation_status,
                diagnostics=base_diagnostics,
            )
        if (
            link.observation_id != proposal.observation_id
            or link.fact_type != proposal.fact_type.value
            or link.fact_id != proposal.fact_id
            or link.fact_field != proposal.fact_field
        ):
            base_diagnostics.append(
                _write_diag(
                    "fact_source_link_mismatch",
                    "The approved source link does not match the proposal.",
                )
            )
            return _write_plan(
                proposal,
                status=CanonicalWritePlanStatus.FAILED,
                target_entity_type=_target_entity_type_for(proposal.intent),
                provenance_link_id=review_result.fact_source_link_id,
                confidence=confidence,
                observation_status=observation_status,
                diagnostics=base_diagnostics,
            )

        return self._build_canonical_write_plan(
            proposal,
            provenance_link_id=review_result.fact_source_link_id,
            confidence=Confidence(link.confidence),
            observation_status=ObservationStatus(link.observation_status),
            base_diagnostics=base_diagnostics,
            manual_review_required=review_result.manual_review_required,
        )

    def execute_canonical_write_plan(
        self,
        plan: CanonicalWritePlan,
        decision: CanonicalWriteExecutionDecision,
    ) -> CanonicalWriteExecutionResult:
        """Execute a manually approved canonical write plan.

        This is the first ingestion path that mutates canonical domain rows,
        and only after an explicit approval decision. It still does not trigger
        scoring, outputs, jobs, audits, or external collection.
        """
        diagnostics: list[CanonicalWriteExecutionDiagnostic] = []
        if decision.plan_id != plan.plan_id:
            diagnostics.append(
                _execution_diag(
                    "plan_id_mismatch",
                    "Execution decision does not match the write plan.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if not decision.approved:
            diagnostics.append(
                _execution_diag(
                    "execution_not_approved",
                    decision.rejection_reason or "Execution decision was not approved.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.REJECTED,
                diagnostics=diagnostics,
            )
        if plan.status in {
            CanonicalWritePlanStatus.REJECTED,
            CanonicalWritePlanStatus.FAILED,
            CanonicalWritePlanStatus.UNSUPPORTED,
            CanonicalWritePlanStatus.REQUIRES_MANUAL_REVIEW,
        }:
            diagnostics.append(
                _execution_diag(
                    "plan_status_not_executable",
                    f"Write plan status {plan.status.value!r} is not executable.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if not plan.dry_run:
            diagnostics.append(
                _execution_diag(
                    "plan_not_dry_run",
                    "Only dry-run write plans can enter the manual execution gate.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if not plan.operations:
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.NO_OP,
                diagnostics=diagnostics,
            )
        if len(plan.operations) != 1:
            diagnostics.append(
                _execution_diag(
                    "multiple_operations_unsupported",
                    "Layer 4G executes one canonical operation per plan.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )

        operation = plan.operations[0]
        if operation.operation_type is CanonicalWriteOperationType.NO_OP:
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.NO_OP,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        if operation.operation_type not in {
            CanonicalWriteOperationType.CREATE,
            CanonicalWriteOperationType.UPDATE,
        }:
            diagnostics.append(
                _execution_diag(
                    "operation_not_executable",
                    f"Operation {operation.operation_type.value!r} is not executable.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        if operation.provenance_link_id is None:
            diagnostics.append(
                _execution_diag(
                    "missing_fact_source_link",
                    "Canonical writes require a FactSourceLink-backed operation.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        link = self._repo.get_fact_source_link(operation.provenance_link_id)
        if link is None:
            diagnostics.append(
                _execution_diag(
                    "fact_source_link_not_found",
                    "The operation FactSourceLink does not exist.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )

        unsafe_count = _unsafe_count_write(operation)
        if unsafe_count is not None:
            diagnostics.append(unsafe_count)
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )

        changes = _execution_changes(operation, link)
        if operation.target_entity_type in {
            "company_region_presence",
            "company_region_hiring",
            "company_region_entry_level",
        }:
            supplied_region_id = _string_change(changes, "region_id")
            resolution = GeographicResolver(
                RegionRepository(self._repo.session)
            ).resolve(supplied_region_id)
            if not resolution.resolved or resolution.region_id is None:
                diagnostics.append(
                    _execution_diag(
                        "noncanonical_region_dependency",
                        "Company-region writes require an unambiguous canonical Region.",
                    )
                )
                return _execution_result(
                    plan,
                    status=CanonicalWriteExecutionStatus.BLOCKED,
                    operation_type=operation.operation_type,
                    diagnostics=diagnostics,
                )
            changes["region_id"] = resolution.region_id
        target = self._get_execution_target(operation, changes=changes)
        if target is None and operation.operation_type is CanonicalWriteOperationType.UPDATE:
            diagnostics.append(
                _execution_diag(
                    "update_target_not_found",
                    "Update operation target does not exist.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        if target is not None:
            if _target_matches(target, changes):
                return _execution_result(
                    plan,
                    status=CanonicalWriteExecutionStatus.ALREADY_APPLIED,
                    operation_type=operation.operation_type,
                    diagnostics=diagnostics,
                )
            if operation.operation_type is CanonicalWriteOperationType.CREATE:
                diagnostics.append(
                    _execution_diag(
                        "create_target_already_exists",
                        "Create operation target already exists with different values.",
                    )
                )
                return _execution_result(
                    plan,
                    status=CanonicalWriteExecutionStatus.BLOCKED,
                    operation_type=operation.operation_type,
                    diagnostics=diagnostics,
                )
            _apply_execution_changes(target, changes)
            target.version = next_version(target.version)
            self._repo.flush()
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.EXECUTED,
                operation_type=CanonicalWriteOperationType.UPDATE,
                diagnostics=diagnostics,
                canonical_domain_mutated=True,
            )

        target = self._build_execution_target(operation, changes)
        if target is None:
            diagnostics.append(
                _execution_diag(
                    "execution_mapping_unsupported",
                    "The write plan target is not supported by Layer 4G execution.",
                )
            )
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        missing_dependency = self._missing_execution_dependency(operation, changes)
        if missing_dependency is not None:
            diagnostics.append(missing_dependency)
            return _execution_result(
                plan,
                status=CanonicalWriteExecutionStatus.BLOCKED,
                operation_type=operation.operation_type,
                diagnostics=diagnostics,
            )
        self._add_execution_target(operation.target_entity_type, target)
        self._repo.flush()
        return _execution_result(
            plan,
            status=CanonicalWriteExecutionStatus.EXECUTED,
            operation_type=operation.operation_type,
            diagnostics=diagnostics,
            canonical_domain_mutated=True,
        )

    def plan_post_write_refresh(
        self,
        execution_result: CanonicalWriteExecutionResult,
    ) -> PostWriteRefreshPlan:
        """Describe downstream refresh work after a canonical write.

        This is dry-run dependency planning only. It does not recompute scores,
        rebuild outputs, enqueue jobs, run audits, or mutate refresh state.
        """
        diagnostics: list[PostWriteRefreshDiagnostic] = []
        if execution_result.status is CanonicalWriteExecutionStatus.REJECTED:
            diagnostics.append(
                _refresh_diag(
                    "execution_not_approved",
                    "Rejected or unapproved write executions cannot produce refresh plans.",
                )
            )
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.REJECTED,
                diagnostics=diagnostics,
            )
        if execution_result.status in {
            CanonicalWriteExecutionStatus.BLOCKED,
            CanonicalWriteExecutionStatus.FAILED,
        }:
            diagnostics.append(
                _refresh_diag(
                    "execution_not_successful",
                    f"Execution status {execution_result.status.value!r} cannot "
                    "produce a refresh plan.",
                )
            )
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.FAILED,
                diagnostics=diagnostics,
            )
        if execution_result.status in {
            CanonicalWriteExecutionStatus.NO_OP,
            CanonicalWriteExecutionStatus.ALREADY_APPLIED,
        }:
            diagnostics.append(
                _refresh_diag(
                    "execution_no_canonical_change",
                    "No canonical row changed, so no downstream refresh is planned.",
                )
            )
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.NO_OP,
                diagnostics=diagnostics,
            )
        if not execution_result.canonical_domain_mutated:
            diagnostics.append(
                _refresh_diag(
                    "execution_did_not_mutate_canonical_domain",
                    "Refresh planning requires an executed canonical domain mutation.",
                )
            )
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.NO_OP,
                diagnostics=diagnostics,
            )

        changed_type = execution_result.target_entity_type
        changed_id = execution_result.target_identifier
        affected_company_ids: set[str] = set()
        affected_region_ids: set[str] = set()

        if changed_type == "companies":
            if changed_id is None:
                diagnostics.append(_missing_changed_entity_id_diag())
            else:
                affected_company_ids.add(changed_id)
                if self._repo.get_company(changed_id) is None:
                    diagnostics.append(
                        _refresh_diag(
                            "changed_company_not_found",
                            "The executed company write target could not be found.",
                        )
                    )
                affected_region_ids.update(
                    self._affected_region_ids_for_company(changed_id)
                )
        elif changed_type == "regions":
            if changed_id is None:
                diagnostics.append(_missing_changed_entity_id_diag())
            else:
                affected_region_ids.add(changed_id)
                if self._repo.get_region(changed_id) is None:
                    diagnostics.append(
                        _refresh_diag(
                            "changed_region_not_found",
                            "The executed region write target could not be found.",
                        )
                    )
        elif changed_type == "company_region_presence":
            context = self._presence_refresh_context(changed_id, diagnostics)
            if context is not None:
                company_id, region_id = context
                affected_company_ids.add(company_id)
                affected_region_ids.add(region_id)
        elif changed_type == "company_region_hiring":
            context = self._hiring_refresh_context(changed_id, diagnostics)
            if context is not None:
                company_id, region_id = context
                affected_company_ids.add(company_id)
                affected_region_ids.add(region_id)
        elif changed_type == "company_region_entry_level":
            context = self._entry_level_refresh_context(changed_id, diagnostics)
            if context is not None:
                company_id, region_id = context
                affected_company_ids.add(company_id)
                affected_region_ids.add(region_id)
        else:
            diagnostics.append(
                _refresh_diag(
                    "unsupported_refresh_mapping",
                    "No post-write refresh mapping is defined for this execution target.",
                )
            )
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.UNSUPPORTED,
                affected_region_ids=tuple(),
                affected_company_ids=tuple(),
                refresh_targets=(
                    _refresh_target(
                        PostWriteRefreshTargetType.UNKNOWN_OR_UNSUPPORTED,
                        target_id=changed_id,
                        reason="Layer 4H has no dependency mapping for this target.",
                    ),
                ),
                diagnostics=diagnostics,
            )

        if diagnostics and not (affected_company_ids or affected_region_ids):
            return _post_write_refresh_plan(
                execution_result,
                status=PostWriteRefreshPlanStatus.FAILED,
                diagnostics=diagnostics,
            )

        refresh_targets = _refresh_targets_for_scope(
            changed_type=changed_type,
            changed_id=changed_id,
            affected_company_ids=affected_company_ids,
            affected_region_ids=affected_region_ids,
        )
        return _post_write_refresh_plan(
            execution_result,
            status=PostWriteRefreshPlanStatus.PLANNED,
            affected_region_ids=tuple(sorted(affected_region_ids)),
            affected_company_ids=tuple(sorted(affected_company_ids)),
            refresh_targets=refresh_targets,
            diagnostics=diagnostics,
        )

    def execute_post_write_refresh_plan(
        self,
        plan: PostWriteRefreshPlan,
        decision: PostWriteRefreshExecutionDecision,
    ) -> PostWriteRefreshExecutionResult:
        """Execute a manually approved post-write refresh plan synchronously.

        Only already-supported local scoring/output builders are invoked. This
        method does not enqueue jobs, schedule workers, collect external data,
        create ingestion records, or mutate provenance links.
        """
        plan_id = _post_write_refresh_plan_id(plan)
        diagnostics: list[PostWriteRefreshExecutionDiagnostic] = []
        if decision.refresh_plan_id != plan_id:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_plan_id_mismatch",
                    "Refresh execution decision does not match the refresh plan.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if not decision.approved:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_execution_not_approved",
                    decision.rejection_reason
                    or "Refresh execution decision was not approved.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.REJECTED,
                diagnostics=diagnostics,
            )
        if decision.expected_target_count is not None and (
            decision.expected_target_count != len(plan.refresh_targets)
        ):
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_target_count_mismatch",
                    "Refresh execution decision target count does not match the plan.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if plan.status is PostWriteRefreshPlanStatus.NO_OP:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_plan_no_op",
                    "No-op refresh plans do not execute downstream refreshes.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.NO_OP,
                diagnostics=diagnostics,
            )
        if plan.status in {
            PostWriteRefreshPlanStatus.REJECTED,
            PostWriteRefreshPlanStatus.FAILED,
        }:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_plan_not_executable",
                    f"Refresh plan status {plan.status.value!r} is not executable.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if plan.status is PostWriteRefreshPlanStatus.UNSUPPORTED:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_plan_unsupported",
                    "Unsupported refresh plans cannot execute downstream refreshes.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.UNSUPPORTED,
                diagnostics=diagnostics,
            )
        if not plan.dry_run:
            diagnostics.append(
                _refresh_execution_diag(
                    "refresh_plan_not_dry_run",
                    "Only dry-run refresh plans can enter manual refresh execution.",
                )
            )
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.BLOCKED,
                diagnostics=diagnostics,
            )
        if not plan.refresh_targets:
            return _post_write_refresh_execution_result(
                plan,
                status=PostWriteRefreshExecutionStatus.NO_OP,
                diagnostics=diagnostics,
            )

        target_results = tuple(
            self._execute_refresh_target(target) for target in plan.refresh_targets
        )
        status = _overall_refresh_execution_status(target_results)
        return _post_write_refresh_execution_result(
            plan,
            status=status,
            target_results=target_results,
            diagnostics=diagnostics,
        )

    def _get_execution_target(
        self,
        operation: CanonicalWriteOperation,
        *,
        changes: dict[str, object] | None = None,
    ) -> object | None:
        target_id = operation.target_identifier
        if target_id is None:
            return None
        if operation.target_entity_type == "companies":
            return self._repo.get_company(target_id)
        if operation.target_entity_type == "regions":
            return self._repo.get_region(target_id)
        lookup_changes = changes or operation.proposed_field_changes
        company_id = _string_change(lookup_changes, "company_id")
        region_id = _string_change(lookup_changes, "region_id")
        if operation.target_entity_type == "company_region_presence":
            return (
                self._repo.get_presence_by_pair(company_id, region_id)
                if company_id and region_id
                else None
            )
        if operation.target_entity_type == "company_region_hiring":
            return (
                self._repo.get_hiring_by_pair(company_id, region_id)
                if company_id and region_id
                else None
            )
        if operation.target_entity_type == "company_region_entry_level":
            return (
                self._repo.get_entry_level_by_pair(company_id, region_id)
                if company_id and region_id
                else None
            )
        return None

    def _build_execution_target(
        self,
        operation: CanonicalWriteOperation,
        changes: dict[str, object],
    ) -> object | None:
        target_id = operation.target_identifier
        if target_id is None:
            return None
        if operation.target_entity_type == "companies":
            company_name = _string_change(changes, "company_name")
            normalized_name = _string_change(changes, "normalized_company_name")
            if not company_name or not normalized_name:
                return None
            return Company(
                company_id=target_id,
                company_name=company_name,
                normalized_company_name=normalized_name,
                sector_primary=changes.get("sector_primary"),
                sector_secondary=changes.get("sector_secondary"),
                public_or_private=changes.get("public_or_private"),
                prestige_score=changes.get("prestige_score"),
            )
        if operation.target_entity_type == "regions":
            region_name = _string_change(changes, "region_name")
            display_name = _string_change(changes, "display_name")
            region_type = _string_change(changes, "region_type")
            if not region_name or not display_name or not region_type:
                return None
            return Region(
                region_id=target_id,
                region_name=region_name,
                display_name=display_name,
                region_type=region_type,
                parent_region_id=changes.get("parent_region_id"),
                labor_market_group=changes.get("labor_market_group"),
                normalization_profile_id=changes.get("normalization_profile_id"),
            )
        company_id = _string_change(changes, "company_id")
        region_id = _string_change(changes, "region_id")
        if not company_id or not region_id:
            return None
        if operation.target_entity_type == "company_region_presence":
            presence_status = _string_change(changes, "presence_status")
            if not presence_status:
                return None
            return CompanyRegionPresence(
                presence_id=target_id,
                company_id=company_id,
                region_id=region_id,
                presence_status=presence_status,
                presence_basis=changes.get("presence_basis"),
                office_evidence_flag=bool(changes.get("office_evidence_flag", False)),
                operations_evidence_flag=bool(
                    changes.get("operations_evidence_flag", False)
                ),
                hiring_evidence_flag=bool(changes.get("hiring_evidence_flag", False)),
                presence_confidence=changes.get("presence_confidence"),
                source_refs=changes.get("source_refs"),
            )
        if operation.target_entity_type == "company_region_hiring":
            return CompanyRegionHiring(
                hiring_id=target_id,
                company_id=company_id,
                region_id=region_id,
                currently_hiring_flag=bool(
                    changes.get("currently_hiring_flag", False)
                ),
                active_posting_count_now=changes.get("active_posting_count_now"),
                posting_count_30d=changes.get("posting_count_30d"),
                posting_count_90d=changes.get("posting_count_90d"),
                annualized_trend_signal=changes.get("annualized_trend_signal"),
                seasonal_student_hiring_signal=changes.get(
                    "seasonal_student_hiring_signal"
                ),
                hiring_program_count=changes.get("hiring_program_count"),
                role_family_summary=changes.get("role_family_summary"),
                hiring_confidence=changes.get("hiring_confidence"),
                source_refs=changes.get("source_refs"),
            )
        if operation.target_entity_type == "company_region_entry_level":
            return CompanyRegionEntryLevel(
                entry_level_id=target_id,
                company_id=company_id,
                region_id=region_id,
                internship_count=changes.get("internship_count"),
                coop_count=changes.get("coop_count"),
                entry_level_full_time_count=changes.get(
                    "entry_level_full_time_count"
                ),
                formal_early_career_program_flag=bool(
                    changes.get("formal_early_career_program_flag", False)
                ),
                student_season_recurrence_signal=changes.get(
                    "student_season_recurrence_signal"
                ),
                entry_level_access_score=changes.get("entry_level_access_score"),
                entry_level_confidence=changes.get("entry_level_confidence"),
                source_refs=changes.get("source_refs"),
            )
        return None

    def _missing_execution_dependency(
        self,
        operation: CanonicalWriteOperation,
        changes: dict[str, object],
    ) -> CanonicalWriteExecutionDiagnostic | None:
        if operation.target_entity_type in {"companies", "regions"}:
            return None
        company_id = _string_change(changes, "company_id")
        region_id = _string_change(changes, "region_id")
        if not company_id or not region_id:
            return _execution_diag(
                "missing_pair_identifier",
                "Company-region writes require company_id and region_id.",
            )
        if self._repo.get_company(company_id) is None:
            return _execution_diag(
                "missing_company_dependency",
                "Company-region writes require an existing company.",
            )
        if self._repo.get_region(region_id) is None:
            return _execution_diag(
                "missing_region_dependency",
                "Company-region writes require an existing region.",
            )
        if operation.target_entity_type == "company_region_hiring":
            presence = self._repo.get_presence_by_pair(company_id, region_id)
            if presence is None or presence.presence_status != "present":
                return _execution_diag(
                    "missing_present_presence_dependency",
                    "Hiring writes require an existing present company-region row.",
                )
        if operation.target_entity_type == "company_region_entry_level":
            if self._repo.get_hiring_by_pair(company_id, region_id) is None:
                return _execution_diag(
                    "missing_hiring_dependency",
                    "Entry-level writes require an existing hiring row.",
                )
        return None

    def _add_execution_target(self, target_entity_type: str, target: object) -> None:
        if target_entity_type == "companies":
            self._repo.add_company(target)
        elif target_entity_type == "regions":
            self._repo.add_region(target)
        elif target_entity_type == "company_region_presence":
            self._repo.add_presence(target)
        elif target_entity_type == "company_region_hiring":
            self._repo.add_hiring(target)
        elif target_entity_type == "company_region_entry_level":
            self._repo.add_entry_level(target)

    def _affected_region_ids_for_company(self, company_id: str) -> set[str]:
        region_ids: set[str] = set()
        for row in self._repo.list_presence_by_company(company_id):
            region_ids.add(row.region_id)
        for row in self._repo.list_hiring_by_company(company_id):
            region_ids.add(row.region_id)
        for row in self._repo.list_entry_level_by_company(company_id):
            region_ids.add(row.region_id)
        return region_ids

    def _presence_refresh_context(
        self,
        presence_id: str | None,
        diagnostics: list[PostWriteRefreshDiagnostic],
    ) -> tuple[str, str] | None:
        if presence_id is None:
            diagnostics.append(_missing_changed_entity_id_diag())
            return None
        row = self._repo.get_presence(presence_id)
        if row is None:
            diagnostics.append(
                _refresh_diag(
                    "changed_presence_not_found",
                    "The executed presence write target could not be found.",
                )
            )
            return None
        return row.company_id, row.region_id

    def _hiring_refresh_context(
        self,
        hiring_id: str | None,
        diagnostics: list[PostWriteRefreshDiagnostic],
    ) -> tuple[str, str] | None:
        if hiring_id is None:
            diagnostics.append(_missing_changed_entity_id_diag())
            return None
        row = self._repo.get_hiring(hiring_id)
        if row is None:
            diagnostics.append(
                _refresh_diag(
                    "changed_hiring_not_found",
                    "The executed hiring write target could not be found.",
                )
            )
            return None
        return row.company_id, row.region_id

    def _entry_level_refresh_context(
        self,
        entry_level_id: str | None,
        diagnostics: list[PostWriteRefreshDiagnostic],
    ) -> tuple[str, str] | None:
        if entry_level_id is None:
            diagnostics.append(_missing_changed_entity_id_diag())
            return None
        row = self._repo.get_entry_level(entry_level_id)
        if row is None:
            diagnostics.append(
                _refresh_diag(
                    "changed_entry_level_not_found",
                    "The executed entry-level write target could not be found.",
                )
            )
            return None
        return row.company_id, row.region_id

    def _execute_refresh_target(
        self,
        target: PostWriteRefreshTarget,
    ) -> PostWriteRefreshTargetExecutionResult:
        if target.target_type is PostWriteRefreshTargetType.REGION_SCORE:
            return self._execute_region_score_refresh(target)
        if target.target_type is PostWriteRefreshTargetType.REGION_OUTPUT:
            return self._execute_region_output_refresh(target)
        if target.target_type is PostWriteRefreshTargetType.COMPANY_OUTPUT:
            return self._execute_company_output_refresh(target)
        if target.target_type is PostWriteRefreshTargetType.PROVENANCE_AUDIT:
            diagnostic = _refresh_execution_diag(
                "provenance_audit_refresh_deferred",
                "Layer 4I does not run provenance audits as part of refresh execution.",
                target_type=target.target_type,
                target_id=target.target_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.NO_OP,
                action="deferred",
                diagnostics=(diagnostic,),
            )
        diagnostic = _refresh_execution_diag(
            "refresh_target_unsupported",
            f"Refresh target {target.target_type.value!r} is not supported by Layer 4I.",
            target_type=target.target_type,
            target_id=target.target_id,
        )
        return _target_refresh_result(
            target,
            status=PostWriteRefreshExecutionStatus.UNSUPPORTED,
            diagnostics=(diagnostic,),
        )

    def _execute_region_score_refresh(
        self,
        target: PostWriteRefreshTarget,
    ) -> PostWriteRefreshTargetExecutionResult:
        region_id = target.region_id or target.target_id
        if region_id is None:
            diagnostic = _refresh_execution_diag(
                "missing_region_id",
                "Region score refresh target requires a region id.",
                target_type=target.target_type,
                target_id=target.target_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        service = self._region_scoring_service()
        try:
            row, action = service.upsert_for_recompute(region_id)
        except MissingRegionForScoring as exc:
            diagnostic = _refresh_execution_diag(
                "region_score_refresh_failed",
                str(exc),
                target_type=target.target_type,
                target_id=region_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        return _target_refresh_result(
            target,
            status=(
                PostWriteRefreshExecutionStatus.NO_OP
                if action == "unchanged"
                else PostWriteRefreshExecutionStatus.EXECUTED
            ),
            action=action,
            refreshed_artifact_id=row.region_score_id,
        )

    def _execute_region_output_refresh(
        self,
        target: PostWriteRefreshTarget,
    ) -> PostWriteRefreshTargetExecutionResult:
        region_id = target.region_id or target.target_id
        if region_id is None:
            diagnostic = _refresh_execution_diag(
                "missing_region_id",
                "Region output refresh target requires a region id.",
                target_type=target.target_type,
                target_id=target.target_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        service = self._output_assembly_service()
        try:
            result = service.build_region(region_id)
        except MissingRegionForOutput as exc:
            diagnostic = _refresh_execution_diag(
                "region_output_refresh_failed",
                str(exc),
                target_type=target.target_type,
                target_id=region_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        return _target_refresh_result(
            target,
            status=(
                PostWriteRefreshExecutionStatus.NO_OP
                if result.action == "unchanged"
                else PostWriteRefreshExecutionStatus.EXECUTED
            ),
            action=result.action,
            refreshed_artifact_id=(
                result.metadata.output_id if result.metadata is not None else None
            ),
        )

    def _execute_company_output_refresh(
        self,
        target: PostWriteRefreshTarget,
    ) -> PostWriteRefreshTargetExecutionResult:
        company_id = target.company_id or target.target_id
        if company_id is None:
            diagnostic = _refresh_execution_diag(
                "missing_company_id",
                "Company output refresh target requires a company id.",
                target_type=target.target_type,
                target_id=target.target_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        service = self._output_assembly_service()
        try:
            result = service.build_company(company_id)
        except MissingCompanyForOutput as exc:
            diagnostic = _refresh_execution_diag(
                "company_output_refresh_failed",
                str(exc),
                target_type=target.target_type,
                target_id=company_id,
            )
            return _target_refresh_result(
                target,
                status=PostWriteRefreshExecutionStatus.FAILED,
                diagnostics=(diagnostic,),
            )
        return _target_refresh_result(
            target,
            status=(
                PostWriteRefreshExecutionStatus.NO_OP
                if result.action == "unchanged"
                else PostWriteRefreshExecutionStatus.EXECUTED
            ),
            action=result.action,
            refreshed_artifact_id=(
                result.metadata.output_id if result.metadata is not None else None
            ),
        )

    def _region_scoring_service(self) -> RegionScoringService:
        session = self._repo.session
        return RegionScoringService(
            RegionScoreRepository(session),
            region_repo=RegionRepository(session),
        )

    def _output_assembly_service(self) -> OutputAssemblyService:
        session = self._repo.session
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

    def _require_record(self, raw_record_id: str) -> RawIngestionRecord:
        record = self._repo.get_raw_record(raw_record_id)
        if record is None:
            raise KeyError(f"raw ingestion record not found: {raw_record_id}")
        return record

    def _build_canonical_write_plan(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        if proposal.intent is CanonicalFactIntent.COMPANY:
            return self._plan_company(
                proposal,
                provenance_link_id=provenance_link_id,
                confidence=confidence,
                observation_status=observation_status,
                base_diagnostics=base_diagnostics,
                manual_review_required=manual_review_required,
            )
        if proposal.intent is CanonicalFactIntent.REGION:
            return self._plan_region(
                proposal,
                provenance_link_id=provenance_link_id,
                confidence=confidence,
                observation_status=observation_status,
                base_diagnostics=base_diagnostics,
                manual_review_required=manual_review_required,
            )
        if proposal.intent is CanonicalFactIntent.PRESENCE:
            return self._plan_presence(
                proposal,
                provenance_link_id=provenance_link_id,
                confidence=confidence,
                observation_status=observation_status,
                base_diagnostics=base_diagnostics,
                manual_review_required=manual_review_required,
            )
        if proposal.intent is CanonicalFactIntent.HIRING:
            return self._plan_hiring(
                proposal,
                provenance_link_id=provenance_link_id,
                confidence=confidence,
                observation_status=observation_status,
                base_diagnostics=base_diagnostics,
                manual_review_required=manual_review_required,
            )
        if proposal.intent in {
            CanonicalFactIntent.INTERNSHIPS_COOPS,
            CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
        }:
            return self._plan_entry_level(
                proposal,
                provenance_link_id=provenance_link_id,
                confidence=confidence,
                observation_status=observation_status,
                base_diagnostics=base_diagnostics,
                manual_review_required=manual_review_required,
            )
        return _unsupported_write_plan(
            proposal,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            diagnostics=base_diagnostics
            + [
                _write_diag(
                    "unsupported_mapping",
                    "No canonical dry-run mapping is defined for this fact intent.",
                )
            ],
        )

    def _plan_company(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        fields = proposal.normalized_payload
        company_id = _string_field(fields, "company_id")
        changes = _present_fields(
            fields,
            (
                "company_name",
                "normalized_company_name",
                "sector_primary",
                "sector_secondary",
                "public_or_private",
                "prestige_score",
            ),
        )
        if "normalized_company_name" not in changes and "company_name" in changes:
            changes["normalized_company_name"] = str(changes["company_name"]).lower()
        existing = self._repo.get_company(company_id) if company_id else None
        return _plan_against_existing(
            proposal,
            target_entity_type="companies",
            target_identifier=company_id,
            existing=existing,
            proposed_changes=changes,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            base_diagnostics=base_diagnostics,
            manual_review_required=manual_review_required,
        )

    def _plan_region(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        fields = proposal.normalized_payload
        region_id = _string_field(fields, "region_id")
        changes = _present_fields(
            fields,
            (
                "region_name",
                "display_name",
                "region_type",
                "parent_region_id",
                "labor_market_group",
                "normalization_profile_id",
            ),
        )
        existing = self._repo.get_region(region_id) if region_id else None
        return _plan_against_existing(
            proposal,
            target_entity_type="regions",
            target_identifier=region_id,
            existing=existing,
            proposed_changes=changes,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            base_diagnostics=base_diagnostics,
            manual_review_required=manual_review_required,
        )

    def _plan_presence(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        fields = proposal.normalized_payload
        company_id = _string_field(fields, "company_id")
        region_id = _string_field(fields, "region_id")
        target_id = _pair_target_id("presence", company_id, region_id)
        changes = _present_fields(
            fields,
            (
                "company_id",
                "region_id",
                "presence_status",
                "presence_basis",
                "office_evidence_flag",
                "operations_evidence_flag",
                "hiring_evidence_flag",
                "presence_confidence",
            ),
        )
        existing = (
            self._repo.get_presence_by_pair(company_id, region_id)
            if company_id and region_id
            else None
        )
        return _plan_against_existing(
            proposal,
            target_entity_type="company_region_presence",
            target_identifier=existing.presence_id if existing else target_id,
            existing=existing,
            proposed_changes=changes,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            base_diagnostics=base_diagnostics,
            manual_review_required=manual_review_required,
            conflict_fields=frozenset({"presence_status"}),
        )

    def _plan_hiring(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        fields = proposal.normalized_payload
        company_id = _string_field(fields, "company_id")
        region_id = _string_field(fields, "region_id")
        target_id = _pair_target_id("hiring", company_id, region_id)
        changes = _present_fields(
            fields,
            (
                "company_id",
                "region_id",
                "currently_hiring_flag",
                "annualized_trend_signal",
                "seasonal_student_hiring_signal",
                "role_family_summary",
                "hiring_confidence",
            ),
        )
        value_statuses: dict[str, str] = {}
        diagnostics = list(base_diagnostics)
        for field_name in (
            "active_posting_count_now",
            "posting_count_30d",
            "posting_count_90d",
            "hiring_program_count",
        ):
            _add_count_change(
                fields,
                field_name,
                changes,
                value_statuses,
                diagnostics,
            )
        existing = (
            self._repo.get_hiring_by_pair(company_id, region_id)
            if company_id and region_id
            else None
        )
        return _plan_against_existing(
            proposal,
            target_entity_type="company_region_hiring",
            target_identifier=existing.hiring_id if existing else target_id,
            existing=existing,
            proposed_changes=changes,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            base_diagnostics=diagnostics,
            manual_review_required=manual_review_required,
            value_statuses=value_statuses,
        )

    def _plan_entry_level(
        self,
        proposal: CanonicalFactProposal,
        *,
        provenance_link_id: str,
        confidence: Confidence,
        observation_status: ObservationStatus,
        base_diagnostics: list[CanonicalWriteDiagnostic],
        manual_review_required: bool,
    ) -> CanonicalWritePlan:
        fields = proposal.normalized_payload
        company_id = _string_field(fields, "company_id")
        region_id = _string_field(fields, "region_id")
        target_id = _pair_target_id("entry_level", company_id, region_id)
        changes = _present_fields(
            fields,
            (
                "company_id",
                "region_id",
                "formal_early_career_program_flag",
                "student_season_recurrence_signal",
                "entry_level_access_score",
                "entry_level_confidence",
            ),
        )
        value_statuses: dict[str, str] = {}
        diagnostics = list(base_diagnostics)
        for field_name in (
            "internship_count",
            "coop_count",
            "entry_level_full_time_count",
        ):
            _add_count_change(
                fields,
                field_name,
                changes,
                value_statuses,
                diagnostics,
            )
        existing = (
            self._repo.get_entry_level_by_pair(company_id, region_id)
            if company_id and region_id
            else None
        )
        return _plan_against_existing(
            proposal,
            target_entity_type="company_region_entry_level",
            target_identifier=existing.entry_level_id if existing else target_id,
            existing=existing,
            proposed_changes=changes,
            provenance_link_id=provenance_link_id,
            confidence=confidence,
            observation_status=observation_status,
            base_diagnostics=diagnostics,
            manual_review_required=manual_review_required,
            value_statuses=value_statuses,
        )


def _intake_provenance_definition_from_manual_run(
    request: ManualIngestionRunRequest,
    *,
    raw_record: RawIngestionRecord,
    normalization_result: NormalizerResult,
) -> IntakeProvenanceDefinition:
    observation_status = (
        normalization_result.observation.observation_status
        if normalization_result.observation is not None
        else None
    )
    return IntakeProvenanceDefinition(
        raw_record_id=raw_record.raw_record_id,
        source_id=request.source_id or f"source_{raw_record.raw_record_id}",
        observation_id=(
            request.observation_id or f"observation_{raw_record.raw_record_id}"
        ),
        source_type=SourceType(raw_record.source_type),
        source_name=raw_record.source_name,
        url_or_provider=raw_record.url_or_provider,
        collected_at=_aware_utc(raw_record.collected_at),
        observed_at=_aware_utc(raw_record.observed_at or raw_record.collected_at),
        license_or_terms_category=_manual_license_terms(request),
        confidence=_manual_confidence(request),
        data_origin=request.data_origin,
        observation_status=observation_status,
        notes=raw_record.parsing_notes,
    )


def _manual_license_terms(
    request: ManualIngestionRunRequest,
) -> LicenseTermsCategory:
    value = request.manual_observation.get("license_or_terms_category")
    if value is None:
        return LicenseTermsCategory.UNKNOWN
    if isinstance(value, LicenseTermsCategory):
        return value
    return LicenseTermsCategory(value)


def _manual_confidence(request: ManualIngestionRunRequest) -> Confidence:
    value = request.manual_observation.get("confidence")
    if value is None:
        return Confidence.UNKNOWN
    if isinstance(value, Confidence):
        return value
    return Confidence(value)


def _manual_diag(
    code: str,
    message: str,
    *,
    stage: str | None = None,
) -> ManualIngestionRunDiagnostic:
    return ManualIngestionRunDiagnostic(
        code=code,
        message=message[:512],
        stage=stage,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _manual_step(
    steps: list[ManualIngestionStepResult],
    stage: str,
    status: str,
    *,
    payload: object | None = None,
    diagnostics: tuple[ManualIngestionRunDiagnostic, ...] = (),
) -> None:
    steps.append(
        ManualIngestionStepResult(
            stage=stage,
            status=status,
            payload=payload,
            diagnostics=diagnostics,
        )
    )


def _manual_completed_status(
    diagnostics: list[ManualIngestionRunDiagnostic],
) -> ManualIngestionRunStatus:
    return (
        ManualIngestionRunStatus.COMPLETED_WITH_WARNINGS
        if diagnostics
        else ManualIngestionRunStatus.COMPLETED
    )


def _manual_run_result(
    request: ManualIngestionRunRequest,
    *,
    status: ManualIngestionRunStatus,
    adapter_result: object | None = None,
    raw_records_created: tuple[str, ...] = (),
    normalization_result: object | None = None,
    provenance_attachment_result: IntakeProvenanceAttachmentResult | None = None,
    canonical_proposal: CanonicalFactProposal | None = None,
    proposal_review_result: ProposalReviewResult | None = None,
    write_plan: CanonicalWritePlan | None = None,
    write_execution_result: CanonicalWriteExecutionResult | None = None,
    refresh_plan: PostWriteRefreshPlan | None = None,
    refresh_execution_result: PostWriteRefreshExecutionResult | None = None,
    steps: list[ManualIngestionStepResult],
    diagnostics: list[ManualIngestionRunDiagnostic],
) -> ManualIngestionRunResult:
    return ManualIngestionRunResult(
        mode=request.mode,
        status=status,
        adapter_result=adapter_result,
        raw_records_created=raw_records_created,
        normalization_result=normalization_result,
        provenance_attachment_result=provenance_attachment_result,
        canonical_proposal=canonical_proposal,
        proposal_review_result=proposal_review_result,
        write_plan=write_plan,
        write_execution_result=write_execution_result,
        refresh_plan=refresh_plan,
        refresh_execution_result=refresh_execution_result,
        steps=tuple(steps),
        diagnostics=tuple(diagnostics),
    )


def _refresh_decision_for_generated_plan(
    decision: PostWriteRefreshExecutionDecision,
    *,
    refresh_plan: PostWriteRefreshPlan,
    write_plan: CanonicalWritePlan,
    diagnostics: list[ManualIngestionRunDiagnostic],
) -> PostWriteRefreshExecutionDecision:
    if decision.refresh_plan_id == refresh_plan.refresh_plan_id:
        return decision
    if decision.refresh_plan_id == write_plan.plan_id and refresh_plan.refresh_plan_id:
        diagnostics.append(
            _manual_diag(
                "refresh_decision_bound_to_generated_plan",
                "Refresh approval named the write plan and was bound to the "
                "generated refresh plan.",
                stage="refresh_execution",
            )
        )
        return decision.model_copy(
            update={"refresh_plan_id": refresh_plan.refresh_plan_id}
        )
    return decision


def _normalization_metadata(normalized_payload: dict) -> dict:
    value = normalized_payload.get("_normalization")
    return value if isinstance(value, dict) else {}


def _normalization_manual_review_required(normalized_payload: dict) -> bool:
    return bool(_normalization_metadata(normalized_payload).get("manual_review_required"))


def _normalization_observation_status(
    normalized_payload: dict,
) -> ObservationStatus | None:
    value = _normalization_metadata(normalized_payload).get("observation_status")
    if value is None:
        return None
    return value if isinstance(value, ObservationStatus) else ObservationStatus(value)


def _attachment_notes(
    definition_notes: str | None,
    record_notes: str | None,
    *,
    manual_review_required: bool,
) -> str | None:
    parts = [part for part in (definition_notes, record_notes) if part]
    if manual_review_required:
        parts.append("manual_review_required")
    if not parts:
        return None
    return "; ".join(parts)


def _proposal_manual_review_required(
    record: RawIngestionRecord,
    *,
    source_type: SourceType,
    observation_notes: str | None,
) -> bool:
    return (
        record.normalization_status == NormalizationStatus.REQUIRES_MANUAL_REVIEW.value
        or (
            record.normalized_payload is not None
            and _normalization_manual_review_required(record.normalized_payload)
        )
        or SOURCE_TYPE_DEFAULT_ACCEPTABILITY[source_type]
        is SourceAcceptability.MANUAL_REVIEW_REQUIRED
        or (
            observation_notes is not None
            and "manual_review_required" in observation_notes
        )
    )


def _proposal_review_notes(
    reviewer_note: str | None,
    *,
    manual_review_override: bool,
) -> str | None:
    parts = [reviewer_note] if reviewer_note else []
    if manual_review_override:
        parts.append("manual_review_override_recorded")
    if not parts:
        return None
    return "; ".join(parts)


def _proposal_fact_source_link_id(proposal: CanonicalFactProposal) -> str:
    raw_key = "|".join(
        (
            proposal.raw_record_id,
            proposal.fact_type.value,
            proposal.fact_id,
            proposal.fact_field or "",
            proposal.observation_id,
        )
    )
    return f"proposal_link_{sha256(raw_key.encode('utf-8')).hexdigest()[:24]}"


def _proposal_review_result(
    proposal: CanonicalFactProposal,
    decision: ProposalReviewDecision,
    *,
    status: ProposalReviewStatus,
    diagnostics: list[str],
    fact_source_link_id: str | None = None,
    fact_source_link_outcome: str | None = None,
    manual_review_required: bool = False,
) -> ProposalReviewResult:
    return ProposalReviewResult(
        raw_record_id=proposal.raw_record_id,
        proposed_fact_id=proposal.fact_id,
        fact_type=proposal.fact_type,
        approval_status=status,
        reviewer_note=decision.reviewer_note,
        diagnostics=tuple(diagnostics),
        source_id=proposal.source_id,
        observation_id=proposal.observation_id,
        fact_source_link_id=fact_source_link_id,
        fact_source_link_outcome=fact_source_link_outcome,
        manual_review_required=manual_review_required,
        canonical_domain_mutated=False,
    )


def _validate_proposal_matches_record(
    proposal: CanonicalFactProposal,
    record: RawIngestionRecord,
) -> None:
    if proposal.source_id != record.source_id:
        raise ValueError("proposal source_id does not match raw intake")
    if proposal.observation_id != record.observation_id:
        raise ValueError("proposal observation_id does not match raw intake")
    if record.intended_fact_type is None:
        raise ValueError("write planning requires intended_fact_type")
    if proposal.intent is not CanonicalFactIntent(record.intended_fact_type):
        raise ValueError("proposal intent does not match raw intake")
    if proposal.normalized_payload != record.normalized_payload:
        raise ValueError("proposal payload does not match normalized intake")


def _write_diag(
    code: str,
    message: str,
    *,
    field_name: str | None = None,
) -> CanonicalWriteDiagnostic:
    return CanonicalWriteDiagnostic(
        code=code,
        message=message,
        field_name=field_name,
    )


def _target_entity_type_for(intent: CanonicalFactIntent) -> str:
    if intent is CanonicalFactIntent.COMPANY:
        return "companies"
    if intent is CanonicalFactIntent.REGION:
        return "regions"
    if intent is CanonicalFactIntent.PRESENCE:
        return "company_region_presence"
    if intent is CanonicalFactIntent.HIRING:
        return "company_region_hiring"
    if intent in {
        CanonicalFactIntent.INTERNSHIPS_COOPS,
        CanonicalFactIntent.EARLY_CAREER_PROGRAMS,
    }:
        return "company_region_entry_level"
    if intent is CanonicalFactIntent.SCORE_INPUT:
        return "score_inputs"
    return "unknown"


def _write_plan(
    proposal: CanonicalFactProposal,
    *,
    status: CanonicalWritePlanStatus,
    target_entity_type: str,
    target_identifier: str | None = None,
    operations: tuple[CanonicalWriteOperation, ...] = (),
    provenance_link_id: str | None = None,
    confidence: Confidence,
    observation_status: ObservationStatus,
    diagnostics: list[CanonicalWriteDiagnostic],
    manual_review_required: bool = False,
) -> CanonicalWritePlan:
    return CanonicalWritePlan(
        raw_record_id=proposal.raw_record_id,
        plan_id=_canonical_write_plan_id(
            proposal,
            target_entity_type=target_entity_type,
            target_identifier=target_identifier,
            provenance_link_id=provenance_link_id,
        ),
        proposal_fact_intent=proposal.intent,
        proposed_fact_id=proposal.fact_id,
        fact_type=proposal.fact_type,
        status=status,
        target_entity_type=target_entity_type,
        target_identifier=target_identifier,
        operations=operations,
        provenance_link_id=provenance_link_id,
        confidence=confidence,
        observation_status=observation_status,
        diagnostics=tuple(diagnostics),
        manual_review_required=manual_review_required,
        dry_run=True,
    )


def _canonical_write_plan_id(
    proposal: CanonicalFactProposal,
    *,
    target_entity_type: str,
    target_identifier: str | None,
    provenance_link_id: str | None,
) -> str:
    raw_key = "|".join(
        (
            proposal.raw_record_id,
            proposal.fact_type.value,
            proposal.fact_id,
            proposal.fact_field or "",
            target_entity_type,
            target_identifier or "",
            provenance_link_id or "",
        )
    )
    return f"write_plan_{sha256(raw_key.encode('utf-8')).hexdigest()[:24]}"


def _unsupported_write_plan(
    proposal: CanonicalFactProposal,
    *,
    provenance_link_id: str,
    confidence: Confidence,
    observation_status: ObservationStatus,
    diagnostics: list[CanonicalWriteDiagnostic],
) -> CanonicalWritePlan:
    operation = CanonicalWriteOperation(
        operation_type=CanonicalWriteOperationType.REQUIRES_MANUAL_REVIEW,
        target_entity_type=_target_entity_type_for(proposal.intent),
        target_identifier=proposal.fact_id,
        provenance_link_id=provenance_link_id,
        confidence=confidence,
        observation_status=observation_status,
        diagnostics=tuple(diagnostics),
        manual_review_required=True,
    )
    return _write_plan(
        proposal,
        status=CanonicalWritePlanStatus.UNSUPPORTED,
        target_entity_type=operation.target_entity_type,
        target_identifier=operation.target_identifier,
        operations=(operation,),
        provenance_link_id=provenance_link_id,
        confidence=confidence,
        observation_status=observation_status,
        diagnostics=diagnostics,
        manual_review_required=True,
    )


def _present_fields(fields: dict, names: tuple[str, ...]) -> dict[str, object]:
    return {name: fields[name] for name in names if name in fields}


def _string_field(fields: dict, name: str) -> str | None:
    value = fields.get(name)
    return value if isinstance(value, str) and value else None


def _pair_target_id(
    prefix: str,
    company_id: str | None,
    region_id: str | None,
) -> str | None:
    if not company_id or not region_id:
        return None
    return f"{prefix}:{company_id}:{region_id}"


def _add_count_change(
    fields: dict,
    field_name: str,
    changes: dict[str, object],
    value_statuses: dict[str, str],
    diagnostics: list[CanonicalWriteDiagnostic],
) -> None:
    status_key = f"{field_name}_status"
    raw_status = fields.get(status_key)
    if field_name not in fields and raw_status is None:
        return
    status = (
        ObservationStatus(raw_status)
        if raw_status is not None
        else ObservationStatus.UNKNOWN
    )
    value_statuses[field_name] = status.value
    value = fields.get(field_name)
    if status in {
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.STALE,
    }:
        diagnostics.append(
            _write_diag(
                "count_value_not_planned_as_zero",
                f"{field_name} is {status.value}; the plan keeps it null.",
                field_name=field_name,
            )
        )
        changes[field_name] = None
        return
    if status is ObservationStatus.ZERO_OBSERVED:
        if value != 0:
            diagnostics.append(
                _write_diag(
                    "zero_observed_value_mismatch",
                    "zero_observed count status requires numeric zero.",
                    field_name=field_name,
                )
            )
            changes[field_name] = None
            return
        changes[field_name] = 0
        return
    if value == 0:
        diagnostics.append(
            _write_diag(
                "zero_requires_observed_basis",
                "Zero count is not planned without zero_observed status.",
                field_name=field_name,
            )
        )
        changes[field_name] = None
        value_statuses[field_name] = ObservationStatus.UNKNOWN.value
        return
    changes[field_name] = value


def _plan_against_existing(
    proposal: CanonicalFactProposal,
    *,
    target_entity_type: str,
    target_identifier: str | None,
    existing: object | None,
    proposed_changes: dict[str, object],
    provenance_link_id: str,
    confidence: Confidence,
    observation_status: ObservationStatus,
    base_diagnostics: list[CanonicalWriteDiagnostic],
    manual_review_required: bool,
    value_statuses: dict[str, str] | None = None,
    conflict_fields: frozenset[str] = frozenset(),
) -> CanonicalWritePlan:
    diagnostics = list(base_diagnostics)
    value_statuses = value_statuses or {}
    missing_id = target_identifier is None
    if missing_id:
        diagnostics.append(
            _write_diag(
                "missing_target_identifier",
                "The canonical target identifier could not be derived.",
            )
        )

    conflicts: list[CanonicalWriteDiagnostic] = []
    executable_changes: dict[str, object] = {}
    if existing is not None:
        for field_name, proposed_value in proposed_changes.items():
            current_value = getattr(existing, field_name, None)
            status = value_statuses.get(field_name)
            if proposed_value is None and status in {
                ObservationStatus.UNKNOWN.value,
                ObservationStatus.NOT_COLLECTED.value,
                ObservationStatus.STALE.value,
            }:
                continue
            if current_value == proposed_value:
                continue
            if (
                field_name in conflict_fields
                and current_value is not None
                and proposed_value is not None
            ):
                conflicts.append(
                    _write_diag(
                        "existing_value_conflict",
                        "Existing canonical value differs from proposed value.",
                        field_name=field_name,
                    )
                )
                continue
            executable_changes[field_name] = proposed_value
    else:
        executable_changes = dict(proposed_changes)

    diagnostics.extend(conflicts)
    review_required = manual_review_required or missing_id or bool(conflicts)
    operation_type: CanonicalWriteOperationType
    plan_status: CanonicalWritePlanStatus
    if review_required:
        operation_type = CanonicalWriteOperationType.REQUIRES_MANUAL_REVIEW
        plan_status = CanonicalWritePlanStatus.REQUIRES_MANUAL_REVIEW
    elif existing is None:
        operation_type = CanonicalWriteOperationType.CREATE
        plan_status = CanonicalWritePlanStatus.PLANNED
    elif executable_changes:
        operation_type = CanonicalWriteOperationType.UPDATE
        plan_status = CanonicalWritePlanStatus.PLANNED
    else:
        operation_type = CanonicalWriteOperationType.NO_OP
        plan_status = CanonicalWritePlanStatus.NO_OP

    operation = CanonicalWriteOperation(
        operation_type=operation_type,
        target_entity_type=target_entity_type,
        target_identifier=target_identifier,
        proposed_field_changes=executable_changes,
        value_statuses=value_statuses,
        provenance_link_id=provenance_link_id,
        confidence=confidence,
        observation_status=observation_status,
        diagnostics=tuple(diagnostics),
        manual_review_required=review_required,
    )
    return _write_plan(
        proposal,
        status=plan_status,
        target_entity_type=target_entity_type,
        target_identifier=target_identifier,
        operations=(operation,),
        provenance_link_id=provenance_link_id,
        confidence=confidence,
        observation_status=observation_status,
        diagnostics=diagnostics,
        manual_review_required=review_required,
    )


def _refresh_diag(
    code: str,
    message: str,
    *,
    field_name: str | None = None,
) -> PostWriteRefreshDiagnostic:
    return PostWriteRefreshDiagnostic(
        code=code,
        message=message,
        field_name=field_name,
    )


def _missing_changed_entity_id_diag() -> PostWriteRefreshDiagnostic:
    return _refresh_diag(
        "missing_changed_entity_id",
        "The execution result does not identify the changed canonical entity.",
    )


def _refresh_target(
    target_type: PostWriteRefreshTargetType,
    *,
    reason: str,
    target_id: str | None = None,
    region_id: str | None = None,
    company_id: str | None = None,
) -> PostWriteRefreshTarget:
    return PostWriteRefreshTarget(
        target_type=target_type,
        target_id=target_id,
        region_id=region_id,
        company_id=company_id,
        reason=reason,
        dry_run=True,
    )


def _refresh_targets_for_scope(
    *,
    changed_type: str,
    changed_id: str | None,
    affected_company_ids: set[str],
    affected_region_ids: set[str],
) -> tuple[PostWriteRefreshTarget, ...]:
    targets: list[PostWriteRefreshTarget] = []
    for company_id in sorted(affected_company_ids):
        targets.append(
            _refresh_target(
                PostWriteRefreshTargetType.COMPANY_OUTPUT,
                target_id=company_id,
                company_id=company_id,
                reason=f"{changed_type} write affects company output.",
            )
        )
    for region_id in sorted(affected_region_ids):
        targets.append(
            _refresh_target(
                PostWriteRefreshTargetType.REGION_SCORE,
                target_id=region_id,
                region_id=region_id,
                reason=f"{changed_type} write affects region score.",
            )
        )
        targets.append(
            _refresh_target(
                PostWriteRefreshTargetType.REGION_OUTPUT,
                target_id=region_id,
                region_id=region_id,
                reason=f"{changed_type} write affects region output.",
            )
        )
    if changed_id is not None:
        targets.append(
            _refresh_target(
                PostWriteRefreshTargetType.PROVENANCE_AUDIT,
                target_id=changed_id,
                reason="Canonical write should be included in a later provenance audit.",
            )
        )
    return _dedupe_refresh_targets(targets)


def _dedupe_refresh_targets(
    targets: list[PostWriteRefreshTarget],
) -> tuple[PostWriteRefreshTarget, ...]:
    deduped: list[PostWriteRefreshTarget] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for target in targets:
        key = (
            target.target_type.value,
            target.target_id,
            target.region_id,
            target.company_id,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return tuple(deduped)


def _post_write_refresh_plan(
    execution_result: CanonicalWriteExecutionResult,
    *,
    status: PostWriteRefreshPlanStatus,
    affected_region_ids: tuple[str, ...] = (),
    affected_company_ids: tuple[str, ...] = (),
    refresh_targets: tuple[PostWriteRefreshTarget, ...] = (),
    diagnostics: list[PostWriteRefreshDiagnostic],
) -> PostWriteRefreshPlan:
    plan = PostWriteRefreshPlan(
        refresh_plan_id=None,
        execution_plan_id=execution_result.plan_id,
        raw_record_id=execution_result.raw_record_id,
        changed_canonical_entity_type=execution_result.target_entity_type,
        changed_canonical_entity_id=execution_result.target_identifier,
        affected_region_ids=affected_region_ids,
        affected_company_ids=affected_company_ids,
        status=status,
        refresh_targets=refresh_targets,
        diagnostics=tuple(diagnostics),
        dry_run=True,
    )
    return plan.model_copy(update={"refresh_plan_id": _post_write_refresh_plan_id(plan)})


def _post_write_refresh_plan_id(plan: PostWriteRefreshPlan) -> str:
    if plan.refresh_plan_id is not None:
        return plan.refresh_plan_id
    target_parts = [
        "|".join(
            (
                target.target_type.value,
                target.target_id or "",
                target.region_id or "",
                target.company_id or "",
            )
        )
        for target in plan.refresh_targets
    ]
    raw_key = "|".join(
        (
            plan.execution_plan_id,
            plan.raw_record_id,
            plan.changed_canonical_entity_type,
            plan.changed_canonical_entity_id or "",
            plan.status.value,
            *target_parts,
        )
    )
    return f"refresh_plan_{sha256(raw_key.encode('utf-8')).hexdigest()[:24]}"


def _refresh_execution_diag(
    code: str,
    message: str,
    *,
    target_type: PostWriteRefreshTargetType | None = None,
    target_id: str | None = None,
) -> PostWriteRefreshExecutionDiagnostic:
    return PostWriteRefreshExecutionDiagnostic(
        code=code,
        message=message,
        target_type=target_type,
        target_id=target_id,
    )


def _target_refresh_result(
    target: PostWriteRefreshTarget,
    *,
    status: PostWriteRefreshExecutionStatus,
    action: str | None = None,
    refreshed_artifact_id: str | None = None,
    diagnostics: tuple[PostWriteRefreshExecutionDiagnostic, ...] = (),
) -> PostWriteRefreshTargetExecutionResult:
    return PostWriteRefreshTargetExecutionResult(
        target_type=target.target_type,
        target_id=target.target_id,
        region_id=target.region_id,
        company_id=target.company_id,
        status=status,
        action=action,
        refreshed_artifact_id=refreshed_artifact_id,
        diagnostics=diagnostics,
    )


def _overall_refresh_execution_status(
    target_results: tuple[PostWriteRefreshTargetExecutionResult, ...],
) -> PostWriteRefreshExecutionStatus:
    if not target_results:
        return PostWriteRefreshExecutionStatus.NO_OP
    statuses = {result.status for result in target_results}
    if statuses <= {PostWriteRefreshExecutionStatus.NO_OP}:
        return PostWriteRefreshExecutionStatus.NO_OP
    if statuses <= {PostWriteRefreshExecutionStatus.UNSUPPORTED}:
        return PostWriteRefreshExecutionStatus.UNSUPPORTED
    if statuses & {PostWriteRefreshExecutionStatus.FAILED}:
        return PostWriteRefreshExecutionStatus.PARTIAL
    if statuses & {PostWriteRefreshExecutionStatus.UNSUPPORTED}:
        return PostWriteRefreshExecutionStatus.PARTIAL
    if statuses & {PostWriteRefreshExecutionStatus.EXECUTED}:
        return PostWriteRefreshExecutionStatus.EXECUTED
    return PostWriteRefreshExecutionStatus.NO_OP


def _post_write_refresh_execution_result(
    plan: PostWriteRefreshPlan,
    *,
    status: PostWriteRefreshExecutionStatus,
    diagnostics: list[PostWriteRefreshExecutionDiagnostic],
    target_results: tuple[PostWriteRefreshTargetExecutionResult, ...] = (),
) -> PostWriteRefreshExecutionResult:
    return PostWriteRefreshExecutionResult(
        refresh_plan_id=_post_write_refresh_plan_id(plan),
        execution_plan_id=plan.execution_plan_id,
        raw_record_id=plan.raw_record_id,
        status=status,
        target_results=target_results,
        diagnostics=tuple(diagnostics),
        scores_refreshed_count=sum(
            1
            for result in target_results
            if result.target_type is PostWriteRefreshTargetType.REGION_SCORE
            and result.status is PostWriteRefreshExecutionStatus.EXECUTED
        ),
        outputs_refreshed_count=sum(
            1
            for result in target_results
            if result.target_type
            in {
                PostWriteRefreshTargetType.REGION_OUTPUT,
                PostWriteRefreshTargetType.COMPANY_OUTPUT,
                PostWriteRefreshTargetType.COMPARISON_OUTPUT,
                PostWriteRefreshTargetType.CONTEXTUAL_OUTPUT,
            }
            and result.status is PostWriteRefreshExecutionStatus.EXECUTED
        ),
        jobs_enqueued=False,
        schedules_created=False,
        external_data_collected=False,
    )


def _execution_diag(
    code: str,
    message: str,
    *,
    field_name: str | None = None,
) -> CanonicalWriteExecutionDiagnostic:
    return CanonicalWriteExecutionDiagnostic(
        code=code,
        message=message,
        field_name=field_name,
    )


def _execution_result(
    plan: CanonicalWritePlan,
    *,
    status: CanonicalWriteExecutionStatus,
    diagnostics: list[CanonicalWriteExecutionDiagnostic],
    operation_type: CanonicalWriteOperationType | None = None,
    canonical_domain_mutated: bool = False,
) -> CanonicalWriteExecutionResult:
    return CanonicalWriteExecutionResult(
        plan_id=plan.plan_id,
        raw_record_id=plan.raw_record_id,
        status=status,
        target_entity_type=plan.target_entity_type,
        target_identifier=plan.target_identifier,
        operation_type=operation_type,
        diagnostics=tuple(diagnostics),
        fact_source_link_id=plan.provenance_link_id,
        canonical_domain_mutated=canonical_domain_mutated,
        downstream_refresh_triggered=False,
    )


def _unsafe_count_write(
    operation: CanonicalWriteOperation,
) -> CanonicalWriteExecutionDiagnostic | None:
    for field_name, status_value in operation.value_statuses.items():
        proposed_value = operation.proposed_field_changes.get(field_name)
        if status_value in {
            ObservationStatus.UNKNOWN.value,
            ObservationStatus.NOT_COLLECTED.value,
            ObservationStatus.STALE.value,
        } and proposed_value == 0:
            return _execution_diag(
                "unsafe_zero_write_blocked",
                "Unknown, not-collected, or stale counts cannot execute as zero.",
                field_name=field_name,
            )
        if status_value == ObservationStatus.ZERO_OBSERVED.value and proposed_value != 0:
            return _execution_diag(
                "zero_observed_requires_zero",
                "zero_observed count execution requires numeric zero.",
                field_name=field_name,
            )
    return None


def _execution_changes(operation: CanonicalWriteOperation, link: object) -> dict[str, object]:
    changes = dict(operation.proposed_field_changes)
    if operation.target_entity_type in {
        "company_region_presence",
        "company_region_hiring",
        "company_region_entry_level",
    }:
        changes["source_refs"] = [
            {
                "fact_source_link_id": operation.provenance_link_id,
                "source_id": link.source_id,
                "observation_id": link.observation_id,
            }
        ]
    return changes


def _string_change(changes: dict[str, object], field_name: str) -> str | None:
    value = changes.get(field_name)
    return value if isinstance(value, str) and value else None


def _target_matches(target: object, changes: dict[str, object]) -> bool:
    return all(getattr(target, field_name, None) == value for field_name, value in changes.items())


def _apply_execution_changes(target: object, changes: dict[str, object]) -> None:
    for field_name, value in changes.items():
        setattr(target, field_name, value)
