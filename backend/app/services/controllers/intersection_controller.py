"""Existing intersection pipeline with independent camera tracking and ROI counts."""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Callable

from app.core.domain_config import DomainConfig, DEFAULT_CONFIG
from app.services.cv.detector import Detector
from app.services.cv.tracker import CentroidIoUTracker, Track
from app.services.cv.lane_assigner import LaneAssigner, LanePolygon, LaneAssignment, camera_lane, DEFAULT_ROI
from app.services.lanes.lane_intelligence import (
    LaneIntelligenceEngine,
    LaneGeometry,
    LaneMetrics,
    TrackedVehicleSnapshot,
)
from app.services.decision.decision_engine import TrafficDecisionEngine, SignalDecision
from app.services.signals.signal_fsm import SignalFSM, SignalMode, PhaseColor, phase_for
from app.services.emergency.ambulance_confirmation import AmbulanceConfirmationTracker
from app.services.emergency.ambulance_analyzer import AmbulanceAnalyzer, IntersectionCenter
from app.services.emergency.emergency_manager import EmergencyManager, EmergencyState
from app.services.safety.helmet_analyzer import HelmetAnalyzer, HelmetObservation, HelmetState
from app.services.cv.helmet_detector import HelmetDetector
from app.services.cv.emergency_lights import EmergencyLightTracker
from app.services.decision.vehicle_scoring import score_classes
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
    direction_signals: dict[str, str] = field(default_factory=dict)
    camera_statuses: dict[str, dict] = field(default_factory=dict)
    camera_vehicles: dict[str, list] = field(default_factory=dict)
    camera_lanes: dict[str, LanePolygon] = field(default_factory=dict)
    demand: dict = field(default_factory=dict)
    score_records: list[dict] = field(default_factory=list)
    ambulance_lights: dict[int, bool] = field(default_factory=dict)


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
        signal_clock: Callable[[], float] | None = None,
    ):
        self.intersection_id = intersection_id
        self._config = config
        self._detector = detector
        self._tracker = CentroidIoUTracker()
        self._lane_assigner = LaneAssigner(lanes, fps=fps)
        self._directions = list(directions)
        self._trackers = {d: CentroidIoUTracker(id_start=i + 1, id_step=len(directions))
                          for i, d in enumerate(directions)}
        self._camera_assigners = {}
        self._camera_rois = {d: DEFAULT_ROI for d in directions}
        self._camera_calibration = {}
        self._camera_ambulance_analyzers = {}
        self._track_helmet_states = {}
        self._lane_engine = LaneIntelligenceEngine(config)
        self._decision_engine = TrafficDecisionEngine(config)
        self._signal_fsm = SignalFSM(directions, config, clock=signal_clock)
        self._ambulance_confirmation = AmbulanceConfirmationTracker(config.detection)
        center = intersection_center or IntersectionCenter(x=320, y=240)
        self._ambulance_analyzer = AmbulanceAnalyzer(self._ambulance_confirmation, center)
        self._emergency = EmergencyManager()
        self._emergency_lights = EmergencyLightTracker()
        self._ambulance_lights = {}
        self._score_records = []
        self._record_elapsed = 0.0
        self._helmet_analyzer = HelmetAnalyzer(config.detection)
        self._helmet_detector = HelmetDetector(confidence_threshold=config.detection.helmet_confidence)
        self._lanes = lanes
        self._lane_geometry = lane_geometry or {
            l.lane_id: LaneGeometry(lane_id=l.lane_id) for l in lanes
        }
        self.decision_log: list[SignalDecision] = []
        self.last_snapshot: IntersectionSnapshot | None = None

    def configure_camera_roi(self, direction, roi, geometry=None, pixels_per_meter=8.0):
        from app.services.cv.lane_assigner import validate_normalized_roi
        self._camera_rois[direction] = validate_normalized_roi(roi)
        self._camera_calibration[direction] = pixels_per_meter
        self._camera_assigners.pop(direction, None)
        if geometry:
            self._lane_geometry[direction] = geometry

    def reset_camera(self, direction):
        self._trackers[direction].reset(preserve_ids=True)
        self._camera_assigners.pop(direction, None)
        for tid in list(self._track_helmet_states):
            if (tid - 1) % len(self._directions) == self._directions.index(direction):
                self._track_helmet_states.pop(tid, None)

    def process_frame(self, image, frame_index: int, dt_seconds: float = 1 / 25.0):
        """Offline detector/test adapter. Live camera ingestion uses process_frames."""
        timestamp = time.time()
        detections = self._detector.detect(image, frame_index)
        tracks = self._tracker.update(detections.detections)
        assignments = self._lane_assigner.assign_many(tracks, frame_index)
        by_track = {a.track_id: a for a in assignments}
        metrics = self._compute_lane_metrics(tracks, by_track)
        self._process_emergency(tracks, by_track, timestamp, {d: image for d in self._directions})
        self._process_helmets(image, tracks, by_track, timestamp)
        self.last_snapshot = self._finish_snapshot(metrics, tracks, by_track, frame_index, timestamp,
                                                  dt_seconds, detections.is_simulated)
        return self.last_snapshot

    def process_frames(self, images: dict, frame_index: int, dt_seconds: float = .2, camera_statuses=None):
        timestamp = time.time()
        detections = self._detector.detect_many(images, frame_index)
        all_tracks, by_track, emergency_assignments, camera_vehicles, camera_lanes = [], {}, {}, {}, {}
        for direction in self._directions:
            image = images.get(direction)
            result = detections.get(direction)
            tracks = self._trackers[direction].update(result.detections if result else [])
            if image is None:
                camera_vehicles[direction] = []
                continue
            h, w = image.shape[:2]
            lane = camera_lane(direction, w, h, self._camera_rois[direction],
                               self._camera_calibration.get(direction, 8.0))
            camera_lanes[direction] = lane
            near_right, near_left = lane.polygon[2], lane.polygon[3]
            self._camera_ambulance_analyzers[direction] = AmbulanceAnalyzer(
                self._ambulance_confirmation,
                IntersectionCenter((near_right[0] + near_left[0]) / 2, (near_right[1] + near_left[1]) / 2))
            previous = self._camera_assigners.get(direction)
            if previous is None or previous._lanes != [lane]:
                previous = self._camera_assigners[direction] = LaneAssigner([lane], fps=1 / max(dt_seconds, .001))
            else:
                previous._fps = 1 / max(dt_seconds, .001)
            assignments = {a.track_id: a for a in previous.assign_many(tracks, frame_index)}
            self._process_helmets(image, tracks, assignments, timestamp)
            camera_vehicles[direction] = [(t, assignments[t.track_id]) for t in tracks]
            all_tracks.extend(tracks)
            by_track.update(assignments)
            emergency_assignments.update({t.track_id: replace(assignments[t.track_id], lane_id=direction, direction=direction)
                                          for t in tracks if t.class_name == "ambulance"})
        self._process_emergency(all_tracks, emergency_assignments, timestamp, images)
        metrics = self._compute_lane_metrics(all_tracks, by_track)
        snap = self._finish_snapshot(metrics, all_tracks, by_track, frame_index, timestamp,
                                     dt_seconds, any(r.is_simulated for r in detections.values()),
                                     data_complete=all(d in images and d in detections for d in self._directions))
        snap.camera_vehicles = camera_vehicles
        snap.camera_lanes = camera_lanes
        snap.camera_statuses = camera_statuses or {}
        self.last_snapshot = snap
        return snap

    def _finish_snapshot(self, lane_metrics, tracks, by_track, frame_index, timestamp, dt_seconds, simulated,
                         data_complete=True):
        before_tick = self._signal_fsm.state
        emergency_direction = self._emergency.emergency_direction
        emergency_active = (self._ambulance_lights.get(self._emergency.active_track_id, False)
                            and self._emergency.state in (EmergencyState.PRIORITY_REQUESTED, EmergencyState.PRIORITY_ACTIVE))
        if (before_tick.color == PhaseColor.YELLOW and before_tick.transition_action == "EMERGENCY"
                and (not emergency_active or phase_for(emergency_direction) != before_tick.target_direction)):
            self._signal_fsm.cancel_pending_emergency()
        completed_action = self._signal_fsm.state.transition_action
        completed_reason = self._signal_fsm.state.transition_reason
        completed_yellow = self._signal_fsm.tick(dt_seconds)
        old = self._signal_fsm.state
        decision = self._decision_engine.decide(
            lane_metrics, old.active_direction, emergency_direction=emergency_direction,
            elapsed_s=old.elapsed_s, data_complete=data_complete,
            full_phase_required=old.full_phase_required, adaptive=old.mode == SignalMode.ADAPTIVE,
            emergency_lights_active=emergency_active,
            transition_target=old.target_direction if old.color == PhaseColor.YELLOW else None)
        decision = replace(decision, mode=old.mode.value)
        if completed_yellow:
            decision = replace(decision, selected_direction=old.active_direction,
                               action=completed_action or "HOLD",
                               reason=[f"{old.active_direction} GREEN after yellow: {completed_reason}"])
        elif old.mode == SignalMode.MANUAL and not emergency_active and old.color == PhaseColor.GREEN:
            decision = replace(decision, selected_direction=old.active_direction, action="HOLD",
                               reason=[f"Operator holds {old.active_direction}"])
        if not completed_yellow and old.color == PhaseColor.GREEN:
            self._signal_fsm.request_phase_change(decision.selected_direction, "; ".join(decision.reason),
                                                  protect_full_phase=decision.action == "EARLY", action=decision.action)
        self.decision_log.append(decision)
        self.decision_log = self.decision_log[-1000:]
        state = self._signal_fsm.state
        if emergency_active and state.color == PhaseColor.GREEN and state.active_direction == phase_for(emergency_direction):
            self._emergency.mark_priority_active(timestamp)
        previous = self.last_snapshot
        current_key = (state.color.value, state.active_direction, state.target_direction)
        previous_key = ((previous.signal_state, previous.signal_active_direction, previous.signal_target_direction)
                        if previous else (before_tick.color.value, before_tick.active_direction, before_tick.target_direction))
        changed = current_key != previous_key
        if changed:
            event_bus.publish(Event(type=EventType.SIGNAL_CHANGED, intersection_id=self.intersection_id,
                                    message=f"{state.active_direction} {state.color.value}; " + (f"next {state.target_direction}" if state.target_direction else "opposite pair RED"),
                                    metadata={"phase": state.active_direction, "previous_phase": state.previous_phase,
                                              "reason": decision.reason, "action": decision.action,
                                              "directions": self._signal_fsm.direction_states}))
        demand = {"pair_scores": decision.pair_scores, "denser_pair": decision.denser_pair,
                  "score_difference": decision.score_difference,
                  "difference_threshold": self._config.signal_timings.score_difference_threshold,
                  "empty_score_max": self._config.signal_timings.empty_score_max,
                  "empty_persistence_s": self._config.signal_timings.empty_persistence_s,
                  "empty_elapsed_s": decision.empty_elapsed_s,
                  "early_switch_min_remaining_s": self._config.signal_timings.early_switch_min_remaining_s,
                  "phase_duration_s": self._config.signal_timings.fixed_phase_s,
                  "yellow_duration_s": state.yellow_duration_s if state.color == PhaseColor.YELLOW else self._config.signal_timings.yellow_s,
                  "previous_phase": state.previous_phase, "full_phase_required": state.full_phase_required,
                  "data_complete": data_complete, "action": decision.action,
                  "rickshaw_supported": getattr(self._detector, "rickshaw_supported", None)}
        self._record_elapsed += dt_seconds
        if data_complete and (not self._score_records or changed or self._record_elapsed >= 2):
            record = {"timestamp": timestamp, "lane_scores": {d: m.vehicle_score for d, m in lane_metrics.items()},
                      "pair_scores": dict(decision.pair_scores), "denser_pair": decision.denser_pair,
                      "score_difference": decision.score_difference,
                      "green_pair": state.active_direction if state.color == PhaseColor.GREEN else None,
                      "yellow_pair": state.active_direction if state.color == PhaseColor.YELLOW else None,
                      "target_pair": state.target_direction, "signal_state": state.color.value,
                      "action": decision.action, "is_simulated": simulated}
            self._score_records.append(record)
            self._score_records = self._score_records[-60:]
            self._record_elapsed = 0.0
            event_bus.publish(Event(type=EventType.DECISION_MADE, intersection_id=self.intersection_id,
                                    message=f"EW {decision.pair_scores['EW']:g}; NS {decision.pair_scores['NS']:g}; denser {decision.denser_pair}",
                                    metadata=record))
        return IntersectionSnapshot(
            frame_index=frame_index, timestamp=timestamp, lane_metrics=lane_metrics, decision=decision,
            signal_state=state.color.value, signal_active_direction=state.active_direction,
            signal_countdown_s=round(self._signal_fsm.countdown_s, 1), emergency_state=self._emergency.state.value,
            emergency_direction=self._emergency.emergency_direction,
            vehicles=[(t, by_track[t.track_id]) for t in tracks if t.track_id in by_track],
            is_simulated=simulated, signal_mode=state.mode.value, signal_target_direction=state.target_direction,
            direction_signals=self._signal_fsm.direction_states, demand=demand,
            score_records=list(self._score_records), ambulance_lights=dict(self._ambulance_lights),
            safety_summary={"compliant_count": self._helmet_analyzer.compliant_count,
                            "violation_count": self._helmet_analyzer.violation_count,
                            "compliance_rate": self._helmet_analyzer.compliance_rate},
            vehicle_helmet_states=dict(self._track_helmet_states))

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
        classes = {lid: [] for lid in by_lane}
        for track in tracks:
            assignment = assignment_by_track.get(track.track_id)
            if assignment and assignment.lane_id in classes:
                classes[assignment.lane_id].append(track.class_name)
        metrics = {}
        for lane_id, vehicles in by_lane.items():
            score, counts = score_classes(classes[lane_id])
            metrics[lane_id] = replace(self._lane_engine.compute(self._lane_geometry[lane_id], vehicles),
                                       vehicle_score=score, vehicle_counts=counts)
        return metrics

    def _process_emergency(self, tracks, assignment_by_track, timestamp: float, images) -> None:
        visible_ids = set()
        self._ambulance_lights = {}
        for track in tracks:
            assignment = assignment_by_track.get(track.track_id)
            if (track.class_name != "ambulance" or assignment is None or assignment.direction is None
                    or assignment.direction not in images):
                continue
            visible_ids.add(track.track_id)
            lights_on = self._emergency_lights.observe(track.track_id, images[assignment.direction],
                                                       track.bbox, timestamp)
            self._ambulance_lights[track.track_id] = lights_on
            analyzer = self._camera_ambulance_analyzers.get(assignment.direction, self._ambulance_analyzer)
            candidate = analyzer.process(track, assignment, timestamp)
            if candidate is None:
                continue
            self._emergency.on_candidate_detected(candidate, timestamp)
            if candidate.state.value == "CONFIRMED" and lights_on:
                unconfirmed = self._emergency.active_track_id is None
                self._emergency.on_candidate_confirmed(candidate, timestamp)
                if unconfirmed and self._emergency.active_track_id == track.track_id:
                    event_bus.publish(Event(type=EventType.AMBULANCE_DETECTED, intersection_id=self.intersection_id,
                        message=f"Ambulance with flashing lights confirmed in {assignment.direction}",
                        severity="WARNING", metadata={"track_id": track.track_id, "direction": assignment.direction}))
                if self._emergency.state == EmergencyState.CONFIRMED:
                    self._emergency.request_priority(timestamp)
        self._emergency_lights.retain(visible_ids)
        active_present = self._ambulance_lights.get(self._emergency.active_track_id, False)
        self._emergency.observe_tick(still_present=active_present, timestamp=timestamp)
        if self._emergency.state == EmergencyState.PASSED:
            self._emergency.resolve(timestamp)
            event_bus.publish(Event(type=EventType.EMERGENCY_RESOLVED, intersection_id=self.intersection_id,
                                    message="Ambulance flashing-light priority ended"))
        if not visible_ids and self._emergency.state == EmergencyState.DETECTED:
            self._emergency.state = EmergencyState.NONE

    def _process_helmets(self, image, tracks, assignment_by_track, timestamp: float) -> None:
        for track in tracks:
            if track.class_name != "motorcycle":
                continue
            assignment = assignment_by_track.get(track.track_id)
            if assignment is None or assignment.direction is None:
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

    @property
    def signal_mode(self):
        return self._signal_fsm.state.mode

    @property
    def signal_target_direction(self):
        return self._signal_fsm.state.target_direction or self._signal_fsm.state.active_direction

    def set_signal_mode(self, mode, target_direction=None):
        self.set_mode(mode)
        if target_direction:
            self._signal_fsm.request_phase_change(target_direction, "Operator selection")
