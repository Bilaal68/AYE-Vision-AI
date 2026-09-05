# Security Intelligence Platform Architecture

## Component Overview

### 1. Backend (`backend/`)
- **Framework**: Django 4.2 + Django REST Framework (DRF)
- **Role**: Core API gateway, domain models, authentication, audit logging, entity relationships, and case management workflows.
- **Key Modules**:
  - `events`: Log ingestion & normalized event stream handler.
  - `incidents`: Incident life-cycle and case management.
  - `entities`: Vehicles, IoT devices, organizations, IP/Domain entities.
  - `graph`: Network graph relationships and edge mapping.
  - `investigations`: Collaborative forensic workspace.
  - `accounts`: User authentication, roles, and granular RBAC.
  - `audit`: Immutable audit trail for compliance and tracking.

### 2. Machine Learning & AI Microservice (`ml-service/`)
- **Framework**: FastAPI (Python 3.11)
- **Role**: High-performance asynchronous AI/ML telemetry processing.
- **Key Sub-modules**:
  - `anomaly_detection`: Scikit-learn Isolation Forest anomaly scoring models.
  - `rag_assistant`: LangChain RAG pipeline for cyber analyst AI assistants.
  - `correlation`: Real-time cross-event correlation and clustering logic.

### 3. Frontend Dashboard (`frontend/`)
- **Framework**: React 18 + Vite
- **Role**: High-fidelity security analyst dashboard.
- **Visualization Libraries**:
  - **Leaflet / React-Leaflet**: Geospatial threat tracking and asset mapping.
  - **react-force-graph**: Interactive 2D relationship network graph rendering.

### 4. Database Layer (`infra/postgres`)
- **Engine**: PostgreSQL 16
- **Extensions**:
  - **PostGIS**: Spatial indexing and spatial query operators (`GEOMETRY`, `ST_DWithin`).
  - **pgvector**: High-dimensional vector embedding store for AI RAG similarity search.

### 5. Cyber Range (`cyber-range/`)
- **Isolation**: Runs strictly on a separate Docker network (`cyberrange_net`).
- **Role**: Safe sandbox for adversary simulation, vulnerability verification, and detection validation.
