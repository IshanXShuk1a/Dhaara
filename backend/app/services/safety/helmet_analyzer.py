"""
HelmetAnalyzer

An independent safety-analytics module: aggregates per-motorcycle helmet
detections into compliance counts and violation events. Deliberately has no
reference to SignalFSM, TrafficDecisionEngine, or any other traffic-control
component - per project rules, a helmet violation must never alter signal
timing unless a separate, explicit policy is later designed for that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.domain_config import DetectionConfig, DEFAULT_CONFIG


class HelmetState(str, Enum):
    HELMET = "HELMET"
    NO_HELMET = "NO_HELMET"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HelmetObservation:
    track_id: int
    confidence: float
    state: HelmetState
    lane_id: str
    timestamp: float


@dataclass(frozen=True)
class SafetyEvent:
    event_type: str  # "NO_HELMET"
    track_id: int
    lane_id: str
    confidence: float
    timestamp: float


@dataclass
class HelmetAnalyzer:
    config: DetectionConfig = field(default_factory=lambda: DEFAULT_CONFIG.detection)
    _reported_violations: set[int] = field(default_factory=set)
    compliant_count: int = 0
    violation_count: int = 0
    events: list[SafetyEvent] = field(default_factory=list)

    def classify(self, raw_confidence_helmet: float, raw_confidence_no_helmet: float) -> HelmetState:
        """Pick whichever class exceeds the configured confidence threshold; if
        neither does, report UNKNOWN rather than guessing."""
        if raw_confidence_no_helmet >= self.config.helmet_confidence and raw_confidence_no_helmet >= raw_confidence_helmet:
            return HelmetState.NO_HELMET
        if raw_confidence_helmet >= self.config.helmet_confidence:
            return HelmetState.HELMET
        return HelmetState.UNKNOWN

    def observe(self, observation: HelmetObservation) -> SafetyEvent | None:
        if observation.state == HelmetState.HELMET:
            self.compliant_count += 1
            return None
        if observation.state == HelmetState.NO_HELMET:
            # Count each track's violation once (avoid inflating counts by
            # re-counting the same motorcycle every frame it's visible).
            if observation.track_id in self._reported_violations:
                return None
            self._reported_violations.add(observation.track_id)
            self.violation_count += 1
            event = SafetyEvent(
                event_type="NO_HELMET",
                track_id=observation.track_id,
                lane_id=observation.lane_id,
                confidence=observation.confidence,
                timestamp=observation.timestamp,
            )
            self.events.append(event)
            return event
        return None  # UNKNOWN - not counted either way

    @property
    def compliance_rate(self) -> float | None:
        total = self.compliant_count + self.violation_count
        if total == 0:
            return None  # no data yet - dashboard must show N/A, not 0% or a fabricated number
        return round(self.compliant_count / total, 3)
