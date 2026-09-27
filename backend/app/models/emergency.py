from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Integer, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class EmergencyEventRecord(Base):
    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    ambulance_track_id: Mapped[int] = mapped_column(Integer)
    lane_id: Mapped[str] = mapped_column(String)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String)  # DETECTED|CONFIRMED|PRIORITY_REQUESTED|PRIORITY_ACTIVE|PASSED|RESOLVED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
