"""
AnalyticsService

Persists periodic traffic snapshots and signal decisions to the database
(see models/traffic.py) and answers the analytics API's historical queries
by aggregating real stored rows - never by generating placeholder chart data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.traffic import TrafficSnapshot, SignalDecisionRecord
from app.models.emergency import EmergencyEventRecord
from app.models.safety import SafetyEventRecord
from app.models.signal import SignalStateRecord
from app.services.lanes.lane_intelligence import LaneMetrics


class AnalyticsService:
    def __init__(self, db: Session):
        self._db = db

    def record_snapshot(self, intersection_id: str, lane_metrics: dict[str, LaneMetrics], is_simulated: bool) -> None:
        for lane_id, metrics in lane_metrics.items():
            row = TrafficSnapshot(
                intersection_id=intersection_id,
                lane_id=lane_id,
                vehicle_count=metrics.vehicle_count,
                occupancy=metrics.occupancy,
                queue_length_m=metrics.queue_length_m,
                average_speed_kmph=metrics.average_speed_kmph,
                average_waiting_time_s=metrics.average_waiting_time_s,
                flow_rate=metrics.flow_rate,
                traffic_pressure=metrics.traffic_pressure,
                status=metrics.status.value,
                is_simulated=is_simulated,
            )
            self._db.add(row)
        self._db.commit()

    def record_decision(self, intersection_id: str, decision) -> None:
        row = SignalDecisionRecord(
            intersection_id=intersection_id,
            selected_lane=decision.selected_direction,
            reason=decision.reason,
            traffic_pressure=decision.traffic_pressure,
            queue_length_m=decision.queue_length_m,
            waiting_time_s=decision.waiting_time_s,
            vehicle_count=decision.vehicle_count,
            mode=decision.mode,
            fairness_applied=decision.fairness_applied,
            green_duration_s=decision.green_duration_s,
        )
        self._db.add(row)
        self._db.commit()

    def record_signal_transition(self, intersection_id: str, transition, mode: str = "ADAPTIVE") -> None:
        row = SignalStateRecord(
            intersection_id=intersection_id,
            from_color=transition.from_color.value if hasattr(transition.from_color, "value") else str(transition.from_color),
            to_color=transition.to_color.value if hasattr(transition.to_color, "value") else str(transition.to_color),
            active_direction=transition.active_direction or "",
            target_direction=transition.target_direction,
            elapsed_in_previous_s=transition.elapsed_in_previous_s,
            reason=transition.reason,
            mode=mode,
        )
        self._db.add(row)
        self._db.commit()

    def regional_summary(self, since: datetime | None = None) -> dict:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        total_snapshots = self._db.execute(select(func.count(TrafficSnapshot.id)).where(TrafficSnapshot.timestamp >= since)).scalar_one()
        total_decisions = self._db.execute(select(func.count(SignalDecisionRecord.id)).where(SignalDecisionRecord.created_at >= since)).scalar_one()
        total_emergencies = self._db.execute(select(func.count(EmergencyEventRecord.id)).where(EmergencyEventRecord.created_at >= since)).scalar_one()
        total_violations = self._db.execute(select(func.count(SafetyEventRecord.id)).where(SafetyEventRecord.created_at >= since)).scalar_one()
        avg_pressure = self._db.execute(select(func.avg(TrafficSnapshot.traffic_pressure)).where(TrafficSnapshot.timestamp >= since)).scalar_one()
        avg_speed = self._db.execute(select(func.avg(TrafficSnapshot.average_speed_kmph)).where(TrafficSnapshot.timestamp >= since)).scalar_one()
        return {
            "total_snapshots": total_snapshots,
            "total_decisions": total_decisions,
            "total_emergencies_24h": total_emergencies,
            "total_helmet_violations_24h": total_violations,
            "average_network_pressure": round(float(avg_pressure), 1) if avg_pressure is not None else 0.0,
            "average_network_speed_kmph": round(float(avg_speed), 1) if avg_speed is not None else 0.0,
        }

    def volume_history(self, intersection_id: str, since: datetime | None = None) -> list[dict]:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        stmt = (
            select(TrafficSnapshot.lane_id, TrafficSnapshot.timestamp, TrafficSnapshot.vehicle_count)
            .where(TrafficSnapshot.intersection_id == intersection_id, TrafficSnapshot.timestamp >= since)
            .order_by(TrafficSnapshot.timestamp)
        )
        return [
            {"lane_id": r.lane_id, "timestamp": r.timestamp.isoformat(), "vehicle_count": r.vehicle_count}
            for r in self._db.execute(stmt)
        ]

    def average_pressure_by_lane(self, intersection_id: str, since: datetime | None = None) -> dict[str, float | None]:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        stmt = (
            select(TrafficSnapshot.lane_id, func.avg(TrafficSnapshot.traffic_pressure))
            .where(TrafficSnapshot.intersection_id == intersection_id, TrafficSnapshot.timestamp >= since)
            .group_by(TrafficSnapshot.lane_id)
        )
        result = {lane_id: float(avg) if avg is not None else None for lane_id, avg in self._db.execute(stmt)}
        return result

    def signal_distribution(self, intersection_id: str, since: datetime | None = None) -> dict[str, int]:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        stmt = (
            select(SignalDecisionRecord.selected_lane, func.count())
            .where(SignalDecisionRecord.intersection_id == intersection_id, SignalDecisionRecord.created_at >= since)
            .group_by(SignalDecisionRecord.selected_lane)
        )
        return {lane: count for lane, count in self._db.execute(stmt)}

    def emergency_count(self, intersection_id: str, since: datetime | None = None) -> int:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        stmt = select(func.count(EmergencyEventRecord.id)).where(
            EmergencyEventRecord.intersection_id == intersection_id,
            EmergencyEventRecord.created_at >= since,
            EmergencyEventRecord.state == "CONFIRMED",
        )
        return self._db.execute(stmt).scalar_one()

    def helmet_violation_count(self, intersection_id: str, since: datetime | None = None) -> int:
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))
        stmt = select(func.count(SafetyEventRecord.id)).where(
            SafetyEventRecord.intersection_id == intersection_id,
            SafetyEventRecord.created_at >= since,
        )
        return self._db.execute(stmt).scalar_one()
