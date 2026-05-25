"""Deterministic renderer for structured guidance packets."""

from __future__ import annotations

from backend.explanations.payloads import (
    ExplanationEntityType,
    ExplanationEvidencePacket,
    ExplanationResult,
    ExplanationSection,
    ExplanationSectionType,
    ExplanationStatus,
)


class ExplanationService:
    """Render readable guidance without becoming a fact source."""

    def explain(self, evidence: ExplanationEvidencePacket) -> ExplanationResult:
        sections = [
            _structured_fact_section(evidence),
            _score_section(evidence),
            _freshness_section(evidence),
            _missing_unsupported_section(evidence),
            _personalized_overlay_section(evidence),
        ]
        sections = [section for section in sections if section.statements]
        limitations = _limitations(evidence)
        status = _status(evidence, sections)
        if status is ExplanationStatus.REFUSED:
            sections = [
                ExplanationSection(
                    section_type=ExplanationSectionType.MISSING_UNSUPPORTED_DATA,
                    title="Evidence Required",
                    statements=[
                        "The explanation layer cannot produce guidance because "
                        "the packet does not include enough structured evidence."
                    ],
                )
            ]
        return ExplanationResult(
            status=status,
            entity_type=evidence.entity_type,
            subject_refs=dict(evidence.subject_refs),
            sections=sections,
            limitations=limitations,
            evidence_refs=list(evidence.source_refs),
        )


def _structured_fact_section(evidence: ExplanationEvidencePacket) -> ExplanationSection:
    statements: list[str] = []
    label = evidence.display_label or _subject_label(evidence.entity_type, evidence.subject_refs)
    statements.append(
        "This guidance is based on structured "
        f"{evidence.entity_type.value} evidence for {label}."
    )
    if evidence.alert is not None:
        statements.append(
            f"The alert type is {evidence.alert.event_type}; relevance is "
            f"{evidence.alert.relevance_reason or 'not provided'}."
        )
        if evidence.alert.changed_fields:
            statements.append(
                "The structured change fields are: "
                + ", ".join(sorted(evidence.alert.changed_fields))
                + "."
            )
    if evidence.watchlist_context:
        statements.append(
            "User-specific relevance context: "
            + ", ".join(sorted(evidence.watchlist_context))
            + "."
        )
    if evidence.notes:
        statements.extend(f"Structured note: {note}." for note in evidence.notes)
    return ExplanationSection(
        section_type=ExplanationSectionType.STRUCTURED_FACT,
        title="Structured Facts",
        statements=statements,
    )


def _score_section(evidence: ExplanationEvidencePacket) -> ExplanationSection:
    statements: list[str] = []
    known_scores = {
        key: value for key, value in evidence.canonical_scores.items() if value is not None
    }
    if known_scores:
        ordered = sorted(known_scores.items())
        statements.append(
            "Canonical/default score fields present in the packet: "
            + ", ".join(f"{_pretty_key(key)} {_format_score(value)}" for key, value in ordered)
            + "."
        )
    missing_scores = [
        key for key, value in evidence.canonical_scores.items() if value is None
    ]
    if missing_scores:
        statements.append(
            "Canonical/default score fields missing from the packet: "
            + ", ".join(sorted(_pretty_key(key) for key in missing_scores))
            + "."
        )
    if evidence.scoring_factors:
        used = [
            factor
            for factor in evidence.scoring_factors
            if factor.value is not None and factor.status != "missing"
        ]
        missing = [
            factor
            for factor in evidence.scoring_factors
            if factor.value is None or factor.status == "missing"
        ]
        if used:
            statements.append(
                "Score factor evidence used: "
                + ", ".join(
                    f"{factor.label or _pretty_key(factor.factor)} {_format_score(factor.value)}"
                    + (
                        f" at {round(float(factor.weight) * 100)}% weight"
                        if factor.weight is not None
                        else ""
                    )
                    for factor in used
                )
                + "."
            )
        if missing:
            statements.append(
                "Some score factors were unavailable: "
                + ", ".join(factor.label or _pretty_key(factor.factor) for factor in missing)
                + "."
            )
    return ExplanationSection(
        section_type=ExplanationSectionType.SCORE_INTERPRETATION,
        title="Score Interpretation",
        statements=statements,
    )


def _freshness_section(evidence: ExplanationEvidencePacket) -> ExplanationSection:
    statements: list[str] = []
    if evidence.freshness is None:
        statements.append(
            "Freshness evidence was not provided, so recency cannot be assessed here."
        )
    else:
        status = evidence.freshness.freshness_status or "unknown"
        basis = evidence.freshness.data_basis or "unknown basis"
        statements.append(f"Freshness status is {status} with {basis} data.")
        if evidence.freshness.freshness_expires_at:
            statements.append(
                "The packet reports freshness expiration at "
                f"{evidence.freshness.freshness_expires_at}."
            )
        if evidence.freshness.source_count is not None:
            statements.append(f"The packet references {evidence.freshness.source_count} source(s).")
    if evidence.demo_or_seeded:
        statements.append(
            "This packet is marked seeded/demo, so it should not be treated as "
            "production-grade coverage."
        )
    return ExplanationSection(
        section_type=ExplanationSectionType.FRESHNESS_LIMITATION,
        title="Freshness And Coverage",
        statements=statements,
    )


def _missing_unsupported_section(evidence: ExplanationEvidencePacket) -> ExplanationSection:
    statements: list[str] = []
    if evidence.missing_data:
        statements.append(
            "Missing structured data: " + ", ".join(sorted(evidence.missing_data)) + "."
        )
    if evidence.unsupported_data:
        statements.append(
            "Unsupported in this packet: " + ", ".join(sorted(evidence.unsupported_data)) + "."
        )
    return ExplanationSection(
        section_type=ExplanationSectionType.MISSING_UNSUPPORTED_DATA,
        title="Missing Or Unsupported Data",
        statements=statements,
    )


def _personalized_overlay_section(evidence: ExplanationEvidencePacket) -> ExplanationSection:
    statements: list[str] = []
    known = {
        key: value for key, value in evidence.personalized_overlay.items() if value is not None
    }
    if known:
        statements.append(
            "Personalized overlay fields are separate from canonical/default scores: "
            + ", ".join(
                f"{_pretty_key(key)} {_format_score(value)}"
                for key, value in sorted(known.items())
            )
            + "."
        )
    if any(value is None for value in evidence.personalized_overlay.values()):
        statements.append("At least one personalized overlay field was missing or unavailable.")
    return ExplanationSection(
        section_type=ExplanationSectionType.PERSONALIZED_OVERLAY,
        title="Personalized Overlay",
        statements=statements,
    )


def _limitations(evidence: ExplanationEvidencePacket) -> list[str]:
    limitations: list[str] = [
        "Explanation text is rendered from structured evidence only and is not "
        "stored as canonical market fact."
    ]
    freshness_status = evidence.freshness.freshness_status if evidence.freshness else None
    if freshness_status in {None, "unknown", "stale", "partial", "seeded_demo"}:
        limitations.append("Do not treat the guidance as complete or real-time market coverage.")
    if evidence.unsupported_data:
        limitations.append("Unsupported dimensions are not inferred.")
    return limitations


def _status(
    evidence: ExplanationEvidencePacket,
    sections: list[ExplanationSection],
) -> ExplanationStatus:
    if not sections:
        return ExplanationStatus.REFUSED
    if evidence.missing_data or evidence.unsupported_data or evidence.freshness is None:
        return ExplanationStatus.CONSTRAINED
    freshness_status = evidence.freshness.freshness_status if evidence.freshness else None
    if (
        freshness_status in {"unknown", "stale", "partial", "seeded_demo"}
        or evidence.demo_or_seeded
    ):
        return ExplanationStatus.CONSTRAINED
    return ExplanationStatus.OK


def _subject_label(
    entity_type: ExplanationEntityType,
    refs: dict[str, str],
) -> str:
    if not refs:
        return f"the requested {entity_type.value}"
    preferred = {
        ExplanationEntityType.REGION: "region_id",
        ExplanationEntityType.COMPANY: "company_id",
        ExplanationEntityType.COMPARISON: "comparison_id",
        ExplanationEntityType.ALERT: "alert_event_id",
    }[entity_type]
    return refs.get(preferred) or next(iter(refs.values()))


def _format_score(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{round(value * 100)}%"


def _pretty_key(value: str) -> str:
    return value.replace("_", " ")
