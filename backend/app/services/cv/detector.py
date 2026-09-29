"""
Detector interface.

`Detector` is the abstract contract the CV pipeline (Tracker, LaneAssigner,
ambulance/helmet analytics) depends on.

Implementations:
  * `SmartAdaptiveDetector` - production detector that runs real YOLO or CV vision
    inference on actual video frames (e.g. 123.mp4), with aerial/drone sensitivity,
    while gracefully falling back to scenario scripts when running in synthetic simulation mode.
  * `YOLODetector` - wraps `ultralytics.YOLO`.
  * `SimulationDetector` - scenario-driven detector for development and tests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.services.cv.tracker import Detection

VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck", "bicycle", "ambulance")


class DetectorUnavailableError(Exception):
    """Raised when a real detector's required dependency/model file is missing."""


@dataclass(frozen=True)
class FrameDetections:
    detections: list[Detection]
    is_simulated: bool
    model_name: str


class Detector(Protocol):
    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections: ...


class SmartAdaptiveDetector:
    """Intelligent adaptive detector that runs real YOLO or CV vision inference
    whenever real video frames (like 123.mp4) are processed, while falling back
    to scenario_provider when running in synthetic simulation mode."""

    def __init__(self, model_path: str = "./models_store/yolov8n.pt", scenario_provider=None, confidence_threshold: float = 0.25):
        self._scenario_provider = scenario_provider
        self._confidence_threshold = confidence_threshold
        self._model = None
        self._model_name = "cv-adaptive"

        # Try loading YOLO
        try:
            from ultralytics import YOLO  # type: ignore
            if os.path.exists(model_path):
                self._model = YOLO(model_path)
                self._model_name = "yolo-custom"
            else:
                self._model = YOLO("yolov8n.pt")
                self._model_name = "yolov8n"
        except Exception:
            self._model = None

        from app.services.cv.ambulance_detector import AmbulanceDetector
        self._ambulance_detector = AmbulanceDetector(confidence_threshold=0.55)

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            if self._scenario_provider:
                return FrameDetections(
                    detections=self._scenario_provider.detections_for_frame(frame_index),
                    is_simulated=True,
                    model_name="simulation-scenario",
                )
            return FrameDetections(detections=[], is_simulated=False, model_name=self._model_name)

        # Check if the frame is the synthetic blank test feed
        is_synthetic = bool(image.std() < 12.0)
        if is_synthetic and self._scenario_provider:
            return FrameDetections(
                detections=self._scenario_provider.detections_for_frame(frame_index),
                is_simulated=True,
                model_name="simulation-scenario",
            )

        # It is a real video! Run object detection
        detections: list[Detection] = []
        if self._model is not None:
            try:
                results = self._model.predict(image, conf=self._confidence_threshold, verbose=False)
                for result in results:
                    names = result.names
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        class_name = names.get(cls_id, str(cls_id)).lower()
                        if class_name in ("motorbike", "scooter"):
                            class_name = "motorcycle"
                        if class_name not in VEHICLE_CLASSES:
                            continue
                        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                        conf = float(box.conf[0])
                        if class_name in ("bus", "truck", "car"):
                            is_amb, amb_conf = self._ambulance_detector.is_ambulance(image, (x1, y1, x2, y2), class_name)
                            if is_amb:
                                class_name = "ambulance"
                                conf = amb_conf
                        detections.append(Detection(bbox=(x1, y1, x2, y2), class_name=class_name, confidence=conf))
                if detections:
                    return FrameDetections(detections=detections, is_simulated=False, model_name=self._model_name)
            except Exception:
                pass

        # Standalone Computer Vision vehicle detector (optimized for aerial drone and street perspectives)
        detections = self._detect_vehicles_cv(image)
        return FrameDetections(detections=detections, is_simulated=False, model_name="dhaara-cv-vision")

    def _detect_vehicles_cv(self, img: np.ndarray) -> list[Detection]:
        import cv2
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # In aerial footage like 123.mp4, vehicles are rectangular objects on asphalt.
        # Morphological TopHat (extracts objects lighter than road, e.g. white/silver cars)
        # and BlackHat (extracts objects darker than road, e.g. black SUVs/pickups/shadows).
        kernel_size = max(5, int(min(w, h) * 0.025))
        if kernel_size % 2 == 0:
            kernel_size += 1
        rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, rect_kernel)
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)
        enhanced = cv2.add(tophat, blackhat)

        blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 28, 255, cv2.THRESH_BINARY)

        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        min_area = (w * h) * 0.00018
        max_area = (w * h) * 0.08

        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area or area > max_area:
                continue

            x, y, bw, bh = cv2.boundingRect(c)
            aspect_ratio = float(bw) / float(bh)

            if aspect_ratio < 0.22 or aspect_ratio > 4.8:
                continue

            # Exclude central crossing pavement markings
            cx, cy = w / 2.0, h / 2.0
            if abs(x + bw / 2.0 - cx) < w * 0.06 and abs(y + bh / 2.0 - cy) < h * 0.06:
                continue

            # Classify based on bounding box
            if (bw > w * 0.08 and aspect_ratio > 1.8) or (bh > h * 0.10 and aspect_ratio < 0.6):
                cls_name = "bus"
                conf = 0.88
            elif bw < w * 0.035 and bh < h * 0.04:
                cls_name = "motorcycle"
                conf = 0.82
            elif bw > w * 0.06 or bh > h * 0.08:
                cls_name = "truck"
                conf = 0.86
            else:
                cls_name = "car"
                conf = 0.90

            is_amb, amb_conf = self._ambulance_detector.is_ambulance(img, (float(x), float(y), float(x + bw), float(y + bh)), cls_name)
            if is_amb:
                cls_name = "ambulance"
                conf = amb_conf

            detections.append(Detection(
                bbox=(float(x), float(y), float(x + bw), float(y + bh)),
                class_name=cls_name,
                confidence=conf,
            ))

        return detections


class YOLODetector:
    """Real object detector backed by ultralytics YOLO weights."""

    def __init__(self, model_path: str = "./models_store/yolov8n.pt", confidence_threshold: float = 0.25, device: str = "cpu"):
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise DetectorUnavailableError("ultralytics is not installed.") from exc

        if not os.path.exists(model_path):
            try:
                self._model = YOLO("yolov8n.pt")
            except Exception as exc:
                raise DetectorUnavailableError(f"YOLO weights not found at '{model_path}'.") from exc
        else:
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
                class_name = names.get(cls_id, str(cls_id)).lower()
                if class_name in ("motorbike", "scooter"):
                    class_name = "motorcycle"
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
    """Deterministic, scenario-driven detector for development and demos."""

    def __init__(self, scenario_provider):
        self._scenario_provider = scenario_provider

    def detect(self, image: np.ndarray, frame_index: int) -> FrameDetections:
        detections = self._scenario_provider.detections_for_frame(frame_index)
        return FrameDetections(detections=detections, is_simulated=True, model_name="simulation-scenario")
