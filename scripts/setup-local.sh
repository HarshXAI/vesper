#!/bin/bash
set -e

# VESPER Local Development Setup Script
# This script initializes your local development environment

echo "🚀 VESPER Local Development Setup"
echo "=================================="

# Check prerequisites
echo "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting." >&2; exit 1; }

echo "✅ Prerequisites check passed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file. Please review and update with your configuration."
fi

# Create necessary directories
echo "Creating directory structure..."
mkdir -p data/{bronze,silver,gold,raw}
mkdir -p logs/{airflow,api,services}
mkdir -p orchestration/{dags,logs,plugins}
mkdir -p monitoring/{prometheus,grafana}/{data,dashboards}
mkdir -p mlruns
mkdir -p secrets
mkdir -p tmp

echo "✅ Directory structure created"

# Create .gitkeep files
find data -type d -exec touch {}/.gitkeep \;
find logs -type d -exec touch {}/.gitkeep \;
find orchestration -type d -exec touch {}/.gitkeep \;

# Create init-db.sql for PostgreSQL initialization
cat > scripts/init-db.sql << 'EOF'
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
EOF

echo "✅ Database initialization script created"

# Create Prometheus configuration
mkdir -p monitoring/prometheus
cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'vesper-dev'
    environment: 'development'

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  # - "alerts/*.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'api-gateway'
    static_configs:
      - targets: ['api-gateway:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'kafka'
    static_configs:
      - targets: ['redpanda:9644']
EOF

echo "✅ Prometheus configuration created"

# Create example Airflow DAG
mkdir -p orchestration/dags
cat > orchestration/dags/example_ingestion_dag.py << 'EOF'
"""
Example VESPER Ingestion DAG
Demonstrates the Bronze -> Silver -> Gold data flow
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'vesper',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'example_ingestion_pipeline',
    default_args=default_args,
    description='Example data ingestion pipeline',
    schedule_interval=timedelta(days=1),
    catchup=False,
    tags=['example', 'ingestion'],
)

def bronze_ingestion(**context):
    """Ingest raw data to Bronze layer"""
    print("Ingesting raw data to Bronze layer...")
    # TODO: Implement actual ingestion logic
    return "bronze_complete"

def silver_transformation(**context):
    """Transform Bronze to Silver"""
    print("Transforming Bronze data to Silver layer...")
    # TODO: Implement transformation logic
    return "silver_complete"

def gold_aggregation(**context):
    """Aggregate Silver to Gold"""
    print("Aggregating Silver data to Gold layer...")
    # TODO: Implement aggregation logic
    return "gold_complete"

bronze_task = PythonOperator(
    task_id='bronze_ingestion',
    python_callable=bronze_ingestion,
    dag=dag,
)

silver_task = PythonOperator(
    task_id='silver_transformation',
    python_callable=silver_transformation,
    dag=dag,
)

gold_task = PythonOperator(
    task_id='gold_aggregation',
    python_callable=gold_aggregation,
    dag=dag,
)

bronze_task >> silver_task >> gold_task
EOF

echo "✅ Example Airflow DAG created"

# Ask user which docker-compose to use
echo ""
echo "Which Docker Compose configuration would you like to use?"
echo "1) Full stack (includes Airflow, MLflow, Redpanda) - Recommended"
echo "2) Simplified stack (Postgres, Redis, Kafka, MinIO, Prometheus, Grafana)"
echo ""
read -p "Enter your choice (1 or 2, default: 2): " compose_choice

case $compose_choice in
    1)
        echo "Using full docker-compose.yml"
        COMPOSE_FILE="docker-compose.yml"
        ;;
    *)
        echo "Using simplified docker-compose.simple.yml"
        COMPOSE_FILE="docker-compose.simple.yml"
        ;;
esac

# Pull Docker images
echo "Pulling Docker images (this may take a while)..."
docker-compose -f $COMPOSE_FILE pull 2>&1 | grep -v "version.*obsolete" || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "Configuration used: $COMPOSE_FILE"
echo ""
echo "Next steps:"
echo "1. Review and update .env file with your configuration"
if [ "$COMPOSE_FILE" = "docker-compose.simple.yml" ]; then
    echo "2. Start services: docker-compose -f docker-compose.simple.yml up -d"
    echo "3. Check service health: docker-compose -f docker-compose.simple.yml ps"
else
    echo "2. Start services: docker-compose up -d"
    echo "3. Check service health: docker-compose ps"
fi
echo "4. Access UIs:"
echo "   - Grafana: http://localhost:3003 (admin/admin)"
echo "   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "   - Prometheus: http://localhost:9090"
if [ "$COMPOSE_FILE" = "docker-compose.yml" ]; then
    echo "   - Airflow: http://localhost:8080 (admin/admin)"
    echo "   - MLflow: http://localhost:5000"
fi
echo ""
echo "For more information, see README.md"
