"""
LaneAssigner

Assigns each tracked vehicle to a configured lane polygon by testing whether
the vehicle's bbox center falls inside that lane's region-of-interest (ROI).
Vehicles that fall inside no configured polygon are assigned "UNKNOWN" -
never guessed into a random lane.

Also derives per-vehicle speed (km/h) and waiting time (s) from the track's
recent pixel-position history, using a configurable pixels-per-meter
calibration and the pipeline's known frame rate. This lets
LaneIntelligenceEngine work from real per-vehicle motion rather than
fabricated numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.cv.tracker import Track

Point = tuple[float, float]
DIRECTIONS = ("EAST", "WEST", "NORTH", "SOUTH")
# far-left, far-right, near-right, near-left; edges are the four boundaries.
DEFAULT_ROI = ((0.35, 0.20), (0.65, 0.20), (0.90, 0.90), (0.10, 0.90))


def validate_normalized_roi(polygon) -> list[Point]:
    if len(polygon) != 4 or any(len(p) != 2 for p in polygon):
        raise ValueError("ROI must have four ordered [x, y] vertices")
    points = [tuple(float(v) for v in p) for p in polygon]
    if any(not 0 <= v <= 1 for p in points for v in p):
        raise ValueError("ROI coordinates must be finite numbers between 0 and 1")
    turns = []
    for i in range(4):
        a, b, c = points[i], points[(i + 1) % 4], points[(i + 2) % 4]
        turns.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if not (all(t > 1e-9 for t in turns) or all(t < -1e-9 for t in turns)):
        raise ValueError("ROI must be a non-degenerate convex quadrilateral in boundary order")
    return points


def camera_lane(direction: str, width: int, height: int, roi=DEFAULT_ROI, pixels_per_meter: float = 8.0) -> LanePolygon:
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown camera direction: {direction}")
    points = validate_normalized_roi(roi)
    return LanePolygon(direction, direction, [(x * width, y * height) for x, y in points], pixels_per_meter)


@dataclass(frozen=True)
class LanePolygon:
    """Configured lane ROI. Stored in the database/config, not hard-coded in the frontend."""

    lane_id: str
    direction: str
    polygon: list[Point]  # ordered vertices, image pixel coordinates
    pixels_per_meter: float = 8.0
    # speed (px/frame) below this is considered "stopped", for queue/wait calc
    stopped_speed_px_per_frame: float = 1.5


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Ray casting, including points on a boundary."""
    if len(polygon) < 3:
        return False
    x, y = point
    n = len(polygon)
    inside = False
    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-7 and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2):
            return True
        if y > min(y1, y2):
            if y <= max(y1, y2):
                if x <= max(x1, x2):
                    if y1 != y2:
                        x_intersect = (y - y1) * (x2 - x1) / (y2 - y1) + x1
                    else:
                        x_intersect = x1
                    if x1 == x2 or x <= x_intersect:
                        inside = not inside
        x1, y1 = x2, y2
    return inside


UNKNOWN_LANE = "UNKNOWN"


@dataclass
class LaneAssignment:
    track_id: int
    lane_id: str
    direction: str | None
    speed_kmph: float
    waiting_time_s: float
    is_stopped: bool


class LaneAssigner:
    def __init__(self, lanes: list[LanePolygon], fps: float = 25.0):
        self._lanes = lanes
        self._fps = fps
        # per-track waiting-time accumulator, keyed by track_id
        self._stopped_since_frame: dict[int, int] = {}

    def assign(self, track: Track, frame_index: int) -> LaneAssignment:
        lane = self._find_lane(track.detection_center or track.center)

        vx, vy = track.velocity_px_per_frame()
        speed_px_per_frame = (vx**2 + vy**2) ** 0.5
        is_stopped = speed_px_per_frame < (lane.stopped_speed_px_per_frame if lane else 1.5)

        if is_stopped:
            self._stopped_since_frame.setdefault(track.track_id, frame_index)
        else:
            self._stopped_since_frame.pop(track.track_id, None)

        waiting_frames = (
            frame_index - self._stopped_since_frame[track.track_id]
            if track.track_id in self._stopped_since_frame
            else 0
        )
        waiting_time_s = waiting_frames / self._fps if self._fps > 0 else 0.0

        speed_kmph = self._speed_to_kmph(speed_px_per_frame, lane)

        return LaneAssignment(
            track_id=track.track_id,
            lane_id=lane.lane_id if lane else UNKNOWN_LANE,
            direction=lane.direction if lane else None,
            speed_kmph=round(speed_kmph, 1),
            waiting_time_s=round(waiting_time_s, 1),
            is_stopped=is_stopped,
        )

    def assign_many(self, tracks: list[Track], frame_index: int) -> list[LaneAssignment]:
        return [self.assign(t, frame_index) for t in tracks]

    def _find_lane(self, point: Point) -> LanePolygon | None:
        for lane in self._lanes:
            if point_in_polygon(point, lane.polygon):
                return lane
        return None

    def _speed_to_kmph(self, speed_px_per_frame: float, lane: LanePolygon | None) -> float:
        ppm = lane.pixels_per_meter if lane else 8.0
        meters_per_frame = speed_px_per_frame / ppm if ppm > 0 else 0.0
        meters_per_second = meters_per_frame * self._fps
        return meters_per_second * 3.6
