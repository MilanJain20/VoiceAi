-- ============================================================
-- Voice AI Platform — PostgreSQL Initialization
-- ============================================================
-- Runs once when the container is first created.
-- Enables required extensions.

-- Enable pgvector for embedding storage (RAG, Phase 8)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
