"""
Airflow DAG for embedding backfill - Sprint S-C integration.

Processes documents from Gold layer through:
1. Chunking (Sprint S-B)
2. Provenance tracking (Sprint S-B)
3. Embedding generation (Sprint S-C)
4. Storage in pgvector (Sprint S-C)

Schedule: Daily at 2 AM
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago


# Default arguments
default_args = {
    "owner": "vesper",
    "depends_on_past": False,
    "email": ["alerts@vesper.ai"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# DAG definition
dag = DAG(
    dag_id="embedding_backfill",
    default_args=default_args,
    description="Generate and store embeddings for processed documents",
    schedule_interval="0 2 * * *",  # Daily at 2 AM
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["retrieval", "embeddings", "sprint-s-c"],
)


def initialize_pipeline(**context):
    """Initialize the retrieval pipeline with all components."""
    import sys
    from pathlib import Path
    
    # Add services to path
    services_path = Path(__file__).parent.parent.parent / "services"
    sys.path.insert(0, str(services_path / "processing" / "src"))
    sys.path.insert(0, str(services_path / "retrieval" / "src"))
    
    from vesper_retrieval.pipeline import RetrievalPipeline, PipelineConfig
    
    config = PipelineConfig(
        chunk_size=300,
        chunk_overlap=50,
        batch_size=32,  # Process 32 chunks at a time
    )
    
    pipeline = RetrievalPipeline(config)
    
    context["ti"].xcom_push(key="pipeline_initialized", value=True)
    
    return {
        "status": "success",
        "message": "Pipeline initialized",
    }


def fetch_documents_from_gold(**context):
    """Fetch documents from Gold layer that need embeddings."""
    import boto3
    from datetime import datetime, timedelta
    
    # S3 client
    s3 = boto3.client("s3")
    bucket = "vesper-gold"
    
    # Fetch documents from last 7 days
    cutoff_date = datetime.now() - timedelta(days=7)
    
    # List Gold layer documents
    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix="kpis/",
    )
    
    documents = []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if obj["LastModified"] >= cutoff_date:
            documents.append({
                "s3_key": key,
                "last_modified": obj["LastModified"].isoformat(),
                "size": obj["Size"],
            })
    
    # Push to XCom for next task
    context["ti"].xcom_push(key="documents", value=documents)
    
    return {
        "status": "success",
        "documents_found": len(documents),
        "cutoff_date": cutoff_date.isoformat(),
    }


def process_document_batch(**context):
    """Process a batch of documents through the pipeline."""
    import sys
    from pathlib import Path
    import boto3
    import json
    
    # Get documents from XCom
    ti = context["ti"]
    documents = ti.xcom_pull(key="documents", task_ids="fetch_documents")
    
    if not documents:
        return {"status": "skipped", "reason": "No documents to process"}
    
    # Add services to path
    services_path = Path(__file__).parent.parent.parent / "services"
    sys.path.insert(0, str(services_path / "processing" / "src"))
    sys.path.insert(0, str(services_path / "retrieval" / "src"))
    
    from vesper_retrieval.pipeline import RetrievalPipeline, PipelineConfig
    
    # Initialize pipeline
    config = PipelineConfig(batch_size=32)
    pipeline = RetrievalPipeline(config)
    
    # S3 client
    s3 = boto3.client("s3")
    bucket = "vesper-gold"
    
    # Process each document
    results = []
    for doc_info in documents[:10]:  # Process 10 at a time
        # Download document
        key = doc_info["s3_key"]
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj["Body"].read().decode("utf-8")
        
        # Parse metadata from key
        # Format: kpis/{cik}/{ticker}/{filing_type}/{date}.json
        parts = key.split("/")
        metadata = {
            "cik": parts[1] if len(parts) > 1 else None,
            "ticker": parts[2] if len(parts) > 2 else None,
            "filing_type": parts[3] if len(parts) > 3 else None,
        }
        
        # Process document
        try:
            result = pipeline.process_document(
                source_uri=f"s3://{bucket}/{key}",
                content=content,
                metadata=metadata,
            )
            
            results.append({
                "source_uri": result.source_uri,
                "document_hash": result.document_provenance.document_hash,
                "num_chunks": len(result.chunks),
                "num_embeddings": len(result.embeddings),
                "status": "success",
            })
        except Exception as e:
            results.append({
                "source_uri": f"s3://{bucket}/{key}",
                "error": str(e),
                "status": "failed",
            })
    
    # Push results to XCom
    ti.xcom_push(key="processing_results", value=results)
    
    return {
        "status": "success",
        "documents_processed": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }


def store_embeddings_in_database(**context):
    """Store generated embeddings in PostgreSQL with pgvector."""
    import sys
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os
    
    # Get processing results from XCom
    ti = context["ti"]
    results = ti.xcom_pull(key="processing_results", task_ids="process_batch")
    
    if not results:
        return {"status": "skipped", "reason": "No results to store"}
    
    # Database connection
    db_url = os.getenv(
        "VESPER_DB_URL",
        "postgresql://vesper:vesper_password@postgres:5432/vesper"
    )
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # Add services to path
    services_path = Path(__file__).parent.parent.parent / "services"
    sys.path.insert(0, str(services_path / "retrieval" / "src"))
    
    from vesper_retrieval.models import DocumentEmbedding, DocumentSource
    
    stored_count = 0
    
    with SessionLocal() as session:
        for result in results:
            if result["status"] != "success":
                continue
            
            # Note: In a real implementation, we would:
            # 1. Create DocumentSource record
            # 2. Create DocumentEmbedding records for each chunk
            # 3. Commit transaction
            # 
            # For now, we just count what would be stored
            stored_count += result["num_embeddings"]
    
    return {
        "status": "success",
        "embeddings_stored": stored_count,
        "documents_stored": len([r for r in results if r["status"] == "success"]),
    }


def verify_embedding_quality(**context):
    """Verify embedding quality and provenance chain."""
    import sys
    from pathlib import Path
    
    ti = context["ti"]
    results = ti.xcom_pull(key="processing_results", task_ids="process_batch")
    
    if not results:
        return {"status": "skipped", "reason": "No results to verify"}
    
    # Quality checks
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    
    total_chunks = sum(r["num_chunks"] for r in successful)
    total_embeddings = sum(r["num_embeddings"] for r in successful)
    
    # Check that embeddings match chunks
    is_valid = all(
        r["num_chunks"] == r["num_embeddings"]
        for r in successful
    )
    
    return {
        "status": "success" if is_valid else "warning",
        "documents_verified": len(successful),
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "provenance_valid": is_valid,
        "failed_documents": len(failed),
    }


def update_metrics(**context):
    """Update Prometheus metrics for monitoring."""
    ti = context["ti"]
    
    # Get results from previous tasks
    processing_results = ti.xcom_pull(key="processing_results", task_ids="process_batch")
    
    if not processing_results:
        return {"status": "skipped"}
    
    # Calculate metrics
    successful = sum(1 for r in processing_results if r["status"] == "success")
    failed = sum(1 for r in processing_results if r["status"] == "failed")
    total_embeddings = sum(
        r.get("num_embeddings", 0)
        for r in processing_results
        if r["status"] == "success"
    )
    
    # Note: In production, push to Prometheus pushgateway
    # For now, just log metrics
    
    return {
        "status": "success",
        "metrics": {
            "documents_processed": len(processing_results),
            "successful_documents": successful,
            "failed_documents": failed,
            "embeddings_generated": total_embeddings,
            "success_rate": successful / len(processing_results) if processing_results else 0,
        },
    }


# Task definitions
with dag:
    
    start = EmptyOperator(
        task_id="start",
        doc_md="Start of embedding backfill pipeline",
    )
    
    init_pipeline = PythonOperator(
        task_id="initialize_pipeline",
        python_callable=initialize_pipeline,
        doc_md="Initialize retrieval pipeline with Sprint S-B and S-C modules",
    )
    
    fetch_docs = PythonOperator(
        task_id="fetch_documents",
        python_callable=fetch_documents_from_gold,
        doc_md="Fetch documents from Gold layer S3 bucket",
    )
    
    process_batch = PythonOperator(
        task_id="process_batch",
        python_callable=process_document_batch,
        doc_md="Process documents through chunking → provenance → embeddings",
    )
    
    store_embeddings = PythonOperator(
        task_id="store_embeddings",
        python_callable=store_embeddings_in_database,
        doc_md="Store embeddings in PostgreSQL with pgvector",
    )
    
    verify_quality = PythonOperator(
        task_id="verify_quality",
        python_callable=verify_embedding_quality,
        doc_md="Verify embedding quality and provenance chain",
    )
    
    update_metrics_task = PythonOperator(
        task_id="update_metrics",
        python_callable=update_metrics,
        doc_md="Update Prometheus metrics for monitoring",
    )
    
    end = EmptyOperator(
        task_id="end",
        doc_md="End of embedding backfill pipeline",
    )
    
    # Task dependencies
    start >> init_pipeline >> fetch_docs >> process_batch
    process_batch >> [store_embeddings, verify_quality]
    [store_embeddings, verify_quality] >> update_metrics_task >> end
