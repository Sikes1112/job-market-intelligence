import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.companies.models import Company


def _make_company(**overrides) -> Company:
    defaults = dict(
        company_id="comp_101",
        company_name="Example AI",
        normalized_company_name="example ai",
    )
    defaults.update(overrides)
    return Company(**defaults)


def test_company_created_with_required_fields(session: Session) -> None:
    session.add(_make_company())
    session.flush()
    fetched = session.get(Company, "comp_101")
    assert fetched is not None
    assert fetched.company_name == "Example AI"


def test_company_classification_defaults_are_conservative(session: Session) -> None:
    company = _make_company()
    session.add(company)
    session.flush()
    assert company.eligibility_status == "ineligible"
    assert company.eligibility_override_flag is False
    assert company.is_major_tech is False
    assert company.is_mag7 is False
    assert company.eligibility_score is None
    assert company.major_tech_score is None
    assert company.prestige_score is None
    assert company.classification_confidence is None


def test_company_canonical_metadata_defaults_set(session: Session) -> None:
    company = _make_company()
    session.add(company)
    session.flush()
    assert company.state == "new"
    assert company.version == 1


def test_company_missing_normalized_name_raises(session: Session) -> None:
    company = Company(
        company_id="comp_999",
        company_name="X",
    )
    session.add(company)
    with pytest.raises(IntegrityError):
        session.flush()


def test_company_override_fields_round_trip(session: Session) -> None:
    company = _make_company(
        eligibility_status="override_included",
        eligibility_override_flag=True,
        eligibility_override_reason="credible edge case",
        classification_confidence="override_edge_case",
        is_major_tech=True,
        major_tech_score=0.42,
        prestige_score=0.7,
    )
    session.add(company)
    session.flush()
    fetched = session.get(Company, "comp_101")
    assert fetched is not None
    assert fetched.eligibility_status == "override_included"
    assert fetched.eligibility_override_flag is True
    assert fetched.eligibility_override_reason == "credible edge case"
    assert fetched.classification_confidence == "override_edge_case"
    assert fetched.is_major_tech is True
    assert fetched.major_tech_score == 0.42
    assert fetched.prestige_score == 0.7
