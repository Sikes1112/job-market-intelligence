"""Company universe service.

Owns:
* the :class:`CompanyDefinition` Pydantic input shape,
* create / update / upsert operations over :class:`Company`,
* classification orchestration (Mag 7 first, then eligibility rule, then
  major-tech rule, then override application if present),
* a defensive consistency check that catches structurally contradictory
  classifications.

It deliberately does **not**:

* implement full scoring engines, ML, or external research (Slice 10+);
* run jobs through a queue (Slice 14);
* expose API endpoints (Slice 12);
* mutate any non-company canonical truth.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.companies.classification import (
    DefaultEligibilityRule,
    DefaultMajorTechRule,
    EligibilityRule,
    Mag7List,
    MajorTechRule,
)
from backend.companies.exceptions import (
    CompanyNotFound,
    DuplicateCompany,
    InvalidClassification,
)
from backend.companies.models import Company
from backend.companies.overrides import Override
from backend.companies.repository import CompanyRepository
from backend.companies.types import (
    ClassificationConfidence,
    EligibilityStatus,
    PublicOrPrivate,
)
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]

# Eligibility score the service stamps onto override_included companies. The
# default rule does not produce this value (overrides bypass the rule); 0.5
# is a documented "credible-but-not-confident" floor.
_OVERRIDE_INCLUDED_SCORE: float = 0.5


class CompanyDefinition(BaseModel):
    """Input shape accepted by :class:`CompanyService` and the
    eligibility-classification job handler.

    Notes:

    * ``sector_primary`` / ``sector_secondary`` stay free-form strings to
      avoid forcing schema updates when a new in-scope sector is documented;
      the default eligibility rule consults the in-scope set internally.
    * ``eligibility_override`` carries the documented override path; presence
      of an :class:`Override` flips the company to ``override_included`` with
      ``override_edge_case`` confidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    normalized_company_name: str = Field(min_length=1)
    sector_primary: str | None = None
    sector_secondary: str | None = None
    public_or_private: PublicOrPrivate | None = None
    prestige_score: float | None = None
    eligibility_override: Override | None = None


class CompanyService:
    def __init__(
        self,
        repository: CompanyRepository,
        *,
        eligibility_rule: EligibilityRule | None = None,
        major_tech_rule: MajorTechRule | None = None,
        mag7_list: Mag7List | None = None,
    ) -> None:
        self._repo = repository
        self._eligibility_rule: EligibilityRule = (
            eligibility_rule or DefaultEligibilityRule()
        )
        self._major_tech_rule: MajorTechRule = (
            major_tech_rule or DefaultMajorTechRule()
        )
        self._mag7_list = mag7_list or Mag7List.default()

    # --- reads -----------------------------------------------------------

    def get_company(self, company_id: str) -> Company:
        company = self._repo.get(company_id)
        if company is None:
            raise CompanyNotFound(company_id)
        return company

    def list_companies(self) -> list[Company]:
        return self._repo.list()

    # --- writes ----------------------------------------------------------

    def create_company(self, definition: CompanyDefinition) -> Company:
        if self._repo.exists(definition.company_id):
            raise DuplicateCompany(definition.company_id)
        company = self._build_row(definition)
        self._classify(company, definition)
        self._validate_consistency(company)
        self._repo.add(company)
        self._repo.flush()
        return company

    def update_company(self, definition: CompanyDefinition) -> Company:
        company = self.get_company(definition.company_id)
        self._apply_definition(company, definition)
        self._classify(company, definition)
        self._validate_consistency(company)
        company.version = next_version(company.version)
        self._repo.flush()
        return company

    def upsert_for_classify(
        self, definition: CompanyDefinition
    ) -> tuple[Company, UpsertOutcome]:
        """Idempotent upsert used by the Eligibility & Classification handler.

        State-machine handling matches Slice 5's geography pattern:

        * brand-new row → create + walk ``new → building → fresh``;
        * existing row + identical content → return ``"unchanged"`` (no
          version bump, no state change);
        * existing row + content differs → apply, classify, bump version;
          if state is still ``new`` or ``building``, walk to ``fresh``.
          A row already at ``fresh`` stays ``fresh`` (the new content is the
          current build; reaching ``rebuilding`` requires going through
          ``stale`` per ``OBJECT_STATE_MODEL.md`` §17 — Slices 14+).
        """
        existing = self._repo.get(definition.company_id)
        if existing is None:
            company = self.create_company(definition)
            self._set_state(company, ObjectState.BUILDING)
            self._set_state(company, ObjectState.FRESH)
            self._repo.flush()
            return company, "created"

        if self._is_unchanged(existing, definition):
            return existing, "unchanged"

        self._apply_definition(existing, definition)
        self._classify(existing, definition)
        self._validate_consistency(existing)
        existing.version = next_version(existing.version)

        if existing.state == ObjectState.NEW.value:
            self._set_state(existing, ObjectState.BUILDING)
            self._set_state(existing, ObjectState.FRESH)
        elif existing.state == ObjectState.BUILDING.value:
            self._set_state(existing, ObjectState.FRESH)
        # Other states left as-is. Slice 14 owns lifecycle progression.

        self._repo.flush()
        return existing, "updated"

    # --- internals -------------------------------------------------------

    def _build_row(self, definition: CompanyDefinition) -> Company:
        return Company(
            company_id=definition.company_id,
            company_name=definition.company_name,
            normalized_company_name=definition.normalized_company_name,
            sector_primary=definition.sector_primary,
            sector_secondary=definition.sector_secondary,
            public_or_private=(
                definition.public_or_private.value
                if definition.public_or_private
                else None
            ),
            prestige_score=definition.prestige_score,
        )

    def _apply_definition(
        self, company: Company, definition: CompanyDefinition
    ) -> None:
        company.company_name = definition.company_name
        company.normalized_company_name = definition.normalized_company_name
        company.sector_primary = definition.sector_primary
        company.sector_secondary = definition.sector_secondary
        company.public_or_private = (
            definition.public_or_private.value if definition.public_or_private else None
        )
        company.prestige_score = definition.prestige_score

    def _classify(self, company: Company, definition: CompanyDefinition) -> None:
        is_mag7 = self._mag7_list.is_mag7(definition.normalized_company_name)
        company.is_mag7 = is_mag7

        major_tech = self._major_tech_rule.evaluate(definition, is_mag7=is_mag7)
        company.is_major_tech = major_tech.is_major_tech
        company.major_tech_score = major_tech.score

        if definition.eligibility_override is not None:
            company.eligibility_status = EligibilityStatus.OVERRIDE_INCLUDED.value
            company.eligibility_override_flag = True
            company.eligibility_override_reason = definition.eligibility_override.reason
            company.classification_confidence = (
                ClassificationConfidence.OVERRIDE_EDGE_CASE.value
            )
            company.eligibility_score = _OVERRIDE_INCLUDED_SCORE
            return

        if is_mag7:
            company.eligibility_status = EligibilityStatus.ELIGIBLE.value
            company.eligibility_score = 1.0
            company.classification_confidence = (
                ClassificationConfidence.HIGH_CONFIDENCE.value
            )
            company.eligibility_override_flag = False
            company.eligibility_override_reason = None
            return

        result = self._eligibility_rule.evaluate(definition)
        company.eligibility_status = result.status.value
        company.eligibility_score = result.score
        company.classification_confidence = result.confidence.value
        company.eligibility_override_flag = False
        company.eligibility_override_reason = None

    def _validate_consistency(self, company: Company) -> None:
        if (
            company.is_mag7
            and company.eligibility_status == EligibilityStatus.INELIGIBLE.value
        ):
            raise InvalidClassification(
                f"company {company.company_id!r}: is_mag7=True with "
                "eligibility_status=ineligible — Mag 7 companies must be "
                "eligible (or override_included)."
            )
        if (
            company.is_major_tech
            and company.eligibility_status == EligibilityStatus.INELIGIBLE.value
            and not company.eligibility_override_flag
        ):
            raise InvalidClassification(
                f"company {company.company_id!r}: is_major_tech=True with "
                "eligibility_status=ineligible and no override."
            )

    def _set_state(self, company: Company, target: ObjectState) -> None:
        validate_transition(company.state, target)
        company.state = target.value

    def _is_unchanged(self, company: Company, definition: CompanyDefinition) -> bool:
        same_inputs = (
            company.company_name == definition.company_name
            and company.normalized_company_name == definition.normalized_company_name
            and company.sector_primary == definition.sector_primary
            and company.sector_secondary == definition.sector_secondary
            and company.public_or_private
            == (
                definition.public_or_private.value
                if definition.public_or_private
                else None
            )
            and company.prestige_score == definition.prestige_score
        )
        # Override toggling is a meaningful change even if other fields match.
        if definition.eligibility_override is not None:
            return same_inputs and (
                company.eligibility_override_flag
                and company.eligibility_override_reason
                == definition.eligibility_override.reason
            )
        return same_inputs and not company.eligibility_override_flag
