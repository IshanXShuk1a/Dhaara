"""
CentroidIoUTracker

A dependency-light (numpy only) multi-object tracker that assigns persistent
`track_id`s to detections across frames, so DHAARA never counts the same
physical vehicle twice just because it appeared in consecutive frames.

Algorithm (intentionally simple and explainable, not a black box):
  1. For each existing track, compute IoU + centroid distance against every
     new detection of the same class.
  2. Greedily match the highest-IoU pairs above `iou_threshold` (falling back
     to nearest-centroid within `max_centroid_distance_px` if IoU is 0, which
     handles fast motion / low frame rate).
  3. Unmatched existing tracks are marked "missed" for this frame, not deleted
     immediately - they survive up to `max_missed_frames` to tolerate
     occlusion. Beyond that, the track is considered gone (vehicle left frame).
  4. Unmatched detections spawn new tracks with a fresh, never-reused id.

A full video restart is handled by the caller creating a new Tracker instance
(`reset()` is also provided) - this module holds no global state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count


@dataclass
class Detection:
    """One frame's raw detection, in image pixel coordinates."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    class_name: str
    confidence: float

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass
class Track:
    track_id: int
    class_name: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    previous_center: tuple[float, float] | None
    confidence: float
    first_seen_frame: int
    last_seen_frame: int
    missed_frames: int = 0
    # position history used for speed/waiting-time estimation downstream
    positions: list[tuple[float, float]] = field(default_factory=list)

    def velocity_px_per_frame(self) -> tuple[float, float]:
        if self.previous_center is None:
            return (0.0, 0.0)
        return (self.center[0] - self.previous_center[0], self.center[1] - self.previous_center[1])


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def _centroid_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class CentroidIoUTracker:
    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_centroid_distance_px: float = 80.0,
        max_missed_frames: int = 10,
    ):
        self._iou_threshold = iou_threshold
        self._max_centroid_distance_px = max_centroid_distance_px
        self._max_missed_frames = max_missed_frames
        self._id_counter = count(1)
        self._tracks: dict[int, Track] = {}
        self._frame_index = 0

    @property
    def active_tracks(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.missed_frames == 0]

    def reset(self) -> None:
        self._id_counter = count(1)
        self._tracks = {}
        self._frame_index = 0

    def update(self, detections: list[Detection]) -> list[Track]:
        """Process one frame's detections. Returns the list of currently active tracks."""
        self._frame_index += 1
        unmatched_detections = list(range(len(detections)))
        matched_track_ids: set[int] = set()

        MOTORIZED_SET = {"car", "truck", "bus", "ambulance"}
        TWO_WHEELER_SET = {"motorcycle", "bicycle"}

        # Build candidate pairs (track_id, detection_index, score) with intelligent class compatibility.
        candidates: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            for det_idx in unmatched_detections:
                det = detections[det_idx]

                # Check class compatibility: exact match OR compatible vehicle family
                is_exact = (det.class_name == track.class_name)
                is_compat_motorized = (det.class_name in MOTORIZED_SET and track.class_name in MOTORIZED_SET)
                is_compat_two_wheel = (det.class_name in TWO_WHEELER_SET and track.class_name in TWO_WHEELER_SET)

                if not (is_exact or is_compat_motorized or is_compat_two_wheel):
                    continue

                iou = _iou(track.bbox, det.bbox)
                # Small penalty if matching compatible class instead of exact class
                class_multiplier = 1.0 if is_exact else 0.88

                if iou > 0:
                    candidates.append((iou * class_multiplier, track_id, det_idx))
                else:
                    dist = _centroid_distance(track.center, det.center)
                    if dist <= self._max_centroid_distance_px:
                        # encode as a negative pseudo-score so IoU matches always win
                        candidates.append((-dist / class_multiplier, track_id, det_idx))

        # Greedy matching, best score first (highest IoU, or least-negative distance).
        candidates.sort(key=lambda c: c[0], reverse=True)
        used_detections: set[int] = set()
        for score, track_id, det_idx in candidates:
            if track_id in matched_track_ids or det_idx in used_detections:
                continue
            if score <= 0 and -score > self._max_centroid_distance_px:
                continue
            if 0 < score < self._iou_threshold:
                continue
            self._apply_match(track_id, detections[det_idx])
            matched_track_ids.add(track_id)
            used_detections.add(det_idx)

        # Unmatched existing tracks: increment missed counter, or drop if stale.
        for track_id, track in list(self._tracks.items()):
            if track_id not in matched_track_ids:
                track.missed_frames += 1
                if track.missed_frames > self._max_missed_frames:
                    del self._tracks[track_id]

        # Unmatched detections: spawn new tracks (vehicle entering frame).
        for det_idx, det in enumerate(detections):
            if det_idx in used_detections:
                continue
            new_id = next(self._id_counter)
            self._tracks[new_id] = Track(
                track_id=new_id,
                class_name=det.class_name,
                bbox=det.bbox,
                center=det.center,
                previous_center=None,
                confidence=det.confidence,
                first_seen_frame=self._frame_index,
                last_seen_frame=self._frame_index,
                positions=[det.center],
            )

        return self.active_tracks

    def _apply_match(self, track_id: int, det: Detection) -> None:
        track = self._tracks[track_id]
        track.previous_center = track.center

        # Exponential Moving Average (EMA) bounding box smoothing: suppresses jitter and stabilizes geometry
        alpha = 0.70
        ox1, oy1, ox2, oy2 = track.bbox
        nx1, ny1, nx2, ny2 = det.bbox
        smoothed_bbox = (
            alpha * nx1 + (1.0 - alpha) * ox1,
            alpha * ny1 + (1.0 - alpha) * oy1,
            alpha * nx2 + (1.0 - alpha) * ox2,
            alpha * ny2 + (1.0 - alpha) * oy2,
        )
        track.bbox = smoothed_bbox
        track.center = ((smoothed_bbox[0] + smoothed_bbox[2]) / 2.0, (smoothed_bbox[1] + smoothed_bbox[3]) / 2.0)

        # Update class if higher confidence or emergency ambulance
        if det.class_name == "ambulance" or det.confidence > track.confidence:
            track.class_name = det.class_name
        track.confidence = max(track.confidence * 0.88, det.confidence)
        track.last_seen_frame = self._frame_index
        track.missed_frames = 0
        track.positions.append(track.center)
        if len(track.positions) > 60:
            track.positions.pop(0)
