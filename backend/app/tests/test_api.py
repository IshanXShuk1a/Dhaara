"""API and WebSocket integration tests with isolated per-test SQLite engines."""
from __future__ import annotations

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import database
    from app.main import app
    from fastapi.testclient import TestClient
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=test_engine))
    with TestClient(app) as test_client:
        yield test_client
    test_engine.dispose()


@pytest.fixture()
def admin_token(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "dhaara-admin"})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        from app.core.state import app_state
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "SIMULATION-LAB" not in payload["intersections_online"]
        live = {iid for iid, runtime in app_state.runtimes.items() if runtime.simulation_lab is None}
        assert set(payload["intersections_online"]) <= live
        assert payload["intersection_count"] == len(live) == 1
        assert payload["simulation_available"]


class TestAuth:
    def test_login_success(self, client):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "dhaara-admin"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password_rejected(self, client):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 401

    def test_protected_route_requires_token(self, client):
        response = client.get("/api/intersections")
        assert response.status_code == 401


class TestIntersections:
    def test_default_intersection_registered(self, client, admin_token):
        response = client.get("/api/intersections", headers=auth_headers(admin_token))
        assert response.status_code == 200
        ids = [i["id"] for i in response.json()]
        assert "OD-BBSR-001" in ids

    def test_create_requires_admin_role(self, client):
        # A VIEWER-role token (would need seeding a viewer user in a fuller
        # test) is out of scope here; this at minimum verifies the route is
        # wired and rejects unauthenticated requests.
        response = client.post("/api/intersections", json={"id": "TEST-002", "name": "Test"})
        assert response.status_code == 401


class TestSimulationIsolation:
    def test_traffic_slider_changes_lane_metrics(self, client, admin_token):
        from app.core.state import app_state
        headers = auth_headers(admin_token)
        live = app_state.get("OD-BBSR-001")
        live_controller = live.controller
        live_detector = live.controller._detector
        live_sources = {d: c.source for d, c in live.cameras.items()}
        response = client.post(
            "/api/simulation/traffic",
            json={"north": 2, "south": 28, "east": 2, "west": 2},
            headers=headers,
        )
        assert response.status_code == 200
        lanes = response.json()["lanes"]
        assert lanes["SOUTH"]["vehicle_count"] == 28
        assert lanes["SOUTH"]["vehicle_score"] == 56
        assert lanes["NORTH"]["vehicle_count"] == 2
        assert live.controller is live_controller and live.controller._detector is live_detector
        assert not live.is_simulated and all(live.cameras[d].source is s for d, s in live_sources.items())
        assert live.scenario_provider is None and live.scenario_builder is None

    @pytest.mark.parametrize("endpoint,body", [
        ("start", None), ("reset", None),
        ("traffic", {"north": 20}), ("ambulance", {"direction": "NORTH"}),
        ("scenario", {"scenario": "ns_busy"}), ("control", {"paused": True}),
    ])
    def test_simulation_endpoint_rejects_live_intersection(self, client, admin_token, endpoint, body):
        from app.core.state import app_state
        live = app_state.get("OD-BBSR-001")
        controller, sources = live.controller, {d: c.source for d, c in live.cameras.items()}
        response = client.post(f"/api/simulation/{endpoint}", params={"intersection_id": "OD-BBSR-001"},
                               json=body, headers=auth_headers(admin_token))
        assert response.status_code == 409
        assert live.controller is controller and not live.is_simulated
        assert all(live.cameras[d].source is source for d, source in sources.items())

    def test_lab_excluded_from_live_nodes_and_persistent_records(self, client, admin_token):
        import time
        from app.core.state import app_state
        from app.database.database import session_scope
        from app.models.events import SystemEventRecord
        from app.models.traffic import TrafficSnapshot
        headers = auth_headers(admin_token)
        ids = [i["id"] for i in client.get("/api/intersections", headers=headers).json()]
        assert "SIMULATION-LAB" not in ids
        assert "SIMULATION-LAB" not in app_state.coordinator.all_ids()
        client.post("/api/simulation/scenario", json={"scenario": "empty_ew"}, headers=headers)
        time.sleep(.5)
        with session_scope() as db:
            assert db.query(SystemEventRecord).filter_by(intersection_id="SIMULATION-LAB").count() == 0
            assert db.query(TrafficSnapshot).filter_by(intersection_id="SIMULATION-LAB").count() == 0

    def test_readonly_user_can_operate_only_the_isolated_lab(self, client):
        from app.core.auth import hash_password
        from app.database.database import session_scope
        from app.models.user import User
        with session_scope() as db:
            db.add(User(username="student", hashed_password=hash_password("student-pass"), role="VIEWER"))
        token = client.post("/api/auth/login", json={"username":"student", "password":"student-pass"}).json()["access_token"]
        headers = auth_headers(token)
        response = client.post("/api/simulation/scenario", json={"scenario":"ew_busy"}, headers=headers)
        assert response.status_code == 200 and response.json()["demand"]["pair_scores"] == {"EW":36,"NS":8}
        assert client.post("/api/intersections/OD-BBSR-001/signal/override", json={"direction":"NORTH"}, headers=headers).status_code == 403

    def test_pause_speed_and_websocket_metadata(self, client, admin_token):
        import time
        headers = auth_headers(admin_token)
        response = client.post("/api/simulation/control", json={"paused":True,"speed":5}, headers=headers)
        assert response.status_code == 200
        before = response.json()
        time.sleep(.3)
        after = client.get("/api/simulation/state",headers=headers).json()
        assert before["frame_index"] == after["frame_index"]
        assert before["signal"]["countdown_s"] == after["signal"]["countdown_s"]
        assert after["simulation"]["paused"] and after["simulation"]["speed"] == 5
        with client.websocket_connect("/ws/intersections/SIMULATION-LAB") as ws:
            payload = ws.receive_json()
            assert payload["simulation"] == after["simulation"]
            assert payload["is_simulated"]
        assert client.post("/api/simulation/control",json={"speed":100},headers=headers).status_code == 422
        assert client.post("/api/video/start",params={"intersection_id":"SIMULATION-LAB"},headers=headers).status_code == 409

    def test_ambulance_metadata_and_traffic_validation(self, client, admin_token):
        headers = auth_headers(admin_token)
        response = client.post("/api/simulation/ambulance",json={"direction":"NORTH","lights_active":False},headers=headers)
        assert response.status_code == 200
        assert response.json()["simulation"]["ambulance"] == {"direction":"NORTH","lights_active":False}
        assert client.post("/api/simulation/ambulance",json={"direction":"INVALID"},headers=headers).status_code == 422
        assert client.post("/api/simulation/traffic",json={"north":31},headers=headers).status_code == 422


class TestSignalEndpoint:
    def test_get_signal_state(self, client, admin_token):
        response = client.get("/api/intersections/OD-BBSR-001/signal", headers=auth_headers(admin_token))
        assert response.status_code == 200
        body = response.json()
        assert body["color"] in ("GREEN", "YELLOW", "ALL_RED")


class TestWebSocket:
    def test_websocket_connects_and_receives_initial_state(self, client):
        with client.websocket_connect("/ws/intersections/OD-BBSR-001") as websocket:
            data = websocket.receive_json()
            assert data["intersection_id"] == "OD-BBSR-001"

    def test_websocket_unknown_intersection_closes(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/intersections/DOES-NOT-EXIST") as websocket:
                websocket.receive_json()


class TestFourCameraFlow:
    def test_independent_uploads_frames_rest_and_websocket(self, client, admin_token, tmp_path, monkeypatch):
        import cv2
        import numpy as np
        import time
        from app.core.state import app_state
        from app.services.cv.lane_assigner import DIRECTIONS
        from app.services.cv.detector import FrameDetections
        from app.services.cv.tracker import Detection
        from app.tests.test_four_cameras import write_video
        from app.api.routes import video as video_routes
        monkeypatch.setattr(video_routes, "UPLOAD_DIR", tmp_path / "uploads")
        runtime = app_state.get("OD-BBSR-001")
        counts = dict(EAST=12, WEST=5, NORTH=8, SOUTH=3)
        class Detector:
            def detect_many(self, images, frame_index):
                return {d: FrameDetections([Detection((45+i*2,40,51+i*2,50), "car", .9)
                        for i in range(counts[d])], False, "test") for d in images}
        with runtime.lock:
            runtime.real_detector = runtime.controller._detector = Detector()
        headers = auth_headers(admin_token)
        paths = []
        for i,d in enumerate(DIRECTIONS):
            path = tmp_path / f"{d}.mp4"
            write_video(path, 160, 120, 30+i*50)
            with path.open("rb") as video:
                response = client.post("/api/video/upload", params={"intersection_id":"OD-BBSR-001", "direction":d},
                                       files={"file":(path.name,video,"video/mp4")}, headers=headers)
            assert response.status_code == 200
            assert response.json()["direction"] == d
            paths.append(response.json()["path"])
        assert len(set(paths)) == 4
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            snap = runtime.controller.last_snapshot
            if snap and all(snap.lane_metrics[d].vehicle_count == counts[d] for d in DIRECTIONS):
                break
            time.sleep(.05)
        else:
            pytest.fail("Four camera counts did not update")
        for i,d in enumerate(DIRECTIONS):
            response = client.get("/api/video/frame", params={"intersection_id":"OD-BBSR-001", "direction":d,
                "show_lanes":"false", "show_boxes":"false", "show_labels":"false", "show_heat":"false"})
            assert response.status_code == 200
            image = cv2.imdecode(np.frombuffer(response.content,np.uint8),cv2.IMREAD_COLOR)
            assert image.shape[:2] == (120,160)  # full input, no directional crop
            assert abs(float(image[90:110].mean())-(30+i*50)) < 10
        response = client.get("/api/video/frame", params={"intersection_id":"OD-BBSR-001", "direction":"INVALID"})
        assert response.status_code == 400
        signal = client.get("/api/intersections/OD-BBSR-001/signal",headers=headers).json()
        assert signal["directions"] == dict(EAST="GREEN",WEST="GREEN",NORTH="RED",SOUTH="RED")
        assert signal["active_direction"] == "EW"
        assert signal["decision"]["pair_scores"] == {"EW":17,"NS":11}
        traffic = client.get("/api/intersections/OD-BBSR-001/traffic",headers=headers).json()
        assert traffic["lanes"]["EAST"]["vehicle_score"] == 24
        assert traffic["lanes"]["EAST"]["vehicle_counts"] == {"car":12}
        history = client.get("/api/intersections/OD-BBSR-001/traffic/scores/history",headers=headers).json()
        assert any(record["pair_scores"] == {"EW":17,"NS":11} and record["denser_pair"] == "EW" for record in history["records"])
        with client.websocket_connect("/ws/intersections/OD-BBSR-001") as ws:
            payload = ws.receive_json()
            assert all(payload["lanes"][d]["vehicle_count"] == counts[d] for d in DIRECTIONS)
            assert all(payload["cameras"][d]["status"] == "ONLINE" for d in DIRECTIONS)
            assert payload["signal"]["directions"] == signal["directions"]

    def test_roi_configuration_is_validated_and_applies_live(self, client, admin_token):
        from app.core.state import app_state
        headers = auth_headers(admin_token)
        endpoint = "/api/intersections/OD-BBSR-001/lanes"
        entries = client.get(endpoint, headers=headers).json()
        assert len(entries) == 4
        assert all(e["coordinate_space"] == "normalized" for e in entries)
        entries[0]["polygon"] = [[.01,.01],[.2,.01],[.2,.2],[.01,.2]]
        assert client.put(endpoint,json=entries,headers=headers).status_code == 200
        runtime = app_state.get("OD-BBSR-001")
        assert runtime.controller._camera_rois[entries[0]["direction"]] == [tuple(p) for p in entries[0]["polygon"]]
        assert client.put(endpoint,json=entries[:3],headers=headers).status_code == 400
        entries[0]["polygon"] = [[0,0],[1,1],[0,1],[1,0]]
        assert client.put(endpoint,json=entries,headers=headers).status_code == 422

    def test_directional_upload_requires_valid_direction(self, client, admin_token):
        response = client.post("/api/video/upload",params={"intersection_id":"OD-BBSR-001", "direction":"LANE1"},
                               files={"file":("test.mp4",b"invalid","video/mp4")},headers=auth_headers(admin_token))
        assert response.status_code == 400


class TestLiveConfiguration:
    def test_invalid_update_does_not_partially_change_settings(self, client, admin_token):
        from app.core.state import app_state
        headers = auth_headers(admin_token)
        original = client.get("/api/config",headers=headers).json()
        response = client.put("/api/config",headers=headers,json={"detection":{"yolo_confidence":.2}, "signal_timings":{"fixed_phase_s":0}})
        assert response.status_code == 422
        assert client.get("/api/config",headers=headers).json() == original
        response = client.put("/api/config",headers=headers,json={"detection":{"yolo_confidence":.31}})
        assert response.status_code == 200
        assert app_state.get("OD-BBSR-001").real_detector._confidence_threshold == .31
        assert client.put("/api/config",headers=headers,json=original).status_code == 200

    def test_invalid_manual_override_preserves_mode(self, client, admin_token):
        headers = auth_headers(admin_token)
        endpoint = "/api/intersections/OD-BBSR-001/signal"
        response = client.post(endpoint+"/override",headers=headers,json={"direction":"INVALID"})
        assert response.status_code == 400
        assert client.get(endpoint,headers=headers).json()["mode"] == "ADAPTIVE"


def test_cleanup_removes_only_seeded_demo_nodes_without_real_cameras(client):
    from app.database.database import session_scope
    from app.models.intersection import Intersection
    from app.models.camera import Camera
    from app.main import _remove_seeded_demo_nodes
    with session_scope() as db:
        db.add(Intersection(id="OD-BBSR-002",name="Vani Vihar Junction",location="NH-16 / Utkal University"))
        db.add(Intersection(id="OD-BBSR-003",name="Rasulgarh Square",location="Cuttack-Puri Bypass"))
        db.add(Intersection(id="OD-BBSR-004",name="User configured node",location="User road"))
        db.add(Camera(id="real",intersection_id="OD-BBSR-003",source_type="UPLOADED_FILE",source_url="actual.mp4"))
    _remove_seeded_demo_nodes()
    with session_scope() as db:
        assert db.get(Intersection,"OD-BBSR-002") is None
        assert db.get(Intersection,"OD-BBSR-003") is not None
        assert db.get(Intersection,"OD-BBSR-004") is not None


def test_manual_override_exposes_yellow_in_rest_and_websocket(client,admin_token,monkeypatch):
    from app.core.state import app_state
    monkeypatch.setattr(app_state.get("OD-BBSR-001").controller.signal_fsm,"_clock",None)
    headers = auth_headers(admin_token)
    endpoint = "/api/intersections/OD-BBSR-001/signal"
    response = client.post(endpoint+"/override",headers=headers,json={"direction":"NORTH"})
    assert response.status_code == 200 and response.json()["status"] == "TRANSITIONING"
    state = client.get(endpoint,headers=headers).json()
    assert state["color"] == "YELLOW" and state["target_direction"] == "NS"
    assert 0 < state["countdown_s"] <= 3
    assert state["directions"] == dict(EAST="YELLOW",WEST="YELLOW",NORTH="RED",SOUTH="RED")
    assert client.post(endpoint+"/override",headers=headers,json={"direction":"EAST"}).status_code == 409
    runtime = app_state.get("OD-BBSR-001")
    with runtime.lock:
        runtime.controller.process_frames({},1,dt_seconds=0)
    with client.websocket_connect("/ws/intersections/OD-BBSR-001") as ws:
        payload = ws.receive_json()
        assert payload["signal"]["state"] == "YELLOW"
        assert payload["signal"]["directions"] == state["directions"]
        assert payload["signal"]["target_direction"] == "NS"
    with runtime.lock:
        snap = runtime.controller.process_frames({},2,dt_seconds=3)
    assert snap.signal_state == "GREEN" and snap.signal_active_direction == "NS"
    assert snap.signal_countdown_s == 70


def test_config_cannot_disable_yellow(client,admin_token):
    headers = auth_headers(admin_token)
    original = client.get("/api/config",headers=headers).json()
    response = client.put("/api/config",headers=headers,json={"signal_timings":{"yellow_s":0}})
    assert response.status_code == 422
    assert client.get("/api/config",headers=headers).json() == original
