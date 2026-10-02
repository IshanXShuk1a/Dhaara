from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.services.cv.image_classifier import classifier_service

router = APIRouter(prefix="/api/classifier", tags=["classifier"])

ALLOWED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/avi",
    "video/x-matroska",
    "application/octet-stream",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
MAX_MEDIA_BYTES = 60 * 1024 * 1024  # 60 MB


@router.post("/classify")
async def classify_traffic_image(file: UploadFile = File(...)):
    """Upload an image or video file and receive full AI traffic classification, vehicle counts,
    density calculations, and an annotated visualization image with bounding boxes."""
    filename = file.filename or "uploaded_media.jpg"
    ext = Path(filename).suffix.lower()

    if file.content_type and file.content_type not in ALLOWED_MEDIA_TYPES and ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media type: {file.content_type}. Please upload a JPEG, PNG, WebP image or MP4/MOV/AVI video.",
        )

    content = await file.read()
    if len(content) > MAX_MEDIA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Media file exceeds 60MB limit.",
        )

    is_video = (
        (file.content_type and file.content_type.startswith("video/"))
        or ext in VIDEO_EXTENSIONS
    )

    try:
        if is_video:
            # Write to a temporary file for OpenCV VideoCapture decoding
            with tempfile.NamedTemporaryFile(suffix=ext or ".mp4", delete=False) as temp_video:
                temp_video.write(content)
                temp_video_path = temp_video.name

            try:
                result = classifier_service.classify_video_file(temp_video_path, filename=filename)
                return result
            finally:
                if os.path.exists(temp_video_path):
                    try:
                        os.remove(temp_video_path)
                    except OSError:
                        pass
        else:
            result = classifier_service.classify_image(content, filename=filename)
            return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification inference failed: {str(e)}",
        )


@router.post("/classify-quad")
async def classify_quad_traffic_images(
    files: list[UploadFile] = File(None, description="List of up to 4 image files uploaded simultaneously"),
    file1: UploadFile | None = File(None, description="Approach 1 (North) image"),
    file2: UploadFile | None = File(None, description="Approach 2 (South) image"),
    file3: UploadFile | None = File(None, description="Approach 3 (East) image"),
    file4: UploadFile | None = File(None, description="Approach 4 (West) image"),
    label1: str = "Approach 1 (North)",
    label2: str = "Approach 2 (South)",
    label3: str = "Approach 3 (East)",
    label4: str = "Approach 4 (West)",
):
    """Accepts four image inputs simultaneously. Performs multi-approach vehicle detection,
    comparative density analysis across all four approaches, and outputs classifications
    based on relative traffic levels, imbalance indices, and proportional signal allocations."""
    collected_files = []
    labels = [label1, label2, label3, label4]

    if files and len(files) >= 2:
        collected_files = files[:4]
    else:
        named = [file1, file2, file3, file4]
        if any(f is not None for f in named):
            collected_files = named
        elif files:
            collected_files = files[:4]

    approach_items = []
    for i in range(4):
        curr_file = collected_files[i] if i < len(collected_files) and collected_files[i] is not None else None
        if curr_file is not None:
            content = await curr_file.read()
            fname = curr_file.filename or f"approach_{i+1}.jpg"
            approach_items.append({
                "bytes": content,
                "filename": fname,
                "label": labels[i] if i < len(labels) else f"Approach {i+1}",
            })
        else:
            approach_items.append({
                "filename": f"approach_{i+1}.jpg",
                "label": labels[i] if i < len(labels) else f"Approach {i+1}",
            })

    try:
        result = classifier_service.classify_quad_images(approach_items)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quad comparative classification failed: {str(e)}",
        )


@router.get("/quad-presets")
def get_quad_classifier_presets():
    """List available 4-image comparative traffic scenario presets."""
    return [
        {
            "id": "preset_quad_asymmetric",
            "title": "Asymmetric Rush Hour (Dominant Northbound Queue)",
            "description": "Severe directional imbalance: Approach 1 (North) is heavily backed up (12 vehicles, 78% density) while cross-streets (East/West) are light.",
            "expected_state": "ASYMMETRIC_BOTTLENECK",
            "icon": "⚡",
        },
        {
            "id": "preset_quad_emergency",
            "title": "Emergency Preemption (Ambulance in Southbound Approach)",
            "description": "Approach 2 (South) has an approaching ambulance in traffic, demanding immediate green wave priority corridor.",
            "expected_state": "EMERGENCY_PREEMPTION",
            "icon": "🚨",
        },
        {
            "id": "preset_quad_peak_gridlock",
            "title": "Peak Hour Uniform Gridlock (All 4 Saturated)",
            "description": "High volume and multi-lane queues across all four approaches (> 75% density), requiring maximum cycle splits.",
            "expected_state": "UNIFORM_GRIDLOCK",
            "icon": "🛑",
        },
        {
            "id": "preset_quad_balanced_flow",
            "title": "Off-Peak Balanced Flow (Uniform Moderate Demand)",
            "description": "Evenly distributed light-to-moderate volume (2-4 vehicles per approach, 25% density).",
            "expected_state": "BALANCED_MODERATE",
            "icon": "🟢",
        },
    ]


@router.post("/classify-quad-preset/{preset_id}")
def classify_quad_preset(preset_id: str):
    """Run comparative 4-image classification on a preset scenario."""
    scenario_configs = {
        "preset_quad_asymmetric": [
            ("gridlock", "Approach 1 (North)"),
            ("moderate", "Approach 2 (South)"),
            ("light", "Approach 3 (East)"),
            ("free_flow", "Approach 4 (West)"),
        ],
        "preset_quad_emergency": [
            ("moderate", "Approach 1 (North)"),
            ("emergency", "Approach 2 (South - Ambulance)"),
            ("moderate", "Approach 3 (East)"),
            ("light", "Approach 4 (West)"),
        ],
        "preset_quad_peak_gridlock": [
            ("gridlock", "Approach 1 (North)"),
            ("gridlock", "Approach 2 (South)"),
            ("gridlock", "Approach 3 (East)"),
            ("gridlock", "Approach 4 (West)"),
        ],
        "preset_quad_balanced_flow": [
            ("moderate", "Approach 1 (North)"),
            ("moderate", "Approach 2 (South)"),
            ("moderate", "Approach 3 (East)"),
            ("moderate", "Approach 4 (West)"),
        ],
    }

    cfg = scenario_configs.get(preset_id, scenario_configs["preset_quad_asymmetric"])
    items = []
    for i, (app_type, lbl) in enumerate(cfg):
        img = classifier_service.generate_synthetic_approach_image(approach_type=app_type, label=lbl)
        items.append({
            "image": img,
            "label": lbl,
            "filename": f"preset_{preset_id}_app_{i+1}.jpg",
        })

    return classifier_service.classify_quad_images(items)


@router.get("/presets")
def get_classifier_presets():
    """List available realistic traffic scenario presets for instant 1-click evaluation."""
    return [
        {
            "id": "preset_123_video",
            "title": "123.mp4 — Aerial Drone 4-Way Junction",
            "description": "High-altitude 4-way intersection footage: West queue (10 vehicles) requiring signal extension.",
            "expected_state": "HEAVY",
            "icon": "🚁",
        },
        {
            "id": "preset_free_flow",
            "title": "Arterial Expressway (Free Flow)",
            "description": "Smooth flowing highway corridor with low density (1-2 cars, high speed).",
            "expected_state": "FREE_FLOW",
            "icon": "🟢",
        },
        {
            "id": "preset_moderate",
            "title": "Janpath Urban Junction (Moderate)",
            "description": "Normal city intersection traffic with mixed cars and two-wheelers.",
            "expected_state": "MODERATE",
            "icon": "🟡",
        },
        {
            "id": "preset_gridlock",
            "title": "Peak Hour Bottleneck (Severe Gridlock)",
            "description": "Heavy multi-lane saturation with high queue density and multiple buses/trucks.",
            "expected_state": "GRIDLOCK",
            "icon": "🔴",
        },
        {
            "id": "preset_emergency",
            "title": "Emergency Vehicle Incident (Ambulance in Traffic)",
            "description": "Life-critical ambulance caught in heavy corridor traffic requiring green wave.",
            "expected_state": "EMERGENCY_PRIORITY",
            "icon": "🚨",
        },
    ]


@router.post("/classify-preset/{preset_id}")
def classify_preset(preset_id: str):
    """Run AI classification on one of the built-in traffic scenarios."""
    if preset_id == "preset_123_video":
        candidate_paths = [
            "./videos/123.mp4",
            "backend/videos/123.mp4",
            "../videos/123.mp4",
            "C:/Users/ishan/Downloads/code/backend/videos/123.mp4",
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                return classifier_service.classify_video_file(p, filename="123.mp4")

    img = _generate_preset_image(preset_id)
    _, buffer = cv2.imencode(".jpg", img)
    raw_bytes = buffer.tobytes()

    title_map = {
        "preset_free_flow": "free_flow_arterial.jpg",
        "preset_moderate": "moderate_urban_junction.jpg",
        "preset_gridlock": "severe_gridlock_corridor.jpg",
        "preset_emergency": "ambulance_priority_incident.jpg",
    }
    filename = title_map.get(preset_id, f"{preset_id}.jpg")
    return classifier_service.classify_image(raw_bytes, filename=filename)


def _generate_preset_image(preset_id: str) -> np.ndarray:
    """Renders a realistic traffic scene with roads, lane markings, and vehicle geometries."""
    w, h = 960, 540
    # Asphalt road canvas
    canvas = np.full((h, w, 3), (42, 45, 50), dtype=np.uint8)

    # Road lanes geometry
    road_top = int(h * 0.22)
    road_bottom = int(h * 0.95)
    road_left = int(w * 0.08)
    road_right = int(w * 0.92)

    # Road shoulder & surface
    cv2.rectangle(canvas, (road_left, road_top), (road_right, road_bottom), (55, 58, 65), -1)
    # Side curbs
    cv2.rectangle(canvas, (road_left - 15, road_top), (road_left, road_bottom), (180, 180, 180), -1)
    cv2.rectangle(canvas, (road_right, road_top), (road_right + 15, road_bottom), (180, 180, 180), -1)

    # Lane dividing dashed lines
    lane_y1 = road_top + int((road_bottom - road_top) * 0.33)
    lane_y2 = road_top + int((road_bottom - road_top) * 0.66)

    for ly in (lane_y1, lane_y2):
        for x in range(road_left + 10, road_right - 40, 50):
            cv2.line(canvas, (x, ly), (x + 30, ly), (220, 220, 220), 2)

    # Helper to draw realistic vehicle rectangles
    def draw_vehicle(x, y, vw, vh, color, base_class="car"):
        # Chassis
        cv2.rectangle(canvas, (x, y), (x + vw, y + vh), color, -1)
        # Windows / Windshield
        cv2.rectangle(canvas, (x + int(vw * 0.15), y + int(vh * 0.2)), (x + int(vw * 0.85), y + int(vh * 0.5)), (30, 32, 36), -1)
        # Headlights / Taillights
        cv2.circle(canvas, (x + 4, y + 4), 3, (255, 255, 200), -1)
        cv2.circle(canvas, (x + vw - 4, y + 4), 3, (255, 255, 200), -1)
        cv2.circle(canvas, (x + 4, y + vh - 4), 3, (50, 50, 240), -1)
        cv2.circle(canvas, (x + vw - 4, y + vh - 4), 3, (50, 50, 240), -1)

    def draw_ambulance(x, y, vw, vh):
        # White bodywork
        cv2.rectangle(canvas, (x, y), (x + vw, y + vh), (245, 245, 245), -1)
        # Red lateral emergency reflective stripes
        cv2.rectangle(canvas, (x, y + int(vh * 0.42)), (x + vw, y + int(vh * 0.58)), (35, 35, 220), -1)
        # Red Cross on roof
        cx, cy = x + vw // 2, y + vh // 2
        cv2.rectangle(canvas, (cx - 3, cy - 12), (cx + 3, cy + 12), (20, 20, 220), -1)
        cv2.rectangle(canvas, (cx - 12, cy - 3), (cx + 12, cy + 3), (20, 20, 220), -1)
        # Emergency Lightbar on top (Flashing Red and Blue)
        cv2.rectangle(canvas, (x + int(vw * 0.3), y + 2), (x + int(vw * 0.5), y + 8), (20, 20, 240), -1)
        cv2.rectangle(canvas, (x + int(vw * 0.5), y + 2), (x + int(vw * 0.7), y + 8), (240, 40, 20), -1)

    def draw_motorcycle(x, y):
        # Slim bike chassis
        cv2.rectangle(canvas, (x, y), (x + 22, y + 55), (30, 30, 30), -1)
        # Rider shoulders & helmet (yellow helmet for compliance)
        cv2.circle(canvas, (x + 11, y + 15), 9, (40, 200, 250), -1)

    # Populate vehicles according to scenario
    if preset_id == "preset_free_flow":
        # Just 2 spaced cars moving smoothly
        draw_vehicle(200, 200, 80, 45, (160, 90, 40), "car")
        draw_vehicle(620, 340, 85, 48, (70, 70, 180), "car")

    elif preset_id == "preset_moderate":
        # 4 cars, 2 motorcycles
        draw_vehicle(150, 180, 82, 45, (180, 120, 40), "car")
        draw_vehicle(340, 190, 85, 46, (60, 140, 60), "car")
        draw_vehicle(560, 280, 80, 44, (50, 50, 180), "car")
        draw_vehicle(720, 360, 85, 46, (140, 80, 140), "car")
        draw_motorcycle(280, 270)
        draw_motorcycle(460, 370)

    elif preset_id == "preset_gridlock":
        # 14 vehicles: buses, trucks, dense queue of cars
        draw_vehicle(120, 160, 140, 60, (180, 80, 150), "bus")
        draw_vehicle(280, 165, 80, 44, (60, 60, 180), "car")
        draw_vehicle(380, 165, 82, 45, (160, 140, 40), "car")
        draw_vehicle(480, 160, 130, 55, (150, 110, 80), "truck")
        draw_vehicle(630, 165, 80, 44, (40, 150, 160), "car")
        draw_vehicle(730, 165, 85, 46, (180, 60, 60), "car")

        draw_vehicle(140, 260, 80, 45, (80, 140, 90), "car")
        draw_vehicle(240, 260, 82, 45, (140, 70, 160), "car")
        draw_vehicle(340, 255, 140, 60, (180, 80, 150), "bus")
        draw_vehicle(500, 260, 85, 46, (70, 70, 190), "car")
        draw_vehicle(600, 260, 80, 44, (160, 120, 50), "car")

        draw_motorcycle(110, 360)
        draw_motorcycle(200, 365)
        draw_motorcycle(450, 360)
        draw_vehicle(700, 350, 85, 46, (50, 160, 170), "car")

    elif preset_id == "preset_emergency":
        # Queued cars with an Ambulance requiring urgent corridor preemption
        draw_vehicle(150, 175, 80, 44, (160, 80, 80), "car")
        draw_vehicle(250, 175, 85, 45, (70, 140, 70), "car")
        draw_vehicle(560, 175, 80, 44, (80, 80, 180), "car")

        # The Ambulance
        draw_ambulance(380, 250, 125, 55)

        draw_vehicle(180, 340, 82, 45, (160, 140, 40), "car")
        draw_vehicle(540, 340, 85, 46, (50, 160, 160), "car")
        draw_motorcycle(320, 350)

    # Add environment details (horizon, trees, sky)
    cv2.rectangle(canvas, (0, 0), (w, road_top), (28, 30, 36), -1)
    cv2.rectangle(canvas, (0, road_bottom), (w, h), (24, 26, 30), -1)

    return canvas
