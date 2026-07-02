"""Permission helpers for governed Layer 18D contributions."""

from __future__ import annotations

from backend.institutions.permissions import has_required_institutional_role
from backend.institutions.repository import InstitutionRepository
from backend.institutions.roles import ADVISOR_TOOL_ROLES
from backend.platform_intelligence.schemas import ContributionType

BASIC_USER_CONTRIBUTION_TYPES: frozenset[ContributionType] = frozenset(
    {
        ContributionType.VERIFIED_CORRECTION,
        ContributionType.COMPANY_PRESENCE_UPDATE,
        ContributionType.ROLE_ACCESS_FEEDBACK,
        ContributionType.SOURCE_SUGGESTION,
        ContributionType.MARKET_QUALITY_FEEDBACK,
        ContributionType.OUTDATED_DATA_REPORT,
    }
)

INSTITUTION_CONTRIBUTION_TYPES: frozenset[ContributionType] = frozenset(
    {
        ContributionType.VERIFIED_CORRECTION,
        ContributionType.COMPANY_PRESENCE_UPDATE,
        ContributionType.REGIONAL_EMPLOYER_LIST,
        ContributionType.CAREER_CENTER_INTELLIGENCE,
        ContributionType.INTERNSHIP_PROGRAM_INFORMATION,
    }
)


def can_submit_contribution(
    institution_repo: InstitutionRepository,
    *,
    user_id: str,
    contribution_type: ContributionType,
    institution_id: str | None,
) -> bool:
    if institution_id is None:
        return contribution_type in BASIC_USER_CONTRIBUTION_TYPES

    if contribution_type not in INSTITUTION_CONTRIBUTION_TYPES:
        return False
    return has_required_institutional_role(
        institution_repo,
        user_id=user_id,
        organization_id=institution_id,
        required_roles=ADVISOR_TOOL_ROLES,
    )
