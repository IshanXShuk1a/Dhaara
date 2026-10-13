from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.state import app_state
from app.database.database import get_db
from app.models.intersection import Intersection
from app.models.user import User
from app.schemas.intersection import IntersectionOut, IntersectionCreateRequest, IntersectionUpdateRequest

router = APIRouter(prefix="/api/intersections", tags=["intersections"])


@router.get("", response_model=list[IntersectionOut])
def list_intersections(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    from datetime import datetime, timezone
    from pathlib import Path
    from app.services.image_demo import IMAGE_DEMO_ID
    rows = db.query(Intersection).all()
    demo = app_state.get(IMAGE_DEMO_ID)
    if demo is None:
        return rows
    video_paths = [Path(camera.path) for runtime in app_state.runtimes.values()
                   if runtime.simulation_lab is None and runtime.image_demo is None
                   for camera in runtime.cameras.values()]
    has_video = any((path if path.is_absolute() else Path(__file__).resolve().parents[3] / path).is_file()
                    for path in video_paths)
    return [IntersectionOut(id=IMAGE_DEMO_ID, name="Image traffic demonstration", location="Supplied EW / NS reference images",
            status="IMAGE_DEMO", created_at=datetime.fromtimestamp(demo.image_demo.started_at, timezone.utc),
            input_mode="IMAGE_DEMO", preferred=not has_video), *rows]


@router.get("/{intersection_id}", response_model=IntersectionOut)
def get_intersection(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    if intersection_id == "IMAGE-DEMO":
        return next((item for item in list_intersections(db, _user) if getattr(item, "id", None) == intersection_id), None) or _missing_demo()
    intersection = db.get(Intersection, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not found")
    return intersection


def _missing_demo():
    raise HTTPException(404, "Image demonstration unavailable")


@router.post("", response_model=IntersectionOut, status_code=status.HTTP_201_CREATED)
def create_intersection(
    payload: IntersectionCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("ADMIN")),
):
    if db.get(Intersection, payload.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Intersection already exists")
    intersection = Intersection(id=payload.id, name=payload.name, location=payload.location)
    db.add(intersection)
    db.commit()
    db.refresh(intersection)
    return intersection


@router.put("/{intersection_id}", response_model=IntersectionOut)
def update_intersection(
    intersection_id: str,
    payload: IntersectionUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("ADMIN")),
):
    intersection = db.get(Intersection, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(intersection, field, value)
    db.commit()
    db.refresh(intersection)
    return intersection
