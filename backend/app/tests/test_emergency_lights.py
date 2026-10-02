import numpy as np
import pytest
from app.services.cv.emergency_lights import EmergencyLightTracker
from app.services.cv.tracker import Detection
from app.services.cv.lane_assigner import DIRECTIONS
from app.tests.test_four_cameras import CameraDetector, controller


def frame(lights=False):
    image = np.full((100,100,3),80,np.uint8)
    if lights:
        image[40:45,45:55] = (0,0,255)
    return image


def test_flashing_beacon_requires_multiple_on_off_transitions():
    tracker = EmergencyLightTracker()
    bbox = (40,40,60,70)
    assert not tracker.observe(1,frame(True),bbox,0)
    assert not tracker.observe(1,frame(False),bbox,.2)
    assert not tracker.observe(1,frame(True),bbox,.4)
    assert tracker.observe(1,frame(False),bbox,.6)
    assert not tracker.observe(1,frame(False),bbox,1.3)


@pytest.mark.parametrize("lights", [True,False])
def test_steady_lights_or_no_lights_never_confirm_flashing(lights):
    tracker = EmergencyLightTracker()
    for i in range(20):
        assert not tracker.observe(1,frame(lights),(40,40,60,70),i*.2)


def test_tracks_cannot_share_beacon_confirmation():
    tracker = EmergencyLightTracker()
    for i in range(8):
        assert not tracker.observe(i,frame(i%2==0),(40,40,60,70),i*.2)


@pytest.mark.parametrize("flashing", [True,False])
def test_stationary_ambulance_changes_paired_signal_only_with_flashing_lights(monkeypatch,flashing):
    detector = CameraDetector()
    detector.outputs["NORTH"] = [Detection((40,40,60,70),"ambulance",.95)]
    c = controller(detector)
    now = [100.0]
    monkeypatch.setattr("app.services.controllers.intersection_controller.time.time",lambda: now[0])
    for i in range(30):
        now[0] = 100+i*.2
        images = {d:frame() for d in DIRECTIONS}
        images["NORTH"] = frame(flashing and i%2==0)
        snap = c.process_frames(images,i,dt_seconds=.2)
    assert snap.signal_active_direction == ("NS" if flashing else "EW")
    assert snap.direction_signals["NORTH"] == snap.direction_signals["SOUTH"]
    assert snap.emergency_state == ("PRIORITY_ACTIVE" if flashing else "DETECTED")
    detector.outputs["NORTH"] = []
    for i in range(6):
        now[0] += .2
        snap = c.process_frames({d:frame() for d in DIRECTIONS},20+i)
    assert snap.emergency_state == "NONE"
    assert snap.ambulance_lights == {}


def test_flashing_ambulance_outside_measurement_roi_still_gets_camera_pair_priority(monkeypatch):
    detector = CameraDetector()
    detector.outputs["NORTH"] = [Detection((5,5,25,35),"ambulance",.95)]
    c = controller(detector)
    now = [100.0]
    monkeypatch.setattr("app.services.controllers.intersection_controller.time.time",lambda: now[0])
    for i in range(30):
        now[0] = 100+i*.2
        images = {d:frame() for d in DIRECTIONS}
        if i%2 == 0:
            images["NORTH"][5:10,10:20] = (0,0,255)
        snap = c.process_frames(images,i)
    assert snap.lane_metrics["NORTH"].vehicle_score == 0
    assert snap.signal_active_direction == "NS" and snap.emergency_state == "PRIORITY_ACTIVE"


def test_ambulance_request_cannot_skip_yellow_and_is_cancelled_when_lights_stop(monkeypatch):
    detector = CameraDetector()
    detector.outputs["NORTH"] = [Detection((40,40,60,70),"ambulance",.95)]
    c = controller(detector)
    now = [100.0]
    monkeypatch.setattr("app.services.controllers.intersection_controller.time.time",lambda: now[0])
    for i in range(8):
        now[0] = 100+i*.2
        images = {d:frame() for d in DIRECTIONS}
        images["NORTH"] = frame(i%2==0)
        snap = c.process_frames(images,i)
    assert snap.signal_state == "YELLOW" and snap.signal_target_direction == "NS"
    assert snap.direction_signals == dict(EAST="YELLOW",WEST="YELLOW",NORTH="RED",SOUTH="RED")
    assert snap.emergency_state == "PRIORITY_REQUESTED"
    detector.outputs["NORTH"] = []
    for i in range(16):
        now[0] += .2
        snap = c.process_frames({d:frame() for d in DIRECTIONS},8+i)
        assert snap.signal_active_direction == "EW"
        assert snap.direction_signals["NORTH"] == "RED"
    assert snap.signal_state == "GREEN" and snap.emergency_state == "NONE"
