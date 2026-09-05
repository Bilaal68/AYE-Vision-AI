# Health API

`GET /api/health/`

Public. No authentication.

Success (`200`):

```json
{
  "status": "ok",
  "service": "backend",
  "database": "ok"
}
```

If PostgreSQL is unreachable: `503` with `"status": "degraded"` and `"database": "error"`.
