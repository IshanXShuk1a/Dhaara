from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Intersection(Base):
    __tablename__ = "intersections"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "OD-BBSR-001"
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="ONLINE")  # ONLINE|OFFLINE|HIGH_TRAFFIC|EMERGENCY
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    lanes = relationship("Lane", back_populates="intersection", cascade="all, delete-orphan")
    cameras = relationship("Camera", back_populates="intersection", cascade="all, delete-orphan")
