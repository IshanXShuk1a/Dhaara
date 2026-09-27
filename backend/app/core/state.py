"""
AppState

Holds the process-wide (but per-intersection-scoped) live objects the API
and WebSocket layers need: the RegionalTrafficCoordinator, each
intersection's VideoSource, ScenarioProvider/SimulationScenarioBuilder (for
the /api/simulation endpoints), and the SimulationSignalController.

This is intentionally the ONLY module holding global mutable state, and
even here nothing is global traffic state - it is a dict keyed by
intersection_id, so adding intersection 2, 3, ... never touches
intersection 1's data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.controllers.intersection_controller import IntersectionController
from app.services.controllers.regional_coordinator import RegionalTrafficCoordinator
from app.services.cv.video_source import VideoSource
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder
from app.services.signals.signal_controller import SimulationSignalController


@dataclass
class IntersectionRuntime:
    controller: IntersectionController
    video_source: VideoSource | None
    scenario_provider: ScenarioProvider
    scenario_builder: SimulationScenarioBuilder
    lanes: list = field(default_factory=list)  # LanePolygon list, needed by /api/video/frame to render overlays
    hardware_controller: SimulationSignalController = field(default_factory=SimulationSignalController)
    frame_index: int = 0
    camera_status: str = "OFFLINE"
    last_frame_image: object = None  # most recent raw np.ndarray frame, for on-demand overlay rendering


class AppState:
    def __init__(self):
        self.coordinator = RegionalTrafficCoordinator()
        self.runtimes: dict[str, IntersectionRuntime] = {}

    def register(self, intersection_id: str, runtime: IntersectionRuntime) -> None:
        self.runtimes[intersection_id] = runtime
        self.coordinator.register(runtime.controller)

    def get(self, intersection_id: str) -> IntersectionRuntime | None:
        return self.runtimes.get(intersection_id)


app_state = AppState()
