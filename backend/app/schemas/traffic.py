from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LaneMetricsOut(BaseModel):
    lane_id: str
    vehicle_count: int
    vehicle_score: float = 0.0
    vehicle_counts: dict[str, int] = Field(default_factory=dict)
    occupancy: float
    queue_length_m: float
    average_speed_kmph: float
    average_waiting_time_s: float
    flow_rate: float
    traffic_pressure: float
    status: str
    reasons: list[str]
    is_simulated: bool = False


class TrafficSnapshotOut(BaseModel):
    intersection_id: str
    timestamp: datetime
    lanes: dict[str, LaneMetricsOut]


class SignalDecisionOut(BaseModel):
    selected_direction: str
    green_duration_s: int
    reason: list[str]
    mode: str
    traffic_pressure: float
    queue_length_m: float
    waiting_time_s: float
    vehicle_count: int
    fairness_applied: bool
    pair_scores: dict[str, float | None] = Field(default_factory=dict)
    denser_pair: str | None = None
    score_difference: float | None = None
    action: str = "HOLD"


class SignalStateOut(BaseModel):
    directions: dict[str, str] = Field(default_factory=dict)
    intersection_id: str
    color: str
    active_direction: str
    target_direction: str | None
    countdown_s: float
    mode: str
    decision: SignalDecisionOut | None = None
    previous_phase: str | None = None
    full_phase_required: bool = False


class SignalModeRequest(BaseModel):
    mode: str  # FIXED|ADAPTIVE|MANUAL


class SignalOverrideRequest(BaseModel):
    direction: str
    operator_note: str = ""


class EmergencyEventOut(BaseModel):
    intersection_id: str
    ambulance_track_id: int
    lane_id: str
    direction: str | None
    confidence: float
    state: str
    created_at: datetime

    class Config:
        from_attributes = True


class SafetyEventOut(BaseModel):
    intersection_id: str
    event_type: str
    lane_id: str
    track_id: int
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class SafetySummaryOut(BaseModel):
    intersection_id: str
    compliant_count: int
    violation_count: int
    compliance_rate: float | None  # None -> dashboard must show N/A, not a fabricated %


class SystemEventOut(BaseModel):
    intersection_id: str | None
    event_type: str
    message: str
    severity: str
    timestamp: datetime

    class Config:
        from_attributes = True


class SimulationSliderRequest(BaseModel):
    north: int = Field(10, ge=0, le=30)
    south: int = Field(10, ge=0, le=30)
    east: int = Field(10, ge=0, le=30)
    west: int = Field(10, ge=0, le=30)


class SimulationAmbulanceRequest(BaseModel):
    direction: Literal["NORTH", "SOUTH", "EAST", "WEST"]
    lights_active: bool = True


class SimulationHelmetViolationRequest(BaseModel):
    direction: Literal["NORTH", "SOUTH", "EAST", "WEST"]


class SimulationScenarioRequest(BaseModel):
    scenario: Literal["balanced", "ns_busy", "ew_busy", "empty_ew", "empty_ns"]


class SimulationControlRequest(BaseModel):
    paused: bool | None = None
    speed: Literal[1, 2, 5, 10] | None = None
