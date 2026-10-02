"""Exercise four independent synthetic cameras through the existing controller."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import SimulationDetector
from app.services.cv.lane_assigner import DIRECTIONS, camera_lane
from app.services.cv.video_source import SimulationVideoSource
from app.services.cv.overlay_renderer import OverlayRenderer, VehicleOverlayItem
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder, TrafficSliderState


def run():
    provider = ScenarioProvider()
    builder = SimulationScenarioBuilder(provider, {d: (260.,120.,380.,240.) for d in DIRECTIONS})
    sources = {d: SimulationVideoSource(d) for d in DIRECTIONS}
    controller = IntersectionController("DEMO", [camera_lane(d,640,360) for d in DIRECTIONS], list(DIRECTIONS), SimulationDetector(provider))
    output = Path(__file__).resolve().parents[1] / "videos" / "four_camera_demo.mp4"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), 25., (1280,720))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot write {output}")
    try:
        for index in range(100):
            if index == 0:
                builder.apply_slider_state(TrafficSliderState(east=12,west=5,north=8,south=3), index)
            if index == 50:
                builder.apply_slider_state(TrafficSliderState(east=2,west=4,north=6,south=15), index)
            frames = {d: source.read().image for d,source in sources.items()}
            snapshot = controller.process_frames(frames, index, .04)
            panels = []
            for d in DIRECTIONS:
                items = [VehicleOverlayItem(t,a) for t,a in snapshot.camera_vehicles[d]]
                panel = OverlayRenderer([snapshot.camera_lanes[d]]).render(frames[d], snapshot.lane_metrics, items)
                cv2.putText(panel, snapshot.direction_signals[d], (16,55), cv2.FONT_HERSHEY_SIMPLEX, .6, (220,220,220), 2)
                panels.append(panel)
            writer.write(np.vstack([np.hstack(panels[:2]),np.hstack(panels[2:])]))
            if index in (0,50):
                print({d: {"vehicles":snapshot.lane_metrics[d].vehicle_count, "score":snapshot.lane_metrics[d].vehicle_score, "signal":snapshot.direction_signals[d]} for d in DIRECTIONS})
            assert sum(v == "GREEN" for v in snapshot.direction_signals.values()) == (2 if snapshot.signal_state == "GREEN" else 0)
            assert sum(v == "YELLOW" for v in snapshot.direction_signals.values()) == (2 if snapshot.signal_state == "YELLOW" else 0)
    finally:
        writer.release()
        for source in sources.values():
            source.close()
    print(f"Four-camera demo: {output}")

if __name__ == "__main__":
    run()
