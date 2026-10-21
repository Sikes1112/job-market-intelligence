from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.config.settings import Settings
from backend.explore.shared_intelligence import (
    SharedIntelligenceCoordinator,
    SharedIntelligenceWaitTimeout,
)
from backend.market_intelligence.schemas import CareerGoal
from backend.shared.db import create_all, make_engine


@dataclass(frozen=True, slots=True)
class _Result:
    label: str
    nested: dict[str, int]


class _Intelligence:
    def __init__(self) -> None:
        self.ranking_calls = 0
        self.summary_calls = 0
        self.value = 1
        self.fail_next = False
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False
        self._lock = threading.Lock()

    def ranking(self, *, goal, as_of=None):  # noqa: ANN001, ANN201
        with self._lock:
            self.ranking_calls += 1
        self.started.set()
        if self.block:
            assert self.release.wait(2.0)
        if self.fail_next:
            self.fail_next = False
            raise ValueError("expected calculation failure")
        return _Result(f"ranking:{goal}:{as_of}", {"value": self.value})

    def platform_summary(self, *, goal=CareerGoal.SOFTWARE_ENGINEERING, as_of=None):  # noqa: ANN001, ANN201
        with self._lock:
            self.summary_calls += 1
        return _Result(f"summary:{goal}:{as_of}", {"value": self.value})


def _coordinator(
    *,
    capacity: int = 8,
    wait_timeout_seconds: float = 1.0,
    engine_identity: int = 1,
) -> SharedIntelligenceCoordinator:
    return SharedIntelligenceCoordinator(
        release_id="release-test",
        engine_identity=engine_identity,
        capacity=capacity,
        wait_timeout_seconds=wait_timeout_seconds,
        process_generation="process-test",
    )


def _wait_for_coalesced(
    coordinator: SharedIntelligenceCoordinator,
    expected: int,
) -> None:
    deadline = time.monotonic() + 1.0
    while coordinator.stats().coalesced_waits < expected:
        if time.monotonic() >= deadline:
            raise AssertionError("callers did not join the in-flight calculation")
        time.sleep(0.001)


def test_four_cold_callers_share_one_calculation_and_receive_independent_results() -> None:
    coordinator = _coordinator()
    intelligence = _Intelligence()
    intelligence.block = True

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(
                coordinator.ranking,
                intelligence,
                goal=CareerGoal.SOFTWARE_ENGINEERING,
                as_of=date(2026, 10, 20),
            )
            for _ in range(4)
        ]
        assert intelligence.started.wait(1.0)
        _wait_for_coalesced(coordinator, 3)
        intelligence.release.set()
        results = [future.result(timeout=2.0) for future in futures]

    assert intelligence.ranking_calls == 1
    assert coordinator.stats().calculations_started == 1
    assert coordinator.stats().coalesced_waits == 3
    assert all(result == results[0] for result in results)
    assert len({id(result) for result in results}) == 4
    assert len({id(result.nested) for result in results}) == 4
    results[0].nested["value"] = 999
    assert [result.nested["value"] for result in results[1:]] == [1, 1, 1]
    warm = coordinator.ranking(
        intelligence,
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        as_of=date(2026, 10, 20),
    )
    assert warm.nested == {"value": 1}
    assert intelligence.ranking_calls == 1
    assert coordinator.stats().cache_hits == 1


def test_goal_date_and_operation_are_independent_key_dimensions() -> None:
    coordinator = _coordinator()
    intelligence = _Intelligence()
    day = date(2026, 10, 20)

    first = coordinator.ranking(intelligence, goal="software_engineering", as_of=day)
    equivalent = coordinator.ranking(
        intelligence,
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        as_of=datetime(2026, 10, 20, 23, 59, tzinfo=UTC),
    )
    coordinator.ranking(intelligence, goal="product_management", as_of=day)
    coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 21),
    )
    coordinator.platform_summary(intelligence, as_of=day)

    assert first == equivalent
    assert intelligence.ranking_calls == 3
    assert intelligence.summary_calls == 1
    assert coordinator.stats().calculations_started == 4


def test_failed_calculation_is_shared_but_does_not_poison_retry() -> None:
    coordinator = _coordinator()
    intelligence = _Intelligence()
    intelligence.block = True
    intelligence.fail_next = True

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(
                coordinator.ranking,
                intelligence,
                goal="software_engineering",
                as_of=date(2026, 10, 20),
            )
            for _ in range(4)
        ]
        assert intelligence.started.wait(1.0)
        _wait_for_coalesced(coordinator, 3)
        intelligence.release.set()
        for future in futures:
            with pytest.raises(ValueError, match="expected calculation failure"):
                future.result(timeout=2.0)

    intelligence.block = False
    result = coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )
    assert result.nested == {"value": 1}
    assert intelligence.ranking_calls == 2
    stats = coordinator.stats()
    assert stats.calculations_failed == 1
    assert stats.calculations_succeeded == 1
    assert stats.completed_entries == 1


def test_waiters_have_a_bounded_wait_without_cancelling_the_leader() -> None:
    coordinator = _coordinator(wait_timeout_seconds=0.02)
    intelligence = _Intelligence()
    intelligence.block = True

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(
            coordinator.ranking,
            intelligence,
            goal="software_engineering",
            as_of=date(2026, 10, 20),
        )
        assert intelligence.started.wait(1.0)
        waiter = pool.submit(
            coordinator.ranking,
            intelligence,
            goal="software_engineering",
            as_of=date(2026, 10, 20),
        )
        with pytest.raises(SharedIntelligenceWaitTimeout):
            waiter.result(timeout=1.0)
        intelligence.release.set()
        assert leader.result(timeout=2.0).nested == {"value": 1}

    assert coordinator.stats().wait_timeouts == 1
    assert coordinator.stats().completed_entries == 1


def test_lru_capacity_is_fixed_and_evicted_keys_recompute() -> None:
    coordinator = _coordinator(capacity=2)
    intelligence = _Intelligence()

    for goal in (
        "software_engineering",
        "product_management",
        "ai_ml",
    ):
        coordinator.ranking(intelligence, goal=goal, as_of=date(2026, 10, 20))

    stats = coordinator.stats()
    assert stats.capacity == 2
    assert stats.completed_entries == 2
    assert stats.evictions == 1
    coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )
    assert intelligence.ranking_calls == 4
    assert coordinator.stats().completed_entries == 2


def test_invalidation_advances_evidence_generation_for_mutable_fixture_changes() -> None:
    coordinator = _coordinator()
    intelligence = _Intelligence()

    original = coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )
    intelligence.value = 2
    cached = coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )
    coordinator.invalidate()
    refreshed = coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )

    assert original.nested == cached.nested == {"value": 1}
    assert refreshed.nested == {"value": 2}
    assert intelligence.ranking_calls == 2
    assert coordinator.stats().invalidations == 1


def test_different_keys_compute_concurrently_without_a_coordinator_wide_lock() -> None:
    coordinator = _coordinator()
    barrier = threading.Barrier(2)

    class _ParallelIntelligence(_Intelligence):
        def ranking(self, *, goal, as_of=None):  # noqa: ANN001, ANN201
            with self._lock:
                self.ranking_calls += 1
            barrier.wait(timeout=1.0)
            return _Result(str(goal), {"value": 1})

    intelligence = _ParallelIntelligence()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda goal: coordinator.ranking(
                    intelligence,
                    goal=goal,
                    as_of=date(2026, 10, 20),
                ),
                ("software_engineering", "product_management"),
            )
        )

    assert len(results) == 2
    assert intelligence.ranking_calls == 2


def test_in_flight_completion_remains_valid_during_concurrent_eviction() -> None:
    coordinator = _coordinator(capacity=1)
    slow_started = threading.Event()
    release_slow = threading.Event()

    class _EvictionIntelligence(_Intelligence):
        def ranking(self, *, goal, as_of=None):  # noqa: ANN001, ANN201
            with self._lock:
                self.ranking_calls += 1
            if goal == CareerGoal.SOFTWARE_ENGINEERING:
                slow_started.set()
                assert release_slow.wait(1.0)
            return _Result(str(goal), {"value": 1})

    intelligence = _EvictionIntelligence()
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(
            coordinator.ranking,
            intelligence,
            goal="software_engineering",
            as_of=date(2026, 10, 20),
        )
        assert slow_started.wait(1.0)
        fast = coordinator.ranking(
            intelligence,
            goal="product_management",
            as_of=date(2026, 10, 20),
        )
        release_slow.set()
        slow_result = slow.result(timeout=2.0)

    assert fast.label == CareerGoal.PRODUCT_MANAGEMENT.value
    assert slow_result.label == CareerGoal.SOFTWARE_ENGINEERING.value
    assert coordinator.stats().completed_entries == 1
    assert coordinator.stats().evictions == 1
    warm_slow = coordinator.ranking(
        intelligence,
        goal="software_engineering",
        as_of=date(2026, 10, 20),
    )
    assert warm_slow == slow_result
    assert intelligence.ranking_calls == 2


def test_separate_coordinators_never_share_entries() -> None:
    first = _coordinator(engine_identity=1)
    second = _coordinator(engine_identity=2)
    intelligence = _Intelligence()

    first.ranking(intelligence, goal="software_engineering", as_of=date(2026, 10, 20))
    second.ranking(intelligence, goal="software_engineering", as_of=date(2026, 10, 20))

    assert intelligence.ranking_calls == 2
    assert first.stats().completed_entries == 1
    assert second.stats().completed_entries == 1


def test_coordinator_is_app_scoped_and_enabled_only_for_public_guest(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "assets").mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    guest_settings = Settings(
        app_env="public_guest_demo",
        database_url="sqlite:///:memory:",
        public_origin="https://demo.example",
        frontend_dist_dir=str(dist),
        release_id="release-test",
        _env_file=None,
    )
    first_engine = make_engine("sqlite:///:memory:")
    second_engine = make_engine("sqlite:///:memory:")
    local_engine = make_engine("sqlite:///:memory:")
    for engine in (first_engine, second_engine, local_engine):
        create_all(engine)
    try:
        first = create_app(engine=first_engine, settings=guest_settings)
        second = create_app(engine=second_engine, settings=guest_settings)
        local = create_app(
            engine=local_engine,
            settings=Settings(
                app_env="test",
                database_url="sqlite:///:memory:",
                release_id="release-test",
                _env_file=None,
            ),
        )
        assert first.state.explore_shared_intelligence is not None
        assert second.state.explore_shared_intelligence is not None
        assert (
            first.state.explore_shared_intelligence
            is not second.state.explore_shared_intelligence
        )
        assert local.state.explore_shared_intelligence is None
    finally:
        first_engine.dispose()
        second_engine.dispose()
        local_engine.dispose()


@pytest.mark.parametrize(
    ("capacity", "wait_timeout_seconds"),
    ((0, 1.0), (1, 0.0)),
)
def test_invalid_bounds_are_rejected(capacity: int, wait_timeout_seconds: float) -> None:
    with pytest.raises(ValueError):
        _coordinator(capacity=capacity, wait_timeout_seconds=wait_timeout_seconds)
