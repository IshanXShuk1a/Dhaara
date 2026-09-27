from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Float, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class TrafficSnapshot(Base):
    """One persisted lane-metrics reading, for analytics/history."""

    __tablename__ = "traffic_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    lane_id: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    vehicle_count: Mapped[int] = mapped_column(Integer)
    occupancy: Mapped[float] = mapped_column(Float)
    queue_length_m: Mapped[float] = mapped_column(Float)
    average_speed_kmph: Mapped[float] = mapped_column(Float)
    average_waiting_time_s: Mapped[float] = mapped_column(Float)
    flow_rate: Mapped[float] = mapped_column(Float)
    traffic_pressure: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)
    is_simulated: Mapped[bool] = mapped_column(default=False)


class SignalDecisionRecord(Base):
    """One persisted decision-engine output, for audit and the decision-explanation card."""

    __tablename__ = "signal_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    selected_lane: Mapped[str] = mapped_column(String)
    reason: Mapped[list] = mapped_column(JSON)  # list[str]
    traffic_pressure: Mapped[float] = mapped_column(Float)
    queue_length_m: Mapped[float] = mapped_column(Float)
    waiting_time_s: Mapped[float] = mapped_column(Float)
    vehicle_count: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String)  # ADAPTIVE|EMERGENCY|FIXED
    fairness_applied: Mapped[bool] = mapped_column(default=False)
    green_duration_s: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
