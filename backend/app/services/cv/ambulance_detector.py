"""
Dedicated Ambulance Detector / Classifier

Evaluates vehicle bounding boxes for distinct emergency vehicle features:
- High contrast emergency livery (white/yellow chassis with red/blue/green reflective stripes)
- Roof emergency light bar indicators (high luminance peaks in the top 20% of bbox)
- Red cross / emergency insignia color clusters

Color evidence provides a heuristic candidate label and requires footage validation.
Signal priority separately requires temporal flashing-beacon evidence.
"""
from __future__ import annotations

import cv2
import numpy as np


class AmbulanceDetector:
    def __init__(self, confidence_threshold: float = 0.60):
        self.confidence_threshold = confidence_threshold

    def is_ambulance(
        self, image: np.ndarray | None, bbox: tuple[float, float, float, float], base_class: str
    ) -> tuple[bool, float]:
        """Determines if a vehicle detection is an emergency ambulance.

        Returns (is_ambulance, confidence).
        """
        if base_class == "ambulance":
            return (True, 0.95)

        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return (False, 0.0)

        # Only candidate vehicle classes can be ambulances
        if base_class not in ("bus", "truck", "car"):
            return (False, 0.0)

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        box_w = x2 - x1
        box_h = y2 - y1
        if box_w < 20 or box_h < 20:
            return (False, 0.0)

        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return (False, 0.0)

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        total_pixels = float(crop.shape[0] * crop.shape[1])

        # 1. White / Emergency Yellow bodywork (low saturation high value OR bright yellow)
        white_mask = cv2.inRange(hsv, np.array([0, 0, 150], dtype=np.uint8), np.array([180, 55, 255], dtype=np.uint8))
        yellow_mask = cv2.inRange(hsv, np.array([15, 60, 140], dtype=np.uint8), np.array([35, 255, 255], dtype=np.uint8))
        body_mask = white_mask | yellow_mask
        body_ratio = float(np.count_nonzero(body_mask)) / total_pixels

        # 2. Emergency markings (Red stripes & Blue emergency livery)
        red_mask1 = cv2.inRange(hsv, np.array([0, 110, 90], dtype=np.uint8), np.array([12, 255, 255], dtype=np.uint8))
        red_mask2 = cv2.inRange(hsv, np.array([168, 110, 90], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8))
        blue_mask = cv2.inRange(hsv, np.array([95, 100, 90], dtype=np.uint8), np.array([135, 255, 255], dtype=np.uint8))
        marking_mask = red_mask1 | red_mask2 | blue_mask
        marking_ratio = float(np.count_nonzero(marking_mask)) / total_pixels

        # 3. Emergency roof light bar (top 25% of vehicle)
        roof_crop = hsv[: int(box_h * 0.25), :]
        if roof_crop.size > 0:
            roof_v = roof_crop[:, :, 2]
            roof_peak_ratio = float(np.count_nonzero(roof_v > 220)) / float(roof_v.size)
            roof_red = (cv2.inRange(roof_crop, np.array([0, 100, 90], dtype=np.uint8), np.array([12, 255, 255], dtype=np.uint8)) |
                        cv2.inRange(roof_crop, np.array([168, 100, 90], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8)))
            roof_blue = cv2.inRange(roof_crop, np.array([95, 100, 90], dtype=np.uint8), np.array([135, 255, 255], dtype=np.uint8))
            roof_beacon_ratio = float(np.count_nonzero(roof_red | roof_blue)) / float(roof_crop.shape[0] * roof_crop.shape[1])
        else:
            roof_peak_ratio = 0.0
            roof_beacon_ratio = 0.0

        # Characteristic ambulance profile: predominantly white/yellow body with emergency markings & roof beacon
        evidence_score = 0.0
        if body_ratio > 0.30:
            evidence_score += 0.35
        if marking_ratio > 0.035:
            evidence_score += 0.35
        if roof_peak_ratio > 0.08 or roof_beacon_ratio > 0.04:
            evidence_score += 0.25

        if evidence_score >= self.confidence_threshold:
            return (True, round(min(0.98, evidence_score), 2))

        return (False, round(evidence_score, 2))
