# Archived from the previous prototype

These folders are **not started** by `docker-compose.yml`. They are kept so earlier work is not lost.

| Path | What it was | Why it is not in the live stack |
| --- | --- | --- |
| `cyber-range/` | Isolated vulnerable services for attack simulation | Different product (cyber range), not situational awareness |
| `ml-service/` | FastAPI health stub + planned anomaly/RAG | Extra microservice; AI now lives as packages under `/ai` |
| `infra-compose/` | Duplicate Compose file | Replaced by root `docker-compose.yml` + `infrastructure/` |
| `backend-apps/` | `events`, `entities`, `graph`, `accounts`, `audit` placeholders | Replaced by domain apps (`users`, `cameras`, …) |
| `architecture-v0.md`, `stack.txt` | Old architecture notes | Superseded by `docs/architecture/` |

Useful pieces that **were reused**:

- PostGIS Docker image + `init.sql`
- Nginx reverse-proxy idea
- Django + DRF + CORS pattern
- Health-check URL
- Dark UI color tokens
- Leaflet as the map library
- Investigations / incidents as domain names
