-- Runs automatically the first time the Postgres container initializes its data volume.
-- Enables the pgvector extension so we can store embedding vectors in later milestones.
CREATE EXTENSION IF NOT EXISTS vector;
