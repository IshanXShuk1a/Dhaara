"""
Unit tests for CV heuristic detectors (AmbulanceDetector, HelmetDetector) and
IntersectionController signal modes (FIXED, MANUAL, ADAPTIVE).
"""
import unittest
import numpy as np

from app.services.cv.ambulance_detector import AmbulanceDetector
from app.services.cv.helmet_detector import HelmetDetector
from app.services.safety.helmet_analyzer import HelmetState
from app.services.signals.signal_controller import SignalMode
from app.services.controllers.intersection_controller import IntersectionController
from app.services.cv.detector import SimulationDetector
from app.services.cv.lane_assigner import LanePolygon
from app.services.simulation.simulation_engine import ScenarioProvider
from app.core.domain_config import DomainConfig, SignalTimings


class TestAmbulanceDetector(unittest.TestCase):
    def setUp(self):
        self.detector = AmbulanceDetector()

    def test_dark_car_is_not_ambulance(self):
        # A dark grey/black car image (H, W, 3)
        image = np.full((120, 100, 3), (30, 30, 30), dtype=np.uint8)
        is_amb, conf = self.detector.is_ambulance(image, (0, 0, 100, 120), "car")
        self.assertFalse(is_amb)
        self.assertLess(conf, 0.4)

    def test_white_vehicle_with_red_cross_is_detected(self):
        # Create an image that looks like an ambulance:
        # white background with red cross in center and bright roof lights
        image = np.full((120, 100, 3), (245, 245, 245), dtype=np.uint8)
        # Red cross in center (BGR: B=20, G=20, R=220)
        image[50:70, 35:65] = (20, 20, 220)
        image[40:80, 45:55] = (20, 20, 220)
        # Top roof beacon
        image[5:15, 40:60] = (255, 255, 255)
        is_amb, conf = self.detector.is_ambulance(image, (0, 0, 100, 120), "truck")
        self.assertTrue(is_amb)
        self.assertGreater(conf, 0.5)


class TestHelmetDetector(unittest.TestCase):
    def setUp(self):
        self.detector = HelmetDetector()

    def test_invalid_or_tiny_crop_returns_unknown(self):
        tiny = np.zeros((3, 3, 3), dtype=np.uint8)
        state, conf = self.detector.evaluate(tiny, (0, 0, 3, 3))
        self.assertEqual(state, HelmetState.UNKNOWN)

    def test_colored_helmet_head_crop(self):
        # Head crop wearing a bright protective white/yellow helmet (low skin HSV, high helmet color)
        head_crop = np.full((40, 40, 3), (0, 220, 255), dtype=np.uint8)  # yellow helmet
        state, conf = self.detector.evaluate(head_crop, (0, 0, 40, 40))
        self.assertIn(state, (HelmetState.HELMET, HelmetState.UNKNOWN))


class TestIntersectionControllerModes(unittest.TestCase):
    def _make_controller(self):
        lanes = [
            LanePolygon("NORTH", "NORTH", [(0, 0), (50, 0), (50, 50), (0, 50)]),
            LanePolygon("SOUTH", "SOUTH", [(50, 50), (100, 50), (100, 100), (50, 100)]),
        ]
        provider = ScenarioProvider()
        detector = SimulationDetector(provider)
        config = DomainConfig(signal_timings=SignalTimings(fixed_phase_s=2))
        return IntersectionController(
            intersection_id="TEST-INT-01",
            lanes=lanes + [LanePolygon(d,d,[(0,0),(10,0),(10,10),(0,10)]) for d in ["EAST","WEST"]],
            directions=["EAST", "WEST", "NORTH", "SOUTH"],
            detector=detector,
            config=config,
            fps=10.0,
        )

    def test_adaptive_mode_default(self):
        c = self._make_controller()
        self.assertEqual(c.signal_mode, SignalMode.ADAPTIVE)

    def test_manual_mode_holds_signal(self):
        c = self._make_controller()
        c.set_signal_mode(SignalMode.MANUAL, target_direction="NORTH")
        self.assertEqual(c.signal_mode, SignalMode.MANUAL)
        self.assertEqual(c.signal_target_direction, "NS")
        # In MANUAL mode, active direction remains held
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        snap = c.process_frame(dummy_frame, frame_index=1, dt_seconds=0.1)
        self.assertEqual(snap.signal_state, "YELLOW")
        self.assertEqual(snap.signal_target_direction, "NS")
        self.assertEqual(snap.decision.mode, "MANUAL")
        snap = c.process_frame(dummy_frame, frame_index=2, dt_seconds=3)
        self.assertEqual(snap.signal_active_direction, "NS")
        self.assertEqual(snap.signal_state, "GREEN")

    def test_fixed_mode_cycles(self):
        c = self._make_controller()
        c.set_signal_mode(SignalMode.FIXED)
        self.assertEqual(c.signal_mode, SignalMode.FIXED)
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        snap = c.process_frame(dummy_frame, frame_index=1, dt_seconds=0.1)
        self.assertIsNotNone(snap)

    def test_lane_density_and_allotment(self):
        c = self._make_controller()
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        snap = c.process_frame(dummy_frame, frame_index=1, dt_seconds=0.1)
        self.assertIn("NORTH", snap.lane_metrics)
        self.assertIn("SOUTH", snap.lane_metrics)
        # Verify density calculation returns valid non-negative pressure
        for lane_id, m in snap.lane_metrics.items():
            self.assertGreaterEqual(m.traffic_pressure, 0.0)
            self.assertLessEqual(m.traffic_pressure, 100.0)
        # Verify green allotment state exists
        self.assertIn(snap.signal_active_direction, ("EW", "NS"))


if __name__ == "__main__":
    unittest.main()
