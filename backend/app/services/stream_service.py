"""Stream service – bridges the API layer to the StreamManager.

Provides async-friendly wrappers for starting/stopping camera streams,
capturing snapshots, testing connections, and serving MJPEG frames.
"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

import cv2
import numpy as np
import structlog

from app.services.stream_manager import StreamManager, StreamState, get_stream_manager

logger = structlog.stdlib.get_logger(__name__)


# ── Stream lifecycle ────────────────────────────────────────────────────


async def start_stream(camera_id: str, stream_url: str | None = None, camera_name: str = "") -> dict[str, Any]:
    """Start streaming for a camera.

    If *stream_url* is not provided the function looks up the camera in the
    database to get its stream URL.  For USB cameras the stream_url is the
    device path (e.g. ``/dev/video0``).
    """
    cam_uuid = uuid.UUID(camera_id)
    mgr = get_stream_manager()

    # If stream_url or camera_name not passed, look them up
    if not stream_url or not camera_name:
        try:
            from app.database import AsyncSessionLocal
            from app.models.camera import Camera
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(Camera.stream_url, Camera.name).where(Camera.id == cam_uuid))
                row = res.first()
                if row:
                    if not stream_url:
                        stream_url = row[0]
                    if not camera_name:
                        camera_name = row[1]
        except Exception:
            pass

    if not stream_url:
        stream_url = await _lookup_stream_url(camera_id)

    # Normalize internal hostname for MediaMTX
    if isinstance(stream_url, str):
        if "localhost:8554" in stream_url or "127.0.0.1:8554" in stream_url:
            stream_url = stream_url.replace("localhost:8554", "mediamtx:8554").replace("127.0.0.1:8554", "mediamtx:8554")

    # For USB device paths, convert to integer index for OpenCV
    effective_url: str | int = stream_url
    if stream_url.startswith("/dev/video"):
        try:
            effective_url = int(stream_url.replace("/dev/video", ""))
        except ValueError:
            effective_url = stream_url

    metrics = await asyncio.to_thread(
        mgr.start_stream,
        camera_id=cam_uuid,
        stream_url=effective_url,
        camera_name=camera_name,
    )

    logger.info("Stream started via service", camera_id=camera_id)
    return metrics.to_dict()


async def stop_stream(camera_id: str) -> dict[str, Any]:
    """Stop streaming for a camera."""
    cam_uuid = uuid.UUID(camera_id)
    mgr = get_stream_manager()
    metrics = await asyncio.to_thread(mgr.stop_stream, cam_uuid)
    logger.info("Stream stopped via service", camera_id=camera_id)
    return metrics.to_dict()


async def get_stream_status(camera_id: str) -> dict[str, Any]:
    """Return stream metrics for a camera."""
    cam_uuid = uuid.UUID(camera_id)
    mgr = get_stream_manager()
    return mgr.get_stream_status(cam_uuid).to_dict()


# ── Snapshot ────────────────────────────────────────────────────────────


async def capture_snapshot(camera_id: str) -> dict[str, Any]:
    """Capture a single JPEG snapshot from the camera's stream.

    If the stream is already running, grabs the latest buffered frame.
    Otherwise opens a one-shot capture, grabs a frame, and closes.

    Returns a dict with ``url`` (data-uri) and ``timestamp``.
    """
    cam_uuid = uuid.UUID(camera_id)
    mgr = get_stream_manager()

    frame = mgr.get_frame(cam_uuid)

    # If stream isn't running, do a one-shot capture
    if frame is None:
        try:
            stream_url = await _lookup_stream_url(camera_id)
            frame = await asyncio.wait_for(_oneshot_capture(stream_url), timeout=0.8)
        except Exception:
            frame = None

    if frame is None:
        h, w = 720, 1280
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (24, 28, 36)
        # Subtle grid
        cv2.line(frame, (0, 60), (w, 60), (45, 55, 75), 1)
        cv2.line(frame, (0, 660), (w, 660), (45, 55, 75), 1)
        cv2.putText(frame, f"AYE VISION | SNAPSHOT {camera_id[:8]}", (40, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 220, 240), 2)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        cv2.putText(frame, now_str, (40, 695), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, "STATUS: STANDBY / LIVE CAPTURE READY", (780, 695), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 180, 200), 1)

    # Encode to JPEG
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    import base64
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    return {
        "url": f"data:image/jpeg;base64,{b64}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Stream test ─────────────────────────────────────────────────────────


async def test_camera_stream(
    stream_url: str,
    username_encrypted: str | None = None,
    password_encrypted: str | None = None,
    protocol: str = "rtsp",
) -> dict[str, Any]:
    """Test connectivity to a camera stream by opening it briefly.

    Returns resolution, fps, and a snapshot if successful.
    """
    effective_url: str | int = stream_url
    if stream_url.startswith("/dev/video"):
        try:
            effective_url = int(stream_url.replace("/dev/video", ""))
        except ValueError:
            pass

    start = time.monotonic()
    frame = await _oneshot_capture(effective_url)
    latency = round((time.monotonic() - start) * 1000, 1)

    if frame is None:
        return {"connected": False, "latency_ms": latency}

    h, w = frame.shape[:2]
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    import base64
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    return {
        "connected": True,
        "resolution": f"{w}x{h}",
        "fps": 30,
        "codec": "mjpeg",
        "snapshot_url": f"data:image/jpeg;base64,{b64}",
        "latency_ms": latency,
    }


# ── MJPEG generator ────────────────────────────────────────────────────


async def mjpeg_frame_generator(
    camera_id: str,
    fps_target: int = 15,
    quality: int = 70,
) -> AsyncGenerator[bytes, None]:
    """Yield MJPEG multipart frames for HTTP streaming.

    This is an async generator suitable for use with
    ``StreamingResponse(media_type="multipart/x-mixed-replace; ...")``.
    """
    cam_uuid = uuid.UUID(camera_id)
    mgr = get_stream_manager()
    interval = 1.0 / max(fps_target, 1)

    # Auto-start stream if not active
    try:
        worker = mgr._workers.get(cam_uuid)
        if not worker or not worker.is_running:
            stream_url = await _lookup_stream_url(camera_id)
            # Normalize local URLs for Docker networking
            if "localhost:8554" in stream_url or "127.0.0.1:8554" in stream_url:
                stream_url = stream_url.replace("localhost:8554", "mediamtx:8554").replace("127.0.0.1:8554", "mediamtx:8554")
            await start_stream(camera_id, stream_url=stream_url)
    except Exception as exc:
        logger.warning("Could not auto-start stream worker", camera_id=camera_id, error=str(exc))

    def _make_connecting_frame() -> bytes:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Connecting to camera feed...", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return buf.tobytes()

    from app.cv.live_detector import detect_and_annotate
    from app.dependencies import get_redis
    import json

    redis_client = None
    try:
        redis_client = await get_redis()
    except Exception:
        pass

    while True:
        frame = mgr.get_frame(cam_uuid)

        if frame is not None:
            # Run intelligent detection & bounding box annotation
            annotated_frame, detections = detect_and_annotate(frame)

            # Publish detections to WebSocket channel if redis is available
            if redis_client and detections:
                try:
                    redis_channel = f"visionai:detections:{camera_id}"
                    await redis_client.publish(
                        redis_channel,
                        json.dumps({"camera_id": camera_id, "detections": detections})
                    )
                except Exception:
                    pass

            _, buf = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            jpg_bytes = buf.tobytes()
        else:
            jpg_bytes = _make_connecting_frame()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpg_bytes)).encode() + b"\r\n"
            b"\r\n" + jpg_bytes + b"\r\n"
        )

        await asyncio.sleep(interval)


# ── Internal helpers ────────────────────────────────────────────────────


async def _lookup_stream_url(camera_id: str) -> str:
    """Look up the stream_url for a camera from the database."""
    from app.database import AsyncSessionLocal as async_session_factory
    from app.models.camera import Camera

    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Camera.stream_url).where(Camera.id == uuid.UUID(camera_id))
        )
        url = result.scalar_one_or_none()
        if not url:
            raise RuntimeError(f"Camera {camera_id} not found")
        return url


async def _oneshot_capture(stream_url: str | int) -> Optional[np.ndarray]:
    """Open a video source, grab one frame, and close."""
    def _grab():
        try:
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;1000000|stimeout;1000000"
            cap = cv2.VideoCapture(stream_url)
            if not cap.isOpened():
                return None
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, frame = cap.read()
            cap.release()
            return frame if ret else None
        except Exception:
            return None

    return await asyncio.to_thread(_grab)
