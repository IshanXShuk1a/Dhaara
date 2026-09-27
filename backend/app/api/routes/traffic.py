from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.state import app_state
from app.database.database import get_db
from app.models.user import User
from app.services.analytics.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/intersections", tags=["traffic"])


@router.get("/{intersection_id}/traffic")
def get_current_traffic(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not running")
    last = getattr(runtime.controller, "last_snapshot", None)
    if last is None:
        return {"intersection_id": intersection_id, "lanes": {}, "note": "No frames processed yet"}
    return {
        "intersection_id": intersection_id,
        "timestamp": last.timestamp,
        "is_simulated": last.is_simulated,
        "lanes": {
            lane_id: {
                "vehicle_count": m.vehicle_count,
                "occupancy": m.occupancy,
                "queue_length_m": m.queue_length_m,
                "average_speed_kmph": m.average_speed_kmph,
                "average_waiting_time_s": m.average_waiting_time_s,
                "flow_rate": m.flow_rate,
                "traffic_pressure": m.traffic_pressure,
                "status": m.status.value,
                "reasons": m.reasons,
            }
            for lane_id, m in last.lane_metrics.items()
        },
    }


@router.get("/{intersection_id}/traffic/history")
def get_traffic_history(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    service = AnalyticsService(db)
    return {
        "intersection_id": intersection_id,
        "volume": service.volume_history(intersection_id),
        "average_pressure_by_lane": service.average_pressure_by_lane(intersection_id),
    }
