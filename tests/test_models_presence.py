import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.presence.models import CompanyRegionPresence


def _seed_company_and_region(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_101",
                company_name="Example AI",
                normalized_company_name="example ai",
            ),
        ]
    )
    session.flush()


def _make_presence(**overrides) -> CompanyRegionPresence:
    defaults = dict(
        presence_id="pres_1",
        company_id="comp_101",
        region_id="greater_boston",
        presence_status="present",
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
    )
    defaults.update(overrides)
    return CompanyRegionPresence(**defaults)


def test_presence_created_and_fetched(session: Session) -> None:
    _seed_company_and_region(session)
    session.add(_make_presence())
    session.flush()
    fetched = session.get(CompanyRegionPresence, "pres_1")
    assert fetched is not None
    assert fetched.presence_status == "present"
    assert fetched.presence_basis == "office_plus_hiring"
    assert fetched.office_evidence_flag is True
    assert fetched.operations_evidence_flag is False
    assert fetched.hiring_evidence_flag is True


def test_presence_unique_per_company_region_pair(session: Session) -> None:
    _seed_company_and_region(session)
    session.add(_make_presence())
    session.flush()
    session.add(_make_presence(presence_id="pres_dup"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_presence_requires_existing_company_and_region(session: Session) -> None:
    session.add(
        _make_presence(company_id="ghost", region_id="ghost_region", presence_id="pres_ghost")
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_presence_source_refs_round_trip(session: Session) -> None:
    _seed_company_and_region(session)
    session.add(
        _make_presence(
            source_refs=[
                {"kind": "office_data", "ref": "office_data_v2"},
                {"kind": "hiring_data", "ref": "jobs_feed_v10"},
            ]
        )
    )
    session.flush()
    fetched = session.get(CompanyRegionPresence, "pres_1")
    assert fetched is not None
    assert fetched.source_refs[0]["ref"] == "office_data_v2"


def test_presence_canonical_metadata_defaults(session: Session) -> None:
    _seed_company_and_region(session)
    presence = _make_presence()
    session.add(presence)
    session.flush()
    assert presence.state == "new"
    assert presence.version == 1
