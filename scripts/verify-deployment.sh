#!/bin/bash
"""
VESPER Enhanced Deployment Verification Script
Validates the deployment and infrastructure setup
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

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq is required for JSON parsing"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Check ECS cluster
check_ecs_cluster() {
    log_info "Checking ECS cluster..."
    
    local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    local cluster_status=$(aws ecs describe-clusters \
        --clusters "$cluster_name" \
        --region "$AWS_REGION" \
        --query 'clusters[0].status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$cluster_status" = "ACTIVE" ]; then
        log_success "ECS cluster is active: $cluster_name"
        return 0
    else
        log_error "ECS cluster not found or not active: $cluster_name"
        return 1
    fi
}

# Check ECS services
check_ecs_services() {
    log_info "Checking ECS services..."
    
    local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    local services=("api-gateway" "agents" "guardrails" "processing" "retrieval")
    local all_healthy=true
    
    for service in "${services[@]}"; do
        local service_name="${PROJECT_NAME}-${ENVIRONMENT}-${service}"
        
        local service_info=$(aws ecs describe-services \
            --cluster "$cluster_name" \
            --services "$service_name" \
            --region "$AWS_REGION" \
            --query 'services[0]' 2>/dev/null)
        
        if [ "$service_info" != "null" ] && [ -n "$service_info" ]; then
            local running_count=$(echo "$service_info" | jq -r '.runningCount // 0')
            local desired_count=$(echo "$service_info" | jq -r '.desiredCount // 0')
            
            if [ "$running_count" -eq "$desired_count" ] && [ "$running_count" -gt 0 ]; then
                log_success "Service $service: $running_count/$desired_count tasks running"
            else
                log_warning "Service $service: $running_count/$desired_count tasks running"
                all_healthy=false
            fi
        else
            log_error "Service $service: not found"
            all_healthy=false
        fi
    done
    
    if $all_healthy; then
        return 0
    else
        return 1
    fi
}

# Check Load Balancer
check_load_balancer() {
    log_info "Checking Application Load Balancer..."
    
    local alb_name="${PROJECT_NAME}-${ENVIRONMENT}-alb"
    local alb_info=$(aws elbv2 describe-load-balancers \
        --names "$alb_name" \
        --region "$AWS_REGION" \
        --query 'LoadBalancers[0]' 2>/dev/null)
    
    if [ "$alb_info" != "null" ] && [ -n "$alb_info" ]; then
        local alb_state=$(echo "$alb_info" | jq -r '.State.Code')
        local alb_dns=$(echo "$alb_info" | jq -r '.DNSName')
        
        if [ "$alb_state" = "active" ]; then
            log_success "Load Balancer is active: $alb_dns"
            export ALB_URL="$alb_dns"
            return 0
        else
            log_warning "Load Balancer state: $alb_state"
            return 1
        fi
    else
        log_error "Load Balancer not found: $alb_name"
        return 1
    fi
}

# Check Service Discovery
check_service_discovery() {
    log_info "Checking Service Discovery..."
    
    local namespace_name="${PROJECT_NAME}-${ENVIRONMENT}"
    local namespace_info=$(aws servicediscovery list-namespaces \
        --region "$AWS_REGION" \
        --query "Namespaces[?Name=='$namespace_name']" 2>/dev/null)
    
    if [ "$(echo "$namespace_info" | jq length)" -gt 0 ]; then
        log_success "Service Discovery namespace found: $namespace_name"
        
        # Check services in the namespace
        local namespace_id=$(echo "$namespace_info" | jq -r '.[0].Id')
        local services_count=$(aws servicediscovery list-services \
            --region "$AWS_REGION" \
            --filters "Name=NAMESPACE_ID,Values=$namespace_id" \
            --query 'Services | length' --output text 2>/dev/null || echo "0")
        
        log_success "Service Discovery services: $services_count registered"
        return 0
    else
        log_error "Service Discovery namespace not found: $namespace_name"
        return 1
    fi
}

# Check Auto Scaling
check_auto_scaling() {
    log_info "Checking Auto Scaling configuration..."
    
    local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    local api_gateway_resource="service/${cluster_name}/${PROJECT_NAME}-${ENVIRONMENT}-api-gateway"
    
    # Check if auto-scaling target is registered
    local scaling_targets=$(aws application-autoscaling describe-scalable-targets \
        --service-namespace ecs \
        --resource-ids "$api_gateway_resource" \
        --region "$AWS_REGION" \
        --query 'ScalableTargets | length' --output text 2>/dev/null || echo "0")
    
    if [ "$scaling_targets" -gt 0 ]; then
        log_success "Auto Scaling target registered for API Gateway"
        
        # Check scaling policies
        local scaling_policies=$(aws application-autoscaling describe-scaling-policies \
            --service-namespace ecs \
            --resource-id "$api_gateway_resource" \
            --region "$AWS_REGION" \
            --query 'ScalingPolicies | length' --output text 2>/dev/null || echo "0")
        
        log_success "Auto Scaling policies configured: $scaling_policies"
        return 0
    else
        log_warning "Auto Scaling not configured for API Gateway"
        return 1
    fi
}

# Check CloudWatch logs
check_cloudwatch_logs() {
    log_info "Checking CloudWatch logs..."
    
    local log_groups=(
        "/aws/ecs/${PROJECT_NAME}-${ENVIRONMENT}/api-gateway"
        "/aws/ecs/${PROJECT_NAME}-${ENVIRONMENT}/agents"
        "/aws/ecs/${PROJECT_NAME}-${ENVIRONMENT}/guardrails"
    )
    
    local logs_healthy=true
    
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-groups \
            --log-group-name-prefix "$log_group" \
            --region "$AWS_REGION" \
            --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$log_group"; then
            log_success "Log group exists: $log_group"
        else
            log_warning "Log group not found: $log_group"
            logs_healthy=false
        fi
    done
    
    if $logs_healthy; then
        return 0
    else
        return 1
    fi
}

# Check ECR repositories
check_ecr_repositories() {
    log_info "Checking ECR repositories..."
    
    local repositories=("api-gateway" "agents" "guardrails" "processing" "retrieval")
    local repos_healthy=true
    
    for repo in "${repositories[@]}"; do
        local repo_name="${PROJECT_NAME}/${repo}"
        
        if aws ecr describe-repositories \
            --repository-names "$repo_name" \
            --region "$AWS_REGION" &> /dev/null; then
            
            # Check if repository has images
            local image_count=$(aws ecr list-images \
                --repository-name "$repo_name" \
                --region "$AWS_REGION" \
                --query 'imageIds | length' --output text 2>/dev/null || echo "0")
            
            log_success "ECR repository $repo_name: $image_count images"
        else
            log_warning "ECR repository not found: $repo_name"
            repos_healthy=false
        fi
    done
    
    if $repos_healthy; then
        return 0
    else
        return 1
    fi
}

# Test basic connectivity
test_connectivity() {
    if [ -n "$ALB_URL" ]; then
        log_info "Testing basic connectivity to $ALB_URL..."
        
        if curl -f -s --max-time 10 "http://$ALB_URL/health" > /dev/null; then
            log_success "Basic connectivity test passed"
            return 0
        else
            log_error "Basic connectivity test failed"
            return 1
        fi
    else
        log_warning "No ALB URL available for connectivity test"
        return 1
    fi
}

# Print deployment summary
print_summary() {
    echo ""
    echo "🚀 VESPER Enhanced Deployment Summary"
    echo "====================================="
    
    if [ -n "$ALB_URL" ]; then
        echo "🌐 Application URL: http://$ALB_URL"
        echo "🔍 Health Check: http://$ALB_URL/health"
        echo "📊 Metrics: http://$ALB_URL/metrics"
        echo "📚 API Docs: http://$ALB_URL/docs"
        echo ""
    fi
    
    echo "📋 Infrastructure Components:"
    echo "  • ECS Cluster: ${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    echo "  • Load Balancer: ${PROJECT_NAME}-${ENVIRONMENT}-alb"
    echo "  • Service Discovery: ${PROJECT_NAME}-${ENVIRONMENT}"
    echo "  • ECR Repositories: vesper/{api-gateway,agents,guardrails,processing,retrieval}"
    echo ""
    
    echo "⚡ Next Steps:"
    echo "  1. Run integration tests: ./scripts/test-enhanced.sh"
    echo "  2. Set up monitoring dashboards in Grafana"
    echo "  3. Configure SSL/TLS certificate for production"
    echo "  4. Set up CI/CD pipeline for automated deployments"
    echo ""
}

# Main verification function
main() {
    echo "🔍 VESPER Enhanced Deployment Verification"
    echo "=========================================="
    echo ""
    
    local checks_passed=0
    local total_checks=8
    
    # Run all checks
    if check_prerequisites; then ((checks_passed++)); fi
    if check_ecs_cluster; then ((checks_passed++)); fi
    if check_ecs_services; then ((checks_passed++)); fi
    if check_load_balancer; then ((checks_passed++)); fi
    if check_service_discovery; then ((checks_passed++)); fi
    if check_auto_scaling; then ((checks_passed++)); fi
    if check_cloudwatch_logs; then ((checks_passed++)); fi
    if check_ecr_repositories; then ((checks_passed++)); fi
    
    # Optional connectivity test
    test_connectivity
    
    echo ""
    echo "📊 Verification Results: $checks_passed/$total_checks checks passed"
    
    if [ $checks_passed -eq $total_checks ]; then
        log_success "🎉 Deployment verification completed successfully!"
        print_summary
        exit 0
    else
        log_warning "⚠️  Some verification checks failed. Please review the logs."
        print_summary
        exit 1
    fi
}

# Handle script arguments
case "${1:-verify}" in
    "quick")
        check_prerequisites
        check_ecs_cluster
        check_load_balancer
        test_connectivity
        ;;
    "verify"|*)
        main
        ;;
esac