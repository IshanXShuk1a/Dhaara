from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class SystemEventRecord(Base):
    """General-purpose structured event log: startup, camera connect/disconnect,
    model load/error, manual overrides, config changes, etc."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str | None] = mapped_column(ForeignKey("intersections.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="INFO")  # INFO|WARNING|ERROR|CRITICAL
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
