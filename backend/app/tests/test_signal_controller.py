import unittest

from app.services.signals.signal_controller import SimulationSignalController, HardwareSignalController
from app.services.signals.signal_fsm import SignalFSM
from app.core.domain_config import DomainConfig, SignalTimings


class TestSimulationSignalController(unittest.TestCase):
    def test_apply_and_health(self):
        fsm = SignalFSM(["EAST", "WEST", "NORTH", "SOUTH"], config=DomainConfig(signal_timings=SignalTimings(fixed_phase_s=1)))
        controller = SimulationSignalController()
        controller.apply_state("OD-BBSR-001", fsm.state)
        self.assertTrue(controller.health_check())
        self.assertEqual(controller.applied_states["OD-BBSR-001"].active_direction, "EW")


class TestHardwareSignalController(unittest.TestCase):
    def test_unimplemented_raises_rather_than_pretending(self):
        controller = HardwareSignalController(connection_config={})
        fsm = SignalFSM(["EAST", "WEST", "NORTH", "SOUTH"], config=DomainConfig(signal_timings=SignalTimings(fixed_phase_s=1)))
        with self.assertRaises(NotImplementedError):
            controller.apply_state("OD-BBSR-001", fsm.state)
        self.assertFalse(controller.health_check())


if __name__ == "__main__":
    unittest.main()
