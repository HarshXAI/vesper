#!/bin/bash
# Quick setup script to start all monitoring services and generate metrics

set -e

echo "🚀 VESPER Monitoring Setup"
echo "=========================="
echo ""

# Start demo metrics service
echo "📊 Starting demo metrics service..."
docker compose up -d demo-metrics
sleep 2

# Restart Prometheus to pick up config
echo "🔄 Restarting Prometheus..."
docker compose restart prometheus
sleep 3

# Check if services are healthy
echo ""
echo "🏥 Health Checks:"
echo "----------------"

# Check demo metrics
if curl -sf http://localhost:9101/ > /dev/null 2>&1; then
    echo "✅ Demo Metrics (http://localhost:9101)"
else
    echo "❌ Demo Metrics - NOT responding"
fi

# Check Prometheus
if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus (http://localhost:9090)"
else
    echo "❌ Prometheus - NOT responding"
fi

# Check Grafana
if curl -sf http://localhost:3003/api/health > /dev/null 2>&1; then
    echo "✅ Grafana (http://localhost:3003)"
else
    echo "❌ Grafana - NOT responding"
fi

# Check API Gateway
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API Gateway (http://localhost:8000)"
else
    echo "❌ API Gateway - NOT responding"
fi

echo ""
echo "📈 Quick Access Links:"
echo "---------------------"
echo "Prometheus:        http://localhost:9090"
echo "Prometheus Targets: http://localhost:9090/targets"
echo "Grafana:           http://localhost:3003 (admin/admin)"
echo "Demo Metrics:      http://localhost:9101"
echo "API Gateway:       http://localhost:8000/health"
echo ""

echo "🎯 Next Steps:"
echo "-------------"
echo "1. Open Grafana: http://localhost:3003"
echo "2. Import dashboard: monitoring/grafana/dashboards/vesper-api-gateway.json"
echo "3. (Optional) Start load generator in new terminal:"
echo "   python3 scripts/generate_load.py"
echo ""

echo "✅ Setup complete!"
