FROM postgis/postgis:16-3.4

# pgvector is optional. It was in the previous project for future embeddings.
# PostGIS is the required geospatial extension.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
