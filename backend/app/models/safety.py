from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Integer, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class SafetyEventRecord(Base):
    __tablename__ = "safety_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    event_type: Mapped[str] = mapped_column(String)  # NO_HELMET
    lane_id: Mapped[str] = mapped_column(String)
    track_id: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
