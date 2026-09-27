"""
Computer Vision Helmet Detector

Analyzes motorcycle vehicle detections to determine whether the rider
is wearing a helmet or has a helmet violation (NO_HELMET).
Uses OpenCV spatial analysis, rider head ROI cropping, and color/texture
cues to evaluate helmet presence without interfering with traffic signal timing.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.services.safety.helmet_analyzer import HelmetState


class HelmetDetector:
    def __init__(self, confidence_threshold: float = 0.55):
        self.confidence_threshold = confidence_threshold

    def evaluate(self, image: np.ndarray | None, bbox: tuple[float, float, float, float]) -> tuple[HelmetState, float]:
        """Evaluates helmet status on the motorcycle bounding box.

        Returns (HelmetState, confidence).
        """
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return (HelmetState.UNKNOWN, 0.0)

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        box_w = x2 - x1
        box_h = y2 - y1
        if box_w < 15 or box_h < 25:
            return (HelmetState.UNKNOWN, 0.0)

        # Rider head is typically located in the top 35% of the motorcycle bbox
        head_y1 = y1
        head_y2 = y1 + int(box_h * 0.35)
        # Narrow the x-bounds slightly toward the center
        head_x1 = x1 + int(box_w * 0.2)
        head_x2 = x2 - int(box_w * 0.2)

        if head_y2 <= head_y1 or head_x2 <= head_x1:
            return (HelmetState.UNKNOWN, 0.0)

        crop = image[head_y1:head_y2, head_x1:head_x2]
        if crop.size == 0:
            return (HelmetState.UNKNOWN, 0.0)

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # Skin tone range in HSV (exposed face/neck/bare head)
        lower_skin = np.array([0, 30, 60], dtype=np.uint8)
        upper_skin = np.array([25, 180, 255], dtype=np.uint8)
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_ratio = float(np.count_nonzero(skin_mask)) / float(crop.shape[0] * crop.shape[1])

        # Gray gradient / edge smoothness: helmets have smooth curved specular boundaries
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Helmet shell color uniformity (high brightness or distinct solid color)
        v_channel = hsv[:, :, 2]
        high_specular = float(np.count_nonzero(v_channel > 200)) / float(v_channel.size)

        # Heuristic scoring: high exposed skin ratio + textured hair indicates NO_HELMET
        if skin_ratio > 0.28:
            no_helmet_conf = min(0.95, 0.5 + skin_ratio * 0.9)
            return (HelmetState.NO_HELMET, round(no_helmet_conf, 2))
        elif high_specular > 0.15 or (skin_ratio < 0.12 and laplacian_var < 500):
            helmet_conf = min(0.92, 0.55 + high_specular * 0.8)
            return (HelmetState.HELMET, round(helmet_conf, 2))
        else:
            return (HelmetState.UNKNOWN, 0.45)
