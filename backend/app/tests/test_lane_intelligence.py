import unittest

from app.services.lanes.lane_intelligence import (
    LaneIntelligenceEngine,
    LaneGeometry,
    TrackedVehicleSnapshot,
    LaneStatus,
    classify_status,
    compute_traffic_pressure,
)
from app.core.domain_config import DEFAULT_CONFIG


class TestClassifyStatus(unittest.TestCase):
    def test_boundaries(self):
        t = DEFAULT_CONFIG.lane_thresholds
        self.assertEqual(classify_status(0, t), LaneStatus.FREE)
        self.assertEqual(classify_status(t.free_max, t), LaneStatus.FREE)
        self.assertEqual(classify_status(t.free_max + 0.1, t), LaneStatus.LOW)
        self.assertEqual(classify_status(t.low_max + 0.1, t), LaneStatus.MODERATE)
        self.assertEqual(classify_status(t.moderate_max + 0.1, t), LaneStatus.HIGH)
        self.assertEqual(classify_status(t.high_max + 0.1, t), LaneStatus.CONGESTED)
        self.assertEqual(classify_status(100, t), LaneStatus.CONGESTED)

    def test_never_out_of_defined_states(self):
        t = DEFAULT_CONFIG.lane_thresholds
        for p in range(0, 101):
            self.assertIn(classify_status(p, t), list(LaneStatus))


class TestComputeTrafficPressure(unittest.TestCase):
    def test_empty_road_is_low_pressure(self):
        w = DEFAULT_CONFIG.pressure_weights
        p = compute_traffic_pressure(0, 0, 0, 0, w.free_flow_speed_kmph, w)
        self.assertLess(p, 5)

    def test_full_congestion_is_high_pressure(self):
        w = DEFAULT_CONFIG.pressure_weights
        p = compute_traffic_pressure(
            occupancy=1.0,
            queue_length_m=w.max_queue_m,
            vehicle_count=w.max_vehicle_count,
            average_waiting_time_s=w.max_waiting_time_s,
            average_speed_kmph=0,
            weights=w,
        )
        self.assertGreater(p, 85)

    def test_clamped_to_0_100(self):
        w = DEFAULT_CONFIG.pressure_weights
        p_low = compute_traffic_pressure(0, 0, 0, 0, w.free_flow_speed_kmph * 10, w)
        p_high = compute_traffic_pressure(10, 10_000, 10_000, 10_000, 0, w)
        self.assertGreaterEqual(p_low, 0)
        self.assertLessEqual(p_high, 100)

    def test_higher_speed_reduces_pressure_all_else_equal(self):
        w = DEFAULT_CONFIG.pressure_weights
        slow = compute_traffic_pressure(0.5, 20, 10, 20, 5, w)
        fast = compute_traffic_pressure(0.5, 20, 10, 20, 40, w)
        self.assertGreater(slow, fast)


class TestLaneIntelligenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = LaneIntelligenceEngine()
        self.geometry = LaneGeometry(lane_id="NORTH", length_m=60, capacity_vehicles=25, vehicle_spacing_m=7)

    def test_no_vehicles_is_free(self):
        metrics = self.engine.compute(self.geometry, [])
        self.assertEqual(metrics.vehicle_count, 0)
        self.assertEqual(metrics.status, LaneStatus.FREE)
        self.assertEqual(metrics.traffic_pressure, 0.0)

    def test_light_traffic_is_low_or_free(self):
        vehicles = [
            TrackedVehicleSnapshot(track_id=i, speed_kmph=35, waiting_time_s=1, is_stopped=False)
            for i in range(3)
        ]
        metrics = self.engine.compute(self.geometry, vehicles)
        self.assertIn(metrics.status, (LaneStatus.FREE, LaneStatus.LOW))
        self.assertEqual(metrics.vehicle_count, 3)

    def test_heavy_queued_traffic_is_congested(self):
        # Fill the lane to capacity, fully stopped, at maximum modeled waiting
        # time and near-zero speed - the worst case the formula can express.
        vehicles = [
            TrackedVehicleSnapshot(track_id=i, speed_kmph=0, waiting_time_s=90, is_stopped=True)
            for i in range(self.geometry.capacity_vehicles)
        ]
        metrics = self.engine.compute(self.geometry, vehicles)
        self.assertEqual(metrics.status, LaneStatus.CONGESTED)
        self.assertGreater(metrics.queue_length_m, 0)
        self.assertTrue(len(metrics.reasons) > 0)

    def test_metrics_explainable_with_reasons(self):
        vehicles = [
            TrackedVehicleSnapshot(track_id=i, speed_kmph=8, waiting_time_s=40, is_stopped=True)
            for i in range(15)
        ]
        metrics = self.engine.compute(self.geometry, vehicles)
        self.assertTrue(any("wait" in r for r in metrics.reasons))


if __name__ == "__main__":
    unittest.main()
