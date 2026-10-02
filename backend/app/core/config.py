"""
DHAARA central configuration.

Every threshold, weight, and timing constant used by the traffic-intelligence
and signal-control logic is defined here and can be overridden via environment
variables (see .env.example). No module outside this file should hard-code a
traffic-classification threshold, a pressure weight, or a signal timing value.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LaneThresholds(BaseSettings):
    """Traffic-pressure score (0-100) boundaries for each lane status bucket.

    These are configurable engineering defaults chosen to give a readable
    demo spread, not a claim of a universally correct traffic-engineering
    standard. Operators are expected to tune them per deployment.
    """

    free_max: float = 20.0
    low_max: float = 40.0
    moderate_max: float = 60.0
    high_max: float = 80.0
    # anything above high_max is CONGESTED


class PressureWeights(BaseSettings):
    """Weights for the traffic-pressure formula.

    pressure = w_occupancy * occupancy
             + w_queue * normalized_queue
             + w_count * normalized_vehicle_count
             + w_wait * normalized_waiting_time
             - w_speed * normalized_speed

    All inputs are normalized to [0, 1] before weighting, and the final
    pressure score is clamped to [0, 100].
    """

    w_occupancy: float = 30.0
    w_queue: float = 25.0
    w_count: float = 15.0
    w_wait: float = 20.0
    w_speed: float = 10.0

    # Normalization reference values (the value that maps input -> 1.0)
    max_queue_m: float = 60.0
    max_vehicle_count: float = 40.0
    max_waiting_time_s: float = 90.0
    free_flow_speed_kmph: float = 45.0


class SignalTimings(BaseSettings):
    """Signal state-machine timing configuration, in seconds."""

    fixed_phase_s: int = Field(70, gt=0)
    yellow_s: float = Field(3.0, gt=0, allow_inf_nan=False)
    score_difference_threshold: float = Field(20, gt=0)
    empty_score_max: float = Field(5, ge=0)
    early_switch_min_remaining_s: float = Field(20, ge=0)
    empty_persistence_s: float = Field(3, gt=0)


class DetectionConfig(BaseSettings):
    yolo_confidence: float = Field(0.45, ge=0, le=1)
    helmet_confidence: float = Field(0.55, ge=0, le=1)
    ambulance_confidence: float = Field(0.60, ge=0, le=1)
    # Frames a candidate ambulance must be seen in, above ambulance_confidence,
    # while approaching, before emergency priority is requested.
    ambulance_confirmation_frames: int = Field(8, ge=1)
    ambulance_confirmation_window_s: float = Field(4.0, gt=0)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    app_name: str = "DHAARA"
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./dhaara.db"

    model_path: str = "./models_store/yolov8n.pt"
    east_video: str = "./videos/east.mp4"
    west_video: str = "./videos/west.mp4"
    north_video: str = "./videos/north.mp4"
    south_video: str = "./videos/south.mp4"
    east_roi: list[list[float]] = Field(default_factory=lambda: [[.35, .2], [.65, .2], [.9, .9], [.1, .9]])
    west_roi: list[list[float]] = Field(default_factory=lambda: [[.35, .2], [.65, .2], [.9, .9], [.1, .9]])
    north_roi: list[list[float]] = Field(default_factory=lambda: [[.35, .2], [.65, .2], [.9, .9], [.1, .9]])
    south_roi: list[list[float]] = Field(default_factory=lambda: [[.35, .2], [.65, .2], [.9, .9], [.1, .9]])

    @field_validator("east_roi", "west_roi", "north_roi", "south_roi")
    @classmethod
    def validate_roi(cls, value):
        from app.services.cv.lane_assigner import validate_normalized_roi
        return [list(p) for p in validate_normalized_roi(value)]

    @model_validator(mode="after")
    def independent_inputs(self):
        from pathlib import Path
        backend_dir = Path(__file__).resolve().parents[2]
        paths = []
        for d in ("east", "west", "north", "south"):
            value = getattr(self, f"{d}_video")
            if not value.strip():
                raise ValueError(f"{d.upper()}_VIDEO must specify a video path")
            path = Path(value)
            paths.append(str((path if path.is_absolute() else backend_dir / path).resolve()).casefold())
        if len(set(paths)) != 4:
            raise ValueError("East, West, North and South must use four independent video paths")
        return self

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    lane_thresholds: LaneThresholds = Field(default_factory=LaneThresholds)
    pressure_weights: PressureWeights = Field(default_factory=PressureWeights)
    signal_timings: SignalTimings = Field(default_factory=SignalTimings)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()
