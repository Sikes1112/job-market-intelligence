"""Opportunity normalization helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from backend.companies.models import Company
from backend.current_opportunities.schemas import (
    CompensationInterval,
    ConfidenceLevel,
    EmploymentType,
    NormalizedOpportunity,
    OpportunityKind,
    WorkArrangement,
    safe_external_url,
)
from backend.geography.resolver import GeographicResolver


def normalize_opportunity_payload(
    payload: dict[str, Any],
    *,
    provider_record_id: str,
    companies_by_name: dict[str, Company],
    geographic_resolver: GeographicResolver,
) -> NormalizedOpportunity:
    warnings: list[str] = []
    company_name = _text(payload, "company_name") or _text(payload, "company")
    original_title = _text(payload, "title") or _text(payload, "original_title")
    normalized_title = _normalize_title(original_title)
    role_family = _role_family(payload, normalized_title)
    seniority = _seniority(payload, normalized_title)
    market_id = _text(payload, "market_id") or _text(payload, "region_id")
    market_label = _text(payload, "market_label") or _text(payload, "location")
    location_text = _text(payload, "location")
    application_url = _text(payload, "application_url") or _text(payload, "apply_url")
    source_url = _text(payload, "source_url") or _text(payload, "url")

    if company_name is None:
        warnings.append("missing_company")
    if original_title is None:
        warnings.append("missing_title")
    if application_url is None:
        warnings.append("missing_application_url")

    company = companies_by_name.get(_norm(company_name)) if company_name else None
    geographic_resolution = None
    for candidate in (market_id, market_label, location_text):
        if not candidate:
            continue
        result = geographic_resolver.resolve(candidate)
        if result.status == "ambiguous":
            geographic_resolution = result
            break
        if result.resolved:
            geographic_resolution = result
            break

    safe_application_url = None
    application_host = None
    if application_url is not None:
        try:
            safe_application_url = safe_external_url(application_url)
            application_host = urlparse(safe_application_url).hostname
        except ValueError as exc:
            warnings.append(f"invalid_application_url:{exc!s}")
    safe_source_url = None
    if source_url is not None:
        try:
            safe_source_url = safe_external_url(source_url)
        except ValueError as exc:
            warnings.append(f"invalid_source_url:{exc!s}")

    compensation_min = _float(payload.get("compensation_min") or payload.get("salary_min"))
    compensation_max = _float(payload.get("compensation_max") or payload.get("salary_max"))
    if (
        compensation_min is not None
        and compensation_max is not None
        and compensation_max < compensation_min
    ):
        warnings.append("invalid_compensation_range")
        compensation_min = None
        compensation_max = None

    confidence = ConfidenceLevel.HIGH
    if warnings:
        confidence = ConfidenceLevel.MEDIUM
    if company_name is None or original_title is None or safe_application_url is None:
        confidence = ConfidenceLevel.LOW

    return NormalizedOpportunity(
        provider_record_id=provider_record_id,
        company_name=company_name,
        company_id=company.company_id if company else _text(payload, "company_id"),
        original_title=original_title,
        normalized_title=normalized_title,
        role_family=role_family,
        seniority_level=seniority,
        market_id=(
            geographic_resolution.region_id
            if geographic_resolution and geographic_resolution.resolved
            else None
        ),
        # Preserve provider text even when its identity resolves. Canonical
        # consumers use market_id; this field remains source evidence.
        market_label=market_label,
        location_text=location_text,
        location_resolution_status=(
            geographic_resolution.status if geographic_resolution else "unresolved"
        ),
        location_resolution_source=(
            geographic_resolution.resolution_source if geographic_resolution else None
        ),
        work_arrangement=_work_arrangement(payload),
        compensation_min=compensation_min,
        compensation_max=compensation_max,
        compensation_currency=(_text(payload, "compensation_currency") or "USD")
        if compensation_min is not None or compensation_max is not None
        else None,
        compensation_interval=_compensation_interval(payload),
        employment_type=_employment_type(payload),
        opportunity_type=_opportunity_type(payload),
        posting_date=_date(payload.get("posting_date") or payload.get("posted_at")),
        closing_date=_date(payload.get("closing_date") or payload.get("expires_at")),
        application_url=safe_application_url,
        application_host=application_host,
        source_url=safe_source_url,
        description_text=_bounded_text(payload.get("description"), 8000),
        skills=_string_tuple(payload.get("skills")),
        requirements=_string_tuple(payload.get("requirements")),
        source_values={
            "company": company_name,
            "title": original_title,
            "location": location_text,
            "application_url": application_url,
            "source_url": source_url,
        },
        normalization_confidence=confidence,
        normalization_warnings=tuple(warnings),
    )


def _text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _bounded_text(value: Any, max_length: int) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    return stripped[:max_length]


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def _normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    title = _norm(value)
    replacements = {
        "software engineer i": "software engineer",
        "software engineering": "software engineer",
        "swe": "software engineer",
        "product mgr": "product manager",
    }
    return replacements.get(title, title)


def _role_family(payload: dict[str, Any], normalized_title: str | None) -> str:
    explicit = _text(payload, "role_family") or _text(payload, "function")
    if explicit:
        return explicit.strip().lower().replace(" ", "_")
    title = normalized_title or ""
    if any(token in title for token in ("software", "backend", "frontend", "cloud", "platform")):
        return "software_engineering"
    if "product" in title:
        return "product"
    if any(token in title for token in ("data", "analytics", "analyst")):
        return "data_analytics"
    if "design" in title:
        return "design"
    return "unknown"


def _seniority(payload: dict[str, Any], normalized_title: str | None) -> str:
    explicit = _text(payload, "seniority_level") or _text(payload, "level")
    if explicit:
        return explicit.strip().lower().replace(" ", "_")
    title = normalized_title or ""
    if any(token in title for token in ("intern", "internship")):
        return "internship"
    if any(token in title for token in ("new grad", "graduate", "entry")):
        return "entry_level"
    if any(token in title for token in ("senior", "staff", "principal")):
        return "senior"
    return "unknown"


def _work_arrangement(payload: dict[str, Any]) -> WorkArrangement:
    raw = _norm(
        _text(payload, "work_arrangement")
        or _text(payload, "remote_status")
        or _text(payload, "location")
    )
    if "remote" in raw:
        return WorkArrangement.REMOTE
    if "hybrid" in raw:
        return WorkArrangement.HYBRID
    if "onsite" in raw or "on site" in raw:
        return WorkArrangement.ONSITE
    if "mixed" in raw:
        return WorkArrangement.MIXED
    return WorkArrangement.UNKNOWN


def _employment_type(payload: dict[str, Any]) -> EmploymentType:
    raw = _norm(_text(payload, "employment_type"))
    mapping = {
        "full time": EmploymentType.FULL_TIME,
        "full_time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "part_time": EmploymentType.PART_TIME,
        "internship": EmploymentType.INTERNSHIP,
        "contract": EmploymentType.CONTRACT,
        "temporary": EmploymentType.TEMPORARY,
    }
    return mapping.get(raw, EmploymentType.UNKNOWN)


def _opportunity_type(payload: dict[str, Any]) -> OpportunityKind:
    raw = _norm(_text(payload, "opportunity_type") or _text(payload, "program_type"))
    mapping = {
        "job": OpportunityKind.JOB,
        "internship": OpportunityKind.INTERNSHIP,
        "co op": OpportunityKind.CO_OP,
        "co_op": OpportunityKind.CO_OP,
        "apprenticeship": OpportunityKind.APPRENTICESHIP,
        "fellowship": OpportunityKind.FELLOWSHIP,
        "early career program": OpportunityKind.EARLY_CAREER_PROGRAM,
        "early_career_program": OpportunityKind.EARLY_CAREER_PROGRAM,
    }
    if raw:
        return mapping.get(raw, OpportunityKind.UNKNOWN)
    if _employment_type(payload) is EmploymentType.INTERNSHIP:
        return OpportunityKind.INTERNSHIP
    return OpportunityKind.JOB


def _compensation_interval(payload: dict[str, Any]) -> CompensationInterval:
    raw = _norm(_text(payload, "compensation_interval"))
    mapping = {
        "annual": CompensationInterval.ANNUAL,
        "year": CompensationInterval.ANNUAL,
        "hourly": CompensationInterval.HOURLY,
        "hour": CompensationInterval.HOURLY,
        "monthly": CompensationInterval.MONTHLY,
        "stipend": CompensationInterval.STIPEND,
    }
    return mapping.get(raw, CompensationInterval.UNKNOWN)


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()
    cleaned = tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(cleaned))
