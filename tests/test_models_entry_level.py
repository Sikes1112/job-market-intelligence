import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region


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


def _make_entry_level(**overrides) -> CompanyRegionEntryLevel:
    defaults = dict(
        entry_level_id="ent_1",
        company_id="comp_101",
        region_id="greater_boston",
    )
    defaults.update(overrides)
    return CompanyRegionEntryLevel(**defaults)


def test_entry_level_counts_default_to_null(session: Session) -> None:
    _seed(session)
    record = _make_entry_level()
    session.add(record)
    session.flush()
    fetched = session.get(CompanyRegionEntryLevel, "ent_1")
    assert fetched is not None
    # Honors the rule: unknown counts must not be silently treated as zero.
    assert fetched.internship_count is None
    assert fetched.coop_count is None
    assert fetched.entry_level_full_time_count is None
    assert fetched.entry_level_access_score is None
    assert fetched.formal_early_career_program_flag is False


def test_internship_and_coop_stored_as_separate_columns(session: Session) -> None:
    """Slice 9 weights internships and co-ops equally; storage keeps them distinct."""
    _seed(session)
    session.add(_make_entry_level(internship_count=3, coop_count=2))
    session.flush()
    fetched = session.get(CompanyRegionEntryLevel, "ent_1")
    assert fetched is not None
    assert fetched.internship_count == 3
    assert fetched.coop_count == 2


def test_entry_level_unique_per_company_region_pair(session: Session) -> None:
    _seed(session)
    session.add(_make_entry_level())
    session.flush()
    session.add(_make_entry_level(entry_level_id="ent_dup"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_entry_level_round_trip_with_signals(session: Session) -> None:
    _seed(session)
    session.add(
        _make_entry_level(
            internship_count=3,
            coop_count=2,
            entry_level_full_time_count=4,
            formal_early_career_program_flag=True,
            student_season_recurrence_signal="strong",
            entry_level_access_score=0.81,
            entry_level_confidence="high_confidence",
        )
    )
    session.flush()
    fetched = session.get(CompanyRegionEntryLevel, "ent_1")
    assert fetched is not None
    assert fetched.formal_early_career_program_flag is True
    assert fetched.student_season_recurrence_signal == "strong"
    assert fetched.entry_level_access_score == 0.81
