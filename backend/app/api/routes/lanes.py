from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.database.database import get_db
from app.models.lane import Lane
from app.models.user import User
from app.schemas.intersection import LaneOut, LaneConfigureRequest

router = APIRouter(prefix="/api/intersections", tags=["lanes"])


@router.get("/{intersection_id}/lanes", response_model=list[LaneOut])
def get_lanes(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Lane).filter(Lane.intersection_id == intersection_id).all()


@router.put("/{intersection_id}/lanes", response_model=list[LaneOut])
def configure_lanes(
    intersection_id: str,
    payload: list[LaneConfigureRequest],
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("ADMIN")),
):
    """Replaces this intersection's lane geometry. Configuration only -
    callers must separately restart/reload the IntersectionController's
    LaneAssigner for the change to take effect on the live pipeline
    (see /api/video/start), since polygons are baked into the running
    LaneAssigner instance for performance."""
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one lane is required")

    db.query(Lane).filter(Lane.intersection_id == intersection_id).delete()
    created = []
    for lane_cfg in payload:
        lane = Lane(
            id=f"{intersection_id}:{lane_cfg.direction}",
            intersection_id=intersection_id,
            direction=lane_cfg.direction,
            polygon=lane_cfg.polygon,
            pixels_per_meter=lane_cfg.pixels_per_meter,
            length_m=lane_cfg.length_m,
            capacity_vehicles=lane_cfg.capacity_vehicles,
        )
        db.add(lane)
        created.append(lane)
    db.commit()
    for lane in created:
        db.refresh(lane)

    from app.core.state import app_state
    from app.services.cv.lane_assigner import LanePolygon, LaneAssigner
    from app.services.lanes.lane_intelligence import LaneGeometry

    runtime = app_state.get(intersection_id)
    if runtime is not None:
        new_polygons = [
            LanePolygon(
                lane_id=cfg.direction,
                direction=cfg.direction,
                polygon=[tuple(pt) for pt in cfg.polygon],
                pixels_per_meter=cfg.pixels_per_meter,
            )
            for cfg in payload
        ]
        runtime.lanes = new_polygons
        runtime.controller._lane_assigner = LaneAssigner(new_polygons, fps=25.0)
        runtime.controller._lane_geometry = {
            cfg.direction: LaneGeometry(
                lane_id=cfg.direction,
                length_m=cfg.length_m,
                capacity_vehicles=cfg.capacity_vehicles,
            )
            for cfg in payload
        }

    return created
