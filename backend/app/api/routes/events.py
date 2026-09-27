from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.database import get_db
from app.models.events import SystemEventRecord
from app.models.user import User

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(SystemEventRecord).order_by(SystemEventRecord.timestamp.desc()).limit(200).all()


@router.get("/{intersection_id}")
def list_intersection_events(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return (
        db.query(SystemEventRecord)
        .filter(SystemEventRecord.intersection_id == intersection_id)
        .order_by(SystemEventRecord.timestamp.desc())
        .limit(200)
        .all()
    )
