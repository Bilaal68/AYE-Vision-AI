#!/usr/bin/env bash
# ================================================================
# Stream Simulator for AYE Vision / MediaMTX
# ================================================================
set -e

STREAM_TARGET="${1:-cam1}"
SOURCE_TYPE="${2:-test}" # 'test', 'webcam', or a file path like 'video.mp4'
RTSP_URL="rtsp://127.0.0.1:8554/${STREAM_TARGET}"

echo "=================================================="
echo "  AYE Vision Camera Stream Feed"
echo "  Target: ${RTSP_URL}"
echo "  Source: ${SOURCE_TYPE}"
echo "=================================================="

if [ "$SOURCE_TYPE" = "test" ]; then
    echo "Streaming synthetic test pattern over TCP..."
    ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 \
        -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p \
        -rtsp_transport tcp -f rtsp "${RTSP_URL}"
elif [ "$SOURCE_TYPE" = "webcam" ]; then
    DEVICE="${3:-/dev/video0}"
    echo "Streaming local webcam ${DEVICE}..."
    # Use raw YUYV format (640x480 @ 30fps) to eliminate mjpeg decode warnings
    ffmpeg -re -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 -i "${DEVICE}" \
        -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p \
        -rtsp_transport tcp -f rtsp "${RTSP_URL}"
else
    echo "Streaming media file ${SOURCE_TYPE} in loop over TCP..."
    ffmpeg -re -stream_loop -1 -i "${SOURCE_TYPE}" \
        -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p \
        -rtsp_transport tcp -f rtsp "${RTSP_URL}"
fi
