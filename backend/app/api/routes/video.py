from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.state import app_state
from app.database.database import get_db
from app.models.events import SystemEventRecord
from app.models.user import User
from app.services.cv.video_source import UploadedVideoSource, VideoSourceError
from app.services.cv.lane_assigner import DIRECTIONS

router = APIRouter(prefix="/api/video", tags=["video"])

UPLOAD_DIR = Path("./videos/uploads")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/upload")
def upload_video(
    intersection_id: str,
    direction: str,
    file: UploadFile,
    user: User = Depends(require_role("TRAFFIC_OPERATOR")),
    db: Session = Depends(get_db),
):
    runtime = _runtime_or_404(intersection_id)
    direction = _direction(direction)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported video format: {ext}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Never trust the client filename for the on-disk path (path traversal protection).
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / safe_name

    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Video exceeds 500MB limit")
            out.write(chunk)

    try:
        probe = UploadedVideoSource(str(dest.resolve()))
        probe.open()
        probe.close()
    except VideoSourceError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid video file: {exc}")

    with runtime.lock:
        camera = runtime.cameras[direction]
        camera.path = str(dest.resolve())
        camera.source = UploadedVideoSource(camera.path)
        camera.frame = None
        camera.status, camera.error = "CONNECTING", None
        runtime.controller.reset_camera(direction)
        runtime.processed_frames.pop(direction, None)

    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="SYSTEM_STARTUP",
        message=f"{user.username} uploaded {direction} video {safe_name} for {intersection_id}",
        severity="INFO",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "direction": direction, "path": str(dest.resolve())}


def _runtime_or_404(intersection_id):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(404, "Intersection not configured")
    if runtime.simulation_lab is not None:
        raise HTTPException(409, "The simulation lab does not accept live video controls")
    return runtime


def _direction(direction):
    value = direction.upper()
    if value not in DIRECTIONS:
        raise HTTPException(400, "Direction must be EAST, WEST, NORTH or SOUTH")
    return value


@router.post("/start")
def start_video(intersection_id: str, _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = _runtime_or_404(intersection_id)
    runtime.restart_video_inputs()
    return {"intersection_id": intersection_id, "status": "ONLINE"}


@router.post("/stop")
def stop_video(intersection_id: str, _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        runtime.camera_status = "OFFLINE"
        runtime.processed_frames = {}
        for camera in runtime.cameras.values():
            camera.frame, camera.status = None, "OFFLINE"
    return {"intersection_id": intersection_id, "status": "OFFLINE"}


@router.get("/status")
def video_status(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = _runtime_or_404(intersection_id)
    with runtime.lock:
        last = runtime.controller.last_snapshot
        return {"intersection_id": intersection_id, "camera_status": runtime.camera_status,
                "is_simulated": runtime.is_simulated, "last_frame_index": last.frame_index if last else None,
                "cameras": {d: {"status": c.status, "path": c.path, "error": c.error,
                                 "width": c.frame.width if c.frame else None,
                                 "height": c.frame.height if c.frame else None} for d, c in runtime.cameras.items()}}


def _render_camera(runtime, snapshot, direction, toggles):
    import cv2
    from app.services.cv.overlay_renderer import OverlayRenderer, VehicleOverlayItem
    image = runtime.processed_frames.get(direction)
    if image is None or snapshot is None:
        return None
    lane = snapshot.camera_lanes.get(direction)
    items = [VehicleOverlayItem(t, a, snapshot.ambulance_lights.get(t.track_id, False), None)
             for t, a in snapshot.camera_vehicles.get(direction, []) if a.direction == direction or t.class_name == "ambulance"]
    rendered = OverlayRenderer([lane] if lane else []).render(image, snapshot.lane_metrics, items, **toggles)
    metrics = snapshot.lane_metrics.get(direction)
    color = snapshot.direction_signals.get(direction, "RED")
    cv2.putText(rendered, f"{direction} {color} | Score: {metrics.vehicle_score if metrics else 0:g}",
                (12, 24), cv2.FONT_HERSHEY_SIMPLEX, .55,
                {"GREEN": (60, 220, 60), "YELLOW": (0, 190, 255), "RED": (80, 80, 240)}[color], 2)
    return rendered


@router.get("/frame")
def get_annotated_frame(intersection_id: str, token: str | None = None, direction: str | None = None,
                        show_lanes: bool = True, show_boxes: bool = True,
                        show_labels: bool = True, show_heat: bool = True):
    """Full directional frame, or a 2x2 montage of the independent cameras."""
    import cv2
    from fastapi.responses import Response
    runtime = _runtime_or_404(intersection_id)
    toggles = dict(show_lanes=show_lanes, show_boxes=show_boxes, show_labels=show_labels, show_heat=show_heat)
    with runtime.lock:
        snapshot = runtime.controller.last_snapshot
        if direction:
            direction = _direction(direction)
            annotated = _render_camera(runtime, snapshot, direction, toggles)
            if annotated is None:
                raise HTTPException(503, f"{direction} camera is offline or awaiting inference")
        else:
            panels = []
            for d in DIRECTIONS:
                frame = _render_camera(runtime, snapshot, d, toggles)
                panel = np.zeros((360, 640, 3), dtype=np.uint8)
                if frame is not None:
                    h, w = frame.shape[:2]
                    scale = min(640 / w, 360 / h)
                    resized = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
                    rh, rw = resized.shape[:2]
                    y, x = (360 - rh) // 2, (640 - rw) // 2
                    panel[y:y+rh, x:x+rw] = resized
                else:
                    cv2.putText(panel, f"{d}: OFFLINE", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, .8, (180, 180, 180), 2)
                panels.append(panel)
            annotated = np.vstack([np.hstack(panels[:2]), np.hstack(panels[2:])])
    ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise HTTPException(500, "Frame encoding failed")
    return Response(buffer.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
