from sqlalchemy.orm import Session

from backend.outputs.models import OutputMetadata
from backend.outputs.repository import OutputMetadataRepository


def _make(
    output_id: str = "out_1",
    output_type: str = "region_output",
    subject_id: str = "greater_boston",
) -> OutputMetadata:
    return OutputMetadata(
        output_id=output_id,
        output_type=output_type,
        subject_id=subject_id,
    )


def test_repository_get_returns_none_for_missing(session: Session) -> None:
    repo = OutputMetadataRepository(session)
    assert repo.get("ghost") is None
    assert repo.get_by_type_and_subject("region_output", "ghost") is None


def test_repository_round_trip(session: Session) -> None:
    repo = OutputMetadataRepository(session)
    repo.add(_make())
    repo.flush()
    assert repo.get("out_1") is not None
    assert (
        repo.get_by_type_and_subject("region_output", "greater_boston").output_id
        == "out_1"
    )


def test_repository_list_returns_sorted(session: Session) -> None:
    repo = OutputMetadataRepository(session)
    repo.add(_make("z", "region_output", "z_region"))
    repo.add(_make("a", "company_output", "a_company"))
    repo.add(_make("b", "region_output", "a_region"))
    repo.flush()
    rows = repo.list()
    # ordered by (output_type, subject_id)
    assert [r.output_id for r in rows] == ["a", "b", "z"]
