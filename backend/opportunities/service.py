"""Service layer for Layer 23A opportunity records."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.opportunities.governance import assert_ranking_influence_disabled
from backend.opportunities.models import (
    EmployerInfluenceMetadata,
    EmployerProgram,
    Opportunity,
    OpportunityRegionBinding,
    OpportunityReviewActionRecord,
    OpportunityRoleFamilyBinding,
    OpportunitySource,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataPayload,
    EmployerProgramPayload,
    OpportunityCreate,
    OpportunityExpirationState,
    OpportunityListResponse,
    OpportunityPayload,
    OpportunityRegionBindingPayload,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingPayload,
    OpportunitySourceCreate,
    OpportunitySourcePayload,
    OpportunityTrustLabel,
)
from backend.opportunities.verification import (
    is_active_opportunity,
    is_opportunity_expired,
    opportunity_expiration_state,
)


class OpportunityNotFound(Exception):
    pass


class OpportunityValidationError(ValueError):
    pass


class OpportunityService:
    def __init__(self, repository: OpportunityRepository) -> None:
        self._repo = repository

    def create_opportunity(self, request: OpportunityCreate) -> OpportunityPayload:
        """Create an internal opportunity fixture/record.

        Public opportunity submission uses the protected Layer 23B submission
        workflow. This method remains the internal canonical opportunity writer
        used by governed ingestion, review, and tests.
        """

        assert_ranking_influence_disabled(request.employer_influence)
        created_at = request.created_at or datetime.now(UTC)
        program = self._ensure_program(request, created_at=created_at)
        self._repo.flush()
        opportunity_id = request.opportunity_id or _new_id("opportunity")
        opportunity = Opportunity(
            opportunity_id=opportunity_id,
            employer_program_id=program.employer_program_id,
            employer_id=request.employer_id,
            employer_name=request.employer_name,
            program_name=request.program_name,
            program_type=request.program_type.value,
            location_mode=request.location_mode.value,
            seniority_level=request.seniority_level.value,
            eligibility_summary=request.eligibility_summary,
            application_url=request.application_url,
            source_url=request.source_url,
            source_type=request.source_type.value,
            application_open_date=request.application_open_date,
            application_deadline=request.application_deadline,
            expires_at=request.expires_at,
            compensation_min=request.compensation_min,
            compensation_max=request.compensation_max,
            compensation_disclosed=request.compensation_disclosed,
            trust_label=request.trust_label.value,
            review_status=request.review_status.value,
            created_at=created_at,
            updated_at=created_at,
        )
        self._repo.add_opportunity(opportunity)
        self._repo.flush()
        self._repo.add_employer_influence_metadata(
            EmployerInfluenceMetadata(
                employer_influence_metadata_id=(
                    request.employer_influence.employer_influence_metadata_id
                    or _new_id("employer_influence")
                ),
                opportunity_id=opportunity_id,
                partner_submitted=request.employer_influence.partner_submitted,
                paid_partner=request.employer_influence.paid_partner,
                ranking_influence_allowed=False,
                submitted_by_partner_id=request.employer_influence.submitted_by_partner_id,
                paid_partner_label=request.employer_influence.paid_partner_label,
                internal_review_notes=request.employer_influence.internal_review_notes,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        for source in _source_records(request):
            self._repo.add_source(
                OpportunitySource(
                    opportunity_source_id=(
                        source.opportunity_source_id or _new_id("opportunity_source")
                    ),
                    opportunity_id=opportunity_id,
                    source_type=source.source_type.value,
                    source_url=source.source_url,
                    source_name=source.source_name,
                    collected_at=source.collected_at,
                    verification_note=source.verification_note,
                    created_at=source.collected_at or created_at,
                )
            )
        for binding in request.region_bindings:
            self._repo.add_region_binding(
                OpportunityRegionBinding(
                    opportunity_region_binding_id=(
                        binding.opportunity_region_binding_id
                        or _new_id("opportunity_region")
                    ),
                    opportunity_id=opportunity_id,
                    region_id=binding.region_id,
                    region_label=binding.region_label,
                    metro_area=binding.metro_area,
                    binding_confidence=binding.binding_confidence.value,
                    created_at=created_at,
                )
            )
        for binding in request.role_family_bindings:
            self._repo.add_role_family_binding(
                OpportunityRoleFamilyBinding(
                    opportunity_role_family_binding_id=(
                        binding.opportunity_role_family_binding_id
                        or _new_id("opportunity_role_family")
                    ),
                    opportunity_id=opportunity_id,
                    role_family=binding.role_family,
                    role_family_label=binding.role_family_label,
                    binding_confidence=binding.binding_confidence.value,
                    created_at=created_at,
                )
            )
        self._repo.flush()
        return self._payload(opportunity, now=created_at)

    def get_opportunity(
        self,
        opportunity_id: str,
        *,
        now: datetime | None = None,
    ) -> OpportunityPayload:
        opportunity = self._repo.get_opportunity(opportunity_id)
        if opportunity is None:
            raise OpportunityNotFound(opportunity_id)
        return self._payload(opportunity, now=now)

    def list_opportunities(
        self,
        *,
        trust_label: OpportunityTrustLabel | None = None,
        region: str | None = None,
        role_family: str | None = None,
        program_type: str | None = None,
        active: bool | None = None,
        expired: bool | None = None,
        now: datetime | None = None,
        limit: int = 100,
    ) -> OpportunityListResponse:
        if active is not None and expired is not None:
            raise OpportunityValidationError("filter by active or expired, not both")
        rows = self._repo.list_opportunities(
            region=region,
            role_family=role_family,
            program_type=program_type,
        )
        filtered = []
        for row in rows:
            latest_review = self._repo.latest_review_action_for_opportunity(
                row.opportunity_id
            )
            effective_trust_label, effective_review_status = _effective_review_state(
                row,
                latest_review,
            )
            if (
                trust_label is not None
                and effective_trust_label != trust_label.value
            ):
                continue
            is_active = _is_effectively_active(
                row,
                trust_label=effective_trust_label,
                review_status=effective_review_status,
                now=now,
            )
            if active is not None and is_active is not active:
                continue
            is_expired = _is_effectively_expired(
                row,
                trust_label=effective_trust_label,
                review_status=effective_review_status,
                now=now,
            )
            if expired is not None and is_expired is not expired:
                continue
            filtered.append(row)
            if len(filtered) >= limit:
                break
        return OpportunityListResponse(
            opportunities=tuple(self._payload(row, now=now) for row in filtered)
        )

    def list_active_verified_opportunities(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> OpportunityListResponse:
        rows = [
            row
            for row in self._repo.list_opportunities()
            if _is_effectively_active_verified(
                row,
                self._repo.latest_review_action_for_opportunity(row.opportunity_id),
                now=now,
            )
        ][:limit]
        return OpportunityListResponse(
            opportunities=tuple(self._payload(row, now=now) for row in rows)
        )

    def _ensure_program(
        self,
        request: OpportunityCreate,
        *,
        created_at: datetime,
    ) -> EmployerProgram:
        if request.employer_program_id is not None:
            existing = self._repo.get_employer_program(request.employer_program_id)
            if existing is not None:
                return existing
        program = EmployerProgram(
            employer_program_id=request.employer_program_id or _new_id("employer_program"),
            employer_id=request.employer_id,
            employer_name=request.employer_name,
            program_name=request.program_name,
            program_type=request.program_type.value,
            program_url=None,
            created_at=created_at,
            updated_at=created_at,
        )
        self._repo.add_employer_program(program)
        return program

    def _payload(
        self,
        opportunity: Opportunity,
        *,
        now: datetime | None = None,
    ) -> OpportunityPayload:
        program = self._repo.get_employer_program(opportunity.employer_program_id)
        sources = self._repo.list_sources(opportunity.opportunity_id)
        regions = self._repo.list_region_bindings(opportunity.opportunity_id)
        role_families = self._repo.list_role_family_bindings(opportunity.opportunity_id)
        influence = self._repo.get_employer_influence_metadata(opportunity.opportunity_id)
        latest_review = self._repo.latest_review_action_for_opportunity(
            opportunity.opportunity_id
        )
        effective_trust_label, effective_review_status = _effective_review_state(
            opportunity,
            latest_review,
        )
        partner_submitted = influence.partner_submitted if influence is not None else False
        paid_partner = influence.paid_partner if influence is not None else False
        ranking_influence_allowed = (
            influence.ranking_influence_allowed if influence is not None else False
        )
        return OpportunityPayload(
            id=opportunity.opportunity_id,
            employer_program=_program_payload(program) if program is not None else None,
            employer_id=opportunity.employer_id,
            employer_name=opportunity.employer_name,
            program_name=opportunity.program_name,
            program_type=opportunity.program_type,
            role_families=tuple(binding.role_family for binding in role_families),
            regions=tuple(binding.region_id or binding.region_label for binding in regions),
            location_mode=opportunity.location_mode,
            seniority_level=opportunity.seniority_level,
            eligibility_summary=opportunity.eligibility_summary,
            application_url=opportunity.application_url,
            source_url=opportunity.source_url,
            source_type=opportunity.source_type,
            application_open_date=opportunity.application_open_date,
            application_deadline=opportunity.application_deadline,
            expires_at=opportunity.expires_at,
            expiration_state=_effective_expiration_state(
                opportunity,
                trust_label=effective_trust_label,
                review_status=effective_review_status,
                now=now,
            ),
            compensation_min=opportunity.compensation_min,
            compensation_max=opportunity.compensation_max,
            compensation_disclosed=opportunity.compensation_disclosed,
            trust_label=effective_trust_label,
            review_status=effective_review_status,
            partner_submitted=partner_submitted,
            paid_partner=paid_partner,
            ranking_influence_allowed=ranking_influence_allowed,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
            sources=tuple(_source_payload(source) for source in sources),
            region_bindings=tuple(_region_binding_payload(binding) for binding in regions),
            role_family_bindings=tuple(
                _role_family_binding_payload(binding) for binding in role_families
            ),
            employer_influence=(
                _employer_influence_payload(influence) if influence is not None else None
            ),
        )


def _source_records(request: OpportunityCreate) -> tuple[OpportunitySourceCreate, ...]:
    primary = OpportunitySourceCreate(
        source_type=request.source_type,
        source_url=request.source_url,
        collected_at=request.created_at,
    )
    if not request.sources:
        return (primary,)
    if any(
        source.source_type == request.source_type and source.source_url == request.source_url
        for source in request.sources
    ):
        return request.sources
    return (primary, *request.sources)


def _program_payload(row: EmployerProgram) -> EmployerProgramPayload:
    return EmployerProgramPayload(
        employer_program_id=row.employer_program_id,
        employer_id=row.employer_id,
        employer_name=row.employer_name,
        program_name=row.program_name,
        program_type=row.program_type,
        program_url=row.program_url,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _source_payload(row: OpportunitySource) -> OpportunitySourcePayload:
    return OpportunitySourcePayload(
        opportunity_source_id=row.opportunity_source_id,
        source_type=row.source_type,
        source_url=row.source_url,
        source_name=row.source_name,
        collected_at=row.collected_at,
        verification_note=row.verification_note,
        created_at=row.created_at,
    )


def _region_binding_payload(
    row: OpportunityRegionBinding,
) -> OpportunityRegionBindingPayload:
    return OpportunityRegionBindingPayload(
        opportunity_region_binding_id=row.opportunity_region_binding_id,
        region_id=row.region_id,
        region_label=row.region_label,
        metro_area=row.metro_area,
        binding_confidence=row.binding_confidence,
        created_at=row.created_at,
    )


def _role_family_binding_payload(
    row: OpportunityRoleFamilyBinding,
) -> OpportunityRoleFamilyBindingPayload:
    return OpportunityRoleFamilyBindingPayload(
        opportunity_role_family_binding_id=row.opportunity_role_family_binding_id,
        role_family=row.role_family,
        role_family_label=row.role_family_label,
        binding_confidence=row.binding_confidence,
        created_at=row.created_at,
    )


def _employer_influence_payload(
    row: EmployerInfluenceMetadata,
) -> EmployerInfluenceMetadataPayload:
    return EmployerInfluenceMetadataPayload(
        employer_influence_metadata_id=row.employer_influence_metadata_id,
        partner_submitted=row.partner_submitted,
        paid_partner=row.paid_partner,
        ranking_influence_allowed=row.ranking_influence_allowed,
        submitted_by_partner_id=row.submitted_by_partner_id,
        paid_partner_label=row.paid_partner_label,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _effective_review_state(
    opportunity: Opportunity,
    latest_review: OpportunityReviewActionRecord | None,
) -> tuple[str, str]:
    if latest_review is None:
        return opportunity.trust_label, opportunity.review_status
    return latest_review.resulting_trust_label, latest_review.resulting_review_status


def _effective_expiration_state(
    opportunity: Opportunity,
    *,
    trust_label: str,
    review_status: str,
    now: datetime | None = None,
) -> OpportunityExpirationState:
    if _is_effectively_expired(
        opportunity,
        trust_label=trust_label,
        review_status=review_status,
        now=now,
    ):
        return OpportunityExpirationState.EXPIRED
    return opportunity_expiration_state(opportunity, now=now)


def _is_effectively_expired(
    opportunity: Opportunity,
    *,
    trust_label: str,
    review_status: str,
    now: datetime | None = None,
) -> bool:
    return (
        trust_label == OpportunityTrustLabel.EXPIRED.value
        or review_status == OpportunityReviewStatus.EXPIRED.value
        or is_opportunity_expired(opportunity, now=now)
    )


def _is_effectively_active(
    opportunity: Opportunity,
    *,
    trust_label: str,
    review_status: str,
    now: datetime | None = None,
) -> bool:
    if _is_effectively_expired(
        opportunity,
        trust_label=trust_label,
        review_status=review_status,
        now=now,
    ):
        return False
    if trust_label in {
        OpportunityTrustLabel.EXPIRED.value,
        OpportunityTrustLabel.REJECTED.value,
    }:
        return False
    if review_status in {
        OpportunityReviewStatus.EXPIRED.value,
        OpportunityReviewStatus.REJECTED.value,
    }:
        return False
    return is_active_opportunity(opportunity, now=now)


def _is_effectively_active_verified(
    opportunity: Opportunity,
    latest_review: OpportunityReviewActionRecord | None,
    *,
    now: datetime | None = None,
) -> bool:
    trust_label, review_status = _effective_review_state(opportunity, latest_review)
    return (
        _is_effectively_active(
            opportunity,
            trust_label=trust_label,
            review_status=review_status,
            now=now,
        )
        and trust_label
        in {
            OpportunityTrustLabel.VERIFIED.value,
            OpportunityTrustLabel.SOURCE_CHECKED.value,
        }
        and review_status
        in {
            OpportunityReviewStatus.APPROVED.value,
            OpportunityReviewStatus.SOURCE_CHECKED.value,
        }
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
