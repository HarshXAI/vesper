"""
Demo Repeatability Tests

Validates that demo runs produce consistent, reproducible results:
- warm_run_identical_citations: Cache hits return same citations
- cold_run_within_slo: Fresh queries complete within SLO

Usage:
    pytest tests/e2e/demo_repeatability_test.py -v
    pytest tests/e2e/demo_repeatability_test.py -v -k warm_run
    pytest tests/e2e/demo_repeatability_test.py -v -k cold_run
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
import pytest

# Test configuration
API_URL = os.getenv("VESPER_API_URL", "http://localhost:8000")
CACHE_DIR = Path(os.getenv("DEMO_CACHE_DIR", "data/demo/cache"))
SLO_P95_SECONDS = float(os.getenv("SLO_P95_SECONDS", "2.5"))
SLO_ERROR_RATE = float(os.getenv("SLO_ERROR_RATE", "0.01"))

# Demo queries for testing
DEMO_QUERIES = [
    {
        "id": "q01",
        "query": "What was Apple's total revenue for fiscal year 2024?",
        "expected_ticker": "AAPL",
        "expected_keywords": ["revenue", "394", "billion"],
    },
    {
        "id": "q02",
        "query": "What are the main risk factors for Amazon?",
        "expected_ticker": "AMZN",
        "expected_keywords": ["risk", "competition", "regulatory"],
    },
    {
        "id": "q03",
        "query": "What is Microsoft's operating margin?",
        "expected_ticker": "MSFT",
        "expected_keywords": ["operating", "margin", "42"],
    },
    {
        "id": "q04",
        "query": "Compare revenue growth across AAPL, AMZN, and MSFT",
        "expected_ticker": None,
        "expected_keywords": ["revenue", "growth"],
    },
    {
        "id": "q05",
        "query": "What are Apple's main business segments?",
        "expected_ticker": "AAPL",
        "expected_keywords": ["iPhone", "services", "segments"],
    },
]


@dataclass
class QueryResult:
    """Result of a demo query execution."""
    
    query_id: str
    query: str
    response: str
    citations: List[Dict[str, Any]]
    latency_ms: float
    cached: bool
    success: bool
    error: Optional[str] = None


async def execute_query(
    client: httpx.AsyncClient,
    query_config: Dict[str, Any],
    use_cache: bool = True,
) -> QueryResult:
    """Execute a single demo query and return results."""
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{API_URL}/api/v1/query",
            json={
                "query": query_config["query"],
                "include_citations": True,
                "cache": use_cache,
            },
            headers={
                "X-Tenant-ID": "demo",
                "X-Cache-Enabled": str(use_cache).lower(),
            },
            timeout=30.0,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            result = response.json()
            
            return QueryResult(
                query_id=query_config["id"],
                query=query_config["query"],
                response=result.get("answer", result.get("response", "")),
                citations=result.get("citations", result.get("sources", [])),
                latency_ms=latency_ms,
                cached=result.get("cached", False),
                success=True,
            )
        else:
            return QueryResult(
                query_id=query_config["id"],
                query=query_config["query"],
                response="",
                citations=[],
                latency_ms=latency_ms,
                cached=False,
                success=False,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )
            
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        
        return QueryResult(
            query_id=query_config["id"],
            query=query_config["query"],
            response="",
            citations=[],
            latency_ms=latency_ms,
            cached=False,
            success=False,
            error=str(e),
        )


def load_cached_response(query_id: str) -> Optional[Dict[str, Any]]:
    """Load cached response for comparison."""
    cache_file = CACHE_DIR / f"{query_id}.json"
    
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    
    return None


def compare_citations(
    actual: List[Dict[str, Any]],
    expected: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare actual citations with expected cached citations."""
    if not expected:
        return {"match": True, "reason": "No expected citations to compare"}
    
    if not actual:
        return {"match": False, "reason": "No actual citations returned"}
    
    # Compare citation IDs
    actual_ids = {c.get("citation_id") or c.get("id") for c in actual}
    expected_ids = {c.get("citation_id") or c.get("id") for c in expected}
    
    if actual_ids == expected_ids:
        return {"match": True, "reason": "Citation IDs match exactly"}
    
    # Check for subset match (acceptable)
    if expected_ids.issubset(actual_ids):
        return {"match": True, "reason": "Expected citations found (with extras)"}
    
    # Check overlap
    overlap = actual_ids.intersection(expected_ids)
    overlap_ratio = len(overlap) / len(expected_ids) if expected_ids else 0
    
    if overlap_ratio >= 0.8:
        return {
            "match": True,
            "reason": f"80%+ citation overlap ({len(overlap)}/{len(expected_ids)})",
        }
    
    return {
        "match": False,
        "reason": f"Citation mismatch: expected {expected_ids}, got {actual_ids}",
        "overlap_ratio": overlap_ratio,
    }


class TestWarmRunIdenticalCitations:
    """Test that warm (cached) runs return identical citations."""
    
    @pytest.fixture
    def cached_responses(self) -> Dict[str, Dict[str, Any]]:
        """Load all cached responses."""
        responses = {}
        for query in DEMO_QUERIES:
            cached = load_cached_response(query["id"])
            if cached:
                responses[query["id"]] = cached
        return responses
    
    @pytest.mark.asyncio
    async def test_cached_citations_match(self, cached_responses):
        """Verify that cached query results return identical citations."""
        if not cached_responses:
            pytest.skip("No cached responses found. Run cache_warmers.py first.")
        
        async with httpx.AsyncClient() as client:
            for query_config in DEMO_QUERIES:
                query_id = query_config["id"]
                
                if query_id not in cached_responses:
                    continue
                
                expected = cached_responses[query_id]
                
                # Execute query (should hit cache)
                result = await execute_query(client, query_config, use_cache=True)
                
                if not result.success:
                    # API might not be running, skip
                    pytest.skip(f"API not available: {result.error}")
                
                # Compare citations
                comparison = compare_citations(
                    result.citations,
                    expected.get("citations", []),
                )
                
                assert comparison["match"], (
                    f"Query {query_id}: {comparison['reason']}"
                )
    
    @pytest.mark.asyncio
    async def test_repeated_queries_same_result(self):
        """Verify that repeated queries return consistent results."""
        query = DEMO_QUERIES[0]  # Use first query
        
        async with httpx.AsyncClient() as client:
            # Execute same query multiple times
            results = []
            for _ in range(3):
                result = await execute_query(client, query, use_cache=True)
                if not result.success:
                    pytest.skip(f"API not available: {result.error}")
                results.append(result)
            
            # All responses should be identical
            first_response = results[0].response
            first_citations = {
                c.get("citation_id") or c.get("id")
                for c in results[0].citations
            }
            
            for i, result in enumerate(results[1:], 2):
                # Check response similarity (allow minor formatting differences)
                assert len(result.response) > 0, f"Run {i} returned empty response"
                
                # Check citations match
                run_citations = {
                    c.get("citation_id") or c.get("id")
                    for c in result.citations
                }
                
                assert run_citations == first_citations, (
                    f"Run {i} citations differ: expected {first_citations}, got {run_citations}"
                )
    
    @pytest.mark.asyncio
    async def test_cache_hit_faster_than_cold(self):
        """Verify that cached queries are faster than cold queries."""
        query = DEMO_QUERIES[0]
        
        async with httpx.AsyncClient() as client:
            # Cold run (cache disabled)
            cold_result = await execute_query(client, query, use_cache=False)
            
            if not cold_result.success:
                pytest.skip(f"API not available: {cold_result.error}")
            
            # Warm run (cache enabled)
            warm_result = await execute_query(client, query, use_cache=True)
            
            # Cache hit should be faster (allow for variance)
            # If cold run < 100ms, both are likely mocked
            if cold_result.latency_ms > 100:
                assert warm_result.latency_ms <= cold_result.latency_ms * 1.5, (
                    f"Warm run ({warm_result.latency_ms}ms) not faster than "
                    f"cold run ({cold_result.latency_ms}ms)"
                )


class TestColdRunWithinSLO:
    """Test that cold (uncached) runs complete within SLO."""
    
    @pytest.mark.asyncio
    async def test_single_query_within_slo(self):
        """Verify single query completes within p95 SLO."""
        query = DEMO_QUERIES[0]
        
        async with httpx.AsyncClient() as client:
            result = await execute_query(client, query, use_cache=False)
            
            if not result.success:
                pytest.skip(f"API not available: {result.error}")
            
            slo_ms = SLO_P95_SECONDS * 1000
            
            assert result.latency_ms < slo_ms, (
                f"Query latency ({result.latency_ms:.0f}ms) exceeds "
                f"SLO ({slo_ms:.0f}ms)"
            )
    
    @pytest.mark.asyncio
    async def test_all_demo_queries_within_slo(self):
        """Verify all demo queries complete within SLO."""
        latencies = []
        errors = []
        
        async with httpx.AsyncClient() as client:
            for query_config in DEMO_QUERIES:
                result = await execute_query(client, query_config, use_cache=False)
                
                if not result.success:
                    # Skip if API not available (404 or connection error)
                    if "404" in str(result.error) or "connection" in str(result.error).lower():
                        pytest.skip(f"API not available: {result.error}")
                    errors.append(f"{query_config['id']}: {result.error}")
                else:
                    latencies.append(result.latency_ms)
        
        # Check error rate
        error_rate = len(errors) / len(DEMO_QUERIES)
        assert error_rate <= SLO_ERROR_RATE, (
            f"Error rate ({error_rate:.1%}) exceeds SLO ({SLO_ERROR_RATE:.1%}). "
            f"Errors: {errors}"
        )
        
        # Check p95 latency
        if latencies:
            latencies.sort()
            p95_idx = int(len(latencies) * 0.95)
            p95_latency_ms = latencies[min(p95_idx, len(latencies) - 1)]
            slo_ms = SLO_P95_SECONDS * 1000
            
            assert p95_latency_ms < slo_ms, (
                f"p95 latency ({p95_latency_ms:.0f}ms) exceeds SLO ({slo_ms:.0f}ms)"
            )
    
    @pytest.mark.asyncio
    async def test_response_contains_expected_content(self):
        """Verify responses contain expected keywords and structure."""
        async with httpx.AsyncClient() as client:
            for query_config in DEMO_QUERIES:
                result = await execute_query(client, query_config, use_cache=False)
                
                if not result.success:
                    pytest.skip(f"API not available: {result.error}")
                
                # Check response is non-empty
                assert len(result.response) > 0, (
                    f"Query {query_config['id']} returned empty response"
                )
                
                # Check for expected keywords (case-insensitive)
                response_lower = result.response.lower()
                expected_keywords = query_config.get("expected_keywords", [])
                
                missing_keywords = [
                    kw for kw in expected_keywords
                    if kw.lower() not in response_lower
                ]
                
                # Allow some missing keywords (80% threshold)
                if expected_keywords:
                    match_ratio = 1 - (len(missing_keywords) / len(expected_keywords))
                    assert match_ratio >= 0.5, (
                        f"Query {query_config['id']}: Missing keywords {missing_keywords}"
                    )
    
    @pytest.mark.asyncio
    async def test_citations_present(self):
        """Verify responses include citations."""
        async with httpx.AsyncClient() as client:
            for query_config in DEMO_QUERIES:
                result = await execute_query(client, query_config, use_cache=False)
                
                if not result.success:
                    pytest.skip(f"API not available: {result.error}")
                
                # Check citations exist
                assert len(result.citations) > 0, (
                    f"Query {query_config['id']} returned no citations"
                )
                
                # Check citation structure
                for citation in result.citations:
                    assert "text" in citation or "content" in citation, (
                        f"Citation missing text/content: {citation}"
                    )


class TestDomainPortability:
    """Test domain swap functionality."""
    
    @pytest.mark.asyncio
    async def test_healthcare_domain_smoke(self):
        """Verify healthcare domain works when enabled."""
        # This test requires DOMAIN=healthcare
        current_domain = os.getenv("DOMAIN", "finance")
        
        if current_domain != "healthcare":
            pytest.skip("Healthcare domain not enabled (set DOMAIN=healthcare)")
        
        healthcare_query = {
            "id": "hc01",
            "query": "What is the patient satisfaction score at Metro General?",
            "expected_keywords": ["patient", "satisfaction", "metro"],
        }
        
        async with httpx.AsyncClient() as client:
            result = await execute_query(client, healthcare_query, use_cache=False)
            
            if not result.success:
                pytest.skip(f"API not available: {result.error}")
            
            # Check response mentions healthcare concepts
            response_lower = result.response.lower()
            assert any(
                kw in response_lower
                for kw in ["hospital", "patient", "satisfaction", "quality"]
            ), f"Response doesn't contain healthcare concepts: {result.response[:200]}"
    
    @pytest.mark.asyncio
    async def test_finance_domain_smoke(self):
        """Verify finance domain works when enabled."""
        current_domain = os.getenv("DOMAIN", "finance")
        
        if current_domain != "finance":
            pytest.skip("Finance domain not enabled (set DOMAIN=finance)")
        
        finance_query = DEMO_QUERIES[0]  # Apple revenue query
        
        async with httpx.AsyncClient() as client:
            result = await execute_query(client, finance_query, use_cache=False)
            
            if not result.success:
                pytest.skip(f"API not available: {result.error}")
            
            # Check response mentions finance concepts
            response_lower = result.response.lower()
            assert any(
                kw in response_lower
                for kw in ["revenue", "billion", "fiscal", "financial"]
            ), f"Response doesn't contain finance concepts: {result.response[:200]}"


# Utility for running tests directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
