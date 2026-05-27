"""Privacy-aware institutional cohort dashboard aggregation."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.search import region_coverage_lookup
from backend.companies.models import Company
from backend.geography.market_coverage import CoverageMetadataPayload
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.roles import OrganizationMembershipStatus, OrganizationRole
from backend.users.models import SavedMarketArtifact, UserPreferenceProfile

DEFAULT_MINIMUM_GROUP_SIZE = 5
MAXIMUM_GROUP_SIZE = 50
LOW_SAMPLE_REASON = "minimum_group_size_not_met"
LOW_SAMPLE_LABEL = "Other / insufficient sample size"


class InstitutionalAggregateItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    count: int | None = None
    percentage: float | None = None
    category: str | None = None
    suppressed: bool = False
    suppression_reason: str | None = None
    source_count: int | None = None
    coverage: dict[str, Any] | None = None
    confidence: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InstitutionalSuppressedCategory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section: str
    suppressed_count: int = Field(ge=1)
    suppression_reason: str
    minimum_group_size: int = Field(ge=1)


class InstitutionalDashboardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    organization_name: str
    generated_at: datetime
    minimum_group_size: int
    cohort_size: int
    visible_student_count: int
    popular_target_markets: list[InstitutionalAggregateItem] = Field(default_factory=list)
    role_interest_summary: list[InstitutionalAggregateItem] = Field(default_factory=list)
    saved_company_summary: list[InstitutionalAggregateItem] = Field(default_factory=list)
    market_demand_trends: list[InstitutionalAggregateItem] = Field(default_factory=list)
    coverage_gaps: list[InstitutionalAggregateItem] = Field(default_factory=list)
    suppressed_categories: list[InstitutionalSuppressedCategory] = Field(
        default_factory=list
    )
    privacy_notes: list[str] = Field(default_factory=list)
    coverage_warnings: list[str] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)


def build_institutional_dashboard(
    session: Session,
    *,
    organization: Organization,
    student_memberships: list[OrganizationMembership],
    minimum_group_size: int = DEFAULT_MINIMUM_GROUP_SIZE,
) -> InstitutionalDashboardPayload:
    minimum_group_size = max(
        DEFAULT_MINIMUM_GROUP_SIZE,
        min(MAXIMUM_GROUP_SIZE, int(minimum_group_size)),
    )
    student_ids = _active_student_ids(student_memberships)
    cohort_size = len(student_ids)
    generated_at = datetime.now(UTC)

    profiles = _preference_profiles(session, student_ids)
    saved_artifacts = _saved_artifacts(session, student_ids)
    region_labels = _region_labels(session)
    company_labels = _company_labels(session)

    suppressed_categories: list[InstitutionalSuppressedCategory] = []

    target_market_contributors, target_market_labels = _target_market_contributors(
        profiles,
        saved_artifacts,
        region_labels=region_labels,
    )
    popular_target_markets, target_suppressed = _aggregate_items(
        section="popular_target_markets",
        contributors=target_market_contributors,
        labels=target_market_labels,
        cohort_size=cohort_size,
        minimum_group_size=minimum_group_size,
        category="target_market",
        metadata_for_key=lambda key, _users: {"region_id": key},
    )
    suppressed_categories.extend(target_suppressed)

    role_contributors, role_labels = _role_interest_contributors(profiles)
    role_interest_summary, role_suppressed = _aggregate_items(
        section="role_interest_summary",
        contributors=role_contributors,
        labels=role_labels,
        cohort_size=cohort_size,
        minimum_group_size=minimum_group_size,
        category="role_interest",
    )
    suppressed_categories.extend(role_suppressed)

    company_contributors, saved_company_labels = _saved_company_contributors(
        saved_artifacts,
        company_labels=company_labels,
    )
    saved_company_summary, company_suppressed = _aggregate_items(
        section="saved_company_summary",
        contributors=company_contributors,
        labels=saved_company_labels,
        cohort_size=cohort_size,
        minimum_group_size=minimum_group_size,
        category="saved_company",
        metadata_for_key=lambda key, _users: {"company_id": key},
    )
    suppressed_categories.extend(company_suppressed)

    visible_region_counts = _visible_region_counts(popular_target_markets)
    market_demand_trends = _market_demand_trends(
        session,
        visible_region_counts=visible_region_counts,
        region_labels=region_labels,
    )
    coverage_gaps, coverage_warnings = _coverage_gaps(
        session,
        visible_region_counts=visible_region_counts,
        region_labels=region_labels,
    )
    coverage_warnings.extend(
        _dashboard_coverage_warnings(
            cohort_size=cohort_size,
            minimum_group_size=minimum_group_size,
            visible_region_counts=visible_region_counts,
            suppressed_categories=suppressed_categories,
        )
    )

    return InstitutionalDashboardPayload(
        organization_id=organization.organization_id,
        organization_name=organization.name,
        generated_at=generated_at,
        minimum_group_size=minimum_group_size,
        cohort_size=cohort_size,
        visible_student_count=cohort_size,
        popular_target_markets=popular_target_markets,
        role_interest_summary=role_interest_summary,
        saved_company_summary=saved_company_summary,
        market_demand_trends=market_demand_trends,
        coverage_gaps=coverage_gaps,
        suppressed_categories=suppressed_categories,
        privacy_notes=[
            "Layer 16 cohort dashboards are aggregate-first and do not expose "
            "student-level searches, saved items, recommendations, or activity rows.",
            "Low-sample categories are suppressed according to the configured "
            "minimum group threshold.",
        ],
        coverage_warnings=coverage_warnings,
        data_freshness={
            "generated_at": generated_at.isoformat(),
            "source": (
                "active organization student memberships, user-owned preference "
                "profiles, saved market artifacts, and canonical market coverage"
            ),
            "freshness_status": "unknown",
        },
    )


def _active_student_ids(memberships: list[OrganizationMembership]) -> list[str]:
    return sorted(
        {
            membership.user_id
            for membership in memberships
            if membership.role == OrganizationRole.STUDENT.value
            and membership.status == OrganizationMembershipStatus.ACTIVE.value
        }
    )


def _preference_profiles(
    session: Session,
    student_ids: list[str],
) -> list[UserPreferenceProfile]:
    if not student_ids:
        return []
    return list(
        session.execute(
            select(UserPreferenceProfile)
            .where(UserPreferenceProfile.user_id.in_(student_ids))
            .order_by(UserPreferenceProfile.user_id)
        ).scalars()
    )


def _saved_artifacts(
    session: Session,
    student_ids: list[str],
) -> list[SavedMarketArtifact]:
    if not student_ids:
        return []
    return list(
        session.execute(
            select(SavedMarketArtifact)
            .where(SavedMarketArtifact.user_id.in_(student_ids))
            .order_by(
                SavedMarketArtifact.user_id,
                SavedMarketArtifact.artifact_type,
                SavedMarketArtifact.artifact_ref,
            )
        ).scalars()
    )


def _region_labels(session: Session) -> dict[str, str]:
    return {
        row.region_id: row.display_name
        for row in session.execute(select(Region).order_by(Region.region_id)).scalars()
    }


def _company_labels(session: Session) -> dict[str, str]:
    return {
        row.company_id: row.company_name
        for row in session.execute(select(Company).order_by(Company.company_id)).scalars()
    }


def _target_market_contributors(
    profiles: list[UserPreferenceProfile],
    artifacts: list[SavedMarketArtifact],
    *,
    region_labels: dict[str, str],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    contributors: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}

    for profile in profiles:
        for region_id in _json_string_values(profile.preferred_regions):
            contributors[region_id].add(profile.user_id)
            labels.setdefault(region_id, region_labels.get(region_id) or _display_label(region_id))

    for artifact in artifacts:
        if artifact.artifact_type != "region":
            continue
        region_id = _clean_string(artifact.artifact_ref)
        if region_id is None:
            continue
        contributors[region_id].add(artifact.user_id)
        labels.setdefault(
            region_id,
            region_labels.get(region_id) or artifact.label or _display_label(region_id),
        )

    return dict(contributors), labels


def _role_interest_contributors(
    profiles: list[UserPreferenceProfile],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    contributors: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for profile in profiles:
        for role in _json_string_values(profile.role_interests):
            contributors[role].add(profile.user_id)
            labels.setdefault(role, _display_label(role))
    return dict(contributors), labels


def _saved_company_contributors(
    artifacts: list[SavedMarketArtifact],
    *,
    company_labels: dict[str, str],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    contributors: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for artifact in artifacts:
        if artifact.artifact_type != "company":
            continue
        company_id = _clean_string(artifact.artifact_ref)
        if company_id is None:
            continue
        contributors[company_id].add(artifact.user_id)
        labels.setdefault(
            company_id,
            company_labels.get(company_id) or artifact.label or _display_label(company_id),
        )
    return dict(contributors), labels


def _aggregate_items(
    *,
    section: str,
    contributors: dict[str, set[str]],
    labels: dict[str, str],
    cohort_size: int,
    minimum_group_size: int,
    category: str,
    metadata_for_key: Callable[[str, set[str]], dict[str, Any]] | None = None,
) -> tuple[list[InstitutionalAggregateItem], list[InstitutionalSuppressedCategory]]:
    visible: list[InstitutionalAggregateItem] = []
    suppressed_count = 0
    ranked = sorted(
        contributors.items(),
        key=lambda item: (-len(item[1]), labels.get(item[0], item[0])),
    )
    for key, user_ids in ranked:
        contributor_count = len(user_ids)
        if contributor_count < minimum_group_size:
            suppressed_count += 1
            continue
        metadata = metadata_for_key(key, user_ids) if metadata_for_key else {}
        visible.append(
            InstitutionalAggregateItem(
                label=labels.get(key) or _display_label(key),
                count=contributor_count,
                percentage=_percentage(contributor_count, cohort_size),
                category=category,
                suppressed=False,
                source_count=contributor_count,
                confidence="aggregate",
                metadata=metadata,
            )
        )

    suppressed: list[InstitutionalSuppressedCategory] = []
    if suppressed_count:
        visible.append(
            InstitutionalAggregateItem(
                label=LOW_SAMPLE_LABEL,
                count=None,
                percentage=None,
                category=category,
                suppressed=True,
                suppression_reason=LOW_SAMPLE_REASON,
                source_count=suppressed_count,
                confidence="suppressed",
                metadata={"minimum_group_size": minimum_group_size},
            )
        )
        suppressed.append(
            InstitutionalSuppressedCategory(
                section=section,
                suppressed_count=suppressed_count,
                suppression_reason=LOW_SAMPLE_REASON,
                minimum_group_size=minimum_group_size,
            )
        )

    return visible, suppressed


def _visible_region_counts(
    target_market_items: list[InstitutionalAggregateItem],
) -> dict[str, int]:
    visible: dict[str, int] = {}
    for item in target_market_items:
        if item.suppressed or item.count is None:
            continue
        region_id = item.metadata.get("region_id")
        if isinstance(region_id, str) and region_id:
            visible[region_id] = item.count
    return visible


def _market_demand_trends(
    session: Session,
    *,
    visible_region_counts: dict[str, int],
    region_labels: dict[str, str],
) -> list[InstitutionalAggregateItem]:
    if not visible_region_counts:
        return []
    rows = session.execute(
        select(CompanyRegionHiring)
        .where(CompanyRegionHiring.region_id.in_(list(visible_region_counts)))
        .order_by(CompanyRegionHiring.region_id, CompanyRegionHiring.company_id)
    ).scalars()
    by_region: dict[str, list[CompanyRegionHiring]] = defaultdict(list)
    for row in rows:
        by_region[row.region_id].append(row)

    items: list[InstitutionalAggregateItem] = []
    for region_id, student_count in sorted(
        visible_region_counts.items(),
        key=lambda item: (-item[1], region_labels.get(item[0], item[0])),
    ):
        region_rows = by_region.get(region_id, [])
        active_postings = sum(row.active_posting_count_now or 0 for row in region_rows)
        currently_hiring_companies = len(
            {row.company_id for row in region_rows if row.currently_hiring_flag}
        )
        trend_signal = _most_common(
            row.annualized_trend_signal for row in region_rows if row.annualized_trend_signal
        )
        confidence_values = [
            row.hiring_confidence for row in region_rows if row.hiring_confidence
        ]
        items.append(
            InstitutionalAggregateItem(
                label=region_labels.get(region_id) or _display_label(region_id),
                count=active_postings,
                category="market_demand",
                suppressed=False,
                source_count=len(region_rows),
                confidence=_most_common(confidence_values) or "limited",
                metadata={
                    "region_id": region_id,
                    "student_interest_count": student_count,
                    "currently_hiring_company_count": currently_hiring_companies,
                    "trend_signal": trend_signal or "unknown",
                },
            )
        )
    return items


def _coverage_gaps(
    session: Session,
    *,
    visible_region_counts: dict[str, int],
    region_labels: dict[str, str],
) -> tuple[list[InstitutionalAggregateItem], list[str]]:
    if not visible_region_counts:
        return [], []
    coverage_by_region = region_coverage_lookup(session)
    gaps: list[InstitutionalAggregateItem] = []
    warnings: list[str] = []

    for region_id, student_count in sorted(
        visible_region_counts.items(),
        key=lambda item: (-item[1], region_labels.get(item[0], item[0])),
    ):
        coverage = coverage_by_region.get(region_id)
        if coverage is None or not _coverage_is_weak(coverage):
            continue
        coverage_payload = _coverage_summary(coverage)
        gaps.append(
            InstitutionalAggregateItem(
                label=region_labels.get(region_id) or _display_label(region_id),
                count=student_count,
                percentage=None,
                category="coverage_gap",
                suppressed=False,
                source_count=student_count,
                coverage=coverage_payload,
                confidence=str(coverage_payload.get("label") or "limited"),
                metadata={"region_id": region_id},
            )
        )

    if gaps:
        warnings.append(
            "One or more visible target markets have limited coverage quality; "
            "treat dashboard alignment signals as directional."
        )
    return gaps, warnings


def _dashboard_coverage_warnings(
    *,
    cohort_size: int,
    minimum_group_size: int,
    visible_region_counts: dict[str, int],
    suppressed_categories: list[InstitutionalSuppressedCategory],
) -> list[str]:
    warnings: list[str] = []
    if cohort_size < minimum_group_size:
        warnings.append(
            "Cohort size is below the configured minimum group size, so "
            "category-level detail is suppressed."
        )
    if not visible_region_counts:
        warnings.append(
            "No target market category met the minimum group threshold; market "
            "demand and coverage gap detail is withheld."
        )
    if suppressed_categories:
        warnings.append(
            "Some cohort categories were withheld because too few students "
            "contributed to them."
        )
    return warnings


def _coverage_is_weak(coverage: CoverageMetadataPayload) -> bool:
    tier = coverage.tier.value
    return (
        tier in {"tier_3", "tier_4"}
        or coverage.quality_score < 50
        or not coverage.safe_for_confident_market_comparison
    )


def _coverage_summary(coverage: CoverageMetadataPayload) -> dict[str, Any]:
    return {
        "tier": coverage.tier.value,
        "label": coverage.label,
        "quality_score": coverage.quality_score,
        "safe_for_confident_market_comparison": (
            coverage.safe_for_confident_market_comparison
        ),
        "coverage_limitations": list(coverage.coverage_limitations),
    }


def _json_string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = _clean_string(item)
        elif isinstance(item, dict):
            cleaned = _clean_string(
                item.get("region_id")
                or item.get("role")
                or item.get("id")
                or item.get("value")
                or item.get("ref")
            )
        else:
            cleaned = None
        if cleaned is not None:
            values.append(cleaned)
    return sorted(set(values))


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _display_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _percentage(count: int, cohort_size: int) -> float | None:
    if cohort_size <= 0:
        return None
    return round((count / cohort_size) * 100, 1)


def _most_common(values: Iterable[str | None]) -> str | None:
    cleaned = [value for value in values if isinstance(value, str) and value.strip()]
    if not cleaned:
        return None
    return Counter(cleaned).most_common(1)[0][0]
