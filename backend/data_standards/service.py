"""Deterministic Layer 27 standards and partner submission services."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.admin.repository import AdminEventLogRepository
from backend.admin.service import AdminEventLogInput, AdminEventLogService
from backend.companies.models import Company
from backend.data_standards.models import (
    DataStandardCandidateFactRecord,
    DataStandardCandidateReviewRecord,
    DataStandardCanonicalMergeRecord,
    DataStandardPartnerSubmissionRecord,
)
from backend.data_standards.schemas import (
    CandidateCanonicalTargetType,
    CandidateFactListResponse,
    CandidateFactPayload,
    CandidateFactState,
    CandidateProvenanceSnapshot,
    CandidateReviewDecision,
    CandidateReviewPayload,
    CandidateReviewRequest,
    CanonicalMergeAction,
    CanonicalMergePreview,
    CanonicalMergeRequest,
    CanonicalMergeResult,
    CanonicalMergeStatus,
    DataQualityCertificationRequest,
    DataQualityCertificationResult,
    DataQualityLabel,
    DataQualityLabelList,
    DataQualityLabelValue,
    GovernanceArea,
    GovernanceFramework,
    GovernanceFrameworkRecord,
    GovernanceStatus,
    MergeConflict,
    PartnerConfidence,
    PartnerFreshness,
    PartnerFreshnessStatus,
    PartnerIdentityContext,
    PartnerPublicContactMetadata,
    PartnerRecordType,
    PartnerRegistry,
    PartnerRegistryRecord,
    PartnerSourceRef,
    PartnerSubmission,
    PartnerSubmissionRecord,
    PartnerSubmissionSchema,
    PartnerSubmissionValidationError,
    PartnerSubmissionValidationResult,
    PartnerSubmissionWarning,
    PartnerSubmitterType,
    PartnerTrustTier,
    PartnerType,
    PartnerValidationStatus,
    PartnerVerificationStatus,
    StandardDefinition,
    StandardDefinitionList,
    StandardDefinitionStatus,
    SubmissionReviewLifecycleState,
)
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.service import InvalidationApplyResult, InvalidationService
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.shared.confidence import Confidence
from backend.trust.adapters import DataStandardsTrustAdapter
from backend.trust.exceptions import ExceptionWorkflowService
from backend.trust.explanations import TrustExplanationService
from backend.trust.reports import latest_report_recheck_status
from backend.trust.risk import RiskRoutingService
from backend.trust.schemas import (
    PublicExceptionStatus,
    RankingInfluenceDecision,
    RiskLevel,
    RoutingOutcome,
    TrustAssessmentSubjectType,
    TrustExplanation,
    TrustTier,
)
from backend.trust.service import TrustAssessmentService

STANDARDS_VERSION = "27.1.0"
PARTNER_NETWORK_VERSION = "27.3.0"
QUALITY_LABEL_VERSION = "27.4.0"
GOVERNANCE_FRAMEWORK_VERSION = "27.5.0"
PARTNER_SCHEMA_VERSION = "partner_submission_v1"

REQUIRED_SUBMISSION_FIELDS = (
    "submission_id",
    "partner_id",
    "submitted_at",
    "schema_version",
    "submitter_type",
    "records",
    "source_refs",
    "freshness",
    "confidence",
)

REQUIRED_FIELDS_BY_RECORD_TYPE: dict[str, tuple[str, ...]] = {
    PartnerRecordType.COMPANY.value: (
        "company_name",
        "company_website",
    ),
    PartnerRecordType.REGION.value: (
        "region_name",
        "country_code",
        "region_type",
    ),
    PartnerRecordType.EARLY_CAREER_PROGRAM.value: (
        "company_name",
        "program_name",
        "program_type",
        "role_family",
    ),
    PartnerRecordType.HIRING_SIGNAL.value: (
        "company_name",
        "signal_type",
        "observed_at",
    ),
    PartnerRecordType.COMPANY_REGION_PRESENCE.value: (
        "company_name",
        "region_name",
        "presence_status",
        "observed_at",
    ),
}


class PartnerSubmissionValidationFailed(ValueError):
    def __init__(self, result: PartnerSubmissionValidationResult) -> None:
        super().__init__("Partner submission failed Layer 27 validation.")
        self.result = result


class PartnerSubmissionNotFound(Exception):
    pass


class PartnerSubmissionReviewLifecycleError(ValueError):
    pass


class CandidateFactNotFound(Exception):
    pass


class CandidateReviewWorkflowError(ValueError):
    pass


class CanonicalMergeBlocked(ValueError):
    def __init__(self, preview: CanonicalMergePreview) -> None:
        super().__init__("Candidate fact is not eligible for canonical merge.")
        self.preview = preview


class DataStandardsService:
    """Serve standards metadata and validate/store partner submissions."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def standard_definitions(self) -> StandardDefinitionList:
        return StandardDefinitionList(
            version=STANDARDS_VERSION,
            definitions=STANDARD_DEFINITIONS,
        )

    def partner_schema(self) -> PartnerSubmissionSchema:
        return PartnerSubmissionSchema(
            schema_version=PARTNER_SCHEMA_VERSION,
            supported_submitter_types=tuple(sorted(PartnerSubmitterType.values())),
            supported_record_types=tuple(sorted(PartnerRecordType.values())),
            validation_statuses=tuple(sorted(PartnerValidationStatus.values())),
            review_lifecycle_states=tuple(
                sorted(SubmissionReviewLifecycleState.values())
            ),
            required_submission_fields=REQUIRED_SUBMISSION_FIELDS,
            required_fields_by_record_type=REQUIRED_FIELDS_BY_RECORD_TYPE,
            source_refs_required_for_record_types=tuple(sorted(PartnerRecordType.values())),
        )

    def partner_registry(self) -> PartnerRegistry:
        return PartnerRegistry(
            version=PARTNER_NETWORK_VERSION,
            supported_partner_types=tuple(sorted(PartnerType.values())),
            verification_statuses=tuple(sorted(PartnerVerificationStatus.values())),
            trust_tiers=tuple(sorted(PartnerTrustTier.values())),
            partners=PARTNER_REGISTRY,
        )

    def partner_by_id(self, partner_id: str) -> PartnerRegistryRecord | None:
        return PARTNER_REGISTRY_BY_ID.get(partner_id)

    def quality_labels(self) -> DataQualityLabelList:
        return DataQualityLabelList(
            version=QUALITY_LABEL_VERSION,
            labels=tuple(_quality_label_payload(label) for label in QUALITY_LABELS),
        )

    def governance_framework(self) -> GovernanceFramework:
        return GovernanceFramework(
            version=GOVERNANCE_FRAMEWORK_VERSION,
            status=GovernanceStatus.FRAMEWORK_DEFINED,
            governance_records=GOVERNANCE_FRAMEWORK,
        )

    def evaluate_quality_label(
        self,
        payload: Mapping[str, Any] | DataQualityCertificationRequest,
    ) -> DataQualityCertificationResult:
        request = (
            payload
            if isinstance(payload, DataQualityCertificationRequest)
            else DataQualityCertificationRequest.model_validate(dict(payload))
        )
        label = _quality_label_payload(QUALITY_LABELS_BY_VALUE[request.label])
        partner = (
            PARTNER_REGISTRY_BY_ID.get(request.partner_id)
            if request.partner_id is not None
            else None
        )
        reasons: list[str] = []
        warnings: list[str] = [label.warning_copy]
        source_refs = tuple(request.source_refs)

        if request.partner_id is not None and partner is None:
            reasons.append("partner_not_registered")
        if label.requires_source_refs and not source_refs:
            reasons.append("source_refs_required")
        if label.requires_partner_verification and (
            partner is None
            or partner.verification_status != PartnerVerificationStatus.VERIFIED
        ):
            reasons.append("verified_partner_required")
        if not _confidence_meets_minimum(
            request.confidence,
            minimum=label.minimum_confidence,
        ):
            reasons.append("minimum_confidence_not_met")

        if label.label == DataQualityLabelValue.AUDITED_SOURCE_DATA:
            if not _has_audit_marker(request):
                reasons.append("audit_or_review_marker_required")
        if label.label == DataQualityLabelValue.SELF_REPORTED_EMPLOYER_DATA:
            if not _is_employer_context(partner, request):
                reasons.append("employer_context_required")
        if label.label == DataQualityLabelValue.PUBLIC_SOURCE_VERIFIED:
            if not _has_allowed_source_type(source_refs, label.allowed_sources):
                reasons.append("public_source_ref_required")
        if label.label == DataQualityLabelValue.VERIFIED_PARTNER_DATA:
            if not _has_allowed_source_type(source_refs, label.allowed_sources):
                reasons.append("accepted_source_ref_required")
        if label.label == DataQualityLabelValue.LOW_CONFIDENCE_SIGNAL:
            if not _low_confidence_condition_present(request):
                reasons.append("low_confidence_or_stale_signal_required")

        eligible = not reasons
        return DataQualityCertificationResult(
            label=label,
            eligible=eligible,
            certification_status="eligible" if eligible else "not_eligible",
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            partner_id=partner.partner_id if partner is not None else request.partner_id,
            partner_verification_status=(
                partner.verification_status if partner is not None else None
            ),
            partner_trust_tier=partner.trust_tier if partner is not None else None,
            source_ref_count=len(source_refs),
            freshness=request.freshness,
            confidence=request.confidence,
            ranking_influence_allowed=label.ranking_influence_allowed,
            public_display_allowed=label.public_display_allowed,
        )

    def validate_submission(
        self,
        payload: Mapping[str, Any],
    ) -> PartnerSubmissionValidationResult:
        data = dict(payload)
        errors: list[PartnerSubmissionValidationError] = []
        warnings = _coerce_warnings(data.get("warnings"))

        _validate_top_level(data, errors)
        source_ref_ids = _validate_source_refs(data.get("source_refs"), errors)
        _validate_records(data.get("records"), source_ref_ids, errors)
        _validate_partner_permissions(data.get("partner_id"), data.get("records"), errors)
        _validate_freshness(data.get("freshness"), errors)
        _validate_confidence(data.get("confidence"), errors)

        if errors:
            return PartnerSubmissionValidationResult(
                validation_status=PartnerValidationStatus.REJECTED,
                schema_version=_string_or_none(data.get("schema_version")),
                errors=tuple(errors),
                warnings=warnings,
            )

        normalized_payload = {
            **data,
            "validation_status": PartnerValidationStatus.VALIDATED.value,
            "warnings": [warning.model_dump(mode="json") for warning in warnings],
        }
        try:
            normalized = PartnerSubmission.model_validate(normalized_payload)
        except ValidationError as exc:
            return PartnerSubmissionValidationResult(
                validation_status=PartnerValidationStatus.REJECTED,
                schema_version=_string_or_none(data.get("schema_version")),
                errors=tuple(_errors_from_pydantic(exc)),
                warnings=warnings,
            )

        return PartnerSubmissionValidationResult(
            validation_status=PartnerValidationStatus.VALIDATED,
            schema_version=normalized.schema_version,
            warnings=normalized.warnings,
            normalized_submission=normalized,
        )

    def create_submission(
        self,
        payload: Mapping[str, Any],
    ) -> PartnerSubmission:
        if self._session is None:
            raise RuntimeError("create_submission requires a database session")
        result = self.validate_submission(payload)
        if result.validation_status is not PartnerValidationStatus.VALIDATED:
            raise PartnerSubmissionValidationFailed(result)
        assert result.normalized_submission is not None
        submission = result.normalized_submission
        row = DataStandardPartnerSubmissionRecord(
            partner_submission_id=submission.submission_id,
            partner_id=submission.partner_id,
            submitted_at=submission.submitted_at,
            schema_version=submission.schema_version,
            submitter_type=submission.submitter_type.value,
            validation_status=submission.validation_status.value,
            review_lifecycle_state=(
                SubmissionReviewLifecycleState.VALIDATION_PASSED.value
            ),
            review_state_history_json=[
                _submission_lifecycle_history_entry(
                    SubmissionReviewLifecycleState.SUBMITTED,
                    actor=submission.partner_id,
                    reason="Partner submission received.",
                    at=submission.submitted_at,
                ),
                _submission_lifecycle_history_entry(
                    SubmissionReviewLifecycleState.VALIDATION_PASSED,
                    actor="data_standards_validation",
                    reason="Layer 27 validation passed; canonical acceptance not implied.",
                ),
            ],
            records_json=[record.model_dump(mode="json") for record in submission.records],
            source_refs_json=[ref.model_dump(mode="json") for ref in submission.source_refs],
            freshness_json=submission.freshness.model_dump(mode="json"),
            confidence_json=submission.confidence.model_dump(mode="json"),
            warnings_json=[warning.model_dump(mode="json") for warning in submission.warnings],
            validation_errors_json=[],
            raw_submission_json=dict(payload),
        )
        self._session.add(row)
        self._session.flush()
        return submission

    def transition_submission_lifecycle(
        self,
        submission_id: str,
        target_state: SubmissionReviewLifecycleState | str,
        *,
        actor: str,
        reason: str,
    ) -> SubmissionReviewLifecycleState:
        session = self._require_session("transition_submission_lifecycle")
        submission_row = session.get(DataStandardPartnerSubmissionRecord, submission_id)
        if submission_row is None:
            raise PartnerSubmissionNotFound(submission_id)
        state = (
            target_state
            if isinstance(target_state, SubmissionReviewLifecycleState)
            else SubmissionReviewLifecycleState(target_state)
        )
        _transition_submission_lifecycle(
            submission_row,
            state,
            actor=actor,
            reason=reason,
        )
        session.flush()
        return state

    def create_candidates_from_submission(
        self,
        submission_id: str,
    ) -> CandidateFactListResponse:
        session = self._require_session("create_candidates_from_submission")
        submission_row = session.get(DataStandardPartnerSubmissionRecord, submission_id)
        if submission_row is None:
            raise PartnerSubmissionNotFound(submission_id)

        existing = self._candidate_rows_for_submission(submission_id)
        _assert_submission_can_create_candidates(
            submission_row,
            returning_existing=bool(existing),
        )
        if existing:
            return CandidateFactListResponse(
                candidates=tuple(self._candidate_payload(row) for row in existing)
            )

        submission = _submission_from_row(submission_row)
        source_refs_by_id = {ref.source_ref_id: ref for ref in submission.source_refs}
        partner_context = _partner_identity_context(submission.partner_id)
        rows: list[DataStandardCandidateFactRecord] = []
        for record in submission.records:
            selected_refs = tuple(
                source_refs_by_id[ref_id]
                for ref_id in record.source_ref_ids
                if ref_id in source_refs_by_id
            )
            target = _candidate_target(record)
            provenance_complete, provenance_warnings = _provenance_completeness(
                source_refs=selected_refs,
                freshness=submission.freshness,
                confidence=submission.confidence,
                partner_context=partner_context,
                submitted_at=submission.submitted_at,
            )
            if target["canonical_target_type"] == CandidateCanonicalTargetType.UNSUPPORTED:
                provenance_warnings = (
                    *provenance_warnings,
                    "record_type_not_supported_for_canonical_merge",
                )
            row = DataStandardCandidateFactRecord(
                candidate_fact_id=_stable_id(
                    "candidate",
                    f"{submission.submission_id}:{record.record_id}",
                    max_length=128,
                ),
                partner_submission_id=submission.submission_id,
                partner_id=submission.partner_id,
                partner_name=partner_context.partner_name,
                partner_type=(
                    partner_context.partner_type.value
                    if partner_context.partner_type is not None
                    else None
                ),
                partner_verification_status=partner_context.verification_status.value,
                partner_trust_tier=partner_context.trust_tier.value,
                submitter_type=submission.submitter_type.value,
                submitted_at=submission.submitted_at,
                record_id=record.record_id,
                record_type=record.record_type.value,
                candidate_state=CandidateFactState.PENDING_REVIEW.value,
                canonical_target_type=target["canonical_target_type"].value,
                canonical_target_id=target["canonical_target_id"],
                canonical_target_key_json=target["canonical_target_key"],
                fact_payload_json=target["fact_payload"],
                source_refs_json=[ref.model_dump(mode="json") for ref in selected_refs],
                freshness_json=submission.freshness.model_dump(mode="json"),
                confidence_json=submission.confidence.model_dump(mode="json"),
                provenance_complete=provenance_complete,
                provenance_warnings_json=list(provenance_warnings),
                raw_record_json=record.model_dump(mode="json"),
                ranking_influence_allowed=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(row)
            rows.append(row)

        _transition_submission_lifecycle(
            submission_row,
            SubmissionReviewLifecycleState.ACCEPTED_AS_CANDIDATE,
            actor="data_standards_candidate_creation",
            reason="Validated submission records were accepted into candidate review.",
        )
        session.flush()
        return CandidateFactListResponse(
            candidates=tuple(self._candidate_payload(row) for row in rows)
        )

    def list_candidates_for_submission(
        self,
        submission_id: str,
    ) -> CandidateFactListResponse:
        session = self._require_session("list_candidates_for_submission")
        if session.get(DataStandardPartnerSubmissionRecord, submission_id) is None:
            raise PartnerSubmissionNotFound(submission_id)
        return CandidateFactListResponse(
            candidates=tuple(
                self._candidate_payload(row)
                for row in self._candidate_rows_for_submission(submission_id)
            )
        )

    def list_review_candidates(self, *, limit: int = 100) -> CandidateFactListResponse:
        session = self._require_session("list_review_candidates")
        rows = session.execute(
            select(DataStandardCandidateFactRecord)
            .order_by(
                DataStandardCandidateFactRecord.created_at.asc(),
                DataStandardCandidateFactRecord.candidate_fact_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return CandidateFactListResponse(
            candidates=tuple(self._candidate_payload(row) for row in rows)
        )

    def candidate_detail(self, candidate_fact_id: str) -> dict[str, Any]:
        session = self._require_session("candidate_detail")
        row = session.get(DataStandardCandidateFactRecord, candidate_fact_id)
        if row is None:
            raise CandidateFactNotFound(candidate_fact_id)
        latest_review = self._latest_review_for_candidate(candidate_fact_id)
        preview = self.preview_canonical_merge(candidate_fact_id)
        return {
            "candidate": self._candidate_payload(row).model_dump(mode="json"),
            "latest_review": (
                self._review_payload(latest_review).model_dump(mode="json")
                if latest_review is not None
                else None
            ),
            "merge_preview": preview.model_dump(mode="json"),
        }

    def review_candidate_fact(
        self,
        candidate_fact_id: str,
        request: CandidateReviewRequest,
    ) -> CandidateReviewPayload:
        session = self._require_session("review_candidate_fact")
        candidate = session.get(DataStandardCandidateFactRecord, candidate_fact_id)
        if candidate is None:
            raise CandidateFactNotFound(candidate_fact_id)
        if self._merge_record_for_candidate(candidate_fact_id) is not None:
            raise CandidateReviewWorkflowError("merged candidate facts cannot be reviewed")

        resulting_state = _review_resulting_state(request.decision)
        if (
            _review_decision_is_approval(request.decision)
            and not candidate.provenance_complete
        ):
            raise CandidateReviewWorkflowError(
                "candidate approval requires complete candidate provenance"
            )
        if (
            _review_decision_is_approval(request.decision)
            and candidate.canonical_target_type
            == CandidateCanonicalTargetType.UNSUPPORTED.value
        ):
            raise CandidateReviewWorkflowError(
                "unsupported candidate facts cannot be approved for merge"
            )
        if _review_decision_is_approval(request.decision):
            provenance_blockers = _merge_provenance_blockers(
                candidate,
                request_source_basis=request.source_basis,
            )
            if provenance_blockers:
                raise CandidateReviewWorkflowError(
                    "candidate approval requires complete merge provenance: "
                    + ", ".join(provenance_blockers)
                )

        reviewed_at = request.reviewed_at or datetime.now(UTC)
        review_id = _new_id("candidate_review")
        audit_event = AdminEventLogService(
            AdminEventLogRepository(session),
            clock=lambda: reviewed_at,
        ).record_event(
            AdminEventLogInput(
                actor=request.reviewer_id,
                action="data_standard_candidate_review",
                object_type="data_standard_candidate",
                object_id=candidate.candidate_fact_id,
                before_state={
                    "candidate_state": _effective_candidate_state(
                        candidate,
                        latest_review=self._latest_review_for_candidate(candidate_fact_id),
                        merge_record=self._merge_record_for_candidate(candidate_fact_id),
                    ).value,
                    "canonical_target_id": candidate.canonical_target_id,
                },
                after_state={
                    "candidate_review_id": review_id,
                    "decision": request.decision.value,
                    "resulting_candidate_state": resulting_state.value,
                    "source_basis": request.source_basis,
                    "before_after_diff": request.before_after_diff,
                    "resolved_conflict_codes": _resolved_conflict_codes(request),
                },
                reason=request.reason,
                request_id=review_id,
            )
        )
        review = DataStandardCandidateReviewRecord(
            candidate_review_id=review_id,
            candidate_fact_id=candidate.candidate_fact_id,
            partner_submission_id=candidate.partner_submission_id,
            decision=request.decision.value,
            resulting_candidate_state=resulting_state.value,
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
            review_note=request.decision_notes,
            correction_reason=request.reason,
            reason=request.reason,
            decision_notes=request.decision_notes,
            source_basis_json=dict(request.source_basis),
            before_after_diff_json=dict(request.before_after_diff),
            resolved_conflict_codes_json=list(_resolved_conflict_codes(request)),
            audit_event_id=audit_event.admin_event_id,
            provenance_complete=candidate.provenance_complete,
            provenance_snapshot_json=self._provenance_snapshot(candidate).model_dump(
                mode="json"
            ),
            ranking_influence_allowed=False,
            reviewed_at=reviewed_at,
            created_at=reviewed_at,
        )
        session.add(review)
        submission_row = session.get(
            DataStandardPartnerSubmissionRecord,
            candidate.partner_submission_id,
        )
        if submission_row is not None:
            _apply_review_submission_lifecycle(
                submission_row,
                request.decision,
                actor=request.reviewer_id,
                reason=request.reason,
            )
        session.flush()
        if request.decision is CandidateReviewDecision.MERGE_TO_CANONICAL:
            try:
                self.merge_candidate_fact(
                    candidate_fact_id,
                    CanonicalMergeRequest(
                        merged_by=request.reviewer_id,
                        reason=request.reason,
                        merged_at=reviewed_at,
                    ),
                )
            except CanonicalMergeBlocked as exc:
                raise CandidateReviewWorkflowError(
                    "merge_to_canonical decision could not merge candidate"
                ) from exc
        return self._review_payload(review)

    def preview_canonical_merge(self, candidate_fact_id: str) -> CanonicalMergePreview:
        session = self._require_session("preview_canonical_merge")
        candidate = session.get(DataStandardCandidateFactRecord, candidate_fact_id)
        if candidate is None:
            raise CandidateFactNotFound(candidate_fact_id)
        latest_review = self._latest_review_for_candidate(candidate_fact_id)
        existing_merge = self._merge_record_for_candidate(candidate_fact_id)
        canonical_before = _canonical_before(session, candidate)
        canonical_after = _canonical_payload(candidate)
        conflicts = _detect_conflicts(session, candidate)
        unresolved_conflicts = _unresolved_conflicts(conflicts, latest_review)
        blockers: list[str] = []

        if existing_merge is not None:
            blockers.append("candidate_already_merged")
        if latest_review is None:
            blockers.append("candidate_not_reviewed")
        elif (
            latest_review.resulting_candidate_state
            != CandidateFactState.APPROVED_FOR_MERGE.value
        ):
            blockers.append("candidate_not_approved_for_merge")
        if not candidate.provenance_complete:
            blockers.append("provenance_incomplete")
        if candidate.canonical_target_type == CandidateCanonicalTargetType.UNSUPPORTED.value:
            blockers.append("unsupported_canonical_target")
        submission_row = session.get(
            DataStandardPartnerSubmissionRecord,
            candidate.partner_submission_id,
        )
        if submission_row is None:
            blockers.append("partner_submission_missing")
        else:
            blockers.extend(_submission_merge_blockers(submission_row))
        blockers.extend(_merge_provenance_blockers(candidate, latest_review=latest_review))
        if unresolved_conflicts:
            blockers.append("unresolved_conflicts")

        can_merge = not blockers
        action = _merge_action(canonical_before)
        return CanonicalMergePreview(
            candidate_fact_id=candidate.candidate_fact_id,
            canonical_target_type=candidate.canonical_target_type,
            canonical_target_id=candidate.canonical_target_id,
            status=(
                CanonicalMergeStatus.PREVIEW_READY
                if can_merge
                else (
                    CanonicalMergeStatus.MERGED
                    if existing_merge is not None
                    else CanonicalMergeStatus.BLOCKED
                )
            ),
            action=action,
            can_merge=can_merge,
            blockers=tuple(blockers),
            conflicts=tuple(conflicts),
            canonical_before=canonical_before,
            canonical_after=canonical_after,
            provenance_complete=candidate.provenance_complete,
            latest_review=(
                self._review_payload(latest_review)
                if latest_review is not None
                else None
            ),
            ranking_influence_allowed=False,
        )

    def merge_candidate_fact(
        self,
        candidate_fact_id: str,
        request: CanonicalMergeRequest,
    ) -> CanonicalMergeResult:
        session = self._require_session("merge_candidate_fact")
        candidate = session.get(DataStandardCandidateFactRecord, candidate_fact_id)
        if candidate is None:
            raise CandidateFactNotFound(candidate_fact_id)

        preview = self.preview_canonical_merge(candidate_fact_id)
        if not preview.can_merge or preview.action is None:
            raise CanonicalMergeBlocked(preview)

        merged_at = request.merged_at or datetime.now(UTC)
        if preview.action is CanonicalMergeAction.CREATE:
            _create_canonical_record(session, candidate, merged_at=merged_at)
            session.flush()

        latest_review = self._latest_review_for_candidate(candidate_fact_id)
        if latest_review is None:
            raise CanonicalMergeBlocked(preview)
        provenance_link_ids = _bind_provenance(
            session,
            candidate,
            latest_review=latest_review,
            merged_at=merged_at,
        )
        invalidation = _apply_invalidation(session, candidate, merged_at=merged_at)
        audit_event = AdminEventLogService(
            AdminEventLogRepository(session),
            clock=lambda: merged_at,
        ).record_event(
            AdminEventLogInput(
                actor=request.merged_by,
                action="data_standard_candidate_merge",
                object_type=candidate.canonical_target_type,
                object_id=candidate.canonical_target_id,
                before_state=preview.canonical_before,
                after_state=preview.canonical_after,
                reason=request.reason,
                request_id=candidate.candidate_fact_id,
            )
        )
        merge_record = DataStandardCanonicalMergeRecord(
            merge_record_id=_new_id("data_standard_merge"),
            candidate_fact_id=candidate.candidate_fact_id,
            partner_submission_id=candidate.partner_submission_id,
            review_decision_id=latest_review.candidate_review_id,
            canonical_target_type=candidate.canonical_target_type,
            canonical_target_id=candidate.canonical_target_id,
            merge_action=preview.action.value,
            merge_status=CanonicalMergeStatus.MERGED.value,
            conflict_detected=bool(preview.conflicts),
            conflicts_json=[
                conflict.model_dump(mode="json")
                for conflict in preview.conflicts
            ],
            canonical_before_json=preview.canonical_before,
            canonical_after_json=preview.canonical_after or {},
            provenance_binding_json={
                "partner_submission_id": candidate.partner_submission_id,
                "candidate_fact_id": candidate.candidate_fact_id,
                "review_decision_id": latest_review.candidate_review_id,
                "fact_source_link_ids": list(provenance_link_ids),
                "source_ref_count": len(candidate.source_refs_json),
                "source_ref_ids": [
                    ref.get("source_ref_id") for ref in candidate.source_refs_json
                ],
            },
            invalidation_json=[
                directive.model_dump(mode="json")
                for directive in invalidation.directives
            ],
            stale_output_ids_json=list(invalidation.stale_output_ids),
            audit_event_id=audit_event.admin_event_id,
            ranking_influence_allowed=False,
            merged_by=request.merged_by,
            merged_at=merged_at,
            created_at=merged_at,
        )
        session.add(merge_record)
        submission_row = session.get(
            DataStandardPartnerSubmissionRecord,
            candidate.partner_submission_id,
        )
        if submission_row is not None:
            _transition_submission_lifecycle(
                submission_row,
                SubmissionReviewLifecycleState.MERGED,
                actor=request.merged_by,
                reason=request.reason,
            )
        session.flush()
        return CanonicalMergeResult(
            merge_record_id=merge_record.merge_record_id,
            candidate_fact_id=candidate.candidate_fact_id,
            canonical_target_type=candidate.canonical_target_type,
            canonical_target_id=candidate.canonical_target_id,
            status=CanonicalMergeStatus.MERGED,
            action=preview.action,
            audit_event_id=audit_event.admin_event_id,
            provenance_link_ids=tuple(provenance_link_ids),
            invalidation_directives=tuple(
                directive.model_dump(mode="json")
                for directive in invalidation.directives
            ),
            stale_output_ids=tuple(invalidation.stale_output_ids),
            merged_at=merged_at,
            ranking_influence_allowed=False,
        )

    def _require_session(self, operation: str) -> Session:
        if self._session is None:
            raise RuntimeError(f"{operation} requires a database session")
        return self._session

    def _candidate_rows_for_submission(
        self,
        submission_id: str,
    ) -> list[DataStandardCandidateFactRecord]:
        session = self._require_session("_candidate_rows_for_submission")
        rows = session.execute(
            select(DataStandardCandidateFactRecord)
            .where(DataStandardCandidateFactRecord.partner_submission_id == submission_id)
            .order_by(
                DataStandardCandidateFactRecord.created_at.asc(),
                DataStandardCandidateFactRecord.candidate_fact_id.asc(),
            )
        ).scalars()
        return list(rows)

    def _latest_review_for_candidate(
        self,
        candidate_fact_id: str,
    ) -> DataStandardCandidateReviewRecord | None:
        session = self._require_session("_latest_review_for_candidate")
        return session.execute(
            select(DataStandardCandidateReviewRecord)
            .where(
                DataStandardCandidateReviewRecord.candidate_fact_id
                == candidate_fact_id
            )
            .order_by(
                DataStandardCandidateReviewRecord.reviewed_at.desc(),
                DataStandardCandidateReviewRecord.candidate_review_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def _merge_record_for_candidate(
        self,
        candidate_fact_id: str,
    ) -> DataStandardCanonicalMergeRecord | None:
        session = self._require_session("_merge_record_for_candidate")
        return session.execute(
            select(DataStandardCanonicalMergeRecord).where(
                DataStandardCanonicalMergeRecord.candidate_fact_id == candidate_fact_id
            )
        ).scalar_one_or_none()

    def _candidate_payload(
        self,
        row: DataStandardCandidateFactRecord,
    ) -> CandidateFactPayload:
        payload = CandidateFactPayload(
            candidate_fact_id=row.candidate_fact_id,
            partner_submission_id=row.partner_submission_id,
            record_id=row.record_id,
            record_type=row.record_type,
            candidate_state=_effective_candidate_state(
                row,
                latest_review=self._latest_review_for_candidate(row.candidate_fact_id),
                merge_record=self._merge_record_for_candidate(row.candidate_fact_id),
            ),
            canonical_target_type=row.canonical_target_type,
            canonical_target_id=row.canonical_target_id,
            canonical_target_key=row.canonical_target_key_json,
            fact_payload=row.fact_payload_json,
            raw_record=row.raw_record_json,
            provenance=self._provenance_snapshot(row),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        subject = DataStandardsTrustAdapter.from_candidate_payload(payload)
        assessment = TrustAssessmentService().assess(subject)
        routing = RiskRoutingService().decide(assessment, subject)
        report_status = latest_report_recheck_status(
            self._require_session("_candidate_payload"),
            subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
            subject_id=row.candidate_fact_id,
        )
        exception_status = ExceptionWorkflowService(
            self._require_session("_candidate_payload")
        ).get_exception_status_for_subject(
            subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
            subject_id=row.candidate_fact_id,
        )
        safe_exception_status = (
            None
            if exception_status.public_safe_status is PublicExceptionStatus.NO_EXCEPTION
            else exception_status
        )
        explanation = TrustExplanationService().explain(
            assessment=assessment,
            routing=routing,
            subject_type=subject.subject_type,
            subject_id=subject.subject_id,
            report_recheck_status=report_status,
            exception_status=safe_exception_status,
        )
        return payload.model_copy(
            update={
                "trust_tier": assessment.trust_tier,
                "evidence_requirements_met": assessment.evidence_requirements_met,
                "evidence_requirements_missing": assessment.evidence_requirements_missing,
                "evidence_requirements_failed": assessment.evidence_requirements_failed,
                "trust_warnings": assessment.warnings,
                "risk_level": routing.risk_level,
                "routing_outcome": routing.routing_outcome,
                "routing_reasons": routing.routing_reasons,
                "ranking_influence_decision": routing.ranking_influence_decision,
                "ranking_influence_reason": routing.ranking_influence_reason,
                "ranking_influence_reason_codes": (
                    routing.ranking_influence_reason_codes
                ),
                "trust_explanation": explanation,
                "report_recheck_status": report_status,
                "exception_status": safe_exception_status,
            }
        )

    def _review_payload(
        self,
        row: DataStandardCandidateReviewRecord,
    ) -> CandidateReviewPayload:
        return CandidateReviewPayload(
            candidate_review_id=row.candidate_review_id,
            candidate_fact_id=row.candidate_fact_id,
            partner_submission_id=row.partner_submission_id,
            decision=row.decision,
            resulting_candidate_state=row.resulting_candidate_state,
            reviewed_at=row.reviewed_at,
            reviewer_name=row.reviewer_name,
            reason=row.reason,
            source_basis=row.source_basis_json,
            before_after_diff=row.before_after_diff_json,
            audit_event_id=row.audit_event_id,
            resolved_conflict_codes=tuple(row.resolved_conflict_codes_json),
            provenance_complete=row.provenance_complete,
            ranking_influence_allowed=False,
        )

    def _provenance_snapshot(
        self,
        row: DataStandardCandidateFactRecord,
    ) -> CandidateProvenanceSnapshot:
        return CandidateProvenanceSnapshot(
            partner=PartnerIdentityContext(
                partner_id=row.partner_id,
                partner_name=row.partner_name,
                partner_type=row.partner_type,
                verification_status=row.partner_verification_status,
                trust_tier=row.partner_trust_tier,
                region_scope=tuple(
                    _partner_identity_context(row.partner_id).region_scope
                ),
            ),
            submitter_type=row.submitter_type,
            submitted_at=_aware(row.submitted_at),
            source_refs=tuple(
                PartnerSourceRef.model_validate(ref)
                for ref in row.source_refs_json
            ),
            freshness=PartnerFreshness.model_validate(row.freshness_json),
            confidence=PartnerConfidence.model_validate(row.confidence_json),
            provenance_complete=row.provenance_complete,
            provenance_warnings=tuple(row.provenance_warnings_json),
            ranking_influence_allowed=False,
        )


_REGISTRY_TIMESTAMP = datetime(2026, 6, 30, tzinfo=UTC)
_ALL_SUBMISSION_TYPES = tuple(PartnerRecordType)

PARTNER_REGISTRY: tuple[PartnerRegistryRecord, ...] = (
    PartnerRegistryRecord(
        partner_id="partner_state_university",
        name="State University Career Center",
        partner_type=PartnerType.UNIVERSITY,
        region_scope=("statewide",),
        verification_status=PartnerVerificationStatus.VERIFIED,
        allowed_submission_types=(
            PartnerRecordType.EARLY_CAREER_PROGRAM,
            PartnerRecordType.HIRING_SIGNAL,
            PartnerRecordType.COMPANY_REGION_PRESENCE,
        ),
        trust_tier=PartnerTrustTier.TIER_1_VERIFIED_INSTITUTIONAL,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://state-university.example/career-center",
            contact_page_url="https://state-university.example/career-center/contact",
            public_contact_label="Career center public contact page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_metro_workforce_board",
        name="Metro Workforce Board",
        partner_type=PartnerType.WORKFORCE_BOARD,
        region_scope=("metro",),
        verification_status=PartnerVerificationStatus.VERIFIED,
        allowed_submission_types=(
            PartnerRecordType.REGION,
            PartnerRecordType.HIRING_SIGNAL,
            PartnerRecordType.COMPANY_REGION_PRESENCE,
        ),
        trust_tier=PartnerTrustTier.TIER_2_VERIFIED_REGIONAL,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://metro-workforce.example",
            contact_page_url="https://metro-workforce.example/contact",
            public_contact_label="Public workforce board contact page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_bootcamp_network",
        name="Bootcamp Outcomes Network",
        partner_type=PartnerType.BOOTCAMP,
        region_scope=("multi_region",),
        verification_status=PartnerVerificationStatus.PENDING_REVIEW,
        allowed_submission_types=(
            PartnerRecordType.EARLY_CAREER_PROGRAM,
            PartnerRecordType.HIRING_SIGNAL,
        ),
        trust_tier=PartnerTrustTier.TIER_4_LIMITED_PARTNER,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://bootcamp-network.example",
            contact_page_url="https://bootcamp-network.example/partners",
            public_contact_label="Partner information page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_regional_economic_group",
        name="Regional Economic Development Group",
        partner_type=PartnerType.REGIONAL_ECONOMIC_GROUP,
        region_scope=("regional",),
        verification_status=PartnerVerificationStatus.VERIFIED,
        allowed_submission_types=(
            PartnerRecordType.REGION,
            PartnerRecordType.HIRING_SIGNAL,
            PartnerRecordType.COMPANY_REGION_PRESENCE,
        ),
        trust_tier=PartnerTrustTier.TIER_2_VERIFIED_REGIONAL,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://regional-economic-group.example",
            contact_page_url="https://regional-economic-group.example/contact",
            public_contact_label="Economic development public contact page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_career_platform",
        name="Career Platform Exchange",
        partner_type=PartnerType.CAREER_PLATFORM,
        region_scope=("national",),
        verification_status=PartnerVerificationStatus.VERIFIED,
        allowed_submission_types=_ALL_SUBMISSION_TYPES,
        trust_tier=PartnerTrustTier.TIER_3_VERIFIED_PLATFORM,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://career-platform.example",
            contact_page_url="https://career-platform.example/data-partners",
            public_contact_label="Data partner information page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_acme_employer",
        name="Acme Employer Programs",
        partner_type=PartnerType.EMPLOYER,
        region_scope=("company_reported",),
        verification_status=PartnerVerificationStatus.UNVERIFIED,
        allowed_submission_types=(
            PartnerRecordType.COMPANY,
            PartnerRecordType.EARLY_CAREER_PROGRAM,
            PartnerRecordType.HIRING_SIGNAL,
            PartnerRecordType.COMPANY_REGION_PRESENCE,
        ),
        trust_tier=PartnerTrustTier.TIER_4_LIMITED_PARTNER,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://acme.example/careers",
            contact_page_url="https://acme.example/contact",
            public_contact_label="Public careers contact page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_labor_research_group",
        name="Labor Market Research Group",
        partner_type=PartnerType.RESEARCH_GROUP,
        region_scope=("national",),
        verification_status=PartnerVerificationStatus.SUSPENDED,
        allowed_submission_types=(
            PartnerRecordType.REGION,
            PartnerRecordType.HIRING_SIGNAL,
        ),
        trust_tier=PartnerTrustTier.UNTRUSTED,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://labor-research.example",
            contact_page_url="https://labor-research.example/contact",
            public_contact_label="Public research group page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
    PartnerRegistryRecord(
        partner_id="partner_public_labor_agency",
        name="Public Labor Agency",
        partner_type=PartnerType.PUBLIC_AGENCY,
        region_scope=("statewide",),
        verification_status=PartnerVerificationStatus.REVOKED,
        allowed_submission_types=(
            PartnerRecordType.REGION,
            PartnerRecordType.HIRING_SIGNAL,
        ),
        trust_tier=PartnerTrustTier.UNTRUSTED,
        public_contact_metadata=PartnerPublicContactMetadata(
            website_url="https://public-labor-agency.example",
            contact_page_url="https://public-labor-agency.example/contact",
            public_contact_label="Public agency contact page",
        ),
        created_at=_REGISTRY_TIMESTAMP,
        updated_at=_REGISTRY_TIMESTAMP,
    ),
)

PARTNER_REGISTRY_BY_ID = {
    partner.partner_id: partner
    for partner in PARTNER_REGISTRY
}

_SUBMISSION_LIFECYCLE_TRANSITIONS: dict[
    SubmissionReviewLifecycleState,
    frozenset[SubmissionReviewLifecycleState],
] = {
    SubmissionReviewLifecycleState.SUBMITTED: frozenset(
        {
            SubmissionReviewLifecycleState.VALIDATION_FAILED,
            SubmissionReviewLifecycleState.VALIDATION_PASSED,
            SubmissionReviewLifecycleState.WITHDRAWN,
        }
    ),
    SubmissionReviewLifecycleState.VALIDATION_FAILED: frozenset(),
    SubmissionReviewLifecycleState.VALIDATION_PASSED: frozenset(
        {
            SubmissionReviewLifecycleState.ACCEPTED_AS_CANDIDATE,
            SubmissionReviewLifecycleState.REJECTED,
            SubmissionReviewLifecycleState.SUPERSEDED,
            SubmissionReviewLifecycleState.WITHDRAWN,
        }
    ),
    SubmissionReviewLifecycleState.ACCEPTED_AS_CANDIDATE: frozenset(
        {
            SubmissionReviewLifecycleState.UNDER_REVIEW,
            SubmissionReviewLifecycleState.REJECTED,
            SubmissionReviewLifecycleState.SUPERSEDED,
            SubmissionReviewLifecycleState.WITHDRAWN,
        }
    ),
    SubmissionReviewLifecycleState.UNDER_REVIEW: frozenset(
        {
            SubmissionReviewLifecycleState.NEEDS_CHANGES,
            SubmissionReviewLifecycleState.REJECTED,
            SubmissionReviewLifecycleState.MERGED,
            SubmissionReviewLifecycleState.SUPERSEDED,
            SubmissionReviewLifecycleState.WITHDRAWN,
        }
    ),
    SubmissionReviewLifecycleState.NEEDS_CHANGES: frozenset(
        {
            SubmissionReviewLifecycleState.UNDER_REVIEW,
            SubmissionReviewLifecycleState.REJECTED,
            SubmissionReviewLifecycleState.SUPERSEDED,
            SubmissionReviewLifecycleState.WITHDRAWN,
        }
    ),
    SubmissionReviewLifecycleState.REJECTED: frozenset(),
    SubmissionReviewLifecycleState.MERGED: frozenset(),
    SubmissionReviewLifecycleState.SUPERSEDED: frozenset(),
    SubmissionReviewLifecycleState.WITHDRAWN: frozenset(),
}


def _submission_lifecycle_history_entry(
    state: SubmissionReviewLifecycleState,
    *,
    actor: str,
    reason: str,
    at: datetime | None = None,
) -> dict[str, str]:
    timestamp = at or datetime.now(UTC)
    return {
        "state": state.value,
        "actor": actor,
        "reason": reason,
        "at": _aware(timestamp).isoformat(),
    }


def _transition_submission_lifecycle(
    row: DataStandardPartnerSubmissionRecord,
    target_state: SubmissionReviewLifecycleState,
    *,
    actor: str,
    reason: str,
) -> None:
    current = SubmissionReviewLifecycleState(row.review_lifecycle_state)
    if current is target_state:
        return
    allowed = _SUBMISSION_LIFECYCLE_TRANSITIONS[current]
    if target_state not in allowed:
        raise PartnerSubmissionReviewLifecycleError(
            f"invalid submission lifecycle transition: {current.value} -> "
            f"{target_state.value}"
        )
    row.review_lifecycle_state = target_state.value
    row.review_state_history_json = [
        *list(row.review_state_history_json or []),
        _submission_lifecycle_history_entry(
            target_state,
            actor=actor,
            reason=reason,
        ),
    ]


def _assert_submission_can_create_candidates(
    row: DataStandardPartnerSubmissionRecord,
    *,
    returning_existing: bool,
) -> None:
    lifecycle_state = SubmissionReviewLifecycleState(row.review_lifecycle_state)
    if row.validation_status != PartnerValidationStatus.VALIDATED.value:
        raise PartnerSubmissionReviewLifecycleError(
            "candidate creation requires stored validation_status=validated"
        )
    if returning_existing and lifecycle_state in {
        SubmissionReviewLifecycleState.ACCEPTED_AS_CANDIDATE,
        SubmissionReviewLifecycleState.UNDER_REVIEW,
        SubmissionReviewLifecycleState.NEEDS_CHANGES,
        SubmissionReviewLifecycleState.MERGED,
    }:
        return
    if lifecycle_state is not SubmissionReviewLifecycleState.VALIDATION_PASSED:
        raise PartnerSubmissionReviewLifecycleError(
            "candidate creation requires review_lifecycle_state=validation_passed"
        )


def _submission_merge_blockers(row: DataStandardPartnerSubmissionRecord) -> list[str]:
    blockers: list[str] = []
    lifecycle_state = SubmissionReviewLifecycleState(row.review_lifecycle_state)
    if row.validation_status != PartnerValidationStatus.VALIDATED.value:
        blockers.append("submission_validation_not_passed")
    if lifecycle_state in {
        SubmissionReviewLifecycleState.SUBMITTED,
        SubmissionReviewLifecycleState.VALIDATION_FAILED,
        SubmissionReviewLifecycleState.NEEDS_CHANGES,
        SubmissionReviewLifecycleState.REJECTED,
        SubmissionReviewLifecycleState.SUPERSEDED,
        SubmissionReviewLifecycleState.WITHDRAWN,
    }:
        blockers.append(f"submission_state_{lifecycle_state.value}")
    return blockers


def _apply_review_submission_lifecycle(
    row: DataStandardPartnerSubmissionRecord,
    decision: CandidateReviewDecision,
    *,
    actor: str,
    reason: str,
) -> None:
    current = SubmissionReviewLifecycleState(row.review_lifecycle_state)
    if current in {
        SubmissionReviewLifecycleState.ACCEPTED_AS_CANDIDATE,
        SubmissionReviewLifecycleState.NEEDS_CHANGES,
    }:
        _transition_submission_lifecycle(
            row,
            SubmissionReviewLifecycleState.UNDER_REVIEW,
            actor=actor,
            reason="Reviewer opened candidate decision workflow.",
        )
    if decision in {
        CandidateReviewDecision.REQUEST_CHANGES,
        CandidateReviewDecision.REQUEST_CORRECTION,
    }:
        _transition_submission_lifecycle(
            row,
            SubmissionReviewLifecycleState.NEEDS_CHANGES,
            actor=actor,
            reason=reason,
        )
    elif decision in {
        CandidateReviewDecision.REJECT,
        CandidateReviewDecision.REJECT_CANDIDATE,
    }:
        _transition_submission_lifecycle(
            row,
            SubmissionReviewLifecycleState.REJECTED,
            actor=actor,
            reason=reason,
        )


def _submission_from_row(row: DataStandardPartnerSubmissionRecord) -> PartnerSubmission:
    return PartnerSubmission.model_validate(
        {
            "submission_id": row.partner_submission_id,
            "partner_id": row.partner_id,
            "submitted_at": _aware(row.submitted_at),
            "schema_version": row.schema_version,
            "submitter_type": row.submitter_type,
            "records": row.records_json,
            "source_refs": row.source_refs_json,
            "freshness": row.freshness_json,
            "confidence": row.confidence_json,
            "warnings": row.warnings_json,
            "validation_status": row.validation_status,
        }
    )


def _partner_identity_context(partner_id: str) -> PartnerIdentityContext:
    partner = PARTNER_REGISTRY_BY_ID.get(partner_id)
    if partner is None:
        return PartnerIdentityContext(
            partner_id=partner_id,
            partner_name=None,
            partner_type=None,
            verification_status=PartnerVerificationStatus.UNVERIFIED,
            trust_tier=PartnerTrustTier.UNTRUSTED,
            region_scope=(),
        )
    return PartnerIdentityContext(
        partner_id=partner.partner_id,
        partner_name=partner.name,
        partner_type=partner.partner_type,
        verification_status=partner.verification_status,
        trust_tier=partner.trust_tier,
        region_scope=partner.region_scope,
    )


def _candidate_target(record: PartnerSubmissionRecord) -> dict[str, Any]:
    payload = dict(record.payload)
    if record.record_type is PartnerRecordType.COMPANY:
        company_name = str(payload["company_name"])
        normalized = _normalize_name(company_name)
        company_id = _stable_id("company", normalized)
        return {
            "canonical_target_type": CandidateCanonicalTargetType.COMPANY,
            "canonical_target_id": company_id,
            "canonical_target_key": {"normalized_company_name": normalized},
            "fact_payload": {
                "company_id": company_id,
                "company_name": company_name.strip(),
                "normalized_company_name": normalized,
                "sector_primary": _optional_str(payload.get("sector_primary")),
                "company_website": _optional_str(payload.get("company_website")),
            },
        }
    if record.record_type is PartnerRecordType.REGION:
        region_label = str(payload["region_name"])
        normalized = _normalize_name(region_label)
        region_id = _stable_id("region", normalized)
        return {
            "canonical_target_type": CandidateCanonicalTargetType.REGION,
            "canonical_target_id": region_id,
            "canonical_target_key": {"region_name": _slug_name(region_label)},
            "fact_payload": {
                "region_id": region_id,
                "region_name": _slug_name(region_label),
                "display_name": region_label.strip(),
                "region_type": str(payload["region_type"]).strip(),
                "country_code": str(payload["country_code"]).strip().upper(),
            },
        }
    if record.record_type is PartnerRecordType.COMPANY_REGION_PRESENCE:
        company_name = str(payload["company_name"])
        region_name = str(payload["region_name"])
        company_id = _stable_id("company", _normalize_name(company_name))
        region_id = _stable_id("region", _normalize_name(region_name))
        target_id = _stable_id("presence", f"{company_id}:{region_id}")
        return {
            "canonical_target_type": CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE,
            "canonical_target_id": target_id,
            "canonical_target_key": {
                "company_id": company_id,
                "region_id": region_id,
                "normalized_company_name": _normalize_name(company_name),
                "region_name": _slug_name(region_name),
            },
            "fact_payload": {
                "presence_id": target_id,
                "company_id": company_id,
                "region_id": region_id,
                "company_name": company_name.strip(),
                "region_name": region_name.strip(),
                "presence_status": _optional_str(payload.get("presence_status")),
                "observed_at": _optional_str(payload.get("observed_at")),
            },
        }
    if record.record_type is PartnerRecordType.HIRING_SIGNAL:
        company_name = str(payload["company_name"])
        region_name = _optional_str(payload.get("region_name"))
        if region_name is None:
            return _unsupported_target(record)
        company_id = _stable_id("company", _normalize_name(company_name))
        region_id = _stable_id("region", _normalize_name(region_name))
        target_id = _stable_id("hiring", f"{company_id}:{region_id}")
        return {
            "canonical_target_type": CandidateCanonicalTargetType.COMPANY_REGION_HIRING,
            "canonical_target_id": target_id,
            "canonical_target_key": {
                "company_id": company_id,
                "region_id": region_id,
                "normalized_company_name": _normalize_name(company_name),
                "region_name": _slug_name(region_name),
            },
            "fact_payload": {
                "hiring_id": target_id,
                "company_id": company_id,
                "region_id": region_id,
                "company_name": company_name.strip(),
                "region_name": region_name.strip(),
                "signal_type": str(payload["signal_type"]).strip(),
                "observed_at": str(payload["observed_at"]).strip(),
                "active_posting_count_now": payload.get("active_posting_count_now"),
            },
        }
    return _unsupported_target(record)


def _unsupported_target(record: PartnerSubmissionRecord) -> dict[str, Any]:
    return {
        "canonical_target_type": CandidateCanonicalTargetType.UNSUPPORTED,
        "canonical_target_id": _stable_id(
            "unsupported",
            f"{record.record_type.value}:{record.record_id}",
            max_length=128,
        ),
        "canonical_target_key": {
            "record_type": record.record_type.value,
            "record_id": record.record_id,
        },
        "fact_payload": dict(record.payload),
    }


def _provenance_completeness(
    *,
    source_refs: tuple[PartnerSourceRef, ...],
    freshness: PartnerFreshness,
    confidence: PartnerConfidence,
    partner_context: PartnerIdentityContext,
    submitted_at: datetime,
) -> tuple[bool, tuple[str, ...]]:
    warnings: list[str] = []
    if not source_refs:
        warnings.append("source_refs_missing")
    if submitted_at.tzinfo is None:
        warnings.append("submitted_at_not_timezone_aware")
    if freshness.freshness_status is PartnerFreshnessStatus.UNKNOWN:
        warnings.append("freshness_unknown")
    if confidence.confidence_label is Confidence.UNKNOWN:
        warnings.append("confidence_unknown")
    if partner_context.trust_tier is PartnerTrustTier.UNTRUSTED:
        warnings.append("partner_untrusted_or_unregistered")
    if any(ref.license_or_terms_category is None for ref in source_refs):
        warnings.append("source_license_terms_missing")
    hard_gaps = {"source_refs_missing", "submitted_at_not_timezone_aware"}
    return not (set(warnings) & hard_gaps), tuple(warnings)


def _review_resulting_state(decision: CandidateReviewDecision) -> CandidateFactState:
    if decision in {
        CandidateReviewDecision.APPROVE_CANDIDATE,
        CandidateReviewDecision.APPROVE_FOR_MERGE,
        CandidateReviewDecision.RESOLVE_CONFLICTS,
        CandidateReviewDecision.MERGE_TO_CANONICAL,
    }:
        return CandidateFactState.APPROVED_FOR_MERGE
    if decision in {
        CandidateReviewDecision.REJECT,
        CandidateReviewDecision.REJECT_CANDIDATE,
    }:
        return CandidateFactState.REJECTED
    if decision in {
        CandidateReviewDecision.REQUEST_CORRECTION,
        CandidateReviewDecision.REQUEST_CHANGES,
    }:
        return CandidateFactState.NEEDS_CORRECTION
    if decision is CandidateReviewDecision.MARK_CONFLICT:
        return CandidateFactState.CONFLICT
    if decision is CandidateReviewDecision.MARK_DUPLICATE:
        return CandidateFactState.DUPLICATE
    if decision is CandidateReviewDecision.MARK_LOW_CONFIDENCE:
        return CandidateFactState.LOW_CONFIDENCE
    if decision is CandidateReviewDecision.ESCALATE:
        return CandidateFactState.ESCALATED
    raise CandidateReviewWorkflowError(f"unsupported candidate review decision: {decision!r}")


def _review_decision_is_approval(decision: CandidateReviewDecision) -> bool:
    return decision in {
        CandidateReviewDecision.APPROVE_CANDIDATE,
        CandidateReviewDecision.APPROVE_FOR_MERGE,
        CandidateReviewDecision.RESOLVE_CONFLICTS,
        CandidateReviewDecision.MERGE_TO_CANONICAL,
    }


def _resolved_conflict_codes(request: CandidateReviewRequest) -> tuple[str, ...]:
    raw_codes = request.source_basis.get("resolved_conflict_codes")
    if raw_codes is None:
        return ()
    if isinstance(raw_codes, str):
        raw_codes = [raw_codes]
    if not isinstance(raw_codes, list | tuple):
        return ()
    return tuple(
        str(code).strip()
        for code in raw_codes
        if str(code).strip()
    )


def _review_source_basis_license(
    review: DataStandardCandidateReviewRecord | None = None,
    *,
    request_source_basis: Mapping[str, Any] | None = None,
) -> str | None:
    basis = request_source_basis
    if basis is None and review is not None:
        basis = review.source_basis_json
    if basis is None:
        return None
    raw = basis.get("license_or_terms_category")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _merge_provenance_blockers(
    row: DataStandardCandidateFactRecord,
    *,
    latest_review: DataStandardCandidateReviewRecord | None = None,
    request_source_basis: Mapping[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    source_refs = [
        PartnerSourceRef.model_validate(ref)
        for ref in row.source_refs_json
    ]
    if not source_refs:
        blockers.append("source_refs_missing")
    if any(ref.collected_at is None for ref in source_refs):
        blockers.append("source_collected_at_missing")
    if not all(
        ref.license_or_terms_category
        or _review_source_basis_license(
            latest_review,
            request_source_basis=request_source_basis,
        )
        for ref in source_refs
    ):
        blockers.append("license_or_terms_category_missing")
    if row.confidence_json.get("confidence_label") in (None, Confidence.UNKNOWN.value):
        blockers.append("confidence_missing")
    if row.freshness_json.get("freshness_status") in (None, PartnerFreshnessStatus.UNKNOWN.value):
        blockers.append("freshness_missing")
    if latest_review is None and request_source_basis is None:
        blockers.append("review_decision_reference_missing")
    return blockers


def _unresolved_conflicts(
    conflicts: tuple[MergeConflict, ...],
    latest_review: DataStandardCandidateReviewRecord | None,
) -> tuple[MergeConflict, ...]:
    if latest_review is None or latest_review.resulting_candidate_state != (
        CandidateFactState.APPROVED_FOR_MERGE.value
    ):
        return conflicts
    resolved_codes = set(latest_review.resolved_conflict_codes_json or [])
    return tuple(conflict for conflict in conflicts if conflict.code not in resolved_codes)


def _effective_candidate_state(
    row: DataStandardCandidateFactRecord,
    *,
    latest_review: DataStandardCandidateReviewRecord | None,
    merge_record: DataStandardCanonicalMergeRecord | None,
) -> CandidateFactState:
    if merge_record is not None:
        return CandidateFactState.MERGED
    if latest_review is not None:
        return CandidateFactState(latest_review.resulting_candidate_state)
    return CandidateFactState(row.candidate_state)


def _canonical_payload(row: DataStandardCandidateFactRecord) -> dict[str, Any]:
    payload = dict(row.fact_payload_json)
    if row.canonical_target_type == CandidateCanonicalTargetType.COMPANY.value:
        return {
            "company_id": row.canonical_target_id,
            "company_name": payload["company_name"],
            "normalized_company_name": payload["normalized_company_name"],
            "sector_primary": payload.get("sector_primary"),
            "classification_confidence": row.confidence_json.get("confidence_label"),
        }
    if row.canonical_target_type == CandidateCanonicalTargetType.REGION.value:
        return {
            "region_id": row.canonical_target_id,
            "region_name": payload["region_name"],
            "display_name": payload["display_name"],
            "region_type": payload["region_type"],
        }
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE.value
    ):
        status, basis = _presence_status_and_basis(payload.get("presence_status"))
        return {
            "presence_id": row.canonical_target_id,
            "company_id": payload["company_id"],
            "region_id": payload["region_id"],
            "presence_status": status,
            "presence_basis": basis,
            "office_evidence_flag": "office" in str(payload.get("presence_status", "")),
            "operations_evidence_flag": "operations"
            in str(payload.get("presence_status", "")),
            "hiring_evidence_flag": "hiring" in str(payload.get("presence_status", "")),
            "presence_confidence": row.confidence_json.get("confidence_label"),
            "source_refs": row.source_refs_json,
        }
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_HIRING.value
    ):
        active_count = payload.get("active_posting_count_now")
        return {
            "hiring_id": row.canonical_target_id,
            "company_id": payload["company_id"],
            "region_id": payload["region_id"],
            "currently_hiring_flag": _hiring_signal_is_active(payload),
            "active_posting_count_now": active_count if isinstance(active_count, int) else None,
            "hiring_confidence": row.confidence_json.get("confidence_label"),
            "source_refs": row.source_refs_json,
        }
    return {}


def _canonical_before(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> dict[str, Any] | None:
    if row.canonical_target_type == CandidateCanonicalTargetType.COMPANY.value:
        existing = session.get(Company, row.canonical_target_id)
        return _company_dict(existing) if existing is not None else None
    if row.canonical_target_type == CandidateCanonicalTargetType.REGION.value:
        existing = session.get(Region, row.canonical_target_id)
        return _region_dict(existing) if existing is not None else None
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE.value
    ):
        existing = session.get(CompanyRegionPresence, row.canonical_target_id)
        return _presence_dict(existing) if existing is not None else None
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_HIRING.value
    ):
        existing = session.get(CompanyRegionHiring, row.canonical_target_id)
        return _hiring_dict(existing) if existing is not None else None
    return None


def _detect_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    conflicts = list(_provenance_conflicts(session, row))
    if row.canonical_target_type == CandidateCanonicalTargetType.COMPANY.value:
        conflicts.extend(_company_conflicts(session, row))
        return tuple(conflicts)
    if row.canonical_target_type == CandidateCanonicalTargetType.REGION.value:
        conflicts.extend(_region_conflicts(session, row))
        return tuple(conflicts)
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE.value
    ):
        conflicts.extend(_presence_conflicts(session, row))
        return tuple(conflicts)
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_HIRING.value
    ):
        conflicts.extend(_hiring_conflicts(session, row))
        return tuple(conflicts)
    return tuple(conflicts)


def _provenance_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    conflicts: list[MergeConflict] = []
    if row.freshness_json.get("freshness_status") == PartnerFreshnessStatus.STALE.value:
        conflicts.append(
            _conflict(
                "stale_source",
                "freshness.freshness_status",
                "Candidate source freshness is stale.",
                candidate_value=row.freshness_json.get("freshness_status"),
            )
        )
    canonical_before = _canonical_before(session, row)
    if (
        canonical_before is not None
        and _partner_trust_rank(row.partner_trust_tier) < 3
        and _has_higher_trust_existing_source(session, row)
    ):
        conflicts.append(
            _conflict(
                "lower_trust_source_conflict",
                "partner_trust_tier",
                "Candidate comes from a lower-trust partner than existing canonical evidence.",
                canonical_value="higher_trust_existing_source",
                candidate_value=row.partner_trust_tier,
            )
        )
    return tuple(conflicts)


def _company_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    payload = _canonical_payload(row)
    conflicts: list[MergeConflict] = []
    existing = session.get(Company, row.canonical_target_id)
    duplicate = session.execute(
        select(Company)
        .where(Company.normalized_company_name == payload["normalized_company_name"])
        .where(Company.company_id != row.canonical_target_id)
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        conflicts.append(
            _conflict(
                "duplicate_canonical_key",
                "normalized_company_name",
                "Another canonical company already owns this normalized name.",
                canonical_value=duplicate.company_id,
                candidate_value=row.canonical_target_id,
            )
        )
    if existing is not None and (
        existing.normalized_company_name != payload["normalized_company_name"]
    ):
        conflicts.append(
            _conflict(
                "canonical_value_mismatch",
                "normalized_company_name",
                "Candidate company key differs from the existing canonical row.",
                canonical_value=existing.normalized_company_name,
                candidate_value=payload["normalized_company_name"],
            )
        )
    if (
        existing is not None
        and existing.sector_primary is not None
        and payload.get("sector_primary") is not None
        and existing.sector_primary != payload.get("sector_primary")
    ):
        conflicts.append(
            _conflict(
                "canonical_value_mismatch",
                "sector_primary",
                "Candidate sector conflicts with existing canonical company sector.",
                canonical_value=existing.sector_primary,
                candidate_value=payload.get("sector_primary"),
            )
        )
    return tuple(conflicts)


def _region_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    payload = _canonical_payload(row)
    conflicts: list[MergeConflict] = []
    existing = session.get(Region, row.canonical_target_id)
    duplicate = session.execute(
        select(Region)
        .where(Region.region_name == payload["region_name"])
        .where(Region.region_id != row.canonical_target_id)
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        conflicts.append(
            _conflict(
                "duplicate_canonical_key",
                "region_name",
                "Another canonical region already owns this region name.",
                canonical_value=duplicate.region_id,
                candidate_value=row.canonical_target_id,
            )
        )
    if existing is not None and existing.region_type != payload["region_type"]:
        conflicts.append(
            _conflict(
                "canonical_value_mismatch",
                "region_type",
                "Candidate region type conflicts with existing canonical region.",
                canonical_value=existing.region_type,
                candidate_value=payload["region_type"],
            )
        )
    return tuple(conflicts)


def _presence_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    payload = _canonical_payload(row)
    conflicts = _dependency_conflicts(session, payload)
    existing = session.get(CompanyRegionPresence, row.canonical_target_id)
    duplicate = session.execute(
        select(CompanyRegionPresence)
        .where(CompanyRegionPresence.company_id == payload["company_id"])
        .where(CompanyRegionPresence.region_id == payload["region_id"])
        .where(CompanyRegionPresence.presence_id != row.canonical_target_id)
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        conflicts.append(
            _conflict(
                "duplicate_canonical_key",
                "company_region_pair",
                "Another canonical presence row already owns this pair.",
                canonical_value=duplicate.presence_id,
                candidate_value=row.canonical_target_id,
            )
        )
    if existing is not None and existing.presence_status != payload["presence_status"]:
        conflicts.append(
            _conflict(
                "canonical_value_mismatch",
                "presence_status",
                "Candidate presence status conflicts with existing canonical presence.",
                canonical_value=existing.presence_status,
                candidate_value=payload["presence_status"],
            )
        )
    return tuple(conflicts)


def _hiring_conflicts(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> tuple[MergeConflict, ...]:
    payload = _canonical_payload(row)
    conflicts = _dependency_conflicts(session, payload)
    existing = session.get(CompanyRegionHiring, row.canonical_target_id)
    duplicate = session.execute(
        select(CompanyRegionHiring)
        .where(CompanyRegionHiring.company_id == payload["company_id"])
        .where(CompanyRegionHiring.region_id == payload["region_id"])
        .where(CompanyRegionHiring.hiring_id != row.canonical_target_id)
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        conflicts.append(
            _conflict(
                "duplicate_canonical_key",
                "company_region_pair",
                "Another canonical hiring row already owns this pair.",
                canonical_value=duplicate.hiring_id,
                candidate_value=row.canonical_target_id,
            )
        )
    if (
        existing is not None
        and existing.currently_hiring_flag != payload["currently_hiring_flag"]
    ):
        conflicts.append(
            _conflict(
                "canonical_value_mismatch",
                "currently_hiring_flag",
                "Candidate hiring signal conflicts with existing canonical hiring.",
                canonical_value=existing.currently_hiring_flag,
                candidate_value=payload["currently_hiring_flag"],
            )
        )
    if (
        existing is not None
        and existing.active_posting_count_now is not None
        and payload.get("active_posting_count_now") is not None
        and existing.active_posting_count_now != payload.get("active_posting_count_now")
    ):
        conflicts.append(
            _conflict(
                "numeric_mismatch",
                "active_posting_count_now",
                "Candidate active posting count conflicts with canonical hiring count.",
                canonical_value=existing.active_posting_count_now,
                candidate_value=payload.get("active_posting_count_now"),
            )
        )
    return tuple(conflicts)


def _dependency_conflicts(session: Session, payload: dict[str, Any]) -> list[MergeConflict]:
    conflicts: list[MergeConflict] = []
    if session.get(Company, payload["company_id"]) is None:
        conflicts.append(
            _conflict(
                "missing_dependency",
                "company_id",
                "Company-region candidate requires a canonical company row first.",
                candidate_value=payload["company_id"],
            )
        )
    if session.get(Region, payload["region_id"]) is None:
        conflicts.append(
            _conflict(
                "missing_dependency",
                "region_id",
                "Company-region candidate requires a canonical region row first.",
                candidate_value=payload["region_id"],
            )
        )
    return conflicts


def _create_canonical_record(
    session: Session,
    row: DataStandardCandidateFactRecord,
    *,
    merged_at: datetime,
) -> None:
    payload = _canonical_payload(row)
    if row.canonical_target_type == CandidateCanonicalTargetType.COMPANY.value:
        session.add(
            Company(
                company_id=payload["company_id"],
                company_name=payload["company_name"],
                normalized_company_name=payload["normalized_company_name"],
                sector_primary=payload.get("sector_primary"),
                classification_confidence=payload.get("classification_confidence"),
                created_at=merged_at,
                updated_at=merged_at,
            )
        )
        return
    if row.canonical_target_type == CandidateCanonicalTargetType.REGION.value:
        session.add(
            Region(
                region_id=payload["region_id"],
                region_name=payload["region_name"],
                display_name=payload["display_name"],
                region_type=payload["region_type"],
                created_at=merged_at,
                updated_at=merged_at,
            )
        )
        return
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE.value
    ):
        session.add(
            CompanyRegionPresence(
                presence_id=payload["presence_id"],
                company_id=payload["company_id"],
                region_id=payload["region_id"],
                presence_status=payload["presence_status"],
                presence_basis=payload["presence_basis"],
                office_evidence_flag=payload["office_evidence_flag"],
                operations_evidence_flag=payload["operations_evidence_flag"],
                hiring_evidence_flag=payload["hiring_evidence_flag"],
                presence_confidence=payload["presence_confidence"],
                source_refs=payload["source_refs"],
                created_at=merged_at,
                updated_at=merged_at,
            )
        )
        return
    if (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_HIRING.value
    ):
        session.add(
            CompanyRegionHiring(
                hiring_id=payload["hiring_id"],
                company_id=payload["company_id"],
                region_id=payload["region_id"],
                currently_hiring_flag=payload["currently_hiring_flag"],
                active_posting_count_now=payload["active_posting_count_now"],
                hiring_confidence=payload["hiring_confidence"],
                source_refs=payload["source_refs"],
                created_at=merged_at,
                updated_at=merged_at,
            )
        )


def _bind_provenance(
    session: Session,
    row: DataStandardCandidateFactRecord,
    *,
    latest_review: DataStandardCandidateReviewRecord,
    merged_at: datetime,
) -> tuple[str, ...]:
    link_ids: list[str] = []
    for raw_ref in row.source_refs_json:
        ref = PartnerSourceRef.model_validate(raw_ref)
        license_or_terms_category = (
            ref.license_or_terms_category
            or _review_source_basis_license(latest_review)
        )
        if license_or_terms_category is None:
            raise CanonicalMergeBlocked(
                CanonicalMergePreview(
                    candidate_fact_id=row.candidate_fact_id,
                    canonical_target_type=row.canonical_target_type,
                    canonical_target_id=row.canonical_target_id,
                    status=CanonicalMergeStatus.BLOCKED,
                    can_merge=False,
                    blockers=("license_or_terms_category_missing",),
                    provenance_complete=row.provenance_complete,
                    ranking_influence_allowed=False,
                )
            )
        source_id = _stable_id(
            "source",
            f"{ref.source_type}:{ref.url or ref.citation or ref.source_ref_id}",
        )
        observed_at = _coerce_observed_at(
            ref.collected_at,
            row.freshness_json.get("observed_at"),
            row.submitted_at,
        )
        collected_at = _coerce_observed_at(ref.collected_at, None, row.submitted_at)
        if session.get(SourceRef, source_id) is None:
            session.add(
                SourceRef(
                    source_id=source_id,
                    source_type=ref.source_type,
                    source_name=row.partner_name or row.partner_id,
                    url_or_provider=ref.url or ref.citation or ref.source_ref_id,
                    collected_at=collected_at,
                    observed_at=observed_at,
                    license_or_terms_category=license_or_terms_category,
                    confidence=row.confidence_json.get("confidence_label", "unknown"),
                    data_origin="partner_submission",
                    notes=_provenance_notes(ref.notes, row, latest_review),
                    created_at=merged_at,
                    updated_at=merged_at,
                )
            )
        observation_id = _stable_id(
            "obs",
            f"{row.candidate_fact_id}:{ref.source_ref_id}",
        )
        if session.get(SourceObservation, observation_id) is None:
            session.add(
                SourceObservation(
                    observation_id=observation_id,
                    source_id=source_id,
                    source_type=ref.source_type,
                    source_name=row.partner_name or row.partner_id,
                    url_or_provider=ref.url or ref.citation or ref.source_ref_id,
                    collected_at=collected_at,
                    observed_at=observed_at,
                    license_or_terms_category=license_or_terms_category,
                    confidence=row.confidence_json.get("confidence_label", "unknown"),
                    data_origin="partner_submission",
                    observation_status="active",
                    notes=_provenance_notes(ref.notes, row, latest_review),
                    created_at=merged_at,
                    updated_at=merged_at,
                )
            )
        link_id = _stable_id(
            "fsl",
            f"{row.candidate_fact_id}:{ref.source_ref_id}:{row.canonical_target_id}",
            max_length=128,
        )
        if session.get(FactSourceLink, link_id) is None:
            session.add(
                FactSourceLink(
                    link_id=link_id,
                    observation_id=observation_id,
                    source_id=source_id,
                    fact_type=row.canonical_target_type,
                    fact_id=row.canonical_target_id,
                    fact_field=None,
                    source_type=ref.source_type,
                    source_name=row.partner_name or row.partner_id,
                    url_or_provider=ref.url or ref.citation or ref.source_ref_id,
                    collected_at=collected_at,
                    observed_at=observed_at,
                    license_or_terms_category=license_or_terms_category,
                    confidence=row.confidence_json.get("confidence_label", "unknown"),
                    data_origin="partner_submission",
                    observation_status="active",
                    notes=_provenance_notes(ref.notes, row, latest_review),
                    created_at=merged_at,
                    updated_at=merged_at,
                )
            )
        link_ids.append(link_id)
    session.flush()
    return tuple(link_ids)


def _provenance_notes(
    ref_notes: str | None,
    row: DataStandardCandidateFactRecord,
    latest_review: DataStandardCandidateReviewRecord,
) -> str:
    parts = [
        f"partner_submission_id={row.partner_submission_id}",
        f"candidate_fact_id={row.candidate_fact_id}",
        f"review_decision_id={latest_review.candidate_review_id}",
    ]
    if ref_notes:
        parts.append(f"source_notes={ref_notes}")
    return "; ".join(parts)


def _apply_invalidation(
    session: Session,
    row: DataStandardCandidateFactRecord,
    *,
    merged_at: datetime,
) -> InvalidationApplyResult:
    event = _merge_event(row, emitted_at=merged_at)
    if event is None:
        return InvalidationApplyResult(directives=[], stale_output_ids=[])
    return InvalidationService().mark_stale_for(event, session=session)


def _merge_event(
    row: DataStandardCandidateFactRecord,
    *,
    emitted_at: datetime,
) -> Event | None:
    scope: dict[str, Any]
    event_type: EventType
    if row.canonical_target_type == CandidateCanonicalTargetType.COMPANY.value:
        event_type = EventType.NEW_COMPANY_CANDIDATE_ADDED
        scope = {"company_id": row.canonical_target_id}
    elif row.canonical_target_type == CandidateCanonicalTargetType.REGION.value:
        event_type = EventType.REGION_ADDED
        scope = {"region_id": row.canonical_target_id}
    elif (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_PRESENCE.value
    ):
        event_type = EventType.COMPANY_PRESENCE_UPDATED
        scope = {"company_region_pairs": [row.canonical_target_key_json]}
    elif (
        row.canonical_target_type
        == CandidateCanonicalTargetType.COMPANY_REGION_HIRING.value
    ):
        event_type = EventType.HIRING_DATA_UPDATED
        scope = {"company_region_pairs": [row.canonical_target_key_json]}
    else:
        return None
    return Event(
        event_id=_stable_id("event", f"{row.candidate_fact_id}:{event_type.value}"),
        event_type=event_type,
        emitted_at=emitted_at,
        source="data_standard_canonical_merge",
        scope=scope,
        payload={"candidate_fact_id": row.candidate_fact_id},
        correlation_id=row.candidate_fact_id,
    )


def _merge_action(canonical_before: dict[str, Any] | None) -> CanonicalMergeAction:
    return (
        CanonicalMergeAction.NOOP
        if canonical_before is not None
        else CanonicalMergeAction.CREATE
    )


def _company_dict(row: Company | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "company_id": row.company_id,
        "company_name": row.company_name,
        "normalized_company_name": row.normalized_company_name,
        "sector_primary": row.sector_primary,
        "classification_confidence": row.classification_confidence,
    }


def _region_dict(row: Region | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "region_id": row.region_id,
        "region_name": row.region_name,
        "display_name": row.display_name,
        "region_type": row.region_type,
    }


def _presence_dict(row: CompanyRegionPresence | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "presence_id": row.presence_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "presence_status": row.presence_status,
        "presence_basis": row.presence_basis,
        "office_evidence_flag": row.office_evidence_flag,
        "operations_evidence_flag": row.operations_evidence_flag,
        "hiring_evidence_flag": row.hiring_evidence_flag,
        "presence_confidence": row.presence_confidence,
        "source_refs": row.source_refs,
    }


def _hiring_dict(row: CompanyRegionHiring | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "hiring_id": row.hiring_id,
        "company_id": row.company_id,
        "region_id": row.region_id,
        "currently_hiring_flag": row.currently_hiring_flag,
        "active_posting_count_now": row.active_posting_count_now,
        "hiring_confidence": row.hiring_confidence,
        "source_refs": row.source_refs,
    }


def _conflict(
    code: str,
    field: str,
    message: str,
    *,
    canonical_value: Any = None,
    candidate_value: Any = None,
) -> MergeConflict:
    return MergeConflict(
        code=code,
        field=field,
        message=message,
        canonical_value=canonical_value,
        candidate_value=candidate_value,
    )


def _partner_trust_rank(trust_tier: str) -> int:
    ranks = {
        PartnerTrustTier.UNTRUSTED.value: 0,
        PartnerTrustTier.TIER_4_LIMITED_PARTNER.value: 1,
        PartnerTrustTier.TIER_3_VERIFIED_PLATFORM.value: 2,
        PartnerTrustTier.TIER_2_VERIFIED_REGIONAL.value: 3,
        PartnerTrustTier.TIER_1_VERIFIED_INSTITUTIONAL.value: 4,
    }
    return ranks.get(trust_tier, 0)


def _quality_label_payload(label: DataQualityLabel) -> DataQualityLabel:
    if label.trust_explanation is not None:
        return label
    return label.model_copy(
        update={
            "trust_explanation": TrustExplanation(
                subject_type=TrustAssessmentSubjectType.DATA_STANDARD_FACT,
                subject_id=f"quality_label:{label.label.value}",
                trust_tier=TrustTier.RANKING_INELIGIBLE,
                trust_label="Excluded from rankings",
                trust_summary=(
                    "This quality label is visible data-standard metadata. It does "
                    "not grant ranking influence."
                ),
                risk_level=RiskLevel.LOW,
                risk_label="Low risk",
                risk_summary=(
                    "This label is safe to display, but it is not ranking evidence."
                ),
                routing_outcome=RoutingOutcome.AUTO_ACCEPT_NON_RANKING,
                routing_label="Visible, not used in rankings",
                routing_summary=(
                    "This label can be shown to users while remaining separate from "
                    "ranking influence."
                ),
                ranking_influence_allowed=False,
                ranking_influence_decision=RankingInfluenceDecision.DENIED,
                ranking_influence_label="Excluded from rankings",
                ranking_influence_reason=(
                    "Data-standard quality labels are informational metadata and do "
                    "not affect rankings unless a later deterministic ranking decision "
                    "explicitly allows it."
                ),
            )
        }
    )


def _has_higher_trust_existing_source(
    session: Session,
    row: DataStandardCandidateFactRecord,
) -> bool:
    links = session.execute(
        select(FactSourceLink)
        .where(FactSourceLink.fact_type == row.canonical_target_type)
        .where(FactSourceLink.fact_id == row.canonical_target_id)
        .limit(10)
    ).scalars()
    trusted_origins = {"real_observed", "public_dataset", "manual_verified"}
    trusted_source_types = {
        "public_agency",
        "government_public",
        "institutional_public",
        "company_official",
        "employer_official",
    }
    return any(
        link.data_origin in trusted_origins or link.source_type in trusted_source_types
        for link in links
    )


def _presence_status_and_basis(raw_status: Any) -> tuple[str, str | None]:
    status = str(raw_status or "").strip()
    if status in {"not_present", "absent"}:
        return "not_present", "insufficient_evidence"
    if status in {"uncertain", "unknown", "insufficient_evidence"}:
        return "uncertain", "insufficient_evidence"
    if status:
        return "present", status
    return "uncertain", "insufficient_evidence"


def _hiring_signal_is_active(payload: Mapping[str, Any]) -> bool:
    signal_type = str(payload.get("signal_type", "")).casefold()
    active_count = payload.get("active_posting_count_now")
    if isinstance(active_count, int):
        return active_count > 0
    return signal_type not in {"no_hiring", "closed", "inactive"}


def _coerce_observed_at(
    value: datetime | date | str | None,
    fallback_value: datetime | date | str | None,
    submitted_at: datetime,
) -> datetime:
    for candidate in (value, fallback_value, submitted_at):
        if isinstance(candidate, datetime):
            return _aware(candidate)
        if isinstance(candidate, date):
            return datetime.combine(candidate, time.min, tzinfo=UTC)
        if isinstance(candidate, str) and candidate:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                try:
                    return datetime.combine(
                        date.fromisoformat(candidate),
                        time.min,
                        tzinfo=UTC,
                    )
                except ValueError:
                    continue
            return _aware(parsed)
    return _aware(submitted_at)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _slug_name(value: str) -> str:
    normalized = _normalize_name(value)
    out = []
    for char in normalized:
        if char.isalnum():
            out.append(char)
        elif char in {" ", "-", "_"}:
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "unknown"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _new_id(prefix: str) -> str:
    return _stable_id(prefix, uuid4().hex, max_length=128)


def _stable_id(prefix: str, seed: str, *, max_length: int = 64) -> str:
    digest = sha256(seed.encode("utf-8")).hexdigest()[:24]
    prefix_room = max(1, max_length - len(digest) - 1)
    safe_prefix = _slug_name(prefix)[:prefix_room]
    return f"{safe_prefix}_{digest}"


QUALITY_LABELS: tuple[DataQualityLabel, ...] = (
    DataQualityLabel(
        label=DataQualityLabelValue.VERIFIED_PARTNER_DATA,
        display_name="Verified Partner Data",
        description=(
            "Partner-submitted data that is eligible only when the partner is "
            "verified and the record includes source refs."
        ),
        allowed_sources=(
            "employer_official",
            "institutional_partner",
            "workforce_board",
            "public_agency",
            "partner_submission",
        ),
        minimum_confidence=Confidence.MEDIUM,
        requires_source_refs=True,
        requires_partner_verification=True,
        ranking_influence_allowed=False,
        public_display_allowed=True,
        warning_copy=(
            "Verified partner status does not certify record content; source, "
            "freshness, and confidence checks still apply."
        ),
    ),
    DataQualityLabel(
        label=DataQualityLabelValue.AUDITED_SOURCE_DATA,
        display_name="Audited Source Data",
        description=(
            "Data eligible for this label only when source refs and an "
            "audit/review marker are present."
        ),
        allowed_sources=(
            "audited_partner_source",
            "reviewed_public_source",
            "public_agency",
            "institutional_public",
        ),
        minimum_confidence=Confidence.MEDIUM,
        requires_source_refs=True,
        requires_partner_verification=False,
        ranking_influence_allowed=False,
        public_display_allowed=True,
        warning_copy=(
            "Audited source labels identify review eligibility only and do not "
            "merge records into canonical intelligence."
        ),
    ),
    DataQualityLabel(
        label=DataQualityLabelValue.SELF_REPORTED_EMPLOYER_DATA,
        display_name="Self-Reported Employer Data",
        description=(
            "Employer-provided data that remains self-reported and requires "
            "warning copy even when source refs are present."
        ),
        allowed_sources=("employer_official", "partner_submission"),
        minimum_confidence=Confidence.LOW,
        requires_source_refs=True,
        requires_partner_verification=False,
        ranking_influence_allowed=False,
        public_display_allowed=True,
        warning_copy=(
            "This is self-reported employer data and should be reviewed before "
            "being used as canonical market evidence."
        ),
    ),
    DataQualityLabel(
        label=DataQualityLabelValue.PUBLIC_SOURCE_VERIFIED,
        display_name="Public Source Verified",
        description=(
            "Data eligible when a public source ref supports the submitted "
            "record and confidence is at least medium."
        ),
        allowed_sources=(
            "public_source",
            "employer_official",
            "public_agency",
            "government_public",
            "institutional_public",
            "career_platform_public",
        ),
        minimum_confidence=Confidence.MEDIUM,
        requires_source_refs=True,
        requires_partner_verification=False,
        ranking_influence_allowed=False,
        public_display_allowed=True,
        warning_copy=(
            "Public source verification confirms a cited source exists; it is "
            "not a canonical merge or ranking signal."
        ),
    ),
    DataQualityLabel(
        label=DataQualityLabelValue.LOW_CONFIDENCE_SIGNAL,
        display_name="Low Confidence Signal",
        description=(
            "Records with weak, stale, incomplete, or low-confidence evidence "
            "that should be treated as limited signals."
        ),
        allowed_sources=("*",),
        minimum_confidence=Confidence.UNKNOWN,
        requires_source_refs=False,
        requires_partner_verification=False,
        ranking_influence_allowed=False,
        public_display_allowed=True,
        warning_copy=(
            "Low-confidence signals are not ranking inputs and require review "
            "before any downstream use."
        ),
    ),
)

QUALITY_LABELS_BY_VALUE = {
    label.label: label
    for label in QUALITY_LABELS
}

GOVERNANCE_FRAMEWORK: tuple[GovernanceFrameworkRecord, ...] = (
    GovernanceFrameworkRecord(
        area=GovernanceArea.DATA_ETHICS,
        display_name="Data Ethics",
        description=(
            "Guidance for responsible partner intake, public standards display, "
            "and separation between submitted data and canonical intelligence."
        ),
        review_questions=(
            "Does the submission identify who provided the data and why it was collected?",
            "Are private notes, private contact details, or internal review fields excluded?",
            "Could public display imply stronger authority than the evidence supports?",
        ),
        risk_flags=(
            "private_fields_present",
            "authority_overclaim",
            "unclear_partner_context",
        ),
        recommended_controls=(
            "Keep partner intake separate from canonical market records.",
            "Require source refs, freshness, and confidence before certification eligibility.",
            "Use public-safe partner contact metadata only.",
        ),
        status=GovernanceStatus.FRAMEWORK_DEFINED,
        version=GOVERNANCE_FRAMEWORK_VERSION,
        public_summary=(
            "Layer 27 defines ethics guidance for standards and intake; it is "
            "not an active external governance board."
        ),
    ),
    GovernanceFrameworkRecord(
        area=GovernanceArea.LABOR_MARKET_FAIRNESS,
        display_name="Labor Market Fairness",
        description=(
            "Guidance for avoiding unfair amplification of incomplete, stale, "
            "or self-reported labor-market data."
        ),
        review_questions=(
            "Could this data underrepresent smaller employers, regions, or programs?",
            "Is low-confidence or stale data clearly labeled before public display?",
            "Would use of the record create hidden ranking or recommendation bias?",
        ),
        risk_flags=(
            "coverage_gap",
            "low_confidence_signal",
            "hidden_ranking_bias",
        ),
        recommended_controls=(
            "Default quality labels to no ranking influence.",
            "Expose warning copy for low-confidence and self-reported data.",
            "Require downstream tests before any ranking or recommendation use.",
        ),
        status=GovernanceStatus.FRAMEWORK_DEFINED,
        version=GOVERNANCE_FRAMEWORK_VERSION,
        public_summary=(
            "Fairness guidance is defined for review; it does not alter "
            "rankings, recommendations, forecasts, policy outputs, or scores."
        ),
    ),
    GovernanceFrameworkRecord(
        area=GovernanceArea.SOURCE_STANDARDS,
        display_name="Source Standards",
        description=(
            "Guidance for source refs, freshness, confidence, and quality-label "
            "eligibility in partner-submitted records."
        ),
        review_questions=(
            "Are source refs attached where the record type requires them?",
            "Is freshness declared and clear enough for downstream review?",
            "Does the confidence label match the source and review basis?",
        ),
        risk_flags=(
            "missing_source_refs",
            "stale_freshness",
            "confidence_mismatch",
        ),
        recommended_controls=(
            "Reject records without required source refs.",
            "Carry freshness and confidence through API serialization.",
            "Keep source refs as eligibility metadata until review/merge exists.",
        ),
        status=GovernanceStatus.FRAMEWORK_DEFINED,
        version=GOVERNANCE_FRAMEWORK_VERSION,
        public_summary=(
            "Source standards guide validation and quality-label eligibility; "
            "they do not certify submitted facts automatically."
        ),
    ),
    GovernanceFrameworkRecord(
        area=GovernanceArea.INSTITUTIONAL_USE,
        display_name="Institutional Use",
        description=(
            "Guidance for universities, workforce boards, and institutions using "
            "Layer 27 standards in advising, reporting, or data-sharing workflows."
        ),
        review_questions=(
            "Is institutional data aggregate-safe and public-display appropriate?",
            "Does the payload separate partner context from product-owned evidence?",
            "Are students, cohorts, and partners protected from private data leakage?",
        ),
        risk_flags=(
            "private_student_data",
            "partner_context_as_evidence",
            "public_private_boundary_blur",
        ),
        recommended_controls=(
            "Keep memory, partner records, and institutional private data out of public payloads.",
            "Use partner verification only as registry metadata.",
            "Document that validation, labeling, and canonical acceptance are separate.",
        ),
        status=GovernanceStatus.FRAMEWORK_DEFINED,
        version=GOVERNANCE_FRAMEWORK_VERSION,
        public_summary=(
            "Institutional guidance is standards metadata for safe use; no "
            "institutional approval board is active in this layer."
        ),
    ),
    GovernanceFrameworkRecord(
        area=GovernanceArea.BIAS_REVIEW,
        display_name="Bias Review",
        description=(
            "Guidance for identifying hidden employer, partner, regional, or "
            "source-quality bias before any future downstream use."
        ),
        review_questions=(
            "Could partner status be mistaken for data certification?",
            "Could paid, partner, employer, or regional influence be hidden?",
            "Do warning labels remain visible to public and institutional users?",
        ),
        risk_flags=(
            "partner_verification_confused_with_certification",
            "hidden_partner_influence",
            "warning_suppression",
        ),
        recommended_controls=(
            "Disclose partner and quality-label boundaries in public surfaces.",
            "Keep all quality labels non-ranking until an explicit consumer contract exists.",
            "Test that warnings and non-authority language survive UI rendering.",
        ),
        status=GovernanceStatus.FRAMEWORK_DEFINED,
        version=GOVERNANCE_FRAMEWORK_VERSION,
        public_summary=(
            "Bias-review scaffolding is defined, but no active governance board "
            "or external approval process is claimed."
        ),
    ),
)


STANDARD_DEFINITIONS: tuple[StandardDefinition, ...] = (
    StandardDefinition(
        term="entry-level role",
        canonical_name="entry_level_role",
        description=(
            "A role intended for candidates at the beginning of a career path, "
            "typically requiring limited full-time professional experience."
        ),
        inclusion_criteria=(
            "Explicitly labeled entry-level, new graduate, associate, junior, or equivalent.",
            "Requires limited prior full-time experience or is designed for recent graduates.",
            "Has duties that can be performed with supervised onboarding.",
        ),
        exclusion_criteria=(
            "Mid-level, senior, staff, principal, or manager roles.",
            "Roles requiring extensive specialized professional experience.",
            "Unpaid training-only listings without a defined role or program.",
        ),
        examples=("Software Engineer I", "Junior Data Analyst", "New Graduate Consultant"),
        related_terms=("internship", "early_career_program"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="internship",
        canonical_name="internship",
        description=(
            "A time-bounded early-career work experience intended for students, "
            "recent graduates, or career entrants."
        ),
        inclusion_criteria=(
            "Has a defined temporary term or cohort window.",
            "Is positioned as a learning or early-career work experience.",
            "May be paid, for credit, or formally sponsored by an employer or institution.",
        ),
        exclusion_criteria=(
            "Permanent full-time entry-level roles.",
            "Volunteer-only experiences without employer-sponsored work duties.",
            "General talent communities with no defined work experience.",
        ),
        examples=("Summer software internship", "Policy research intern"),
        related_terms=("co_op", "early_career_program", "entry_level_role"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="co-op",
        canonical_name="co_op",
        description=(
            "A structured cooperative education work placement connected to an "
            "academic program or institutional work-integrated learning model."
        ),
        inclusion_criteria=(
            "Linked to a school, academic program, or cooperative education requirement.",
            "Has a defined employer placement or work term.",
            "Includes supervised professional work aligned to the student's field.",
        ),
        exclusion_criteria=(
            "Standalone internships with no academic cooperative structure.",
            "Class projects without employer placement.",
            "Permanent roles unrelated to cooperative education.",
        ),
        examples=("Six-month engineering co-op", "Accounting co-op work term"),
        related_terms=("internship", "early_career_program"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="early-career program",
        canonical_name="early_career_program",
        description=(
            "A named employer, institution, or public-sector program designed to "
            "recruit, train, rotate, or place early-career candidates."
        ),
        inclusion_criteria=(
            "Has a defined program name, cohort, rotation, fellowship, apprenticeship, or track.",
            "Targets interns, students, recent graduates, or early-career workers.",
            "Contains structured training, placement, mentorship, or progression criteria.",
        ),
        exclusion_criteria=(
            "One-off job postings without a program structure.",
            "General career pages or talent networks.",
            "Senior leadership or executive development programs.",
        ),
        examples=("New graduate rotational program", "Apprenticeship cohort"),
        related_terms=("internship", "co_op", "entry_level_role"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="company-region presence",
        canonical_name="company_region_presence",
        description=(
            "Evidence that a company has meaningful operating, office, hiring, "
            "program, or partnership presence in a region."
        ),
        inclusion_criteria=(
            "Verified office, facility, campus, or recurring regional hiring evidence.",
            "Public employer, government, institution, or partner source supports the claim.",
            "Presence can be tied to a specific region identifier or region label.",
        ),
        exclusion_criteria=(
            "Unverified remote-only reach with no regional signal.",
            "Historical presence with no current source or stale evidence.",
            "Speculative expansion rumors without structured source refs.",
        ),
        examples=("Employer office in Greater Boston", "Recurring Atlanta internship hiring"),
        related_terms=("hiring_activity", "market_opportunity_score"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="hiring activity",
        canonical_name="hiring_activity",
        description=(
            "Observed or reported employer demand signal, such as active postings, "
            "program openings, hiring events, or sourced partner hiring counts."
        ),
        inclusion_criteria=(
            "Signal has an observation date or collection period.",
            "Signal identifies employer, role family, region, program, or source basis.",
            "Source refs and freshness metadata are attached.",
        ),
        exclusion_criteria=(
            "Unsupported claims that a company is hiring.",
            "Forecasts presented as observed hiring.",
            "Outdated postings without freshness or expiration context.",
        ),
        examples=("Active posting count now", "Internship postings collected this month"),
        related_terms=("company_region_presence", "market_opportunity_score"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
    StandardDefinition(
        term="market opportunity score",
        canonical_name="market_opportunity_score",
        description=(
            "A governed score summarizing structured regional or market opportunity "
            "signals. It is metadata for interpretation and must not be replaced by "
            "partner-submitted raw scores without downstream review."
        ),
        inclusion_criteria=(
            "Combines documented structured market signals.",
            "Carries version, confidence, and freshness context.",
            "Is traceable to platform scoring rules or reviewed downstream consumers.",
        ),
        exclusion_criteria=(
            "Raw partner ratings without scoring methodology.",
            "Forecast claims presented as current market truth.",
            "Scores that silently incorporate paid or partner influence.",
        ),
        examples=("Objective opportunity score", "Early-career accessibility score"),
        related_terms=("hiring_activity", "company_region_presence"),
        version=STANDARDS_VERSION,
        status=StandardDefinitionStatus.ACTIVE,
    ),
)


_CONFIDENCE_RANK = {
    Confidence.UNKNOWN: 0,
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
}


def _confidence_meets_minimum(
    confidence: PartnerConfidence | None,
    *,
    minimum: Confidence,
) -> bool:
    if confidence is None:
        return minimum == Confidence.UNKNOWN
    return _CONFIDENCE_RANK[confidence.confidence_label] >= _CONFIDENCE_RANK[minimum]


def _has_allowed_source_type(
    source_refs: tuple[PartnerSourceRef, ...],
    allowed_sources: tuple[str, ...],
) -> bool:
    if "*" in allowed_sources:
        return bool(source_refs)
    allowed = set(allowed_sources)
    return any(source.source_type in allowed for source in source_refs)


def _has_audit_marker(request: DataQualityCertificationRequest) -> bool:
    if request.audit_marker is not None:
        return True
    if request.record is None:
        return False
    payload = request.record.payload
    marker = payload.get("audit_marker") or payload.get("review_status")
    return marker in {"audited", "reviewed", "review_safe", "reviewed_public_source"}


def _is_employer_context(
    partner: PartnerRegistryRecord | None,
    request: DataQualityCertificationRequest,
) -> bool:
    if partner is not None and partner.partner_type == PartnerType.EMPLOYER:
        return True
    return request.submitter_type == PartnerSubmitterType.EMPLOYER


def _low_confidence_condition_present(
    request: DataQualityCertificationRequest,
) -> bool:
    if not request.source_refs:
        return True
    if request.confidence is None:
        return True
    if request.confidence.confidence_label in {Confidence.LOW, Confidence.UNKNOWN}:
        return True
    if request.freshness is None:
        return True
    return request.freshness.freshness_status in {
        PartnerFreshnessStatus.STALE,
        PartnerFreshnessStatus.PARTIAL,
        PartnerFreshnessStatus.UNKNOWN,
    }


def _validate_top_level(
    data: dict[str, Any],
    errors: list[PartnerSubmissionValidationError],
) -> None:
    for field in REQUIRED_SUBMISSION_FIELDS:
        if field not in data or data[field] in (None, "", []):
            errors.append(_error("required_field_missing", field, f"{field} is required."))
    if data.get("schema_version") != PARTNER_SCHEMA_VERSION:
        errors.append(
            _error(
                "unsupported_schema_version",
                "schema_version",
                f"schema_version must be {PARTNER_SCHEMA_VERSION}.",
            )
        )
    if data.get("submitter_type") not in PartnerSubmitterType.values():
        errors.append(
            _error(
                "unsupported_submitter_type",
                "submitter_type",
                "submitter_type is not supported.",
            )
        )


def _validate_source_refs(
    source_refs: Any,
    errors: list[PartnerSubmissionValidationError],
) -> set[str]:
    if not isinstance(source_refs, list) or not source_refs:
        errors.append(
            _error("source_refs_required", "source_refs", "source_refs are required.")
        )
        return set()
    ids: set[str] = set()
    for index, ref in enumerate(source_refs):
        field = f"source_refs[{index}]"
        if not isinstance(ref, dict):
            errors.append(
                _error("invalid_source_ref", field, "source ref must be an object.")
            )
            continue
        ref_id = ref.get("source_ref_id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            errors.append(
                _error(
                    "required_field_missing",
                    f"{field}.source_ref_id",
                    "source_ref_id is required.",
                )
            )
        else:
            ids.add(ref_id)
        if not ref.get("source_type"):
            errors.append(
                _error(
                    "required_field_missing",
                    f"{field}.source_type",
                    "source_type is required.",
                )
            )
        if not ref.get("url") and not ref.get("citation"):
            errors.append(
                _error(
                    "source_ref_basis_required",
                    field,
                    "source ref requires url or citation.",
                )
            )
        try:
            PartnerSourceRef.model_validate(ref)
        except ValidationError as exc:
            errors.extend(_errors_from_pydantic(exc, prefix=field))
    return ids


def _validate_records(
    records: Any,
    source_ref_ids: set[str],
    errors: list[PartnerSubmissionValidationError],
) -> None:
    if not isinstance(records, list) or not records:
        errors.append(_error("records_required", "records", "records are required."))
        return
    for index, record in enumerate(records):
        field = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(
                _error("invalid_record", field, "record must be an object.")
            )
            continue
        record_id = _string_or_none(record.get("record_id"))
        record_type = record.get("record_type")
        if record_type not in PartnerRecordType.values():
            errors.append(
                _error(
                    "unsupported_record_type",
                    f"{field}.record_type",
                    "record_type is not supported.",
                    record_id=record_id,
                )
            )
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            errors.append(
                _error(
                    "required_field_missing",
                    f"{field}.payload",
                    "payload object is required.",
                    record_id=record_id,
                )
            )
            payload = {}
        for required in REQUIRED_FIELDS_BY_RECORD_TYPE[str(record_type)]:
            if payload.get(required) in (None, "", []):
                errors.append(
                    _error(
                        "required_record_field_missing",
                        f"{field}.payload.{required}",
                        f"{required} is required for {record_type}.",
                        record_id=record_id,
                    )
                )
        refs = record.get("source_ref_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(
                _error(
                    "record_source_refs_required",
                    f"{field}.source_ref_ids",
                    "record source_ref_ids are required.",
                    record_id=record_id,
                )
            )
        else:
            for ref_id in refs:
                if ref_id not in source_ref_ids:
                    errors.append(
                        _error(
                            "unknown_source_ref",
                            f"{field}.source_ref_ids",
                            f"source ref {ref_id!r} is not attached.",
                            record_id=record_id,
                        )
                    )
        try:
            PartnerSubmissionRecord.model_validate(record)
        except ValidationError as exc:
            errors.extend(_errors_from_pydantic(exc, prefix=field, record_id=record_id))


def _validate_partner_permissions(
    partner_id: Any,
    records: Any,
    errors: list[PartnerSubmissionValidationError],
) -> None:
    if not isinstance(partner_id, str) or not partner_id.strip():
        return
    partner = PARTNER_REGISTRY_BY_ID.get(partner_id)
    if partner is None:
        errors.append(
            _error(
                "partner_not_registered",
                "partner_id",
                "partner must be registered before candidate creation.",
            )
        )
        return
    if not isinstance(records, list):
        return
    allowed = {record_type.value for record_type in partner.allowed_submission_types}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_type = record.get("record_type")
        record_id = _string_or_none(record.get("record_id"))
        if record_type in PartnerRecordType.values() and record_type not in allowed:
            errors.append(
                _error(
                    "partner_submission_type_not_permitted",
                    f"records[{index}].record_type",
                    "partner submission permissions do not allow this record type.",
                    record_id=record_id,
                )
            )


def _validate_freshness(
    freshness: Any,
    errors: list[PartnerSubmissionValidationError],
) -> None:
    if not isinstance(freshness, dict):
        errors.append(
            _error(
                "freshness_required",
                "freshness",
                "freshness declaration is required.",
            )
        )
        return
    if not freshness.get("freshness_status"):
        errors.append(
            _error(
                "required_field_missing",
                "freshness.freshness_status",
                "freshness_status is required.",
            )
        )
    try:
        PartnerFreshness.model_validate(freshness)
    except ValidationError as exc:
        errors.extend(_errors_from_pydantic(exc, prefix="freshness"))


def _validate_confidence(
    confidence: Any,
    errors: list[PartnerSubmissionValidationError],
) -> None:
    if not isinstance(confidence, dict):
        errors.append(
            _error(
                "confidence_required",
                "confidence",
                "confidence declaration is required.",
            )
        )
        return
    if not confidence.get("confidence_label"):
        errors.append(
            _error(
                "required_field_missing",
                "confidence.confidence_label",
                "confidence_label is required.",
            )
        )
    try:
        PartnerConfidence.model_validate(confidence)
    except ValidationError as exc:
        errors.extend(_errors_from_pydantic(exc, prefix="confidence"))


def _coerce_warnings(value: Any) -> tuple[PartnerSubmissionWarning, ...]:
    if value in (None, ""):
        return ()
    raw_items = value if isinstance(value, list) else [value]
    warnings: list[PartnerSubmissionWarning] = []
    for index, item in enumerate(raw_items):
        if isinstance(item, str):
            item = {"code": f"partner_warning_{index + 1}", "message": item}
        if isinstance(item, dict):
            try:
                warnings.append(PartnerSubmissionWarning.model_validate(item))
            except ValidationError:
                warnings.append(
                    PartnerSubmissionWarning(
                        code=f"invalid_partner_warning_{index + 1}",
                        message="Partner warning could not be parsed.",
                    )
                )
    return tuple(warnings)


def _errors_from_pydantic(
    exc: ValidationError,
    *,
    prefix: str | None = None,
    record_id: str | None = None,
) -> tuple[PartnerSubmissionValidationError, ...]:
    errors: list[PartnerSubmissionValidationError] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        if prefix:
            location = f"{prefix}.{location}" if location else prefix
        errors.append(
            _error(
                "schema_validation_error",
                location or "submission",
                str(item.get("msg", "schema validation failed")),
                record_id=record_id,
            )
        )
    return tuple(errors)


def _error(
    code: str,
    field: str,
    message: str,
    *,
    record_id: str | None = None,
) -> PartnerSubmissionValidationError:
    return PartnerSubmissionValidationError(
        code=code,
        field=field,
        message=message,
        record_id=record_id,
    )


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None
