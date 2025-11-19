#!/usr/bin/env python3
"""Generate continuous load on the API Gateway to produce metrics.

Makes requests to /v1/ask endpoint with various queries to generate
API metrics visible in Prometheus and Grafana.
"""
import time
import random
import requests
import json
from datetime import datetime
from typing import List

API_BASE_URL = "http://localhost:8000"
TENANT_ID = "demo"

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
]


def make_request(query: str) -> dict:
    """Make a streaming request to /v1/ask and collect the response."""
    url = f"{API_BASE_URL}/v1/ask"
    payload = {
        "query": query,
        "tenant_id": TENANT_ID,
        "stream": True
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=30
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "status_code": response.status_code,
                "latency_ms": (time.time() - start_time) * 1000,
                "error": f"HTTP {response.status_code}"
            }
        
        # Read streaming response
        tokens_received = 0
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                try:
                    event = json.loads(data_str)
                    if event.get("type") == "token":
                        tokens_received += 1
                    elif event.get("type") == "done":
                        break
                except json.JSONDecodeError:
                    pass
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "status_code": 200,
            "latency_ms": latency_ms,
            "tokens_received": tokens_received
        }
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": 30000,
            "error": "timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "latency_ms": (time.time() - start_time) * 1000,
            "error": str(e)
        }


def check_health() -> bool:
    """Check if API is healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Run continuous load generation."""
    print("🚀 API Load Generator")
    print(f"   Target: {API_BASE_URL}")
    print(f"   Queries: {len(SAMPLE_QUERIES)} samples")
    print()
    
    # Check health first
    print("🏥 Checking API health...", end=" ")
    if not check_health():
        print("❌ FAILED")
        print("   API is not healthy. Start the API Gateway first:")
        print("   docker compose up -d api-gateway")
        return
    print("✅ OK")
    print()
    
    print("📊 Starting load generation (Ctrl+C to stop)")
    print("-" * 60)
    
    request_count = 0
    success_count = 0
    error_count = 0
    total_latency_ms = 0
    
    try:
        while True:
            # Pick random query
            query = random.choice(SAMPLE_QUERIES)
            
            # Make request
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Query: {query[:50]}...", end=" ")
            
            result = make_request(query)
            request_count += 1
            
            if result["success"]:
                success_count += 1
                total_latency_ms += result["latency_ms"]
                avg_latency = total_latency_ms / success_count
                print(f"✅ {result['latency_ms']:.0f}ms (avg: {avg_latency:.0f}ms)")
            else:
                error_count += 1
                print(f"❌ {result.get('error', 'unknown')}")
            
            # Print stats every 10 requests
            if request_count % 10 == 0:
                success_rate = (success_count / request_count) * 100
                print()
                print(f"📈 Stats: {request_count} requests, "
                      f"{success_count} success ({success_rate:.1f}%), "
                      f"{error_count} errors")
                print("-" * 60)
            
            # Wait before next request (random delay 2-8 seconds)
            time.sleep(random.uniform(2, 8))
            
    except KeyboardInterrupt:
        print()
        print()
        print("🛑 Stopping load generator")
        print()
        print("📊 Final Stats:")
        print(f"   Total requests: {request_count}")
        print(f"   Successful: {success_count}")
        print(f"   Errors: {error_count}")
        if success_count > 0:
            avg_latency = total_latency_ms / success_count
            print(f"   Average latency: {avg_latency:.0f}ms")


if __name__ == "__main__":
    main()
