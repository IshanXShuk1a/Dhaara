from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LaneOut(BaseModel):
    id: str
    intersection_id: str
    direction: str
    polygon: list[list[float]]
    pixels_per_meter: float
    length_m: float
    capacity_vehicles: int
    status: str

    class Config:
        from_attributes = True


class LaneConfigureRequest(BaseModel):
    direction: str
    polygon: list[list[float]] = Field(..., min_length=3)
    pixels_per_meter: float = 8.0
    length_m: float = 50.0
    capacity_vehicles: int = 25


class CameraOut(BaseModel):
    id: str
    intersection_id: str
    source_type: str
    source_url: str
    status: str
    resolution_width: int
    resolution_height: int
    fps: float

    class Config:
        from_attributes = True


class IntersectionOut(BaseModel):
    id: str
    name: str
    location: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class IntersectionCreateRequest(BaseModel):
    id: str
    name: str
    location: str = ""


class IntersectionUpdateRequest(BaseModel):
    name: str | None = None
    location: str | None = None
    status: str | None = None
