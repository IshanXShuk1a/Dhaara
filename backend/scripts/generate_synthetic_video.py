"""Generate four distinct directional test videos; these contain no real vehicles."""
from pathlib import Path
import sys
import cv2
import numpy as np


def generate_camera_video(path, direction, width=640, height=360, num_frames=100, fps=25.):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot write {path}")
    try:
        color = {"EAST": (50,60,90), "WEST": (80,60,50), "NORTH": (50,90,60), "SOUTH": (90,50,80)}[direction]
        for index in range(num_frames):
            image = np.full((height, width, 3), color, np.uint8)
            cv2.putText(image, f"TEST {direction} {index}", (16, 30), cv2.FONT_HERSHEY_SIMPLEX, .7, (220,220,220), 2)
            writer.write(image)
    finally:
        writer.release()


if __name__ == "__main__":
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./videos/test_cameras")
    for direction in ("EAST", "WEST", "NORTH", "SOUTH"):
        path = output_dir / f"{direction.lower()}.mp4"
        generate_camera_video(path, direction)
        print(path)
