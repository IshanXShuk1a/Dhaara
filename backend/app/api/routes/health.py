from __future__ import annotations

from fastapi import APIRouter

from app.core.state import app_state

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": "DHAARA",
        "intersections_online": [
            iid for iid, rt in app_state.runtimes.items() if rt.camera_status == "ONLINE"
        ],
        "intersection_count": len(app_state.runtimes),
    }
