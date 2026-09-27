from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Integer, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class SignalStateRecord(Base):
    """Audit-log entry for a completed signal-color transition (from SignalFSM.history)."""

    __tablename__ = "signal_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    from_color: Mapped[str] = mapped_column(String)
    to_color: Mapped[str] = mapped_column(String)
    active_direction: Mapped[str] = mapped_column(String)
    target_direction: Mapped[str | None] = mapped_column(String, nullable=True)
    elapsed_in_previous_s: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="ADAPTIVE")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
