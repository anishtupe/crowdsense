-- Enables the extensions CrowdSense relies on.
-- pgvector may not be preinstalled on every Postgres image; if the
-- CREATE EXTENSION for it fails, install the pgvector package for your
-- Postgres version and re-run this file.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
