"""Scores use only vehicles currently assigned to a measurement ROI."""
from collections import Counter

CLASS_ALIASES = {
    "motorbike": "motorcycle", "scooter": "motorcycle", "two wheeler": "motorcycle",
    "two_wheeler": "motorcycle", "auto": "rickshaw", "autorickshaw": "rickshaw",
    "auto_rickshaw": "rickshaw", "auto rickshaw": "rickshaw", "ricksaw": "rickshaw",
    "rickshaws": "rickshaw", "ricksaws": "rickshaw", "van": "car",
}
# Unspecified motor vehicles use the car weight; bicycles use the two-wheeler weight.
VEHICLE_WEIGHTS = {"car": 2.0, "rickshaw": 1.5, "motorcycle": 1.0,
                   "bicycle": 1.0, "bus": 2.0, "truck": 2.0, "ambulance": 2.0}

def canonical_class(name: str) -> str:
    key = name.strip().lower()
    return CLASS_ALIASES.get(key, key)

def score_classes(classes) -> tuple[float, dict[str, int]]:
    counts = dict(Counter(canonical_class(name) for name in classes))
    return sum(VEHICLE_WEIGHTS.get(name, 0.0) * count for name, count in counts.items()), counts
