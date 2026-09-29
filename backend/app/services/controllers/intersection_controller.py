"""
IntersectionController

One instance per physical intersection. Owns everything that must NOT be
shared globally across intersections: its own tracker, lane geometry,
traffic state, signal FSM, decision engine (with its own fairness tracker),
emergency manager, and helmet analyzer. Running N intersections means
creating N of these - there is no single global traffic-state object that
would make multi-intersection support impossible.

Each call to `process_frame` runs exactly one step of the full causal chain:

    detections -> tracks -> lane assignments -> lane metrics
        -> emergency state update -> decision -> signal FSM tick

and returns an `IntersectionSnapshot` capturing every intermediate value, so
the API/WebSocket layer (and, in this repo, the integration test) can expose
the complete trace rather than only the final numbers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.domain_config import DomainConfig, DEFAULT_CONFIG
from app.services.cv.detector import Detector
from app.services.cv.tracker import CentroidIoUTracker, Track
from app.services.cv.lane_assigner import LaneAssigner, LanePolygon, LaneAssignment
from app.services.lanes.lane_intelligence import (
    LaneIntelligenceEngine,
    LaneGeometry,
    LaneMetrics,
    TrackedVehicleSnapshot,
)
from app.services.decision.fairness import FairnessTracker
from app.services.decision.decision_engine import TrafficDecisionEngine, SignalDecision
from app.services.signals.signal_fsm import SignalFSM, SignalMode
from app.services.emergency.ambulance_confirmation import AmbulanceConfirmationTracker
from app.services.emergency.ambulance_analyzer import AmbulanceAnalyzer, IntersectionCenter
from app.services.emergency.emergency_manager import EmergencyManager, EmergencyState
from app.services.safety.helmet_analyzer import HelmetAnalyzer, HelmetObservation, HelmetState
from app.services.cv.helmet_detector import HelmetDetector
from app.services.event_bus import event_bus, Event, EventType


@dataclass
class IntersectionSnapshot:
    frame_index: int
    timestamp: float
    lane_metrics: dict[str, LaneMetrics]
    decision: SignalDecision | None
    signal_state: str
    signal_active_direction: str
    signal_countdown_s: float
    emergency_state: str
    emergency_direction: str | None
    vehicles: list[tuple[Track, LaneAssignment]]
    is_simulated: bool
    signal_mode: str = "ADAPTIVE"
    signal_target_direction: str | None = None
    safety_summary: dict = field(default_factory=dict)
    vehicle_helmet_states: dict[int, str] = field(default_factory=dict)


class IntersectionController:
    def __init__(
        self,
        intersection_id: str,
        lanes: list[LanePolygon],
        directions: list[str],
        detector: Detector,
        config: DomainConfig = DEFAULT_CONFIG,
        fps: float = 25.0,
        lane_geometry: dict[str, LaneGeometry] | None = None,
        intersection_center: IntersectionCenter | None = None,
    ):
        self.intersection_id = intersection_id
        self._config = config
        self._detector = detector
        self._tracker = CentroidIoUTracker()
        self._lane_assigner = LaneAssigner(lanes, fps=fps)
        self._lane_engine = LaneIntelligenceEngine(config)
        self._fairness = FairnessTracker(config.fairness)
        self._decision_engine = TrafficDecisionEngine(self._fairness, config)
        self._signal_fsm = SignalFSM(directions, config)
        self._ambulance_confirmation = AmbulanceConfirmationTracker(config.detection)
        center = intersection_center or IntersectionCenter(x=320, y=240)
        self._ambulance_analyzer = AmbulanceAnalyzer(self._ambulance_confirmation, center)
        self._emergency = EmergencyManager()
        self._helmet_analyzer = HelmetAnalyzer(config.detection)
        self._helmet_detector = HelmetDetector(confidence_threshold=config.detection.helmet_confidence)
        self._lanes = lanes
        self._lane_geometry = lane_geometry or {
            l.lane_id: LaneGeometry(lane_id=l.lane_id) for l in lanes
        }
        self.decision_log: list[SignalDecision] = []
        self.last_snapshot: IntersectionSnapshot | None = None

    def update_lane_geometry(self, lanes: list[LanePolygon], center: IntersectionCenter | None = None) -> None:
        """Update lane polygons and center coordinate to match the full frame dimensions of the active video feed."""
        self._lanes = lanes
        self._lane_assigner = LaneAssigner(lanes, fps=self._lane_assigner._fps)
        self._lane_geometry = {l.lane_id: LaneGeometry(lane_id=l.lane_id) for l in lanes}
        if center is not None:
            self._ambulance_analyzer = AmbulanceAnalyzer(self._ambulance_confirmation, center)

    def process_frame(self, image, frame_index: int, dt_seconds: float = 1 / 25.0) -> IntersectionSnapshot:
        timestamp = time.time()
        frame_detections = self._detector.detect(image, frame_index)
        tracks = self._tracker.update(frame_detections.detections)
        assignments = self._lane_assigner.assign_many(tracks, frame_index)
        assignment_by_track = {a.track_id: a for a in assignments}

        lane_metrics = self._compute_lane_metrics(tracks, assignment_by_track)
        self._process_emergency(tracks, assignment_by_track, timestamp)
        self._process_helmets(image, tracks, assignment_by_track, timestamp)

        self._signal_fsm.tick(dt_seconds)
        if self._signal_fsm.advance_if_ready():
            event_bus.publish(Event(
                type=EventType.SIGNAL_CHANGED,
                intersection_id=self.intersection_id,
                message=f"Signal transitioned to {self._signal_fsm.state.color.value} ({self._signal_fsm.state.active_direction})",
                severity="INFO",
                metadata={
                    "color": self._signal_fsm.state.color.value,
                    "active_direction": self._signal_fsm.state.active_direction,
                    "target_direction": self._signal_fsm.state.target_direction,
                    "mode": self._signal_fsm.state.mode.value,
                }
            ))

        decision = None
        if self._emergency.emergency_direction and self._signal_fsm.state.color.value == "GREEN":
            # Emergency forces immediate safe phase change
            decision = self._decide_and_apply(lane_metrics, force=True)
        elif self._signal_fsm.state.mode == SignalMode.MANUAL:
            # Manual mode: operator override holds current phase; automated transitions paused
            pass
        elif self._signal_fsm.state.mode == SignalMode.FIXED:
            # Fixed mode: cycle through directions with configured fixed_phase_s duration
            if self._signal_fsm.state.color.value == "GREEN" and self._signal_fsm.state.elapsed_s >= self._config.signal_timings.fixed_phase_s:
                dirs = self._signal_fsm.directions
                curr_dir = self._signal_fsm.state.active_direction
                curr_idx = dirs.index(curr_dir) if curr_dir in dirs else 0
                next_dir = dirs[(curr_idx + 1) % len(dirs)]
                m = lane_metrics.get(next_dir)
                decision = SignalDecision(
                    selected_direction=next_dir,
                    green_duration_s=self._config.signal_timings.fixed_phase_s,
                    reason=[f"Fixed cycle sequence: advancing to {next_dir} ({self._config.signal_timings.fixed_phase_s}s phase)"],
                    mode="FIXED",
                    traffic_pressure=m.traffic_pressure if m else 0.0,
                    queue_length_m=m.queue_length_m if m else 0.0,
                    waiting_time_s=m.average_waiting_time_s if m else 0.0,
                    vehicle_count=m.vehicle_count if m else 0,
                    fairness_applied=False,
                )
                try:
                    self._signal_fsm.request_phase_change(next_dir, reason=f"Fixed-phase timer elapsed ({self._config.signal_timings.fixed_phase_s}s)")
                except Exception:
                    pass
                self.decision_log.append(decision)
        elif self._signal_fsm.state.mode == SignalMode.ADAPTIVE:
            if self._signal_fsm.state.color.value == "GREEN" and self._signal_fsm.can_end_green_early():
                decision = self._decide_and_apply(lane_metrics)

        if self._emergency.state == EmergencyState.PRIORITY_REQUESTED:
            if self._signal_fsm.state.active_direction == self._emergency.active_direction and \
               self._signal_fsm.state.color.value == "GREEN":
                self._emergency.mark_priority_active(timestamp)

        remaining = max(
            0.0,
            (decision.green_duration_s if decision else self._config.signal_timings.base_green_s)
            - self._signal_fsm.state.elapsed_s,
        )

        self.last_snapshot = IntersectionSnapshot(
            frame_index=frame_index,
            timestamp=timestamp,
            lane_metrics=lane_metrics,
            decision=decision,
            signal_state=self._signal_fsm.state.color.value,
            signal_active_direction=self._signal_fsm.state.active_direction,
            signal_countdown_s=round(remaining, 1),
            emergency_state=self._emergency.state.value,
            emergency_direction=self._emergency.emergency_direction,
            vehicles=[(t, assignment_by_track[t.track_id]) for t in tracks if t.track_id in assignment_by_track],
            is_simulated=frame_detections.is_simulated,
            signal_mode=self._signal_fsm.state.mode.value,
            signal_target_direction=self._signal_fsm.state.target_direction,
            safety_summary={
                "compliant_count": self._helmet_analyzer.compliant_count,
                "violation_count": self._helmet_analyzer.violation_count,
                "compliance_rate": self._helmet_analyzer.compliance_rate,
            },
            vehicle_helmet_states=dict(self._track_helmet_states),
        )
        return self.last_snapshot

    def _compute_lane_metrics(self, tracks, assignment_by_track) -> dict[str, LaneMetrics]:
        by_lane: dict[str, list[TrackedVehicleSnapshot]] = {lid: [] for lid in self._lane_geometry}
        for track in tracks:
            assignment = assignment_by_track.get(track.track_id)
            if assignment is None or assignment.lane_id not in by_lane:
                continue
            by_lane[assignment.lane_id].append(
                TrackedVehicleSnapshot(
                    track_id=track.track_id,
                    speed_kmph=assignment.speed_kmph,
                    waiting_time_s=assignment.waiting_time_s,
                    is_stopped=assignment.is_stopped,
                )
            )
        return {
            lane_id: self._lane_engine.compute(self._lane_geometry[lane_id], vehicles)
            for lane_id, vehicles in by_lane.items()
        }

    def _process_emergency(self, tracks, assignment_by_track, timestamp: float) -> None:
        seen_confirmed_track = False
        for track in tracks:
            assignment = assignment_by_track.get(track.track_id)
            if assignment is None:
                continue
            candidate = self._ambulance_analyzer.process(track, assignment, timestamp)
            if candidate is None:
                continue
            self._emergency.on_candidate_detected(candidate, timestamp)
            if candidate.state.value == "CONFIRMED":
                was_unconfirmed = self._emergency.state != EmergencyState.CONFIRMED
                self._emergency.on_candidate_confirmed(candidate, timestamp)
                if self._emergency.active_track_id == track.track_id:
                    seen_confirmed_track = True
                if was_unconfirmed:
                    event_bus.publish(Event(
                        type=EventType.AMBULANCE_DETECTED,
                        intersection_id=self.intersection_id,
                        message=f"Ambulance confirmed in {self._emergency.active_direction or assignment.lane_id}",
                        severity="WARNING",
                        metadata={"track_id": track.track_id, "lane": assignment.lane_id}
                    ))

            if self._emergency.state == EmergencyState.CONFIRMED:
                self._emergency.request_priority(timestamp)
                event_bus.publish(Event(
                    type=EventType.EMERGENCY_PRIORITY_REQUESTED,
                    intersection_id=self.intersection_id,
                    message=f"Emergency signal priority requested for {self._emergency.active_direction}",
                    severity="CRITICAL",
                    metadata={"direction": self._emergency.active_direction}
                ))

        if self._emergency.state == EmergencyState.PRIORITY_ACTIVE:
            self._emergency.observe_tick(still_present=seen_confirmed_track, timestamp=timestamp)
        if self._emergency.state == EmergencyState.PASSED:
            self._emergency.resolve(timestamp)
            event_bus.publish(Event(
                type=EventType.EMERGENCY_RESOLVED,
                intersection_id=self.intersection_id,
                message="Ambulance cleared intersection - resuming normal signal operation",
                severity="INFO"
            ))

    def _process_helmets(self, image, tracks, assignment_by_track, timestamp: float) -> None:
        for track in tracks:
            if track.class_name != "motorcycle":
                continue
            assignment = assignment_by_track.get(track.track_id)
            if assignment is None:
                continue
            state, conf = self._helmet_detector.evaluate(image, track.bbox)
            if state != HelmetState.UNKNOWN:
                self._track_helmet_states[track.track_id] = state.value
                ev = self.report_helmet_observation(track.track_id, assignment.lane_id, state, conf, timestamp)
                if ev is not None:
                    event_bus.publish(Event(
                        type=EventType.HELMET_VIOLATION,
                        intersection_id=self.intersection_id,
                        message=f"Helmet violation: motorcycle #{track.track_id} in {assignment.lane_id} ({int(conf * 100)}% conf)",
                        severity="WARNING",
                        metadata={"track_id": track.track_id, "lane_id": assignment.lane_id, "confidence": conf}
                    ))

    def report_helmet_observation(self, track_id: int, lane_id: str, state: HelmetState, confidence: float, timestamp: float):
        self._track_helmet_states[track_id] = state.value
        return self._helmet_analyzer.observe(
            HelmetObservation(track_id=track_id, confidence=confidence, state=state, lane_id=lane_id, timestamp=timestamp)
        )

    def _decide_and_apply(self, lane_metrics: dict[str, LaneMetrics], force: bool = False) -> SignalDecision | None:
        try:
            decision = self._decision_engine.decide(
                lane_metrics,
                current_direction=self._signal_fsm.state.active_direction,
                emergency_direction=self._emergency.emergency_direction,
            )
        except ValueError:
            return None
        try:
            self._signal_fsm.request_phase_change(decision.selected_direction, reason="; ".join(decision.reason), force=force or decision.mode == "EMERGENCY")
        except Exception:
            pass
        self.decision_log.append(decision)
        return decision

    @property
    def helmet_analyzer(self) -> HelmetAnalyzer:
        return self._helmet_analyzer

    @property
    def signal_fsm(self) -> SignalFSM:
        return self._signal_fsm

    @property
    def emergency_manager(self) -> EmergencyManager:
        return self._emergency

    def set_mode(self, mode: SignalMode) -> None:
        self._signal_fsm.set_mode(mode)
