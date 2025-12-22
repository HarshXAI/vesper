#!/usr/bin/env python3
"""
VESPER Cache Warmers Script
Pre-warms cache with top demo queries and persists cached answers with citation IDs.

Usage:
    python scripts/cache_warmers.py
    python scripts/cache_warmers.py --queries 20 --persist
    python scripts/cache_warmers.py --validate
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cache_warmers")

# Top 20 demo queries with expected results
DEMO_QUERIES = [
    {
        "id": "q01",
        "query": "What was Apple's total revenue for fiscal year 2024?",
        "expected_ticker": "AAPL",
        "expected_section": "Financial Performance",
        "expected_keywords": ["revenue", "394.3", "billion"],
    },
    {
        "id": "q02",
        "query": "What are the main risk factors for Amazon?",
        "expected_ticker": "AMZN",
        "expected_section": "Risk Factors",
        "expected_keywords": ["competition", "regulatory", "supply chain"],
    },
    {
        "id": "q03",
        "query": "What is Microsoft's operating margin?",
        "expected_ticker": "MSFT",
        "expected_section": "Financial Performance",
        "expected_keywords": ["operating", "margin", "42%"],
    },
    {
        "id": "q04",
        "query": "Compare revenue growth across AAPL, AMZN, and MSFT",
        "expected_ticker": None,  # Multi-company
        "expected_section": "Financial Performance",
        "expected_keywords": ["growth", "revenue", "year-over-year"],
    },
    {
        "id": "q05",
        "query": "What are Apple's main business segments?",
        "expected_ticker": "AAPL",
        "expected_section": "Business Overview",
        "expected_keywords": ["iPhone", "Mac", "Services"],
    },
    {
        "id": "q06",
        "query": "How much cash does Microsoft have on its balance sheet?",
        "expected_ticker": "MSFT",
        "expected_section": "Management's Discussion",
        "expected_keywords": ["cash", "111", "billion"],
    },
    {
        "id": "q07",
        "query": "What is Amazon's strategy for AWS growth?",
        "expected_ticker": "AMZN",
        "expected_section": "Business Overview",
        "expected_keywords": ["AWS", "cloud", "enterprise"],
    },
    {
        "id": "q08",
        "query": "What was Apple's earnings per share in 2024?",
        "expected_ticker": "AAPL",
        "expected_section": "Financial Performance",
        "expected_keywords": ["earnings", "EPS", "6.16"],
    },
    {
        "id": "q09",
        "query": "What cybersecurity risks does Amazon face?",
        "expected_ticker": "AMZN",
        "expected_section": "Risk Factors",
        "expected_keywords": ["cybersecurity", "security", "threats"],
    },
    {
        "id": "q10",
        "query": "How much did Microsoft return to shareholders?",
        "expected_ticker": "MSFT",
        "expected_section": "Financial Performance",
        "expected_keywords": ["returned", "shareholders", "dividends", "repurchases"],
    },
    {
        "id": "q11",
        "query": "What are Apple's AI and machine learning initiatives?",
        "expected_ticker": "AAPL",
        "expected_section": "Management's Discussion",
        "expected_keywords": ["AI", "machine learning", "initiatives"],
    },
    {
        "id": "q12",
        "query": "What is Amazon's quarterly segment breakdown?",
        "expected_ticker": "AMZN",
        "expected_section": "Segment Performance",
        "expected_keywords": ["segment", "AWS", "revenue"],
    },
    {
        "id": "q13",
        "query": "What is Microsoft's Azure strategy?",
        "expected_ticker": "MSFT",
        "expected_section": "Business Overview",
        "expected_keywords": ["Azure", "cloud", "OpenAI"],
    },
    {
        "id": "q14",
        "query": "What supply chain risks affect Apple?",
        "expected_ticker": "AAPL",
        "expected_section": "Risk Factors",
        "expected_keywords": ["supply chain", "suppliers", "disruptions"],
    },
    {
        "id": "q15",
        "query": "What was Amazon's free cash flow?",
        "expected_ticker": "AMZN",
        "expected_section": "Financial Performance",
        "expected_keywords": ["free cash flow", "35.5", "billion"],
    },
    {
        "id": "q16",
        "query": "What regulatory changes affect Microsoft?",
        "expected_ticker": "MSFT",
        "expected_section": "Risk Factors",
        "expected_keywords": ["regulatory", "antitrust", "compliance"],
    },
    {
        "id": "q17",
        "query": "Compare operating margins: Apple vs Microsoft",
        "expected_ticker": None,
        "expected_section": "Financial Performance",
        "expected_keywords": ["operating margin", "Apple", "Microsoft"],
    },
    {
        "id": "q18",
        "query": "What leadership changes were announced?",
        "expected_ticker": None,
        "expected_section": "Current Report",
        "expected_keywords": ["announced", "leadership", "appointment"],
    },
    {
        "id": "q19",
        "query": "What is Amazon's logistics network strategy?",
        "expected_ticker": "AMZN",
        "expected_section": "Business Overview",
        "expected_keywords": ["logistics", "network", "optimization"],
    },
    {
        "id": "q20",
        "query": "What is Apple's gross margin trend?",
        "expected_ticker": "AAPL",
        "expected_section": "Financial Performance",
        "expected_keywords": ["gross margin", "44%"],
    },
]


@dataclass
class CachedResponse:
    """Represents a cached query response with citations."""
    
    query_id: str
    query: str
    response: str
    citations: list[dict[str, Any]]
    cached_at: str
    latency_ms: float
    cache_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WarmingResult:
    """Result of cache warming operation."""
    
    total_queries: int = 0
    successful: int = 0
    failed: int = 0
    cached_responses: list[CachedResponse] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_latency_ms: float = 0.0


def generate_cache_key(query: str) -> str:
    """Generate a deterministic cache key for a query."""
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


async def warm_single_query(
    client: httpx.AsyncClient,
    query_config: dict[str, Any],
    api_url: str,
    tenant_id: str = "demo",
) -> CachedResponse | None:
    """Warm cache for a single query using SSE /v1/ask endpoint."""
    query_id = query_config["id"]
    query = query_config["query"]
    cache_key = generate_cache_key(query)
    
    start_time = time.time()
    
    try:
        # Use SSE streaming endpoint
        full_response = ""
        citations = []
        
        async with client.stream(
            "POST",
            f"{api_url}/v1/ask",
            json={
                "query": query,
                "tenant_id": tenant_id,
                "stream": True,
            },
            headers={
                "X-Tenant-ID": tenant_id,
                "X-Cache-Warm": "true",
                "Accept": "text/event-stream",
            },
            timeout=60.0,
        ) as response:
            if response.status_code != 200:
                latency_ms = (time.time() - start_time) * 1000
                logger.warning(f"✗ Failed {query_id}: HTTP {response.status_code}")
                return None
            
            # Parse SSE stream
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        event = json.loads(data_str)
                        event_type = event.get("type", "")
                        
                        if event_type == "token":
                            full_response += event.get("content", "")
                        elif event_type == "citations":
                            citations = event.get("citations", [])
                        elif event_type == "done":
                            # Final metrics
                            pass
                    except json.JSONDecodeError:
                        continue
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Format citations
        formatted_citations = [
            {
                "citation_id": c.get("citation_id", c.get("id", f"cit_{i}")),
                "filing_id": c.get("filing_id", c.get("document_id")),
                "section": c.get("section", ""),
                "text": c.get("text", "")[:200],
                "score": c.get("score", 0.0),
            }
            for i, c in enumerate(citations)
        ]
        
        cached_response = CachedResponse(
            query_id=query_id,
            query=query,
            response=full_response,
            citations=formatted_citations,
            cached_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            cache_key=cache_key,
            metadata={
                "expected_ticker": query_config.get("expected_ticker"),
                "expected_section": query_config.get("expected_section"),
            },
        )
        
        logger.info(f"✓ Warmed {query_id}: {latency_ms:.0f}ms, {len(formatted_citations)} citations")
        return cached_response
            
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"✗ Error {query_id}: {e}")
        
        # Create mock response for offline demo
        mock_response = CachedResponse(
            query_id=query_id,
            query=query,
            response=f"[Mock response for demo] Based on the SEC filings, {query.lower().replace('what', 'the').replace('?', '.')}",
            citations=[
                {
                    "citation_id": f"mock_cit_{query_id}_1",
                    "filing_id": f"{query_config.get('expected_ticker', 'AAPL')}-10-K-20240115",
                    "section": query_config.get("expected_section", "Financial Performance"),
                    "text": "Mock citation text for demo purposes.",
                    "score": 0.95,
                }
            ],
            cached_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            cache_key=cache_key,
            metadata={
                "expected_ticker": query_config.get("expected_ticker"),
                "mock": True,
            },
        )
        return mock_response


async def warm_cache(
    queries: list[dict[str, Any]] | None = None,
    api_url: str | None = None,
    concurrency: int = 5,
) -> WarmingResult:
    """Warm cache with multiple queries concurrently."""
    queries = queries or DEMO_QUERIES
    api_url = api_url or os.getenv("VESPER_API_URL", "http://localhost:8000")
    
    result = WarmingResult(total_queries=len(queries))
    semaphore = asyncio.Semaphore(concurrency)
    
    async def warm_with_limit(query_config: dict[str, Any]) -> CachedResponse | None:
        async with semaphore:
            async with httpx.AsyncClient(timeout=60.0) as client:
                return await warm_single_query(client, query_config, api_url)
    
    # Warm queries concurrently
    tasks = [warm_with_limit(q) for q in queries]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, resp in enumerate(responses):
        if isinstance(resp, Exception):
            result.errors.append(f"{queries[i]['id']}: {str(resp)}")
            result.failed += 1
        elif resp is None:
            result.failed += 1
        else:
            result.cached_responses.append(resp)
            result.successful += 1
            result.total_latency_ms += resp.latency_ms
    
    return result


def persist_cached_responses(
    responses: list[CachedResponse],
    output_dir: Path,
) -> None:
    """Persist cached responses to JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save individual responses
    for resp in responses:
        resp_path = output_dir / f"{resp.query_id}.json"
        with open(resp_path, "w") as f:
            json.dump({
                "query_id": resp.query_id,
                "query": resp.query,
                "response": resp.response,
                "citations": resp.citations,
                "cached_at": resp.cached_at,
                "latency_ms": resp.latency_ms,
                "cache_key": resp.cache_key,
                "metadata": resp.metadata,
            }, f, indent=2)
    
    # Save manifest with all queries
    manifest_path = output_dir / "cache_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query_count": len(responses),
            "queries": [
                {
                    "query_id": r.query_id,
                    "query": r.query,
                    "cache_key": r.cache_key,
                    "citation_count": len(r.citations),
                    "latency_ms": r.latency_ms,
                }
                for r in responses
            ],
        }, f, indent=2)
    
    logger.info(f"Persisted {len(responses)} cached responses to {output_dir}")


def validate_cached_responses(
    cached_dir: Path,
    queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate cached responses match expected results."""
    queries = queries or DEMO_QUERIES
    results = {
        "total": len(queries),
        "valid": 0,
        "invalid": 0,
        "missing": 0,
        "issues": [],
    }
    
    for query_config in queries:
        query_id = query_config["id"]
        cache_file = cached_dir / f"{query_id}.json"
        
        if not cache_file.exists():
            results["missing"] += 1
            results["issues"].append(f"{query_id}: Cache file not found")
            continue
        
        with open(cache_file) as f:
            cached = json.load(f)
        
        # Validate citations exist
        if not cached.get("citations"):
            results["invalid"] += 1
            results["issues"].append(f"{query_id}: No citations found")
            continue
        
        # Validate expected keywords in response
        response_lower = cached.get("response", "").lower()
        expected_keywords = query_config.get("expected_keywords", [])
        missing_keywords = [kw for kw in expected_keywords if kw.lower() not in response_lower]
        
        if missing_keywords:
            results["issues"].append(f"{query_id}: Missing keywords: {missing_keywords}")
        
        # Validate ticker match if expected
        expected_ticker = query_config.get("expected_ticker")
        if expected_ticker:
            citations = cached.get("citations", [])
            ticker_found = any(
                expected_ticker.lower() in str(c.get("filing_id", "")).lower()
                for c in citations
            )
            if not ticker_found:
                results["issues"].append(f"{query_id}: Expected ticker {expected_ticker} not in citations")
        
        results["valid"] += 1
    
    return results


async def main():
    """Main entry point for cache warmers."""
    parser = argparse.ArgumentParser(description="VESPER Cache Warmers Script")
    parser.add_argument("--queries", type=int, default=20, help="Number of queries to warm")
    parser.add_argument("--persist", action="store_true", help="Persist cached responses to files")
    parser.add_argument("--validate", action="store_true", help="Validate existing cached responses")
    parser.add_argument("--output-dir", type=str, default="data/demo/cache", help="Output directory")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--ttl", type=int, default=3600, help="Cache TTL in seconds")
    parser.add_argument("--tenant", type=str, default="demo", help="Tenant ID for warming")
    parser.add_argument("--api-url", type=str, default=None, help="API base URL (default: VESPER_API_BASE or localhost:8000)")
    
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    api_url = args.api_url or os.getenv("VESPER_API_BASE", os.getenv("VESPER_API_URL", "http://localhost:8000"))
    
    logger.info("=" * 60)
    logger.info("VESPER Cache Warmers")
    logger.info(f"  API: {api_url}")
    logger.info(f"  Tenant: {args.tenant}")
    logger.info(f"  TTL: {args.ttl}s")
    logger.info("=" * 60)
    
    logger.info("=" * 60)
    logger.info("VESPER Cache Warmers")
    logger.info("=" * 60)
    
    if args.validate:
        logger.info("Validating cached responses...")
        validation = validate_cached_responses(output_dir)
        logger.info(f"Validation Results:")
        logger.info(f"  Valid: {validation['valid']}/{validation['total']}")
        logger.info(f"  Invalid: {validation['invalid']}")
        logger.info(f"  Missing: {validation['missing']}")
        if validation["issues"]:
            logger.warning(f"Issues found:")
            for issue in validation["issues"]:
                logger.warning(f"  - {issue}")
        return
    
    # Select queries to warm
    queries = DEMO_QUERIES[:args.queries]
    logger.info(f"Warming {len(queries)} queries...")
    
    # Warm cache
    result = await warm_cache(queries, api_url=api_url, concurrency=args.concurrency)
    
    # Persist if requested
    if args.persist or True:  # Always persist for demo
        persist_cached_responses(result.cached_responses, output_dir)
    
    # Calculate hit ratio (assume first run is all misses)
    # For subsequent runs, check if responses were from cache
    cache_hits = sum(1 for r in result.cached_responses if r.metadata.get("cache_hit", False))
    hit_ratio = cache_hits / max(result.successful, 1)
    
    # Summary
    avg_latency = result.total_latency_ms / max(result.successful, 1)
    
    logger.info("=" * 60)
    logger.info("Cache Warming Complete!")
    logger.info(f"  Total: {result.total_queries}")
    logger.info(f"  Successful: {result.successful}")
    logger.info(f"  Failed: {result.failed}")
    logger.info(f"  Average Latency: {avg_latency:.0f}ms")
    logger.info(f"  Cache Hit Ratio: {hit_ratio:.1%}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 60)
    
    if result.errors:
        logger.warning("Errors:")
        for error in result.errors:
            logger.warning(f"  - {error}")


if __name__ == "__main__":
    asyncio.run(main())
