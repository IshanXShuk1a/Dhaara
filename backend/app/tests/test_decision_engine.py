import unittest

from app.services.decision.fairness import FairnessTracker
from app.services.decision.decision_engine import TrafficDecisionEngine
from app.services.lanes.lane_intelligence import LaneMetrics, LaneStatus
from app.core.domain_config import DomainConfig, FairnessConfig


def make_metrics(lane_id: str, pressure: float, queue=10.0, wait=10.0, count=5) -> LaneMetrics:
    return LaneMetrics(
        lane_id=lane_id,
        vehicle_count=count,
        occupancy=pressure / 100,
        queue_length_m=queue,
        average_speed_kmph=20,
        average_waiting_time_s=wait,
        flow_rate=5,
        traffic_pressure=pressure,
        status=LaneStatus.HIGH,
        reasons=[],
    )


class TestFairnessTracker(unittest.TestCase):
    def test_eligible_by_default(self):
        f = FairnessTracker(FairnessConfig(consecutive_priority_limit=3))
        self.assertTrue(f.is_eligible("NORTH"))

    def test_blocks_after_limit(self):
        f = FairnessTracker(FairnessConfig(consecutive_priority_limit=3))
        for _ in range(3):
            f.record_selection("NORTH")
        self.assertFalse(f.is_eligible("NORTH"))
        self.assertTrue(f.is_eligible("SOUTH"))

    def test_resets_streak_on_different_direction(self):
        f = FairnessTracker(FairnessConfig(consecutive_priority_limit=3))
        f.record_selection("NORTH")
        f.record_selection("NORTH")
        f.record_selection("SOUTH")
        self.assertEqual(f.state.last_selected_direction, "SOUTH")
        self.assertEqual(f.state.consecutive_count, 1)
        self.assertTrue(f.is_eligible("NORTH"))


class TestTrafficDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.fairness = FairnessTracker(FairnessConfig(consecutive_priority_limit=3))
        self.engine = TrafficDecisionEngine(self.fairness)

    def test_selects_highest_pressure(self):
        metrics = {
            "NORTH": make_metrics("NORTH", 20),
            "SOUTH": make_metrics("SOUTH", 86),
            "EAST": make_metrics("EAST", 52),
            "WEST": make_metrics("WEST", 8),
        }
        decision = self.engine.decide(metrics, current_direction="NORTH")
        self.assertEqual(decision.selected_direction, "SOUTH")
        self.assertTrue(any("pressure" in r.lower() for r in decision.reason))

    def test_green_duration_scales_with_pressure(self):
        low = make_metrics("NORTH", 5)
        high = make_metrics("NORTH", 95)
        d_low = self.engine._green_duration(low)
        d_high = self.engine._green_duration(high)
        self.assertLess(d_low, d_high)
        self.assertGreaterEqual(d_low, self.engine._timings.minimum_green_s)
        self.assertLessEqual(d_high, self.engine._timings.maximum_green_s)

    def test_fairness_blocks_repeated_direction(self):
        metrics = {
            "NORTH": make_metrics("NORTH", 90),
            "SOUTH": make_metrics("SOUTH", 40),
        }
        # NORTH wins 3 times in a row (the fairness limit)
        for _ in range(3):
            d = self.engine.decide(metrics, current_direction="SOUTH")
            self.assertEqual(d.selected_direction, "NORTH")
        # 4th time, NORTH must be skipped even though it has higher pressure
        d4 = self.engine.decide(metrics, current_direction="SOUTH")
        self.assertEqual(d4.selected_direction, "SOUTH")
        self.assertTrue(d4.fairness_applied)

    def test_emergency_overrides_fairness_and_pressure(self):
        metrics = {
            "NORTH": make_metrics("NORTH", 90),
            "SOUTH": make_metrics("SOUTH", 5),
        }
        decision = self.engine.decide(metrics, current_direction="NORTH", emergency_direction="SOUTH")
        self.assertEqual(decision.selected_direction, "SOUTH")
        self.assertEqual(decision.mode, "EMERGENCY")
        self.assertFalse(decision.fairness_applied)

    def test_reason_is_explainable(self):
        metrics = {"NORTH": make_metrics("NORTH", 50, queue=30, wait=25, count=12)}
        d = self.engine.decide(metrics, current_direction="NORTH")
        joined = " ".join(d.reason)
        self.assertIn("30", joined)
        self.assertIn("25", joined)
        self.assertIn("12", joined)


if __name__ == "__main__":
    unittest.main()
