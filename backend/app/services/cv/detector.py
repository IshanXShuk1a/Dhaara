"""
Detector interface.

`Detector` is the abstract contract the CV pipeline (Tracker, LaneAssigner,
ambulance/helmet analytics) depends on.

Implementations:
  * `YOLODetector` - wraps `ultralytics.YOLO`.
  * `SimulationDetector` - scenario-driven detector for development and tests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.services.cv.tracker import Detection

from app.services.decision.vehicle_scoring import VEHICLE_WEIGHTS, canonical_class

VEHICLE_CLASSES = tuple(VEHICLE_WEIGHTS)


class DetectorUnavailableError(Exception):
    """Raised when a real detector's required dependency/model file is missing."""


@dataclass(frozen=True)
class FrameDetections:
    detections: list[Detection]
    is_simulated: bool
    model_name: str


class Detector(Protocol):
    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections: ...


class YOLODetector:
    """Real object detector backed by ultralytics YOLO weights."""

    def __init__(self, model_path: str = "./models_store/yolov8n.pt", confidence_threshold: float = 0.18, device: str = "cpu"):
        from threading import Lock
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._device = device
        self._model = None
        self._lock = Lock()
        from app.services.cv.ambulance_detector import AmbulanceDetector
        self._ambulance_detector = AmbulanceDetector(confidence_threshold=0.60)

    @property
    def rickshaw_supported(self):
        if self._model is None:
            return None
        names = self._model.names
        return any(canonical_class(str(name)) == "rickshaw" for name in (names.values() if isinstance(names, dict) else names))

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
            if not os.path.exists(self._model_path) and os.path.basename(self._model_path) != "yolov8n.pt":
                raise FileNotFoundError(self._model_path)
            self._model = YOLO(self._model_path if os.path.exists(self._model_path) else "yolov8n.pt")
        except Exception as exc:
            raise DetectorUnavailableError(f"Cannot load YOLO weights: {self._model_path}: {exc}") from exc

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        return self.detect_many({"frame": image}, frame_index)["frame"]

    def detect_many(self, images: dict[str, np.ndarray], frame_index: int) -> dict[str, FrameDetections]:
        if not images:
            return {}
        # One model and one inference batch for all ready cameras. The lock
        # also permits sharing this instance across intersection workers.
        with self._lock:
            self._load_model()
            max_dim = max(max(image.shape[:2]) for image in images.values())
            img_size = min(1280, max(640, (max_dim // 32) * 32))
            results = self._model.predict(list(images.values()), conf=self._confidence_threshold,
                                          iou=0.40, imgsz=img_size, device=self._device, verbose=False)
            if len(results) != len(images):
                raise DetectorUnavailableError("YOLO returned an incomplete camera batch")
            return {direction: self._parse_result(image, result)
                    for (direction, image), result in zip(images.items(), results)}

    def _parse_result(self, image, result) -> FrameDetections:
        detections = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = result.names.get(cls_id, str(cls_id)).lower()
            class_name = canonical_class(class_name)
            if class_name not in VEHICLE_CLASSES:
                continue
            bbox = tuple(float(v) for v in box.xyxy[0])
            confidence = float(box.conf[0])
            if class_name in ("bus", "truck", "car"):
                is_amb, amb_conf = self._ambulance_detector.is_ambulance(image, bbox, class_name)
                if is_amb:
                    class_name, confidence = "ambulance", amb_conf
            detections.append(Detection(bbox=bbox, class_name=class_name, confidence=confidence))
        return FrameDetections(detections, False, "yolo")


class SimulationDetector:
    """Deterministic, scenario-driven detector for development and demos."""

    def __init__(self, scenario_provider):
        self._scenario_provider = scenario_provider

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        detections = self._scenario_provider.detections_for_frame(frame_index)
        return FrameDetections(detections=detections, is_simulated=True, model_name="simulation-scenario")

    def detect_many(self, images: dict[str, np.ndarray], frame_index: int) -> dict[str, FrameDetections]:
        return {direction: FrameDetections(
            self._scenario_provider.detections_for_frame(frame_index, direction), True, "simulation-scenario")
            for direction in images}
