-- Initial database setup for PrivateSearch.
-- This script runs once on first start of the pgvector image.
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL PRIVILEGES ON DATABASE privatesearch TO privatesearch;