"""Canonical identity resolution for current opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from backend.current_opportunities.models import CurrentOpportunity
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    ConfidenceLevel,
    IdentityResolutionStatus,
    NormalizedOpportunity,
)


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    opportunity_id: str
    identity_key: str
    duplicate_group_key: str
    confidence: ConfidenceLevel
    status: IdentityResolutionStatus
    existing: CurrentOpportunity | None
    warnings: tuple[str, ...]


def resolve_current_opportunity_identity(
    repo: CurrentOpportunityRepository,
    normalized: NormalizedOpportunity,
    *,
    source_id: str,
) -> IdentityResolution:
    identity_key = canonical_identity_key(normalized)
    duplicate_key = duplicate_group_key(normalized)
    source_link = repo.get_source_link(
        source_id=source_id,
        provider_record_id=normalized.provider_record_id,
    )
    if source_link is not None:
        existing = repo.get_opportunity(source_link.current_opportunity_id)
        if existing is not None and existing.duplicate_group_key == duplicate_key:
            return IdentityResolution(
                opportunity_id=existing.current_opportunity_id,
                identity_key=existing.canonical_identity_key,
                duplicate_group_key=duplicate_key,
                confidence=ConfidenceLevel.HIGH,
                status=IdentityResolutionStatus.EXISTING_SOURCE_RECORD,
                existing=existing,
                warnings=(),
            )
        if existing is not None and _same_entity_except_geography(existing, normalized):
            warnings: tuple[str, ...] = ()
            if existing.market_id is not None and normalized.market_id is None:
                warnings = ("geography_resolution_degraded_ignored",)
            elif (
                existing.market_id is not None
                and normalized.market_id is not None
                and existing.market_id != normalized.market_id
            ):
                warnings = (
                    f"resolved_geography_conflict:{existing.market_id}:{normalized.market_id}",
                )
            return IdentityResolution(
                opportunity_id=existing.current_opportunity_id,
                identity_key=identity_key,
                duplicate_group_key=duplicate_key,
                confidence=ConfidenceLevel.HIGH,
                status=IdentityResolutionStatus.EXISTING_SOURCE_RECORD,
                existing=existing,
                warnings=warnings,
            )
        warnings = ("provider_record_identity_conflict",)
        return IdentityResolution(
            opportunity_id=opportunity_id(identity_key),
            identity_key=identity_key,
            duplicate_group_key=duplicate_key,
            confidence=ConfidenceLevel.LOW,
            status=IdentityResolutionStatus.SOURCE_ID_REUSE_CONFLICT,
            existing=repo.get_opportunity_by_identity_key(identity_key),
            warnings=warnings,
        )

    existing_by_identity = repo.get_opportunity_by_identity_key(identity_key)
    if existing_by_identity is not None:
        return IdentityResolution(
            opportunity_id=existing_by_identity.current_opportunity_id,
            identity_key=identity_key,
            duplicate_group_key=duplicate_key,
            confidence=ConfidenceLevel.HIGH,
            status=IdentityResolutionStatus.CROSS_SOURCE_DUPLICATE,
            existing=existing_by_identity,
            warnings=(),
        )

    duplicate = repo.get_opportunity_by_duplicate_group(duplicate_key)
    if duplicate is not None:
        return IdentityResolution(
            opportunity_id=duplicate.current_opportunity_id,
            identity_key=duplicate.canonical_identity_key,
            duplicate_group_key=duplicate_key,
            confidence=ConfidenceLevel.MEDIUM,
            status=IdentityResolutionStatus.CROSS_SOURCE_DUPLICATE,
            existing=duplicate,
            warnings=("cross_source_duplicate_group_match",),
        )

    potential = _potential_duplicate(repo, normalized)
    if potential is not None:
        return IdentityResolution(
            opportunity_id=opportunity_id(identity_key),
            identity_key=identity_key,
            duplicate_group_key=duplicate_key,
            confidence=ConfidenceLevel.LOW,
            status=IdentityResolutionStatus.POTENTIAL_DUPLICATE,
            existing=None,
            warnings=(f"potential_duplicate:{potential.current_opportunity_id}",),
        )

    return IdentityResolution(
        opportunity_id=opportunity_id(identity_key),
        identity_key=identity_key,
        duplicate_group_key=duplicate_key,
        confidence=ConfidenceLevel.HIGH
        if normalized.application_url and normalized.company_name and normalized.normalized_title
        else ConfidenceLevel.LOW,
        status=IdentityResolutionStatus.NEW,
        existing=None,
        warnings=(),
    )


def canonical_identity_key(normalized: NormalizedOpportunity) -> str:
    company = _norm(normalized.company_id or normalized.company_name or "unknown_company")
    title = _norm(normalized.normalized_title or "unknown_title")
    market = _norm(
        normalized.market_id
        or normalized.market_label
        or normalized.location_text
        or "unknown_market"
    )
    route = _norm(
        normalized.application_host or normalized.application_url or normalized.provider_record_id
    )
    return "|".join((company, title, market, normalized.employment_type.value, route))


def duplicate_group_key(normalized: NormalizedOpportunity) -> str:
    company = _norm(normalized.company_id or normalized.company_name or "unknown_company")
    title = _norm(normalized.normalized_title or "unknown_title")
    market = _norm(
        normalized.market_id
        or normalized.market_label
        or normalized.location_text
        or "unknown_market"
    )
    return "|".join((company, title, market, normalized.employment_type.value))


def canonical_identity_keys_for_row(
    row: CurrentOpportunity,
    *,
    market_id: str,
    provider_record_id: str,
) -> tuple[str, str]:
    """Rebuild both identity indexes after an authorized geography correction."""

    company = _norm(row.company_id or row.company_name or "unknown_company")
    title = _norm(row.normalized_title or "unknown_title")
    market = _norm(market_id)
    route = _norm(
        row.application_host or row.application_url or provider_record_id
    )
    identity_key = "|".join((company, title, market, row.employment_type, route))
    duplicate_key = "|".join((company, title, market, row.employment_type))
    return identity_key, duplicate_key


def source_identity_key(source_id: str, provider_record_id: str) -> str:
    return f"{source_id}|{provider_record_id}"


def opportunity_id(identity_key: str) -> str:
    return "current_opp_" + sha256(identity_key.encode("utf-8")).hexdigest()[:24]


def evidence_id(observation_id: str, opportunity_id_value: str) -> str:
    seed = f"{observation_id}|{opportunity_id_value}"
    return "opp_ident_" + sha256(seed.encode("utf-8")).hexdigest()[:24]


def link_id(source_id: str, provider_record_id: str) -> str:
    seed = source_identity_key(source_id, provider_record_id)
    return "opp_link_" + sha256(seed.encode("utf-8")).hexdigest()[:24]


def _potential_duplicate(
    repo: CurrentOpportunityRepository,
    normalized: NormalizedOpportunity,
) -> CurrentOpportunity | None:
    company = _norm(normalized.company_id or normalized.company_name or "")
    market = _norm(
        normalized.market_id or normalized.market_label or normalized.location_text or ""
    )
    if not company or not market or normalized.role_family == "unknown":
        return None
    for row in repo.list_opportunities(limit=10000):
        row_company = _norm(row.company_id or row.company_name)
        row_market = _norm(row.market_id or row.market_label or row.location_text or "")
        if (
            row_company == company
            and row_market == market
            and row.role_family == normalized.role_family
        ):
            return row
    return None


def _same_entity_except_geography(
    row: CurrentOpportunity,
    normalized: NormalizedOpportunity,
) -> bool:
    """Protect provider-stable identity when only location evidence changes."""

    row_company = _norm(row.company_id or row.company_name or "unknown_company")
    incoming_company = _norm(normalized.company_id or normalized.company_name or "unknown_company")
    return (
        row_company == incoming_company
        and _norm(row.normalized_title or "unknown_title")
        == _norm(normalized.normalized_title or "unknown_title")
        and row.employment_type == normalized.employment_type.value
    )


def _norm(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())
