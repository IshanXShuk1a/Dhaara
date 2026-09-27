from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.services.analytics.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def get_regional_analytics(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    service = AnalyticsService(db)
    return service.regional_summary()


@router.get("/{intersection_id}")
def get_analytics(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    service = AnalyticsService(db)
    return {
        "intersection_id": intersection_id,
        "volume": service.volume_history(intersection_id),
        "average_pressure_by_lane": service.average_pressure_by_lane(intersection_id),
        "signal_distribution": service.signal_distribution(intersection_id),
        "emergency_events_24h": service.emergency_count(intersection_id),
        "helmet_violations_24h": service.helmet_violation_count(intersection_id),
    }
