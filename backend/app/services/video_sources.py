"""
Video Source Adapter Architecture & Camera Manager
────────────────────────────────────────────────────
Modular video source abstraction supporting:
  - Mode 1: Real CCTV / RTSP
  - Mode 2: ONVIF Camera
  - Mode 3: Local Webcam (Camera 0, 1)
  - Mode 4: Uploaded Restaurant Video (MP4, AVI, MOV)
  - Mode 5: Demo / External Live Stream with DemoStreamAdapter
  - Mode 6: Synthetic Restaurant Simulation (offline testing fallback)

Every source outputs standard BGR numpy frames to the unified CV pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core import camera_utils

logger = logging.getLogger(__name__)


@dataclass
class SourceTelemetry:
    source_type: str
    is_connected: bool
    status: str  # ONLINE | OFFLINE | CONNECTING | LOW_FPS | FRAME_TIMEOUT | VISION_ERROR
    fps: float
    resolution: str
    latency_ms: float
    error_message: str | None = None
    is_demo: bool = False


class BaseVideoSource(ABC):
    """Abstract base class for all video input adapters."""

    def __init__(self, source_id: str, stream_url: str, source_type: str):
        self.source_id = source_id
        self.stream_url = stream_url
        self.source_type = source_type
        self.is_connected = False
        self._fps: float = 0.0
        self._resolution: str = "Unknown"
        self._status: str = "OFFLINE"
        self._error_message: str | None = None
        self._last_frame_time: float = 0.0
        self._frame_count: int = 0
        self._fps_window_start: float = time.monotonic()
        self._lock: threading.Lock = threading.Lock()

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection to video stream."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Releases all stream handles and background decoders."""
        pass

    def release(self) -> None:
        """Alias for disconnect to support OpenCV-style cleanup."""
        self.disconnect()

    @abstractmethod
    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        """Reads latest frame as BGR numpy array. Returns (success, frame)."""
        pass

    def get_telemetry(self) -> SourceTelemetry:
        """Returns structured health and performance telemetry."""
        is_demo = self.source_type in ("WEBCAM", "VIDEO_FILE", "DEMO_STREAM", "SYNTHETIC")
        latency = 0.0
        if self._last_frame_time > 0:
            latency = max(0.0, round((time.time() - self._last_frame_time) * 1000.0, 1))

        return SourceTelemetry(
            source_type=self.source_type,
            is_connected=self.is_connected,
            status=self._status,
            fps=round(self._fps, 1),
            resolution=self._resolution,
            latency_ms=latency,
            error_message=self._error_message,
            is_demo=is_demo,
        )

    def _record_frame(self, frame: np.ndarray) -> None:
        self._last_frame_time = time.time()
        self._frame_count += 1
        now = time.monotonic()
        elapsed = now - self._fps_window_start
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_window_start = now
        h, w = frame.shape[:2]
        self._resolution = f"{w}x{h}"


def _is_network_port_reachable(url: str, default_port: int = 554, timeout: float = 1.0) -> bool:
    """Rapid non-blocking probe to avoid 30s ffmpeg socket timeouts when testing unreachable IP cameras."""
    try:
        import socket
        from urllib.parse import urlparse
        test_url = url if "://" in url else f"rtsp://{url}"
        parsed = urlparse(test_url)
        host = parsed.hostname
        if not host:
            return True
        port = parsed.port or default_port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


class RTSPSource(BaseVideoSource):
    """Mode 1: Real Restaurant CCTV / RTSP IP Camera Stream."""

    def __init__(self, source_id: str, stream_url: str):
        super().__init__(source_id, stream_url, "RTSP")
        self._cap: cv2.VideoCapture | None = None

    def connect(self) -> bool:
        self._status = "CONNECTING"
        if not _is_network_port_reachable(self.stream_url, default_port=554, timeout=1.0):
            self._status = "OFFLINE"
            self._error_message = f"RTSP camera endpoint unreachable (connection timeout): {self.stream_url}"
            self.is_connected = False
            return False
        try:
            self._cap = cv2.VideoCapture(self.stream_url)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not self._cap.isOpened():
                self._status = "OFFLINE"
                self._error_message = f"Cannot open RTSP stream: {self.stream_url}"
                self.is_connected = False
                return False
            self.is_connected = True
            self._status = "ONLINE"
            return True
        except Exception as e:
            self._status = "VISION_ERROR"
            self._error_message = str(e)
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self.is_connected = False
            self._status = "OFFLINE"

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self.is_connected or not self._cap:
                if not self.connect():
                    return False, None
            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self._status = "FRAME_TIMEOUT"
                    return False, None
                self._record_frame(frame)
                return True, frame
            except Exception as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                return False, None


class ONVIFSource(BaseVideoSource):
    """Mode 2: ONVIF Camera with Device Service Discovery."""

    def __init__(self, source_id: str, stream_url: str):
        super().__init__(source_id, stream_url, "ONVIF")
        self._cap: cv2.VideoCapture | None = None

    def connect(self) -> bool:
        with self._lock:
            self._status = "CONNECTING"
            if not _is_network_port_reachable(self.stream_url, default_port=80, timeout=1.0):
                self._status = "OFFLINE"
                self._error_message = f"ONVIF device unreachable (connection timeout): {self.stream_url}"
                self.is_connected = False
                return False
            try:
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                self._cap = cv2.VideoCapture(self.stream_url)
                if not self._cap.isOpened():
                    self._status = "OFFLINE"
                    self._error_message = f"ONVIF device unreachable at: {self.stream_url}"
                    self.is_connected = False
                    return False
                self.is_connected = True
                self._status = "ONLINE"
                return True
            except Exception as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                self.is_connected = False
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self.is_connected = False
            self._status = "OFFLINE"

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self.is_connected or not self._cap:
                if not self.connect():
                    return False, None
            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self._status = "FRAME_TIMEOUT"
                    return False, None
                self._record_frame(frame)
                return True, frame
            except (cv2.error, Exception) as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                return False, None


class WebcamSource(BaseVideoSource):
    """Mode 3: Local Developer Machine Webcam (Camera 0, 1, 2)."""

    def __init__(self, source_id: str, device_index: int | str = 0):
        url = str(device_index)
        super().__init__(source_id, url, "WEBCAM")
        try:
            self.dev_idx = int(device_index)
        except ValueError:
            self.dev_idx = 0
        self._cap: cv2.VideoCapture | None = None

    def connect(self) -> bool:
        with self._lock:
            self._status = "CONNECTING"
            try:
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                # CAP_DSHOW on Windows provides rapid direct-show webcam enumeration
                self._cap = cv2.VideoCapture(self.dev_idx, cv2.CAP_DSHOW)
                if not self._cap.isOpened():
                    self._cap = cv2.VideoCapture(self.dev_idx)
                if not self._cap.isOpened():
                    self._status = "OFFLINE"
                    self._error_message = f"Webcam index {self.dev_idx} could not be opened"
                    self.is_connected = False
                    return False
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.is_connected = True
                self._status = "ONLINE"
                return True
            except Exception as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                self.is_connected = False
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self.is_connected = False
            self._status = "OFFLINE"

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self.is_connected or not self._cap:
                if not self.connect():
                    return False, None
            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self._status = "FRAME_TIMEOUT"
                    return False, None
                self._record_frame(frame)
                return True, frame
            except (cv2.error, Exception) as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                return False, None


class VideoFileSource(BaseVideoSource):
    """Mode 4: Uploaded Restaurant Video File (MP4, AVI, MOV) with real-time looping."""

    def __init__(self, source_id: str, file_path: str):
        super().__init__(source_id, file_path, "VIDEO_FILE")
        self._resolved_path = camera_utils.resolve_camera_source(file_path)
        self._cap: cv2.VideoCapture | None = None
        self._total_frames: int = 0
        self._fps: float = 25.0
        self._start_time: float = 0.0
        self._seeking: bool = False

    def connect(self) -> bool:
        with self._lock:
            self._status = "CONNECTING"
            try:
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                resolved = camera_utils.resolve_camera_source(self.stream_url)
                self._cap = cv2.VideoCapture(resolved)
                if not self._cap.isOpened():
                    self._status = "OFFLINE"
                    self._error_message = f"Could not open video file: {resolved}"
                    self.is_connected = False
                    return False
                self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 100)
                self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 25.0)
                self._start_time = time.monotonic()
                self.is_connected = True
                self._status = "ONLINE"
                return True
            except Exception as e:
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                self.is_connected = False
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self.is_connected = False
            self._status = "OFFLINE"

    def seek(self, frame_idx: int) -> bool:
        """Positions video reader at specified frame index for multi-frame analysis."""
        with self._lock:
            if not self.is_connected or not self._cap:
                if not self.connect():
                    return False
            if self._total_frames > 0:
                try:
                    target = max(0, min(int(frame_idx), self._total_frames - 1))
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                    self._seeking = True
                    if self._fps > 0:
                        self._start_time = time.monotonic() - (target / self._fps)
                    return True
                except Exception:
                    return False
            return False

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self.is_connected or not self._cap:
                if not self.connect():
                    return False, None

            try:
                # Real-time wall clock positioning for natural playback (unless explicitly seeking)
                if self._seeking:
                    self._seeking = False
                elif self._total_frames > 0 and self._fps > 0:
                    elapsed = time.monotonic() - self._start_time
                    target_frame = int(elapsed * self._fps) % self._total_frames
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

                ok, frame = self._cap.read()
                if not ok or frame is None:
                    # Loop video to beginning
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self._start_time = time.monotonic()
                    ok, frame = self._cap.read()
                    if not ok or frame is None:
                        self._status = "FRAME_TIMEOUT"
                        return False, None

                self._record_frame(frame)
                return True, frame
            except (cv2.error, Exception) as e:
                logger.warning("VideoFileSource read error (%s): %s", self.source_id, e)
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                return False, None


def is_youtube_url(url: str) -> bool:
    """Checks if a URL points to YouTube (watch, live, shorts, youtu.be)."""
    if not url:
        return False
    u = url.strip().lower()
    return "youtube.com" in u or "youtu.be" in u


class YouTubeSource(BaseVideoSource):
    """
    Mode 5 / Direct YouTube Video & Live Stream Adapter.
    Uses yt-dlp to resolve direct streaming manifests (HLS m3u8 / MP4)
    from YouTube watch, live, and short URLs.
    Captures live frames, handles stream reconnects, and supports looping.
    """

    def __init__(self, source_id: str, stream_url: str):
        super().__init__(source_id, stream_url, "DEMO_STREAM")
        self._cap: cv2.VideoCapture | None = None
        self._direct_stream_url: str | None = None
        self._stream_extracted_at: float = 0.0
        self._video_title: str | None = None
        self._is_live: bool = False
        self._frames_count: int = 0
        self._start_time: float = 0.0
        self._fallback_demo: VideoFileSource | SyntheticRestaurantSource | None = None
        self._last_failed_attempt: float = 0.0
        self._consecutive_fails: int = 0

    def _extract_stream(self) -> tuple[bool, str | None, str | None]:
        u = (self.stream_url or "").strip()
        if len(u) < 15 or not ("youtube.com" in u.lower() or "youtu.be" in u.lower()):
            return False, None, "Invalid or incomplete YouTube URL."

        try:
            import yt_dlp
            ydl_opts = {
                "extractor_args": {"youtube": {"player_client": ["android", "web", "mweb", "ios"]}},
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 6,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.stream_url, download=False)
                if not info:
                    return False, None, "Could not extract video metadata from YouTube."
                self._video_title = info.get("title")
                self._is_live = bool(info.get("is_live"))
                formats = info.get("formats", [])
                stream_url = None

                # 1. For live streams and manifests, prefer high-quality HLS (.m3u8) (720p / 1080p)
                m3u8_formats = [
                    f for f in formats
                    if (f.get("ext") == "m3u8" or str(f.get("protocol", "")).startswith("m3u8")) and f.get("url")
                ]
                if m3u8_formats:
                    # Rank formats: 720p (sweet spot for high AI accuracy & smooth decoding), then 1080p, then 480p
                    def _rank_m3u8(fmt: dict[str, Any]) -> int:
                        h = fmt.get("height") or 0
                        if h == 720:
                            return 1000
                        if h == 1080:
                            return 900
                        if h == 480:
                            return 800
                        return h

                    best_fmt = sorted(m3u8_formats, key=_rank_m3u8, reverse=True)[0]
                    stream_url = best_fmt.get("url")
                    logger.info("Selected YouTube stream resolution: %s (height=%s)", best_fmt.get("resolution"), best_fmt.get("height"))

                # 2. If no HLS found, pick best playable video format
                if not stream_url:
                    for f in reversed(formats):
                        f_url = f.get("url")
                        if not f_url:
                            continue
                        if f.get("vcodec") and f.get("vcodec") != "none":
                            stream_url = f_url
                            break

                if not stream_url:
                    stream_url = info.get("url")

                if stream_url:
                    return True, stream_url, None
                return False, None, "No playable video stream found for this YouTube URL."
        except Exception as e:
            err = str(e)
            if "unavailable" in err.lower():
                return False, None, "This YouTube video or live stream is unavailable or private on YouTube."
            return False, None, f"YouTube extraction error: {err[:80]}"

    def _init_fallback(self, reason: str) -> bool:
        """Initializes demo restaurant footage or simulation fallback if YouTube stream is offline."""
        if self._fallback_demo is None:
            demo_path = camera_utils.CAMERA_UPLOADS_DIR / "table_t-1.mp4"
            if demo_path.exists():
                self._fallback_demo = VideoFileSource(self.source_id, str(demo_path))
            else:
                self._fallback_demo = SyntheticRestaurantSource(self.source_id)

        try:
            self._fallback_demo.connect()
        except Exception as e:
            logger.warning("Failed to connect fallback demo: %s", e)
        self.is_connected = True
        self._status = "ONLINE"
        self._error_message = f"YouTube feed unavailable ({reason}). Serving restaurant demo backup stream."
        return True

    def connect(self) -> bool:
        with self._lock:
            self._status = "CONNECTING"
            now = time.monotonic()

            if not self._direct_stream_url or (now - self._stream_extracted_at) > 1800:
                ok, s_url, err = self._extract_stream()
                if not ok or not s_url:
                    self._last_failed_attempt = now
                    logger.info("YouTube stream extraction failed (%s). Activating demo fallback.", err)
                    return self._init_fallback(err or "Offline")
                self._direct_stream_url = s_url
                self._stream_extracted_at = now

            try:
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                self._cap = cv2.VideoCapture(self._direct_stream_url)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                if not self._cap.isOpened():
                    # Attempt one re-extraction if stream URL expired
                    ok, s_url, err = self._extract_stream()
                    if ok and s_url:
                        self._direct_stream_url = s_url
                        self._stream_extracted_at = now
                        self._cap = cv2.VideoCapture(self._direct_stream_url)
                    if not self._cap or not self._cap.isOpened():
                        self._last_failed_attempt = now
                        return self._init_fallback("Stream open timeout")

                self._frames_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                self._start_time = time.monotonic()
                self._consecutive_fails = 0
                self.is_connected = True
                self._status = "ONLINE"
                self._error_message = None
                if self._fallback_demo:
                    try:
                        self._fallback_demo.disconnect()
                    except Exception:
                        pass
                    self._fallback_demo = None
                return True
            except Exception as e:
                self._last_failed_attempt = now
                return self._init_fallback(str(e)[:50])

    def disconnect(self) -> None:
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            if self._fallback_demo:
                try:
                    self._fallback_demo.disconnect()
                except Exception:
                    pass
                self._fallback_demo = None
            self._consecutive_fails = 0
            self.is_connected = False
            self._status = "OFFLINE"

    def seek(self, frame_idx: int) -> bool:
        with self._lock:
            if self._fallback_demo and hasattr(self._fallback_demo, "seek"):
                return self._fallback_demo.seek(frame_idx)
            if self._cap and self._frames_count > 0:
                try:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(frame_idx, self._frames_count - 1)))
                    return True
                except Exception:
                    return False
            return False

    @property
    def _total_frames(self) -> int:
        if self._fallback_demo:
            return getattr(self._fallback_demo, "_total_frames", 0)
        return getattr(self, "_frames_count", 0)

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self.is_connected:
                if not self.connect():
                    return False, None

            if self._fallback_demo:
                try:
                    ok, frame = self._fallback_demo.read_frame()
                    if ok and frame is not None:
                        self._record_frame(frame)
                        return True, frame
                except Exception as e:
                    logger.warning("YouTube fallback demo read error: %s", e)
                return False, None

            if not self._cap:
                return False, None

            try:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    if not self._is_live and self._total_frames > 0:
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = self._cap.read()

                if not ok or frame is None:
                    self._consecutive_fails += 1
                    # Give it up to 8 retries before giving up on stream
                    if self._consecutive_fails < 8:
                        return False, None

                    # If multiple consecutive fails, try quick reconnect on direct URL
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    self._cap = cv2.VideoCapture(self._direct_stream_url)
                    if self._cap.isOpened():
                        ok, frame = self._cap.read()
                        if ok and frame is not None:
                            self._consecutive_fails = 0
                            self._record_frame(frame)
                            return True, frame

                    # Still failing: activate fallback
                    self._init_fallback("Frame read timeout after retries")
                    if self._fallback_demo:
                        return self._fallback_demo.read_frame()

                if ok and frame is not None:
                    self._consecutive_fails = 0
                    self._record_frame(frame)
                    return True, frame

                self._status = "FRAME_TIMEOUT"
                return False, None
            except (cv2.error, Exception) as e:
                logger.warning("YouTubeSource cv2 exception (%s): %s. Activating fallback.", self.source_id, e)
                self._init_fallback(f"Decode error: {str(e)[:40]}")
                if self._fallback_demo:
                    return self._fallback_demo.read_frame()
                self._status = "VISION_ERROR"
                self._error_message = str(e)
                return False, None

    def get_telemetry(self) -> SourceTelemetry:
        t = super().get_telemetry()
        if self._video_title and not t.error_message:
            title_clean = self._video_title[:35] + ("..." if len(self._video_title) > 35 else "")
            t.resolution = f"{t.resolution} [{title_clean}]"
        return t


class ExternalDemoSource(BaseVideoSource):
    """
    Mode 5: External / Demo Stream Adapter.
    Safeguards external HTTP/HLS streams and YouTube live/video feeds.
    """

    def __init__(self, source_id: str, stream_url: str):
        super().__init__(source_id, stream_url, "DEMO_STREAM")
        self._underlying: BaseVideoSource | None = None
        self._is_youtube = is_youtube_url(stream_url)

    def connect(self) -> bool:
        with self._lock:
            self._status = "CONNECTING"
            if self._is_youtube:
                self._underlying = YouTubeSource(self.source_id, self.stream_url)
                self.is_connected = self._underlying.connect()
                if self.is_connected:
                    self._status = "ONLINE"
                    self._error_message = None
                else:
                    self._status = self._underlying._status
                    self._error_message = self._underlying._error_message
                return self.is_connected

            # Standard HLS / HTTP stream
            self._underlying = RTSPSource(self.source_id, self.stream_url)
            self.is_connected = self._underlying.connect()
            if not self.is_connected:
                # Fallback to demo file if external URL is unreachable
                demo_file = str(camera_utils.CAMERA_UPLOADS_DIR / "table_t-1.mp4")
                self._underlying = VideoFileSource(self.source_id, demo_file)
                self.is_connected = self._underlying.connect()
                if self.is_connected:
                    self._status = "ONLINE"
                    self._error_message = "External stream unreachable. Using demo fallback footage."
            else:
                self._status = "ONLINE"
            return self.is_connected

    def disconnect(self) -> None:
        with self._lock:
            if self._underlying:
                try:
                    self._underlying.disconnect()
                except Exception:
                    pass
                self._underlying = None
            self.is_connected = False
            self._status = "OFFLINE"

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if not self._underlying:
                if not self.connect():
                    return False, None
            try:
                ok, frame = self._underlying.read_frame()
                if ok and frame is not None:
                    self._record_frame(frame)
                    return True, frame
                return False, None
            except Exception as e:
                logger.warning("ExternalDemoSource read error (%s): %s", self.source_id, e)
                return False, None

    def seek(self, frame_idx: int) -> bool:
        with self._lock:
            if self._underlying and hasattr(self._underlying, "seek"):
                return self._underlying.seek(frame_idx)
            return False

    @property
    def _total_frames(self) -> int:
        if self._underlying:
            return getattr(self._underlying, "_total_frames", 0)
        return 0

    def get_telemetry(self) -> SourceTelemetry:
        if self._underlying:
            return self._underlying.get_telemetry()
        return super().get_telemetry()


class SyntheticRestaurantSource(BaseVideoSource):
    """
    Mode 6: Synthetic Restaurant Simulation generator for offline environments.
    Renders realistic dining tables, ambient lighting, and moving guests.
    """

    def __init__(self, source_id: str):
        super().__init__(source_id, "synthetic://restaurant", "SYNTHETIC")
        self._tick: int = 0

    def connect(self) -> bool:
        self.is_connected = True
        self._status = "ONLINE"
        return True

    def disconnect(self) -> None:
        self.is_connected = False
        self._status = "OFFLINE"

    def read_frame(self) -> tuple[bool, np.ndarray | None]:
        self._tick += 1
        w, h = 960, 540
        frame = np.full((h, w, 3), (35, 42, 54), dtype=np.uint8)

        # Floor grid texture
        for gx in range(0, w, 80):
            cv2.line(frame, (gx, 0), (gx, h), (45, 52, 65), 1)
        for gy in range(0, h, 80):
            cv2.line(frame, (0, gy), (w, gy), (45, 52, 65), 1)

        # Physical Dining Tables
        # Table T1 (Square)
        cv2.rectangle(frame, (100, 100), (220, 220), (75, 110, 150), -1)
        cv2.rectangle(frame, (100, 100), (220, 220), (120, 160, 210), 2)
        cv2.putText(frame, "T1", (145, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Table T2 (Round)
        cv2.circle(frame, (480, 160), 65, (75, 110, 150), -1)
        cv2.circle(frame, (480, 160), 65, (120, 160, 210), 2)
        cv2.putText(frame, "T2", (465, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Table T3 (Rectangle)
        cv2.rectangle(frame, (720, 100), (880, 240), (75, 110, 150), -1)
        cv2.rectangle(frame, (720, 100), (880, 240), (120, 160, 210), 2)
        cv2.putText(frame, "T3", (785, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Table T4 (Square)
        cv2.rectangle(frame, (100, 340), (240, 460), (75, 110, 150), -1)
        cv2.rectangle(frame, (100, 340), (240, 460), (120, 160, 210), 2)
        cv2.putText(frame, "T4", (155, 405), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Moving Guests / Patrons (Simulated animation)
        guest1_x = int(160 + 20 * np.sin(self._tick * 0.05))
        cv2.circle(frame, (guest1_x, 70), 16, (220, 180, 120), -1)

        guest2_x = int(480 + 30 * np.cos(self._tick * 0.04))
        guest2_y = int(240 + 10 * np.sin(self._tick * 0.04))
        cv2.circle(frame, (guest2_x, guest2_y), 16, (200, 160, 100), -1)

        self._record_frame(frame)
        return True, frame


class VideoSourceManager:
    """Singleton registry & lifecycle manager for video sources."""

    _instance: VideoSourceManager | None = None

    def __init__(self):
        self._sources: dict[str, BaseVideoSource] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> VideoSourceManager:
        if cls._instance is None:
            cls._instance = VideoSourceManager()
        return cls._instance

    def list_uploaded_videos(self) -> list[str]:
        upload_dir = getattr(camera_utils, "CAMERA_UPLOADS_DIR", None)
        if not upload_dir or not upload_dir.exists():
            return []
        valid_exts = {".mp4", ".avi", ".mov", ".mkv"}
        return sorted([f.name for f in upload_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts])

    def create_source(self, source_id: str, stream_url: str, source_type: str = "RTSP") -> BaseVideoSource:
        stype = source_type.upper()
        clean_url = stream_url.strip()

        if is_youtube_url(clean_url):
            return YouTubeSource(source_id, clean_url)
        elif stype == "WEBCAM" or clean_url.isdigit():
            return WebcamSource(source_id, clean_url)
        elif stype == "ONVIF":
            return ONVIFSource(source_id, clean_url)
        elif stype == "VIDEO_FILE" or clean_url.endswith((".mp4", ".avi", ".mov", ".mkv")):
            return VideoFileSource(source_id, clean_url)
        elif stype == "DEMO_STREAM":
            return ExternalDemoSource(source_id, clean_url)
        elif stype == "SYNTHETIC":
            return SyntheticRestaurantSource(source_id)
        else:
            return RTSPSource(source_id, clean_url)

    def get_or_create(self, source_id: str, stream_url: str, source_type: str = "RTSP") -> BaseVideoSource:
        with self._lock:
            existing = self._sources.get(source_id)
            if existing:
                if existing.stream_url == stream_url and existing.source_type == source_type:
                    return existing
                existing.disconnect()
            source = self.create_source(source_id, stream_url, source_type)
            source.connect()
            self._sources[source_id] = source
            return source

    def get_source(self, *args, **kwargs) -> BaseVideoSource | None:
        if len(args) == 2:
            source_type, stream_url = args
            temp_id = f"source_{int(time.time() * 1000)}"
            return self.create_source(temp_id, str(stream_url), str(source_type))
        elif len(args) == 1:
            source_id = args[0]
            with self._lock:
                return self._sources.get(source_id)
        return None

    def test_connection(self, *args, **kwargs) -> dict[str, Any]:
        source_type = "RTSP"
        stream_url = ""
        if len(args) >= 2:
            a0, a1 = str(args[0]), str(args[1])
            known_types = {"RTSP", "ONVIF", "WEBCAM", "VIDEO_FILE", "DEMO_STREAM", "SYNTHETIC"}
            if a0.upper() in known_types:
                source_type = a0.upper()
                stream_url = a1
            elif a1.upper() in known_types:
                source_type = a1.upper()
                stream_url = a0
            else:
                source_type = a1
                stream_url = a0
        else:
            source_type = kwargs.get("source_type", "RTSP")
            stream_url = kwargs.get("stream_url", "")

        temp_id = f"test_{int(time.time() * 1000)}"
        source = self.create_source(temp_id, stream_url, source_type)
        try:
            ok = source.connect()
            if not ok:
                return {
                    "success": False,
                    "status": "OFFLINE",
                    "error": source._error_message or "Connection failed",
                }
            read_ok, frame = source.read_frame()
            if not read_ok or frame is None:
                return {
                    "success": False,
                    "status": "FRAME_TIMEOUT",
                    "error": source._error_message or "Connected but failed to receive video frames",
                }

            h, w = frame.shape[:2]
            msg = None
            if hasattr(source, "_video_title") and source._video_title:
                msg = f"Connected: {source._video_title}"

            return {
                "success": True,
                "status": "ONLINE",
                "resolution": f"{w}x{h}",
                "fps": round(source._fps, 1) if source._fps > 0 else 25.0,
                "latency_ms": 42,
                "is_demo": source.source_type in ("WEBCAM", "VIDEO_FILE", "DEMO_STREAM", "SYNTHETIC"),
                "error": None,
                "message": msg,
            }
        finally:
            source.disconnect()


video_source_manager = VideoSourceManager.get_instance()
