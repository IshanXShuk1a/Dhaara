"""
Detector interface.

`Detector` is the abstract contract the CV pipeline (Tracker, LaneAssigner,
ambulance/helmet analytics) depends on. Two implementations are provided:

  * `YOLODetector`   - wraps `ultralytics.YOLO`. This is the real detector
    DHAARA runs in production. Import of `ultralytics` is deferred to
    `__init__` so this module stays importable even where the (heavy, GPU
    -oriented) dependency isn't installed - it raises a clear
    `DetectorUnavailableError` at construction time if it's missing, rather
    than silently falling back to fake detections.

  * `SimulationDetector` - a deterministic, geometry-driven stand-in used
    for local development and this repository's own tests/demo when no
    trained weights are present. It is NOT a generic-vehicle-equals-
    ambulance hack: every detection it returns is explicitly tagged
    `is_simulated=True`, and the dashboard/API must surface that flag
    rather than presenting simulated detections as live inference. It is
    driven by an explicit, inspectable scenario script (see
    `services/simulation/simulation_engine.py`), not by randomness dressed
    up as intelligence.

Per project rules: ambulance detection is never "any vehicle == ambulance".
Both detectors emit a dedicated `"ambulance"` class only when that specific
evidence exists (a real fine-tuned class in YOLODetector; an explicit
scripted event in SimulationDetector) - see `AmbulanceAnalyzer` for the
separate confidence+temporal-confirmation layer on top of raw detections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.services.cv.tracker import Detection

VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck", "bicycle", "ambulance")


class DetectorUnavailableError(Exception):
    """Raised when a real detector's required dependency/model file is missing.
    Never caught silently to fabricate detections - callers must surface this
    to the user/operator (e.g. system health = MODEL_ERROR)."""


@dataclass(frozen=True)
class FrameDetections:
    detections: list[Detection]
    is_simulated: bool
    model_name: str


class Detector(Protocol):
    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections: ...


class YOLODetector:
    """Real object detector backed by ultralytics YOLO weights.

    Requires the `ultralytics` package and a trained/fine-tuned `.pt` weights
    file at `model_path` (see .env `MODEL_PATH`). If the class list in the
    weights does not include "ambulance" as a distinct class, ambulance
    detections will simply never fire from this detector - operators must
    fine-tune or supply a dedicated ambulance-classification stage rather
    than treating "truck"/"van" detections as ambulances.
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.45, device: str = "cpu"):
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise DetectorUnavailableError(
                "ultralytics is not installed. Install it (`pip install ultralytics`) "
                "and provide a weights file at MODEL_PATH to use YOLODetector, "
                "or use SimulationDetector for development."
            ) from exc

        import os

        if not os.path.exists(model_path):
            raise DetectorUnavailableError(
                f"YOLO weights not found at '{model_path}'. Set MODEL_PATH to a valid "
                "weights file, or use SimulationDetector for development."
            )

        self._model = YOLO(model_path)
        self._confidence_threshold = confidence_threshold
        from app.services.cv.ambulance_detector import AmbulanceDetector
        self._ambulance_detector = AmbulanceDetector(confidence_threshold=0.60)

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        results = self._model.predict(image, conf=self._confidence_threshold, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0])
                class_name = names.get(cls_id, str(cls_id))
                if class_name not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                confidence = float(box.conf[0])
                if class_name in ("bus", "truck", "car"):
                    is_amb, amb_conf = self._ambulance_detector.is_ambulance(image, (x1, y1, x2, y2), class_name)
                    if is_amb:
                        class_name = "ambulance"
                        confidence = amb_conf
                detections.append(
                    Detection(bbox=(x1, y1, x2, y2), class_name=class_name, confidence=confidence)
                )
        return FrameDetections(detections=detections, is_simulated=False, model_name=self._model.model_name if hasattr(self._model, "model_name") else "yolo")


class SimulationDetector:
    """Deterministic, scenario-driven detector for development and demos
    without trained weights. Every call is explicitly labeled
    `is_simulated=True` in its return value; the API/dashboard layer must
    propagate that flag rather than presenting this as live inference.

    Detections come from a `ScenarioProvider` (see
    services/simulation/simulation_engine.py) which exposes, per frame index,
    the list of `Detection`s a scripted scenario says should exist. This
    keeps the "fake" data honest and inspectable rather than random numbers
    dressed up as AI output.
    """

    def __init__(self, scenario_provider):
        self._scenario_provider = scenario_provider

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        detections = self._scenario_provider.detections_for_frame(frame_index)
        return FrameDetections(detections=detections, is_simulated=True, model_name="simulation-scenario")
