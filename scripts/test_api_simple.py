#!/usr/bin/env python3
"""Simple API test to generate metrics"""

import requests
import time

API_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✓ Health: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Health failed: {e}")
        return False

def test_metrics():
    """Test metrics endpoint"""
    try:
        response = requests.get(f"{API_URL}/metrics", timeout=5)
        print(f"✓ Metrics: {response.status_code}, {len(response.text)} bytes")
        return True
    except Exception as e:
        print(f"✗ Metrics failed: {e}")
        return False

def main():
    print("Testing API endpoints to generate metrics...")
    print()
    
    # Test multiple times to generate data
    for i in range(10):
        print(f"Round {i+1}/10:")
        test_health()
        test_metrics()
        time.sleep(1)
        print()
    
    print("✅ Done! Check Grafana dashboard for metrics")
    print("   Dashboard: http://localhost:3003/d/vesper-api-gateway")

if __name__ == "__main__":
    main()
