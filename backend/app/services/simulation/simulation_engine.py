"""
SimulationEngine

Provides the scripted ground truth that `SimulationDetector` reads from, and
the operator-facing controls ("increase NORTH traffic", "spawn ambulance",
"add helmet violation") that the /api/simulation endpoints call. Every
control here mutates actual engine state (vehicle scripts, spawn queues)
that flows through the exact same Tracker -> LaneAssigner ->
LaneIntelligenceEngine -> TrafficDecisionEngine -> SignalFSM pipeline as a
live camera would - it does not shortcut to just editing a dashboard number.

A `VehicleScript` describes one simulated vehicle's straight-line path
across a frame range. `ScenarioProvider.detections_for_frame` interpolates
every currently-active script into a `Detection` for that frame. This is
intentionally simple/deterministic (no hidden randomness) so a judge or
developer can read the script and verify the resulting Detection by hand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

from app.services.cv.tracker import Detection


@dataclass
class VehicleScript:
    script_id: int
    class_name: str
    start_frame: int
    end_frame: int
    start_bbox: tuple[float, float, float, float]
    end_bbox: tuple[float, float, float, float]
    confidence: float = 0.9
    # if True, the vehicle is held stationary at start_bbox for the whole
    # range (models a queued/stopped vehicle) instead of interpolating.
    stationary: bool = False

    def bbox_at(self, frame_index: int) -> tuple[float, float, float, float] | None:
        if frame_index < self.start_frame or frame_index > self.end_frame:
            return None
        if self.stationary or self.end_frame == self.start_frame:
            return self.start_bbox
        t = (frame_index - self.start_frame) / (self.end_frame - self.start_frame)
        return tuple(
            s + (e - s) * t for s, e in zip(self.start_bbox, self.end_bbox)
        )  # type: ignore[return-value]


class ScenarioProvider:
    def __init__(self):
        self._scripts: dict[int, VehicleScript] = {}
        self._id_counter = count(1)

    def add_vehicle(
        self,
        class_name: str,
        start_frame: int,
        end_frame: int,
        start_bbox: tuple[float, float, float, float],
        end_bbox: tuple[float, float, float, float] | None = None,
        confidence: float = 0.9,
        stationary: bool = False,
    ) -> int:
        script_id = next(self._id_counter)
        self._scripts[script_id] = VehicleScript(
            script_id=script_id,
            class_name=class_name,
            start_frame=start_frame,
            end_frame=end_frame,
            start_bbox=start_bbox,
            end_bbox=end_bbox or start_bbox,
            confidence=confidence,
            stationary=stationary,
        )
        return script_id

    def remove_vehicle(self, script_id: int) -> None:
        self._scripts.pop(script_id, None)

    def clear(self) -> None:
        self._scripts.clear()

    def detections_for_frame(self, frame_index: int) -> list[Detection]:
        detections: list[Detection] = []
        for script in self._scripts.values():
            bbox = script.bbox_at(frame_index)
            if bbox is not None:
                detections.append(Detection(bbox=bbox, class_name=script.class_name, confidence=script.confidence))
        return detections


@dataclass
class TrafficSliderState:
    """Operator-controlled target vehicle counts per direction (0-100 slider).
    SimulationScenarioBuilder reads these to decide how many VehicleScripts
    to spawn per lane - this is the "backend state changes" the traffic
    simulator sliders must actually drive."""

    north: int = 10
    south: int = 10
    east: int = 10
    west: int = 10


class SimulationScenarioBuilder:
    """Translates high-level operator intents (slider values, "spawn
    ambulance", "add helmet violation") into concrete VehicleScripts on a
    ScenarioProvider, for a given lane layout."""

    def __init__(self, provider: ScenarioProvider, lane_bboxes: dict[str, tuple[float, float, float, float]]):
        self._provider = provider
        self._lane_bboxes = lane_bboxes  # direction -> representative bbox region to spawn vehicles inside
        self._active_lane_script_ids: dict[str, list[int]] = {d: [] for d in lane_bboxes}

    def apply_slider_state(self, sliders: TrafficSliderState, current_frame: int, horizon_frames: int = 250) -> None:
        targets = {"NORTH": sliders.north, "SOUTH": sliders.south, "EAST": sliders.east, "WEST": sliders.west}
        for direction, target_count in targets.items():
            for sid in self._active_lane_script_ids[direction]:
                self._provider.remove_vehicle(sid)
            self._active_lane_script_ids[direction] = []

            x1, y1, x2, y2 = self._lane_bboxes[direction]
            lane_width = x2 - x1
            # Higher slider value -> more vehicles AND a larger fraction held stationary
            # (queued), which is what should drive occupancy/queue/pressure up.
            vehicle_count = max(0, min(30, target_count))
            stationary_fraction = min(0.9, target_count / 40.0)
            # Spread vehicles evenly across the lane width (no overlap) instead of
            # a fixed modulo-6 grid, so the overlay stays legible at high counts.
            slot_width = lane_width / max(vehicle_count, 1)
            vehicle_width = max(6.0, min(slot_width * 0.8, lane_width / 8.0))
            for i in range(vehicle_count):
                offset = i * slot_width
                bbox = (x1 + offset, y1, x1 + offset + vehicle_width, y2)
                is_stationary = i < int(vehicle_count * stationary_fraction)
                sid = self._provider.add_vehicle(
                    class_name="car",
                    start_frame=current_frame,
                    end_frame=current_frame + horizon_frames,
                    start_bbox=bbox,
                    end_bbox=bbox if is_stationary else (bbox[0] + 40, bbox[1], bbox[2] + 40, bbox[3]),
                    stationary=is_stationary,
                )
                self._active_lane_script_ids[direction].append(sid)

    def spawn_ambulance(self, direction: str, current_frame: int, duration_frames: int = 150) -> int:
        x1, y1, x2, y2 = self._lane_bboxes[direction]
        return self._provider.add_vehicle(
            class_name="ambulance",
            start_frame=current_frame,
            end_frame=current_frame + duration_frames,
            start_bbox=(x1, y1, x1 + (x2 - x1) / 8.0, y2),
            end_bbox=(x2 - (x2 - x1) / 8.0, y1, x2, y2),
            confidence=0.92,
        )

    def spawn_helmet_violation(self, direction: str, current_frame: int, duration_frames: int = 60) -> int:
        x1, y1, x2, y2 = self._lane_bboxes[direction]
        return self._provider.add_vehicle(
            class_name="motorcycle",
            start_frame=current_frame,
            end_frame=current_frame + duration_frames,
            start_bbox=(x1 + 10, y1 + 10, x1 + 40, y1 + 40),
            confidence=0.88,
            stationary=True,
        )
