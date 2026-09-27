from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.state import app_state
from app.database.database import get_db
from app.models.events import SystemEventRecord
from app.models.user import User
from app.schemas.traffic import SignalStateOut, SignalDecisionOut, SignalModeRequest, SignalOverrideRequest
from app.services.signals.signal_fsm import SignalMode

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
        )
    return SignalStateOut(
        intersection_id=intersection_id,
        color=fsm.state.color.value,
        active_direction=fsm.state.active_direction,
        target_direction=fsm.state.target_direction,
        countdown_s=last.signal_countdown_s if last else 0.0,
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
    """Police/operator override: force the signal toward `direction` via the
    SAME safe SignalFSM transition path (GREEN->YELLOW->ALL_RED->GREEN) used
    by adaptive decisions - manual override never bypasses signal safety."""
    runtime = _runtime_or_404(intersection_id)
    fsm = runtime.controller.signal_fsm
    fsm.set_mode(SignalMode.MANUAL)
    try:
        fsm.request_phase_change(payload.direction, reason=f"MANUAL OVERRIDE by {user.username}: {payload.operator_note}", force=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="MANUAL_OVERRIDE",
        message=f"{user.username} overrode signal to {payload.direction}: {payload.operator_note}",
        severity="WARNING",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "overridden_to": payload.direction}
