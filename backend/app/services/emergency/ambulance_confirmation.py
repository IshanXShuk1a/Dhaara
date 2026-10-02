"""
AmbulanceConfirmationTracker

A single uncertain frame must never trigger emergency signal priority. This
module requires a candidate ambulance track to be seen consistently -
above `ambulance_confidence`, and assigned to a directional camera - for at
least `ambulance_confirmation_frames` observations within a rolling
`ambulance_confirmation_window_s` window before it is considered CONFIRMED.

Flow this module implements the first half of:

    AMBULANCE DETECTED -> TEMPORAL CONFIRMATION -> (caller) PRIORITY REQUEST -> ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.domain_config import DetectionConfig, DEFAULT_CONFIG


class ConfirmationState(str, Enum):
    CANDIDATE = "CANDIDATE"       # seen at least once, not yet enough evidence
    CONFIRMED = "CONFIRMED"       # met the temporal-confirmation bar
    LOST = "LOST"                 # candidate disappeared before confirmation


@dataclass
class AmbulanceObservation:
    track_id: int
    confidence: float
    approaching: bool
    lane_id: str
    direction: str | None
    timestamp: float


@dataclass
class AmbulanceCandidate:
    track_id: int
    observations: list[AmbulanceObservation] = field(default_factory=list)
    state: ConfirmationState = ConfirmationState.CANDIDATE

    @property
    def latest(self) -> AmbulanceObservation:
        return self.observations[-1]


class AmbulanceConfirmationTracker:
    def __init__(self, config: DetectionConfig = DEFAULT_CONFIG.detection):
        self._config = config
        self._candidates: dict[int, AmbulanceCandidate] = {}

    def observe(self, observation: AmbulanceObservation) -> AmbulanceCandidate:
        candidate = self._candidates.setdefault(
            observation.track_id, AmbulanceCandidate(track_id=observation.track_id)
        )
        candidate.observations.append(observation)

        window_start = observation.timestamp - self._config.ambulance_confirmation_window_s
        candidate.observations = [o for o in candidate.observations if o.timestamp >= window_start]

        qualifying = [
            o for o in candidate.observations
            if o.confidence >= self._config.ambulance_confidence and o.approaching
        ]

        if candidate.state != ConfirmationState.CONFIRMED:
            if len(qualifying) >= self._config.ambulance_confirmation_frames:
                candidate.state = ConfirmationState.CONFIRMED

        return candidate

    def mark_lost(self, track_id: int) -> None:
        if track_id in self._candidates and self._candidates[track_id].state != ConfirmationState.CONFIRMED:
            self._candidates[track_id].state = ConfirmationState.LOST

    def confirmed_candidates(self) -> list[AmbulanceCandidate]:
        return [c for c in self._candidates.values() if c.state == ConfirmationState.CONFIRMED]

    def get(self, track_id: int) -> AmbulanceCandidate | None:
        return self._candidates.get(track_id)

    def purge(self, track_id: int) -> None:
        self._candidates.pop(track_id, None)
