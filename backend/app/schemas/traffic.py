from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LaneMetricsOut(BaseModel):
    lane_id: str
    vehicle_count: int
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


class SignalStateOut(BaseModel):
    intersection_id: str
    color: str
    active_direction: str
    target_direction: str | None
    countdown_s: float
    mode: str
    decision: SignalDecisionOut | None = None


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
    north: int = 10
    south: int = 10
    east: int = 10
    west: int = 10


class SimulationAmbulanceRequest(BaseModel):
    direction: str


class SimulationHelmetViolationRequest(BaseModel):
    direction: str
