from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.exceptions import (
    DuplicateHiring,
    HiringNotFound,
    InvalidHiringPair,
    MissingPresenceForHiring,
)
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringDefinition, HiringService, HiringSnapshot
from backend.hiring.types import (
    AnnualizedTrendSignal,
    HiringConfidence,
    SeasonalStudentHiringSignal,
)
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.shared.state import ObjectState


def _seed_pair(
    session: Session,
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    presence_status: str = "present",
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
    session.add(
        CompanyRegionPresence(
            presence_id=f"pres_{company_id}_{region_id}",
            company_id=company_id,
            region_id=region_id,
            presence_status=presence_status,
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
        )
    )
    session.flush()


def _service(session: Session) -> HiringService:
    return HiringService(
        HiringRepository(session),
        presence_repo=PresenceRepository(session),
    )


def _snapshot(**overrides) -> HiringSnapshot:
    payload = dict(currently_hiring_flag=True)
    payload.update(overrides)
    return HiringSnapshot(**payload)


def _def(
    hiring_id: str = "h1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    snapshot: HiringSnapshot | None = None,
) -> HiringDefinition:
    return HiringDefinition(
        hiring_id=hiring_id,
        company_id=company_id,
        region_id=region_id,
        snapshot=snapshot or _snapshot(),
    )


# --- snapshot validation --------------------------------------------------


def test_snapshot_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot(currently_hiring_flag=True, active_posting_count_now=-1)


def test_snapshot_rejects_negative_program_count() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot(currently_hiring_flag=False, hiring_program_count=-3)


_COUNT_FIELDS = (
    "active_posting_count_now",
    "posting_count_30d",
    "posting_count_90d",
    "hiring_program_count",
)


@pytest.mark.parametrize("field", _COUNT_FIELDS)
@pytest.mark.parametrize("bool_value", [True, False])
def test_snapshot_rejects_bool_for_count_field(field: str, bool_value: bool) -> None:
    """Pydantic v2 coerces ``bool → int`` for ``int | None`` fields unless the
    validator runs in ``mode="before"``. This test pins that booleans are
    rejected at raw-type stage for every hiring count field."""
    with pytest.raises(ValidationError):
        HiringSnapshot(currently_hiring_flag=False, **{field: bool_value})


def test_snapshot_rejects_unknown_trend_signal() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot.model_validate(
            {
                "currently_hiring_flag": True,
                "annualized_trend_signal": "skyrocketing",
            }
        )


def test_snapshot_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot.model_validate(
            {"currently_hiring_flag": False, "rogue": True}
        )


def test_snapshot_counts_default_to_none_unknown() -> None:
    s = HiringSnapshot(currently_hiring_flag=False)
    assert s.active_posting_count_now is None
    assert s.posting_count_30d is None
    assert s.posting_count_90d is None
    assert s.hiring_program_count is None


def test_snapshot_role_family_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot(
            currently_hiring_flag=True, role_family_summary={"product": -1}
        )


def test_snapshot_freshness_must_be_aware() -> None:
    with pytest.raises(ValidationError):
        HiringSnapshot(
            currently_hiring_flag=True,
            freshness_expires_at=datetime(2026, 5, 6, 12, 0),  # naive
        )


def test_snapshot_round_trip_with_full_payload() -> None:
    expires = datetime.now(UTC) + timedelta(hours=6)
    s = HiringSnapshot(
        currently_hiring_flag=True,
        active_posting_count_now=12,
        posting_count_30d=24,
        posting_count_90d=55,
        annualized_trend_signal=AnnualizedTrendSignal.POSITIVE,
        seasonal_student_hiring_signal=SeasonalStudentHiringSignal.MODERATE,
        hiring_program_count=2,
        role_family_summary={"product": 3, "ai_cloud_adjacent": 5},
        hiring_confidence=HiringConfidence.HIGH_CONFIDENCE,
        freshness_expires_at=expires,
    )
    again = HiringSnapshot.model_validate(s.model_dump())
    assert again == s


# --- service: preconditions ----------------------------------------------


def test_create_hiring_requires_presence_record(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingPresenceForHiring):
        svc.create_hiring(_def())


def test_create_hiring_rejects_uncertain_presence(session: Session) -> None:
    _seed_pair(session, presence_status="uncertain")
    svc = _service(session)
    with pytest.raises(InvalidHiringPair):
        svc.create_hiring(_def())


def test_create_hiring_rejects_not_present_pair(session: Session) -> None:
    _seed_pair(session, presence_status="not_present")
    svc = _service(session)
    with pytest.raises(InvalidHiringPair):
        svc.create_hiring(_def())


# --- service: create / update / get / list -------------------------------


def test_create_hiring_persists_snapshot(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row = svc.create_hiring(
        _def(snapshot=_snapshot(active_posting_count_now=12, posting_count_30d=24))
    )
    assert row.currently_hiring_flag is True
    assert row.active_posting_count_now == 12
    assert row.posting_count_30d == 24


def test_create_hiring_rejects_duplicate_id(session: Session) -> None:
    _seed_pair(session)
    _seed_pair(session, region_id="greater_sf")
    svc = _service(session)
    svc.create_hiring(_def(hiring_id="h1"))
    with pytest.raises(DuplicateHiring):
        svc.create_hiring(_def(hiring_id="h1", region_id="greater_sf"))


def test_create_hiring_rejects_duplicate_pair(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.create_hiring(_def(hiring_id="h1"))
    with pytest.raises(DuplicateHiring):
        svc.create_hiring(_def(hiring_id="h2"))


def test_get_hiring_raises_when_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(HiringNotFound):
        svc.get_hiring("ghost")


def test_update_hiring_changes_snapshot_and_bumps_version(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.create_hiring(_def(snapshot=_snapshot(active_posting_count_now=12)))
    updated = svc.update_hiring(_def(snapshot=_snapshot(active_posting_count_now=20)))
    assert updated.active_posting_count_now == 20
    assert updated.version == 2


def test_update_hiring_rejects_pair_mismatch(session: Session) -> None:
    _seed_pair(session)
    _seed_pair(session, region_id="greater_sf")
    svc = _service(session)
    svc.create_hiring(_def())
    with pytest.raises(HiringNotFound):
        svc.update_hiring(_def(region_id="greater_sf"))


# --- service: upsert_for_refresh -----------------------------------------


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
    svc.upsert_for_refresh(_def(snapshot=_snapshot(active_posting_count_now=12)))
    same, action = svc.upsert_for_refresh(
        _def(snapshot=_snapshot(active_posting_count_now=12))
    )
    assert action == "unchanged"
    assert same.version == 1


def test_upsert_changed_bumps_version_keeps_fresh(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    svc.upsert_for_refresh(_def(snapshot=_snapshot(active_posting_count_now=12)))
    row, action = svc.upsert_for_refresh(
        _def(snapshot=_snapshot(active_posting_count_now=20))
    )
    assert action == "updated"
    assert row.version == 2
    assert row.state == ObjectState.FRESH.value


def test_upsert_rejects_missing_pair(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingPresenceForHiring):
        svc.upsert_for_refresh(_def())


def test_freshness_only_change_is_unchanged(session: Session) -> None:
    """Rolling freshness_expires_at forward without changing data is not
    a meaningful change."""
    _seed_pair(session)
    svc = _service(session)
    expires_a = datetime.now(UTC) + timedelta(hours=1)
    expires_b = datetime.now(UTC) + timedelta(hours=24)
    svc.upsert_for_refresh(
        _def(snapshot=_snapshot(freshness_expires_at=expires_a))
    )
    same, action = svc.upsert_for_refresh(
        _def(snapshot=_snapshot(freshness_expires_at=expires_b))
    )
    assert action == "unchanged"
    assert same.version == 1


def test_role_family_summary_round_trips(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, _ = svc.upsert_for_refresh(
        _def(
            snapshot=_snapshot(
                role_family_summary={"product": 3, "ai_cloud_adjacent": 5}
            )
        )
    )
    assert row.role_family_summary == {"product": 3, "ai_cloud_adjacent": 5}


def test_signals_round_trip_as_strings(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, _ = svc.upsert_for_refresh(
        _def(
            snapshot=_snapshot(
                annualized_trend_signal=AnnualizedTrendSignal.POSITIVE,
                seasonal_student_hiring_signal=SeasonalStudentHiringSignal.STRONG,
            )
        )
    )
    assert row.annualized_trend_signal == "positive"
    assert row.seasonal_student_hiring_signal == "strong"


def test_unknown_counts_persist_as_null(session: Session) -> None:
    _seed_pair(session)
    svc = _service(session)
    row, _ = svc.upsert_for_refresh(
        _def(snapshot=_snapshot(currently_hiring_flag=False))
    )
    assert row.active_posting_count_now is None
    assert row.posting_count_30d is None
    assert row.posting_count_90d is None
    assert row.hiring_program_count is None
