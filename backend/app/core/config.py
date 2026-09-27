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

from pydantic import Field
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

    minimum_green_s: int = 10
    maximum_green_s: int = 60
    base_green_s: int = 15
    yellow_s: int = 3
    all_red_s: int = 2
    fixed_phase_s: int = 30  # per-direction duration when running FIXED mode


class FairnessConfig(BaseSettings):
    consecutive_priority_limit: int = 3


class DetectionConfig(BaseSettings):
    yolo_confidence: float = 0.45
    helmet_confidence: float = 0.55
    ambulance_confidence: float = 0.60
    # Frames a candidate ambulance must be seen in, above ambulance_confidence,
    # while approaching, before emergency priority is requested.
    ambulance_confirmation_frames: int = 8
    ambulance_confirmation_window_s: float = 4.0


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
    video_source: str = "./videos/sample_intersection.mp4"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    lane_thresholds: LaneThresholds = Field(default_factory=LaneThresholds)
    pressure_weights: PressureWeights = Field(default_factory=PressureWeights)
    signal_timings: SignalTimings = Field(default_factory=SignalTimings)
    fairness: FairnessConfig = Field(default_factory=FairnessConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()
