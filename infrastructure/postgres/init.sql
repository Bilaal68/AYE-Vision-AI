-- Enabled on first database init only (empty volume).
-- PostGIS: geospatial types and functions for future map queries.
-- vector: optional embeddings store; unused in the foundation.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
