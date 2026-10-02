"""Controls for the isolated educational lab, never for live camera runtimes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.websocket import snapshot_to_payload
from app.core.auth import get_current_user
from app.core.state import app_state
from app.models.user import User
from app.schemas.traffic import (
    SimulationSliderRequest, SimulationAmbulanceRequest, SimulationHelmetViolationRequest,
    SimulationScenarioRequest, SimulationControlRequest,
)
from app.services.safety.helmet_analyzer import HelmetState
from app.services.simulation.lab import SIMULATION_INTERSECTION_ID
from app.services.simulation.simulation_engine import TrafficSliderState

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


def _runtime_or_404(intersection_id: str):
    if intersection_id != SIMULATION_INTERSECTION_ID:
        raise HTTPException(409, "Simulation controls are isolated from live intersections; use SIMULATION-LAB")
    runtime = app_state.get(intersection_id)
    if runtime is None or runtime.simulation_lab is None:
        raise HTTPException(404, "Simulation lab is not configured")
    return runtime


def _payload(runtime):
    result = snapshot_to_payload(SIMULATION_INTERSECTION_ID, runtime.controller)
    result["simulation"] = runtime.simulation_lab.metadata()
    return result


@router.get("/state")
def get_simulation_state(intersection_id: str = SIMULATION_INTERSECTION_ID,
                         _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        return _payload(runtime)


@router.post("/start")
def start_simulation(intersection_id: str = SIMULATION_INTERSECTION_ID,
                     _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        runtime.simulation_lab.paused = False
        return {**_payload(runtime), "status": "SIMULATION_STARTED"}


@router.post("/scenario")
def set_scenario(payload: SimulationScenarioRequest,
                 intersection_id: str = SIMULATION_INTERSECTION_ID,
                 _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        runtime.simulation_lab.reset(runtime, payload.scenario)
        return _payload(runtime)


@router.post("/control")
def set_simulation_control(payload: SimulationControlRequest,
                           intersection_id: str = SIMULATION_INTERSECTION_ID,
                           _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        if payload.paused is not None:
            runtime.simulation_lab.paused = payload.paused
        if payload.speed is not None:
            runtime.simulation_lab.speed = payload.speed
        return _payload(runtime)


@router.post("/reset")
def reset_simulation(intersection_id: str = SIMULATION_INTERSECTION_ID,
                     _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        runtime.simulation_lab.reset(runtime)
        return {**_payload(runtime), "status": "RESET"}


@router.post("/traffic")
def set_traffic_sliders(payload: SimulationSliderRequest,
                        intersection_id: str = SIMULATION_INTERSECTION_ID,
                        _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        lab = runtime.simulation_lab
        lab.scenario, lab.label = "custom", "Custom traffic"
        lab.run_id += 1
        lab.set_targets(runtime, TrafficSliderState(**payload.model_dump()))
        lab._process_step(runtime, 0.0)
        return {**_payload(runtime), "sliders": payload.model_dump()}


@router.post("/ambulance")
def spawn_ambulance(payload: SimulationAmbulanceRequest,
                    intersection_id: str = SIMULATION_INTERSECTION_ID,
                    _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        script_id = runtime.simulation_lab.spawn_ambulance(runtime, payload.direction, payload.lights_active)
        return {**_payload(runtime), "script_id": script_id, "direction": payload.direction,
                "lights_active": payload.lights_active}


@router.post("/helmet-violation")
def spawn_helmet_violation(payload: SimulationHelmetViolationRequest,
                           intersection_id: str = SIMULATION_INTERSECTION_ID,
                           _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        script_id = runtime.scenario_builder.spawn_helmet_violation(payload.direction, runtime.frame_index)
        event = runtime.controller.report_helmet_observation(
            track_id=100000 + script_id, lane_id=payload.direction,
            state=HelmetState.NO_HELMET, confidence=.9, timestamp=0.0)
        return {"intersection_id": SIMULATION_INTERSECTION_ID, "script_id": script_id, "event": event}
