"""Authenticated classroom controls, restricted to the image demonstration."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.core.state import app_state
from app.api.websocket import runtime_to_payload
from app.services.image_demo import IMAGE_DEMO_ID

router = APIRouter(prefix="/api/image-demo", tags=["image demo"])

class CaseRequest(BaseModel):
    case_id: Literal["balanced_heavy", "heavy_normal", "normal_low", "heavy_low", "heavy_ambulance", "balanced_normal"]
    swapped: bool = False

class ControlRequest(BaseModel):
    paused: bool | None = None
    speed: Literal[1, 2, 5, 10] | None = None
    auto_tour: bool | None = None
    lights_active: bool | None = None

def get_runtime():
    runtime = app_state.get(IMAGE_DEMO_ID)
    if runtime is None or runtime.image_demo is None:
        raise HTTPException(404, "Image demonstration unavailable; add the four source images to backend/images")
    return runtime

@router.get("")
def state(_user=Depends(get_current_user)):
    runtime = get_runtime()
    with runtime.lock:
        return runtime_to_payload(IMAGE_DEMO_ID, runtime)

@router.post("/case")
def select_case(payload: CaseRequest, _user=Depends(get_current_user)):
    runtime = get_runtime()
    with runtime.lock:
        runtime.image_demo.select_case(runtime, payload.case_id, payload.swapped)
        runtime.image_demo.observe(runtime)
        return runtime_to_payload(IMAGE_DEMO_ID, runtime)

@router.post("/control")
def control(payload: ControlRequest, _user=Depends(get_current_user)):
    runtime = get_runtime()
    with runtime.lock:
        session = runtime.image_demo
        # Validate the entire request before changing any controls.
        if payload.lights_active and "ambulance" not in session.sources.values():
            raise HTTPException(409, "Select Heavy / ambulance before enabling demo lights")
        if payload.paused is not None:
            session.paused = payload.paused
        if payload.speed is not None:
            session.speed = payload.speed
        if payload.auto_tour is not None:
            session.auto_tour = payload.auto_tour
            if payload.auto_tour and session.case_id == "heavy_ambulance" and payload.lights_active is None:
                session.set_lights(True)
        if payload.lights_active is not None:
            session.set_lights(payload.lights_active)
            if runtime.controller.last_snapshot is not None:
                session.observe(runtime)
        session.revision += 1
        return runtime_to_payload(IMAGE_DEMO_ID, runtime)
