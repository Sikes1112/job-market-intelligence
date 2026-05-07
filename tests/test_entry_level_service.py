import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.exceptions import (
    DuplicateEntryLevel,
    EntryLevelNotFound,
    MissingHiringForEntryLevel,
)
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import (
    EntryLevelDefinition,
    EntryLevelService,
    EntryLevelSnapshot,
)
from backend.entry_level.types import (
    EntryLevelConfidence,
    StudentSeasonRecurrenceSignal,
)
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.shared.state import ObjectState


def _seed_pair(
    session: Session,
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    has_hiring: bool = True,
) -> None:
    if session.get(Region, region_id) is None:
        session.add(
            Region(
                region_id=region_id,
                region_name=region_id,
                display_name=region_id.replace("_", " ").title(),
                region_type="greater_region",
            )
        )
    if session.get(Company, company_id) is None:
        session.add(
            Company(
                company_id=company_id,
                company_name=company_id,
                normalized_company_name=company_id,
            )
        )
    session.flush()
    if has_hiring:
        session.add(
            CompanyRegionHiring(
                hiring_id=f"hir_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
            )
        )
        session.flush()


def _service(session: Session) -> EntryLevelService:
    return EntryLevelService(
        EntryLevelRepository(session),
        hiring_repo=HiringRepository(session),
    )


def _snapshot(**overrides) -> EntryLevelSnapshot:
    return EntryLevelSnapshot(**overrides)


def _def(
    entry_level_id: str = "e1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    snapshot: EntryLevelSnapshot | None = None,
) -> EntryLevelDefinition:
    return EntryLevelDefinition(
        entry_level_id=entry_level_id,
        company_id=company_id,
        region_id=region_id,
        snapshot=snapshot or _snapshot(),
    )


# --- snapshot validation --------------------------------------------------


def test_snapshot_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        EntryLevelSnapshot(internship_count=-1)


def test_snapshot_rejects_bool_as_count() -> None:
    with pytest.raises(ValidationError):
        EntryLevelSnapshot(internship_count=True)  # type: ignore[arg-type]


def test_snapshot_rejects_unknown_recurrence_signal() -> None:
    with pytest.raises(ValidationError):
        EntryLevelSnapshot.model_validate(
            {"student_season_recurrence_signal": "yearly"}
        )


def test_snapshot_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EntryLevelSnapshot.model_validate({"rogue": True})


def test_snapshot_counts_default_to_none_unknown() -> None:
    s = EntryLevelSnapshot()
    assert s.internship_count is None
    assert s.coop_count is None
    assert s.entry_level_full_time_count is None
    assert s.formal_early_career_program_flag is False


def test_snapshot_explicit_zero_persists_as_zero(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, _ = svc.upsert_for_refresh(
        _def(
            snapshot=_snapshot(
                internship_count=0,
                coop_count=0,
                entry_level_full_time_count=0,
                student_season_recurrence_signal=StudentSeasonRecurrenceSignal.NONE,
            )
        )
    )
    assert row.internship_count == 0
    assert row.coop_count == 0
    assert row.entry_level_full_time_count == 0


# --- preconditions --------------------------------------------------------


def test_create_requires_hiring_record(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingHiringForEntryLevel):
        svc.create_entry_level(_def())


# --- create / update / get / list -----------------------------------------


def test_create_entry_level_persists_snapshot(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row = svc.create_entry_level(
        _def(snapshot=_snapshot(internship_count=3, coop_count=2))
    )
    assert row.internship_count == 3
    assert row.coop_count == 2
    assert row.entry_level_access_score is not None
    assert 0.0 <= row.entry_level_access_score <= 1.0


def test_create_entry_level_unknown_when_all_counts_none(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row = svc.create_entry_level(_def(snapshot=_snapshot()))
    assert row.entry_level_access_score is None
    assert row.entry_level_confidence == "unknown"


def test_create_entry_level_rejects_duplicate_id(session: Session) -> None:
    _seed_pair(session)
    _seed_pair(session, region_id="greater_sf")
    svc = _service(session)
    svc.create_entry_level(_def())
    with pytest.raises(DuplicateEntryLevel):
        svc.create_entry_level(_def(region_id="greater_sf"))


def test_create_entry_level_rejects_duplicate_pair(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.create_entry_level(_def(entry_level_id="e1"))
    with pytest.raises(DuplicateEntryLevel):
        svc.create_entry_level(_def(entry_level_id="e2"))


def test_get_entry_level_raises_when_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(EntryLevelNotFound):
        svc.get_entry_level("ghost")


def test_update_entry_level_changes_snapshot_and_bumps_version(
    session: Session,
) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.create_entry_level(_def(snapshot=_snapshot(internship_count=3)))
    updated = svc.update_entry_level(
        _def(snapshot=_snapshot(internship_count=5))
    )
    assert updated.internship_count == 5
    assert updated.version == 2


def test_update_entry_level_rejects_pair_mismatch(session: Session) -> None:
    _seed_pair(session)
    _seed_pair(session, region_id="greater_sf")
    svc = _service(session)
    svc.create_entry_level(_def())
    with pytest.raises(EntryLevelNotFound):
        svc.update_entry_level(_def(region_id="greater_sf"))


# --- upsert_for_refresh ---------------------------------------------------


def test_upsert_creates_and_walks_to_fresh(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, action = svc.upsert_for_refresh(_def())
    assert action == "created"
    assert row.state == ObjectState.FRESH.value
    assert row.version == 1


def test_upsert_unchanged_does_not_bump_version(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    snap = _snapshot(internship_count=3, coop_count=2)
    svc.upsert_for_refresh(_def(snapshot=snap))
    same, action = svc.upsert_for_refresh(_def(snapshot=snap))
    assert action == "unchanged"
    assert same.version == 1


def test_upsert_changed_bumps_version_keeps_fresh(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.upsert_for_refresh(_def(snapshot=_snapshot(internship_count=3)))
    row, action = svc.upsert_for_refresh(
        _def(snapshot=_snapshot(internship_count=5))
    )
    assert action == "updated"
    assert row.version == 2
    assert row.state == ObjectState.FRESH.value


# --- equal-treatment integration via the service -------------------------


def test_internship_and_coop_yield_equal_scores_via_service(
    session: Session,
) -> None:
    _seed_pair(session)
    _seed_pair(session, region_id="greater_sf")
    svc = _service(session)
    a, _ = svc.upsert_for_refresh(
        _def(
            snapshot=_snapshot(
                internship_count=4,
                coop_count=0,
                entry_level_full_time_count=0,
                student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
            )
        )
    )
    b, _ = svc.upsert_for_refresh(
        _def(
            entry_level_id="e2",
            region_id="greater_sf",
            snapshot=_snapshot(
                internship_count=0,
                coop_count=4,
                entry_level_full_time_count=0,
                student_season_recurrence_signal=StudentSeasonRecurrenceSignal.STRONG,
            ),
        )
    )
    assert a.entry_level_access_score == b.entry_level_access_score


def test_partial_metadata_yields_low_confidence(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, _ = svc.upsert_for_refresh(
        _def(
            snapshot=_snapshot(
                internship_count=3,
                coop_count=None,  # unknown
                entry_level_full_time_count=4,
            )
        )
    )
    assert row.entry_level_confidence == EntryLevelConfidence.LOW_CONFIDENCE.value
