# Security Intelligence Platform

A modular security intelligence and cyber defense platform prototype designed for threat detection, incident management, geospatial visualization, graph correlation, and AI-assisted investigation.

---

## 📁 Repository Structure

```
security-intelligence-platform/
├── backend/                      # Django + DRF application
│   ├── config/                   # Django project settings & config
│   ├── apps/
│   │   ├── events/                # Event ingestion models, views, serializers
│   │   ├── incidents/              # Incident/case management
│   │   ├── entities/              # Entities, vehicles, devices, orgs
│   │   ├── graph/                  # Relationship/edges model
│   │   ├── investigations/         # Investigation workspace
│   │   ├── accounts/               # Auth, roles, permissions
│   │   └── audit/                  # Audit logging
│   ├── requirements.txt
│   ├── manage.py
│   └── Dockerfile
├── ml-service/                    # FastAPI ML/AI microservice
│   ├── app/
│   │   ├── anomaly_detection/     # Isolation Forest / anomaly scoring
│   │   ├── rag_assistant/          # AI analyst RAG pipeline
│   │   ├── correlation/            # Event correlation logic
│   │   └── main.py                 # Health check endpoint GET /health
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                      # React analyst dashboard
│   ├── src/
│   │   ├── components/            # Visual components (dashboard, map, graph, etc.)
│   │   ├── pages/                 # Dashboard, Incidents, Investigations pages
│   │   ├── services/               # API client code
│   │   ├── hooks/                  # Custom React hooks
│   │   └── App.jsx
│   ├── package.json
│   └── Dockerfile
├── cyber-range/                   # Isolated adversary simulation environment
│   ├── vulnerable-services/        # Intentionally vulnerable containers
│   ├── detection-tests/            # Attack test suites
│   ├── docker-compose.cyberrange.yml # SEPARATE compose file, isolated network
│   └── README.md
├── infra/
│   ├── docker-compose.yml         # Main stack orchestrator (backend, ml-service, frontend, db)
│   ├── postgres/
│   │   ├── Dockerfile              # PostGIS + pgvector PostgreSQL container
│   │   └── init.sql                # Enables PostGIS & pgvector extensions
│   └── nginx/                      # Nginx reverse proxy configuration
├── docs/                          # Architecture notes and documentation
│   └── architecture.md
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore file
├── docker-compose.yml             # Root wrapper compose file
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://www.docker.com/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### 1. Environment Setup
Copy `.env.example` to create your local `.env` configuration:
```bash
cp .env.example .env
```

### 2. Run Main Application Stack
Start all core platform services (`backend`, `ml-service`, `frontend`, `db`) with a single command:
```bash
docker compose up --build
```
*Or using the infra directory file directly:*
```bash
docker compose -f infra/docker-compose.yml up --build
```

### 3. Access Services
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Django Backend API**: [http://localhost:8000/api/health/](http://localhost:8000/api/health/)
- **ML/AI Microservice**: [http://localhost:8001/health](http://localhost:8001/health)
- **PostgreSQL Database**: `localhost:5432` (`secint_db`)

---

## 🎯 Cyber Range Environment (Isolated)

The Cyber Range is kept **strictly isolated** on its own network (`cyberrange_net`).

To boot the Cyber Range simulation environment:
```bash
docker compose -f cyber-range/docker-compose.cyberrange.yml up --build -d
```
Target web endpoint: [http://localhost:8088](http://localhost:8088)

---

## 🧪 Service Health & Verification

Check container health status:
```bash
docker compose ps
```
All containers include automated health check probes to ensure database readines and inter-service communication.
