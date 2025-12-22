"""
E2E Test Configuration and Fixtures.

Provides shared fixtures for E2E tests including HTTP clients,
environment configuration, and test helpers.
"""

import os
import pytest
import httpx
from typing import Generator, AsyncGenerator


# =============================================================================
# Environment Configuration
# =============================================================================

def get_api_base_url() -> str:
    """Get the API base URL from environment."""
    return os.getenv("VESPER_API_BASE", os.getenv("API_BASE_URL", "http://localhost:8000"))


def get_mlflow_url() -> str:
    """Get MLflow URL from environment."""
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def get_prometheus_url() -> str:
    """Get Prometheus URL from environment."""
    return os.getenv("PROM_URL", os.getenv("PROMETHEUS_URL", "http://localhost:9090"))


def get_airflow_url() -> str:
    """Get Airflow URL from environment."""
    return os.getenv("AIRFLOW_URL", os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080"))


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest.fixture
def api_base_url() -> str:
    """Provide API base URL."""
    return get_api_base_url()


@pytest.fixture
def mlflow_url() -> str:
    """Provide MLflow URL."""
    return get_mlflow_url()


@pytest.fixture
def prometheus_url() -> str:
    """Provide Prometheus URL."""
    return get_prometheus_url()


@pytest.fixture
def airflow_url() -> str:
    """Provide Airflow URL."""
    return get_airflow_url()


@pytest.fixture
def http_client(api_base_url: str) -> Generator[httpx.Client, None, None]:
    """Create synchronous HTTP client for API tests."""
    with httpx.Client(
        base_url=api_base_url,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def async_client(api_base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for streaming tests."""
    async with httpx.AsyncClient(
        base_url=api_base_url,
        timeout=60.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
def mlflow_client(mlflow_url: str) -> Generator[httpx.Client, None, None]:
    """Create HTTP client for MLflow API."""
    with httpx.Client(
        base_url=mlflow_url,
        timeout=30.0
    ) as client:
        yield client


@pytest.fixture
def prometheus_client(prometheus_url: str) -> Generator[httpx.Client, None, None]:
    """Create HTTP client for Prometheus API."""
    with httpx.Client(
        base_url=prometheus_url,
        timeout=30.0
    ) as client:
        yield client


@pytest.fixture
def airflow_client(airflow_url: str) -> Generator[httpx.Client, None, None]:
    """Create HTTP client for Airflow API."""
    # Airflow uses basic auth by default
    auth = None
    airflow_user = os.getenv("AIRFLOW_USER", "admin")
    airflow_pass = os.getenv("AIRFLOW_PASSWORD", "admin")
    if airflow_user and airflow_pass:
        auth = (airflow_user, airflow_pass)
    
    with httpx.Client(
        base_url=airflow_url,
        timeout=30.0,
        auth=auth
    ) as client:
        yield client


# =============================================================================
# Service Health Check Fixtures
# =============================================================================

@pytest.fixture
def api_available(http_client: httpx.Client) -> bool:
    """Check if API is available."""
    try:
        response = http_client.get("/health")
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def vesper_api_available(http_client: httpx.Client) -> bool:
    """Check if Vesper /v1/ask endpoint is available."""
    try:
        response = http_client.post("/v1/ask", json={"query": "test", "tenant_id": "test"})
        # 200 or 401/403 means endpoint exists
        return response.status_code != 404
    except Exception:
        return False


@pytest.fixture
def mlflow_available(mlflow_url: str) -> bool:
    """Check if MLflow is available."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{mlflow_url}/health")
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def prometheus_available(prometheus_url: str) -> bool:
    """Check if Prometheus is available."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{prometheus_url}/-/healthy")
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def airflow_available(airflow_url: str) -> bool:
    """Check if Airflow is available."""
    try:
        with httpx.Client(timeout=5.0, auth=("admin", "admin")) as client:
            response = client.get(f"{airflow_url}/health")
            return response.status_code == 200
    except Exception:
        return False


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def demo_query() -> dict:
    """Provide a demo query for testing."""
    return {
        "query": "What was Apple's total revenue for fiscal year 2024?",
        "tenant_id": "demo",
        "stream": True
    }


@pytest.fixture
def auth_headers() -> dict:
    """Provide authentication headers."""
    token = os.getenv("SMOKE_TEST_TOKEN", os.getenv("TEST_JWT_TOKEN", ""))
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
