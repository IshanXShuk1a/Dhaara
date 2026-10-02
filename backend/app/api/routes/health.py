from __future__ import annotations

from fastapi import APIRouter

from app.core.state import app_state

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    live = {iid: runtime for iid, runtime in app_state.runtimes.items()
            if runtime.simulation_lab is None}
    return {
        "status": "ok",
        "app": "DHAARA",
        "intersections_online": [
            iid for iid, runtime in live.items() if runtime.camera_status == "ONLINE"
        ],
        "intersection_count": len(live),
        "simulation_available": any(runtime.simulation_lab is not None for runtime in app_state.runtimes.values()),
    }
