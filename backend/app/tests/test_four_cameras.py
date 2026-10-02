from __future__ import annotations
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from app.core.config import Settings
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import FrameDetections, YOLODetector
from app.services.cv.lane_assigner import DIRECTIONS, camera_lane, point_in_polygon, validate_normalized_roi
from app.services.cv.tracker import Detection
from app.services.cv.video_source import UploadedVideoSource, VideoSourceError


class CameraDetector:
    def __init__(self):
        self.outputs = {d: [] for d in DIRECTIONS}
        self.batches = []

    def detect_many(self, images, frame_index):
        self.batches.append(list(images))
        return {d: FrameDetections(self.outputs[d], False, "test") for d in images}


def controller(detector):
    return IntersectionController("TEST", [camera_lane(d, 100, 100) for d in DIRECTIONS], list(DIRECTIONS), detector)


def vehicle(x, y):
    return Detection((x-3, y-3, x+3, y+3), "car", .9)


def test_camera_isolation_roi_exclusion_and_live_density_change():
    detector = CameraDetector()
    c = controller(detector)
    images = {d: np.zeros((100, 100, 3), np.uint8) for d in DIRECTIONS}
    detector.outputs["EAST"] = [vehicle(50, 50), vehicle(60, 60), vehicle(10, 10)]
    detector.outputs["WEST"] = [vehicle(50, 50)]
    detector.outputs["NORTH"] = [vehicle(10, 10)]
    first = c.process_frames(images, 1)
    assert {d: m.vehicle_count for d, m in first.lane_metrics.items()} == dict(EAST=2, WEST=1, NORTH=0, SOUTH=0)
    assert first.direction_signals == dict(EAST="GREEN", WEST="GREEN", NORTH="RED", SOUTH="RED")
    ids = [t.track_id for t, a in first.vehicles]
    assert len(ids) == len(set(ids))
    detector.outputs["EAST"] = [vehicle(50, 95)]  # just crossed near boundary
    detector.outputs["SOUTH"] = [vehicle(50, 50), vehicle(60, 60), vehicle(40, 60)]
    second = c.process_frames(images, 2)
    assert second.lane_metrics["EAST"].vehicle_count == 0  # raw detection, not smoothed bbox or missed tracks
    assert second.lane_metrics["SOUTH"].vehicle_count == 3
    assert second.signal_active_direction == "EW"
    third = c.process_frames({d: im for d, im in images.items() if d != "SOUTH"}, 3)
    assert third.lane_metrics["SOUTH"].vehicle_count == 0
    assert third.signal_active_direction == "EW"
    assert detector.batches[:2] == [list(DIRECTIONS), list(DIRECTIONS)]


@pytest.mark.parametrize("width,height", [(100, 100), (640, 480), (1920, 1080)])
def test_normalized_roi_is_resolution_independent(width, height):
    lane = camera_lane("EAST", width, height)
    assert point_in_polygon((.5*width, .5*height), lane.polygon)
    assert not point_in_polygon((.1*width, .1*height), lane.polygon)
    assert point_in_polygon((.5*width, .2*height), lane.polygon)


@pytest.mark.parametrize("roi", [[], [[0,0],[1,1],[0,1],[1,0]], [[0,0],[1,0],[2,1],[0,1]], [[0,0]]*4,
                                 [[0,0],[1,0],[1,float("nan")],[0,1]]])
def test_invalid_roi_rejected(roi):
    with pytest.raises(ValueError):
        validate_normalized_roi(roi)


def test_each_camera_roi_can_change_independently():
    det = CameraDetector()
    c = controller(det)
    images = {d: np.zeros((100,100,3), np.uint8) for d in DIRECTIONS}
    for d in DIRECTIONS:
        det.outputs[d] = [vehicle(50,50)]
    c.configure_camera_roi("EAST", [[.01,.01],[.2,.01],[.2,.2],[.01,.2]])
    snap = c.process_frames(images, 1)
    assert snap.lane_metrics["EAST"].vehicle_count == 0
    assert all(snap.lane_metrics[d].vehicle_count == 1 for d in DIRECTIONS[1:])
    assert snap.signal_active_direction == "EW"


def test_settings_reject_reusing_one_source():
    with pytest.raises(ValueError, match="independent"):
        Settings(_env_file=None, east_video="same.mp4", west_video="same.mp4")


def test_missing_camera_never_substitutes_existing_project_video(tmp_path):
    source = UploadedVideoSource(str(tmp_path / "missing.mp4"))
    with pytest.raises(VideoSourceError, match="not found"):
        source.open()


def write_video(path, width, height, value):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25, (width,height))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.full((height,width,3), value, np.uint8))
    writer.release()


def test_four_distinct_inputs_decode_and_loop_at_different_resolutions(tmp_path):
    sources = []
    try:
        for i, direction in enumerate(DIRECTIONS):
            width, height, value = 160+i*32, 120+i*24, 30+i*50
            path = tmp_path / f"{direction}.mp4"
            write_video(path, width, height, value)
            source = UploadedVideoSource(str(path))
            sources.append(source)
            source.open()
            for _ in range(5):  # includes EOF looping
                frame = source.read()
                assert frame.image.shape[:2] == (height,width)
                assert abs(float(frame.image.mean())-value) < 10
                assert frame.source_label == path.name
    finally:
        for source in sources:
            source.close()


def test_yolo_uses_one_batch_and_never_cv_fallback_on_empty_detections():
    detector = YOLODetector()
    images = {d: np.zeros((100+i*20,100,3), np.uint8) for i,d in enumerate(DIRECTIONS)}
    detector._model = Mock()
    detector._model.predict.return_value = [SimpleNamespace(boxes=[], names={}) for _ in DIRECTIONS]
    results = detector.detect_many(images, 1)
    args, kwargs = detector._model.predict.call_args
    assert len(args[0]) == 4
    assert all(a is b for a,b in zip(args[0], images.values()))
    assert all(not r.detections and not r.is_simulated for r in results.values())
    detector._model.predict.assert_called_once()


def test_slow_camera_does_not_hold_other_capture_buffers():
    from app.main import _capture_camera
    from app.core.state import CameraRuntime
    from app.services.cv.video_source import SimulationVideoSource
    class SlowSource(SimulationVideoSource):
        def read(self):
            time.sleep(.3)
            return super().read()
    cameras = {d: CameraRuntime(d, SlowSource(d) if d == "EAST" else SimulationVideoSource(d), "unused") for d in DIRECTIONS}
    runtime = SimpleNamespace(cameras=cameras, camera_status="ONLINE")
    async def exercise():
        tasks = [asyncio.create_task(_capture_camera(runtime,d)) for d in DIRECTIONS]
        try:
            await asyncio.sleep(.12)
            assert cameras["EAST"].frame is None
            assert all(cameras[d].frame is not None for d in DIRECTIONS[1:])
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.run(exercise())


def test_settings_resolve_relative_and_absolute_aliases_to_same_video():
    from pathlib import Path
    absolute = Path(__file__).resolve().parents[2] / "videos/east.mp4"
    with pytest.raises(ValueError, match="independent"):
        Settings(_env_file=None, east_video="./videos/east.mp4", west_video=str(absolute))


def test_settings_reject_empty_camera_path():
    with pytest.raises(ValueError, match="video path"):
        Settings(_env_file=None, east_video=" ")


def test_roi_scores_use_actual_classes_and_exclude_outside_vehicles():
    det = CameraDetector()
    c = controller(det)
    det.outputs["EAST"] = [Detection((47,47,53,53),"car",.9), Detection((57,57,63,63),"auto",.9),
                           Detection((37,57,43,63),"motorcycle",.9), Detection((0,0,6,6),"car",.9)]
    snap = c.process_frames({d: np.zeros((100,100,3),np.uint8) for d in DIRECTIONS},1)
    assert snap.lane_metrics["EAST"].vehicle_count == 3
    assert snap.lane_metrics["EAST"].vehicle_score == 4.5
    assert snap.demand["pair_scores"] == {"EW": 2.25, "NS": 0}
    assert snap.score_records[-1]["denser_pair"] == "EW"


def test_controller_early_switch_full_phase_and_normal_alternation():
    det = CameraDetector()
    c = controller(det)
    images = {d: np.zeros((100,100,3),np.uint8) for d in DIRECTIONS}
    for d in ("EAST","WEST"):
        det.outputs[d] = [vehicle(40+i*4,50) for i in range(3)]
    c.process_frames(images,1,dt_seconds=.2)  # establish initial EW phase with score >5
    det.outputs["EAST"] = det.outputs["WEST"] = []
    for d in ("NORTH","SOUTH"):
        det.outputs[d] = [vehicle(40+i%5*4,40+i//5*4) for i in range(25)]
    c.process_frames(images,2,dt_seconds=26.8)
    for index in range(3,6):
        snap = c.process_frames(images,index,dt_seconds=1)
    assert snap.signal_state == "YELLOW" and snap.signal_active_direction == "EW"
    assert snap.signal_target_direction == "NS" and snap.signal_countdown_s == 3
    assert snap.score_records[-1]["green_pair"] is None
    snap = c.process_frames(images,6,dt_seconds=3)
    assert snap.signal_state == "GREEN" and snap.signal_active_direction == "NS" and snap.signal_countdown_s == 70
    assert snap.demand["full_phase_required"] and snap.demand["action"] == "EARLY"
    for d in ("NORTH","SOUTH"):
        det.outputs[d] = []
    for d in ("EAST","WEST"):
        det.outputs[d] = [vehicle(40+i%5*4,40+i//5*4) for i in range(25)]
    snap = c.process_frames(images,4,dt_seconds=30)
    assert snap.signal_active_direction == "NS" and snap.signal_countdown_s == 40
    snap = c.process_frames(images,5,dt_seconds=40)
    assert snap.signal_state == "YELLOW" and snap.signal_active_direction == "NS" and snap.signal_countdown_s == 3
    assert snap.demand["action"] == "TIMER"
    snap = c.process_frames(images,7,dt_seconds=3)
    assert snap.signal_state == "GREEN" and snap.signal_active_direction == "EW" and snap.signal_countdown_s == 70
