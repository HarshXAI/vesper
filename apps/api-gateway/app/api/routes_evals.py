"""
Evaluation API Routes.

Provides read-only endpoints for accessing evaluation results from MLflow
and metrics from Prometheus.
"""

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx

from app.core import settings


# =============================================================================
# Models
# =============================================================================

class EvalRun(BaseModel):
    """Evaluation run summary."""
    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metrics: Dict[str, float] = {}
    params: Dict[str, str] = {}


class EvalMetrics(BaseModel):
    """Aggregated evaluation metrics."""
    faithfulness: Optional[float] = None
    hallucination_rate: Optional[float] = None
    relevance: Optional[float] = None
    answer_similarity: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    error_rate_5xx: Optional[float] = None
    total_runs: int = 0
    last_run_time: Optional[datetime] = None


class EvalListResponse(BaseModel):
    """Response for list of eval runs."""
    runs: List[EvalRun] = []
    total: int = 0
    experiment_name: str = ""


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/v1/evals", tags=["evaluations"])


# =============================================================================
# MLflow Client Helpers
# =============================================================================

async def get_mlflow_client() -> httpx.AsyncClient:
    """Create MLflow API client."""
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", settings.mlflow_tracking_uri)
    return httpx.AsyncClient(
        base_url=mlflow_uri,
        timeout=30.0,
        headers={"Content-Type": "application/json"}
    )


async def get_experiment_by_name(client: httpx.AsyncClient, name: str) -> Optional[Dict[str, Any]]:
    """Get MLflow experiment by name."""
    try:
        response = await client.get(
            "/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": name}
        )
        if response.status_code == 200:
            return response.json().get("experiment")
        return None
    except Exception:
        return None


async def get_runs_for_experiment(
    client: httpx.AsyncClient, 
    experiment_id: str,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """Get runs for an MLflow experiment."""
    try:
        response = await client.post(
            "/api/2.0/mlflow/runs/search",
            json={
                "experiment_ids": [experiment_id],
                "max_results": max_results,
                "order_by": ["start_time DESC"]
            }
        )
        if response.status_code == 200:
            return response.json().get("runs", [])
        return []
    except Exception:
        return []


# =============================================================================
# Prometheus Client Helpers
# =============================================================================

async def query_prometheus(query: str) -> Optional[float]:
    """Query Prometheus and return single value."""
    prom_url = os.getenv("PROM_URL", os.getenv("PROMETHEUS_URL", "http://prometheus:9090"))
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{prom_url}/api/v1/query",
                params={"query": query}
            )
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", {}).get("result", [])
                if results and len(results) > 0:
                    value = results[0].get("value", [None, None])
                    if len(value) >= 2 and value[1] is not None:
                        return float(value[1])
    except Exception:
        pass
    return None


async def get_prometheus_metrics() -> Dict[str, Optional[float]]:
    """Get key metrics from Prometheus."""
    metrics = {}
    
    # P95 latency (in seconds, convert to ms)
    p95 = await query_prometheus(
        'histogram_quantile(0.95, sum(rate(vesper_request_duration_seconds_bucket[5m])) by (le))'
    )
    metrics["p95_latency_ms"] = p95 * 1000 if p95 else None
    
    # P99 latency
    p99 = await query_prometheus(
        'histogram_quantile(0.99, sum(rate(vesper_request_duration_seconds_bucket[5m])) by (le))'
    )
    metrics["p99_latency_ms"] = p99 * 1000 if p99 else None
    
    # 5xx error rate
    error_rate = await query_prometheus(
        'sum(rate(vesper_request_total{status=~"5.."}[5m])) / sum(rate(vesper_request_total[5m]))'
    )
    metrics["error_rate_5xx"] = error_rate
    
    return metrics


# =============================================================================
# Routes
# =============================================================================

@router.get("", response_model=EvalListResponse)
async def list_eval_runs(
    limit: int = 50,
    experiment_name: Optional[str] = None
):
    """
    List evaluation runs from MLflow.
    
    Returns recent evaluation runs with their metrics and parameters.
    """
    exp_name = experiment_name or os.getenv("MLFLOW_EXPERIMENT_NAME", settings.mlflow_experiment_name)
    
    try:
        async with await get_mlflow_client() as client:
            # Get experiment
            experiment = await get_experiment_by_name(client, exp_name)
            if not experiment:
                # Return empty response if experiment doesn't exist yet
                return EvalListResponse(
                    runs=[],
                    total=0,
                    experiment_name=exp_name
                )
            
            # Get runs
            raw_runs = await get_runs_for_experiment(
                client, 
                experiment["experiment_id"],
                max_results=limit
            )
            
            # Convert to response model
            runs = []
            for raw_run in raw_runs:
                info = raw_run.get("info", {})
                data = raw_run.get("data", {})
                
                # Parse metrics
                metrics = {}
                for m in data.get("metrics", []):
                    metrics[m["key"]] = m["value"]
                
                # Parse params
                params = {}
                for p in data.get("params", []):
                    params[p["key"]] = p["value"]
                
                runs.append(EvalRun(
                    run_id=info.get("run_id", ""),
                    experiment_id=info.get("experiment_id", ""),
                    run_name=info.get("run_name"),
                    status=info.get("status", "UNKNOWN"),
                    start_time=datetime.fromtimestamp(info["start_time"] / 1000, tz=timezone.utc) if info.get("start_time") else None,
                    end_time=datetime.fromtimestamp(info["end_time"] / 1000, tz=timezone.utc) if info.get("end_time") else None,
                    metrics=metrics,
                    params=params
                ))
            
            return EvalListResponse(
                runs=runs,
                total=len(runs),
                experiment_name=exp_name
            )
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="MLflow service unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"MLflow error: {str(e)}"
        )


@router.get("/metrics", response_model=EvalMetrics)
async def get_eval_metrics():
    """
    Get aggregated evaluation metrics.
    
    Combines latest eval metrics from MLflow with real-time metrics from Prometheus.
    """
    exp_name = os.getenv("MLFLOW_EXPERIMENT_NAME", settings.mlflow_experiment_name)
    
    metrics = EvalMetrics()
    
    # Get Prometheus metrics (always attempt)
    prom_metrics = await get_prometheus_metrics()
    metrics.p95_latency_ms = prom_metrics.get("p95_latency_ms")
    metrics.p99_latency_ms = prom_metrics.get("p99_latency_ms")
    metrics.error_rate_5xx = prom_metrics.get("error_rate_5xx")
    
    # Get MLflow metrics
    try:
        async with await get_mlflow_client() as client:
            experiment = await get_experiment_by_name(client, exp_name)
            if experiment:
                runs = await get_runs_for_experiment(
                    client,
                    experiment["experiment_id"],
                    max_results=10
                )
                
                metrics.total_runs = len(runs)
                
                if runs:
                    # Get latest run metrics
                    latest_run = runs[0]
                    info = latest_run.get("info", {})
                    data = latest_run.get("data", {})
                    
                    if info.get("start_time"):
                        metrics.last_run_time = datetime.fromtimestamp(
                            info["start_time"] / 1000, tz=timezone.utc
                        )
                    
                    # Extract eval metrics
                    for m in data.get("metrics", []):
                        key = m["key"].lower()
                        value = m["value"]
                        
                        if "faithfulness" in key:
                            metrics.faithfulness = value
                        elif "hallucination" in key:
                            metrics.hallucination_rate = value
                        elif "relevance" in key:
                            metrics.relevance = value
                        elif "similarity" in key:
                            metrics.answer_similarity = value
                            
    except Exception:
        # MLflow unavailable - return Prometheus metrics only
        pass
    
    return metrics


@router.get("/health")
async def eval_health():
    """Check evaluation infrastructure health."""
    mlflow_healthy = False
    prometheus_healthy = False
    
    # Check MLflow
    try:
        async with await get_mlflow_client() as client:
            response = await client.get("/health")
            mlflow_healthy = response.status_code == 200
    except Exception:
        pass
    
    # Check Prometheus
    prom_url = os.getenv("PROM_URL", os.getenv("PROMETHEUS_URL", "http://prometheus:9090"))
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{prom_url}/-/healthy")
            prometheus_healthy = response.status_code == 200
    except Exception:
        pass
    
    return {
        "mlflow": "healthy" if mlflow_healthy else "unavailable",
        "prometheus": "healthy" if prometheus_healthy else "unavailable",
        "overall": "healthy" if (mlflow_healthy or prometheus_healthy) else "degraded"
    }
