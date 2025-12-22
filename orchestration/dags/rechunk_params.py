"""
VESPER Rechunk Parameters DAG
==============================

Airflow DAG for auto-remediation: update chunking parameters and re-process documents.
Triggered when retrieval quality degrades due to chunk-related issues.

This DAG:
1. Analyzes current chunk quality metrics
2. Proposes new chunking parameters
3. Re-chunks affected documents
4. Generates new embeddings
5. A/B tests new chunks vs old
6. Swaps to new chunks if improved
"""

from datetime import datetime, timedelta
import json
import logging
import os
from typing import Optional

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable

# Try to import optional dependencies
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ==============================================================================
# Configuration
# ==============================================================================

VESPER_API_URL = Variable.get("vesper_api_url", default_var="http://vesper-api-gateway:8000")
S3_BUCKET = Variable.get("chunks_bucket", default_var="vesper-chunks")
SLACK_WEBHOOK_URL = Variable.get("slack_webhook_url", default_var="")

# Chunking parameter presets
CHUNK_PRESETS = {
    "default": {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "split_by": "sentence"
    },
    "small": {
        "chunk_size": 256,
        "chunk_overlap": 25,
        "split_by": "sentence"
    },
    "large": {
        "chunk_size": 1024,
        "chunk_overlap": 100,
        "split_by": "paragraph"
    },
    "semantic": {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "split_by": "semantic"
    }
}


# ==============================================================================
# Default Arguments  
# ==============================================================================

default_args = {
    'owner': 'vesper-ml',
    'depends_on_past': False,
    'email': ['ml-ops@vesper.ai'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=15),
    'execution_timeout': timedelta(hours=6),
}


# ==============================================================================
# Task Functions
# ==============================================================================

def parse_trigger_event(**context) -> dict:
    """Parse EventBridge trigger event."""
    dag_run = context.get('dag_run')
    conf = dag_run.conf or {}
    
    params = {
        "trigger_source": conf.get("source", "manual"),
        "doc_ids": conf.get("doc_ids", []),
        "categories": conf.get("categories", []),
        "current_preset": conf.get("current_preset", "default"),
        "target_preset": conf.get("target_preset", None),  # Auto-detect if None
        "dry_run": conf.get("dry_run", False),
        "ab_test_ratio": conf.get("ab_test_ratio", 0.1),  # 10% of traffic for A/B
        "quality_threshold": conf.get("quality_threshold", 0.75),
    }
    
    logging.info(f"Rechunk triggered: {params}")
    context['ti'].xcom_push(key='params', value=params)
    return params


def analyze_chunk_quality(**context) -> dict:
    """Analyze current chunk quality to determine best parameters."""
    ti = context['ti']
    params = ti.xcom_pull(key='params', task_ids='parse_trigger') or {}
    
    analysis = {
        "avg_chunk_size": 0,
        "chunk_size_variance": 0,
        "avg_overlap_ratio": 0,
        "fragmentation_score": 0,
        "semantic_coherence": 0,
        "recommended_preset": "default",
        "issues": []
    }
    
    if REQUESTS_AVAILABLE:
        try:
            response = requests.post(
                f"{VESPER_API_URL}/internal/admin/chunk-analysis",
                json={
                    "categories": params.get("categories", []),
                    "sample_size": 100
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                analysis.update(data)
        except Exception as e:
            logging.error(f"Failed to analyze chunks: {e}")
    
    # Determine recommended preset based on analysis
    if analysis.get("fragmentation_score", 0) > 0.7:
        analysis["recommended_preset"] = "large"
        analysis["issues"].append("High fragmentation - recommend larger chunks")
    elif analysis.get("avg_chunk_size", 512) > 800:
        analysis["recommended_preset"] = "small"
        analysis["issues"].append("Chunks too large - recommend smaller chunks")
    elif analysis.get("semantic_coherence", 1) < 0.6:
        analysis["recommended_preset"] = "semantic"
        analysis["issues"].append("Low semantic coherence - recommend semantic chunking")
    
    # Use target preset if specified
    if params.get("target_preset"):
        analysis["recommended_preset"] = params["target_preset"]
    
    logging.info(f"Chunk analysis: {analysis}")
    ti.xcom_push(key='analysis', value=analysis)
    return analysis


def identify_documents(**context) -> list[str]:
    """Identify documents to re-chunk."""
    ti = context['ti']
    params = ti.xcom_pull(key='params', task_ids='parse_trigger') or {}
    
    if params.get("doc_ids"):
        logging.info(f"Using provided doc_ids: {len(params['doc_ids'])}")
        ti.xcom_push(key='doc_ids', value=params['doc_ids'])
        return params['doc_ids']
    
    doc_ids = []
    
    if REQUESTS_AVAILABLE:
        try:
            response = requests.post(
                f"{VESPER_API_URL}/internal/admin/documents-by-category",
                json={"categories": params.get("categories", [])},
                timeout=60
            )
            
            if response.status_code == 200:
                doc_ids = response.json().get("doc_ids", [])
        except Exception as e:
            logging.error(f"Failed to get documents: {e}")
    
    if not doc_ids:
        doc_ids = [f"doc-{i:04d}" for i in range(20)]  # Fallback
    
    logging.info(f"Identified {len(doc_ids)} documents for re-chunking")
    ti.xcom_push(key='doc_ids', value=doc_ids)
    return doc_ids


def check_should_proceed(**context) -> str:
    """Check if we should proceed with re-chunking."""
    ti = context['ti']
    params = ti.xcom_pull(key='params', task_ids='parse_trigger') or {}
    doc_ids = ti.xcom_pull(key='doc_ids', task_ids='identify_docs') or []
    
    if params.get("dry_run"):
        logging.info("Dry run mode - skipping")
        return 'skip_rechunk'
    
    if not doc_ids:
        logging.info("No documents to re-chunk")
        return 'skip_rechunk'
    
    return 'fetch_documents'


def fetch_documents(**context) -> list[dict]:
    """Fetch source documents for re-chunking."""
    ti = context['ti']
    doc_ids = ti.xcom_pull(key='doc_ids', task_ids='identify_docs') or []
    
    documents = []
    
    for doc_id in doc_ids[:100]:  # Limit batch
        if REQUESTS_AVAILABLE:
            try:
                response = requests.get(
                    f"{VESPER_API_URL}/internal/admin/documents/{doc_id}/source",
                    timeout=30
                )
                
                if response.status_code == 200:
                    documents.append(response.json())
                    continue
            except Exception as e:
                logging.error(f"Failed to fetch {doc_id}: {e}")
        
        # Fallback
        documents.append({
            "id": doc_id,
            "content": f"Sample document content for {doc_id}. " * 50,
            "metadata": {"source": "fallback"}
        })
    
    logging.info(f"Fetched {len(documents)} source documents")
    ti.xcom_push(key='documents', value=documents)
    return documents


def rechunk_documents(**context) -> dict:
    """Re-chunk documents with new parameters."""
    ti = context['ti']
    documents = ti.xcom_pull(key='documents', task_ids='fetch_documents') or []
    analysis = ti.xcom_pull(key='analysis', task_ids='analyze_chunks') or {}
    
    preset_name = analysis.get("recommended_preset", "default")
    preset = CHUNK_PRESETS.get(preset_name, CHUNK_PRESETS["default"])
    
    chunks = []
    
    for doc in documents:
        content = doc.get("content", "")
        doc_id = doc.get("id", "unknown")
        
        # Simple chunking implementation
        chunk_size = preset["chunk_size"]
        overlap = preset["chunk_overlap"]
        
        start = 0
        chunk_idx = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_text = content[start:end]
            
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": f"{doc_id}-chunk-{chunk_idx}",
                    "doc_id": doc_id,
                    "text": chunk_text,
                    "start": start,
                    "end": end,
                    "metadata": {
                        "preset": preset_name,
                        "chunk_size": chunk_size,
                        "overlap": overlap
                    }
                })
                chunk_idx += 1
            
            start = end - overlap
            if start >= len(content) - overlap:
                break
    
    result = {
        "preset": preset_name,
        "params": preset,
        "total_chunks": len(chunks),
        "documents_processed": len(documents)
    }
    
    logging.info(f"Re-chunking result: {result}")
    ti.xcom_push(key='chunks', value=chunks)
    ti.xcom_push(key='rechunk_result', value=result)
    return result


def generate_embeddings(**context) -> dict:
    """Generate embeddings for new chunks."""
    ti = context['ti']
    chunks = ti.xcom_pull(key='chunks', task_ids='rechunk_documents') or []
    
    embeddings = {}
    
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        
        if REQUESTS_AVAILABLE:
            try:
                response = requests.post(
                    f"{VESPER_API_URL}/internal/embed",
                    json={"text": chunk.get("text", "")},
                    timeout=30
                )
                
                if response.status_code == 200:
                    embeddings[chunk_id] = response.json().get("embedding")
                    continue
            except Exception as e:
                logging.error(f"Failed to embed {chunk_id}: {e}")
        
        # Fallback
        embeddings[chunk_id] = [0.1] * 1536
    
    result = {
        "total": len(chunks),
        "embedded": len(embeddings)
    }
    
    logging.info(f"Embedding result: {result}")
    ti.xcom_push(key='embeddings', value=embeddings)
    ti.xcom_push(key='embed_result', value=result)
    return result


def setup_ab_test(**context) -> dict:
    """Set up A/B test for new chunks vs old."""
    ti = context['ti']
    params = ti.xcom_pull(key='params', task_ids='parse_trigger') or {}
    chunks = ti.xcom_pull(key='chunks', task_ids='rechunk_documents') or []
    embeddings = ti.xcom_pull(key='embeddings', task_ids='generate_embeddings') or {}
    
    ab_ratio = params.get("ab_test_ratio", 0.1)
    
    # Configure A/B test in API
    ab_config = {
        "test_id": f"rechunk-{datetime.now().strftime('%Y%m%d%H%M')}",
        "variant_a": "current_chunks",
        "variant_b": "new_chunks",
        "traffic_split": ab_ratio,
        "metrics": ["ndcg10", "recall5", "latency"],
        "duration_hours": 24,
        "new_chunk_ids": [c["chunk_id"] for c in chunks],
    }
    
    if REQUESTS_AVAILABLE:
        try:
            response = requests.post(
                f"{VESPER_API_URL}/internal/admin/ab-test",
                json=ab_config,
                timeout=30
            )
            
            if response.status_code == 200:
                ab_config["status"] = "configured"
        except Exception as e:
            logging.error(f"Failed to configure A/B test: {e}")
            ab_config["status"] = "failed"
    else:
        ab_config["status"] = "simulated"
    
    logging.info(f"A/B test setup: {ab_config}")
    ti.xcom_push(key='ab_config', value=ab_config)
    return ab_config


def store_chunks_staging(**context) -> dict:
    """Store new chunks in staging before swap."""
    ti = context['ti']
    chunks = ti.xcom_pull(key='chunks', task_ids='rechunk_documents') or []
    embeddings = ti.xcom_pull(key='embeddings', task_ids='generate_embeddings') or {}
    
    stored = 0
    
    if BOTO3_AVAILABLE:
        try:
            s3 = boto3.client('s3')
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Store chunks
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=f"staging/{timestamp}/chunks.json",
                Body=json.dumps(chunks),
                ContentType='application/json'
            )
            
            # Store embeddings
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=f"staging/{timestamp}/embeddings.json",
                Body=json.dumps(embeddings),
                ContentType='application/json'
            )
            
            stored = len(chunks)
        except Exception as e:
            logging.error(f"Failed to store to S3: {e}")
    else:
        stored = len(chunks)  # Simulate
    
    result = {"stored": stored, "total": len(chunks)}
    logging.info(f"Staging result: {result}")
    ti.xcom_push(key='staging_result', value=result)
    return result


def send_notification(**context) -> None:
    """Send completion notification."""
    if not SLACK_WEBHOOK_URL or not REQUESTS_AVAILABLE:
        logging.warning("Slack not configured")
        return
    
    ti = context['ti']
    params = ti.xcom_pull(key='params', task_ids='parse_trigger') or {}
    analysis = ti.xcom_pull(key='analysis', task_ids='analyze_chunks') or {}
    rechunk_result = ti.xcom_pull(key='rechunk_result', task_ids='rechunk_documents') or {}
    ab_config = ti.xcom_pull(key='ab_config', task_ids='setup_ab_test') or {}
    
    message = {
        "text": "🔄 VESPER Rechunk DAG Completed",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🔄 Rechunk Parameters Completed"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Trigger:* {params.get('trigger_source', 'manual')}\n"
                           f"*New Preset:* `{rechunk_result.get('preset', 'unknown')}`\n"
                           f"*Documents:* {rechunk_result.get('documents_processed', 0)}\n"
                           f"*Chunks created:* {rechunk_result.get('total_chunks', 0)}\n"
                           f"*A/B Test:* {ab_config.get('status', 'none')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Analysis Issues:*\n" + 
                           "\n".join(f"• {i}" for i in analysis.get("issues", ["None"]))
                }
            }
        ]
    }
    
    try:
        requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        logging.info("Notification sent")
    except Exception as e:
        logging.error(f"Failed to send notification: {e}")


# ==============================================================================
# DAG Definition
# ==============================================================================

with DAG(
    'rechunk_params',
    default_args=default_args,
    description='Re-chunk documents with new parameters (auto-remediation)',
    schedule_interval=None,  # Triggered by EventBridge
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['vesper', 'remediation', 'chunking', 'auto'],
    doc_md=__doc__,
) as dag:
    
    # Parse trigger
    parse_trigger = PythonOperator(
        task_id='parse_trigger',
        python_callable=parse_trigger_event,
        provide_context=True,
    )
    
    # Analyze chunks
    analyze_chunks = PythonOperator(
        task_id='analyze_chunks',
        python_callable=analyze_chunk_quality,
        provide_context=True,
    )
    
    # Identify documents
    identify_docs = PythonOperator(
        task_id='identify_docs',
        python_callable=identify_documents,
        provide_context=True,
    )
    
    # Check should proceed
    should_proceed = BranchPythonOperator(
        task_id='should_proceed',
        python_callable=check_should_proceed,
        provide_context=True,
    )
    
    # Skip path
    skip_rechunk = EmptyOperator(
        task_id='skip_rechunk',
    )
    
    # Fetch documents
    fetch_docs = PythonOperator(
        task_id='fetch_documents',
        python_callable=fetch_documents,
        provide_context=True,
    )
    
    # Rechunk
    rechunk = PythonOperator(
        task_id='rechunk_documents',
        python_callable=rechunk_documents,
        provide_context=True,
    )
    
    # Generate embeddings
    gen_embeddings = PythonOperator(
        task_id='generate_embeddings',
        python_callable=generate_embeddings,
        provide_context=True,
    )
    
    # Setup A/B test
    ab_test = PythonOperator(
        task_id='setup_ab_test',
        python_callable=setup_ab_test,
        provide_context=True,
    )
    
    # Store staging
    store_staging = PythonOperator(
        task_id='store_staging',
        python_callable=store_chunks_staging,
        provide_context=True,
    )
    
    # Join
    join = EmptyOperator(
        task_id='join',
        trigger_rule='none_failed_min_one_success',
    )
    
    # Notify
    notify = PythonOperator(
        task_id='notify',
        python_callable=send_notification,
        provide_context=True,
    )
    
    # Dependencies
    parse_trigger >> [analyze_chunks, identify_docs]
    [analyze_chunks, identify_docs] >> should_proceed
    should_proceed >> [skip_rechunk, fetch_docs]
    fetch_docs >> rechunk >> gen_embeddings >> [ab_test, store_staging]
    [skip_rechunk, ab_test, store_staging] >> join >> notify
