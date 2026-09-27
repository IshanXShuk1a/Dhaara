"""
AmbulanceAnalyzer

Bridges raw "ambulance"-class tracks (from Detector/Tracker) into
AmbulanceConfirmationTracker observations. Determines `approaching` from the
track's actual motion vector relative to the intersection center - a vehicle
classified "ambulance" that is moving away from the intersection is not
treated as an approach candidate, regardless of confidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.cv.tracker import Track
from app.services.cv.lane_assigner import LaneAssignment
from app.services.emergency.ambulance_confirmation import (
    AmbulanceConfirmationTracker,
    AmbulanceObservation,
    AmbulanceCandidate,
)


@dataclass(frozen=True)
class IntersectionCenter:
    x: float
    y: float


class AmbulanceAnalyzer:
    def __init__(self, confirmation_tracker: AmbulanceConfirmationTracker, intersection_center: IntersectionCenter):
        self._confirmation = confirmation_tracker
        self._center = intersection_center

    def is_approaching(self, track: Track) -> bool:
        vx, vy = track.velocity_px_per_frame()
        if vx == 0 and vy == 0:
            return False
        dist_now = self._distance(track.center)
        prev = track.previous_center or track.center
        dist_prev = self._distance(prev)
        return dist_now < dist_prev  # getting closer to the intersection center

    def _distance(self, point: tuple[float, float]) -> float:
        return ((point[0] - self._center.x) ** 2 + (point[1] - self._center.y) ** 2) ** 0.5

    def process(self, track: Track, lane_assignment: LaneAssignment, timestamp: float) -> AmbulanceCandidate | None:
        if track.class_name != "ambulance":
            return None
        observation = AmbulanceObservation(
            track_id=track.track_id,
            confidence=track.confidence,
            approaching=self.is_approaching(track),
            lane_id=lane_assignment.lane_id,
            direction=lane_assignment.direction,
            timestamp=timestamp,
        )
        return self._confirmation.observe(observation)
