"""
VESPER Nightly Evaluation DAG
==============================

Airflow DAG to run VESPER evaluation suite nightly and log results to MLflow.

Schedule: Daily at 2:00 AM UTC
Retries: 2
Timeout: 30 minutes
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Default arguments
default_args = {
    'owner': 'vesper',
    'depends_on_past': False,
    'email': ['team@vesper.ai'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

# Define DAG
dag = DAG(
    'vesper_nightly_evaluation',
    default_args=default_args,
    description='Run VESPER evaluation suite nightly',
    schedule_interval='0 2 * * *',  # 2 AM daily UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['vesper', 'evaluation', 'quality'],
)

# Task 1: Health check API
check_api_health = BashOperator(
    task_id='check_api_health',
    bash_command="""
    curl -f http://vesper-dev-alb-924352127.ap-south-1.elb.amazonaws.com/health || exit 1
    """,
    dag=dag,
)

# Task 2: Run evaluation
run_evaluation = BashOperator(
    task_id='run_evaluation',
    bash_command="""
    cd /path/to/vesper/evaluation && \
    python3 nightly_eval.py --mlflow --notify
    """,
    dag=dag,
)

# Task 3: Archive results
archive_results = BashOperator(
    task_id='archive_results',
    bash_command="""
    cd /path/to/vesper/evaluation && \
    mkdir -p archive/$(date +%Y/%m) && \
    cp results/eval_results_all_*.json archive/$(date +%Y/%m)/ || true
    """,
    dag=dag,
)

# Task 4: Cleanup old results (keep last 30 days)
cleanup_old_results = BashOperator(
    task_id='cleanup_old_results',
    bash_command="""
    find /path/to/vesper/evaluation/results -name "eval_results_*.json" -mtime +30 -delete
    """,
    dag=dag,
)

# Define task dependencies
check_api_health >> run_evaluation >> archive_results >> cleanup_old_results
