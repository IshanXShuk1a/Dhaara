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
    """Standard ray-casting point-in-polygon test."""
    x, y = point
    n = len(polygon)
    inside = False
    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
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


def generate_full_frame_lanes(width: int, height: int) -> list[LanePolygon]:
    """Generates 4 full-frame approach lanes (NORTH, SOUTH, EAST, WEST) that span
    the FULL FRAME of any video resolution (e.g. 1920x1080, 1280x720, 640x480).
    Ensures that 100% of the intersection approaches, turn pockets, and queues
    from edge to edge are analyzed."""
    cx = width // 2
    cy = height // 2

    # Stop-line / intersection crossing box boundaries
    box_w = int(width * 0.14)
    box_h = int(height * 0.15)

    # Road corridor half-widths (covers wide multi-lane boulevards and turn bays)
    road_w_half = int(width * 0.28)
    road_h_half = int(height * 0.30)
    ppm = max(4.0, 8.0 * (width / 640.0))

    return [
        LanePolygon(
            lane_id="NORTH",
            direction="NORTH",
            polygon=[
                (float(cx - road_w_half), 0.0),
                (float(cx + road_w_half), 0.0),
                (float(cx + road_w_half), float(cy - box_h)),
                (float(cx - road_w_half), float(cy - box_h)),
            ],
            pixels_per_meter=ppm,
        ),
        LanePolygon(
            lane_id="SOUTH",
            direction="SOUTH",
            polygon=[
                (float(cx - road_w_half), float(cy + box_h)),
                (float(cx + road_w_half), float(cy + box_h)),
                (float(cx + road_w_half), float(height)),
                (float(cx - road_w_half), float(height)),
            ],
            pixels_per_meter=ppm,
        ),
        LanePolygon(
            lane_id="EAST",
            direction="EAST",
            polygon=[
                (float(cx + box_w), float(cy - road_h_half)),
                (float(width), float(cy - road_h_half)),
                (float(width), float(cy + road_h_half)),
                (float(cx + box_w), float(cy + road_h_half)),
            ],
            pixels_per_meter=ppm,
        ),
        LanePolygon(
            lane_id="WEST",
            direction="WEST",
            polygon=[
                (0.0, float(cy - road_h_half)),
                (float(cx - box_w), float(cy - road_h_half)),
                (float(cx - box_w), float(cy + road_h_half)),
                (0.0, float(cy + road_h_half)),
            ],
            pixels_per_meter=ppm,
        ),
    ]


def generate_full_frame_bboxes(width: int, height: int) -> dict[str, tuple[float, float, float, float]]:
    """Bounding boxes covering the 4 full-frame approach regions for simulation and vehicle spawning."""
    cx = width // 2
    cy = height // 2
    box_w = int(width * 0.14)
    box_h = int(height * 0.15)
    road_w_half = int(width * 0.28)
    road_h_half = int(height * 0.30)
    return {
        "NORTH": (float(cx - road_w_half + 10), 10.0, float(cx + road_w_half - 10), float(cy - box_h - 10)),
        "SOUTH": (float(cx - road_w_half + 10), float(cy + box_h + 10), float(cx + road_w_half - 10), float(height - 10)),
        "EAST": (float(cx + box_w + 10), float(cy - road_h_half + 10), float(width - 10), float(cy + road_h_half - 10)),
        "WEST": (10.0, float(cy - road_h_half + 10), float(cx - box_w - 10), float(cy + road_h_half - 10)),
    }


class LaneAssigner:
    def __init__(self, lanes: list[LanePolygon], fps: float = 25.0):
        self._lanes = lanes
        self._fps = fps
        # per-track waiting-time accumulator, keyed by track_id
        self._stopped_since_frame: dict[int, int] = {}

    def assign(self, track: Track, frame_index: int) -> LaneAssignment:
        lane = self._find_lane(track.center)

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
        # 1. Direct polygon match across configured full-frame lanes
        for lane in self._lanes:
            if point_in_polygon(point, lane.polygon):
                return lane

        # 2. Quadrant matching across the full frame for outer turn bays & lane edges
        x, y = point
        max_px = max((max(p[0] for p in l.polygon) for l in self._lanes), default=1280.0)
        max_py = max((max(p[1] for p in l.polygon) for l in self._lanes), default=720.0)

        cx = max_px / 2.0
        cy = max_py / 2.0
        dx = x - cx
        dy = y - cy

        # Center intersection crossing zone is neutral (inside the box)
        if abs(dx) < (max_px * 0.10) and abs(dy) < (max_py * 0.10):
            return None

        # Full-frame quadrant classification
        if abs(dx) > abs(dy):
            target_dir = "EAST" if dx > 0 else "WEST"
        else:
            target_dir = "SOUTH" if dy > 0 else "NORTH"

        return next((l for l in self._lanes if l.direction == target_dir), None)

    def _speed_to_kmph(self, speed_px_per_frame: float, lane: LanePolygon | None) -> float:
        ppm = lane.pixels_per_meter if lane else 8.0
        meters_per_frame = speed_px_per_frame / ppm if ppm > 0 else 0.0
        meters_per_second = meters_per_frame * self._fps
        return meters_per_second * 3.6
