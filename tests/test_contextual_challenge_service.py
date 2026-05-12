"""ContextualChallengeService tests — exercises the persistence path."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.outputs.contextual_challenge import (
    ChallengeStatus,
    ContextualChallengeService,
)
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingRegionForOutput,
)
from backend.outputs.models import OutputMetadata
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.types import BuildOutcome
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.shared.state import ObjectState


def _service(session: Session) -> ContextualChallengeService:
    return ContextualChallengeService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _seed_region(session: Session, region_id: str) -> Region:
    region = Region(
        region_id=region_id,
        region_name=region_id,
        display_name=region_id.replace("_", " ").title(),
        region_type="greater_region",
    )
    session.add(region)
    session.flush()
    return region


def _seed_score(
    session: Session,
    *,
    region_id: str,
    objective: float | None = 0.7,
    live: float | None = 0.5,
    structural: float | None = 0.5,
    early_career: float | None = 0.5,
    raw_total: float | None = 0.5,
    general_density: float | None = 0.5,
    tech_density: float | None = 0.5,
) -> RegionMarketScore:
    s = RegionMarketScore(
        region_score_id=f"rms_{region_id}",
        region_id=region_id,
        structural_ecosystem_score=structural,
        live_market_score=live,
        objective_opportunity_score=objective,
        raw_total_score=raw_total,
        general_density_score=general_density,
        tech_market_density_score=tech_density,
        early_career_accessibility_score=early_career,
        score_ruleset_version="marketscore_v1",
    )
    session.add(s)
    session.flush()
    return s


def test_first_build_creates_metadata_row(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8, live=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4, live=0.4)

    svc = _service(session)
    result = svc.build("greater_boston", "greater_sf")

    assert result.action == "created"
    assert result.metadata.output_type == "contextual_challenge_output"
    assert result.metadata.subject_id == "greater_boston__greater_sf"
    assert result.metadata.state == "fresh"
    assert result.metadata.artifact_hash is not None
    assert result.metadata.artifact_uri is None
    assert result.metadata.version == 1
    assert (
        result.payload.contextual_challenge.challenge_status
        is ChallengeStatus.REINFORCED
    )


def test_unchanged_rebuild_does_not_bump_version(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8, live=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4, live=0.4)

    svc = _service(session)
    first = svc.build("greater_boston", "greater_sf")
    initial_version = first.metadata.version
    initial_hash = first.metadata.artifact_hash

    second = svc.build("greater_boston", "greater_sf")
    assert second.action == "unchanged"
    assert second.metadata.version == initial_version
    assert second.metadata.artifact_hash == initial_hash


def test_changed_rebuild_bumps_version_and_state_stays_fresh(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    score_a = _seed_score(
        session, region_id="greater_boston", objective=0.8, live=0.8
    )
    _seed_score(session, region_id="greater_sf", objective=0.4, live=0.4)

    svc = _service(session)
    first = svc.build("greater_boston", "greater_sf")
    initial_version = first.metadata.version

    # Mutate score values; this changes the artifact_hash.
    score_a.live_market_score = 0.1  # SF now wins live; fewer reinforcements.
    session.flush()

    second = svc.build("greater_boston", "greater_sf")
    assert second.action == "updated"
    assert second.metadata.version == initial_version + 1
    assert second.metadata.state == "fresh"


@pytest.mark.parametrize(
    ("initial", "outcome", "expected_path"),
    [
        (ObjectState.FRESH, BuildOutcome.FRESH, ["rebuilding", "fresh"]),
        (ObjectState.FRESH, BuildOutcome.STALE, ["rebuilding", "fresh", "stale"]),
        (ObjectState.FRESH, BuildOutcome.PARTIAL, ["rebuilding", "partial"]),
        (ObjectState.STALE, BuildOutcome.FRESH, ["rebuilding", "fresh"]),
        (ObjectState.PARTIAL, BuildOutcome.FRESH, ["rebuilding", "fresh"]),
    ],
)
def test_changed_rebuild_walks_existing_contextual_state_through_rebuilding(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    initial: ObjectState,
    outcome: BuildOutcome,
    expected_path: list[str],
) -> None:
    svc = _service(session)
    row = OutputMetadata(
        output_id="out_contextual_test",
        output_type="contextual_challenge_output",
        subject_id="a__b",
        state=initial.value,
    )
    transitions: list[str] = []
    original = svc._set_state

    def record_transition(row: OutputMetadata, target: ObjectState) -> None:
        transitions.append(target.value)
        original(row, target)

    monkeypatch.setattr(svc, "_set_state", record_transition)
    svc._walk_changed_rebuild_state(row, outcome)

    assert transitions == expected_path
    assert row.state == expected_path[-1]


def test_subject_id_is_canonical_regardless_of_argument_order(
    session: Session,
) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4)

    svc = _service(session)
    forward = svc.build("greater_boston", "greater_sf")
    reverse = svc.build("greater_sf", "greater_boston")
    assert forward.metadata.output_id == reverse.metadata.output_id
    assert reverse.action == "unchanged"


def test_missing_score_yields_partial_state(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8)
    # No score for greater_sf.

    svc = _service(session)
    result = svc.build("greater_boston", "greater_sf")
    assert result.action == "created"
    assert result.metadata.state == "partial"
    assert (
        result.payload.contextual_challenge.challenge_status
        is ChallengeStatus.INSUFFICIENT_DATA
    )


def test_rejects_identical_regions(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_score(session, region_id="greater_boston", objective=0.8)
    svc = _service(session)
    with pytest.raises(InvalidComparisonInput):
        svc.build("greater_boston", "greater_boston")


def test_rejects_blank_region_id(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(InvalidComparisonInput):
        svc.build("", "greater_sf")


def test_missing_region_raises(session: Session) -> None:
    _seed_region(session, "greater_boston")
    svc = _service(session)
    with pytest.raises(MissingRegionForOutput):
        svc.build("greater_boston", "nope")


def test_does_not_modify_comparison_outputs_table(session: Session) -> None:
    """Contextual challenge writes only ``contextual_challenge_output`` rows;
    the primary comparison output is never touched."""
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4)

    svc = _service(session)
    svc.build("greater_boston", "greater_sf")

    repo = OutputMetadataRepository(session)
    rows = repo.list()
    types = {r.output_type for r in rows}
    assert types == {"contextual_challenge_output"}


def test_source_version_bundle_records_score_versions(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4)

    svc = _service(session)
    result = svc.build("greater_boston", "greater_sf")
    bundle = result.metadata.source_version_bundle
    assert bundle["region_a"]["region_id"] == "greater_boston"
    assert bundle["region_b"]["region_id"] == "greater_sf"
    assert bundle["region_a"]["region_market_score_version"] == 1
    assert bundle["region_b"]["region_market_score_version"] == 1
