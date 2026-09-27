"""
DHAARA FastAPI application entrypoint.

Startup sequence (see `on_startup`):
  1. Initialize the database (create tables if missing).
  2. Seed a default ADMIN user if none exists (so auth works out of the box
     in a fresh dev deployment - operators should change this password).
  3. Register the default demo intersection (OD-BBSR-001) with its lane
     geometry and a SimulationDetector-backed IntersectionController.
  4. Launch the background control loop as an asyncio task: it reads frames
     from each intersection's VideoSource, calls
     IntersectionController.process_frame, persists a snapshot periodically,
     and broadcasts the result over WebSocket.

Run: `uvicorn app.main:app --reload` (see README for full instructions).
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.state import app_state, IntersectionRuntime
from app.database.database import init_db, session_scope
from app.models.user import User
from app.core.auth import hash_password
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import SimulationDetector
from app.services.cv.lane_assigner import LanePolygon
from app.services.cv.video_source import SimulationVideoSource
from app.services.emergency.ambulance_analyzer import IntersectionCenter
from app.services.simulation.simulation_engine import ScenarioProvider, SimulationScenarioBuilder, TrafficSliderState
from app.services.analytics.analytics_service import AnalyticsService
from app.services.event_bus import event_bus, Event, EventType

from app.api.routes import (
    health, auth, intersections, lanes, traffic, signals, video, emergency, safety, analytics, simulation, events, config,
)
from app.api.websocket import router as websocket_router, connection_manager

logger = get_logger("dhaara.main")

app = FastAPI(title="DHAARA", description="AI-Powered Adaptive Traffic Management System")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, auth.router, intersections.router, lanes.router, traffic.router,
               signals.router, video.router, emergency.router, safety.router, analytics.router,
               simulation.router, events.router, config.router, websocket_router):
    app.include_router(router)

DEFAULT_INTERSECTION_ID = "OD-BBSR-001"
WIDTH, HEIGHT = 640, 480
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2

DEFAULT_LANES = [
    LanePolygon(lane_id="NORTH", direction="NORTH", polygon=[(CENTER_X - 60, 0), (CENTER_X + 60, 0), (CENTER_X + 60, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y - 60)]),
    LanePolygon(lane_id="SOUTH", direction="SOUTH", polygon=[(CENTER_X - 60, CENTER_Y + 60), (CENTER_X + 60, CENTER_Y + 60), (CENTER_X + 60, HEIGHT), (CENTER_X - 60, HEIGHT)]),
    LanePolygon(lane_id="EAST", direction="EAST", polygon=[(CENTER_X + 60, CENTER_Y - 60), (WIDTH, CENTER_Y - 60), (WIDTH, CENTER_Y + 60), (CENTER_X + 60, CENTER_Y + 60)]),
    LanePolygon(lane_id="WEST", direction="WEST", polygon=[(0, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y - 60), (CENTER_X - 60, CENTER_Y + 60), (0, CENTER_Y + 60)]),
]
DEFAULT_LANE_BBOXES = {
    "NORTH": (CENTER_X - 60, 10, CENTER_X + 60, CENTER_Y - 70),
    "SOUTH": (CENTER_X - 60, CENTER_Y + 70, CENTER_X + 60, HEIGHT - 10),
    "EAST": (CENTER_X + 70, CENTER_Y - 60, WIDTH - 10, CENTER_Y + 60),
    "WEST": (10, CENTER_Y - 60, CENTER_X - 70, CENTER_Y + 60),
}

from app.services.controllers.regional_coordinator import RegionalTrafficCoordinator
regional_coordinator = RegionalTrafficCoordinator()

_control_loop_task: asyncio.Task | None = None


def _subscribe_event_persistence() -> None:
    from app.models.events import SystemEventRecord

    def _persist(event: Event) -> None:
        try:
            with session_scope() as db:
                db.add(SystemEventRecord(
                    intersection_id=event.intersection_id,
                    event_type=event.type.value if hasattr(event.type, "value") else str(event.type),
                    message=event.message,
                    severity=event.severity,
                    metadata_json=event.metadata or {},
                    timestamp=event.timestamp,
                ))
        except Exception:
            pass

    event_bus.subscribe(_persist)


def _seed_admin_user() -> None:
    with session_scope() as db:
        if db.query(User).count() == 0:
            db.add(User(username="admin", hashed_password=hash_password("dhaara-admin"), role="ADMIN"))
            logger.warning("Seeded default admin user 'admin' / 'dhaara-admin' - CHANGE THIS PASSWORD before any real deployment.")


def _register_default_intersection() -> None:
    from app.models.intersection import Intersection
    from app.models.lane import Lane

    with session_scope() as db:
        if db.get(Intersection, DEFAULT_INTERSECTION_ID) is None:
            db.add(Intersection(id=DEFAULT_INTERSECTION_ID, name="Master Canteen Square", location="Bhubaneswar Central", status="ONLINE"))
        for lane in DEFAULT_LANES:
            if db.get(Lane, f"{DEFAULT_INTERSECTION_ID}:{lane.direction}") is None:
                db.add(Lane(
                    id=f"{DEFAULT_INTERSECTION_ID}:{lane.direction}",
                    intersection_id=DEFAULT_INTERSECTION_ID,
                    direction=lane.direction,
                    polygon=[list(p) for p in lane.polygon],
                    pixels_per_meter=lane.pixels_per_meter,
                ))

    provider = ScenarioProvider()
    builder = SimulationScenarioBuilder(provider, DEFAULT_LANE_BBOXES)
    detector = SimulationDetector(provider)
    controller = IntersectionController(
        intersection_id=DEFAULT_INTERSECTION_ID,
        lanes=DEFAULT_LANES,
        directions=["NORTH", "SOUTH", "EAST", "WEST"],
        detector=detector,
        intersection_center=IntersectionCenter(x=CENTER_X, y=CENTER_Y),
    )
    video_source = SimulationVideoSource(settings.video_source)
    app_state.register(
        DEFAULT_INTERSECTION_ID,
        IntersectionRuntime(
            controller=controller,
            video_source=video_source,
            scenario_provider=provider,
            scenario_builder=builder,
            lanes=DEFAULT_LANES,
            camera_status="ONLINE",
        ),
    )
    builder.apply_slider_state(
        TrafficSliderState(north=6, south=14, east=9, west=4),
        current_frame=0,
    )
    regional_coordinator.register(controller)
    logger.info(f"Registered default intersection {DEFAULT_INTERSECTION_ID}")


def _register_regional_intersections() -> None:
    from app.models.intersection import Intersection
    from app.models.lane import Lane

    specs = [
        ("OD-BBSR-002", "Vani Vihar Junction", "NH-16 / Utkal University", "ONLINE", TrafficSliderState(north=8, south=10, east=12, west=6)),
        ("OD-BBSR-003", "Rasulgarh Square", "Cuttack-Puri Bypass", "HIGH_TRAFFIC", TrafficSliderState(north=22, south=26, east=18, west=15)),
        ("OD-BBSR-004", "Khandagiri Chowk", "Khandagiri / Baramunda", "EMERGENCY", TrafficSliderState(north=5, south=7, east=4, west=25)),
    ]

    for int_id, name, location, status, sliders in specs:
        with session_scope() as db:
            if db.get(Intersection, int_id) is None:
                db.add(Intersection(id=int_id, name=name, location=location, status=status))
            for lane in DEFAULT_LANES:
                lane_key = f"{int_id}:{lane.direction}"
                if db.get(Lane, lane_key) is None:
                    db.add(Lane(
                        id=lane_key,
                        intersection_id=int_id,
                        direction=lane.direction,
                        polygon=[list(p) for p in lane.polygon],
                        pixels_per_meter=lane.pixels_per_meter,
                    ))

        provider = ScenarioProvider()
        builder = SimulationScenarioBuilder(provider, DEFAULT_LANE_BBOXES)
        detector = SimulationDetector(provider)
        controller = IntersectionController(
            intersection_id=int_id,
            lanes=DEFAULT_LANES,
            directions=["NORTH", "SOUTH", "EAST", "WEST"],
            detector=detector,
            intersection_center=IntersectionCenter(x=CENTER_X, y=CENTER_Y),
        )
        video_source = SimulationVideoSource(settings.video_source)
        app_state.register(
            int_id,
            IntersectionRuntime(
                controller=controller,
                video_source=video_source,
                scenario_provider=provider,
                scenario_builder=builder,
                lanes=DEFAULT_LANES,
                camera_status="ONLINE",
            ),
        )
        builder.apply_slider_state(sliders, current_frame=0)
        if int_id == "OD-BBSR-004":
            builder.spawn_ambulance("WEST", current_frame=0)
        regional_coordinator.register(controller)
        logger.info(f"Registered regional intersection {int_id} ({name})")


async def _control_loop() -> None:
    tick_hz = 10.0
    persist_every_n_ticks = 25
    tick_count = 0

    for runtime in app_state.runtimes.values():
        try:
            runtime.video_source.open()
        except Exception as exc:
            logger.error(f"Video source failed to open: {exc}")
            runtime.camera_status = "OFFLINE"

    try:
        while True:
            tick_count += 1
            for intersection_id, runtime in app_state.runtimes.items():
                if runtime.camera_status != "ONLINE":
                    continue
                try:
                    if not runtime.video_source.is_open():
                        runtime.video_source.open()
                    frame = runtime.video_source.read()
                except Exception as exc:
                    logger.warning(f"[{intersection_id}] video read failed, looping source: {exc}")
                    with contextlib.suppress(Exception):
                        runtime.video_source.close()
                        runtime.video_source.open()
                    continue

                runtime.frame_index = frame.frame_index
                runtime.last_frame_image = frame.image
                snapshot = runtime.controller.process_frame(frame.image, frame.frame_index, dt_seconds=1 / tick_hz)
                runtime.hardware_controller.apply_state(intersection_id, runtime.controller.signal_fsm.state)

                if snapshot.decision is not None:
                    with contextlib.suppress(Exception), session_scope() as db:
                        AnalyticsService(db).record_decision(intersection_id, snapshot.decision)

                if tick_count % persist_every_n_ticks == 0:
                    with contextlib.suppress(Exception), session_scope() as db:
                        AnalyticsService(db).record_snapshot(intersection_id, snapshot.lane_metrics, snapshot.is_simulated)

                from app.api.websocket import snapshot_to_payload
                await connection_manager.broadcast(intersection_id, snapshot_to_payload(intersection_id, runtime.controller))

            await asyncio.sleep(1.0 / tick_hz)
    except asyncio.CancelledError:
        logger.info("Control loop cancelled - shutting down")
        raise


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _control_loop_task
    init_db()
    _subscribe_event_persistence()
    _seed_admin_user()
    _register_default_intersection()
    _register_regional_intersections()
    event_bus.publish(Event(type=EventType.SYSTEM_STARTUP, intersection_id=None, message="DHAARA backend started"))
    _control_loop_task = asyncio.create_task(_control_loop())
    logger.info("DHAARA backend startup complete")
    yield
    if _control_loop_task is not None:
        _control_loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _control_loop_task
    for runtime in app_state.runtimes.values():
        with contextlib.suppress(Exception):
            runtime.video_source.close()


app.router.lifespan_context = lifespan
