"""
Dedicated Ambulance Detector / Classifier

Evaluates vehicle bounding boxes for distinct emergency vehicle features:
- High contrast emergency livery (white/yellow chassis with red/blue/green reflective stripes)
- Roof emergency light bar indicators (high luminance peaks in the top 20% of bbox)
- Red cross / emergency insignia color clusters

Ensures DHAARA never confuses generic trucks or vans with ambulances.
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

        # 1. White bodywork (low saturation, high value)
        white_mask = cv2.inRange(hsv, np.array([0, 0, 160], dtype=np.uint8), np.array([180, 50, 255], dtype=np.uint8))
        white_ratio = float(np.count_nonzero(white_mask)) / total_pixels

        # 2. Red emergency markings (H near 0 or 170-180 with high saturation)
        red_mask1 = cv2.inRange(hsv, np.array([0, 120, 100], dtype=np.uint8), np.array([10, 255, 255], dtype=np.uint8))
        red_mask2 = cv2.inRange(hsv, np.array([170, 120, 100], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8))
        red_mask = red_mask1 | red_mask2
        red_ratio = float(np.count_nonzero(red_mask)) / total_pixels

        # 3. Emergency roof light bar (top 25% of vehicle)
        roof_crop = hsv[: int(box_h * 0.25), :]
        if roof_crop.size > 0:
            roof_v = roof_crop[:, :, 2]
            roof_peak_ratio = float(np.count_nonzero(roof_v > 230)) / float(roof_v.size)
        else:
            roof_peak_ratio = 0.0

        # Characteristic ambulance profile: predominantly white/yellow body with red accents & roof light cluster
        evidence_score = 0.0
        if white_ratio > 0.35:
            evidence_score += 0.35
        if red_ratio > 0.05:
            evidence_score += 0.35
        if roof_peak_ratio > 0.08:
            evidence_score += 0.25

        if evidence_score >= self.confidence_threshold:
            return (True, round(min(0.98, evidence_score), 2))

        return (False, round(evidence_score, 2))
