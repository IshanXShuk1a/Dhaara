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
                # High-resolution inference preserving small drone and aerial vehicles
                max_dim = max(image.shape[:2])
                img_size = min(1280, max(640, (max_dim // 32) * 32))
                results = self._model.predict(image, conf=0.18, iou=0.40, imgsz=img_size, verbose=False)
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

        # High-Precision Computer Vision Vehicle Detector (CLAHE + TopHat/BlackHat + Texture Verification + NMS)
        detections = self._detect_vehicles_cv(image)
        return FrameDetections(detections=detections, is_simulated=False, model_name="dhaara-cv-vision")

    def _detect_vehicles_cv(self, img: np.ndarray) -> list[Detection]:
        import cv2
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. CLAHE Local Contrast Enhancement (reveals shadowy and low-contrast vehicles)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)

        # 2. Dual Multi-Scale Morphological TopHat (bright cars on dark road) & BlackHat (dark vehicles on light road)
        k_small = max(5, int(min(w, h) * 0.020))
        if k_small % 2 == 0:
            k_small += 1
        k_large = max(9, int(min(w, h) * 0.038))
        if k_large % 2 == 0:
            k_large += 1

        kernel_s = cv2.getStructuringElement(cv2.MORPH_RECT, (k_small, k_small))
        kernel_l = cv2.getStructuringElement(cv2.MORPH_RECT, (k_large, k_large))

        tophat = cv2.morphologyEx(enhanced_gray, cv2.MORPH_TOPHAT, kernel_s)
        blackhat = cv2.morphologyEx(enhanced_gray, cv2.MORPH_BLACKHAT, kernel_l)
        morph_combined = cv2.addWeighted(tophat, 0.65, blackhat, 0.65, 0)

        # 3. Gradient Edge Fusion: preserve sharp vehicle chassis and windshields
        grad_x = cv2.Sobel(enhanced_gray, cv2.CV_16S, 1, 0, ksize=3)
        grad_y = cv2.Sobel(enhanced_gray, cv2.CV_16S, 0, 1, ksize=3)
        abs_grad = cv2.convertScaleAbs(cv2.addWeighted(cv2.convertScaleAbs(grad_x), 0.5, cv2.convertScaleAbs(grad_y), 0.5, 0))

        fused = cv2.addWeighted(morph_combined, 0.60, abs_grad, 0.40, 0)
        blur = cv2.GaussianBlur(fused, (5, 5), 0)

        # 4. Otsu Adaptive Thresholding
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Close gaps between roof, windshield, and bonnet
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw_candidates: list[Detection] = []
        min_area = (w * h) * 0.00015
        max_area = (w * h) * 0.085

        ref_car_area = (w * h) * 0.0016
        cx, cy = w / 2.0, h / 2.0

        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area or area > max_area:
                continue

            x, y, bw, bh = cv2.boundingRect(c)
            aspect_ratio = float(bw) / float(bh)

            # Strict aspect ratio boundaries (filters out thin lane lines, lane dividers)
            if aspect_ratio < 0.20 or aspect_ratio > 5.0:
                continue

            # Central intersection crossing pavement filter
            if abs(x + bw / 2.0 - cx) < w * 0.055 and abs(y + bh / 2.0 - cy) < h * 0.055:
                continue

            # 5. Internal Texture & Feature Verification
            # Real vehicles have high internal gradient/texture variance (windows, roof, shadow)
            # whereas painted road stripes and uniform asphalt have low variance (< 14)
            crop = gray[y:y + bh, x:x + bw]
            if crop.size == 0 or crop.std() < 15.0:
                continue

            # Vehicle classification based on area scale and aspect ratio
            box_area = bw * bh
            if box_area > ref_car_area * 2.2 and (aspect_ratio > 1.6 or aspect_ratio < 0.6):
                cls_name = "bus" if (aspect_ratio > 2.2 or aspect_ratio < 0.45) else "truck"
                conf = 0.90
            elif box_area < ref_car_area * 0.45:
                cls_name = "motorcycle"
                conf = 0.85
            elif box_area > ref_car_area * 1.5:
                cls_name = "truck"
                conf = 0.88
            else:
                cls_name = "car"
                conf = 0.92

            # Check ambulance status
            is_amb, amb_conf = self._ambulance_detector.is_ambulance(img, (float(x), float(y), float(x + bw), float(y + bh)), cls_name)
            if is_amb:
                cls_name = "ambulance"
                conf = amb_conf

            raw_candidates.append(Detection(
                bbox=(float(x), float(y), float(x + bw), float(y + bh)),
                class_name=cls_name,
                confidence=conf,
            ))

        # 6. Non-Maximum Suppression (NMS) to eliminate duplicate overlapping boxes
        return self._apply_nms(raw_candidates, iou_thresh=0.35)

    @staticmethod
    def _apply_nms(detections: list[Detection], iou_thresh: float = 0.35) -> list[Detection]:
        if not detections:
            return []

        def _box_iou(a, b):
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            ix1, iy1 = max(ax1, bx1), max(ay1, by1)
            ix2, iy2 = min(ax2, bx2), min(ay2, by2)
            iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
            iarea = iw * ih
            area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
            area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
            union = area_a + area_b - iarea
            return iarea / union if union > 0 else 0.0

        # Sort by confidence * area descending
        detections.sort(key=lambda d: d.confidence * (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]), reverse=True)
        kept: list[Detection] = []
        for det in detections:
            overlap = False
            for k in kept:
                if _box_iou(det.bbox, k.bbox) > iou_thresh:
                    overlap = True
                    break
            if not overlap:
                kept.append(det)
        return kept


class YOLODetector:
    """Real object detector backed by ultralytics YOLO weights."""

    def __init__(self, model_path: str = "./models_store/yolov8n.pt", confidence_threshold: float = 0.18, device: str = "cpu"):
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
        max_dim = max(image.shape[:2])
        img_size = min(1280, max(640, (max_dim // 32) * 32))
        results = self._model.predict(
            image,
            conf=self._confidence_threshold,
            iou=0.40,
            imgsz=img_size,
            verbose=False,
        )
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
