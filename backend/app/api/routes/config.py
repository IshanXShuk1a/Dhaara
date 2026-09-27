from __future__ import annotations

from fastapi import APIRouter, Depends
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
        "fairness": settings.fairness.model_dump(),
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
        FairnessConfig as DomainFairnessConfig,
        DetectionConfig as DomainDetectionConfig,
        DomainConfig,
    )
    from app.models.events import SystemEventRecord

    settings = get_settings()

    if "detection" in payload and isinstance(payload["detection"], dict):
        for k, v in payload["detection"].items():
            if hasattr(settings.detection, k):
                setattr(settings.detection, k, float(v) if isinstance(v, (int, float)) else v)

    if "signal_timings" in payload and isinstance(payload["signal_timings"], dict):
        for k, v in payload["signal_timings"].items():
            if hasattr(settings.signal_timings, k):
                setattr(settings.signal_timings, k, int(v) if isinstance(v, (int, float)) else v)

    if "fairness" in payload and isinstance(payload["fairness"], dict):
        for k, v in payload["fairness"].items():
            if hasattr(settings.fairness, k):
                setattr(settings.fairness, k, int(v) if isinstance(v, (int, float)) else v)

    if "lane_thresholds" in payload and isinstance(payload["lane_thresholds"], dict):
        for k, v in payload["lane_thresholds"].items():
            if hasattr(settings.lane_thresholds, k):
                setattr(settings.lane_thresholds, k, float(v) if isinstance(v, (int, float)) else v)

    if "pressure_weights" in payload and isinstance(payload["pressure_weights"], dict):
        for k, v in payload["pressure_weights"].items():
            if hasattr(settings.pressure_weights, k):
                setattr(settings.pressure_weights, k, float(v) if isinstance(v, (int, float)) else v)

    # Build updated domain config
    updated_domain = DomainConfig(
        lane_thresholds=DomainLaneThresholds(**settings.lane_thresholds.model_dump()),
        pressure_weights=DomainPressureWeights(**settings.pressure_weights.model_dump()),
        signal_timings=DomainSignalTimings(**settings.signal_timings.model_dump()),
        fairness=DomainFairnessConfig(**settings.fairness.model_dump()),
        detection=DomainDetectionConfig(**settings.detection.model_dump()),
    )

    # Propagate to all live controllers
    for runtime in app_state.runtimes.values():
        c = runtime.controller
        c._config = updated_domain
        c._decision_engine._timings = updated_domain.signal_timings
        c._lane_engine._config = updated_domain
        c._signal_fsm._timings = updated_domain.signal_timings
        c._fairness._config = updated_domain.fairness
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
        "fairness": settings.fairness.model_dump(),
        "lane_thresholds": settings.lane_thresholds.model_dump(),
        "pressure_weights": settings.pressure_weights.model_dump(),
    }
