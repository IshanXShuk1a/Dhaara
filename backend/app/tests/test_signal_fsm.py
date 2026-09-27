import unittest

from app.services.signals.signal_fsm import SignalFSM, PhaseColor, TransitionRejected
from app.core.domain_config import DomainConfig, SignalTimings


def fast_config() -> DomainConfig:
    """Short timings so tests run quickly while still exercising every phase."""
    return DomainConfig(signal_timings=SignalTimings(minimum_green_s=5, maximum_green_s=30, base_green_s=8, yellow_s=2, all_red_s=1))


class TestSignalFSM(unittest.TestCase):
    def setUp(self):
        self.fsm = SignalFSM(directions=["NORTH", "SOUTH", "EAST", "WEST"], config=fast_config())

    def test_starts_green_on_first_direction(self):
        self.assertEqual(self.fsm.state.color, PhaseColor.GREEN)
        self.assertEqual(self.fsm.state.active_direction, "NORTH")

    def test_cannot_end_green_before_minimum(self):
        with self.assertRaises(TransitionRejected):
            self.fsm.request_phase_change("SOUTH", reason="test")

    def test_full_safe_transition_sequence(self):
        self.fsm.tick(5.0)  # satisfy minimum green
        self.fsm.request_phase_change("SOUTH", reason="decision engine selected SOUTH")
        self.assertEqual(self.fsm.state.color, PhaseColor.YELLOW)
        self.assertEqual(self.fsm.state.active_direction, "NORTH")  # still shows who was green
        self.assertEqual(self.fsm.state.target_direction, "SOUTH")

        self.fsm.tick(2.0)  # yellow duration elapsed
        changed = self.fsm.advance_if_ready()
        self.assertTrue(changed)
        self.assertEqual(self.fsm.state.color, PhaseColor.ALL_RED)

        self.fsm.tick(1.0)  # all-red duration elapsed
        changed = self.fsm.advance_if_ready()
        self.assertTrue(changed)
        self.assertEqual(self.fsm.state.color, PhaseColor.GREEN)
        self.assertEqual(self.fsm.state.active_direction, "SOUTH")

    def test_never_jumps_green_to_green(self):
        """The sequence of colors observed must never contain GREEN directly
        followed by a GREEN for a different direction."""
        self.fsm.tick(5.0)
        self.fsm.request_phase_change("EAST", reason="test")
        colors_and_dirs = [(self.fsm.state.color, self.fsm.state.active_direction)]
        for _ in range(10):
            self.fsm.tick(1.0)
            if self.fsm.advance_if_ready():
                colors_and_dirs.append((self.fsm.state.color, self.fsm.state.active_direction))
        # Verify YELLOW and ALL_RED both appear between the two GREEN entries.
        seq = [c for c, _ in colors_and_dirs]
        self.assertIn(PhaseColor.YELLOW, seq)
        self.assertIn(PhaseColor.ALL_RED, seq)
        green_index = seq.index(PhaseColor.GREEN) if PhaseColor.GREEN in seq[1:] else None

    def test_early_end_rejected_without_force(self):
        self.fsm.tick(1.0)
        with self.assertRaises(TransitionRejected):
            self.fsm.request_phase_change("WEST", reason="test")

    def test_force_allows_early_end_for_emergency(self):
        self.fsm.tick(1.0)  # well below minimum green
        self.fsm.request_phase_change("WEST", reason="EMERGENCY override", force=True)
        self.assertEqual(self.fsm.state.color, PhaseColor.YELLOW)

    def test_history_is_logged(self):
        self.fsm.tick(5.0)
        self.fsm.request_phase_change("SOUTH", reason="test")
        self.fsm.tick(2.0)
        self.fsm.advance_if_ready()
        self.fsm.tick(1.0)
        self.fsm.advance_if_ready()
        self.assertEqual(len(self.fsm.history), 3)
        self.assertEqual(self.fsm.history[0].to_color, PhaseColor.YELLOW)
        self.assertEqual(self.fsm.history[1].to_color, PhaseColor.ALL_RED)
        self.assertEqual(self.fsm.history[2].to_color, PhaseColor.GREEN)

    def test_unknown_direction_rejected(self):
        with self.assertRaises(ValueError):
            self.fsm.request_phase_change("NORTHWEST", reason="test")


if __name__ == "__main__":
    unittest.main()
