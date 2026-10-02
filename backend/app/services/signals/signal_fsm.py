"""Atomic paired signal phases: EW or NS, with one clock per phase."""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable
import math
from app.core.domain_config import DomainConfig, DEFAULT_CONFIG

PHASE_DIRECTIONS = {"EW": ("EAST", "WEST"), "NS": ("NORTH", "SOUTH")}

def phase_for(direction: str) -> str:
    if direction in PHASE_DIRECTIONS:
        return direction
    for phase, directions in PHASE_DIRECTIONS.items():
        if direction in directions:
            return phase
    raise ValueError(f"Unknown direction or phase: {direction}")

def opposite_phase(phase: str) -> str:
    return "NS" if phase_for(phase) == "EW" else "EW"

class PhaseColor(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"

class SignalMode(str, Enum):
    FIXED = "FIXED"
    ADAPTIVE = "ADAPTIVE"
    MANUAL = "MANUAL"

class TransitionRejected(Exception):
    pass

@dataclass(frozen=True)
class SignalTransition:
    from_color: PhaseColor
    to_color: PhaseColor
    active_direction: str | None
    target_direction: str | None
    elapsed_in_previous_s: float
    reason: str
    timestamp: float

@dataclass(frozen=True)
class SignalState:
    color: PhaseColor
    active_direction: str
    target_direction: str | None
    elapsed_s: float
    mode: SignalMode
    previous_phase: str | None = None
    full_phase_required: bool = False
    pending_full_phase_required: bool = False
    yellow_duration_s: float = 0.0
    resume_green_elapsed_s: float = 0.0
    transition_action: str | None = None
    transition_reason: str = ""

class SignalFSM:
    def __init__(self, directions: list[str], config: DomainConfig = DEFAULT_CONFIG, clock_start: float = 0.0,
                 clock: Callable[[], float] | None = None):
        if len(directions) != 4 or set(directions) != {d for pair in PHASE_DIRECTIONS.values() for d in pair}:
            raise ValueError("A paired signal requires EAST, WEST, NORTH and SOUTH exactly once")
        if not math.isfinite(config.signal_timings.yellow_s) or config.signal_timings.yellow_s <= 0:
            raise ValueError("Yellow duration must be finite and positive")
        self._directions = list(directions)
        self._timings = config.signal_timings
        self._state = SignalState(PhaseColor.GREEN, "EW", None, 0.0, SignalMode.ADAPTIVE)
        self._now = clock_start
        self._clock = clock
        self._last_clock_read = clock() if clock else None
        self.history: list[SignalTransition] = []

    @property
    def state(self):
        return self._state

    @property
    def directions(self):
        return list(self._directions)

    @property
    def direction_states(self):
        active_pair = PHASE_DIRECTIONS[self._state.active_direction]
        return {d: self._state.color.value if d in active_pair else "RED" for d in self._directions}

    @property
    def countdown_s(self):
        duration = self._state.yellow_duration_s if self._state.color == PhaseColor.YELLOW else self._timings.fixed_phase_s
        return max(0.0, duration - self._state.elapsed_s)

    def other_directions_are_red(self):
        active_pair = PHASE_DIRECTIONS[self._state.active_direction]
        return all(s == "RED" for d, s in self.direction_states.items() if d not in active_pair)

    def _record_transition(self, old, reason):
        self.history.append(SignalTransition(old.color, self._state.color, self._state.active_direction,
                                             self._state.target_direction, old.elapsed_s, reason, self._now))
        self.history = self.history[-1000:]

    def tick(self, dt_seconds: float) -> bool:
        if not math.isfinite(dt_seconds) or dt_seconds < 0:
            raise ValueError("Clock increment must be finite and nonnegative")
        if self._clock is not None:
            now = self._clock()
            dt_seconds = max(0.0, now - self._last_clock_read)
            self._last_clock_read = now
        self._now += dt_seconds
        self._state = replace(self._state, elapsed_s=self._state.elapsed_s + dt_seconds)
        if self._state.color != PhaseColor.YELLOW or self.countdown_s > 1e-9:
            return False
        old = self._state
        target = old.target_direction
        # An output reaches GREEN only now; no overdue tick consumes its new green time.
        if target == old.active_direction:  # a withdrawn ambulance request resumes the old clock
            self._state = SignalState(PhaseColor.GREEN, target, None, old.resume_green_elapsed_s,
                                      old.mode, old.previous_phase, old.full_phase_required)
        else:
            self._state = SignalState(PhaseColor.GREEN, target, None, 0.0, old.mode,
                                      old.active_direction, old.pending_full_phase_required)
        self._record_transition(old, f"Yellow completed: {old.transition_reason}")
        return True

    def request_phase_change(self, target_direction: str, reason: str, force: bool = False,
                             protect_full_phase: bool = False, action: str = "CHANGE") -> bool:
        target = phase_for(target_direction)
        # Even forced/manual requests cannot cancel, shorten or restart yellow.
        if self._state.color == PhaseColor.YELLOW or target == self._state.active_direction:
            return False
        if self._clock is not None:
            self.tick(0.0)  # account for time since the last control tick before yellow starts
        old = self._state
        self._state = SignalState(
            PhaseColor.YELLOW, old.active_direction, target, 0.0, old.mode,
            old.previous_phase, old.full_phase_required, protect_full_phase,
            float(self._timings.yellow_s), old.elapsed_s, action, reason)
        self._record_transition(old, reason)
        return True

    def cancel_pending_emergency(self):
        if self._state.color == PhaseColor.YELLOW and self._state.transition_action == "EMERGENCY":
            # Complete yellow before restoring the original green; do not grant a
            # delayed ambulance green when its flashing-light evidence has ended.
            self._state = replace(self._state, target_direction=self._state.active_direction,
                                  pending_full_phase_required=False, transition_action="CANCELLED",
                                  transition_reason="Ambulance flashing-light priority withdrawn")

    def set_mode(self, mode: SignalMode):
        self._state = replace(self._state, mode=mode)
