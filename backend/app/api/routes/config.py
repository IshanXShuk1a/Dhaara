from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.config import get_settings
from app.database.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def get_config(_user: User = Depends(require_role("ADMIN"))):
    settings = get_settings()
    return {
        "detection": settings.detection.model_dump(),
        "signal_timings": settings.signal_timings.model_dump(),
        "lane_thresholds": settings.lane_thresholds.model_dump(),
        "pressure_weights": settings.pressure_weights.model_dump(),
    }


@router.put("")
def update_config(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("ADMIN")),
):
    """Safely updates running configuration and applies changes live across
    all registered intersection controllers without restarting the server."""
    from app.core.state import app_state
    from app.core.domain_config import (
        LaneThresholds as DomainLaneThresholds,
        PressureWeights as DomainPressureWeights,
        SignalTimings as DomainSignalTimings,
        DetectionConfig as DomainDetectionConfig,
        DomainConfig,
    )
    from app.models.events import SystemEventRecord

    settings = get_settings()

    validated = {}
    try:
        for section in ("detection", "signal_timings", "lane_thresholds", "pressure_weights"):
            if section in payload:
                current = getattr(settings, section)
                if not isinstance(payload[section], dict):
                    raise HTTPException(422, f"{section} must be an object")
                validated[section] = type(current).model_validate({**current.model_dump(), **payload[section]})
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_context=False)) from exc
    for section, value in validated.items():
        setattr(settings, section, value)

    # Build updated domain config
    updated_domain = DomainConfig(
        lane_thresholds=DomainLaneThresholds(**settings.lane_thresholds.model_dump()),
        pressure_weights=DomainPressureWeights(**settings.pressure_weights.model_dump()),
        signal_timings=DomainSignalTimings(**settings.signal_timings.model_dump()),
        detection=DomainDetectionConfig(**settings.detection.model_dump()),
    )

    # Propagate to all live controllers
    for runtime in app_state.runtimes.values():
        if runtime.simulation_lab is not None:
            continue  # live configuration cannot alter an active educational scenario
        with runtime.lock:
            c = runtime.controller
            c._config = updated_domain
            c._decision_engine._timings = updated_domain.signal_timings
            c._lane_engine._config = updated_domain
            c._signal_fsm._timings = updated_domain.signal_timings
            if runtime.real_detector is not None:
                runtime.real_detector._confidence_threshold = updated_domain.detection.yolo_confidence
                runtime.real_detector._ambulance_detector.confidence_threshold = updated_domain.detection.ambulance_confidence
            c._helmet_detector.confidence_threshold = updated_domain.detection.helmet_confidence
            c._helmet_analyzer.config = updated_domain.detection
            c._ambulance_confirmation._config = updated_domain.detection

    db.add(SystemEventRecord(
        intersection_id=None,
        event_type="CONFIGURATION_CHANGED",
        message=f"System configuration updated by {user.username}",
        severity="INFO",
        metadata_json=payload,
    ))
    db.commit()

    return {
        "status": "CONFIG_UPDATED",
        "detection": settings.detection.model_dump(),
        "signal_timings": settings.signal_timings.model_dump(),
        "lane_thresholds": settings.lane_thresholds.model_dump(),
        "pressure_weights": settings.pressure_weights.model_dump(),
    }
