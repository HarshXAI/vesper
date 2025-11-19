-- Initialize VESPER database with pgvector extension

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create MLflow database
CREATE DATABASE mlflow;

-- Create Airflow database (if not exists)
CREATE DATABASE airflow;

-- Create application user
CREATE USER vesper_app WITH PASSWORD 'vesper_app_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE vesper TO vesper_app;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO vesper;

-- Create schemas
\c vesper;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS embeddings;
CREATE SCHEMA IF NOT EXISTS metadata;

-- Enable pgvector in vesper database
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant schema permissions
GRANT ALL PRIVILEGES ON SCHEMA documents TO vesper_app;
GRANT ALL PRIVILEGES ON SCHEMA embeddings TO vesper_app;
GRANT ALL PRIVILEGES ON SCHEMA metadata TO vesper_app;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA documents TO vesper_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA embeddings TO vesper_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA metadata TO vesper_app;

-- Example table for document chunks with embeddings
CREATE TABLE IF NOT EXISTS embeddings.document_chunks (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on embedding for fast similarity search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
ON embeddings.document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Full-text search index for hybrid search
CREATE INDEX IF NOT EXISTS document_chunks_content_idx 
ON embeddings.document_chunks 
USING gin(to_tsvector('english', content));

-- Index on document_id for fast filtering
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx 
ON embeddings.document_chunks(document_id);

-- Documents metadata table
CREATE TABLE IF NOT EXISTS documents.sources (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(255) UNIQUE NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    title TEXT,
    url TEXT,
    file_path TEXT,
    content_hash VARCHAR(64) NOT NULL,
    metadata JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS sources_source_id_idx ON documents.sources(source_id);
CREATE INDEX IF NOT EXISTS sources_source_type_idx ON documents.sources(source_type);

COMMENT ON TABLE embeddings.document_chunks IS 'Stores document chunks with vector embeddings for semantic search';
COMMENT ON TABLE documents.sources IS 'Stores metadata about source documents';
