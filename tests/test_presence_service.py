import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.presence.evidence import PresenceEvidence
from backend.presence.exceptions import (
    DuplicatePresence,
    MissingCompanyForPresence,
    MissingRegionForPresence,
    PresenceNotFound,
)
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceDefinition, PresenceService
from backend.shared.state import ObjectState


def _seed(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_101",
                company_name="Example",
                normalized_company_name="example",
            ),
            Company(
                company_id="comp_202",
                company_name="Acme",
                normalized_company_name="acme",
            ),
        ]
    )
    session.flush()


def _service(
    session: Session,
    *,
    prefer_hiring_evidence: bool = True,
    allow_satellite_office_presence: bool = True,
) -> PresenceService:
    return PresenceService(
        PresenceRepository(session),
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
        prefer_hiring_evidence=prefer_hiring_evidence,
        allow_satellite_office_presence=allow_satellite_office_presence,
    )


def _def(
    presence_id: str = "p1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    office: bool = True,
    operations: bool = False,
    hiring: bool = True,
    source_refs=None,
) -> PresenceDefinition:
    return PresenceDefinition(
        presence_id=presence_id,
        company_id=company_id,
        region_id=region_id,
        evidence=PresenceEvidence(
            office_evidence_flag=office,
            operations_evidence_flag=operations,
            hiring_evidence_flag=hiring,
            source_refs=source_refs,
        ),
    )


# --- input validation -----------------------------------------------------


def test_definition_rejects_blank_required_fields() -> None:
    with pytest.raises(ValidationError):
        PresenceDefinition(
            presence_id="",
            company_id="c",
            region_id="r",
            evidence=PresenceEvidence(
                office_evidence_flag=False,
                operations_evidence_flag=False,
                hiring_evidence_flag=False,
            ),
        )


def test_definition_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PresenceDefinition.model_validate(
            {
                "presence_id": "p1",
                "company_id": "c",
                "region_id": "r",
                "evidence": {
                    "office_evidence_flag": False,
                    "operations_evidence_flag": False,
                    "hiring_evidence_flag": False,
                },
                "rogue": True,
            }
        )


# --- create / update / get / list ----------------------------------------


def test_create_presence_persists_decision(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    p = svc.create_presence(_def(office=True, hiring=True))
    assert p.presence_status == "present"
    assert p.presence_basis == "office_plus_hiring"
    assert p.presence_confidence == "high_confidence"


def test_create_presence_rejects_missing_company(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    with pytest.raises(MissingCompanyForPresence):
        svc.create_presence(_def(company_id="ghost"))


def test_create_presence_rejects_missing_region(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    with pytest.raises(MissingRegionForPresence):
        svc.create_presence(_def(region_id="ghost"))


def test_create_presence_rejects_duplicate_id(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.create_presence(_def())
    with pytest.raises(DuplicatePresence):
        svc.create_presence(
            _def(presence_id="p1", region_id="greater_sf")  # same id, different pair
        )


def test_create_presence_rejects_duplicate_pair(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.create_presence(_def())
    with pytest.raises(DuplicatePresence):
        svc.create_presence(_def(presence_id="p2"))  # same pair, different id


def test_get_presence_raises_when_missing(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    with pytest.raises(PresenceNotFound):
        svc.get_presence("ghost")


def test_list_presence(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.create_presence(_def(presence_id="p1"))
    svc.create_presence(
        _def(presence_id="p2", region_id="greater_sf", office=True, operations=True)
    )
    rows = svc.list_presence()
    assert len(rows) == 2


def test_update_presence_changes_evidence_and_bumps_version(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.create_presence(_def(office=True, hiring=True))
    updated = svc.update_presence(_def(office=True, operations=True, hiring=False))
    assert updated.presence_basis == "office_plus_operations"
    assert updated.version == 2


def test_update_presence_rejects_pair_mismatch(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.create_presence(_def())
    with pytest.raises(PresenceNotFound):
        svc.update_presence(_def(region_id="greater_sf"))


# --- upsert_for_mapping (state machine) ----------------------------------


def test_upsert_creates_and_walks_to_fresh(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    p, action = svc.upsert_for_mapping(_def())
    assert action == "created"
    assert p.state == ObjectState.FRESH.value
    assert p.version == 1


def test_upsert_unchanged_does_nothing(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.upsert_for_mapping(_def())
    same, action = svc.upsert_for_mapping(_def())
    assert action == "unchanged"
    assert same.version == 1
    assert same.state == ObjectState.FRESH.value


def test_upsert_changed_bumps_version_keeps_fresh(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    svc.upsert_for_mapping(_def(office=True, hiring=True))
    p, action = svc.upsert_for_mapping(
        _def(office=True, operations=True, hiring=False)
    )
    assert action == "updated"
    assert p.version == 2
    assert p.state == ObjectState.FRESH.value
    assert p.presence_basis == "office_plus_operations"


def test_source_refs_round_trip(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    refs = [{"kind": "office_data", "ref": "office_data_v2"}]
    p, _ = svc.upsert_for_mapping(_def(source_refs=refs))
    assert p.source_refs == refs


# --- presence rule integration -------------------------------------------


def test_satellite_only_allowed_by_default(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    p, _ = svc.upsert_for_mapping(_def(office=True, operations=False, hiring=False))
    assert p.presence_status == "present"
    assert p.presence_basis == "satellite_office_only"
    assert p.presence_confidence == "moderate_confidence"


def test_satellite_only_disallowed_via_service_option(session: Session) -> None:
    _seed(session)
    svc = _service(session, allow_satellite_office_presence=False)
    p, _ = svc.upsert_for_mapping(_def(office=True, operations=False, hiring=False))
    assert p.presence_status == "uncertain"


def test_no_evidence_at_all_is_not_present_with_unknown_confidence(
    session: Session,
) -> None:
    _seed(session)
    svc = _service(session)
    p, _ = svc.upsert_for_mapping(_def(office=False, operations=False, hiring=False))
    assert p.presence_status == "not_present"
    assert p.presence_confidence == "unknown"
