from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.state import app_state
from app.database.database import get_db
from app.models.safety import SafetyEventRecord
from app.models.user import User
from app.schemas.traffic import SafetySummaryOut

router = APIRouter(prefix="/api", tags=["safety"])


@router.get("/safety")
def list_all_safety_events(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(SafetyEventRecord).order_by(SafetyEventRecord.created_at.desc()).limit(100).all()


@router.get("/intersections/{intersection_id}/safety", response_model=SafetySummaryOut)
def get_intersection_safety(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not running")
    analyzer = runtime.controller.helmet_analyzer
    return SafetySummaryOut(
        intersection_id=intersection_id,
        compliant_count=analyzer.compliant_count,
        violation_count=analyzer.violation_count,
        compliance_rate=analyzer.compliance_rate,  # None if no data yet -> frontend must show N/A
    )
