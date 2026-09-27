from __future__ import annotations

from sqlalchemy import String, ForeignKey, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    intersection_id: Mapped[str] = mapped_column(ForeignKey("intersections.id"))
    source_type: Mapped[str] = mapped_column(String)  # UPLOADED_FILE|WEBCAM|RTSP|SIMULATION
    source_url: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="OFFLINE")  # ONLINE|OFFLINE|ERROR
    resolution_width: Mapped[int] = mapped_column(Integer, default=0)
    resolution_height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)

    intersection = relationship("Intersection", back_populates="cameras")
