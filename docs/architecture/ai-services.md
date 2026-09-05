# AI and service layout

Computer vision is **not** a second HTTP API in this foundation.

```
ai/
  vision/              OpenCV helpers (empty)
  face_recognition/    future experiments
  vehicle_detection/
  plate_recognition/
  event_detection/
  models/              weights go here, gitignored patterns in .gitignore
```

Django will import these through:

```
backend/services/vision/
backend/services/face_recognition/
backend/services/plate_recognition/
backend/services/satellite/
backend/services/correlation/
backend/services/notifications/
```

**Rule:** keep model inference out of request/response views when it becomes slow. That is when Celery tasks belong. Not before.

The archived FastAPI `ml-service` (anomaly detection / RAG) was a different product idea. See `docs/archive/`.
