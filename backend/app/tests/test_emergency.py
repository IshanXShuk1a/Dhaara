import unittest

from app.services.emergency.ambulance_confirmation import (
    AmbulanceConfirmationTracker,
    AmbulanceObservation,
    ConfirmationState,
)
from app.services.emergency.emergency_manager import EmergencyManager, EmergencyState
from app.core.domain_config import DomainConfig, DetectionConfig


class TestAmbulanceConfirmation(unittest.TestCase):
    def setUp(self):
        self.config = DetectionConfig(ambulance_confidence=0.6, ambulance_confirmation_frames=5, ambulance_confirmation_window_s=4.0)
        self.tracker = AmbulanceConfirmationTracker(self.config)

    def test_single_frame_does_not_confirm(self):
        candidate = self.tracker.observe(
            AmbulanceObservation(track_id=1, confidence=0.9, approaching=True, lane_id="NORTH", direction="NORTH", timestamp=0.0)
        )
        self.assertEqual(candidate.state, ConfirmationState.CANDIDATE)

    def test_confirms_after_enough_qualifying_frames(self):
        for t in range(5):
            candidate = self.tracker.observe(
                AmbulanceObservation(track_id=1, confidence=0.9, approaching=True, lane_id="NORTH", direction="NORTH", timestamp=float(t) * 0.5)
            )
        self.assertEqual(candidate.state, ConfirmationState.CONFIRMED)

    def test_low_confidence_never_confirms(self):
        for t in range(10):
            candidate = self.tracker.observe(
                AmbulanceObservation(track_id=1, confidence=0.3, approaching=True, lane_id="NORTH", direction="NORTH", timestamp=float(t) * 0.5)
            )
        self.assertNotEqual(candidate.state, ConfirmationState.CONFIRMED)

    def test_not_approaching_never_confirms(self):
        for t in range(10):
            candidate = self.tracker.observe(
                AmbulanceObservation(track_id=1, confidence=0.95, approaching=False, lane_id="NORTH", direction="NORTH", timestamp=float(t) * 0.5)
            )
        self.assertNotEqual(candidate.state, ConfirmationState.CONFIRMED)

    def test_old_observations_fall_outside_window(self):
        # Two qualifying frames far apart in time should not combine.
        self.tracker.observe(
            AmbulanceObservation(track_id=1, confidence=0.9, approaching=True, lane_id="NORTH", direction="NORTH", timestamp=0.0)
        )
        candidate = self.tracker.observe(
            AmbulanceObservation(track_id=1, confidence=0.9, approaching=True, lane_id="NORTH", direction="NORTH", timestamp=100.0)
        )
        self.assertEqual(len(candidate.observations), 1)  # the first fell outside the window


class TestEmergencyManager(unittest.TestCase):
    def _confirmed_candidate(self, track_id=1, lane="NORTH", direction="NORTH"):
        config = DetectionConfig(ambulance_confidence=0.6, ambulance_confirmation_frames=3, ambulance_confirmation_window_s=4.0)
        tracker = AmbulanceConfirmationTracker(config)
        for t in range(3):
            candidate = tracker.observe(
                AmbulanceObservation(track_id=track_id, confidence=0.9, approaching=True, lane_id=lane, direction=direction, timestamp=float(t))
            )
        return candidate

    def test_full_lifecycle(self):
        mgr = EmergencyManager()
        candidate = self._confirmed_candidate()

        mgr.on_candidate_detected(candidate, timestamp=0.0)
        self.assertEqual(mgr.state, EmergencyState.DETECTED)

        mgr.on_candidate_confirmed(candidate, timestamp=1.0)
        self.assertEqual(mgr.state, EmergencyState.CONFIRMED)
        self.assertEqual(mgr.active_direction, "NORTH")

        mgr.request_priority(timestamp=2.0)
        self.assertEqual(mgr.state, EmergencyState.PRIORITY_REQUESTED)
        self.assertEqual(mgr.emergency_direction, "NORTH")

        mgr.mark_priority_active(timestamp=3.0)
        self.assertEqual(mgr.state, EmergencyState.PRIORITY_ACTIVE)
        self.assertEqual(mgr.emergency_direction, "NORTH")

        # ambulance still present for a few ticks, then leaves
        mgr.observe_tick(still_present=True, timestamp=4.0)
        self.assertEqual(mgr.state, EmergencyState.PRIORITY_ACTIVE)
        for i in range(5, 11):
            mgr.observe_tick(still_present=False, timestamp=float(i))
        self.assertEqual(mgr.state, EmergencyState.PASSED)

        mgr.resolve(timestamp=11.0)
        self.assertEqual(mgr.state, EmergencyState.NONE)
        self.assertIsNone(mgr.active_direction)
        self.assertIsNone(mgr.emergency_direction)

    def test_second_ambulance_ignored_while_one_is_active(self):
        mgr = EmergencyManager()
        c1 = self._confirmed_candidate(track_id=1, lane="NORTH", direction="NORTH")
        mgr.on_candidate_confirmed(c1, timestamp=0.0)
        self.assertEqual(mgr.active_track_id, 1)

        c2 = self._confirmed_candidate(track_id=2, lane="SOUTH", direction="SOUTH")
        mgr.on_candidate_confirmed(c2, timestamp=1.0)
        # still tracking the first ambulance, not overwritten by the second
        self.assertEqual(mgr.active_track_id, 1)
        self.assertEqual(mgr.active_direction, "NORTH")

    def test_events_are_logged(self):
        mgr = EmergencyManager()
        candidate = self._confirmed_candidate()
        mgr.on_candidate_detected(candidate, timestamp=0.0)
        mgr.on_candidate_confirmed(candidate, timestamp=1.0)
        mgr.request_priority(timestamp=2.0)
        self.assertEqual(len(mgr.events), 3)
        self.assertEqual(mgr.events[-1].state, EmergencyState.PRIORITY_REQUESTED)


if __name__ == "__main__":
    unittest.main()
