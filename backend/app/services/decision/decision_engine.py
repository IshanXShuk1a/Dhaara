"""
TrafficDecisionEngine

Selects which direction should receive the next GREEN phase and for how
long, from real LaneMetrics (see services/lanes/lane_intelligence.py) plus
fairness state. Produces a `SignalDecision` with a human-readable, itemized
`reason` list built from the actual numbers that drove the choice - the
frontend must display this verbatim rather than inventing its own
explanation (see PROJECT rules: "Do not generate explanations independently
in the frontend").

Emergency state is an input, not computed here: if `emergency_direction` is
set, the engine returns that direction unconditionally (fairness does not
apply to emergency priority), with the reason clearly marked EMERGENCY.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.domain_config import DomainConfig, SignalTimings, DEFAULT_CONFIG
from app.services.decision.fairness import FairnessTracker
from app.services.lanes.lane_intelligence import LaneMetrics, LaneStatus


@dataclass(frozen=True)
class SignalDecision:
    selected_direction: str
    green_duration_s: int
    reason: list[str]
    mode: str  # "ADAPTIVE" | "EMERGENCY" | "FIXED"
    traffic_pressure: float
    queue_length_m: float
    waiting_time_s: float
    vehicle_count: int
    fairness_applied: bool


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class TrafficDecisionEngine:
    def __init__(self, fairness: FairnessTracker, config: DomainConfig = DEFAULT_CONFIG):
        self._fairness = fairness
        self._timings: SignalTimings = config.signal_timings

    def decide(
        self,
        lane_metrics_by_direction: dict[str, LaneMetrics],
        current_direction: str,
        emergency_direction: str | None = None,
    ) -> SignalDecision:
        if not lane_metrics_by_direction:
            raise ValueError("No lane metrics supplied to decision engine")

        if emergency_direction is not None:
            metrics = lane_metrics_by_direction.get(emergency_direction)
            green = self._timings.maximum_green_s if metrics is None else self._green_duration(metrics)
            decision = SignalDecision(
                selected_direction=emergency_direction,
                green_duration_s=green,
                reason=[f"EMERGENCY: priority requested for {emergency_direction}"],
                mode="EMERGENCY",
                traffic_pressure=metrics.traffic_pressure if metrics else 0.0,
                queue_length_m=metrics.queue_length_m if metrics else 0.0,
                waiting_time_s=metrics.average_waiting_time_s if metrics else 0.0,
                vehicle_count=metrics.vehicle_count if metrics else 0,
                fairness_applied=False,
            )
            # Emergency selection does not count against fairness.
            return decision

        # Rank candidates by traffic pressure, descending, filtering out
        # directions that have exhausted their fairness allowance (unless
        # every candidate has, in which case fairness cannot starve the
        # intersection entirely and the pressure ranking is used as-is).
        ranked = sorted(
            lane_metrics_by_direction.items(), key=lambda kv: kv[1].traffic_pressure, reverse=True
        )
        eligible = [(d, m) for d, m in ranked if self._fairness.is_eligible(d)]
        fairness_applied = len(eligible) < len(ranked)
        candidates = eligible if eligible else ranked

        selected_direction, metrics = candidates[0]
        green = self._green_duration(metrics)
        reason = self._build_reason(selected_direction, metrics, ranked, fairness_applied)

        self._fairness.record_selection(selected_direction)

        return SignalDecision(
            selected_direction=selected_direction,
            green_duration_s=green,
            reason=reason,
            mode="ADAPTIVE",
            traffic_pressure=metrics.traffic_pressure,
            queue_length_m=metrics.queue_length_m,
            waiting_time_s=metrics.average_waiting_time_s,
            vehicle_count=metrics.vehicle_count,
            fairness_applied=fairness_applied,
        )

    def _green_duration(self, metrics: LaneMetrics) -> int:
        """green = clamp(base_green + pressure_factor, minimum_green, maximum_green)."""
        pressure_factor = (metrics.traffic_pressure / 100.0) * (
            self._timings.maximum_green_s - self._timings.base_green_s
        )
        duration = self._timings.base_green_s + pressure_factor
        return int(round(_clamp(duration, self._timings.minimum_green_s, self._timings.maximum_green_s)))

    @staticmethod
    def _build_reason(
        selected: str,
        metrics: LaneMetrics,
        ranked: list[tuple[str, LaneMetrics]],
        fairness_applied: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if len(ranked) > 1 and ranked[0][0] == selected:
            reasons.append(f"Highest traffic pressure ({metrics.traffic_pressure:.0f})")
        elif fairness_applied:
            reasons.append(
                f"Highest-pressure direction is at its fairness limit; "
                f"selected next highest ({metrics.traffic_pressure:.0f})"
            )
        if metrics.queue_length_m > 0:
            reasons.append(f"Queue length {metrics.queue_length_m:.0f}m")
        if metrics.average_waiting_time_s > 0:
            reasons.append(f"Average waiting time {metrics.average_waiting_time_s:.0f}s")
        reasons.append(f"{metrics.vehicle_count} vehicles, status {metrics.status.value}")
        if fairness_applied:
            reasons.append("Fairness limit applied to at least one higher-pressure direction")
        return reasons
