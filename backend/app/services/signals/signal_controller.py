"""
SignalControllerInterface

Separates "what should happen" (SignalFSM's safe state transitions, driven
by TrafficDecisionEngine) from "how the physical/simulated lights actually
get set". This is the abstraction the spec requires so DHAARA is
technically defensible for real hardware deployment: the demo runs
`SimulationSignalController`, and a certified-hardware deployment would
implement `HardwareSignalControllerInterface.apply_state` against its own
controller's protocol (serial, Modbus, a vendor API, etc.) without any of
the FSM/decision code changing.

DHAARA does not claim to drive real traffic lights unless a concrete
`HardwareSignalController` subclass has actually been wired to certified
hardware - `SimulationSignalController` is used by default everywhere in
this repository.
"""
from __future__ import annotations

from typing import Protocol

from app.services.signals.signal_fsm import SignalState


class SignalHardwareError(Exception):
    """Raised when applying a signal state to real hardware fails
    (serial timeout, controller NACK, etc). Must never be swallowed -
    a failed hardware apply is a safety-relevant fault."""


class SignalControllerInterface(Protocol):
    def apply_state(self, intersection_id: str, state: SignalState) -> None: ...
    def health_check(self) -> bool: ...


class SimulationSignalController:
    """Default controller for this prototype: 'applying' a state simply
    means it is now the state IntersectionController/SignalFSM hold in
    memory (and whatever the API/WebSocket layer reads from them) - there
    is no physical output. Always reports healthy."""

    def __init__(self):
        self.applied_states: dict[str, SignalState] = {}

    def apply_state(self, intersection_id: str, state: SignalState) -> None:
        self.applied_states[intersection_id] = state

    def health_check(self) -> bool:
        return True


class HardwareSignalController:
    """Skeleton for a real-hardware deployment. NOT connected to any actual
    traffic-light controller in this repository - `apply_state` must be
    implemented against the target hardware's real protocol before this
    class is used outside simulation. Left unimplemented (raises) rather
    than silently behaving like the simulation controller, so it can never
    be mistaken for a working hardware integration.
    """

    def __init__(self, connection_config: dict):
        self._connection_config = connection_config

    def apply_state(self, intersection_id: str, state: SignalState) -> None:
        raise NotImplementedError(
            "HardwareSignalController.apply_state is not implemented - this prototype "
            "has no certified hardware integration. Implement this method against your "
            "traffic controller's real protocol (e.g. NTCIP, Modbus, vendor SDK) before "
            "using this class outside simulation."
        )

    def health_check(self) -> bool:
        return False
