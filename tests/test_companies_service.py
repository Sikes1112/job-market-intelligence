import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.classification import (
    DefaultEligibilityRule,
    DefaultMajorTechRule,
    Mag7List,
)
from backend.companies.exceptions import (
    CompanyNotFound,
    DuplicateCompany,
)
from backend.companies.overrides import Override
from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyDefinition, CompanyService
from backend.companies.types import (
    ClassificationConfidence,
    EligibilityStatus,
    PublicOrPrivate,
)
from backend.shared.state import ObjectState


def _service(
    session: Session,
    *,
    mag7: Mag7List | None = None,
) -> CompanyService:
    return CompanyService(
        CompanyRepository(session),
        eligibility_rule=DefaultEligibilityRule(),
        major_tech_rule=DefaultMajorTechRule(),
        mag7_list=mag7 or Mag7List.default(),
    )


def _def(company_id: str = "comp_101", **overrides) -> CompanyDefinition:
    base = dict(
        company_id=company_id,
        company_name="Example AI",
        normalized_company_name="example ai",
        sector_primary="ai",
        public_or_private=PublicOrPrivate.PRIVATE,
    )
    base.update(overrides)
    return CompanyDefinition(**base)


# --- CompanyDefinition validation ----------------------------------------


def test_definition_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        CompanyDefinition(
            company_id="",
            company_name="X",
            normalized_company_name="x",
        )


def test_definition_rejects_unknown_public_or_private() -> None:
    with pytest.raises(ValidationError):
        CompanyDefinition.model_validate(
            {
                "company_id": "c1",
                "company_name": "X",
                "normalized_company_name": "x",
                "public_or_private": "spinoff",
            }
        )


def test_definition_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CompanyDefinition.model_validate(
            {
                "company_id": "c1",
                "company_name": "X",
                "normalized_company_name": "x",
                "rogue": True,
            }
        )


# --- create / update / classification -------------------------------------


def test_create_company_persists_and_classifies(session: Session) -> None:
    svc = _service(session)
    c = svc.create_company(_def())
    assert c.company_id == "comp_101"
    assert c.eligibility_status == EligibilityStatus.ELIGIBLE.value  # ai sector
    assert c.is_mag7 is False
    assert c.is_major_tech is False
    assert c.classification_confidence == ClassificationConfidence.HIGH_CONFIDENCE.value
    assert c.state == ObjectState.NEW.value


def test_create_company_rejects_duplicate(session: Session) -> None:
    svc = _service(session)
    svc.create_company(_def())
    with pytest.raises(DuplicateCompany):
        svc.create_company(_def())


def test_create_company_with_excluded_sector_is_ineligible(session: Session) -> None:
    svc = _service(session)
    c = svc.create_company(_def("biotech_co", sector_primary="biotech"))
    assert c.eligibility_status == EligibilityStatus.INELIGIBLE.value
    assert c.classification_confidence == ClassificationConfidence.HIGH_CONFIDENCE.value


def test_create_company_without_sector_falls_to_unknown_confidence(
    session: Session,
) -> None:
    svc = _service(session)
    c = svc.create_company(_def("unknown_sector", sector_primary=None))
    assert c.eligibility_status == EligibilityStatus.INELIGIBLE.value
    assert c.classification_confidence == ClassificationConfidence.UNKNOWN.value


# --- Mag 7 short-circuit --------------------------------------------------


def test_mag7_company_is_eligible_and_major_tech(session: Session) -> None:
    svc = _service(session)
    c = svc.create_company(
        _def("apple", company_name="Apple", normalized_company_name="apple")
    )
    assert c.is_mag7 is True
    assert c.is_major_tech is True
    assert c.eligibility_status == EligibilityStatus.ELIGIBLE.value
    assert c.classification_confidence == ClassificationConfidence.HIGH_CONFIDENCE.value


def test_mag7_company_eligible_even_without_sector(session: Session) -> None:
    """Mag 7 short-circuit overrides the eligibility rule's 'no sector → unknown'."""
    svc = _service(session)
    c = svc.create_company(
        _def(
            "apple_no_sector",
            company_name="Apple",
            normalized_company_name="apple",
            sector_primary=None,
        )
    )
    assert c.is_mag7 is True
    assert c.eligibility_status == EligibilityStatus.ELIGIBLE.value


def test_custom_mag7_list_is_honored(session: Session) -> None:
    svc = _service(session, mag7=Mag7List.from_iterable(["acme"]))
    apple = svc.create_company(
        _def("apple", company_name="Apple", normalized_company_name="apple")
    )
    acme = svc.create_company(
        _def("acme", company_name="Acme", normalized_company_name="acme")
    )
    assert apple.is_mag7 is False
    assert acme.is_mag7 is True


# --- override path --------------------------------------------------------


def test_override_path_marks_override_included(session: Session) -> None:
    svc = _service(session)
    c = svc.create_company(
        _def(
            "edge_case",
            sector_primary="industrials",  # not in scope
            eligibility_override=Override(reason="recognized credible firm"),
        )
    )
    assert c.eligibility_status == EligibilityStatus.OVERRIDE_INCLUDED.value
    assert c.eligibility_override_flag is True
    assert c.eligibility_override_reason == "recognized credible firm"
    assert (
        c.classification_confidence == ClassificationConfidence.OVERRIDE_EDGE_CASE.value
    )


def test_override_requires_non_empty_reason() -> None:
    with pytest.raises(ValidationError):
        # Override itself enforces non-empty reason
        Override(reason="")


# --- get / list / update --------------------------------------------------


def test_get_company_raises_when_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(CompanyNotFound):
        svc.get_company("ghost")


def test_list_companies_returns_inserted(session: Session) -> None:
    svc = _service(session)
    svc.create_company(_def("a"))
    svc.create_company(_def("b"))
    rows = svc.list_companies()
    assert {c.company_id for c in rows} == {"a", "b"}


def test_update_company_changes_fields_and_bumps_version(session: Session) -> None:
    svc = _service(session)
    svc.create_company(_def())
    updated = svc.update_company(_def(company_name="Example AI Inc."))
    assert updated.company_name == "Example AI Inc."
    assert updated.version == 2


def test_update_company_raises_on_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(CompanyNotFound):
        svc.update_company(_def("ghost"))


def test_update_reclassifies_when_sector_changes(session: Session) -> None:
    svc = _service(session)
    svc.create_company(_def(sector_primary="ai"))
    updated = svc.update_company(_def(sector_primary="biotech"))
    assert updated.eligibility_status == EligibilityStatus.INELIGIBLE.value


# --- upsert_for_classify (state machine) ---------------------------------


def test_upsert_creates_and_walks_to_fresh(session: Session) -> None:
    svc = _service(session)
    c, action = svc.upsert_for_classify(_def())
    assert action == "created"
    assert c.state == ObjectState.FRESH.value
    assert c.version == 1


def test_upsert_unchanged_does_nothing(session: Session) -> None:
    svc = _service(session)
    svc.upsert_for_classify(_def())
    same, action = svc.upsert_for_classify(_def())
    assert action == "unchanged"
    assert same.version == 1
    assert same.state == ObjectState.FRESH.value


def test_upsert_changed_bumps_version_and_keeps_fresh(session: Session) -> None:
    svc = _service(session)
    svc.upsert_for_classify(_def())
    c, action = svc.upsert_for_classify(_def(company_name="Example AI Inc."))
    assert action == "updated"
    assert c.version == 2
    assert c.state == ObjectState.FRESH.value


def test_upsert_idempotent_after_override(session: Session) -> None:
    svc = _service(session)
    override = Override(reason="credible")
    svc.upsert_for_classify(_def(eligibility_override=override))
    same, action = svc.upsert_for_classify(_def(eligibility_override=override))
    assert action == "unchanged"
    assert same.eligibility_override_flag is True


def test_upsert_walks_never_built_company_to_fresh(session: Session) -> None:
    svc = _service(session)
    svc.create_company(_def())
    assert svc.get_company("comp_101").state == ObjectState.NEW.value
    c, action = svc.upsert_for_classify(_def(company_name="Example AI Inc."))
    assert action == "updated"
    assert c.state == ObjectState.FRESH.value


# --- consistency validator ------------------------------------------------


def test_consistency_validator_rejects_mag7_with_non_mag7_rule_returning_ineligible(
    session: Session,
) -> None:
    """Use a custom major-tech rule that lies about Mag 7 status to surface
    the consistency check. Normally the service's classify path prevents this
    from arising — the validator is the safety net."""
    from backend.companies.classification import MajorTechResult
    from backend.companies.exceptions import InvalidClassification

    class WrongRule:
        def evaluate(self, definition, *, is_mag7):
            return MajorTechResult(is_major_tech=True, score=1.0)

    # Force the company into ineligible by blocking Mag 7 *and* using
    # excluded sector + claiming major-tech.
    svc = CompanyService(
        CompanyRepository(session),
        eligibility_rule=DefaultEligibilityRule(),
        major_tech_rule=WrongRule(),
        mag7_list=Mag7List.from_iterable([]),  # nobody is Mag 7
    )
    with pytest.raises(InvalidClassification):
        svc.create_company(
            _def(
                "edge",
                normalized_company_name="edge",
                sector_primary="biotech",
            )
        )
