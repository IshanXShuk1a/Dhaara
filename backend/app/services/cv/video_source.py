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

    def open(self) -> None:
        import cv2  # local import: keeps this module importable without cv2 for type-checking tools

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
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> VideoFrame:
        if self._cap is None:
            raise VideoSourceError("read() called before open()")
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
    every frame SourceKind.SIMULATION, so the dashboard can never confuse a
    simulated demo clip with a genuinely live feed."""

    def __init__(self, file_path: str):
        self._delegate = UploadedVideoSource(file_path)

    def open(self) -> None:
        self._delegate.open()

    def is_open(self) -> bool:
        return self._delegate.is_open()

    def read(self) -> VideoFrame:
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

    def close(self) -> None:
        self._delegate.close()
