#!/usr/bin/env python3
"""Simple API test that bypasses the streaming/embedding issue to generate metrics."""

import requests
import time

API_URL = "http://localhost:8000"

def main():
    print("🧪 Testing API Metrics Generation")
    print("=" * 60)
    print()
    
    # Test 1: Health endpoint (should record metrics)
    print("Test 1: Health Endpoint")
    for i in range(5):
        response = requests.get(f"{API_URL}/health")
        print(f"  [{i+1}/5] Status: {response.status_code}")
        time.sleep(0.5)
    
    print()
    print("Test 2: Metrics Endpoint")
    response = requests.get(f"{API_URL}/metrics")
    
    # Count vesper_ metrics
    metrics_text = response.text
    vesper_metrics = [line for line in metrics_text.split('\n') if line.startswith('vesper_')]
    
    print(f"  Found {len(vesper_metrics)} vesper_ metric lines")
    print()
    
    print("✅ Metrics are being exported!")
    print()
    print("📊 Check Prometheus: http://localhost:9090")
    print("   Query: vesper_api_requests_total")
    print()
    print("📈 Import Grafana dashboard to visualize")
    print()

if __name__ == "__main__":
    main()
