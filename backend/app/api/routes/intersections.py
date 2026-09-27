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
    return db.query(Intersection).all()


@router.get("/{intersection_id}", response_model=IntersectionOut)
def get_intersection(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    intersection = db.get(Intersection, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not found")
    return intersection


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
