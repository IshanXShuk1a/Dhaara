from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class SimulationSessionRecord(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    slider_state: Mapped[dict] = mapped_column(JSON, default=dict)  # {north, south, east, west}
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
