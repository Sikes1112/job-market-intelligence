"""Per-category audit checks.

Each function is a pure read-only inspection over canonical truth and/or
output metadata. Checks return ``list[AuditFinding]`` — empty when
everything looks clean.

These functions do **not** import upstream services, output builders,
scoring formulas, or personalization logic. They read ORM model rows and
classify them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from backend.audit.payloads import AuditFinding
from backend.audit.types import (
    DEFAULT_OVERRIDE_RATIO_WARNING_THRESHOLD,
    AuditCategory,
    AuditSeverity,
)
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

# ---------------------------------------------------------------------------
# 1. Override balance
# ---------------------------------------------------------------------------


def check_override_balance(
    companies: Iterable[Company],
    *,
    ratio_warning_threshold: float = DEFAULT_OVERRIDE_RATIO_WARNING_THRESHOLD,
) -> list[AuditFinding]:
    """Flag structural override inconsistencies.

    * ``override_included`` status with a falsy ``eligibility_override_flag``
      (or vice versa) → HIGH (internal contradiction).
    * ``override_included`` with no ``eligibility_override_reason`` → HIGH
      (override path requires a reason per docs).
    * Override-included share of all companies above
      ``ratio_warning_threshold`` → MEDIUM (deterministic threshold; tuned
      via the parameter).
    """
    findings: list[AuditFinding] = []
    company_list = list(companies)
    override_included_count = 0
    total = len(company_list)

    for c in company_list:
        is_override_status = c.eligibility_status == "override_included"
        if is_override_status:
            override_included_count += 1

        # Inconsistent flag vs status
        if is_override_status and not c.eligibility_override_flag:
            findings.append(
                AuditFinding(
                    finding_id=f"override_balance::{c.company_id}::flag_inconsistent",
                    severity=AuditSeverity.HIGH,
                    category=AuditCategory.OVERRIDE_BALANCE,
                    scope_type="company",
                    scope_ref=c.company_id,
                    message=(
                        f"company {c.company_id!r} has eligibility_status="
                        "'override_included' but eligibility_override_flag is False"
                    ),
                )
            )
        if c.eligibility_override_flag and not is_override_status:
            findings.append(
                AuditFinding(
                    finding_id=f"override_balance::{c.company_id}::orphan_flag",
                    severity=AuditSeverity.HIGH,
                    category=AuditCategory.OVERRIDE_BALANCE,
                    scope_type="company",
                    scope_ref=c.company_id,
                    message=(
                        f"company {c.company_id!r} has eligibility_override_flag=True"
                        f" but eligibility_status={c.eligibility_status!r}"
                    ),
                )
            )

        # Missing reason
        if is_override_status:
            reason = (c.eligibility_override_reason or "").strip()
            if not reason:
                findings.append(
                    AuditFinding(
                        finding_id=(
                            f"override_balance::{c.company_id}::missing_reason"
                        ),
                        severity=AuditSeverity.HIGH,
                        category=AuditCategory.OVERRIDE_BALANCE,
                        scope_type="company",
                        scope_ref=c.company_id,
                        message=(
                            f"override-included company {c.company_id!r} has no"
                            " eligibility_override_reason"
                        ),
                    )
                )

    # Ratio threshold
    if total > 0:
        ratio = override_included_count / total
        if ratio > ratio_warning_threshold:
            findings.append(
                AuditFinding(
                    finding_id="override_balance::overall::ratio_warning",
                    severity=AuditSeverity.MEDIUM,
                    category=AuditCategory.OVERRIDE_BALANCE,
                    scope_type="overall",
                    scope_ref=f"override_ratio={ratio:.2f}",
                    message=(
                        f"{override_included_count}/{total} companies are "
                        f"override-included (ratio {ratio:.2f}); threshold is "
                        f"{ratio_warning_threshold}"
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 2. Double-counting (logical-scope duplication)
# ---------------------------------------------------------------------------


def _flag_duplicates(
    items: Iterable[object],
    *,
    key,
    scope_type: str,
    finding_prefix: str,
) -> list[AuditFinding]:
    counter: Counter = Counter(key(item) for item in items)
    findings: list[AuditFinding] = []
    for scope, count in counter.items():
        if count <= 1:
            continue
        scope_ref = (
            "::".join(scope) if isinstance(scope, tuple) else str(scope)
        )
        findings.append(
            AuditFinding(
                finding_id=f"{finding_prefix}::{scope_ref}",
                severity=AuditSeverity.CRITICAL,
                category=AuditCategory.DOUBLE_COUNTING,
                scope_type=scope_type,
                scope_ref=scope_ref,
                message=(
                    f"{count} active {scope_type} rows share the same logical "
                    f"scope {scope_ref!r}"
                ),
            )
        )
    return findings


def check_double_counting(
    *,
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
    score_rows: Iterable[RegionMarketScore],
    output_metadata_rows: Iterable[OutputMetadata],
) -> list[AuditFinding]:
    """Flag any duplicate logical scope. DB unique constraints should make
    this a no-op in practice; the check exists as a defensive integrity
    canary."""
    findings: list[AuditFinding] = []

    findings.extend(
        _flag_duplicates(
            presence_rows,
            key=lambda r: (r.company_id, r.region_id),
            scope_type="company_region_presence",
            finding_prefix="double_counting::presence",
        )
    )
    findings.extend(
        _flag_duplicates(
            hiring_rows,
            key=lambda r: (r.company_id, r.region_id),
            scope_type="company_region_hiring",
            finding_prefix="double_counting::hiring",
        )
    )
    findings.extend(
        _flag_duplicates(
            entry_level_rows,
            key=lambda r: (r.company_id, r.region_id),
            scope_type="company_region_entry_level",
            finding_prefix="double_counting::entry_level",
        )
    )
    findings.extend(
        _flag_duplicates(
            score_rows,
            key=lambda r: r.region_id,
            scope_type="region_market_scores",
            finding_prefix="double_counting::region_market_scores",
        )
    )
    findings.extend(
        _flag_duplicates(
            output_metadata_rows,
            key=lambda r: (r.output_type, r.subject_id),
            scope_type="output_metadata",
            finding_prefix="double_counting::output_metadata",
        )
    )
    return findings


# ---------------------------------------------------------------------------
# 3. Presence inflation
# ---------------------------------------------------------------------------


_LOW_CONFIDENCE_VALUES: frozenset[str] = frozenset({"low_confidence", "unknown"})


def check_presence_inflation(
    presence_rows: Iterable[CompanyRegionPresence],
) -> list[AuditFinding]:
    """Flag suspicious presence rows. Conservative — only patterns the docs
    explicitly call out. Does not recompute presence."""
    findings: list[AuditFinding] = []
    for p in presence_rows:
        if p.presence_status != "present":
            continue
        scope_ref = f"{p.company_id}::{p.region_id}"

        if p.presence_basis == "insufficient_evidence":
            findings.append(
                AuditFinding(
                    finding_id=f"presence_inflation::{scope_ref}::insufficient_basis",
                    severity=AuditSeverity.HIGH,
                    category=AuditCategory.PRESENCE_INFLATION,
                    scope_type="company_region_pair",
                    scope_ref=scope_ref,
                    message=(
                        f"pair {scope_ref!r} marked present with basis "
                        "'insufficient_evidence'"
                    ),
                )
            )
        if (
            not p.office_evidence_flag
            and not p.operations_evidence_flag
            and not p.hiring_evidence_flag
        ):
            findings.append(
                AuditFinding(
                    finding_id=f"presence_inflation::{scope_ref}::no_evidence",
                    severity=AuditSeverity.HIGH,
                    category=AuditCategory.PRESENCE_INFLATION,
                    scope_type="company_region_pair",
                    scope_ref=scope_ref,
                    message=(
                        f"pair {scope_ref!r} marked present with no evidence flags set"
                    ),
                )
            )
        if (
            p.presence_confidence is not None
            and p.presence_confidence in _LOW_CONFIDENCE_VALUES
        ):
            findings.append(
                AuditFinding(
                    finding_id=(
                        f"presence_inflation::{scope_ref}::low_confidence"
                    ),
                    severity=AuditSeverity.MEDIUM,
                    category=AuditCategory.PRESENCE_INFLATION,
                    scope_type="company_region_pair",
                    scope_ref=scope_ref,
                    message=(
                        f"pair {scope_ref!r} marked present with confidence "
                        f"{p.presence_confidence!r}"
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 4. Personal/objective separation
# ---------------------------------------------------------------------------


def check_personal_objective_separation(
    output_metadata_rows: Iterable[OutputMetadata],
) -> list[AuditFinding]:
    """Detect canonical-truth contamination by personalization.

    Slice 13 must not persist personalized output rows. Any
    ``personalized_output`` row found in OutputMetadata is a critical
    integrity violation.
    """
    findings: list[AuditFinding] = []
    for row in output_metadata_rows:
        if row.output_type != "personalized_output":
            continue
        findings.append(
            AuditFinding(
                finding_id=(
                    f"personal_objective_separation::output_metadata::{row.output_id}"
                ),
                severity=AuditSeverity.CRITICAL,
                category=AuditCategory.PERSONAL_OBJECTIVE_SEPARATION,
                scope_type="output_metadata",
                scope_ref=row.output_id,
                message=(
                    f"OutputMetadata row {row.output_id!r} has output_type="
                    "'personalized_output'; personalization must not persist to "
                    "canonical output metadata"
                ),
                recommendation=(
                    "Investigate the writer; remove the row only after confirming "
                    "no downstream consumer relies on it."
                ),
            )
        )
    return findings


# ---------------------------------------------------------------------------
# 5. Output integrity
# ---------------------------------------------------------------------------


def _is_canonical_comparison_subject_id(subject_id: str) -> bool:
    if "__" not in subject_id:
        return False
    parts = subject_id.split("__")
    if len(parts) != 2:
        return False
    a, b = parts
    if not a or not b:
        return False
    return a < b  # canonical: min first (alphabetical)


def check_output_integrity(
    output_metadata_rows: Iterable[OutputMetadata],
) -> list[AuditFinding]:
    """Diagnostic structural checks on OutputMetadata rows.

    * Missing ``artifact_hash`` while in fresh/stale/partial state → MEDIUM.
    * ``comparison_output`` with a non-canonical ``subject_id`` → MEDIUM.
    """
    findings: list[AuditFinding] = []
    expected_hashed_states = {"fresh", "stale", "partial"}
    for row in output_metadata_rows:
        if row.output_type == "personalized_output":
            # Already flagged by personal/objective separation check.
            continue
        if row.state in expected_hashed_states and not row.artifact_hash:
            findings.append(
                AuditFinding(
                    finding_id=(
                        f"output_integrity::{row.output_id}::missing_artifact_hash"
                    ),
                    severity=AuditSeverity.MEDIUM,
                    category=AuditCategory.OUTPUT_INTEGRITY,
                    scope_type="output_metadata",
                    scope_ref=row.output_id,
                    message=(
                        f"OutputMetadata row {row.output_id!r} state={row.state!r} "
                        "but artifact_hash is empty"
                    ),
                )
            )
        if row.output_type == "comparison_output":
            if not _is_canonical_comparison_subject_id(row.subject_id):
                findings.append(
                    AuditFinding(
                        finding_id=(
                            f"output_integrity::{row.output_id}::noncanonical_subject_id"
                        ),
                        severity=AuditSeverity.MEDIUM,
                        category=AuditCategory.OUTPUT_INTEGRITY,
                        scope_type="output_metadata",
                        scope_ref=row.output_id,
                        message=(
                            f"comparison_output row {row.output_id!r} has "
                            f"subject_id={row.subject_id!r}; expected canonical "
                            "min__max format"
                        ),
                    )
                )
    return findings
