from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.state import app_state
from app.database.database import get_db
from app.models.events import SystemEventRecord
from app.models.simulation import SimulationSessionRecord
from app.models.user import User
from app.schemas.traffic import SimulationSliderRequest, SimulationAmbulanceRequest, SimulationHelmetViolationRequest
from app.services.safety.helmet_analyzer import HelmetState

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


def _runtime_or_404(intersection_id: str):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not configured")
    return runtime


@router.post("/start")
def start_simulation(intersection_id: str, db: Session = Depends(get_db), _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = _runtime_or_404(intersection_id)
    runtime.camera_status = "ONLINE"
    session = SimulationSessionRecord(intersection_id=intersection_id, is_active=True, slider_state={})
    db.add(session)
    db.commit()
    return {"intersection_id": intersection_id, "status": "SIMULATION_STARTED", "session_id": session.id}


@router.post("/reset")
def reset_simulation(intersection_id: str, _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = _runtime_or_404(intersection_id)
    runtime.scenario_provider.clear()
    return {"intersection_id": intersection_id, "status": "RESET"}


@router.post("/traffic")
def set_traffic_sliders(
    intersection_id: str,
    payload: SimulationSliderRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("TRAFFIC_OPERATOR")),
):
    """Mutates the real ScenarioProvider's VehicleScripts for this
    intersection. The next frame processed by IntersectionController will
    see these vehicles through the normal detector->tracker->lane-assigner
    ->lane-intelligence->decision-engine chain - this does not just set a
    number the frontend displays."""
    runtime = _runtime_or_404(intersection_id)
    from app.services.simulation.simulation_engine import TrafficSliderState

    current_frame = runtime.controller.last_snapshot.frame_index if runtime.controller.last_snapshot else 0
    runtime.scenario_builder.apply_slider_state(
        TrafficSliderState(north=payload.north, south=payload.south, east=payload.east, west=payload.west),
        current_frame=current_frame,
    )
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="CONFIGURATION_CHANGED",
        message=f"Simulation traffic sliders set: N={payload.north} S={payload.south} E={payload.east} W={payload.west}",
        severity="INFO",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "sliders": payload.model_dump()}


@router.post("/ambulance")
def spawn_ambulance(
    intersection_id: str,
    payload: SimulationAmbulanceRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("TRAFFIC_OPERATOR")),
):
    runtime = _runtime_or_404(intersection_id)
    current_frame = runtime.controller.last_snapshot.frame_index if runtime.controller.last_snapshot else 0
    script_id = runtime.scenario_builder.spawn_ambulance(payload.direction, current_frame=current_frame)
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="AMBULANCE_DETECTED",
        message=f"Simulated ambulance spawned in {payload.direction}",
        severity="WARNING",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "script_id": script_id, "direction": payload.direction}


@router.post("/helmet-violation")
def spawn_helmet_violation(
    intersection_id: str,
    payload: SimulationHelmetViolationRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("TRAFFIC_OPERATOR")),
):
    runtime = _runtime_or_404(intersection_id)
    current_frame = runtime.controller.last_snapshot.frame_index if runtime.controller.last_snapshot else 0
    script_id = runtime.scenario_builder.spawn_helmet_violation(payload.direction, current_frame=current_frame)
    # Also directly register the safety event/observation, since the simulation
    # detector has no separate helmet-classifier confidence channel - this
    # models what a real helmet-classifier stage would report.
    event = runtime.controller.report_helmet_observation(
        track_id=100000 + script_id,
        lane_id=payload.direction,
        state=HelmetState.NO_HELMET,
        confidence=0.9,
        timestamp=0.0,
    )
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="HELMET_VIOLATION",
        message=f"Simulated helmet violation in {payload.direction}",
        severity="WARNING",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "script_id": script_id, "event": event}
