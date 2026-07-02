"""Conservative predictive signals over Layer 18A historical evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    CompanyRegionSnapshot,
    HistoricalObservation,
    MarketSnapshot,
    PredictiveSignal,
    SignalInput,
)
from backend.platform_intelligence.schemas import (
    ConfidenceLevel,
    HistoricalTargetType,
    PredictiveSignalCreate,
    PredictiveSignalStatus,
    PredictiveSignalSummary,
    PredictiveSignalType,
    RegionSignalsSummary,
    SignalInputCreate,
    SignalStrength,
)

MIN_ACTIVE_SNAPSHOT_COUNT = 3
MODERATE_SNAPSHOT_COUNT = 6
STRONG_SNAPSHOT_COUNT = 12
SIGNAL_EXPIRY_DAYS = 120


class PredictiveSignalService:
    def __init__(self, repository: HistoryRepository) -> None:
        self._repo = repository

    def create_signal(self, request: PredictiveSignalCreate) -> PredictiveSignal:
        created_at = request.created_at or datetime.now(UTC)
        row = PredictiveSignal(
            predictive_signal_id=request.predictive_signal_id or _new_id("signal"),
            signal_type=request.signal_type.value,
            target_type=request.target_type.value,
            target_id=request.target_id,
            region_id=request.region_id,
            signal_strength=request.signal_strength.value,
            confidence_level=request.confidence_level.value,
            evidence_window_start=request.evidence_window_start,
            evidence_window_end=request.evidence_window_end,
            snapshot_count=request.snapshot_count,
            minimum_snapshot_count_met=request.minimum_snapshot_count_met,
            summary=request.summary,
            warnings=list(request.warnings),
            status=request.status.value,
            created_at=created_at,
            expires_at=request.expires_at,
        )
        self._repo.add_predictive_signal(row)
        self._repo.flush()
        for signal_input in request.inputs:
            self._repo.add_signal_input(
                SignalInput(
                    signal_input_id=_new_id("signal_input"),
                    predictive_signal_id=row.predictive_signal_id,
                    source_snapshot_id=signal_input.source_snapshot_id,
                    historical_observation_id=signal_input.historical_observation_id,
                    input_type=signal_input.input_type,
                    input_weight=signal_input.input_weight,
                    contribution_strength=signal_input.contribution_strength,
                    created_at=created_at,
                )
            )
        self._repo.flush()
        return row

    def generate_region_signals(
        self,
        region_id: str,
        *,
        created_at: datetime | None = None,
    ) -> tuple[PredictiveSignal, ...]:
        created_at = created_at or datetime.now(UTC)
        market_snapshots = self._repo.list_market_snapshots(region_id, limit=500)
        observations = self._repo.list_region_observations(region_id, limit=500)
        company_snapshots = self._repo.list_company_region_snapshots_for_region(
            region_id,
            limit=1_000,
        )

        requests: list[PredictiveSignalCreate] = []
        requests.extend(
            _market_signal_requests(
                region_id=region_id,
                market_snapshots=market_snapshots,
                observations=observations,
                created_at=created_at,
            )
        )
        company_signal = _company_expansion_signal_request(
            region_id=region_id,
            company_snapshots=company_snapshots,
            observations=observations,
            created_at=created_at,
        )
        if company_signal is not None:
            requests.append(company_signal)

        return tuple(self.create_signal(request) for request in requests)

    def active_region_signals(
        self,
        region_id: str,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> RegionSignalsSummary:
        now = now or datetime.now(UTC)
        rows = self._repo.list_active_region_signals(region_id, now=now, limit=limit)
        return RegionSignalsSummary(
            region_id=region_id,
            signals=tuple(_signal_summary(row) for row in rows),
        )


def _market_signal_requests(
    *,
    region_id: str,
    market_snapshots: Sequence[MarketSnapshot],
    observations: Sequence[HistoricalObservation],
    created_at: datetime,
) -> tuple[PredictiveSignalCreate, ...]:
    if len(market_snapshots) < 2:
        return ()
    first = market_snapshots[0]
    latest = market_snapshots[-1]
    requests: list[PredictiveSignalCreate] = []

    overall_delta = _delta(first.overall_score, latest.overall_score)
    if overall_delta is not None and abs(overall_delta) >= 0.05:
        signal_type = (
            PredictiveSignalType.EMERGING_MARKET
            if overall_delta > 0
            else PredictiveSignalType.DECLINING_MARKET
        )
        summary = (
            "Emerging market signal based on improving historical market snapshots."
            if overall_delta > 0
            else "Declining market signal based on weakening historical market snapshots."
        )
        requests.append(
            _signal_request(
                signal_type=signal_type,
                region_id=region_id,
                snapshots=market_snapshots,
                observations=_matching_observations(
                    observations,
                    {
                        "regional_score_increased",
                        "regional_score_decreased",
                    },
                ),
                summary=summary,
                created_at=created_at,
                contribution_strength=abs(overall_delta),
            )
        )

    entry_delta = _delta(first.entry_level_access_score, latest.entry_level_access_score)
    if entry_delta is not None and abs(entry_delta) >= 0.05:
        direction = "improving" if entry_delta > 0 else "softening"
        requests.append(
            _signal_request(
                signal_type=PredictiveSignalType.ENTRY_LEVEL_ACCESS_TREND,
                region_id=region_id,
                snapshots=market_snapshots,
                observations=_matching_observations(
                    observations,
                    {
                        "entry_level_access_improved",
                        "entry_level_access_declined",
                    },
                ),
                summary=(
                    f"Entry-level access trend signal shows {direction} "
                    "historical access conditions."
                ),
                created_at=created_at,
                contribution_strength=abs(entry_delta),
            )
        )

    internship_delta = _delta(
        first.internship_density_score,
        latest.internship_density_score,
    )
    if internship_delta is not None and abs(internship_delta) >= 0.05:
        requests.append(
            _signal_request(
                signal_type=PredictiveSignalType.SEASONAL_HIRING_WINDOW,
                region_id=region_id,
                snapshots=market_snapshots,
                observations=_matching_observations(
                    observations,
                    {"internship_density_changed"},
                ),
                summary=(
                    "Seasonal hiring window candidate based on internship-density "
                    "movement across the evidence window."
                ),
                created_at=created_at,
                contribution_strength=abs(internship_delta),
            )
        )
    return tuple(requests)


def _company_expansion_signal_request(
    *,
    region_id: str,
    company_snapshots: Sequence[CompanyRegionSnapshot],
    observations: Sequence[HistoricalObservation],
    created_at: datetime,
) -> PredictiveSignalCreate | None:
    if len(company_snapshots) < 2:
        return None
    grouped: dict[str, list[CompanyRegionSnapshot]] = defaultdict(list)
    for snapshot in company_snapshots:
        grouped[snapshot.company_id].append(snapshot)

    expanding_company_count = 0
    expansion_inputs: list[CompanyRegionSnapshot] = []
    for snapshots in grouped.values():
        ordered = sorted(snapshots, key=lambda row: (row.snapshot_date, row.created_at))
        if len(ordered) < 2:
            continue
        if _company_expansion_delta(ordered[0], ordered[-1]) >= 0.05:
            expanding_company_count += 1
            expansion_inputs.extend((ordered[0], ordered[-1]))

    if expanding_company_count == 0:
        return None

    start = min(snapshot.snapshot_date for snapshot in company_snapshots)
    end = max(snapshot.snapshot_date for snapshot in company_snapshots)
    snapshot_count = len(company_snapshots)
    return _build_signal_request(
        signal_type=PredictiveSignalType.COMPANY_EXPANSION_SIGNAL,
        region_id=region_id,
        evidence_window_start=start,
        evidence_window_end=end,
        snapshot_count=snapshot_count,
        confidence_score=None,
        snapshot_inputs=tuple(_company_snapshot_id(row) for row in expansion_inputs),
        observations=_matching_observations(
            observations,
            {
                "company_presence_increased",
                "hiring_activity_increased",
            },
        ),
        summary=(
            "Company expansion signal based on improving company-region presence "
            "or hiring snapshots."
        ),
        created_at=created_at,
        contribution_strength=float(expanding_company_count),
    )


def _signal_request(
    *,
    signal_type: PredictiveSignalType,
    region_id: str,
    snapshots: Sequence[MarketSnapshot],
    observations: Sequence[HistoricalObservation],
    summary: str,
    created_at: datetime,
    contribution_strength: float,
) -> PredictiveSignalCreate:
    return _build_signal_request(
        signal_type=signal_type,
        region_id=region_id,
        evidence_window_start=snapshots[0].snapshot_date,
        evidence_window_end=snapshots[-1].snapshot_date,
        snapshot_count=len(snapshots),
        confidence_score=_average_confidence(snapshots),
        snapshot_inputs=tuple(row.market_snapshot_id for row in snapshots),
        observations=observations,
        summary=summary,
        created_at=created_at,
        contribution_strength=contribution_strength,
    )


def _build_signal_request(
    *,
    signal_type: PredictiveSignalType,
    region_id: str,
    evidence_window_start: date,
    evidence_window_end: date,
    snapshot_count: int,
    confidence_score: float | None,
    snapshot_inputs: Sequence[str],
    observations: Sequence[HistoricalObservation],
    summary: str,
    created_at: datetime,
    contribution_strength: float,
) -> PredictiveSignalCreate:
    minimum_met = snapshot_count >= MIN_ACTIVE_SNAPSHOT_COUNT
    warnings = _warnings_for_snapshot_count(snapshot_count)
    status = (
        PredictiveSignalStatus.ACTIVE
        if minimum_met
        else PredictiveSignalStatus.CANDIDATE
    )
    inputs = [
        SignalInputCreate(
            source_snapshot_id=snapshot_id,
            input_type="historical_snapshot",
            input_weight=1.0,
            contribution_strength=contribution_strength,
        )
        for snapshot_id in snapshot_inputs
    ]
    inputs.extend(
        SignalInputCreate(
            historical_observation_id=observation.historical_observation_id,
            input_type=observation.observation_type,
            input_weight=1.0,
            contribution_strength=observation.delta_value,
        )
        for observation in observations
    )
    return PredictiveSignalCreate(
        signal_type=signal_type,
        target_type=HistoricalTargetType.REGION,
        target_id=region_id,
        region_id=region_id,
        signal_strength=_strength_for_snapshot_count(snapshot_count),
        confidence_level=_confidence_level(snapshot_count, confidence_score),
        evidence_window_start=evidence_window_start,
        evidence_window_end=evidence_window_end,
        snapshot_count=snapshot_count,
        minimum_snapshot_count_met=minimum_met,
        summary=summary,
        warnings=warnings,
        status=status,
        created_at=created_at,
        expires_at=created_at + timedelta(days=SIGNAL_EXPIRY_DAYS),
        inputs=tuple(inputs),
    )


def _warnings_for_snapshot_count(snapshot_count: int) -> tuple[str, ...]:
    warnings: list[str] = []
    if snapshot_count < MIN_ACTIVE_SNAPSHOT_COUNT:
        warnings.append("minimum_snapshot_count_not_met")
    if snapshot_count < MODERATE_SNAPSHOT_COUNT:
        warnings.append("thin_historical_evidence_window")
    return tuple(warnings)


def _strength_for_snapshot_count(snapshot_count: int) -> SignalStrength:
    if snapshot_count >= STRONG_SNAPSHOT_COUNT:
        return SignalStrength.STRONG
    if snapshot_count >= MODERATE_SNAPSHOT_COUNT:
        return SignalStrength.MODERATE
    return SignalStrength.WEAK


def _confidence_level(
    snapshot_count: int,
    confidence_score: float | None,
) -> ConfidenceLevel:
    if confidence_score is None:
        return ConfidenceLevel.UNKNOWN
    if snapshot_count >= STRONG_SNAPSHOT_COUNT and confidence_score >= 0.75:
        return ConfidenceLevel.HIGH
    if snapshot_count >= MODERATE_SNAPSHOT_COUNT and confidence_score >= 0.5:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _average_confidence(snapshots: Sequence[MarketSnapshot]) -> float | None:
    values = [row.confidence_score for row in snapshots if row.confidence_score is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _delta(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None:
        return None
    return current - previous


def _matching_observations(
    observations: Iterable[HistoricalObservation],
    observation_types: set[str],
) -> tuple[HistoricalObservation, ...]:
    return tuple(
        observation
        for observation in observations
        if observation.observation_type in observation_types
    )


def _company_expansion_delta(
    previous: CompanyRegionSnapshot,
    current: CompanyRegionSnapshot,
) -> float:
    deltas = [
        value
        for value in (
            _delta(previous.company_presence_score, current.company_presence_score),
            _delta(previous.hiring_activity_score, current.hiring_activity_score),
            _count_delta(previous.active_posting_count, current.active_posting_count),
        )
        if value is not None
    ]
    return max(deltas) if deltas else 0.0


def _count_delta(previous: int | None, current: int | None) -> float | None:
    if previous is None or current is None:
        return None
    return (current - previous) / 20


def _company_snapshot_id(snapshot: CompanyRegionSnapshot) -> str:
    return snapshot.company_region_snapshot_id


def _signal_summary(row: PredictiveSignal) -> PredictiveSignalSummary:
    return PredictiveSignalSummary(
        signal_id=row.predictive_signal_id,
        signal_type=row.signal_type,
        target_type=row.target_type,
        target_id=row.target_id,
        region_id=row.region_id,
        signal_strength=row.signal_strength,
        confidence_level=row.confidence_level,
        evidence_window_start=row.evidence_window_start,
        evidence_window_end=row.evidence_window_end,
        snapshot_count=row.snapshot_count,
        minimum_snapshot_count_met=row.minimum_snapshot_count_met,
        summary=row.summary,
        warnings=tuple(row.warnings or ()),
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
