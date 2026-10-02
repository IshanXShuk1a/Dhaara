"""Per-intersection camera buffers and the existing controller/coordinator."""
from __future__ import annotations
from dataclasses import dataclass, field
from threading import RLock
from app.services.controllers.intersection_controller import IntersectionController
from app.services.controllers.regional_coordinator import RegionalTrafficCoordinator
from app.services.cv.video_source import VideoSource, UploadedVideoSource
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder
from app.services.signals.signal_controller import SimulationSignalController

@dataclass
class CameraRuntime:
    direction: str
    source: VideoSource
    path: str
    frame: object = None
    status: str = "CONNECTING"
    error: str | None = None

@dataclass
class IntersectionRuntime:
    controller: IntersectionController
    cameras: dict[str, CameraRuntime]
    scenario_provider: ScenarioProvider | None = None
    scenario_builder: SimulationScenarioBuilder | None = None
    real_detector: object = None
    hardware_controller: SimulationSignalController = field(default_factory=SimulationSignalController)
    frame_index: int = 0
    camera_status: str = "ONLINE"
    is_simulated: bool = False
    processed_frames: dict = field(default_factory=dict)
    # The educational lab owns a separate virtual clock and never shares inputs
    # or controller state with a live intersection.
    simulation_lab: object | None = None
    lock: object = field(default_factory=RLock)

    def restart_video_inputs(self):
        with self.lock:
            if self.simulation_lab is not None or self.is_simulated:
                raise ValueError("The educational simulation cannot restart live video inputs")
            self.camera_status = "ONLINE"
            self.controller._detector = self.real_detector
            for direction, camera in self.cameras.items():
                camera.source = UploadedVideoSource(camera.path)
                camera.frame = None
                camera.status, camera.error = "CONNECTING", None
                self.controller.reset_camera(direction)
            self.processed_frames = {}
            self.controller.last_snapshot = None

class AppState:
    def __init__(self):
        self.coordinator = RegionalTrafficCoordinator()
        self.runtimes = {}

    def register(self, intersection_id, runtime):
        self.runtimes[intersection_id] = runtime
        if runtime.simulation_lab is None:
            self.coordinator.register(runtime.controller)

    def get(self, intersection_id):
        return self.runtimes.get(intersection_id)

app_state = AppState()
