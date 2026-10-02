"""
VideoSource abstraction.

The detection/tracking pipeline consumes frames through this interface and
does not care whether they came from an uploaded file, a webcam, an RTSP
stream, or the simulation engine. Each concrete source yields `VideoFrame`
objects carrying the frame image plus its provenance metadata (fps,
resolution, source label) so the dashboard can honestly label what it is
showing (LIVE vs SIMULATION vs OFFLINE).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Protocol

import numpy as np


class SourceKind(str, Enum):
    UPLOADED_FILE = "UPLOADED_FILE"
    WEBCAM = "WEBCAM"
    RTSP = "RTSP"
    SIMULATION = "SIMULATION"


class VideoSourceError(Exception):
    """Raised for any video-ingestion failure: missing file, bad codec,
    disconnected camera/RTSP stream, or end of stream when a live frame was
    required. Callers must handle this - never silently substitute a blank
    frame while claiming the feed is live."""


@dataclass(frozen=True)
class VideoFrame:
    image: np.ndarray  # BGR, as OpenCV would return it
    frame_index: int
    timestamp: float
    source_kind: SourceKind
    source_label: str
    fps: float
    width: int
    height: int


class VideoSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> VideoFrame: ...
    def is_open(self) -> bool: ...
    def close(self) -> None: ...
    def frames(self) -> Iterator[VideoFrame]: ...


class BaseVideoSource:
    """Shared frame-iteration helper; concrete sources implement open/read/close."""

    def frames(self) -> Iterator[VideoFrame]:
        self.open()
        try:
            while self.is_open():
                yield self.read()
        finally:
            self.close()


class UploadedVideoSource(BaseVideoSource):
    """Reads an uploaded MP4 (or any OpenCV-decodable) file from disk."""

    def __init__(self, file_path: str):
        self._path = Path(file_path)
        self._cap = None
        self._frame_index = 0
        self._fps = 25.0
        self._width = 0
        self._height = 0
        self._lock = threading.Lock()

    def _open_locked(self) -> None:
        import cv2
        # Resolve this configured path only. Never substitute another camera.
        if not self._path.is_absolute():
            self._path = Path(__file__).resolve().parents[3] / self._path
        if not self._path.is_file():
            raise VideoSourceError(f"Uploaded video not found: {self._path}")
        cap = cv2.VideoCapture(str(self._path))
        if not cap.isOpened():
            cap.release()
            raise VideoSourceError(f"Could not decode video file: {self._path}")
        self._cap = cap
        self._fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def open(self) -> None:
        with self._lock:
            if self._cap is None:
                self._open_locked()

    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    def read(self) -> VideoFrame:
        import cv2
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                self._open_locked()
            ok, frame = self._cap.read()
            if not ok:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
                if not ok:
                    raise VideoSourceError("Video cannot produce a frame")
            self._frame_index += 1
            return VideoFrame(frame, self._frame_index, time.time(), SourceKind.UPLOADED_FILE,
                              self._path.name, self._fps, self._width, self._height)

    def close(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None


class WebcamSource(BaseVideoSource):
    """Live local webcam via OpenCV VideoCapture(device_index)."""

    def __init__(self, device_index: int = 0):
        self._device_index = device_index
        self._cap = None
        self._frame_index = 0

    def open(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self._device_index)
        if not cap.isOpened():
            raise VideoSourceError(f"Webcam device {self._device_index} unavailable")
        self._cap = cap

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> VideoFrame:
        if self._cap is None:
            raise VideoSourceError("read() called before open()")
        ok, frame = self._cap.read()
        if not ok:
            raise VideoSourceError("Webcam read failed - camera disconnected?")
        self._frame_index += 1
        fps = self._cap.get(__import__("cv2").CAP_PROP_FPS) or 25.0
        h, w = frame.shape[:2]
        return VideoFrame(
            image=frame,
            frame_index=self._frame_index,
            timestamp=time.time(),
            source_kind=SourceKind.WEBCAM,
            source_label=f"webcam:{self._device_index}",
            fps=fps,
            width=w,
            height=h,
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class RTSPVideoSource(BaseVideoSource):
    """RTSP-ready source. Uses the same OpenCV VideoCapture(url) path as a
    webcam - the pipeline treats it identically. Left as a distinct class so
    reconnect/backoff policy can be specialized for network cameras without
    touching the detection pipeline."""

    def __init__(self, rtsp_url: str, reconnect_attempts: int = 3, reconnect_delay_s: float = 2.0):
        self._url = rtsp_url
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay_s = reconnect_delay_s
        self._cap = None
        self._frame_index = 0

    def open(self) -> None:
        import cv2

        last_error: Exception | None = None
        for attempt in range(1, self._reconnect_attempts + 1):
            cap = cv2.VideoCapture(self._url)
            if cap.isOpened():
                self._cap = cap
                return
            last_error = VideoSourceError(f"RTSP connect attempt {attempt} failed: {self._url}")
            time.sleep(self._reconnect_delay_s)
        raise last_error or VideoSourceError(f"Could not open RTSP stream: {self._url}")

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> VideoFrame:
        if self._cap is None:
            raise VideoSourceError("read() called before open()")
        ok, frame = self._cap.read()
        if not ok:
            raise VideoSourceError("RTSP stream disconnected mid-read")
        self._frame_index += 1
        h, w = frame.shape[:2]
        return VideoFrame(
            image=frame,
            frame_index=self._frame_index,
            timestamp=time.time(),
            source_kind=SourceKind.RTSP,
            source_label=self._url,
            fps=25.0,
            width=w,
            height=h,
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class SimulationVideoSource(BaseVideoSource):
    """Explicit synthetic camera for simulation; never a fallback for real inputs."""

    def __init__(self, direction: str, width: int = 640, height: int = 360):
        self.direction = direction
        self.width, self.height = width, height
        self._frame_index = 0
        self._opened = False

    def open(self) -> None:
        self._opened = True

    def is_open(self) -> bool:
        return self._opened

    def read(self) -> VideoFrame:
        import cv2
        self._frame_index += 1
        canvas = np.full((self.height, self.width, 3), (38, 40, 44), dtype=np.uint8)
        cv2.putText(canvas, f"SIMULATION: {self.direction}", (16, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, .6, (220, 220, 220), 1)
        return VideoFrame(canvas, self._frame_index, time.time(), SourceKind.SIMULATION,
                          self.direction, 25.0, self.width, self.height)

    def close(self) -> None:
        self._opened = False
