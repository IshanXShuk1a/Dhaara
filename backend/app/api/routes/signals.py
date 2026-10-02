from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.state import app_state
from app.database.database import get_db
from app.models.events import SystemEventRecord
from app.models.user import User
from app.schemas.traffic import SignalStateOut, SignalDecisionOut, SignalModeRequest, SignalOverrideRequest
from app.services.signals.signal_fsm import SignalMode, PhaseColor, phase_for

router = APIRouter(prefix="/api/intersections", tags=["signals"])


def _runtime_or_404(intersection_id: str):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not running")
    return runtime


@router.get("/{intersection_id}/signal", response_model=SignalStateOut)
def get_signal_state(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    fsm = runtime.controller.signal_fsm
    last = runtime.controller.last_snapshot
    decision_out = None
    if last and last.decision:
        d = last.decision
        decision_out = SignalDecisionOut(
            selected_direction=d.selected_direction,
            green_duration_s=d.green_duration_s,
            reason=d.reason,
            mode=d.mode,
            traffic_pressure=d.traffic_pressure,
            queue_length_m=d.queue_length_m,
            waiting_time_s=d.waiting_time_s,
            vehicle_count=d.vehicle_count,
            fairness_applied=d.fairness_applied,
            pair_scores=d.pair_scores, denser_pair=d.denser_pair, score_difference=d.score_difference, action=d.action,
        )
    return SignalStateOut(
        intersection_id=intersection_id,
        directions=fsm.direction_states,
        color=fsm.state.color.value,
        active_direction=fsm.state.active_direction,
        target_direction=fsm.state.target_direction,
        countdown_s=fsm.countdown_s,
        previous_phase=fsm.state.previous_phase, full_phase_required=fsm.state.full_phase_required,
        mode=fsm.state.mode.value,
        decision=decision_out,
    )


@router.post("/{intersection_id}/signal/mode")
def set_signal_mode(
    intersection_id: str,
    payload: SignalModeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("TRAFFIC_OPERATOR")),
):
    runtime = _runtime_or_404(intersection_id)
    try:
        mode = SignalMode(payload.mode)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid mode: {payload.mode}")
    with runtime.lock:
        runtime.controller.set_mode(mode)
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="CONFIGURATION_CHANGED",
        message=f"Signal mode changed to {mode.value} by {user.username}",
        severity="INFO",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "mode": mode.value}


@router.post("/{intersection_id}/signal/override")
def manual_override(
    intersection_id: str,
    payload: SignalOverrideRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("TRAFFIC_OPERATOR")),
):
    """Operator override through the same exclusive signal state owner."""
    runtime = _runtime_or_404(intersection_id)
    fsm = runtime.controller.signal_fsm
    with runtime.lock:
        if payload.direction not in fsm.directions + ["EW", "NS"]:
            raise HTTPException(400, f"Unknown direction: {payload.direction}")
        if fsm.state.color == PhaseColor.YELLOW and phase_for(payload.direction) != fsm.state.target_direction:
            raise HTTPException(409, "Yellow transition in progress; wait until it completes")
        fsm.set_mode(SignalMode.MANUAL)
        fsm.request_phase_change(payload.direction, reason=f"MANUAL OVERRIDE by {user.username}: {payload.operator_note}", force=True, action="MANUAL")
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="MANUAL_OVERRIDE",
        message=f"{user.username} overrode signal to {payload.direction}: {payload.operator_note}",
        severity="WARNING",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "overridden_to": payload.direction,
            "status": "TRANSITIONING" if fsm.state.color == PhaseColor.YELLOW else "HELD",
            "target_pair": fsm.state.target_direction or fsm.state.active_direction}
