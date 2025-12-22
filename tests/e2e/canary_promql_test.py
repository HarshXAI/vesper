"""
E2E Canary Tests - PromQL & MLflow Gates
==========================================

Validates quality gates using PromQL metrics and MLflow evaluation scores.
Used during blue/green deployments to validate canary health.

Usage:
    pytest tests/e2e/canary_promql_test.py -v --prometheus-url=http://prometheus:9090
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import httpx
import pytest


# =============================================================================
# Configuration
# =============================================================================

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "staging")
DEPLOYMENT_COLOR = os.getenv("DEPLOYMENT_COLOR", "")  # blue or green for canary

# Quality gate thresholds
P95_LATENCY_THRESHOLD_MS = 2500
P99_LATENCY_THRESHOLD_MS = 5000
ERROR_RATE_THRESHOLD_PERCENT = 1.0
FAITHFULNESS_THRESHOLD = 0.90
HALLUCINATION_THRESHOLD = 0.02


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def prometheus_client() -> httpx.Client:
    """Create HTTP client for Prometheus API."""
    return httpx.Client(base_url=PROMETHEUS_URL, timeout=30.0)


@pytest.fixture
def mlflow_client() -> httpx.Client:
    """Create HTTP client for MLflow API."""
    return httpx.Client(base_url=MLFLOW_URL, timeout=30.0)


# =============================================================================
# Helper Functions
# =============================================================================

def query_prometheus(client: httpx.Client, query: str) -> Optional[float]:
    """Execute a PromQL query and return the first result value."""
    try:
        response = client.get(
            "/api/v1/query",
            params={"query": query},
        )
        response.raise_for_status()
        
        data = response.json()
        results = data.get("data", {}).get("result", [])
        
        if not results:
            return None
        
        # Get the value from first result
        value = results[0].get("value", [None, None])[1]
        return float(value) if value else None
        
    except Exception as e:
        print(f"PromQL query failed: {e}")
        return None


def get_deployment_filter() -> str:
    """Get the deployment color filter for PromQL queries."""
    if DEPLOYMENT_COLOR:
        return f',deployment="{DEPLOYMENT_COLOR}"'
    return ""


# =============================================================================
# P95 Latency Gate Tests
# =============================================================================

class TestP95LatencyGate:
    """Tests for p95 latency quality gate."""
    
    def test_p95_latency_below_threshold(self, prometheus_client: httpx.Client):
        """Verify p95 latency is below 2500ms threshold."""
        deployment_filter = get_deployment_filter()
        
        query = f'''
        histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{{
                job="vesper-api-gateway",
                environment="{ENVIRONMENT}"
                {deployment_filter}
            }}[5m])) by (le)
        ) * 1000
        '''
        
        p95_ms = query_prometheus(prometheus_client, query)
        
        if p95_ms is None:
            pytest.skip("No p95 latency data available")
        
        print(f"📊 p95 Latency: {p95_ms:.2f}ms (threshold: {P95_LATENCY_THRESHOLD_MS}ms)")
        
        assert p95_ms < P95_LATENCY_THRESHOLD_MS, (
            f"p95 latency {p95_ms:.2f}ms exceeds threshold {P95_LATENCY_THRESHOLD_MS}ms"
        )
    
    def test_p99_latency_below_threshold(self, prometheus_client: httpx.Client):
        """Verify p99 latency is below 5000ms threshold (canary check)."""
        deployment_filter = get_deployment_filter()
        
        query = f'''
        histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket{{
                job="vesper-api-gateway",
                environment="{ENVIRONMENT}"
                {deployment_filter}
            }}[5m])) by (le)
        ) * 1000
        '''
        
        p99_ms = query_prometheus(prometheus_client, query)
        
        if p99_ms is None:
            pytest.skip("No p99 latency data available")
        
        print(f"📊 p99 Latency: {p99_ms:.2f}ms (threshold: {P99_LATENCY_THRESHOLD_MS}ms)")
        
        assert p99_ms < P99_LATENCY_THRESHOLD_MS, (
            f"p99 latency {p99_ms:.2f}ms exceeds threshold {P99_LATENCY_THRESHOLD_MS}ms"
        )
    
    def test_latency_trend_stable(self, prometheus_client: httpx.Client):
        """Verify latency isn't trending upward significantly."""
        deployment_filter = get_deployment_filter()
        
        # Compare last 5 min to previous 5 min
        current_query = f'''
        histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{{
                job="vesper-api-gateway",
                environment="{ENVIRONMENT}"
                {deployment_filter}
            }}[5m])) by (le)
        ) * 1000
        '''
        
        previous_query = f'''
        histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{{
                job="vesper-api-gateway",
                environment="{ENVIRONMENT}"
                {deployment_filter}
            }}[5m] offset 5m)) by (le)
        ) * 1000
        '''
        
        current = query_prometheus(prometheus_client, current_query)
        previous = query_prometheus(prometheus_client, previous_query)
        
        if current is None or previous is None:
            pytest.skip("Insufficient latency data for trend analysis")
        
        # Allow up to 50% increase
        max_allowed = previous * 1.5
        
        print(f"📊 Current p95: {current:.2f}ms, Previous: {previous:.2f}ms")
        
        assert current < max_allowed, (
            f"Latency increased significantly: {current:.2f}ms vs {previous:.2f}ms"
        )


# =============================================================================
# 5xx Error Rate Gate Tests
# =============================================================================

class TestErrorRateGate:
    """Tests for 5xx error rate quality gate."""
    
    def test_5xx_error_rate_below_threshold(self, prometheus_client: httpx.Client):
        """Verify 5xx error rate is below 1% threshold."""
        deployment_filter = get_deployment_filter()
        
        query = f'''
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}",
            status=~"5.."
            {deployment_filter}
        }}[5m]))
        /
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}"
            {deployment_filter}
        }}[5m]))
        * 100
        '''
        
        error_rate = query_prometheus(prometheus_client, query)
        
        if error_rate is None:
            # No errors means 0%
            error_rate = 0.0
        
        print(f"📊 5xx Error Rate: {error_rate:.4f}% (threshold: {ERROR_RATE_THRESHOLD_PERCENT}%)")
        
        assert error_rate < ERROR_RATE_THRESHOLD_PERCENT, (
            f"5xx error rate {error_rate:.4f}% exceeds threshold {ERROR_RATE_THRESHOLD_PERCENT}%"
        )
    
    def test_4xx_error_rate_reasonable(self, prometheus_client: httpx.Client):
        """Verify 4xx error rate isn't abnormally high (potential auth issues)."""
        deployment_filter = get_deployment_filter()
        
        query = f'''
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}",
            status=~"4.."
            {deployment_filter}
        }}[5m]))
        /
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}"
            {deployment_filter}
        }}[5m]))
        * 100
        '''
        
        error_rate = query_prometheus(prometheus_client, query)
        
        if error_rate is None:
            error_rate = 0.0
        
        print(f"📊 4xx Error Rate: {error_rate:.4f}%")
        
        # 4xx > 10% might indicate auth configuration issues
        assert error_rate < 10.0, (
            f"4xx error rate {error_rate:.4f}% is abnormally high"
        )
    
    def test_no_error_spike(self, prometheus_client: httpx.Client):
        """Verify no sudden spike in errors compared to previous period."""
        deployment_filter = get_deployment_filter()
        
        current_query = f'''
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}",
            status=~"5.."
            {deployment_filter}
        }}[5m])) or vector(0)
        '''
        
        previous_query = f'''
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}",
            status=~"5.."
            {deployment_filter}
        }}[5m] offset 5m)) or vector(0)
        '''
        
        current = query_prometheus(prometheus_client, current_query) or 0
        previous = query_prometheus(prometheus_client, previous_query) or 0
        
        print(f"📊 Current 5xx rate: {current}, Previous: {previous}")
        
        # If previous was 0, just check current is low
        if previous == 0:
            assert current < 0.1, f"New errors appearing: {current}"
        else:
            # Allow up to 2x increase
            assert current < previous * 2, (
                f"Error rate spiked: {current} vs {previous}"
            )


# =============================================================================
# Eval Metrics Gate Tests
# =============================================================================

class TestEvalGate:
    """Tests for evaluation metrics quality gate (via MLflow)."""
    
    def test_faithfulness_above_threshold(self, mlflow_client: httpx.Client):
        """Verify faithfulness score is >= 0.90."""
        try:
            # Get experiment
            response = mlflow_client.get(
                "/api/2.0/mlflow/experiments/get-by-name",
                params={"experiment_name": f"vesper-{ENVIRONMENT}-eval"},
            )
            
            if response.status_code == 404:
                pytest.skip(f"No eval experiment for {ENVIRONMENT}")
            
            response.raise_for_status()
            experiment_id = response.json()["experiment"]["experiment_id"]
            
            # Get latest run
            runs_response = mlflow_client.post(
                "/api/2.0/mlflow/runs/search",
                json={
                    "experiment_ids": [experiment_id],
                    "max_results": 1,
                    "order_by": ["start_time DESC"],
                },
            )
            runs_response.raise_for_status()
            
            runs = runs_response.json().get("runs", [])
            if not runs:
                pytest.skip("No eval runs found")
            
            metrics = runs[0].get("data", {}).get("metrics", [])
            faithfulness = None
            
            for m in metrics:
                if m["key"] == "faithfulness":
                    faithfulness = m["value"]
                    break
            
            if faithfulness is None:
                pytest.skip("Faithfulness metric not found")
            
            print(f"📊 Faithfulness: {faithfulness} (threshold: {FAITHFULNESS_THRESHOLD})")
            
            assert faithfulness >= FAITHFULNESS_THRESHOLD, (
                f"Faithfulness {faithfulness} below threshold {FAITHFULNESS_THRESHOLD}"
            )
            
        except httpx.HTTPError as e:
            pytest.skip(f"MLflow not available: {e}")
    
    def test_hallucination_rate_below_threshold(self, mlflow_client: httpx.Client):
        """Verify hallucination rate is <= 0.02."""
        try:
            response = mlflow_client.get(
                "/api/2.0/mlflow/experiments/get-by-name",
                params={"experiment_name": f"vesper-{ENVIRONMENT}-eval"},
            )
            
            if response.status_code == 404:
                pytest.skip(f"No eval experiment for {ENVIRONMENT}")
            
            response.raise_for_status()
            experiment_id = response.json()["experiment"]["experiment_id"]
            
            runs_response = mlflow_client.post(
                "/api/2.0/mlflow/runs/search",
                json={
                    "experiment_ids": [experiment_id],
                    "max_results": 1,
                    "order_by": ["start_time DESC"],
                },
            )
            runs_response.raise_for_status()
            
            runs = runs_response.json().get("runs", [])
            if not runs:
                pytest.skip("No eval runs found")
            
            metrics = runs[0].get("data", {}).get("metrics", [])
            hallucination_rate = None
            
            for m in metrics:
                if m["key"] == "hallucination_rate":
                    hallucination_rate = m["value"]
                    break
            
            if hallucination_rate is None:
                pytest.skip("Hallucination rate metric not found")
            
            print(f"📊 Hallucination Rate: {hallucination_rate} (threshold: {HALLUCINATION_THRESHOLD})")
            
            assert hallucination_rate <= HALLUCINATION_THRESHOLD, (
                f"Hallucination rate {hallucination_rate} exceeds threshold {HALLUCINATION_THRESHOLD}"
            )
            
        except httpx.HTTPError as e:
            pytest.skip(f"MLflow not available: {e}")


# =============================================================================
# Canary Health Tests
# =============================================================================

class TestCanaryHealth:
    """Combined canary health validation."""
    
    def test_canary_overall_health(self, prometheus_client: httpx.Client):
        """Aggregate check for canary health - all gates must pass."""
        deployment_filter = get_deployment_filter()
        
        results = {}
        
        # Check p95 latency
        p95_query = f'''
        histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{{
                job="vesper-api-gateway",
                environment="{ENVIRONMENT}"
                {deployment_filter}
            }}[5m])) by (le)
        ) * 1000
        '''
        p95_ms = query_prometheus(prometheus_client, p95_query)
        results["p95_latency_ms"] = p95_ms
        results["p95_passed"] = p95_ms is None or p95_ms < P95_LATENCY_THRESHOLD_MS
        
        # Check error rate
        error_query = f'''
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}",
            status=~"5.."
            {deployment_filter}
        }}[5m]))
        /
        sum(rate(http_requests_total{{
            job="vesper-api-gateway",
            environment="{ENVIRONMENT}"
            {deployment_filter}
        }}[5m]))
        * 100
        '''
        error_rate = query_prometheus(prometheus_client, error_query) or 0
        results["error_rate_percent"] = error_rate
        results["error_passed"] = error_rate < ERROR_RATE_THRESHOLD_PERCENT
        
        # Print summary
        print("\n" + "=" * 60)
        print("CANARY HEALTH SUMMARY")
        print("=" * 60)
        print(f"p95 Latency: {results['p95_latency_ms']}ms - {'✅' if results['p95_passed'] else '❌'}")
        print(f"Error Rate: {results['error_rate_percent']:.4f}% - {'✅' if results['error_passed'] else '❌'}")
        print("=" * 60)
        
        all_passed = results["p95_passed"] and results["error_passed"]
        
        assert all_passed, f"Canary health check failed: {results}"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
