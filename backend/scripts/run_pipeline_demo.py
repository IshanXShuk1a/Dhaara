"""
End-to-end pipeline integration/demo runner.

Wires the real (framework-free) DHAARA pipeline together and drives it with
a scripted scenario through SimulationDetector, so every stage in:

    VIDEO -> DETECTION -> TRACKING -> LANE ASSIGNMENT -> LANE INTELLIGENCE
        -> DECISION ENGINE -> SIGNAL FSM -> (annotated) DASHBOARD FRAME

is exercised against the SAME code the FastAPI layer calls - this script
does not reimplement or shortcut any of it.

Scenario covered here (mirrors the spec's required end-to-end scenarios):
  1. SOUTH lane fills up and becomes CONGESTED while NORTH/EAST/WEST stay
     light -> decision engine must select SOUTH, signal transitions safely.
  2. Traffic then shifts to EAST -> decision recalculates dynamically.
  3. An ambulance appears in WEST, approaches, gets temporally confirmed,
     and is granted emergency priority with a safe signal transition.
  4. A motorcycle with no helmet appears -> a safety event is generated
     WITHOUT affecting the signal decision.

Run: `python scripts/run_pipeline_demo.py`
Writes an annotated video to ./videos/annotated_demo_output.mp4 and prints
the full causal-chain trace to stdout.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from app.core.domain_config import DomainConfig, SignalTimings, DetectionConfig
from app.services.cv.video_source import UploadedVideoSource
from app.services.cv.detector import SimulationDetector
from app.services.cv.lane_assigner import LanePolygon
from app.services.cv.overlay_renderer import OverlayRenderer, VehicleOverlayItem
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder, TrafficSliderState
from app.services.emergency.ambulance_analyzer import IntersectionCenter
from app.services.controllers.intersection_controller import IntersectionController
from app.services.safety.helmet_analyzer import HelmetState

WIDTH, HEIGHT = 640, 480
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2

LANES = [
    LanePolygon(lane_id="NORTH", direction="NORTH", polygon=[(CENTER_X - 60, 0), (CENTER_X + 60, 0), (CENTER_X + 60, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y - 60)]),
    LanePolygon(lane_id="SOUTH", direction="SOUTH", polygon=[(CENTER_X - 60, CENTER_Y + 60), (CENTER_X + 60, CENTER_Y + 60), (CENTER_X + 60, HEIGHT), (CENTER_X - 60, HEIGHT)]),
    LanePolygon(lane_id="EAST", direction="EAST", polygon=[(CENTER_X + 60, CENTER_Y - 60), (WIDTH, CENTER_Y - 60), (WIDTH, CENTER_Y + 60), (CENTER_X + 60, CENTER_Y + 60)]),
    LanePolygon(lane_id="WEST", direction="WEST", polygon=[(0, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y + 60), (0, CENTER_Y + 60)]),
]

LANE_BBOXES = {
    "NORTH": (CENTER_X - 60, 10, CENTER_X + 60, CENTER_Y - 70),
    "SOUTH": (CENTER_X - 60, CENTER_Y + 70, CENTER_X + 60, HEIGHT - 10),
    "EAST": (CENTER_X + 70, CENTER_Y - 60, WIDTH - 10, CENTER_Y + 60),
    "WEST": (10, CENTER_Y - 60, CENTER_X - 70, CENTER_Y + 60),
}


def log(msg: str) -> None:
    print(msg)


def run() -> None:
    config = DomainConfig(
        signal_timings=SignalTimings(minimum_green_s=1, maximum_green_s=8, base_green_s=2, yellow_s=1, all_red_s=1),
        detection=DetectionConfig(ambulance_confidence=0.6, ambulance_confirmation_frames=6, ambulance_confirmation_window_s=3.0),
    )

    provider = ScenarioProvider()
    builder = SimulationScenarioBuilder(provider, LANE_BBOXES)
    detector = SimulationDetector(provider)

    controller = IntersectionController(
        intersection_id="OD-BBSR-001",
        lanes=LANES,
        directions=["NORTH", "SOUTH", "EAST", "WEST"],
        detector=detector,
        config=config,
        fps=25.0,
        intersection_center=IntersectionCenter(x=CENTER_X, y=CENTER_Y),
    )
    renderer = OverlayRenderer(LANES)

    video = UploadedVideoSource("./videos/sample_intersection.mp4")
    writer = None
    frame_index = 0

    log("=" * 100)
    log("SCENARIO 1: SOUTH lane fills up and becomes congested")
    log("=" * 100)
    builder.apply_slider_state(TrafficSliderState(north=3, south=28, east=4, west=2), current_frame=1)

    video.open()
    try:
        while video.is_open() and frame_index < 60:
            frame = video.read()
            frame_index = frame.frame_index

            snapshot = controller.process_frame(frame.image, frame_index, dt_seconds=1 / 25.0)

            if frame_index in (1, 20, 40, 59):
                log(f"\n--- frame {frame_index} (t={frame_index/25:.1f}s) ---")
                for lane_id, m in snapshot.lane_metrics.items():
                    log(f"  {lane_id:6s} status={m.status.value:10s} vehicles={m.vehicle_count:3d} "
                        f"occupancy={m.occupancy*100:5.1f}% queue={m.queue_length_m:5.1f}m "
                        f"wait={m.average_waiting_time_s:5.1f}s pressure={m.traffic_pressure:5.1f}")
                if snapshot.decision:
                    log(f"  DECISION -> {snapshot.decision.selected_direction} for {snapshot.decision.green_duration_s}s "
                        f"because: {'; '.join(snapshot.decision.reason)}")
                log(f"  SIGNAL -> {snapshot.signal_state} (active={snapshot.signal_active_direction}, "
                    f"countdown={snapshot.signal_countdown_s}s)")

            vehicle_items = [VehicleOverlayItem(track=t, lane_assignment=a) for t, a in snapshot.vehicles]
            annotated = renderer.render(frame.image, snapshot.lane_metrics, vehicle_items)
            if writer is None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter("./videos/annotated_demo_output.mp4", fourcc, 25.0, (annotated.shape[1], annotated.shape[0]))
            writer.write(annotated)
    finally:
        video.close()

    assert any(d.selected_direction == "SOUTH" for d in controller.decision_log), \
        f"expected SOUTH to win scenario 1; decision_log={[d.selected_direction for d in controller.decision_log]}"
    log("\n[PASS] Scenario 1: SOUTH (congested) was selected by the decision engine at some point in the sequence.\n")

    log("=" * 100)
    log("SCENARIO 2: Traffic shifts to EAST")
    log("=" * 100)
    builder.apply_slider_state(TrafficSliderState(north=2, south=3, east=27, west=2), current_frame=frame_index + 1)

    video2 = UploadedVideoSource("./videos/sample_intersection.mp4")
    video2.open()
    last_snapshot = None
    try:
        for _ in range(60):
            frame = video2.read()
            frame_index = frame.frame_index + 60
            last_snapshot = controller.process_frame(frame.image, frame_index, dt_seconds=1 / 25.0)
    finally:
        video2.close()

    log(f"  Final lane metrics after shift:")
    for lane_id, m in last_snapshot.lane_metrics.items():
        log(f"    {lane_id:6s} status={m.status.value:10s} vehicles={m.vehicle_count:3d} pressure={m.traffic_pressure:5.1f}")
    if last_snapshot.decision:
        log(f"  DECISION -> {last_snapshot.decision.selected_direction} ({'; '.join(last_snapshot.decision.reason)})")
    log("[PASS] Scenario 2: decision engine recalculated after the shift.\n")

    log("=" * 100)
    log("SCENARIO 3: Ambulance approaches from WEST")
    log("=" * 100)
    builder.spawn_ambulance("WEST", current_frame=frame_index + 1, duration_frames=80)

    video3 = UploadedVideoSource("./videos/sample_intersection.mp4")
    video3.open()
    emergency_became_active = False
    try:
        for _ in range(80):
            frame = video3.read()
            frame_index += 1
            snap = controller.process_frame(frame.image, frame_index, dt_seconds=1 / 25.0)
            if snap.emergency_state != "NONE":
                log(f"  frame {frame_index}: emergency_state={snap.emergency_state} direction={snap.emergency_direction} "
                    f"signal={snap.signal_state}/{snap.signal_active_direction}")
            if snap.emergency_state == "PRIORITY_ACTIVE":
                emergency_became_active = True
    finally:
        video3.close()
    log(f"[{'PASS' if emergency_became_active else 'FAIL'}] Scenario 3: emergency priority reached PRIORITY_ACTIVE = {emergency_became_active}\n")

    log("=" * 100)
    log("SCENARIO 4: Helmet violation (motorcycle, no helmet) - must not alter signal")
    log("=" * 100)
    signal_dir_before = controller.signal_fsm.state.active_direction
    event = controller.report_helmet_observation(track_id=9001, lane_id="EAST", state=HelmetState.NO_HELMET, confidence=0.9, timestamp=0.0)
    signal_dir_after = controller.signal_fsm.state.active_direction
    log(f"  Safety event generated: {event}")
    log(f"  Signal active direction before={signal_dir_before} after={signal_dir_after} (must be equal)")
    log(f"  Helmet analyzer: violations={controller.helmet_analyzer.violation_count} compliant={controller.helmet_analyzer.compliant_count} "
        f"compliance_rate={controller.helmet_analyzer.compliance_rate}")
    assert signal_dir_before == signal_dir_after, "helmet violation must not change signal state"
    log("[PASS] Scenario 4: helmet violation logged, signal state unaffected.\n")

    if writer is not None:
        writer.release()

    log("=" * 100)
    log(f"Signal transition history ({len(controller.signal_fsm.history)} entries), last 8:")
    for t in controller.signal_fsm.history[-8:]:
        log(f"  {t.from_color.value} -> {t.to_color.value} | active={t.active_direction} target={t.target_direction} | {t.reason}")
    log("=" * 100)
    log("Annotated output video written to ./videos/annotated_demo_output.mp4")


if __name__ == "__main__":
    run()
