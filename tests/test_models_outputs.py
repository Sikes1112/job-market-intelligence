from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.outputs.models import OutputMetadata


def test_output_metadata_round_trip(session: Session) -> None:
    expires = datetime.now(UTC) + timedelta(hours=12)
    record = OutputMetadata(
        output_id="out_1",
        output_type="region_output",
        subject_id="greater_boston",
        artifact_uri="s3://outputs/region/greater_boston/v40.json",
        artifact_hash="sha256:abc",
        source_version_bundle={
            "region_market_scores": "regionscore_v18",
            "presence": "presence_v33",
        },
        freshness_expires_at=expires,
    )
    session.add(record)
    session.flush()
    fetched = session.get(OutputMetadata, "out_1")
    assert fetched is not None
    assert fetched.output_type == "region_output"
    assert fetched.subject_id == "greater_boston"
    assert fetched.source_version_bundle["region_market_scores"] == "regionscore_v18"
    assert fetched.state == "new"
    assert fetched.freshness_expires_at is not None


def test_output_metadata_unique_per_type_subject(session: Session) -> None:
    session.add(
        OutputMetadata(
            output_id="out_2",
            output_type="region_output",
            subject_id="greater_sf",
        )
    )
    session.flush()
    session.add(
        OutputMetadata(
            output_id="out_dup",
            output_type="region_output",
            subject_id="greater_sf",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_output_metadata_allows_same_subject_different_type(session: Session) -> None:
    """A region and a company can share a subject id namespace harmlessly."""
    session.add_all(
        [
            OutputMetadata(
                output_id="out_3",
                output_type="region_output",
                subject_id="shared_id",
            ),
            OutputMetadata(
                output_id="out_4",
                output_type="company_output",
                subject_id="shared_id",
            ),
        ]
    )
    session.flush()  # no IntegrityError expected
