"""
OverlayRenderer

Draws DHAARA's actual computed state onto a frame: lane polygons + status,
vehicle bounding boxes + track IDs + class, ambulance/helmet labels. Every
value drawn is passed in from the real pipeline output for that frame - this
module does no computation of its own beyond pixel drawing, so there is no
way for the overlay to show something the backend didn't actually compute.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.services.cv.tracker import Track
from app.services.cv.lane_assigner import LanePolygon, LaneAssignment
from app.services.lanes.lane_intelligence import LaneMetrics, LaneStatus

STATUS_COLORS = {
    LaneStatus.FREE: (80, 200, 120),
    LaneStatus.LOW: (200, 200, 120),
    LaneStatus.MODERATE: (0, 190, 255),
    LaneStatus.HIGH: (0, 120, 255),
    LaneStatus.CONGESTED: (0, 0, 220),
}


@dataclass
class VehicleOverlayItem:
    track: Track
    lane_assignment: LaneAssignment
    is_ambulance_confirmed: bool = False
    helmet_label: str | None = None  # "HELMET" | "NO HELMET" | None


class OverlayRenderer:
    def __init__(self, lanes: list[LanePolygon]):
        self._lanes = lanes

    def render(
        self,
        image: np.ndarray,
        lane_metrics: dict[str, LaneMetrics],
        vehicles: list[VehicleOverlayItem],
        show_lanes: bool = True,
        show_boxes: bool = True,
        show_labels: bool = True,
        show_heat: bool = True,
    ) -> np.ndarray:
        frame = image.copy()
        if show_lanes:
            self._draw_lanes(frame, lane_metrics, show_heat=show_heat)
        if show_boxes:
            self._draw_vehicles(frame, vehicles, show_labels=show_labels)
        return frame

    def _draw_lanes(self, frame: np.ndarray, lane_metrics: dict[str, LaneMetrics], show_heat: bool = True) -> None:
        if show_heat:
            overlay = frame.copy()
            for lane in self._lanes:
                pts = np.array(lane.polygon, dtype=np.int32).reshape((-1, 1, 2))
                metrics = lane_metrics.get(lane.lane_id)
                color = STATUS_COLORS.get(metrics.status, (200, 200, 200)) if metrics else (150, 150, 150)
                cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)

        for lane in self._lanes:
            pts = np.array(lane.polygon, dtype=np.int32).reshape((-1, 1, 2))
            metrics = lane_metrics.get(lane.lane_id)
            color = STATUS_COLORS.get(metrics.status, (200, 200, 200)) if metrics else (150, 150, 150)
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

            min_x = min(p[0] for p in lane.polygon)
            min_y = min(p[1] for p in lane.polygon)

            lx = int(max(14, min_x + 14))
            ly = int(max(26, min_y + 24))

            label_lines = [f"{lane.lane_id} APPROACH"]
            if metrics:
                label_lines.append(f"{metrics.vehicle_count} VEHICLES IN ROI")
                label_lines.append(f"SCORE: {metrics.vehicle_score:g}")
            self._draw_label_block(frame, (lx, ly), label_lines, color)

    def _draw_vehicles(self, frame: np.ndarray, vehicles: list[VehicleOverlayItem], show_labels: bool = True) -> None:
        for item in vehicles:
            x1, y1, x2, y2 = [int(v) for v in item.track.bbox]
            box_color = (0, 0, 220) if item.is_ambulance_confirmed else (60, 200, 60)
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            if not show_labels:
                continue

            box_width = x2 - x1
            if box_width < 34 and not item.is_ambulance_confirmed:
                label = f"#{item.track.track_id}"
            else:
                label = f"#{item.track.track_id} {item.track.class_name} {item.track.confidence:.2f}"
                if item.is_ambulance_confirmed:
                    label += " [EMERGENCY]"
                if item.helmet_label:
                    label += f" {item.helmet_label}"
            self._draw_label_block(frame, (x1, max(0, y1 - 8)), [label], box_color)

    @staticmethod
    def _draw_label_block(frame: np.ndarray, origin: tuple[int, int], lines: list[str], color: tuple[int, int, int]) -> None:
        x, y = origin
        for i, line in enumerate(lines):
            y_i = y + i * 16
            cv2.putText(frame, line, (x, y_i), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, line, (x, y_i), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
