"""
Generates a small synthetic top-down "intersection" video for pipeline
testing. This is NOT a stand-in for real traffic footage in production -
it exists solely so the CV pipeline (video ingestion -> detection overlay
rendering) can be exercised end-to-end in environments without a real
camera. The video content itself is just a static intersection backdrop;
the actual "vehicles" seen by the pipeline come from the SimulationDetector
scenario script, not from image content in this video.
"""
from __future__ import annotations

import cv2
import numpy as np


def generate_intersection_video(output_path: str, width: int = 640, height: int = 480, num_frames: int = 150, fps: float = 25.0) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.full((height, width, 3), (40, 42, 46), dtype=np.uint8)
        cv2.rectangle(frame, (0, height // 2 - 60), (width, height // 2 + 60), (60, 60, 60), -1)
        cv2.rectangle(frame, (width // 2 - 60, 0), (width // 2 + 60, height), (60, 60, 60), -1)
        cv2.putText(frame, f"DHAARA SYNTHETIC TEST FEED - frame {i}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        writer.write(frame)

    writer.release()


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "./videos/sample_intersection.mp4"
    generate_intersection_video(out)
    print(f"Wrote synthetic test video to {out}")
