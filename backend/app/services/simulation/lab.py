"""Isolated educational scenarios driven by the production traffic pipeline."""
from __future__ import annotations

from dataclasses import asdict, replace
import math
import time

import cv2
import numpy as np

from app.core.domain_config import DomainConfig
from app.core.state import CameraRuntime, IntersectionRuntime
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import SimulationDetector
from app.services.cv.lane_assigner import DIRECTIONS, DEFAULT_ROI, camera_lane
from app.services.cv.video_source import SimulationVideoSource
from app.services.lanes.lane_intelligence import LaneGeometry
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder, TrafficSliderState


SIMULATION_INTERSECTION_ID = "SIMULATION-LAB"
SCENARIOS = {
    "balanced": ("Balanced traffic", TrafficSliderState(8, 8, 8, 8), "EW", 0.0),
    "ns_busy": ("North and South are busier", TrafficSliderState(18, 18, 4, 4), "EW", 0.0),
    "ew_busy": ("East and West are busier", TrafficSliderState(4, 4, 18, 18), "EW", 0.0),
    "empty_ew": ("Empty EW, busy NS", TrafficSliderState(18, 18, 2, 2), "EW", 30.0),
    "empty_ns": ("Empty NS, busy EW", TrafficSliderState(2, 2, 18, 18), "NS", 30.0),
}


class SimulationLab:
    def __init__(self, config: DomainConfig):
        self.config = config
        self.scenario = "balanced"
        self.run_id = 0
        self.label = "Balanced traffic"
        self.targets = TrafficSliderState(8, 8, 8, 8)
        self.paused = False
        self.speed = 1
        self.simulated_time_s = 0.0
        self.ambulances: dict[int, tuple[str, bool, float]] = {}

    def metadata(self) -> dict:
        ambulance = next(({"direction": direction, "lights_active": lights}
                          for direction, lights, _ in self.ambulances.values()), None)
        return {"scenario": self.scenario, "run_id": self.run_id, "label": self.label, "targets": asdict(self.targets),
                "paused": self.paused, "speed": self.speed,
                "simulated_time_s": round(self.simulated_time_s, 2), "ambulance": ambulance}

    def reset(self, runtime: IntersectionRuntime, scenario: str = "balanced") -> None:
        if scenario not in SCENARIOS:
            raise ValueError("Unknown simulation scenario")
        self.label, self.targets, initial_pair, elapsed_s = SCENARIOS[scenario]
        self.scenario = scenario
        self.run_id += 1
        self.simulated_time_s = 0.0
        self.ambulances.clear()
        runtime.scenario_provider.clear()
        runtime.frame_index = 0
        geometries = {d: LaneGeometry(d, 9.144, 25) for d in DIRECTIONS}
        lanes = [camera_lane(d, 640, 360, DEFAULT_ROI, 8.0) for d in DIRECTIONS]
        runtime.controller = IntersectionController(
            SIMULATION_INTERSECTION_ID, lanes, list(DIRECTIONS), SimulationDetector(runtime.scenario_provider),
            config=self.config, lane_geometry=geometries,
        )
        for direction in DIRECTIONS:
            runtime.controller.configure_camera_roi(direction, DEFAULT_ROI, geometries[direction])
        # A scenario reset places the entire demonstration at its stated starting
        # point. Subsequent changes always use the production yellow transition.
        runtime.controller.signal_fsm._state = replace(
            runtime.controller.signal_fsm.state, active_direction=initial_pair, elapsed_s=elapsed_s)
        self.set_targets(runtime, self.targets)
        self._process_step(runtime, 0.0)

    def set_targets(self, runtime: IntersectionRuntime, targets: TrafficSliderState) -> None:
        self.targets = targets
        runtime.scenario_builder.apply_slider_state(
            targets, runtime.frame_index, horizon_frames=2**31, hold_queues=True)

    def spawn_ambulance(self, runtime: IntersectionRuntime, direction: str, lights_active: bool = True) -> int:
        for previous_id in self.ambulances:
            runtime.scenario_provider.remove_vehicle(previous_id)
        self.ambulances.clear()
        # Keep the ambulance out of the scoring polygon: emergency priority
        # deliberately sees the whole directional camera, independently of ROI.
        script_id = runtime.scenario_provider.add_vehicle(
            "ambulance", runtime.frame_index, 2**31,
            (40.0, 60.0, 110.0, 150.0), stationary=True, direction=direction)
        self.ambulances[script_id] = (direction, lights_active, self.simulated_time_s + 30)
        return script_id

    def step(self, runtime: IntersectionRuntime, dt_seconds: float):
        if self.paused and runtime.controller.last_snapshot is not None:
            return runtime.controller.last_snapshot
        remaining = max(0.0, dt_seconds) * self.speed
        # Sampling the same virtual interval at <=0.2 s preserves yellow and
        # empty-demand observations when demonstration speed is increased.
        if remaining == 0:
            return self._process_step(runtime, 0.0)
        steps = max(1, math.ceil(remaining / .2))
        step_dt = remaining / steps
        for _ in range(steps):
            snapshot = self._process_step(runtime, step_dt)
        return snapshot

    def _process_step(self, runtime: IntersectionRuntime, dt_seconds: float):
        runtime.frame_index += 1
        self.simulated_time_s += dt_seconds
        images = {d: np.full((360, 640, 3), (38, 40, 44), dtype=np.uint8) for d in DIRECTIONS}
        # Render flashing roof pixels for the existing temporal beacon detector;
        # a simulation button never directly grants ambulance priority.
        beacon_on = int(time.monotonic() * 5) % 2 == 0
        for script_id, (direction, lights_active, expires_s) in list(self.ambulances.items()):
            if self.simulated_time_s >= expires_s:
                runtime.scenario_provider.remove_vehicle(script_id)
                self.ambulances.pop(script_id, None)
                continue
            script = runtime.scenario_provider._scripts.get(script_id)
            bbox = script.bbox_at(runtime.frame_index) if script else None
            if bbox is None:
                self.ambulances.pop(script_id, None)
                continue
            if lights_active and beacon_on:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(images[script.direction], (int(x1 + 10), int(y1 + 3)),
                              (int(x2 - 10), int(y1 + 12)), (0, 0, 255), -1)
        statuses = {d: {"status": "ONLINE", "error": None, "source": "SIMULATION",
                        "frame_index": runtime.frame_index} for d in DIRECTIONS}
        snapshot = runtime.controller.process_frames(images, runtime.frame_index, dt_seconds, statuses)
        snapshot.is_simulated = True
        runtime.processed_frames = images
        runtime.hardware_controller.apply_state(SIMULATION_INTERSECTION_ID, runtime.controller.signal_fsm.state)
        return snapshot


def create_simulation_runtime(config: DomainConfig) -> IntersectionRuntime:
    provider = ScenarioProvider()
    builder = SimulationScenarioBuilder(provider, {d: (260., 120., 380., 240.) for d in DIRECTIONS})
    lab = SimulationLab(config)
    # reset() constructs the controller before registration; no database live
    # intersection, real camera source, shared YOLO or regional node is created.
    runtime = IntersectionRuntime(
        controller=None,
        cameras={d: CameraRuntime(d, SimulationVideoSource(d), "") for d in DIRECTIONS},
        scenario_provider=provider, scenario_builder=builder,
        is_simulated=True, simulation_lab=lab,
    )
    lab.reset(runtime)
    return runtime
