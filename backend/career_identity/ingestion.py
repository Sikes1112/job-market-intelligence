from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import ValidationError

from backend.career_identity.exceptions import CareerIdentityValidationError
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityIngestionRequest,
    FactProvenanceInput,
)


def content_hash_for_ingestion(request: CareerIdentityIngestionRequest) -> str:
    if request.text is not None:
        body = f"{request.source_type}\n{request.text}".encode()
    else:
        body = f"{request.source_type}\n{request.structured_profile!r}".encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def fact_inputs_from_ingestion(
    request: CareerIdentityIngestionRequest,
    *,
    source_import_id: str,
) -> tuple[list[CareerIdentityFactInput], list[dict[str, Any]]]:
    provenance = FactProvenanceInput(
        source_type=request.source_type,
        source_label=request.source_label or _default_source_label(request.source_type),
        source_import_id=source_import_id,
        extraction_method=(
            "structured_profile_mapping_v1"
            if request.source_type == "structured_profile"
            else "plain_text_section_heuristics_v1"
        ),
    )
    if request.source_type == "structured_profile":
        return _facts_from_structured_profile(
            request.structured_profile or {},
            provenance=provenance,
        )
    return _facts_from_text(request.text or "", provenance=provenance)


def _facts_from_structured_profile(
    payload: dict[str, Any],
    *,
    provenance: FactProvenanceInput,
) -> tuple[list[CareerIdentityFactInput], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    facts: list[CareerIdentityFactInput] = []
    mapping = {
        "education": CareerFactType.EDUCATION,
        "experience": CareerFactType.EXPERIENCE,
        "skills": CareerFactType.SKILL,
        "projects": CareerFactType.PROJECT,
        "credentials": CareerFactType.CREDENTIAL,
        "goals": CareerFactType.CAREER_GOAL,
        "role_preferences": CareerFactType.ROLE_PREFERENCE,
        "industry_preferences": CareerFactType.INDUSTRY_PREFERENCE,
        "geographic_constraints": CareerFactType.GEOGRAPHIC_CONSTRAINT,
        "compensation_constraints": CareerFactType.COMPENSATION_CONSTRAINT,
        "timing": CareerFactType.TIMING_PREFERENCE,
        "work_arrangement_preferences": CareerFactType.WORK_ARRANGEMENT_PREFERENCE,
    }
    for key, fact_type in mapping.items():
        raw_items = payload.get(key, [])
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            raise CareerIdentityValidationError(
                f"structured_profile.{key} must be a list",
                code="invalid_structured_profile_shape",
            )
        if fact_type is CareerFactType.SKILL:
            raw_items = [
                {"name": item} if isinstance(item, str) else item
                for item in raw_items
            ]
        if not raw_items:
            continue
        for item in raw_items:
            if not isinstance(item, dict):
                raise CareerIdentityValidationError(
                    f"structured_profile.{key} entries must be objects",
                    code="invalid_structured_profile_shape",
                )
            try:
                facts.append(
                    CareerIdentityFactInput(
                        fact_type=fact_type,
                        payload=item,
                        state=CareerFactState.IMPORTED,
                        provenance=provenance,
                    )
                )
            except ValidationError as exc:
                raise CareerIdentityValidationError(
                    f"structured_profile.{key} contains an invalid item: "
                    f"{_safe_validation_summary(exc)}",
                    code="invalid_structured_profile_shape",
                ) from exc
    return facts, diagnostics


def _facts_from_text(
    text: str,
    *,
    provenance: FactProvenanceInput,
) -> tuple[list[CareerIdentityFactInput], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    sections = _split_sections(text)
    facts: list[CareerIdentityFactInput] = []

    skills_text = sections.get("skills", "")
    for skill in _split_list(skills_text):
        facts.append(
            CareerIdentityFactInput(
                fact_type=CareerFactType.SKILL,
                payload={"name": skill},
                state=CareerFactState.IMPORTED,
                provenance=provenance,
            )
        )

    for line in _non_empty_lines(sections.get("education", "")):
        item = _parse_education_line(line)
        if item is not None:
            facts.append(
                CareerIdentityFactInput(
                    fact_type=CareerFactType.EDUCATION,
                    payload=item,
                    state=CareerFactState.IMPORTED,
                    provenance=provenance,
                )
            )

    for line in _non_empty_lines(sections.get("experience", "")):
        item = _parse_experience_line(line)
        if item is not None:
            facts.append(
                CareerIdentityFactInput(
                    fact_type=CareerFactType.EXPERIENCE,
                    payload=item,
                    state=CareerFactState.IMPORTED,
                    provenance=provenance,
                )
            )

    for line in _non_empty_lines(sections.get("projects", "")):
        if len(line) <= 255:
            facts.append(
                CareerIdentityFactInput(
                    fact_type=CareerFactType.PROJECT,
                    payload={"name": line},
                    state=CareerFactState.IMPORTED,
                    provenance=provenance,
                )
            )

    for line in _non_empty_lines(sections.get("certifications", "")) + _non_empty_lines(
        sections.get("credentials", "")
    ):
        if len(line) <= 255:
            facts.append(
                CareerIdentityFactInput(
                    fact_type=CareerFactType.CREDENTIAL,
                    payload={"name": line},
                    state=CareerFactState.IMPORTED,
                    provenance=provenance,
                )
            )

    if not facts:
        diagnostics.append(
            {
                "code": "no_supported_career_facts_detected",
                "message": "No supported career facts were detected in the submitted text.",
            }
        )
    return facts, diagnostics


def _split_sections(text: str) -> dict[str, str]:
    aliases = {
        "skills": "skills",
        "technical skills": "skills",
        "education": "education",
        "experience": "experience",
        "work experience": "experience",
        "professional experience": "experience",
        "projects": "projects",
        "certifications": "certifications",
        "credentials": "credentials",
    }
    current = "summary"
    sections: dict[str, list[str]] = {current: []}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        heading = aliases.get(line.rstrip(":").casefold())
        if heading is not None:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip(" -\t") for line in text.splitlines() if line.strip(" -\t")]


def _split_list(text: str) -> list[str]:
    items: list[str] = []
    for line in _non_empty_lines(text):
        items.extend(part.strip() for part in re.split(r"[,;|]", line))
    return [item for item in dict.fromkeys(items) if item]


def _parse_education_line(line: str) -> dict[str, Any] | None:
    if len(line) > 255:
        return None
    parts = [part.strip() for part in re.split(r"\s[-|]\s", line, maxsplit=2)]
    item: dict[str, Any] = {"institution": parts[0]}
    if len(parts) > 1:
        item["degree_type"] = parts[1]
    if len(parts) > 2:
        item["field_of_study"] = parts[2]
    return item


def _parse_experience_line(line: str) -> dict[str, Any] | None:
    if len(line) > 255:
        return None
    match = re.match(r"(?P<title>.+?)\s+(?:at|@)\s+(?P<org>.+)$", line, flags=re.I)
    if match:
        return {
            "title": match.group("title").strip(),
            "organization": match.group("org").strip(),
        }
    parts = [part.strip() for part in re.split(r"\s[-|]\s", line, maxsplit=1)]
    if len(parts) == 2:
        return {"organization": parts[0], "title": parts[1]}
    return None


def _default_source_label(source_type: str) -> str:
    if source_type == "resume_text":
        return "Submitted resume text"
    if source_type == "profile_text":
        return "Submitted profile text"
    return "Submitted structured profile"


def _safe_validation_summary(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid imported fact"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = str(first.get("msg", "invalid value"))
    return f"{loc}: {msg}" if loc else msg
