#!/usr/bin/env bash
# ================================================================
# AYE Vision - Stop Script
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping AYE Vision Platform..."
docker compose down || true
podman stop visionai-frontend visionai-api visionai-mediamtx visionai-redis visionai-postgres visionai-minio visionai-worker visionai-beat 2>/dev/null || true
podman rm -f visionai-frontend visionai-api visionai-mediamtx visionai-redis visionai-postgres visionai-minio visionai-worker visionai-beat 2>/dev/null || true
echo "All services stopped."
