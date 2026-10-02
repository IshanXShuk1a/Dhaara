from __future__ import annotations

from sqlalchemy import String, ForeignKey, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Lane(Base):
    __tablename__ = "lanes"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "OD-BBSR-001:NORTH"
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    direction: Mapped[str] = mapped_column(String)  # NORTH|SOUTH|EAST|WEST
    polygon: Mapped[list] = mapped_column(JSON)  # [[x,y], ...] configured ROI, not hard-coded in frontend
    pixels_per_meter: Mapped[float] = mapped_column(Float, default=8.0)
    length_m: Mapped[float] = mapped_column(Float, default=9.144)
    capacity_vehicles: Mapped[int] = mapped_column(Integer, default=25)
    status: Mapped[str] = mapped_column(String, default="FREE")  # last computed status, cached for quick reads

    intersection = relationship("Intersection", back_populates="lanes")
