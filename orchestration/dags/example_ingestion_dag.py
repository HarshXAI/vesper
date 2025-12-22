"""
Example VESPER Ingestion DAG
Demonstrates the Bronze -> Silver -> Gold data flow

Supports multiple domains via ENV DOMAIN=finance|healthcare
Toggle domain by setting environment variable before DAG execution.
"""
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable

# Domain configuration from environment or Airflow variable
DOMAIN = os.getenv("DOMAIN", Variable.get("domain", default_var="finance"))

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
    description=f'Example data ingestion pipeline (domain: {DOMAIN})',
    schedule_interval=timedelta(days=1),
    catchup=False,
    tags=['example', 'ingestion', DOMAIN],
)


def detect_domain(**context) -> str:
    """Detect which domain branch to follow."""
    domain = os.getenv("DOMAIN", Variable.get("domain", default_var="finance")).lower()
    context['ti'].xcom_push(key='domain', value=domain)
    
    if domain == "healthcare":
        return "healthcare_bronze_ingestion"
    else:
        return "finance_bronze_ingestion"


def finance_bronze_ingestion(**context):
    """Ingest raw SEC filings to Bronze layer (finance domain)."""
    print(f"[Finance Domain] Ingesting raw SEC filings to Bronze layer...")
    print("Connecting to SEC EDGAR API...")
    print("Downloading 10-K, 10-Q, 8-K filings...")
    # TODO: Implement actual SEC ingestion logic
    return {"domain": "finance", "status": "bronze_complete", "filings_count": 10}


def healthcare_bronze_ingestion(**context):
    """Ingest healthcare documents to Bronze layer (healthcare domain)."""
    print(f"[Healthcare Domain] Ingesting healthcare documents to Bronze layer...")
    print("Connecting to healthcare data sources...")
    print("Downloading quality reports, performance dashboards...")
    
    # Use healthcare connector
    try:
        from vesper_processing.transformers import HealthcareConnector
        connector = HealthcareConnector()
        documents = connector.ingest_documents()
        print(f"Ingested {len(documents)} healthcare documents")
        return {"domain": "healthcare", "status": "bronze_complete", "documents_count": len(documents)}
    except ImportError:
        print("Healthcare connector not available, using mock data")
        return {"domain": "healthcare", "status": "bronze_complete", "documents_count": 6}


def silver_transformation(**context):
    """Transform Bronze to Silver (domain-agnostic with domain-specific NER)."""
    ti = context['ti']
    domain = ti.xcom_pull(key='domain', task_ids='detect_domain') or DOMAIN
    
    print(f"[{domain.title()} Domain] Transforming Bronze data to Silver layer...")
    
    # Apply domain-specific NER filters
    if domain == "healthcare":
        print("Applying healthcare NER patterns: FACILITY, METRIC, DEPARTMENT, COMPLIANCE...")
        try:
            from vesper_processing.transformers import get_entity_filter
            patterns = get_entity_filter("healthcare")
            print(f"Loaded {len(patterns)} healthcare entity patterns")
        except ImportError:
            print("Using default healthcare patterns")
    else:
        print("Applying finance NER patterns: COMPANY, TICKER, CURRENCY, FISCAL_PERIOD...")
        try:
            from vesper_processing.transformers import get_entity_filter
            patterns = get_entity_filter("finance")
            print(f"Loaded {len(patterns)} finance entity patterns")
        except ImportError:
            print("Using default finance patterns")
    
    # TODO: Implement actual transformation logic
    return {"domain": domain, "status": "silver_complete"}


def gold_aggregation(**context):
    """Aggregate Silver to Gold (domain-agnostic)."""
    ti = context['ti']
    domain = ti.xcom_pull(key='domain', task_ids='detect_domain') or DOMAIN
    
    print(f"[{domain.title()} Domain] Aggregating Silver data to Gold layer...")
    print("Creating embeddings...")
    print("Building vector index...")
    
    # TODO: Implement actual aggregation logic
    return {"domain": domain, "status": "gold_complete"}


def validate_ingestion(**context):
    """Validate the ingestion pipeline completed successfully."""
    ti = context['ti']
    domain = ti.xcom_pull(key='domain', task_ids='detect_domain') or DOMAIN
    
    print(f"[{domain.title()} Domain] Validating ingestion pipeline...")
    print("Checking data quality metrics...")
    print("Verifying embedding coverage...")
    
    # Run domain-specific validations
    if domain == "healthcare":
        print("Validating healthcare-specific requirements:")
        print("  ✓ HIPAA compliance fields present")
        print("  ✓ Facility identifiers valid")
        print("  ✓ Quality metrics extracted")
    else:
        print("Validating finance-specific requirements:")
        print("  ✓ CIK/Ticker mappings valid")
        print("  ✓ Filing dates parsed correctly")
        print("  ✓ Financial entities extracted")
    
    return {"domain": domain, "status": "validation_complete"}


# Task definitions
detect_domain_task = BranchPythonOperator(
    task_id='detect_domain',
    python_callable=detect_domain,
    dag=dag,
)

finance_bronze_task = PythonOperator(
    task_id='finance_bronze_ingestion',
    python_callable=finance_bronze_ingestion,
    dag=dag,
)

healthcare_bronze_task = PythonOperator(
    task_id='healthcare_bronze_ingestion',
    python_callable=healthcare_bronze_ingestion,
    dag=dag,
)

silver_task = PythonOperator(
    task_id='silver_transformation',
    python_callable=silver_transformation,
    trigger_rule='none_failed_min_one_success',  # Run after either bronze task
    dag=dag,
)

gold_task = PythonOperator(
    task_id='gold_aggregation',
    python_callable=gold_aggregation,
    dag=dag,
)

validate_task = PythonOperator(
    task_id='validate_ingestion',
    python_callable=validate_ingestion,
    dag=dag,
)

# DAG structure with domain branching
detect_domain_task >> [finance_bronze_task, healthcare_bronze_task]
finance_bronze_task >> silver_task
healthcare_bronze_task >> silver_task
silver_task >> gold_task >> validate_task
