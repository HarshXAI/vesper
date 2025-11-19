#!/usr/bin/env python3
"""Quick verification script to check what metrics are available in Prometheus."""

import requests
import json

PROMETHEUS_URL = "http://localhost:9090"

def query_metric(metric_name):
    """Query a metric from Prometheus."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric_name},
            timeout=5
        )
        data = response.json()
        if data['status'] == 'success' and data['data']['result']:
            return data['data']['result'][0]
        return None
    except Exception as e:
        return None

def main():
    print("🔍 VESPER Metrics Verification")
    print("=" * 60)
    print()
    
    # Check demo metrics
    print("📊 Demo Metrics (Working):")
    print("-" * 60)
    
    temp = query_metric("demo_temperature_celsius")
    if temp:
        value = float(temp['value'][1])
        print(f"✅ Temperature: {value:.2f}°C")
    else:
        print("❌ Temperature: Not found")
    
    requests_total = query_metric("demo_requests_total")
    if requests_total:
        value = float(requests_total['value'][1])
        print(f"✅ Total Requests: {value:.0f}")
    else:
        print("❌ Total Requests: Not found")
    
    print()
    
    # Check API metrics
    print("🌐 API Gateway Metrics:")
    print("-" * 60)
    
    api_requests = query_metric("vesper_api_requests_total")
    if api_requests:
        print(f"✅ API Requests: Available")
    else:
        print("⚠️  API Requests: Not yet available (MetricsCollector not recording)")
    
    print()
    print("=" * 60)
    print()
    print("📈 What You Can See in Grafana RIGHT NOW:")
    print("-" * 60)
    print("• Demo Temperature - Live graph updating every 2 seconds")
    print("• Demo Request Rate - Counter showing growth")
    print("• Demo Response Time - Histogram distribution")
    print()
    print("🔗 Open Grafana: http://localhost:3003 (admin/admin)")
    print("📊 Import dashboard: monitoring/grafana/dashboards/vesper-api-gateway.json")
    print()

if __name__ == "__main__":
    main()
