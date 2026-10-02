"""FastAPI application: independent directional capture and shared YOLO batches."""
from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.domain_config import DomainConfig, LaneThresholds, PressureWeights, SignalTimings, DetectionConfig
from app.core.logging import get_logger
from app.core.state import app_state, IntersectionRuntime, CameraRuntime
from app.database.database import init_db, session_scope
from app.models.user import User
from app.core.auth import hash_password
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import YOLODetector
from app.services.cv.image_classifier import classifier_service
from app.services.lanes.lane_intelligence import LaneGeometry
from app.services.cv.lane_assigner import DIRECTIONS, camera_lane, validate_normalized_roi
from app.services.cv.video_source import UploadedVideoSource
from app.services.simulation.lab import SIMULATION_INTERSECTION_ID, create_simulation_runtime
from app.services.analytics.analytics_service import AnalyticsService
from app.services.event_bus import event_bus, Event, EventType

from app.api.routes import (
    health, auth, intersections, lanes, traffic, signals, video, emergency, safety, analytics, simulation, events, config, classifier,
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
               simulation.router, events.router, config.router, classifier.router, websocket_router):
    app.include_router(router)

DEFAULT_INTERSECTION_ID = "OD-BBSR-001"
DEFAULT_WIDTH, DEFAULT_HEIGHT = 640, 360

BACKEND_DIR = Path(__file__).resolve().parents[1]
model_path = Path(settings.model_path)
shared_detector = YOLODetector(str(model_path if model_path.is_absolute() else BACKEND_DIR / model_path),
                               confidence_threshold=settings.detection.yolo_confidence)
classifier_service._shared_detector = shared_detector

_control_loop_task: asyncio.Task | None = None


def _subscribe_event_persistence():
    from app.models.events import SystemEventRecord

    def _persist(event: Event) -> None:
        if event.intersection_id == SIMULATION_INTERSECTION_ID:
            return  # educational observations never enter the live event log
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
    return _persist


def _seed_admin_user() -> None:
    with session_scope() as db:
        if db.query(User).count() == 0:
            db.add(User(username="admin", hashed_password=hash_password("dhaara-admin"), role="ADMIN"))
            logger.warning("Seeded default admin user 'admin' / 'dhaara-admin' - CHANGE THIS PASSWORD before any real deployment.")


def _register_intersection(intersection_id, name, location):
    from app.models.intersection import Intersection
    from app.models.lane import Lane
    domain = DomainConfig(lane_thresholds=LaneThresholds(**settings.lane_thresholds.model_dump()),
                          pressure_weights=PressureWeights(**settings.pressure_weights.model_dump()),
                          signal_timings=SignalTimings(**settings.signal_timings.model_dump()),
                          detection=DetectionConfig(**settings.detection.model_dump()))
    cameras, polygons, geometries, rois = {}, [], {}, {}
    with session_scope() as db:
        if db.get(Intersection, intersection_id) is None:
            db.add(Intersection(id=intersection_id, name=name, location=location, status="ONLINE"))
        for direction in DIRECTIONS:
            roi = getattr(settings, f"{direction.lower()}_roi")
            row = db.get(Lane, f"{intersection_id}:{direction}")
            if row is None:
                row = Lane(id=f"{intersection_id}:{direction}", intersection_id=intersection_id,
                           direction=direction, polygon=roi, pixels_per_meter=8.0,
                           length_m=9.144, capacity_vehicles=25)
                db.add(row)
            else:
                try:
                    roi = [list(p) for p in validate_normalized_roi(row.polygon)]
                except ValueError:
                    # Migrate obsolete pixel-based intersection polygons once.
                    row.polygon = roi
            if row.length_m == 50:  # obsolete default measurement depth
                row.length_m = 9.144
            rois[direction] = roi
            polygons.append(camera_lane(direction, DEFAULT_WIDTH, DEFAULT_HEIGHT, roi, row.pixels_per_meter))
            geometries[direction] = LaneGeometry(direction, row.length_m, row.capacity_vehicles)
            path = getattr(settings, f"{direction.lower()}_video")
            cameras[direction] = CameraRuntime(direction, UploadedVideoSource(path), path)
    controller = IntersectionController(intersection_id, polygons, list(DIRECTIONS),
                                        shared_detector,
                                        config=domain, lane_geometry=geometries, signal_clock=time.monotonic)
    for d in DIRECTIONS:
        controller.configure_camera_roi(d, rois[d], geometries[d], polygons[list(DIRECTIONS).index(d)].pixels_per_meter)
    runtime = IntersectionRuntime(controller, cameras, real_detector=shared_detector)
    app_state.register(intersection_id, runtime)


def _remove_seeded_demo_nodes():
    """Remove former automatic demo nodes only if they contain no real input data."""
    from app.database.database import Base
    from app.models.intersection import Intersection
    from app.models.camera import Camera
    from app.models.traffic import TrafficSnapshot
    demo_nodes = {"OD-BBSR-002": ("Vani Vihar Junction", "NH-16 / Utkal University"),
                  "OD-BBSR-003": ("Rasulgarh Square", "Cuttack-Puri Bypass"),
                  "OD-BBSR-004": ("Khandagiri Chowk", "Khandagiri / Baramunda")}
    with session_scope() as db:
        for node_id, identity in demo_nodes.items():
            row = db.get(Intersection, node_id)
            if row is None or (row.name, row.location) != identity:
                continue
            if db.query(TrafficSnapshot).filter(TrafficSnapshot.intersection_id == node_id,
                                                TrafficSnapshot.is_simulated.is_(False)).first():
                continue
            if db.query(Camera).filter(Camera.intersection_id == node_id, Camera.source_type != "SIMULATION").first():
                continue
            for table in reversed(Base.metadata.sorted_tables):
                if "intersection_id" in table.c:
                    db.execute(table.delete().where(table.c.intersection_id == node_id))
            db.execute(Intersection.__table__.delete().where(Intersection.id == node_id))


def _register_default_intersection():
    _register_intersection(DEFAULT_INTERSECTION_ID, "Master Canteen Square", "Bhubaneswar Central")


def _register_simulation_lab():
    domain = DomainConfig(lane_thresholds=LaneThresholds(**settings.lane_thresholds.model_dump()),
                          pressure_weights=PressureWeights(**settings.pressure_weights.model_dump()),
                          signal_timings=SignalTimings(**settings.signal_timings.model_dump()),
                          detection=DetectionConfig(**settings.detection.model_dump()))
    app_state.register(SIMULATION_INTERSECTION_ID, create_simulation_runtime(domain))


async def _capture_camera(runtime, direction):
    """One bounded latest-frame buffer per camera; no camera waits for another."""
    camera = runtime.cameras[direction]
    source = None
    try:
        while True:
            if source is not camera.source:
                if source is not None:
                    await asyncio.to_thread(source.close)
                source = camera.source
            if runtime.camera_status == "OFFLINE":
                await asyncio.sleep(.1)
                continue
            try:
                frame = await asyncio.to_thread(source.read)
                # A replacement during read must not publish an old camera frame.
                if source is camera.source:
                    camera.frame, camera.status, camera.error = frame, "ONLINE", None
                await asyncio.sleep(1 / max(frame.fps, 1))
            except Exception as exc:
                if source is camera.source:
                    camera.frame, camera.status, camera.error = None, "OFFLINE", str(exc)
                await asyncio.to_thread(source.close)
                await asyncio.sleep(1)
    finally:
        if source is not None:
            await asyncio.to_thread(source.close)


def _process_runtime(runtime, dt_seconds):
    import time
    with runtime.lock:
        if runtime.simulation_lab is not None:
            return runtime.simulation_lab.step(runtime, dt_seconds)
        images, statuses = {}, {}
        for d, camera in runtime.cameras.items():
            frame = camera.frame
            fresh = frame is not None and time.time() - frame.timestamp < 2.0 and runtime.camera_status == "ONLINE"
            if fresh:
                images[d] = frame.image
            statuses[d] = {"status": camera.status if fresh else "OFFLINE",
                           "error": camera.error, "source": "SIMULATION" if runtime.is_simulated else "VIDEO",
                           "frame_index": frame.frame_index if fresh else None}
        runtime.frame_index += 1
        snapshot = runtime.controller.process_frames(images, runtime.frame_index, dt_seconds, statuses)
        snapshot.is_simulated = runtime.is_simulated
        runtime.processed_frames = images
        runtime.hardware_controller.apply_state(runtime.controller.intersection_id, runtime.controller.signal_fsm.state)
        return snapshot


async def _intersection_loop(intersection_id, runtime):
    import time
    tick_count, previous = 0, time.monotonic()
    while True:
        try:
            now = time.monotonic()
            snapshot = await asyncio.to_thread(_process_runtime, runtime, max(.001, now - previous))
            previous = now
            tick_count += 1
            if tick_count % 10 == 0 and runtime.simulation_lab is None:
                def persist():
                    with session_scope() as db:
                        service = AnalyticsService(db)
                        service.record_snapshot(intersection_id, snapshot.lane_metrics, snapshot.is_simulated)
                        if snapshot.decision:
                            service.record_decision(intersection_id, snapshot.decision)
                await asyncio.to_thread(persist)
            from app.api.websocket import snapshot_to_payload
            with runtime.lock:
                payload = snapshot_to_payload(intersection_id, runtime.controller)
                if runtime.simulation_lab is not None:
                    payload["simulation"] = runtime.simulation_lab.metadata()
            await connection_manager.broadcast(intersection_id, payload)
        except Exception as exc:
            logger.error(f"[{intersection_id}] processing failed: {exc}")
            with runtime.lock:
                runtime.processed_frames = {}
                runtime.controller.last_snapshot = None
            await connection_manager.broadcast(intersection_id, {"intersection_id": intersection_id, "status": "NO_DATA", "error": str(exc)})
        await asyncio.sleep(.2)


async def _control_loop():
    workers = []
    for intersection_id, runtime in app_state.runtimes.items():
        if runtime.simulation_lab is None:
            workers.extend(asyncio.create_task(_capture_camera(runtime, d)) for d in DIRECTIONS)
        workers.append(asyncio.create_task(_intersection_loop(intersection_id, runtime)))
    try:
        await asyncio.gather(*workers)
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _control_loop_task
    init_db()
    _remove_seeded_demo_nodes()
    persistence_subscriber = _subscribe_event_persistence()
    _seed_admin_user()
    _register_default_intersection()
    _register_simulation_lab()
    event_bus.publish(Event(type=EventType.SYSTEM_STARTUP, intersection_id=None, message="DHAARA backend started"))
    _control_loop_task = asyncio.create_task(_control_loop())
    logger.info("DHAARA backend startup complete")
    yield
    if _control_loop_task is not None:
        _control_loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _control_loop_task
    for runtime in app_state.runtimes.values():
        for camera in runtime.cameras.values():
            with contextlib.suppress(Exception):
                camera.source.close()
    app_state.runtimes.clear()
    app_state.coordinator = type(app_state.coordinator)()
    event_bus.unsubscribe(persistence_subscriber)


app.router.lifespan_context = lifespan
