"""Temporal red/blue roof-beacon evidence; steady paint or reflections are insufficient."""
from collections import deque
import cv2
import numpy as np

class EmergencyLightTracker:
    def __init__(self, window_s=3.0, max_dark_s=0.8):
        self.window_s = window_s
        self.max_dark_s = max_dark_s
        self._samples = {}

    def observe(self, track_id, image, bbox, timestamp):
        h, w = image.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, x2 = max(0, int(x1)), min(w, int(x2))
        y1, y2 = max(0, int(y1)), min(h, int(y1 + (y2 - y1) * .30))
        crop = image[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 3 or crop.shape[1] < 8:
            self._samples.pop(track_id, None)
            return False
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        colored = ((hue <= 12) | (hue >= 168) | ((hue >= 95) & (hue <= 135))) & (sat >= 120) & (val >= 200)
        fraction = np.count_nonzero(colored) / colored.size
        state = True if fraction >= .025 else False if fraction <= .008 else None
        samples = self._samples.setdefault(track_id, deque())
        while samples and samples[0][0] < timestamp - self.window_s:
            samples.popleft()
        if state is not None and (not samples or timestamp > samples[-1][0]):
            samples.append((timestamp, state))
        states = [s for _, s in samples]
        transitions = sum(a != b for a, b in zip(states, states[1:]))
        last_on = max((t for t, s in samples if s), default=float("-inf"))
        return (transitions >= 3 and states.count(True) >= 2 and states.count(False) >= 2
                and timestamp - last_on <= self.max_dark_s)

    def retain(self, active_ids):
        self._samples = {key: value for key, value in self._samples.items() if key in active_ids}
