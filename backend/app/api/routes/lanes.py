from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.state import app_state
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
    """Persist four normalized ROIs and apply them to the live camera assigners."""
    from app.services.cv.lane_assigner import DIRECTIONS
    if len(payload) != 4 or {cfg.direction for cfg in payload} != set(DIRECTIONS):
        raise HTTPException(400, "Configure exactly one ROI for each of EAST, WEST, NORTH and SOUTH")

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
    from app.services.lanes.lane_intelligence import LaneGeometry
    runtime = app_state.get(intersection_id)
    if runtime is not None:
        with runtime.lock:
            for cfg in payload:
                runtime.controller.configure_camera_roi(cfg.direction, cfg.polygon,
                    LaneGeometry(cfg.direction, cfg.length_m, cfg.capacity_vehicles), cfg.pixels_per_meter)

    return created
