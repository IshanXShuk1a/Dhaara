from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.state import app_state
from app.database.database import get_db
from app.models.emergency import EmergencyEventRecord
from app.models.user import User

router = APIRouter(prefix="/api", tags=["emergency"])


@router.get("/emergency")
def list_all_emergencies(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.query(EmergencyEventRecord).order_by(EmergencyEventRecord.created_at.desc()).limit(100).all()
    return rows


@router.get("/intersections/{intersection_id}/emergency")
def get_intersection_emergency(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not running")
    mgr = runtime.controller.emergency_manager
    return {
        "intersection_id": intersection_id,
        "state": mgr.state.value,
        "active_direction": mgr.active_direction,
        "active_lane_id": mgr.active_lane_id,
        "active_track_id": mgr.active_track_id,
        "recent_events": [
            {
                "ambulance_track_id": e.ambulance_track_id,
                "lane_id": e.lane_id,
                "direction": e.direction,
                "confidence": e.confidence,
                "state": e.state.value,
                "timestamp": e.timestamp,
            }
            for e in mgr.events[-20:]
        ],
    }
