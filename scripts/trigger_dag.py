#!/usr/bin/env python3
"""Trigger Airflow DAG via REST API.

Triggers the SEC filing ingestion DAG to generate metrics for Airflow
job execution visible in Prometheus and Grafana.
"""
import sys
import requests
from datetime import datetime

AIRFLOW_BASE_URL = "http://localhost:8080"
AIRFLOW_USER = "admin"
AIRFLOW_PASSWORD = "admin"
DAG_ID = "sec_filing_ingestion"


def trigger_dag(dag_id: str = DAG_ID, conf: dict = None) -> dict:
    """Trigger a DAG run via Airflow REST API."""
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}/dagRuns"
    
    payload = {
        "conf": conf or {},
        "note": "Triggered via script for metrics generation"
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            return {
                "success": True,
                "dag_run_id": data.get("dag_run_id"),
                "state": data.get("state"),
                "execution_date": data.get("execution_date")
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_dag_status(dag_id: str = DAG_ID) -> dict:
    """Get current DAG status."""
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}"
    
    try:
        response = requests.get(
            url,
            auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "is_paused": data.get("is_paused"),
                "is_active": data.get("is_active")
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """Main function."""
    print("🚀 Airflow DAG Trigger")
    print(f"   Airflow: {AIRFLOW_BASE_URL}")
    print(f"   DAG: {DAG_ID}")
    print()
    
    # Check DAG status
    print("📊 Checking DAG status...", end=" ")
    status = get_dag_status()
    
    if not status["success"]:
        print("❌ FAILED")
        print(f"   Error: {status['error']}")
        print()
        print("   Make sure Airflow is running:")
        print("   docker compose up -d airflow-webserver")
        sys.exit(1)
    
    print("✅ OK")
    
    if status.get("is_paused"):
        print("   ⚠️  DAG is paused - unpause it in Airflow UI first")
        print(f"   http://localhost:8080/dags/{DAG_ID}/grid")
        sys.exit(1)
    
    print()
    
    # Trigger DAG
    print("▶️  Triggering DAG run...", end=" ")
    result = trigger_dag()
    
    if result["success"]:
        print("✅ SUCCESS")
        print()
        print("   DAG Run Details:")
        print(f"   Run ID: {result['dag_run_id']}")
        print(f"   State: {result['state']}")
        print(f"   Execution Date: {result['execution_date']}")
        print()
        print("   Monitor progress:")
        print(f"   {AIRFLOW_BASE_URL}/dags/{DAG_ID}/grid")
    else:
        print("❌ FAILED")
        print(f"   Error: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
