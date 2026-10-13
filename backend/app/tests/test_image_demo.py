"""Image provenance, cached inference, paired timing and demonstration isolation."""
import asyncio
from pathlib import Path
import cv2
import numpy as np
import pytest
from app.services.cv.detector import FrameDetections
from app.services.cv.tracker import Detection
from app.services.cv.video_source import SourceKind, StillImageSource, VideoSourceError
from app.services.image_demo import IMAGE_CASES, IMAGE_DEMO_ID, IMAGE_FILES, create_image_demo_runtime
from app.api.websocket import runtime_to_payload


class ImageDetectorFixture:
    rickshaw_supported = False
    def __init__(self):
        self.calls = 0
    def detect_many(self, images, frame_index):
        self.calls += 1
        result = {}
        for name, image in images.items():
            code = int(image[0, 0, 0])
            count = {22: 22, 12: 12, 2: 2, 3: 2}[code]
            detections = [Detection((100+i%6*8, 40+i//6*18, 106+i%6*8, 48+i//6*18),
                          "ambulance" if code == 3 and i == 0 else "car", .95) for i in range(count)]
            detections.append(Detection((0, 0, 8, 8), "car", .9))  # outside the counted region
            result[name] = FrameDetections(detections, False, "test-image-detector")
        return result


@pytest.fixture
def image_directory(tmp_path):
    for key, filename in IMAGE_FILES.items():
        assert cv2.imwrite(str(tmp_path / filename), np.full((200, 200, 3),
                           {"heavy": 22, "normal": 12, "low": 2, "ambulance": 3}[key], np.uint8))
    return tmp_path


@pytest.fixture
def runtime(image_directory):
    runtime = create_image_demo_runtime(image_directory, ImageDetectorFixture())
    runtime.image_demo.observe(runtime)
    return runtime


def test_still_source_has_image_provenance_and_same_pixels(image_directory):
    source = StillImageSource(str(image_directory / IMAGE_FILES["low"]))
    first, second = source.read(), source.read()
    assert first.source_kind == SourceKind.STILL_IMAGE and first.source_label == "low traffic.jpeg"
    assert second.frame_index > first.frame_index and np.array_equal(first.image, second.image)
    source.close()
    assert not source.is_open()
    with pytest.raises(VideoSourceError):
        StillImageSource(str(image_directory / "missing.png")).read()


@pytest.mark.parametrize("case", IMAGE_CASES)
def test_cases_use_file_detections_and_average_the_pair(runtime, case):
    session = runtime.image_demo
    session.select_case(runtime, case["id"])
    snapshot = session.observe(runtime)
    expected = {"heavy": 44, "normal": 24, "low": 4, "ambulance": 4}
    assert snapshot.demand["pair_scores"] == {"EW": expected[case["ew"]], "NS": expected[case["ns"]]}
    assert snapshot.is_simulated is False
    assert session.catalog.detector.calls == 1
    assert session.catalog.stats["low"]["vehicle_count"] == 2
    assert session.catalog.stats["low"]["detected_total"] == 3


def test_swap_preserves_controller_clock_and_previous_phase(runtime):
    session, fsm = runtime.image_demo, runtime.controller.signal_fsm
    session.observe(runtime, 70)
    assert fsm.state.color.value == "YELLOW" and fsm.countdown_s == 3
    session.observe(runtime, 3)
    assert fsm.state.active_direction == "NS" and fsm.countdown_s == 70
    session.observe(runtime, 8)
    session.select_case(runtime, "heavy_normal", swapped=True)
    snapshot = session.observe(runtime)
    assert runtime.controller.signal_fsm is fsm and fsm.state.elapsed_s == 8
    assert fsm.state.previous_phase == "EW" and snapshot.demand["pair_scores"] == {"EW": 24, "NS": 44}
    assert session.metadata(runtime)["previous_green_pair"] == "EW"


def test_early_switch_uses_measured_low_demand_and_protects_full_phase(runtime):
    session, fsm = runtime.image_demo, runtime.controller.signal_fsm
    session.observe(runtime, 70); session.observe(runtime, 3)
    session.select_case(runtime, "heavy_low"); session.observe(runtime)
    session.observe(runtime, 3.1)
    assert fsm.state.color.value == "YELLOW" and fsm.state.target_direction == "EW"
    assert fsm.countdown_s == 3
    session.observe(runtime, 3)
    assert fsm.state.active_direction == "EW" and fsm.countdown_s == 70 and fsm.state.full_phase_required
    session.select_case(runtime, "heavy_low", swapped=True); session.observe(runtime)
    session.observe(runtime, 10)
    assert fsm.state.active_direction == "EW" and fsm.state.color.value == "GREEN"


def test_pause_and_speed_affect_only_virtual_observations(runtime):
    session = runtime.image_demo
    session.paused = True
    before = runtime.controller.signal_fsm.countdown_s
    session.step(runtime, 25)
    assert runtime.controller.signal_fsm.countdown_s == before and session.virtual_time_s == 0
    session.paused = False; session.speed = 5
    session.step(runtime, .4)
    assert session.virtual_time_s == pytest.approx(2) and runtime.controller.signal_fsm.countdown_s == pytest.approx(before - 2)


def test_lights_require_detected_ambulance_and_explicit_demo_input(runtime):
    session, fsm = runtime.image_demo, runtime.controller.signal_fsm
    with pytest.raises(ValueError):
        session.set_lights(True)
    session.select_case(runtime, "heavy_ambulance")
    session.set_lights(False)
    for _ in range(10): session.observe(runtime, .2)
    assert runtime.controller.emergency_manager.state.value != "PRIORITY_ACTIVE"
    session.set_lights(True)
    for _ in range(25): session.observe(runtime, .2)
    assert fsm.state.active_direction == "NS" and fsm.state.color.value == "GREEN"
    payload = runtime_to_payload(IMAGE_DEMO_ID, runtime)
    assert payload["emergency"]["light_confirmation_source"] == "DEMO_INPUT"
    assert payload["emergency"]["demo_lights_active"] is True
    assert payload["emergency"]["flashing_lights_confirmed"] is False
    assert "explicit demo lights ON" in payload["decision"]["reason"][0]
    session.paused = True
    session.set_lights(False)
    session.observe(runtime)
    assert runtime.controller.emergency_manager.state.value != "PRIORITY_ACTIVE"
    assert runtime_to_payload(IMAGE_DEMO_ID, runtime)["emergency"]["demo_lights_active"] is False


def test_tour_advances_only_after_yellow_completes(runtime):
    session = runtime.image_demo
    session.auto_tour = True
    session.observe(runtime, 70)
    assert session.case_id == "balanced_heavy"
    session.observe(runtime, 3)
    assert session.case_id == "heavy_normal" and runtime.controller.signal_fsm.state.active_direction == "NS"
    assert runtime.controller.signal_fsm.countdown_s == 70
    assert len(session.transitions) == 2
    assert session.transitions[0]["from_state"] == "GREEN" and session.transitions[0]["to_state"] == "YELLOW"
    assert session.transitions[1]["to_state"] == "GREEN"


def test_cache_reloads_edited_image_instead_of_reusing_old_counts(runtime, image_directory):
    session = runtime.image_demo
    assert session.catalog.detector.calls == 1
    cv2.imwrite(str(image_directory / IMAGE_FILES["heavy"]), np.full((200, 200, 3), 12, np.uint8))
    session.select_case(runtime, "balanced_heavy")
    assert session.observe(runtime).demand["pair_scores"]["EW"] == 24
    assert session.catalog.detector.calls == 2


def test_ambulance_preset_starts_demo_lights_and_still_requires_yellow(runtime):
    session, fsm = runtime.image_demo, runtime.controller.signal_fsm
    session.select_case(runtime, "heavy_ambulance")
    assert session.lights_active and session.lights_until_s == 12
    session.observe(runtime)
    assert fsm.state.color.value == "GREEN" and fsm.state.active_direction == "EW"
    for _ in range(10): session.step(runtime, .2)
    assert fsm.state.color.value == "YELLOW" and fsm.state.target_direction == "NS"
    for _ in range(15): session.step(runtime, .2)
    assert fsm.state.color.value == "GREEN" and fsm.state.active_direction == "NS"
    session.step(runtime, 7.2)
    assert not session.lights_active
    assert not any(runtime.controller.last_snapshot.ambulance_lights.values())


def test_paused_source_edit_refreshes_counts_without_advancing_clock(runtime, image_directory):
    session = runtime.image_demo
    session.paused = True
    before = runtime.controller.signal_fsm.countdown_s
    cv2.imwrite(str(image_directory / IMAGE_FILES["heavy"]), np.full((200, 200, 3), 12, np.uint8))
    snapshot = session.step(runtime, 25)
    assert snapshot.demand["pair_scores"] == {"EW": 24, "NS": 24}
    assert session.virtual_time_s == 0 and snapshot.signal_countdown_s == before


def test_image_sessions_have_distinct_stable_identity(image_directory, runtime):
    session = runtime.image_demo
    identity = session.metadata(runtime)["session_id"]
    session.select_case(runtime, "heavy_normal")
    assert session.metadata(runtime)["session_id"] == identity
    other = create_image_demo_runtime(image_directory, ImageDetectorFixture())
    assert other.image_demo.metadata(other)["session_id"] != identity


@pytest.fixture
def image_client(image_directory, tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import database
    from app import main
    from app.core.state import app_state
    from fastapi.testclient import TestClient
    engine = create_engine(f"sqlite:///{tmp_path / 'images-api.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(main.settings, "image_demo_enabled", True)
    monkeypatch.setattr(main.settings, "image_demo_dir", str(image_directory))
    monkeypatch.setattr(main, "shared_detector", ImageDetectorFixture())
    async def idle_loop():
        await asyncio.Event().wait()
    monkeypatch.setattr(main, "_control_loop", idle_loop)
    with TestClient(main.app) as client:
        app_state.get(IMAGE_DEMO_ID).image_demo.observe(app_state.get(IMAGE_DEMO_ID))
        token = client.post('/api/auth/login', json={"username": "admin", "password": "dhaara-admin"}).json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}
    engine.dispose()


def test_api_sources_and_live_controller_remain_separate(image_client):
    from app.core.state import app_state
    from app.models.events import SystemEventRecord
    from app.database.database import session_scope
    client, headers = image_client
    live = app_state.get("OD-BBSR-001")
    original = (live.controller, {d: camera.source for d, camera in live.cameras.items()})
    response = client.post('/api/image-demo/case', json={"case_id": "heavy_low"}, headers=headers)
    assert response.status_code == 200 and response.json()["demand"]["pair_scores"] == {"EW": 44, "NS": 4}
    assert live.controller is original[0] and all(camera.source is original[1][d] for d, camera in live.cameras.items())
    entries = client.get('/api/intersections', headers=headers).json()
    assert next(item for item in entries if item['id'] == IMAGE_DEMO_ID)['input_mode'] == "IMAGE_DEMO"
    assert IMAGE_DEMO_ID not in client.get('/api/health').json()['intersections_online']
    assert client.post('/api/image-demo/control', json={"lights_active": True}, headers=headers).status_code == 409
    assert client.post('/api/image-demo/control', json={"speed": 20}, headers=headers).status_code == 422
    assert client.post('/api/video/start', params={"intersection_id": IMAGE_DEMO_ID}, headers=headers).status_code == 409
    frame = client.get('/api/video/frame', params={"intersection_id": IMAGE_DEMO_ID, "direction": "EAST"})
    assert frame.status_code == 200 and frame.headers['content-type'] == 'image/jpeg'
    cameras = client.get('/api/video/status', params={"intersection_id": IMAGE_DEMO_ID}, headers=headers).json()['cameras']
    assert all(camera['status'] == 'ONLINE' and camera['width'] == 200 for camera in cameras.values())
    with session_scope() as db:
        assert db.query(SystemEventRecord).filter(SystemEventRecord.intersection_id == IMAGE_DEMO_ID).count() == 0


def test_demo_controls_require_authentication(image_client):
    client, _ = image_client
    assert client.post('/api/image-demo/case', json={"case_id": "heavy_low"}).status_code == 401
    assert client.get('/api/image-demo').status_code == 401


def test_api_ambulance_selection_needs_no_second_lights_click(image_client):
    from app.core.state import app_state
    client, headers = image_client
    response = client.post('/api/image-demo/case', json={"case_id": "heavy_ambulance"}, headers=headers)
    assert response.status_code == 200 and response.json()["image_demo"]["lights_active"]
    runtime = app_state.get(IMAGE_DEMO_ID)
    runtime.image_demo.step(runtime, 5)
    assert client.get('/api/image-demo', headers=headers).json()["signal"]["active_direction"] == "NS"


@pytest.mark.parametrize("intersection_id", [IMAGE_DEMO_ID, "SIMULATION-LAB"])
def test_roi_mutation_cannot_change_educational_runtime_or_persist_rows(image_client, intersection_id):
    from app.core.state import app_state
    from app.models.lane import Lane
    from app.database.database import session_scope
    client, headers = image_client
    entries = client.get('/api/intersections/OD-BBSR-001/lanes', headers=headers).json()
    runtime = app_state.get(intersection_id)
    before = dict(runtime.controller._camera_rois)
    assert client.put(f'/api/intersections/{intersection_id}/lanes', json=entries, headers=headers).status_code == 409
    assert runtime.controller._camera_rois == before
    with session_scope() as db:
        assert db.query(Lane).filter(Lane.intersection_id == intersection_id).count() == 0


def test_paused_lab_ambulance_response_contains_current_detection(image_client):
    client, headers = image_client
    client.post('/api/simulation/control', json={"paused": True}, headers=headers)
    response = client.post('/api/simulation/ambulance', json={"direction": "NORTH", "lights_active": False}, headers=headers)
    body = response.json()
    assert response.status_code == 200 and body["simulation"]["paused"]
    assert body["emergency"]["state"] == "DETECTED"
    assert body["simulation"]["simulated_time_s"] == 0
    assert body["demand"]["pair_scores"] == {"EW": 16, "NS": 16}
