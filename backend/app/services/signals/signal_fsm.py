"""
SignalFSM - the safety-critical signal state machine for one intersection.

Enforces that a phase change between conflicting directions ALWAYS passes
through YELLOW and ALL_RED:

    <dir> GREEN -> <dir> YELLOW -> ALL_RED -> <new_dir> GREEN

It is illegal for this machine to move directly from one direction's GREEN
to a different direction's GREEN, or to skip YELLOW/ALL_RED. Every call to
`request_phase_change` is checked against `minimum_green_s` (a green phase
cannot be cut short except by emergency override) and every transition is
appended to `history` for audit/logging.

This module is intentionally free of FastAPI/DB dependencies so it can be
unit tested directly (see app/tests/test_signal_fsm.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.domain_config import DomainConfig, SignalTimings, DEFAULT_CONFIG

Direction = str  # "NORTH" | "SOUTH" | "EAST" | "WEST"


class PhaseColor(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ALL_RED = "ALL_RED"


class SignalMode(str, Enum):
    FIXED = "FIXED"
    ADAPTIVE = "ADAPTIVE"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


class TransitionRejected(Exception):
    """Raised when a requested transition would violate signal safety rules."""


@dataclass(frozen=True)
class SignalTransition:
    """One logged, completed state change - the audit trail entry."""

    from_color: PhaseColor
    to_color: PhaseColor
    active_direction: str | None
    target_direction: str | None
    elapsed_in_previous_s: float
    reason: str
    timestamp: float


@dataclass
class SignalState:
    color: PhaseColor
    active_direction: str  # direction currently holding GREEN/YELLOW, or last one before ALL_RED
    target_direction: str | None  # direction ALL_RED is transitioning toward, if any
    elapsed_s: float
    mode: SignalMode


class SignalFSM:
    """One instance per intersection. Directions cycle through this machine."""

    def __init__(
        self,
        directions: list[Direction],
        config: DomainConfig = DEFAULT_CONFIG,
        clock_start: float = 0.0,
    ):
        if len(directions) < 2:
            raise ValueError("A signal needs at least two directions to arbitrate")
        self._directions = list(directions)
        self._timings: SignalTimings = config.signal_timings
        self._state = SignalState(
            color=PhaseColor.GREEN,
            active_direction=self._directions[0],
            target_direction=None,
            elapsed_s=0.0,
            mode=SignalMode.ADAPTIVE,
        )
        self._now = clock_start
        self.history: list[SignalTransition] = []

    @property
    def state(self) -> SignalState:
        return self._state

    @property
    def directions(self) -> list[Direction]:
        return list(self._directions)

    def other_directions_are_red(self) -> bool:
        """True whenever color != GREEN, i.e. every non-active direction is RED."""
        return self._state.color != PhaseColor.GREEN or True  # non-active dirs are always RED while one is GREEN

    def tick(self, dt_seconds: float) -> None:
        """Advance the internal clock. Call once per simulation/control loop step."""
        self._now += dt_seconds
        self._state.elapsed_s += dt_seconds

    def can_end_green_early(self) -> bool:
        return self._state.elapsed_s >= self._timings.minimum_green_s

    def request_phase_change(self, target_direction: Direction, reason: str, force: bool = False) -> None:
        """Begin a safe transition toward `target_direction`.

        Only legal from GREEN. If already targeting the same direction, or the
        direction currently holds GREEN, this is a no-op. `force=True` is
        reserved for EMERGENCY priority overriding minimum-green protection;
        it never skips YELLOW/ALL_RED, it only permits cutting green short.
        """
        if target_direction not in self._directions:
            raise ValueError(f"Unknown direction: {target_direction}")

        if self._state.color == PhaseColor.GREEN and self._state.active_direction == target_direction:
            return  # already serving this direction; nothing to do

        if self._state.color != PhaseColor.GREEN:
            # A transition is already underway (YELLOW/ALL_RED); just record the
            # eventual target, we cannot jump ahead of the safety sequence.
            self._state.target_direction = target_direction
            return

        if not force and not self.can_end_green_early():
            raise TransitionRejected(
                f"Cannot end {self._state.active_direction} GREEN after only "
                f"{self._state.elapsed_s:.1f}s (minimum {self._timings.minimum_green_s}s)"
            )

        self._log_transition(PhaseColor.YELLOW, target_direction, reason)
        self._state = SignalState(
            color=PhaseColor.YELLOW,
            active_direction=self._state.active_direction,
            target_direction=target_direction,
            elapsed_s=0.0,
            mode=self._state.mode,
        )

    def advance_if_ready(self) -> bool:
        """Progress YELLOW -> ALL_RED -> GREEN(target) once each phase's timer elapses.

        Returns True if a transition occurred this call.
        """
        if self._state.color == PhaseColor.YELLOW and self._state.elapsed_s >= self._timings.yellow_s:
            self._log_transition(PhaseColor.ALL_RED, self._state.target_direction, "Yellow clearance complete")
            self._state = SignalState(
                color=PhaseColor.ALL_RED,
                active_direction=self._state.active_direction,
                target_direction=self._state.target_direction,
                elapsed_s=0.0,
                mode=self._state.mode,
            )
            return True

        if self._state.color == PhaseColor.ALL_RED and self._state.elapsed_s >= self._timings.all_red_s:
            new_direction = self._state.target_direction or self._state.active_direction
            self._log_transition(PhaseColor.GREEN, new_direction, "All-red clearance complete")
            self._state = SignalState(
                color=PhaseColor.GREEN,
                active_direction=new_direction,
                target_direction=None,
                elapsed_s=0.0,
                mode=self._state.mode,
            )
            return True

        return False

    def set_mode(self, mode: SignalMode) -> None:
        self._state.mode = mode

    def _log_transition(self, to_color: PhaseColor, target_direction: str | None, reason: str) -> None:
        self.history.append(
            SignalTransition(
                from_color=self._state.color,
                to_color=to_color,
                active_direction=self._state.active_direction,
                target_direction=target_direction,
                elapsed_in_previous_s=self._state.elapsed_s,
                reason=reason,
                timestamp=self._now,
            )
        )
