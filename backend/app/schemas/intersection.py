from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LaneOut(BaseModel):
    id: str
    intersection_id: str
    direction: str
    polygon: list[list[float]]
    coordinate_space: str = "normalized"
    pixels_per_meter: float
    length_m: float
    capacity_vehicles: int
    status: str

    class Config:
        from_attributes = True


class LaneConfigureRequest(BaseModel):
    direction: str
    polygon: list[list[float]] = Field(..., min_length=4, max_length=4)
    coordinate_space: str = "normalized"

    @field_validator("direction")
    @classmethod
    def check_direction(cls, value):
        from app.services.cv.lane_assigner import DIRECTIONS
        value = value.upper()
        if value not in DIRECTIONS:
            raise ValueError("Direction must be EAST, WEST, NORTH or SOUTH")
        return value

    @field_validator("coordinate_space")
    @classmethod
    def check_space(cls, value):
        if value != "normalized":
            raise ValueError("ROI coordinates must be normalized")
        return value

    @field_validator("polygon")
    @classmethod
    def check_roi(cls, value):
        from app.services.cv.lane_assigner import validate_normalized_roi
        return [list(p) for p in validate_normalized_roi(value)]
    pixels_per_meter: float = Field(8.0, gt=0)
    length_m: float = Field(9.144, gt=0)
    capacity_vehicles: int = Field(25, gt=0)


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
