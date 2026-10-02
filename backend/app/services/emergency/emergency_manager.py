"""
EmergencyManager

Owns the emergency-priority lifecycle for one intersection:

    NONE -> DETECTED -> CONFIRMED -> PRIORITY_REQUESTED -> PRIORITY_ACTIVE
         -> PASSED -> RESOLVED -> (back to) NONE

Priority is requested by the controller only after ambulance identity and
temporal flashing-light evidence have both been confirmed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.emergency.ambulance_confirmation import AmbulanceCandidate


class EmergencyState(str, Enum):
    NONE = "NONE"
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    PRIORITY_REQUESTED = "PRIORITY_REQUESTED"
    PRIORITY_ACTIVE = "PRIORITY_ACTIVE"
    PASSED = "PASSED"
    RESOLVED = "RESOLVED"


@dataclass
class EmergencyEvent:
    ambulance_track_id: int
    lane_id: str
    direction: str | None
    confidence: float
    state: EmergencyState
    timestamp: float


@dataclass
class EmergencyManager:
    state: EmergencyState = EmergencyState.NONE
    active_track_id: int | None = None
    active_direction: str | None = None
    active_lane_id: str | None = None
    events: list[EmergencyEvent] = field(default_factory=list)
    # frames/ticks the ambulance has not been re-observed while PRIORITY_ACTIVE,
    # used to decide it has passed through the intersection.
    _missed_ticks: int = 0
    clear_after_missed_ticks: int = 5

    @property
    def emergency_direction(self) -> str | None:
        """Direction of the confirmed emergency, for telemetry."""
        if self.state in (EmergencyState.PRIORITY_REQUESTED, EmergencyState.PRIORITY_ACTIVE):
            return self.active_direction
        return None

    def on_candidate_detected(self, candidate: AmbulanceCandidate, timestamp: float) -> None:
        if self.state == EmergencyState.NONE:
            self.state = EmergencyState.DETECTED
            self._log(candidate, timestamp)

    def on_candidate_confirmed(self, candidate: AmbulanceCandidate, timestamp: float) -> None:
        if self.active_track_id is not None and self.active_track_id != candidate.track_id:
            return  # an emergency is already being handled; ignore other candidates
        if self.state in (EmergencyState.NONE, EmergencyState.DETECTED):
            self.state = EmergencyState.CONFIRMED
            self.active_track_id = candidate.track_id
            self.active_lane_id = candidate.latest.lane_id
            self.active_direction = candidate.latest.direction
            self._log(candidate, timestamp)

    def request_priority(self, timestamp: float) -> None:
        if self.state == EmergencyState.CONFIRMED:
            self.state = EmergencyState.PRIORITY_REQUESTED
            self._log(None, timestamp)

    def mark_priority_active(self, timestamp: float) -> None:
        """Call once the SignalFSM has safely reached GREEN for active_direction."""
        if self.state == EmergencyState.PRIORITY_REQUESTED:
            self.state = EmergencyState.PRIORITY_ACTIVE
            self._missed_ticks = 0
            self._log(None, timestamp)

    def observe_tick(self, still_present: bool, timestamp: float) -> None:
        """Call once per control loop tick while PRIORITY_ACTIVE with whether the
        ambulance track is still being observed near/through the intersection."""
        if self.state not in (EmergencyState.PRIORITY_ACTIVE, EmergencyState.PRIORITY_REQUESTED):
            return
        if still_present:
            self._missed_ticks = 0
        else:
            self._missed_ticks += 1
            if self._missed_ticks >= self.clear_after_missed_ticks:
                self.state = EmergencyState.PASSED
                self._log(None, timestamp)

    def resolve(self, timestamp: float) -> None:
        if self.state == EmergencyState.PASSED:
            self.state = EmergencyState.RESOLVED
            self._log(None, timestamp)
            self.state = EmergencyState.NONE
            self.active_track_id = None
            self.active_direction = None
            self.active_lane_id = None

    def _log(self, candidate: AmbulanceCandidate | None, timestamp: float) -> None:
        self.events.append(
            EmergencyEvent(
                ambulance_track_id=self.active_track_id if self.active_track_id is not None else (
                    candidate.track_id if candidate else -1
                ),
                lane_id=self.active_lane_id or (candidate.latest.lane_id if candidate else ""),
                direction=self.active_direction or (candidate.latest.direction if candidate else None),
                confidence=candidate.latest.confidence if candidate else 0.0,
                state=self.state,
                timestamp=timestamp,
            )
        )
