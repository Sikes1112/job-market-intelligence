from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring


def _seed(session: Session) -> None:
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


def _make_hiring(**overrides) -> CompanyRegionHiring:
    defaults = dict(
        hiring_id="hir_1",
        company_id="comp_101",
        region_id="greater_boston",
    )
    defaults.update(overrides)
    return CompanyRegionHiring(**defaults)


def test_hiring_counts_default_to_null_not_zero(session: Session) -> None:
    _seed(session)
    hiring = _make_hiring()
    session.add(hiring)
    session.flush()
    fetched = session.get(CompanyRegionHiring, "hir_1")
    assert fetched is not None
    assert fetched.active_posting_count_now is None
    assert fetched.posting_count_30d is None
    assert fetched.posting_count_90d is None
    assert fetched.hiring_program_count is None
    assert fetched.currently_hiring_flag is False


def test_hiring_unique_per_company_region_pair(session: Session) -> None:
    _seed(session)
    session.add(_make_hiring())
    session.flush()
    session.add(_make_hiring(hiring_id="hir_dup"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_hiring_round_trip_with_window_counts_and_role_summary(session: Session) -> None:
    _seed(session)
    expires = datetime.now(UTC) + timedelta(hours=6)
    session.add(
        _make_hiring(
            currently_hiring_flag=True,
            active_posting_count_now=12,
            posting_count_30d=24,
            posting_count_90d=55,
            annualized_trend_signal="positive",
            seasonal_student_hiring_signal="moderate",
            hiring_program_count=2,
            role_family_summary={"product": 3, "ai_cloud_adjacent": 5},
            hiring_confidence="high_confidence",
            freshness_expires_at=expires,
        )
    )
    session.flush()
    fetched = session.get(CompanyRegionHiring, "hir_1")
    assert fetched is not None
    assert fetched.active_posting_count_now == 12
    assert fetched.posting_count_30d == 24
    assert fetched.role_family_summary == {"product": 3, "ai_cloud_adjacent": 5}
    assert fetched.annualized_trend_signal == "positive"
    assert fetched.freshness_expires_at is not None
