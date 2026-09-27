import unittest

from app.services.safety.helmet_analyzer import HelmetAnalyzer, HelmetObservation, HelmetState
from app.core.domain_config import DetectionConfig


class TestHelmetAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = HelmetAnalyzer(config=DetectionConfig(helmet_confidence=0.5))

    def test_classify_picks_higher_confidence_class(self):
        self.assertEqual(self.analyzer.classify(0.8, 0.1), HelmetState.HELMET)
        self.assertEqual(self.analyzer.classify(0.1, 0.9), HelmetState.NO_HELMET)

    def test_classify_below_threshold_is_unknown(self):
        self.assertEqual(self.analyzer.classify(0.3, 0.2), HelmetState.UNKNOWN)

    def test_no_helmet_generates_event_once_per_track(self):
        obs = HelmetObservation(track_id=42, confidence=0.9, state=HelmetState.NO_HELMET, lane_id="EAST", timestamp=0.0)
        event1 = self.analyzer.observe(obs)
        self.assertIsNotNone(event1)
        self.assertEqual(self.analyzer.violation_count, 1)

        # same track seen again on a later frame - should not double count
        obs2 = HelmetObservation(track_id=42, confidence=0.92, state=HelmetState.NO_HELMET, lane_id="EAST", timestamp=1.0)
        event2 = self.analyzer.observe(obs2)
        self.assertIsNone(event2)
        self.assertEqual(self.analyzer.violation_count, 1)

    def test_helmet_increments_compliant_not_violation(self):
        obs = HelmetObservation(track_id=1, confidence=0.9, state=HelmetState.HELMET, lane_id="EAST", timestamp=0.0)
        self.analyzer.observe(obs)
        self.assertEqual(self.analyzer.compliant_count, 1)
        self.assertEqual(self.analyzer.violation_count, 0)

    def test_compliance_rate_none_when_no_data(self):
        self.assertIsNone(self.analyzer.compliance_rate)

    def test_compliance_rate_computed_from_real_counts(self):
        self.analyzer.observe(HelmetObservation(1, 0.9, HelmetState.HELMET, "EAST", 0.0))
        self.analyzer.observe(HelmetObservation(2, 0.9, HelmetState.HELMET, "EAST", 0.0))
        self.analyzer.observe(HelmetObservation(3, 0.9, HelmetState.NO_HELMET, "EAST", 0.0))
        self.assertAlmostEqual(self.analyzer.compliance_rate, 2 / 3, places=3)

    def test_helmet_never_referenced_by_signal_modules(self):
        """Static guard: helmet_analyzer.py must not import signal/decision modules."""
        import inspect
        import app.services.safety.helmet_analyzer as mod
        source = inspect.getsource(mod)
        self.assertNotIn("signal_fsm", source)
        self.assertNotIn("decision_engine", source)


if __name__ == "__main__":
    unittest.main()
