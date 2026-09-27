"""
Framework-free configuration for DHAARA's domain/business logic.

Deliberately has ZERO third-party dependencies (stdlib `dataclasses` only) so
that lane intelligence, the signal FSM, the decision engine, fairness,
tracking, lane assignment, and emergency logic can be imported and unit
tested without FastAPI, Pydantic, or SQLAlchemy installed.

`app/core/config.py` (the Pydantic `Settings`, used by the API layer) builds
its nested settings with the same field names/values as here; the API layer
converts a `Settings` object into these dataclasses via `from_settings()`
helpers so there is exactly one source of truth for each number.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LaneThresholds:
    """Traffic-pressure score (0-100) boundaries for each lane status bucket."""

    free_max: float = 20.0
    low_max: float = 40.0
    moderate_max: float = 60.0
    high_max: float = 80.0


@dataclass(frozen=True)
class PressureWeights:
    w_occupancy: float = 30.0
    w_queue: float = 25.0
    w_count: float = 15.0
    w_wait: float = 20.0
    w_speed: float = 10.0

    max_queue_m: float = 60.0
    max_vehicle_count: float = 40.0
    max_waiting_time_s: float = 90.0
    free_flow_speed_kmph: float = 45.0


@dataclass(frozen=True)
class SignalTimings:
    minimum_green_s: int = 10
    maximum_green_s: int = 60
    base_green_s: int = 15
    yellow_s: int = 3
    all_red_s: int = 2
    fixed_phase_s: int = 30


@dataclass(frozen=True)
class FairnessConfig:
    consecutive_priority_limit: int = 3


@dataclass(frozen=True)
class DetectionConfig:
    yolo_confidence: float = 0.45
    helmet_confidence: float = 0.55
    ambulance_confidence: float = 0.60
    ambulance_confirmation_frames: int = 8
    ambulance_confirmation_window_s: float = 4.0


@dataclass(frozen=True)
class DomainConfig:
    """Bundles every configurable domain parameter DHAARA's logic needs."""

    lane_thresholds: LaneThresholds = field(default_factory=LaneThresholds)
    pressure_weights: PressureWeights = field(default_factory=PressureWeights)
    signal_timings: SignalTimings = field(default_factory=SignalTimings)
    fairness: FairnessConfig = field(default_factory=FairnessConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)


DEFAULT_CONFIG = DomainConfig()
