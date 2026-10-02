"""
LaneIntelligenceEngine

Turns raw per-vehicle tracking state (positions, speeds, dwell times) for a
single lane into the metrics DHAARA's decision engine and dashboard rely on:

    vehicle_count, occupancy, queue_length_m, average_speed_kmph,
    average_waiting_time_s, flow_rate, traffic_pressure, status

`status` is derived purely from `traffic_pressure` against configurable
thresholds (LaneThresholds) - never set directly or randomly.

This module has no dependency on OpenCV, FastAPI, or the database: it is a
pure function of the `TrackedVehicleSnapshot` list it is given, which makes
it independently unit-testable (see app/tests/test_lane_intelligence.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.domain_config import DomainConfig, LaneThresholds, PressureWeights, DEFAULT_CONFIG


class LaneStatus(str, Enum):
    FREE = "FREE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CONGESTED = "CONGESTED"


@dataclass(frozen=True)
class TrackedVehicleSnapshot:
    """The minimal per-vehicle facts the lane-intelligence calc needs.

    Produced by the Tracker + LaneAssigner for every vehicle currently
    assigned to a given lane, at the moment a lane snapshot is computed.
    """

    track_id: int
    speed_kmph: float
    waiting_time_s: float
    is_stopped: bool  # speed below a near-zero threshold -> counts toward queue


@dataclass(frozen=True)
class LaneGeometry:
    """A lane's configured capacity, used to compute occupancy/queue length.

    `length_m` and `capacity_vehicles` are configuration (from the lane's
    polygon geometry + real-world calibration), not measurements.
    """

    lane_id: str
    length_m: float = 9.144
    capacity_vehicles: int = 25
    # meters of roadway a single queued vehicle is assumed to occupy
    vehicle_spacing_m: float = 7.0


@dataclass(frozen=True)
class LaneMetrics:
    lane_id: str
    vehicle_count: int
    occupancy: float  # 0-1
    queue_length_m: float
    average_speed_kmph: float
    average_waiting_time_s: float
    flow_rate: float  # vehicles/minute estimate
    traffic_pressure: float  # 0-100
    status: LaneStatus
    reasons: list[str]  # human-readable supporting factors, for explainability
    vehicle_score: float = 0.0
    vehicle_counts: dict[str, int] = field(default_factory=dict)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def classify_status(pressure: float, thresholds: LaneThresholds) -> LaneStatus:
    """Pure threshold classification. Never randomized, never hard-coded per-lane."""
    if pressure <= thresholds.free_max:
        return LaneStatus.FREE
    if pressure <= thresholds.low_max:
        return LaneStatus.LOW
    if pressure <= thresholds.moderate_max:
        return LaneStatus.MODERATE
    if pressure <= thresholds.high_max:
        return LaneStatus.HIGH
    return LaneStatus.CONGESTED


def compute_traffic_pressure(
    occupancy: float,
    queue_length_m: float,
    vehicle_count: int,
    average_waiting_time_s: float,
    average_speed_kmph: float,
    weights: PressureWeights,
) -> float:
    """Weighted-factor pressure score in [0, 100]. See module docstring formula."""
    normalized_queue = _clamp(queue_length_m / weights.max_queue_m) if weights.max_queue_m > 0 else 0.0
    normalized_count = _clamp(vehicle_count / weights.max_vehicle_count) if weights.max_vehicle_count > 0 else 0.0
    normalized_wait = _clamp(average_waiting_time_s / weights.max_waiting_time_s) if weights.max_waiting_time_s > 0 else 0.0
    normalized_speed = _clamp(average_speed_kmph / weights.free_flow_speed_kmph) if weights.free_flow_speed_kmph > 0 else 0.0

    raw = (
        weights.w_occupancy * _clamp(occupancy)
        + weights.w_queue * normalized_queue
        + weights.w_count * normalized_count
        + weights.w_wait * normalized_wait
        - weights.w_speed * normalized_speed
    )
    return round(_clamp(raw, 0.0, 100.0), 2)


class LaneIntelligenceEngine:
    """Stateless calculator: one call per lane per traffic snapshot."""

    def __init__(self, config: DomainConfig = DEFAULT_CONFIG):
        self._config = config

    def compute(
        self,
        geometry: LaneGeometry,
        vehicles: list[TrackedVehicleSnapshot],
        window_seconds: float = 60.0,
    ) -> LaneMetrics:
        vehicle_count = len(vehicles)

        if vehicle_count == 0:
            metrics = LaneMetrics(
                lane_id=geometry.lane_id,
                vehicle_count=0,
                occupancy=0.0,
                queue_length_m=0.0,
                average_speed_kmph=self._config.pressure_weights.free_flow_speed_kmph,
                average_waiting_time_s=0.0,
                flow_rate=0.0,
                traffic_pressure=0.0,
                status=LaneStatus.FREE,
                reasons=["No vehicles currently tracked in this lane"],
            )
            return metrics

        occupancy = _clamp(vehicle_count / geometry.capacity_vehicles) if geometry.capacity_vehicles > 0 else 0.0

        queued = [v for v in vehicles if v.is_stopped]
        queue_length_m = min(len(queued) * geometry.vehicle_spacing_m, geometry.length_m)

        average_speed_kmph = sum(v.speed_kmph for v in vehicles) / vehicle_count
        average_waiting_time_s = sum(v.waiting_time_s for v in vehicles) / vehicle_count

        # Flow rate: vehicles per minute, estimated from count / window.
        flow_rate = round((vehicle_count / window_seconds) * 60.0, 2) if window_seconds > 0 else 0.0

        pressure = compute_traffic_pressure(
            occupancy=occupancy,
            queue_length_m=queue_length_m,
            vehicle_count=vehicle_count,
            average_waiting_time_s=average_waiting_time_s,
            average_speed_kmph=average_speed_kmph,
            weights=self._config.pressure_weights,
        )
        status = classify_status(pressure, self._config.lane_thresholds)

        reasons = self._build_reasons(vehicle_count, occupancy, queue_length_m, average_waiting_time_s, average_speed_kmph)

        return LaneMetrics(
            lane_id=geometry.lane_id,
            vehicle_count=vehicle_count,
            occupancy=round(occupancy, 3),
            queue_length_m=round(queue_length_m, 1),
            average_speed_kmph=round(average_speed_kmph, 1),
            average_waiting_time_s=round(average_waiting_time_s, 1),
            flow_rate=flow_rate,
            traffic_pressure=pressure,
            status=status,
            reasons=reasons,
        )

    @staticmethod
    def _build_reasons(
        vehicle_count: int,
        occupancy: float,
        queue_length_m: float,
        average_waiting_time_s: float,
        average_speed_kmph: float,
    ) -> list[str]:
        reasons: list[str] = [f"{vehicle_count} vehicles tracked"]
        if occupancy > 0.5:
            reasons.append(f"high occupancy ({occupancy * 100:.0f}%)")
        if queue_length_m > 10:
            reasons.append(f"queue of {queue_length_m:.0f}m")
        if average_waiting_time_s > 15:
            reasons.append(f"average wait {average_waiting_time_s:.0f}s")
        if average_speed_kmph < 15:
            reasons.append(f"slow average speed ({average_speed_kmph:.0f} km/h)")
        return reasons
