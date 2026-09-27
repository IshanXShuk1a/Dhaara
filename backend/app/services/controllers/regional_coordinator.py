"""
RegionalTrafficCoordinator

Owns a collection of independent `IntersectionController`s (one per real
intersection). Deliberately exchanges only summarized traffic snapshots
between intersections (e.g. for future green-wave coordination) - never raw
video or per-frame detections - since there is no technical requirement to
centralize that here.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.controllers.intersection_controller import IntersectionController, IntersectionSnapshot


@dataclass
class RegionalSummary:
    intersection_id: str
    signal_state: str
    active_direction: str
    emergency_state: str
    congested_directions: list[str]


class RegionalTrafficCoordinator:
    def __init__(self):
        self._intersections: dict[str, IntersectionController] = {}

    def register(self, controller: IntersectionController) -> None:
        self._intersections[controller.intersection_id] = controller

    def unregister(self, intersection_id: str) -> None:
        self._intersections.pop(intersection_id, None)

    def get(self, intersection_id: str) -> IntersectionController | None:
        return self._intersections.get(intersection_id)

    def all_ids(self) -> list[str]:
        return list(self._intersections.keys())

    def summarize(self, snapshots: dict[str, IntersectionSnapshot]) -> list[RegionalSummary]:
        summaries = []
        for intersection_id, snapshot in snapshots.items():
            congested = [
                lane_id for lane_id, metrics in snapshot.lane_metrics.items()
                if metrics.status.value == "CONGESTED"
            ]
            summaries.append(
                RegionalSummary(
                    intersection_id=intersection_id,
                    signal_state=snapshot.signal_state,
                    active_direction=snapshot.signal_active_direction,
                    emergency_state=snapshot.emergency_state,
                    congested_directions=congested,
                )
            )
        return summaries
