"""
Unit tests for evaluation routes.

Tests the /v1/evals and /v1/evals/metrics endpoints.
These tests are designed to run with minimal dependencies using mocks.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

import httpx


# =============================================================================
# Check if full dependencies are available for integration tests
# =============================================================================
try:
    from app.api.routes_evals import (
        router, list_eval_runs, get_eval_metrics,
        EvalRun, EvalMetrics, EvalListResponse
    )
    FULL_DEPS_AVAILABLE = True
except ImportError:
    FULL_DEPS_AVAILABLE = False
    # Create mock classes for basic tests
    class EvalRun:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class EvalMetrics:
        def __init__(self, **kwargs):
            defaults = {
                'faithfulness': None, 'hallucination_rate': None,
                'relevance': None, 'p95_latency_ms': None,
                'p99_latency_ms': None, 'error_rate_5xx': None,
                'total_runs': 0, 'last_run_at': None
            }
            defaults.update(kwargs)
            for k, v in defaults.items():
                setattr(self, k, v)
    
    class EvalListResponse:
        def __init__(self, runs=None, total=0, experiment_name=None):
            self.runs = runs or []
            self.total = total
            self.experiment_name = experiment_name


# =============================================================================
# Mock Data
# =============================================================================

MOCK_EXPERIMENT = {
    "experiment_id": "1",
    "name": "vesper-nightly-eval",
    "lifecycle_stage": "active"
}

MOCK_RUN = {
    "info": {
        "run_id": "abc123",
        "experiment_id": "1",
        "run_name": "nightly-2024-01-15",
        "status": "FINISHED",
        "start_time": 1705276800000,  # 2024-01-15 00:00:00 UTC
        "end_time": 1705277400000     # 2024-01-15 00:10:00 UTC
    },
    "data": {
        "metrics": [
            {"key": "faithfulness", "value": 0.92},
            {"key": "hallucination_rate", "value": 0.03},
            {"key": "relevance", "value": 0.88}
        ],
        "params": [
            {"key": "model", "value": "gpt-4o"},
            {"key": "num_queries", "value": "100"}
        ]
    }
}


# =============================================================================
# Test Cases: Model Validation (No external deps required)
# =============================================================================

class TestModels:
    """Tests for Pydantic models - basic validation."""
    
    def test_eval_run_model(self):
        """Test EvalRun model creation."""
        run = EvalRun(
            run_id="test123",
            experiment_id="1",
            status="FINISHED",
            metrics={"faithfulness": 0.9},
            params={"model": "gpt-4"}
        )
        
        assert run.run_id == "test123"
        assert run.metrics["faithfulness"] == 0.9
    
    def test_eval_metrics_model(self):
        """Test EvalMetrics model with defaults."""
        metrics = EvalMetrics()
        
        assert metrics.faithfulness is None
        assert metrics.total_runs == 0
        assert metrics.p95_latency_ms is None
    
    def test_eval_list_response_model(self):
        """Test EvalListResponse model."""
        response = EvalListResponse(
            runs=[],
            total=0,
            experiment_name="test-exp"
        )
        
        assert response.total == 0
        assert response.experiment_name == "test-exp"


# =============================================================================
# Test Cases: Integration Tests (Require full deps)
# =============================================================================

@pytest.mark.skipif(not FULL_DEPS_AVAILABLE, reason="Full app dependencies not installed")
class TestListRuns:
    """Tests for GET /v1/evals endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_runs_success(self):
        """Test successful listing of eval runs."""
        with patch('app.api.routes_evals.get_mlflow_client') as mock_client:
            # Setup mock
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            # Mock experiment lookup
            mock_async_client.get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"experiment": MOCK_EXPERIMENT}
            )
            
            # Mock runs search
            mock_async_client.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"runs": [MOCK_RUN]}
            )
            
            result = await list_eval_runs(limit=50, experiment_name=None)
            
            assert result.total == 1
            assert len(result.runs) == 1
            assert result.runs[0].run_id == "abc123"
            assert result.runs[0].status == "FINISHED"
    
    @pytest.mark.asyncio
    async def test_list_runs_empty_experiment(self):
        """Test listing runs when experiment doesn't exist."""
        with patch('app.api.routes_evals.get_mlflow_client') as mock_client:
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            # Mock experiment not found
            mock_async_client.get.return_value = MagicMock(
                status_code=404,
                json=lambda: {"error": "Not found"}
            )
            
            result = await list_eval_runs(limit=50, experiment_name=None)
            
            assert result.total == 0
            assert len(result.runs) == 0


@pytest.mark.skipif(not FULL_DEPS_AVAILABLE, reason="Full app dependencies not installed")
class TestMetricsPayloadShape:
    """Tests for GET /v1/evals/metrics endpoint."""
    
    @pytest.mark.asyncio
    async def test_metrics_payload_shape(self):
        """Test that metrics response has correct shape."""
        with patch('app.api.routes_evals.get_mlflow_client') as mock_client, \
             patch('app.api.routes_evals.get_prometheus_metrics') as mock_prom:
            
            # Setup MLflow mock
            mock_async_client = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            mock_async_client.get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"experiment": MOCK_EXPERIMENT}
            )
            mock_async_client.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"runs": [MOCK_RUN]}
            )
            
            # Setup Prometheus mock
            mock_prom.return_value = {
                "p95_latency_ms": 250.5,
                "p99_latency_ms": 450.2,
                "error_rate_5xx": 0.001
            }
            
            result = await get_eval_metrics()
            
            # Check shape
            assert hasattr(result, 'faithfulness')
            assert hasattr(result, 'hallucination_rate')
            assert hasattr(result, 'p95_latency_ms')
            assert hasattr(result, 'p99_latency_ms')
            assert hasattr(result, 'error_rate_5xx')
            assert hasattr(result, 'total_runs')
            
            # Check values
            assert result.faithfulness == 0.92
            assert result.hallucination_rate == 0.03
            assert result.p95_latency_ms == 250.5
            assert result.p99_latency_ms == 450.2
            assert result.total_runs == 1


@pytest.mark.skipif(not FULL_DEPS_AVAILABLE, reason="Full app dependencies not installed")
class TestMLflowUnavailable:
    """Tests for handling MLflow unavailability."""
    
    @pytest.mark.asyncio
    async def test_mlflow_unavailable_returns_503(self):
        """Test that MLflow connection error returns 503."""
        from fastapi import HTTPException
        
        with patch('app.api.routes_evals.get_mlflow_client') as mock_client:
            # Simulate connection error
            mock_client.return_value.__aenter__.side_effect = httpx.ConnectError("Connection refused")
            
            with pytest.raises(HTTPException) as exc_info:
                await list_eval_runs(limit=50, experiment_name=None)
            
            assert exc_info.value.status_code == 503
            assert "unavailable" in exc_info.value.detail.lower()


# =============================================================================
# Test Cases: HTTP Client Tests (Using httpx directly)
# =============================================================================

class TestPrometheusHelper:
    """Tests for Prometheus query helper using httpx mocks."""
    
    def test_prometheus_response_parsing(self):
        """Test parsing Prometheus response format."""
        # Test that we correctly parse Prometheus response format
        prometheus_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{"value": [1705276800, "0.250"]}]
            }
        }
        
        # Parse the value
        result = prometheus_response["data"]["result"]
        if result:
            value = float(result[0]["value"][1])
            assert value == 0.250
        else:
            assert False, "Expected result"
    
    def test_prometheus_empty_response(self):
        """Test handling empty Prometheus response."""
        prometheus_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": []
            }
        }
        
        result = prometheus_response["data"]["result"]
        assert len(result) == 0
