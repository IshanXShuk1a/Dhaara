"""Weighted pair demand with timed alternation and persistent empty-phase release."""
from __future__ import annotations
from dataclasses import dataclass, field
from app.core.domain_config import DomainConfig, DEFAULT_CONFIG
from app.services.lanes.lane_intelligence import LaneMetrics
from app.services.signals.signal_fsm import PHASE_DIRECTIONS, phase_for, opposite_phase

@dataclass(frozen=True)
class SignalDecision:
    selected_direction: str
    green_duration_s: int
    reason: list[str]
    mode: str
    traffic_pressure: float = 0.0
    queue_length_m: float = 0.0
    waiting_time_s: float = 0.0
    vehicle_count: int = 0
    fairness_applied: bool = False
    pair_scores: dict[str, float | None] = field(default_factory=dict)
    denser_pair: str | None = None
    score_difference: float | None = None
    action: str = "HOLD"
    empty_elapsed_s: float = 0.0

class TrafficDecisionEngine:
    def __init__(self, config: DomainConfig = DEFAULT_CONFIG):
        self._timings = config.signal_timings
        self._low_since: float | None = None
        self._observed_phase: str | None = None
        self._last_elapsed = 0.0
        self._initial_evaluated = False

    def decide(self, lane_metrics_by_direction: dict[str, LaneMetrics], current_direction: str,
               emergency_direction: str | None = None, *, elapsed_s: float = 0.0,
               data_complete: bool = True, full_phase_required: bool = False,
               adaptive: bool = True, emergency_lights_active: bool = False,
               transition_target: str | None = None) -> SignalDecision:
        if not lane_metrics_by_direction:
            raise ValueError("No lane metrics supplied to decision engine")
        current = phase_for(current_direction)
        other = opposite_phase(current)
        complete = data_complete and all(d in lane_metrics_by_direction for ds in PHASE_DIRECTIONS.values() for d in ds)
        scores = {pair: round(sum(lane_metrics_by_direction[d].vehicle_score for d in ds) / 2, 2)
                  if complete else None for pair, ds in PHASE_DIRECTIONS.items()}
        difference = abs(scores["EW"] - scores["NS"]) if complete else None
        denser = ("EW" if scores["EW"] > scores["NS"] else "NS" if scores["NS"] > scores["EW"] else "BALANCED") if complete else None
        if transition_target is not None:
            target = phase_for(transition_target)
            self._low_since, self._observed_phase = None, None
            count = sum(lane_metrics_by_direction[d].vehicle_count for d in PHASE_DIRECTIONS[target] if d in lane_metrics_by_direction)
            return SignalDecision(target, self._timings.fixed_phase_s,
                                  [f"{current} YELLOW; {target} GREEN only after yellow completes"],
                                  "ADAPTIVE" if adaptive else "FIXED", vehicle_count=count, pair_scores=scores,
                                  denser_pair=denser, score_difference=difference, action="YELLOW")
        if current != self._observed_phase or elapsed_s < self._last_elapsed:
            self._low_since = None
        self._observed_phase, self._last_elapsed = current, elapsed_s
        low = complete and scores[current] <= self._timings.empty_score_max
        if not low:
            self._low_since = None
        elif self._low_since is None:
            self._low_since = elapsed_s
        low_duration = max(0.0, elapsed_s - self._low_since) if self._low_since is not None else 0.0
        initial_selection = adaptive and complete and not self._initial_evaluated and elapsed_s <= 1.0
        if complete:
            self._initial_evaluated = True
        selected, action = current, "HOLD"
        reasons = [f"{current} keeps its {self._timings.fixed_phase_s}-second phase"]
        if emergency_direction and emergency_lights_active:
            selected, action = phase_for(emergency_direction), "EMERGENCY"
            reasons = [f"Ambulance and flashing emergency lights confirmed in {emergency_direction}"]
        elif initial_selection and scores[other] - scores[current] >= self._timings.score_difference_threshold:
            selected, action = other, "INITIAL"
            reasons = [f"Initial demand: {other} leads by {scores[other] - scores[current]:g} points"]
        elif elapsed_s >= self._timings.fixed_phase_s:
            selected, action = other, "TIMER"
            reasons = [f"{self._timings.fixed_phase_s}-second timer elapsed; alternate to {other}"]
        elif (adaptive and not full_phase_required and complete and low
              and low_duration >= self._timings.empty_persistence_s
              and self._timings.fixed_phase_s - elapsed_s > self._timings.early_switch_min_remaining_s
              and scores[other] - scores[current] >= self._timings.score_difference_threshold):
            selected, action = other, "EARLY"
            reasons = [f"{current} score {scores[current]:g} stayed <= {self._timings.empty_score_max:g} for {low_duration:.1f}s",
                       f"{other} leads by {scores[other] - scores[current]:g} points; more than {self._timings.early_switch_min_remaining_s:g}s remain",
                       f"{other} receives a full {self._timings.fixed_phase_s}-second phase"]
        elif not complete:
            reasons.append("Camera data incomplete; demand switching disabled")
        elif full_phase_required:
            reasons.append("Completing the full phase granted after early switching")
        elif denser != "BALANCED":
            reasons.append(f"{denser} is denser; timed alternation prevents repeated grants")
        count = sum(lane_metrics_by_direction[d].vehicle_count for d in PHASE_DIRECTIONS[selected] if d in lane_metrics_by_direction)
        return SignalDecision(selected, self._timings.fixed_phase_s, reasons, "ADAPTIVE" if adaptive else "FIXED",
                              vehicle_count=count, pair_scores=scores, denser_pair=denser,
                              score_difference=round(difference, 2) if difference is not None else None,
                              action=action, empty_elapsed_s=round(low_duration, 1))
