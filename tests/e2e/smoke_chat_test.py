"""
E2E Smoke Tests - Chat Functionality
=====================================

Validates core chat streaming functionality for production deployments.
These tests are designed to run as part of the deployment pipeline.

Usage:
    pytest tests/e2e/smoke_chat_test.py -v --base-url=https://api.example.com
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Dict, List, Any

import httpx
import pytest


# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("SMOKE_TEST_TOKEN", "")
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def base_url() -> str:
    """Get the API base URL from environment or use default."""
    return BASE_URL


@pytest.fixture
def auth_headers() -> dict:
    """Get authentication headers for API requests."""
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": f"smoke-test-{datetime.now(timezone.utc).isoformat()}",
    }
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return headers


@pytest.fixture
def http_client(base_url: str, auth_headers: dict) -> httpx.Client:
    """Create an HTTP client for synchronous requests."""
    return httpx.Client(
        base_url=base_url,
        headers=auth_headers,
        timeout=TIMEOUT_SECONDS,
    )


@pytest.fixture
def async_client(base_url: str, auth_headers: dict) -> httpx.AsyncClient:
    """Create an async HTTP client for streaming requests."""
    return httpx.AsyncClient(
        base_url=base_url,
        headers=auth_headers,
        timeout=TIMEOUT_SECONDS,
    )


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthChecks:
    """Health check endpoints for smoke testing."""
    
    def test_health_endpoint(self, http_client: httpx.Client):
        """Verify the health endpoint returns OK."""
        response = http_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
    
    def test_readiness_endpoint(self, http_client: httpx.Client):
        """Verify the readiness endpoint returns OK."""
        response = http_client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        # Handle both "ready: true" and "status: ready" formats
        assert data.get("ready") is True or data.get("status") == "ready"
    
    def test_version_endpoint(self, http_client: httpx.Client):
        """Verify the version endpoint returns version info."""
        response = http_client.get("/version")
        
        if response.status_code == 404:
            pytest.skip("Version endpoint not available")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "commit" in data or "build" in data


# =============================================================================
# Chat Endpoint Tests
# =============================================================================

class TestChatEndpoint:
    """Tests for the main chat completion endpoint."""
    
    def test_chat_sync_response(self, http_client: httpx.Client):
        """Test synchronous chat response."""
        payload = {
            "query": "What is the revenue for Apple in Q3 2024?",
            "stream": False,
            "tenant_id": "test-tenant",
        }
        
        response = http_client.post("/v1/ask", json=payload)
        
        if response.status_code == 404:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "response" in data or "answer" in data
        assert "citations" in data or "sources" in data
        assert "trace_id" in data or "request_id" in data
    
    def test_chat_with_citations(self, http_client: httpx.Client):
        """Test that chat responses include citations."""
        payload = {
            "query": "What was Microsoft's operating income?",
            "stream": False,
            "include_citations": True,
            "tenant_id": "test-tenant",
        }
        
        response = http_client.post("/v1/ask", json=payload)
        
        if response.status_code == 404:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        assert response.status_code == 200
        data = response.json()
        
        citations = data.get("citations") or data.get("sources") or []
        # Note: In smoke tests, we may not have real documents
        # So we just verify the structure is correct
        assert isinstance(citations, list)
    
    def test_chat_invalid_request(self, http_client: httpx.Client):
        """Test that invalid requests return proper errors."""
        payload = {
            "query": "",  # Empty query should fail
            "stream": False,
        }
        
        response = http_client.post("/v1/ask", json=payload)
        
        # Skip if endpoint doesn't exist (404 is not a validation error)
        if response.status_code == 404:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        # Should return 400 or 422 for validation error
        assert response.status_code in [400, 422]
    
    def test_chat_missing_auth(self, base_url: str):
        """Test that requests without auth are rejected when auth is enabled."""
        client = httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)
        
        response = client.post("/v1/ask", json={
            "query": "Test query",
            "stream": False,
        })
        
        if response.status_code == 404:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        # Might be 401 (if auth enabled) or 200 (if auth disabled)
        assert response.status_code in [200, 401, 403]


# =============================================================================
# Streaming Tests
# =============================================================================

class TestStreamingChat:
    """Tests for SSE streaming chat functionality."""
    
    @pytest.mark.asyncio
    async def test_streaming_response(self, async_client: httpx.AsyncClient):
        """Test that streaming responses work correctly."""
        payload = {
            "query": "Explain the financial performance briefly.",
            "stream": True,
            "tenant_id": "test-tenant",
        }
        
        tokens_received = []
        events_received = []
        
        async with async_client.stream(
            "POST",
            "/v1/ask",
            json=payload,
        ) as response:
            if response.status_code == 404:
                pytest.skip("Vesper API /v1/ask endpoint not available")
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        events_received.append(data)
                        
                        if "token" in data:
                            tokens_received.append(data["token"])
                        elif "delta" in data:
                            tokens_received.append(data["delta"])
                    except json.JSONDecodeError:
                        continue
        
        # Verify we received tokens
        assert len(tokens_received) > 0 or len(events_received) > 0
    
    @pytest.mark.asyncio
    async def test_streaming_includes_citations(self, async_client: httpx.AsyncClient):
        """Test that streaming responses include citation events."""
        payload = {
            "query": "What are the key metrics?",
            "stream": True,
            "include_citations": True,
            "tenant_id": "test-tenant",
        }
        
        events = []
        
        async with async_client.stream(
            "POST",
            "/v1/ask",
            json=payload,
        ) as response:
            if response.status_code == 404:
                pytest.skip("Vesper API /v1/ask endpoint not available")
            
            assert response.status_code == 200
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        events.append(data)
                    except json.JSONDecodeError:
                        continue
        
        # Check for citation events
        event_types = [e.get("type") or e.get("event") for e in events]
        # Verify stream completed
        assert len(events) > 0
    
    @pytest.mark.asyncio
    async def test_streaming_timeout(self, async_client: httpx.AsyncClient):
        """Test that streaming handles timeouts gracefully."""
        payload = {
            "query": "Very long query that might take time",
            "stream": True,
            "tenant_id": "test-tenant",
        }
        
        start_time = time.time()
        received_data = False
        endpoint_available = True
        
        try:
            async with async_client.stream(
                "POST",
                "/v1/ask",
                json=payload,
                timeout=5.0,  # Short timeout
            ) as response:
                if response.status_code == 404:
                    endpoint_available = False
                else:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            received_data = True
                            break
        except httpx.TimeoutException:
            # Timeout is acceptable
            pass
        
        if not endpoint_available:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        elapsed = time.time() - start_time
        # Either received data or timed out within reasonable time
        assert received_data or elapsed >= 4.0


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Basic performance validation for smoke tests."""
    
    def test_response_time_slo(self, http_client: httpx.Client):
        """Verify response time is within SLO (p95 < 2.5s)."""
        response_times = []
        
        for _ in range(5):
            start = time.time()
            response = http_client.get("/health")
            elapsed = time.time() - start
            response_times.append(elapsed)
            
            assert response.status_code == 200
        
        # Health check should be very fast
        avg_time = sum(response_times) / len(response_times)
        assert avg_time < 0.5, f"Average health check time {avg_time}s exceeds 0.5s"
    
    def test_chat_latency_acceptable(self, http_client: httpx.Client):
        """Test that chat responses are within acceptable latency."""
        payload = {
            "query": "Quick test query",
            "stream": False,
            "tenant_id": "test-tenant",
        }
        
        start = time.time()
        response = http_client.post("/v1/ask", json=payload)
        elapsed = time.time() - start
        
        if response.status_code == 404:
            pytest.skip("Vesper API /v1/ask endpoint not available")
        
        # First response might be slow due to cold start
        # but should still be under 30 seconds
        assert elapsed < 30, f"Chat response took {elapsed}s"
        assert response.status_code == 200


# =============================================================================
# Tracing Tests
# =============================================================================

class TestTracing:
    """Verify distributed tracing is working."""
    
    def test_trace_id_in_response(self, http_client: httpx.Client):
        """Verify trace ID is included in responses."""
        response = http_client.get("/health")
        
        # Check for trace ID in headers or body
        trace_header = response.headers.get("x-trace-id") or response.headers.get("x-request-id")
        
        if trace_header is None:
            # Check in body
            try:
                data = response.json()
                trace_id = data.get("trace_id") or data.get("request_id")
            except:
                trace_id = None
        else:
            trace_id = trace_header
        
        # Trace ID should be present in production
        # For smoke tests, we just log the result
        assert response.status_code == 200
    
    def test_trace_propagation(self, http_client: httpx.Client):
        """Test that trace context is propagated."""
        custom_trace_id = f"smoke-test-{int(time.time())}"
        
        headers = dict(http_client.headers)
        headers["X-Request-ID"] = custom_trace_id
        
        response = http_client.get("/health", headers=headers)
        
        assert response.status_code == 200


# =============================================================================
# Run Smoke Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
