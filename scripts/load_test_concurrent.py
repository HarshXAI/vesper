#!/usr/bin/env python3
"""
Concurrent Load Test Script for Vesper API
============================================

Generates concurrent load for performance testing and SLO validation.
Provides detailed metrics including p50, p90, p95, p99 latencies.

Usage:
    python scripts/load_test_concurrent.py --rps 10 --duration 60
    python scripts/load_test_concurrent.py --users 50 --duration 120
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional

import httpx


# =============================================================================
# Configuration
# =============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("LOAD_TEST_TOKEN", "")
TENANT_ID = os.getenv("TENANT_ID", "load-test")

SAMPLE_QUERIES = [
    "What did Apple report about revenue growth?",
    "What was Microsoft's operating income in the last quarter?",
    "How did Google's cloud revenue perform?",
    "What are Amazon's key risk factors?",
    "What did Tesla report about vehicle deliveries?",
    "What was Netflix's subscriber growth?",
    "How did Meta's advertising revenue change?",
    "What are the main revenue segments for Apple?",
    "What did Nvidia report about data center revenue?",
    "How did Adobe's subscription revenue perform?",
    "What is the guidance for next quarter?",
    "What are the main competitive risks?",
    "How did gross margin change year over year?",
    "What is the company's cash position?",
    "What are the key growth drivers?",
]


# =============================================================================
# Result Tracking
# =============================================================================

@dataclass
class RequestResult:
    """Result of a single request."""
    success: bool
    status_code: int
    latency_ms: float
    query: str
    error: Optional[str] = None
    tokens_received: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class LoadTestStats:
    """Aggregated statistics for load test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_result(self, result: RequestResult):
        """Add a request result to stats."""
        self.total_requests += 1
        if result.success:
            self.successful_requests += 1
            self.latencies_ms.append(result.latency_ms)
        else:
            self.failed_requests += 1
            error_type = result.error or f"HTTP_{result.status_code}"
            self.errors[error_type] = self.errors.get(error_type, 0) + 1
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    def get_percentile(self, p: float) -> float:
        """Get latency percentile (0-100)."""
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        index = int(len(sorted_latencies) * p / 100)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]
    
    @property
    def p50(self) -> float:
        return self.get_percentile(50)
    
    @property
    def p90(self) -> float:
        return self.get_percentile(90)
    
    @property
    def p95(self) -> float:
        return self.get_percentile(95)
    
    @property
    def p99(self) -> float:
        return self.get_percentile(99)
    
    @property
    def avg_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)
    
    @property
    def duration_seconds(self) -> float:
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def requests_per_second(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds
    
    def to_dict(self) -> dict:
        """Convert stats to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate, 2),
            "error_rate": round(self.error_rate, 2),
            "latency_ms": {
                "avg": round(self.avg_latency, 2),
                "p50": round(self.p50, 2),
                "p90": round(self.p90, 2),
                "p95": round(self.p95, 2),
                "p99": round(self.p99, 2),
            },
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
            "requests_per_second": round(self.requests_per_second, 2),
        }


# =============================================================================
# Load Test Runner
# =============================================================================

class LoadTestRunner:
    """Concurrent load test runner."""
    
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        auth_token: str = AUTH_TOKEN,
        tenant_id: str = TENANT_ID,
    ):
        self.base_url = base_url
        self.auth_token = auth_token
        self.tenant_id = tenant_id
        self.stats = LoadTestStats()
        self._running = False
        self._query_index = 0
    
    def _get_next_query(self) -> str:
        """Get next query in round-robin fashion."""
        query = SAMPLE_QUERIES[self._query_index % len(SAMPLE_QUERIES)]
        self._query_index += 1
        return query
    
    async def _make_request(
        self,
        client: httpx.AsyncClient,
        stream: bool = False,
    ) -> RequestResult:
        """Make a single request."""
        query = self._get_next_query()
        start_time = time.perf_counter()
        
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        payload = {
            "query": query,
            "stream": stream,
            "tenant_id": self.tenant_id,
        }
        
        try:
            if stream:
                response = await self._make_streaming_request(client, payload, headers)
            else:
                response = await client.post(
                    f"{self.base_url}/v1/chat",
                    json=payload,
                    headers=headers,
                )
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                if response.status_code == 200:
                    return RequestResult(
                        success=True,
                        status_code=200,
                        latency_ms=latency_ms,
                        query=query,
                    )
                else:
                    return RequestResult(
                        success=False,
                        status_code=response.status_code,
                        latency_ms=latency_ms,
                        query=query,
                        error=f"HTTP_{response.status_code}",
                    )
                    
        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=latency_ms,
                query=query,
                error="timeout",
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=latency_ms,
                query=query,
                error=str(e),
            )
    
    async def _make_streaming_request(
        self,
        client: httpx.AsyncClient,
        payload: dict,
        headers: dict,
    ) -> RequestResult:
        """Make a streaming request and collect tokens."""
        start_time = time.perf_counter()
        tokens_received = 0
        
        async with client.stream(
            "POST",
            f"{self.base_url}/v1/chat/stream",
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code != 200:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return RequestResult(
                    success=False,
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    query=payload["query"],
                    error=f"HTTP_{response.status_code}",
                )
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "token" in data or "delta" in data:
                            tokens_received += 1
                    except json.JSONDecodeError:
                        pass
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        return RequestResult(
            success=True,
            status_code=200,
            latency_ms=latency_ms,
            query=payload["query"],
            tokens_received=tokens_received,
        )
    
    async def run_constant_users(
        self,
        num_users: int,
        duration_seconds: int,
        think_time_ms: float = 1000,
        stream: bool = False,
    ) -> LoadTestStats:
        """Run load test with constant number of concurrent users."""
        print(f"🚀 Starting load test: {num_users} users for {duration_seconds}s")
        print(f"   Target: {self.base_url}")
        print(f"   Stream: {stream}")
        print()
        
        self.stats = LoadTestStats()
        self.stats.start_time = datetime.now(UTC)
        self._running = True
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check health first
            try:
                health = await client.get(f"{self.base_url}/health")
                if health.status_code != 200:
                    print("❌ API health check failed")
                    return self.stats
                print("✅ API health check passed")
            except Exception as e:
                print(f"❌ API not reachable: {e}")
                return self.stats
            
            print()
            print("📊 Running load test...")
            print("-" * 60)
            
            end_time = time.time() + duration_seconds
            
            async def user_loop(user_id: int):
                """Simulate a single user making requests."""
                while self._running and time.time() < end_time:
                    result = await self._make_request(client, stream)
                    self.stats.add_result(result)
                    
                    # Think time between requests
                    await asyncio.sleep(think_time_ms / 1000)
            
            # Start all users
            tasks = [user_loop(i) for i in range(num_users)]
            
            # Progress reporter
            async def progress_reporter():
                last_count = 0
                while self._running and time.time() < end_time:
                    await asyncio.sleep(5)
                    current = self.stats.total_requests
                    rps = (current - last_count) / 5
                    last_count = current
                    print(
                        f"   Progress: {current} requests, "
                        f"{self.stats.success_rate:.1f}% success, "
                        f"~{rps:.1f} req/s"
                    )
            
            tasks.append(progress_reporter())
            
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                pass
        
        self._running = False
        self.stats.end_time = datetime.now(UTC)
        
        return self.stats
    
    async def run_constant_rps(
        self,
        target_rps: int,
        duration_seconds: int,
        stream: bool = False,
    ) -> LoadTestStats:
        """Run load test at constant requests per second."""
        print(f"🚀 Starting load test: {target_rps} RPS for {duration_seconds}s")
        print(f"   Target: {self.base_url}")
        print(f"   Stream: {stream}")
        print()
        
        self.stats = LoadTestStats()
        self.stats.start_time = datetime.now(UTC)
        self._running = True
        
        interval = 1.0 / target_rps
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check health first
            try:
                health = await client.get(f"{self.base_url}/health")
                if health.status_code != 200:
                    print("❌ API health check failed")
                    return self.stats
                print("✅ API health check passed")
            except Exception as e:
                print(f"❌ API not reachable: {e}")
                return self.stats
            
            print()
            print("📊 Running load test...")
            print("-" * 60)
            
            end_time = time.time() + duration_seconds
            pending_tasks = set()
            
            async def bounded_request():
                result = await self._make_request(client, stream)
                self.stats.add_result(result)
            
            last_report = time.time()
            
            while self._running and time.time() < end_time:
                # Schedule new request
                task = asyncio.create_task(bounded_request())
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)
                
                # Limit pending tasks to prevent memory issues
                if len(pending_tasks) > target_rps * 10:
                    done, pending_tasks = await asyncio.wait(
                        pending_tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                
                # Report progress every 5 seconds
                if time.time() - last_report >= 5:
                    print(
                        f"   Progress: {self.stats.total_requests} requests, "
                        f"{self.stats.success_rate:.1f}% success, "
                        f"p95: {self.stats.p95:.0f}ms"
                    )
                    last_report = time.time()
                
                await asyncio.sleep(interval)
            
            # Wait for remaining requests
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
        
        self._running = False
        self.stats.end_time = datetime.now(UTC)
        
        return self.stats


# =============================================================================
# SLO Validation
# =============================================================================

def validate_slos(stats: LoadTestStats) -> dict:
    """Validate results against SLO targets."""
    slos = {
        "p95_latency_ms": {
            "target": 2500,  # p95 < 2.5s
            "actual": stats.p95,
            "passed": stats.p95 < 2500,
        },
        "error_rate_percent": {
            "target": 1.0,  # errors < 1%
            "actual": stats.error_rate,
            "passed": stats.error_rate < 1.0,
        },
        "success_rate_percent": {
            "target": 99.0,  # success > 99%
            "actual": stats.success_rate,
            "passed": stats.success_rate >= 99.0,
        },
    }
    
    all_passed = all(s["passed"] for s in slos.values())
    
    return {
        "passed": all_passed,
        "slos": slos,
    }


# =============================================================================
# Main Entry Point
# =============================================================================

def print_results(stats: LoadTestStats, slo_results: dict):
    """Print formatted results."""
    print()
    print("=" * 60)
    print("📊 LOAD TEST RESULTS")
    print("=" * 60)
    print()
    print(f"Total Requests:    {stats.total_requests}")
    print(f"Successful:        {stats.successful_requests}")
    print(f"Failed:            {stats.failed_requests}")
    print(f"Success Rate:      {stats.success_rate:.2f}%")
    print(f"Duration:          {stats.duration_seconds:.1f}s")
    print(f"Throughput:        {stats.requests_per_second:.2f} req/s")
    print()
    print("Latency (ms):")
    print(f"  Average:         {stats.avg_latency:.2f}")
    print(f"  p50:             {stats.p50:.2f}")
    print(f"  p90:             {stats.p90:.2f}")
    print(f"  p95:             {stats.p95:.2f}")
    print(f"  p99:             {stats.p99:.2f}")
    print()
    
    if stats.errors:
        print("Errors:")
        for error_type, count in stats.errors.items():
            print(f"  {error_type}: {count}")
        print()
    
    print("=" * 60)
    print("🎯 SLO VALIDATION")
    print("=" * 60)
    print()
    
    for name, result in slo_results["slos"].items():
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {name}")
        print(f"   Target: {result['target']}")
        print(f"   Actual: {result['actual']:.2f}")
        print()
    
    overall = "✅ ALL SLOs PASSED" if slo_results["passed"] else "❌ SLOs FAILED"
    print(overall)
    print()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Vesper API Load Tester")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--rps", type=int, default=0, help="Target requests per second (0 = use users mode)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--stream", action="store_true", help="Use streaming endpoint")
    parser.add_argument("--url", type=str, default=API_BASE_URL, help="API base URL")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    runner = LoadTestRunner(base_url=args.url)
    
    if args.rps > 0:
        stats = await runner.run_constant_rps(
            target_rps=args.rps,
            duration_seconds=args.duration,
            stream=args.stream,
        )
    else:
        stats = await runner.run_constant_users(
            num_users=args.users,
            duration_seconds=args.duration,
            stream=args.stream,
        )
    
    slo_results = validate_slos(stats)
    
    if args.json:
        output = {
            "stats": stats.to_dict(),
            "slos": slo_results,
        }
        print(json.dumps(output, indent=2))
    else:
        print_results(stats, slo_results)
    
    # Exit with error code if SLOs failed
    sys.exit(0 if slo_results["passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
