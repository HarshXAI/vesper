#!/bin/bash
"""
VESPER Enhanced Services Integration Test Suite
Tests all deployed services and their integrations
"""

set -e

# Configuration
PROJECT_NAME="vesper"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-ap-south-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test execution helper
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    log_info "Running test: $test_name"
    
    if eval "$test_command"; then
        log_success "$test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "$test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Get ALB URL
get_alb_url() {
    ALB_URL=$(aws elbv2 describe-load-balancers \
        --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
        --region ${AWS_REGION} \
        --query 'LoadBalancers[0].DNSName' \
        --output text 2>/dev/null)
    
    if [ "$ALB_URL" = "None" ] || [ -z "$ALB_URL" ]; then
        log_error "Could not retrieve ALB URL. Make sure services are deployed."
        exit 1
    fi
    
    API_BASE_URL="http://${ALB_URL}"
    log_info "Testing API at: $API_BASE_URL"
}

# Test basic connectivity
test_basic_connectivity() {
    run_test "Basic Connectivity" "curl -f -s --max-time 10 '$API_BASE_URL/' > /dev/null"
}

# Test health endpoint
test_health_endpoint() {
    local health_response=$(curl -s --max-time 10 "$API_BASE_URL/health" 2>/dev/null)
    
    # Check if response contains expected fields
    if echo "$health_response" | jq -e '.status and .timestamp and .services' > /dev/null 2>&1; then
        run_test "Health Endpoint Structure" "true"
        
        # Check individual service health
        local api_gateway_status=$(echo "$health_response" | jq -r '.services.database // "unknown"')
        if [ "$api_gateway_status" = "healthy" ]; then
            run_test "Database Health" "true"
        else
            run_test "Database Health" "false"
        fi
        
    else
        run_test "Health Endpoint Structure" "false"
    fi
}

# Test metrics endpoint
test_metrics_endpoint() {
    local metrics_response=$(curl -s --max-time 10 "$API_BASE_URL/metrics" 2>/dev/null)
    
    # Check for Prometheus metrics format
    if echo "$metrics_response" | grep -q "api_requests_total"; then
        run_test "Metrics Endpoint (Prometheus format)" "true"
    else
        run_test "Metrics Endpoint (Prometheus format)" "false"
    fi
}

# Test API Gateway query endpoint (non-streaming)
test_query_non_streaming() {
    local query_payload='{
        "query": "What is VESPER?",
        "stream": false,
        "user_id": "test_user",
        "tenant_id": "test_tenant"
    }'
    
    local response=$(curl -s --max-time 30 \
        -H "Content-Type: application/json" \
        -d "$query_payload" \
        "$API_BASE_URL/v1/ask" 2>/dev/null)
    
    # Check if response has expected structure
    if echo "$response" | jq -e '.success and .request_id' > /dev/null 2>&1; then
        run_test "Query Non-Streaming API" "true"
    else
        run_test "Query Non-Streaming API" "false"
    fi
}

# Test API Gateway query endpoint (streaming)
test_query_streaming() {
    local query_payload='{
        "query": "Tell me about financial analysis",
        "stream": true,
        "user_id": "test_user",
        "tenant_id": "test_tenant"
    }'
    
    # Test streaming endpoint (just check if it returns SSE format)
    local response=$(curl -s --max-time 20 \
        -H "Content-Type: application/json" \
        -d "$query_payload" \
        "$API_BASE_URL/v1/ask" 2>/dev/null | head -10)
    
    # Check for Server-Sent Events format
    if echo "$response" | grep -q "data:"; then
        run_test "Query Streaming API (SSE format)" "true"
    else
        run_test "Query Streaming API (SSE format)" "false"
    fi
}

# Test document upload
test_document_upload() {
    # Create a test file
    local test_file="/tmp/vesper_test_doc.txt"
    echo "This is a test document for VESPER integration testing." > "$test_file"
    
    local response=$(curl -s --max-time 30 \
        -F "file=@$test_file" \
        "$API_BASE_URL/upload" 2>/dev/null)
    
    # Check if upload was successful
    if echo "$response" | jq -e '.document_id and .filename and .status' > /dev/null 2>&1; then
        run_test "Document Upload" "true"
        
        # Store document ID for cleanup
        export TEST_DOCUMENT_ID=$(echo "$response" | jq -r '.document_id')
    else
        run_test "Document Upload" "false"
    fi
    
    # Cleanup
    rm -f "$test_file"
}

# Test document listing
test_document_listing() {
    local response=$(curl -s --max-time 10 "$API_BASE_URL/documents" 2>/dev/null)
    
    # Check if response is a valid array
    if echo "$response" | jq -e 'type == "array"' > /dev/null 2>&1; then
        run_test "Document Listing" "true"
    else
        run_test "Document Listing" "false"
    fi
}

# Test error handling
test_error_handling() {
    # Test with invalid JSON
    local response=$(curl -s --max-time 10 \
        -H "Content-Type: application/json" \
        -d '{"query": ""}' \
        "$API_BASE_URL/v1/ask" 2>/dev/null)
    
    # Should return error for empty query
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -H "Content-Type: application/json" \
        -d '{"query": ""}' \
        "$API_BASE_URL/v1/ask" 2>/dev/null)
    
    if [ "$status_code" = "422" ]; then
        run_test "Error Handling (Validation)" "true"
    else
        run_test "Error Handling (Validation)" "false"
    fi
}

# Test service discovery and inter-service communication
test_service_discovery() {
    # This tests if services can discover each other
    # We'll check the health endpoint for service status
    
    local health_response=$(curl -s --max-time 10 "$API_BASE_URL/health" 2>/dev/null)
    
    # Count how many services are reported as healthy
    local healthy_services=0
    
    # Check each service status from health response
    if echo "$health_response" | jq -e '.services' > /dev/null 2>&1; then
        local services=$(echo "$health_response" | jq -r '.services | keys[]' 2>/dev/null)
        
        while IFS= read -r service; do
            local status=$(echo "$health_response" | jq -r ".services.\"$service\"" 2>/dev/null)
            if [ "$status" = "healthy" ]; then
                healthy_services=$((healthy_services + 1))
            fi
        done <<< "$services"
        
        # We expect at least database and redis to be healthy
        if [ "$healthy_services" -ge 2 ]; then
            run_test "Service Discovery (Health checks)" "true"
        else
            run_test "Service Discovery (Health checks)" "false"
        fi
    else
        run_test "Service Discovery (Health checks)" "false"
    fi
}

# Test load balancing
test_load_balancing() {
    # Make multiple requests to test load balancing
    local request_count=5
    local successful_requests=0
    
    for i in $(seq 1 $request_count); do
        if curl -f -s --max-time 5 "$API_BASE_URL/health" > /dev/null 2>&1; then
            successful_requests=$((successful_requests + 1))
        fi
    done
    
    # Expect at least 80% success rate
    local success_rate=$((successful_requests * 100 / request_count))
    
    if [ "$success_rate" -ge 80 ]; then
        run_test "Load Balancing (${success_rate}% success rate)" "true"
    else
        run_test "Load Balancing (${success_rate}% success rate)" "false"
    fi
}

# Test auto-scaling (by checking ECS service status)
test_auto_scaling_config() {
    # Check if auto-scaling is configured for services
    local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    
    # Check if API Gateway service has auto-scaling
    local scaling_policies=$(aws application-autoscaling describe-scaling-policies \
        --service-namespace ecs \
        --resource-id "service/${cluster_name}/${PROJECT_NAME}-${ENVIRONMENT}-api-gateway" \
        --region ${AWS_REGION} 2>/dev/null || echo '{"ScalingPolicies": []}')
    
    local policy_count=$(echo "$scaling_policies" | jq '.ScalingPolicies | length' 2>/dev/null || echo "0")
    
    if [ "$policy_count" -gt 0 ]; then
        run_test "Auto-scaling Configuration" "true"
    else
        run_test "Auto-scaling Configuration" "false"
    fi
}

# Test CloudWatch logs
test_cloudwatch_logs() {
    local log_group="/aws/ecs/${PROJECT_NAME}-${ENVIRONMENT}/api-gateway"
    
    # Check if log group exists and has recent logs
    local log_streams=$(aws logs describe-log-streams \
        --log-group-name "$log_group" \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --region ${AWS_REGION} 2>/dev/null || echo '{"logStreams": []}')
    
    local stream_count=$(echo "$log_streams" | jq '.logStreams | length' 2>/dev/null || echo "0")
    
    if [ "$stream_count" -gt 0 ]; then
        run_test "CloudWatch Logs" "true"
    else
        run_test "CloudWatch Logs" "false"
    fi
}

# Performance test
test_performance() {
    log_info "Running performance test (10 concurrent requests)..."
    
    # Create a temporary file for curl results
    local results_file="/tmp/vesper_perf_test.txt"
    
    # Run 10 concurrent requests
    for i in $(seq 1 10); do
        (curl -s -w "%{time_total}\n" --max-time 30 "$API_BASE_URL/health" >> "$results_file") &
    done
    
    # Wait for all requests to complete
    wait
    
    # Calculate average response time
    if [ -f "$results_file" ]; then
        local avg_time=$(awk '{sum+=$1} END {print sum/NR}' "$results_file" 2>/dev/null || echo "999")
        
        # Response time should be under 2 seconds
        if (( $(echo "$avg_time < 2.0" | bc -l) )); then
            run_test "Performance (avg ${avg_time}s)" "true"
        else
            run_test "Performance (avg ${avg_time}s)" "false"
        fi
        
        rm -f "$results_file"
    else
        run_test "Performance Test" "false"
    fi
}

# Print test summary
print_summary() {
    echo ""
    echo "🧪 Test Results Summary"
    echo "======================="
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $TESTS_PASSED"
    echo "Failed: $TESTS_FAILED"
    
    local success_rate=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo "Success Rate: ${success_rate}%"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "🎉 All tests passed! VESPER services are working correctly."
    else
        log_warning "⚠️  Some tests failed. Please check the logs and service status."
    fi
    
    echo ""
    echo "📊 Service Status Dashboard:"
    echo "  API Gateway: $API_BASE_URL"
    echo "  Health Check: $API_BASE_URL/health"
    echo "  Metrics: $API_BASE_URL/metrics"
    echo "  API Documentation: $API_BASE_URL/docs"
    echo ""
}

# Main test function
main() {
    log_info "🧪 Starting VESPER Enhanced Services Integration Tests..."
    echo ""
    
    # Prerequisites
    if ! command -v jq &> /dev/null; then
        log_error "jq is required for JSON parsing. Please install it first."
        exit 1
    fi
    
    if ! command -v bc &> /dev/null; then
        log_warning "bc is not available. Some calculations may not work."
    fi
    
    # Get API endpoint
    get_alb_url
    
    echo ""
    log_info "Running integration tests..."
    echo ""
    
    # Core functionality tests
    test_basic_connectivity
    test_health_endpoint
    test_metrics_endpoint
    
    # API tests
    test_query_non_streaming
    test_query_streaming
    test_document_upload
    test_document_listing
    test_error_handling
    
    # Infrastructure tests
    test_service_discovery
    test_load_balancing
    test_auto_scaling_config
    test_cloudwatch_logs
    
    # Performance test
    test_performance
    
    # Summary
    print_summary
    
    # Exit with appropriate code
    if [ $TESTS_FAILED -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Handle script arguments
case "${1:-test}" in
    "quick")
        log_info "Running quick test suite..."
        get_alb_url
        test_basic_connectivity
        test_health_endpoint
        test_query_non_streaming
        print_summary
        ;;
    "performance")
        log_info "Running performance tests only..."
        get_alb_url
        test_performance
        print_summary
        ;;
    "test"|*)
        main
        ;;
esac