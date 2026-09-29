from __future__ import annotations

import shutil
import time
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

router = APIRouter(prefix="/api/video", tags=["video"])

UPLOAD_DIR = Path("./videos/uploads")
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/upload")
def upload_video(
    intersection_id: str,
    file: UploadFile,
    user: User = Depends(require_role("TRAFFIC_OPERATOR")),
    db: Session = Depends(get_db),
):
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
        probe = UploadedVideoSource(str(dest))
        probe.open()
        probe.close()
    except VideoSourceError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid video file: {exc}")

    db.add(SystemEventRecord(
        intersection_id=intersection_id,
        event_type="SYSTEM_STARTUP",
        message=f"{user.username} uploaded video {safe_name} for {intersection_id}",
        severity="INFO",
    ))
    db.commit()
    return {"intersection_id": intersection_id, "path": str(dest)}


@router.post("/start")
def start_video(intersection_id: str, _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not configured")
    runtime.camera_status = "ONLINE"
    return {"intersection_id": intersection_id, "status": "ONLINE"}


@router.post("/stop")
def stop_video(intersection_id: str, _user: User = Depends(require_role("TRAFFIC_OPERATOR"))):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not configured")
    runtime.camera_status = "OFFLINE"
    return {"intersection_id": intersection_id, "status": "OFFLINE"}


@router.get("/status")
def video_status(intersection_id: str, _user: User = Depends(get_current_user)):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not configured")
    last = runtime.controller.last_snapshot
    return {
        "intersection_id": intersection_id,
        "camera_status": runtime.camera_status,
        "is_simulated": last.is_simulated if last else None,
        "last_frame_index": last.frame_index if last else None,
    }


@router.get("/frame")
def get_annotated_frame(
    intersection_id: str,
    token: str | None = None,
    direction: str | None = None,
    show_lanes: bool = True,
    show_boxes: bool = True,
    show_labels: bool = True,
    show_heat: bool = True,
):
    """Returns the most recent annotated frame (lane polygons, vehicle boxes,
    track IDs, ambulance flags, helmet labels) as a JPEG.
    When direction is provided (NORTH, SOUTH, EAST, WEST), crops and formats
    a dedicated CCTV approach feed showing that lane's traffic, density,
    and signal allotment status."""
    import cv2
    from fastapi.responses import Response
    from app.services.cv.overlay_renderer import OverlayRenderer, VehicleOverlayItem

    runtime = app_state.get(intersection_id)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intersection not configured")

    # Safely retrieve frame from control loop, waiting briefly if initializing
    frame_image = runtime.last_frame_image
    if frame_image is None:
        for _ in range(8):
            time.sleep(0.04)
            frame_image = runtime.last_frame_image
            if frame_image is not None:
                break

    if frame_image is None or getattr(frame_image, "size", 0) == 0:
        w, h = 1280, 720
        canvas = np.full((h, w, 3), (38, 40, 44), dtype=np.uint8)
        cv2.rectangle(canvas, (0, int(h * 0.25)), (w, int(h * 0.75)), (52, 54, 60), -1)
        cv2.rectangle(canvas, (int(w * 0.25), 0), (int(w * 0.75), h), (52, 54, 60), -1)
        frame_image = canvas

    snapshot = runtime.controller.last_snapshot
    renderer = OverlayRenderer(runtime.lanes)

    if snapshot is None:
        lane_metrics = {}
        vehicle_items = []
    else:
        lane_metrics = snapshot.lane_metrics
        confirmed_amb_id = runtime.controller.emergency_manager.active_track_id
        helmet_states = getattr(snapshot, "vehicle_helmet_states", {})
        vehicle_items = [
            VehicleOverlayItem(
                track=t,
                lane_assignment=a,
                is_ambulance_confirmed=(t.track_id == confirmed_amb_id or t.class_name == "ambulance"),
                helmet_label=helmet_states.get(t.track_id),
            )
            for t, a in snapshot.vehicles
        ]

    annotated = renderer.render(
        frame_image,
        lane_metrics,
        vehicle_items,
        show_lanes=show_lanes,
        show_boxes=show_boxes,
        show_labels=show_labels,
        show_heat=show_heat,
    )

    # If an individual approach camera feed is requested, crop and render dedicated approach OSD
    if direction and direction.upper() in ("NORTH", "SOUTH", "EAST", "WEST"):
        dir_upper = direction.upper()
        h_img, w_img = annotated.shape[:2]
        target_lane = next((l for l in runtime.lanes if l.direction.upper() == dir_upper), None)
        if target_lane and target_lane.polygon:
            min_x = min(p[0] for p in target_lane.polygon)
            max_x = max(p[0] for p in target_lane.polygon)
            min_y = min(p[1] for p in target_lane.polygon)
            max_y = max(p[1] for p in target_lane.polygon)

            margin = 60
            if dir_upper == "NORTH":
                crop_x1 = max(0, min_x - margin)
                crop_x2 = min(w_img, max_x + margin)
                crop_y1 = max(0, min_y)
                crop_y2 = min(h_img, max_y + 80)
            elif dir_upper == "SOUTH":
                crop_x1 = max(0, min_x - margin)
                crop_x2 = min(w_img, max_x + margin)
                crop_y1 = max(0, min_y - 80)
                crop_y2 = min(h_img, max_y)
            elif dir_upper == "EAST":
                crop_x1 = max(0, min_x - 80)
                crop_x2 = min(w_img, max_x)
                crop_y1 = max(0, min_y - margin)
                crop_y2 = min(h_img, max_y + margin)
            else:  # WEST
                crop_x1 = max(0, min_x)
                crop_x2 = min(w_img, max_x + 80)
                crop_y1 = max(0, min_y - margin)
                crop_y2 = min(h_img, max_y + margin)

            cropped = annotated[int(crop_y1):int(crop_y2), int(crop_x1):int(crop_x2)]
            if cropped.size > 0:
                annotated = cv2.resize(cropped, (640, 360), interpolation=cv2.INTER_LINEAR)

        # On-Screen Display (OSD) overlay for dedicated camera
        cam_map = {"NORTH": "CAM-01", "SOUTH": "CAM-02", "EAST": "CAM-03", "WEST": "CAM-04"}
        cam_id = cam_map.get(dir_upper, "CAM-0X")
        h_ann, w_ann = annotated.shape[:2]

        # Top and bottom OSD banners
        cv2.rectangle(annotated, (0, 0), (w_ann, 32), (18, 20, 24), -1)
        cv2.rectangle(annotated, (0, h_ann - 24), (w_ann, h_ann), (18, 20, 24), -1)

        # Top Left: Camera identifier
        cv2.circle(annotated, (14, 16), 4, (0, 0, 240), -1)
        cv2.putText(annotated, f"{cam_id} • {dir_upper} APPROACH", (24, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # Top Right: Allotment status
        is_allotted = bool(snapshot and snapshot.signal_active_direction == dir_upper and snapshot.signal_state == "GREEN")
        is_yellow = bool(snapshot and snapshot.signal_active_direction == dir_upper and snapshot.signal_state == "YELLOW")
        countdown = snapshot.signal_countdown_s if snapshot else 0.0
        if is_allotted:
            badge_text = f"ALLOTTED: GREEN [{countdown:.0f}s]"
            badge_color = (60, 220, 60)
        elif is_yellow:
            badge_text = f"CLEARING: YELLOW [{countdown:.0f}s]"
            badge_color = (0, 200, 255)
        else:
            badge_text = "WAITING IN QUEUE"
            badge_color = (80, 80, 240)

        (tw, _), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.putText(annotated, badge_text, (w_ann - tw - 12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45, badge_color, 1, cv2.LINE_AA)

        # Bottom Left: Calculated Density & Metrics
        lane_m = snapshot.lane_metrics.get(dir_upper) if snapshot else None
        if lane_m:
            dens_text = f"DENSITY: {lane_m.traffic_pressure:.1f}% ({lane_m.status.value}) | {lane_m.vehicle_count} VEHICLES | QUEUE: {lane_m.queue_length_m:.0f}m"
        else:
            dens_text = "DENSITY: 0.0% (FREE)"
        cv2.putText(annotated, dens_text, (10, h_ann - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1, cv2.LINE_AA)

        # Bottom Right: ITS System
        cv2.putText(annotated, "DHAARA ITS • 25 FPS", (w_ann - 140, h_ann - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1, cv2.LINE_AA)

    ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Frame encoding failed")
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
