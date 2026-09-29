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

    def open(self) -> None:
        import cv2  # local import: keeps this module importable without cv2 for type-checking tools

        with self._lock:
            # Candidate path auto-resolution (supports running from root or backend directory)
            candidate_paths = [
                self._path,
                Path("backend") / self._path,
                Path("..") / self._path,
                Path("./videos/123.mp4"),
                Path("backend/videos/123.mp4"),
                Path("../videos/123.mp4"),
                Path("./videos/sample_intersection.mp4"),
                Path("backend/videos/sample_intersection.mp4"),
            ]
            resolved = next((p for p in candidate_paths if p.exists()), None)
            if resolved is not None:
                self._path = resolved

            if not self._path.exists():
                raise VideoSourceError(f"Uploaded video not found: {self._path}")
            cap = cv2.VideoCapture(str(self._path))
            if not cap.isOpened():
                raise VideoSourceError(f"Could not decode video file: {self._path}")
            self._cap = cap
            self._fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            self._width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    def read(self) -> VideoFrame:
        import cv2
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                candidate_paths = [
                    self._path,
                    Path("backend") / self._path,
                    Path("..") / self._path,
                    Path("./videos/123.mp4"),
                    Path("backend/videos/123.mp4"),
                    Path("../videos/123.mp4"),
                    Path("./videos/sample_intersection.mp4"),
                    Path("backend/videos/sample_intersection.mp4"),
                ]
                resolved = next((p for p in candidate_paths if p.exists()), None)
                if resolved is not None:
                    self._path = resolved
                if not self._path.exists():
                    raise VideoSourceError(f"Uploaded video not found: {self._path}")
                cap = cv2.VideoCapture(str(self._path))
                if not cap.isOpened():
                    raise VideoSourceError(f"Could not decode video file: {self._path}")
                self._cap = cap
                self._fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                self._width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self._height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            ok, frame = self._cap.read()
            if not ok:
                # Seamless loop: rewind back to frame 0
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
                if not ok:
                    raise VideoSourceError("End of video file reached")
            self._frame_index += 1
            return VideoFrame(
                image=frame,
                frame_index=self._frame_index,
                timestamp=self._frame_index / self._fps if self._fps else time.time(),
                source_kind=SourceKind.UPLOADED_FILE,
                source_label=str(self._path.name),
                fps=self._fps,
                width=self._width,
                height=self._height,
            )

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
    """Wraps the same file-based decoding as UploadedVideoSource but labels
    every frame SourceKind.SIMULATION, and gracefully falls back to synthetic
    frames if no physical video file is available on disk."""

    def __init__(self, file_path: str):
        self._delegate = UploadedVideoSource(file_path)
        self._synthetic_frame_index = 0

    def open(self) -> None:
        try:
            self._delegate.open()
        except Exception:
            pass

    def is_open(self) -> bool:
        return True

    def read(self) -> VideoFrame:
        try:
            frame = self._delegate.read()
            return VideoFrame(
                image=frame.image,
                frame_index=frame.frame_index,
                timestamp=frame.timestamp,
                source_kind=SourceKind.SIMULATION,
                source_label=frame.source_label,
                fps=frame.fps,
                width=frame.width,
                height=frame.height,
            )
        except Exception:
            import cv2
            self._synthetic_frame_index += 1
            w, h = 1280, 720
            canvas = np.full((h, w, 3), (38, 40, 44), dtype=np.uint8)
            cv2.rectangle(canvas, (0, int(h * 0.25)), (w, int(h * 0.75)), (52, 54, 60), -1)
            cv2.rectangle(canvas, (int(w * 0.25), 0), (int(w * 0.75), h), (52, 54, 60), -1)
            cv2.line(canvas, (0, h // 2), (w, h // 2), (200, 200, 200), 2)
            cv2.line(canvas, (w // 2, 0), (w // 2, h), (200, 200, 200), 2)
            return VideoFrame(
                image=canvas,
                frame_index=self._synthetic_frame_index,
                timestamp=time.time(),
                source_kind=SourceKind.SIMULATION,
                source_label="synthetic_fallback",
                fps=25.0,
                width=w,
                height=h,
            )

    def close(self) -> None:
        try:
            self._delegate.close()
        except Exception:
            pass
