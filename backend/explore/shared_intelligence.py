"""Bounded process-local reuse for public-guest market intelligence.

Only request-independent Layer 34 ranking and platform-summary DTOs belong here.
Career Identity, consent, preferences, geographic constraints, opportunity
coverage, telemetry, and final Explore responses remain request scoped.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from threading import Lock
from typing import Protocol, TypeVar, cast
from uuid import uuid4

from backend.market_intelligence.schemas import (
    CareerGoal,
    ExplainableRankingReport,
    PlatformMarketIntelligenceReport,
)

PUBLIC_GUEST_SHARED_INTELLIGENCE_CAPACITY = 8
PUBLIC_GUEST_SHARED_INTELLIGENCE_WAIT_SECONDS = 30.0

_T = TypeVar("_T")


class _MarketIntelligence(Protocol):
    def ranking(
        self,
        *,
        goal: CareerGoal | str,
        as_of: date | datetime | None = None,
    ) -> ExplainableRankingReport: ...

    def platform_summary(
        self,
        *,
        goal: CareerGoal | str = CareerGoal.SOFTWARE_ENGINEERING,
        as_of: date | datetime | None = None,
    ) -> PlatformMarketIntelligenceReport: ...


class SharedIntelligenceWaitTimeout(TimeoutError):
    """A waiter exceeded the bounded single-flight wait."""


@dataclass(frozen=True, slots=True)
class SharedIntelligenceKey:
    operation: str
    goal: str
    as_of: date
    release_id: str
    process_generation: str
    engine_identity: int
    evidence_generation: int


@dataclass(frozen=True, slots=True)
class SharedIntelligenceStats:
    capacity: int
    completed_entries: int
    in_flight_entries: int
    calculations_started: int
    calculations_succeeded: int
    calculations_failed: int
    cache_hits: int
    coalesced_waits: int
    evictions: int
    invalidations: int
    wait_timeouts: int


class SharedIntelligenceCoordinator:
    """Single-flight and bounded LRU reuse for immutable shared DTOs.

    The coordinator is intentionally app scoped. The public guest runtime has no
    route capable of mutating canonical market evidence, so the evidence
    generation remains valid for the process lifetime. ``invalidate`` is the
    explicit boundary for tests and any future in-process evidence replacement.
    """

    def __init__(
        self,
        *,
        release_id: str,
        engine_identity: int,
        capacity: int = PUBLIC_GUEST_SHARED_INTELLIGENCE_CAPACITY,
        wait_timeout_seconds: float = PUBLIC_GUEST_SHARED_INTELLIGENCE_WAIT_SECONDS,
        process_generation: str | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("shared intelligence capacity must be positive")
        if wait_timeout_seconds <= 0:
            raise ValueError("shared intelligence wait timeout must be positive")
        self._release_id = release_id
        self._engine_identity = engine_identity
        self._capacity = capacity
        self._wait_timeout_seconds = wait_timeout_seconds
        self._process_generation = process_generation or uuid4().hex
        self._lock = Lock()
        self._completed: OrderedDict[SharedIntelligenceKey, object] = OrderedDict()
        self._in_flight: dict[SharedIntelligenceKey, Future[object]] = {}
        self._evidence_generation = 0
        self._calculations_started = 0
        self._calculations_succeeded = 0
        self._calculations_failed = 0
        self._cache_hits = 0
        self._coalesced_waits = 0
        self._evictions = 0
        self._invalidations = 0
        self._wait_timeouts = 0

    def ranking(
        self,
        intelligence: _MarketIntelligence,
        *,
        goal: CareerGoal | str,
        as_of: date | datetime | None = None,
    ) -> ExplainableRankingReport:
        normalized_goal = CareerGoal(goal)
        normalized_as_of = _normalize_as_of(as_of)
        return cast(
            ExplainableRankingReport,
            self._get_or_compute(
                operation="ranking",
                goal=normalized_goal,
                as_of=normalized_as_of,
                factory=lambda: intelligence.ranking(
                    goal=normalized_goal,
                    as_of=normalized_as_of,
                ),
            ),
        )

    def platform_summary(
        self,
        intelligence: _MarketIntelligence,
        *,
        goal: CareerGoal | str = CareerGoal.SOFTWARE_ENGINEERING,
        as_of: date | datetime | None = None,
    ) -> PlatformMarketIntelligenceReport:
        normalized_goal = CareerGoal(goal)
        normalized_as_of = _normalize_as_of(as_of)
        return cast(
            PlatformMarketIntelligenceReport,
            self._get_or_compute(
                operation="platform_summary",
                goal=normalized_goal,
                as_of=normalized_as_of,
                factory=lambda: intelligence.platform_summary(
                    goal=normalized_goal,
                    as_of=normalized_as_of,
                ),
            ),
        )

    def invalidate(self) -> None:
        """Advance the evidence generation and discard completed entries."""

        with self._lock:
            self._evidence_generation += 1
            self._completed.clear()
            self._invalidations += 1

    def stats(self) -> SharedIntelligenceStats:
        with self._lock:
            return SharedIntelligenceStats(
                capacity=self._capacity,
                completed_entries=len(self._completed),
                in_flight_entries=len(self._in_flight),
                calculations_started=self._calculations_started,
                calculations_succeeded=self._calculations_succeeded,
                calculations_failed=self._calculations_failed,
                cache_hits=self._cache_hits,
                coalesced_waits=self._coalesced_waits,
                evictions=self._evictions,
                invalidations=self._invalidations,
                wait_timeouts=self._wait_timeouts,
            )

    def _get_or_compute(
        self,
        *,
        operation: str,
        goal: CareerGoal,
        as_of: date,
        factory: Callable[[], _T],
    ) -> _T:
        leader = False
        cached_result: object | None = None
        with self._lock:
            key = SharedIntelligenceKey(
                operation=operation,
                goal=goal.value,
                as_of=as_of,
                release_id=self._release_id,
                process_generation=self._process_generation,
                engine_identity=self._engine_identity,
                evidence_generation=self._evidence_generation,
            )
            cached = self._completed.get(key)
            if cached is not None:
                self._completed.move_to_end(key)
                self._cache_hits += 1
                cached_result = cached
            else:
                future = self._in_flight.get(key)
                if future is None:
                    future = Future()
                    self._in_flight[key] = future
                    self._calculations_started += 1
                    leader = True
                else:
                    self._coalesced_waits += 1

        if cached_result is not None:
            return cast(_T, deepcopy(cached_result))

        if not leader:
            try:
                return cast(
                    _T,
                    deepcopy(future.result(timeout=self._wait_timeout_seconds)),
                )
            except FutureTimeoutError as exc:
                with self._lock:
                    self._wait_timeouts += 1
                raise SharedIntelligenceWaitTimeout(
                    f"shared {operation} calculation exceeded the wait bound"
                ) from exc

        try:
            computed = factory()
            stored = deepcopy(computed)
            delivered = deepcopy(stored)
        except BaseException as exc:
            with self._lock:
                self._in_flight.pop(key, None)
                self._calculations_failed += 1
            future.set_exception(exc)
            raise

        with self._lock:
            self._in_flight.pop(key, None)
            self._calculations_succeeded += 1
            if key.evidence_generation == self._evidence_generation:
                self._completed[key] = stored
                self._completed.move_to_end(key)
                while len(self._completed) > self._capacity:
                    self._completed.popitem(last=False)
                    self._evictions += 1
        future.set_result(stored)
        return cast(_T, delivered)


def _normalize_as_of(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value
