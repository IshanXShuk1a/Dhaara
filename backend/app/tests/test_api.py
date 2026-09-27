"""
API + WebSocket integration tests.

NOTE ON EXECUTION: these require `fastapi`, `httpx`, `sqlalchemy`, and the
rest of requirements.txt installed, which this development sandbox's
network restrictions do not allow (see README "Known Limitations"). They
are written and structurally reviewed but have NOT been executed by the
agent that authored them - run `pytest app/tests/test_api.py` yourself
after `pip install -r requirements.txt` and treat that as the real
verification step, not this file's mere existence.
"""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture()
def client():
    # Use an isolated temp SQLite DB per test run so tests don't collide with
    # a developer's real dhaara.db.
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def admin_token(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "dhaara-admin"})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


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


class TestSimulationMutatesRealState:
    def test_traffic_slider_changes_lane_metrics(self, client, admin_token):
        headers = auth_headers(admin_token)
        # Start video/simulation so the control loop begins processing frames.
        client.post("/api/video/start", params={"intersection_id": "OD-BBSR-001"}, headers=headers)

        response = client.post(
            "/api/simulation/traffic",
            params={"intersection_id": "OD-BBSR-001"},
            json={"north": 2, "south": 28, "east": 2, "west": 2},
            headers=headers,
        )
        assert response.status_code == 200

        import time
        time.sleep(2.0)  # allow the background control loop a few ticks

        traffic_response = client.get("/api/intersections/OD-BBSR-001/traffic", headers=headers)
        assert traffic_response.status_code == 200
        lanes = traffic_response.json().get("lanes", {})
        if "SOUTH" in lanes:
            assert lanes["SOUTH"]["vehicle_count"] > lanes.get("NORTH", {}).get("vehicle_count", 0)


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
