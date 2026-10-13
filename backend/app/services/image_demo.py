"""Photo-based proof of concept: real detections, an explicitly virtual clock."""
from __future__ import annotations

import math
import time
from dataclasses import replace
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.core.domain_config import DomainConfig
from app.core.state import CameraRuntime, IntersectionRuntime
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import FrameDetections
from app.services.cv.lane_assigner import DIRECTIONS, camera_lane, point_in_polygon
from app.services.cv.video_source import SourceKind, StillImageSource, VideoFrame
from app.services.decision.vehicle_scoring import score_classes
from app.services.lanes.lane_intelligence import LaneGeometry

IMAGE_DEMO_ID = "IMAGE-DEMO"
# A sample approach boundary, deliberately not claimed to measure 30 feet.
IMAGE_ROI = ((.48, .13), (1., .13), (.82, .72), (0., .72))
IMAGE_FILES = {"heavy": "heavy traffic.png", "normal": "normal traffic.png",
               "low": "low traffic.jpeg", "ambulance": "ambulance case.png"}
IMAGE_CASES = (
    {"id": "balanced_heavy", "title": "Heavy / heavy", "ew": "heavy", "ns": "heavy"},
    {"id": "heavy_normal", "title": "Heavy / normal", "ew": "heavy", "ns": "normal"},
    {"id": "normal_low", "title": "Normal / low", "ew": "normal", "ns": "low"},
    {"id": "heavy_low", "title": "Heavy / low", "ew": "heavy", "ns": "low"},
    {"id": "heavy_ambulance", "title": "Heavy / ambulance", "ew": "heavy", "ns": "ambulance"},
    {"id": "balanced_normal", "title": "Normal / normal", "ew": "normal", "ns": "normal"},
)
_catalog_cache = {}
_catalog_lock = RLock()


class ImageCatalog:
    def __init__(self, directory: Path, detector):
        self.directory = directory
        self.detector = detector
        self.images = {}
        self.detections = {}
        self.stats = {}
        self._fingerprint = None

    @property
    def ready(self):
        return bool(self.detections)

    def prepare(self):
        with _catalog_lock:
            paths = {key: self.directory / name for key, name in IMAGE_FILES.items()}
            fingerprint = (tuple((key, p.stat().st_mtime_ns, p.stat().st_size) for key, p in paths.items()),
                           getattr(self.detector, "_confidence_threshold", None))
            if self._fingerprint == fingerprint:
                return
            # Cache by actual model instance and source content. Repeated still
            # observations never rerun expensive identical YOLO inference.
            cache_key = (self.detector, str(self.directory), fingerprint)
            cached = _catalog_cache.get(cache_key)
            if cached is None:
                images = {key: StillImageSource(str(path)).read().image for key, path in paths.items()}
                detections = self.detector.detect_many(images, 1)
                if set(detections) != set(images):
                    raise ValueError("Detector did not return all four source images")
                stats = {}
                for key, result in detections.items():
                    h, w = images[key].shape[:2]
                    polygon = camera_lane("EAST", w, h, IMAGE_ROI).polygon
                    included = [d.class_name for d in result.detections if point_in_polygon(d.center, polygon)]
                    score, counts = score_classes(included)
                    stats[key] = {"filename": IMAGE_FILES[key], "vehicle_count": len(included),
                                  "vehicle_score": score, "vehicle_counts": counts,
                                  "detected_total": len(result.detections), "model": result.model_name}
                cached = (images, detections, stats)
                # Bound cache growth when images/configuration are changed repeatedly.
                if len(_catalog_cache) >= 4:
                    _catalog_cache.pop(next(iter(_catalog_cache)))
                _catalog_cache[cache_key] = cached
            self.images, self.detections, self.stats = cached
            self._fingerprint = fingerprint


class CachedImageDetector:
    def __init__(self, catalog: ImageCatalog, session):
        self.catalog, self.session = catalog, session

    @property
    def rickshaw_supported(self):
        return getattr(self.catalog.detector, "rickshaw_supported", None)

    def detect_many(self, images, frame_index):
        self.catalog.prepare()
        return {direction: FrameDetections(list(self.catalog.detections[self.session.sources[direction]].detections),
                                           False, self.catalog.detections[self.session.sources[direction]].model_name)
                for direction in images}


class ImageDemoSession:
    def __init__(self, catalog: ImageCatalog):
        self.catalog = catalog
        self.session_id = uuid4().hex
        self.case_id = "balanced_heavy"
        self.swapped = False
        self.paused = False
        self.speed = 1
        self.auto_tour = False
        self.virtual_time_s = 0.0
        self.revision = 0
        self.lights_active = False
        self.lights_until_s = 0.0
        self.sources = {}
        self.transitions = []
        self.case_history = []
        self.started_at = time.time()
        self._observed_fingerprint = None

    def select_case(self, runtime, case_id, swapped=False):
        case = next((item for item in IMAGE_CASES if item["id"] == case_id), None)
        if case is None:
            raise ValueError("Unknown image case")
        self.case_id, self.swapped = case_id, swapped
        ew, ns = (case["ns"], case["ew"]) if swapped else (case["ew"], case["ns"])
        selected = {"EAST": ew, "WEST": ew, "NORTH": ns, "SOUTH": ns}
        for direction, image_id in selected.items():
            if self.sources.get(direction) != image_id:
                runtime.controller.reset_camera(direction)
                path = self.catalog.directory / IMAGE_FILES[image_id]
                runtime.cameras[direction] = CameraRuntime(direction, StillImageSource(str(path)), str(path))
        self.sources = selected
        # Selecting this labelled demonstration supplies the light input; the
        # photograph itself is never treated as temporal flashing evidence.
        self.set_lights("ambulance" in selected.values())
        self.revision += 1
        self.case_history.append({"time_s": round(self.virtual_time_s, 1), "case_id": case_id,
                                  "ew": ew, "ns": ns, "swapped": swapped})
        self.case_history = self.case_history[-20:]
        # Keep the same FSM, previous green, full-phase protection and history.

    def set_lights(self, active):
        if active and "ambulance" not in self.sources.values():
            raise ValueError("Select the ambulance image case first")
        self.lights_active = active
        self.lights_until_s = self.virtual_time_s + 12 if active else 0.0
        self.revision += 1

    def metadata(self, runtime):
        case = next(item for item in IMAGE_CASES if item["id"] == self.case_id)
        state = runtime.controller.signal_fsm.state
        previous_green = state.active_direction if state.color.value == "YELLOW" else state.previous_phase
        return {"session_id": self.session_id, "case_id": self.case_id, "title": case["title"], "swapped": self.swapped,
                "sources": dict(self.sources), "presets": list(IMAGE_CASES), "images": self.catalog.stats,
                "ready": self.catalog.ready, "paused": self.paused, "speed": self.speed,
                "auto_tour": self.auto_tour, "virtual_time_s": round(self.virtual_time_s, 2),
                "revision": self.revision, "lights_active": self.lights_active,
                "lights_remaining_s": round(max(0, self.lights_until_s - self.virtual_time_s), 1),
                "previous_green_pair": previous_green,
                "previous_red_pair": ("NS" if previous_green == "EW" else "EW") if previous_green else None,
                "transitions": list(self.transitions), "case_history": list(self.case_history),
                "roi_calibrated": False, "detection_source": "YOLO on supplied images"}

    def step(self, runtime, dt_seconds):
        self.catalog.prepare()
        if self.paused and runtime.controller.last_snapshot is not None:
            if self._observed_fingerprint != self.catalog._fingerprint:
                return self.observe(runtime, 0.0)
            return runtime.controller.last_snapshot
        remaining = max(0, dt_seconds) * self.speed
        steps = max(1, math.ceil(remaining / .2))
        for _ in range(steps):
            snapshot = self.observe(runtime, remaining / steps)
        return snapshot

    def observe(self, runtime, dt_seconds=0.0):
        self.catalog.prepare()
        if self._observed_fingerprint != self.catalog._fingerprint:
            for direction in DIRECTIONS:
                runtime.controller.reset_camera(direction)
            self._observed_fingerprint = self.catalog._fingerprint
        self.virtual_time_s += dt_seconds
        if self.lights_active and self.virtual_time_s >= self.lights_until_s:
            self.lights_active = False
            self.revision += 1
        images = {direction: self.catalog.images[image_id] for direction, image_id in self.sources.items()}
        runtime.frame_index += 1
        statuses = {direction: {"status": "ONLINE", "error": None, "source": "IMAGE",
                    "filename": IMAGE_FILES[image_id], "image_id": image_id, "frame_index": runtime.frame_index}
                    for direction, image_id in self.sources.items()}
        before = runtime.controller.signal_fsm.state
        for direction, image in images.items():
            h, w = image.shape[:2]
            camera = runtime.cameras[direction]
            camera.frame = VideoFrame(image, runtime.frame_index, time.time(), SourceKind.STILL_IMAGE,
                                      IMAGE_FILES[self.sources[direction]], 5.0, w, h)
            camera.status, camera.error = "ONLINE", None
        lights = {direction: image_id == "ambulance" and self.lights_active
                  for direction, image_id in self.sources.items()}
        snapshot = runtime.controller.process_frames(images, runtime.frame_index, dt_seconds, statuses,
                                                     demo_light_inputs=lights)
        # This is operator-provided demo evidence, not observed temporal flashing.
        if snapshot.decision:
            snapshot.decision = replace(snapshot.decision, reason=[reason.replace(
                "Ambulance and flashing emergency lights confirmed", "Detected ambulance + explicit demo lights ON")
                for reason in snapshot.decision.reason])
        after = runtime.controller.signal_fsm.state
        if (before.color, before.active_direction, before.target_direction) != (after.color, after.active_direction, after.target_direction):
            self.transitions.append({"time_s": round(self.virtual_time_s, 1), "case_id": self.case_id,
                "from_pair": before.active_direction, "from_state": before.color.value,
                "to_pair": after.active_direction, "to_state": after.color.value,
                "target_pair": after.target_direction, "directions": dict(snapshot.direction_signals),
                "pair_scores": dict(snapshot.demand["pair_scores"]), "reason": snapshot.decision.reason})
            self.transitions = self.transitions[-20:]
        runtime.processed_frames = images
        runtime.hardware_controller.apply_state(IMAGE_DEMO_ID, after)
        if (self.auto_tour and before.color.value == "YELLOW" and after.color.value == "GREEN"
                and before.active_direction != after.active_direction):
            index = next(i for i, item in enumerate(IMAGE_CASES) if item["id"] == self.case_id)
            self.select_case(runtime, IMAGE_CASES[(index + 1) % len(IMAGE_CASES)]["id"], self.swapped)
            return self.observe(runtime, 0.0)
        return snapshot


def create_image_demo_runtime(directory: Path, detector) -> IntersectionRuntime:
    catalog = ImageCatalog(directory, detector)
    session = ImageDemoSession(catalog)
    config = DomainConfig()
    geometries = {d: LaneGeometry(d, 9.144, 40) for d in DIRECTIONS}
    controller = IntersectionController(IMAGE_DEMO_ID,
        [camera_lane(d, 640, 360, IMAGE_ROI) for d in DIRECTIONS], list(DIRECTIONS),
        CachedImageDetector(catalog, session), config=config, lane_geometry=geometries)
    # An explicit lights-OFF input is certain, unlike a missed video detection.
    # Release demo priority on that observation even when its clock is paused.
    controller.emergency_manager.clear_after_missed_ticks = 1
    for direction in DIRECTIONS:
        controller.configure_camera_roi(direction, IMAGE_ROI, geometries[direction])
    runtime = IntersectionRuntime(controller, {}, real_detector=detector, image_demo=session)
    session.select_case(runtime, session.case_id)
    return runtime
