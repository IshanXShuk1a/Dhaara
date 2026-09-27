"""
FairnessTracker

Prevents a single direction from receiving adaptive-priority GREEN more than
`consecutive_priority_limit` times in a row, regardless of how high its
traffic pressure is. Emergency priority is allowed to supersede fairness
(it is a distinct control path, not routed through `is_eligible`).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.domain_config import FairnessConfig, DEFAULT_CONFIG


@dataclass
class FairnessState:
    last_selected_direction: str | None = None
    consecutive_count: int = 0


class FairnessTracker:
    def __init__(self, config: FairnessConfig = DEFAULT_CONFIG.fairness):
        self._limit = config.consecutive_priority_limit
        self._state = FairnessState()

    @property
    def state(self) -> FairnessState:
        return self._state

    def is_eligible(self, direction: str) -> bool:
        """False only when `direction` has already won the configured
        consecutive-priority limit in a row and would extend the streak."""
        if direction != self._state.last_selected_direction:
            return True
        return self._state.consecutive_count < self._limit

    def record_selection(self, direction: str) -> None:
        if direction == self._state.last_selected_direction:
            self._state.consecutive_count += 1
        else:
            self._state.last_selected_direction = direction
            self._state.consecutive_count = 1

    def reset(self) -> None:
        self._state = FairnessState()
