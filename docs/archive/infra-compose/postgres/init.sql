-- Security Intelligence Platform Database Initialization Script
-- Enables PostGIS for spatial/geospatial analytics and pgvector for AI embedding similarity searches

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
