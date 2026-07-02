"""Repository helpers for Layer 23A opportunity records."""

from __future__ import annotations

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from backend.opportunities.models import (
    EmployerInfluenceMetadata,
    EmployerProgram,
    Opportunity,
    OpportunityRegionBinding,
    OpportunityReviewActionRecord,
    OpportunityRoleFamilyBinding,
    OpportunitySource,
    OpportunitySubmission,
)


class OpportunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add_employer_program(self, row: EmployerProgram) -> None:
        self._session.add(row)

    def get_employer_program(self, employer_program_id: str) -> EmployerProgram | None:
        return self._session.get(EmployerProgram, employer_program_id)

    def add_opportunity(self, row: Opportunity) -> None:
        self._session.add(row)

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        return self._session.get(Opportunity, opportunity_id)

    def list_opportunities(
        self,
        *,
        trust_label: str | None = None,
        region: str | None = None,
        role_family: str | None = None,
        program_type: str | None = None,
    ) -> list[Opportunity]:
        stmt = select(Opportunity)
        if trust_label is not None:
            stmt = stmt.where(Opportunity.trust_label == trust_label)
        if program_type is not None:
            stmt = stmt.where(Opportunity.program_type == program_type)
        if region is not None:
            stmt = stmt.where(
                exists()
                .where(OpportunityRegionBinding.opportunity_id == Opportunity.opportunity_id)
                .where(
                    or_(
                        OpportunityRegionBinding.region_id == region,
                        OpportunityRegionBinding.region_label == region,
                        OpportunityRegionBinding.metro_area == region,
                    )
                )
            )
        if role_family is not None:
            stmt = stmt.where(
                exists()
                .where(
                    OpportunityRoleFamilyBinding.opportunity_id
                    == Opportunity.opportunity_id
                )
                .where(OpportunityRoleFamilyBinding.role_family == role_family)
            )
        rows = self._session.execute(
            stmt.order_by(
                Opportunity.created_at.desc(),
                Opportunity.opportunity_id.desc(),
            )
        ).scalars()
        return list(rows)

    def add_source(self, row: OpportunitySource) -> None:
        self._session.add(row)

    def list_sources(self, opportunity_id: str) -> list[OpportunitySource]:
        rows = self._session.execute(
            select(OpportunitySource)
            .where(OpportunitySource.opportunity_id == opportunity_id)
            .order_by(
                OpportunitySource.created_at.asc(),
                OpportunitySource.opportunity_source_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_region_binding(self, row: OpportunityRegionBinding) -> None:
        self._session.add(row)

    def list_region_bindings(self, opportunity_id: str) -> list[OpportunityRegionBinding]:
        rows = self._session.execute(
            select(OpportunityRegionBinding)
            .where(OpportunityRegionBinding.opportunity_id == opportunity_id)
            .order_by(
                OpportunityRegionBinding.region_label.asc(),
                OpportunityRegionBinding.opportunity_region_binding_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_role_family_binding(self, row: OpportunityRoleFamilyBinding) -> None:
        self._session.add(row)

    def list_role_family_bindings(
        self,
        opportunity_id: str,
    ) -> list[OpportunityRoleFamilyBinding]:
        rows = self._session.execute(
            select(OpportunityRoleFamilyBinding)
            .where(OpportunityRoleFamilyBinding.opportunity_id == opportunity_id)
            .order_by(
                OpportunityRoleFamilyBinding.role_family.asc(),
                OpportunityRoleFamilyBinding.opportunity_role_family_binding_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_employer_influence_metadata(
        self,
        row: EmployerInfluenceMetadata,
    ) -> None:
        self._session.add(row)

    def get_employer_influence_metadata(
        self,
        opportunity_id: str,
    ) -> EmployerInfluenceMetadata | None:
        return self._session.execute(
            select(EmployerInfluenceMetadata).where(
                EmployerInfluenceMetadata.opportunity_id == opportunity_id
            )
        ).scalar_one_or_none()

    def add_submission(self, row: OpportunitySubmission) -> None:
        self._session.add(row)

    def get_submission(self, submission_id: str) -> OpportunitySubmission | None:
        return self._session.get(OpportunitySubmission, submission_id)

    def get_submission_for_opportunity(
        self,
        opportunity_id: str,
    ) -> OpportunitySubmission | None:
        return self._session.execute(
            select(OpportunitySubmission).where(
                OpportunitySubmission.opportunity_id == opportunity_id
            )
        ).scalar_one_or_none()

    def list_submissions(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[OpportunitySubmission]:
        stmt = select(OpportunitySubmission)
        if status is not None:
            stmt = stmt.where(OpportunitySubmission.status == status)
        rows = self._session.execute(
            stmt.order_by(
                OpportunitySubmission.submitted_at.desc(),
                OpportunitySubmission.opportunity_submission_id.desc(),
            ).limit(limit)
        ).scalars()
        return list(rows)

    def add_review_action(self, row: OpportunityReviewActionRecord) -> None:
        self._session.add(row)

    def latest_review_action_for_submission(
        self,
        submission_id: str,
    ) -> OpportunityReviewActionRecord | None:
        return self._session.execute(
            select(OpportunityReviewActionRecord)
            .where(OpportunityReviewActionRecord.submission_id == submission_id)
            .order_by(
                OpportunityReviewActionRecord.reviewed_at.desc(),
                OpportunityReviewActionRecord.opportunity_review_action_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def latest_review_action_for_opportunity(
        self,
        opportunity_id: str,
    ) -> OpportunityReviewActionRecord | None:
        return self._session.execute(
            select(OpportunityReviewActionRecord)
            .where(OpportunityReviewActionRecord.opportunity_id == opportunity_id)
            .order_by(
                OpportunityReviewActionRecord.reviewed_at.desc(),
                OpportunityReviewActionRecord.opportunity_review_action_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_review_actions(
        self,
        submission_id: str,
    ) -> list[OpportunityReviewActionRecord]:
        rows = self._session.execute(
            select(OpportunityReviewActionRecord)
            .where(OpportunityReviewActionRecord.submission_id == submission_id)
            .order_by(
                OpportunityReviewActionRecord.reviewed_at.asc(),
                OpportunityReviewActionRecord.opportunity_review_action_id.asc(),
            )
        ).scalars()
        return list(rows)

    def flush(self) -> None:
        self._session.flush()
