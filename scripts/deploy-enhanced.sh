#!/bin/bash
#
# VESPER Enhanced Services Deployment Script
# Builds and deploys all integrated services to AWS ECS
#

set -e

# Configuration
PROJECT_NAME="vesper"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-ap-south-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

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
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install it first."
        exit 1
    fi
    
    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform not found. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Login to ECR
ecr_login() {
    log_info "Logging in to Amazon ECR..."
    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
    log_success "ECR login successful"
}

# Create ECR repositories if they don't exist
create_ecr_repositories() {
    log_info "Creating ECR repositories..."
    
    services=("api-gateway" "agents" "guardrails" "processing" "retrieval")
    
    for service in "${services[@]}"; do
        repo_name="${PROJECT_NAME}-${service}"
        
        if ! aws ecr describe-repositories --repository-names ${repo_name} --region ${AWS_REGION} &> /dev/null; then
            log_info "Creating ECR repository: ${repo_name}"
            aws ecr create-repository \
                --repository-name ${repo_name} \
                --region ${AWS_REGION} \
                --image-scanning-configuration scanOnPush=true
        else
            log_info "ECR repository ${repo_name} already exists"
        fi
    done
    
    log_success "ECR repositories ready"
}

# Build and push Docker images
build_and_push_images() {
    log_info "Building and pushing Docker images..."
    
    # Get the current git commit hash for tagging
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
    
    # Build API Gateway
    log_info "Building API Gateway image..."
    cd services/api-gateway
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:${GIT_COMMIT} .
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:latest .
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:${GIT_COMMIT}
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:latest
    cd ../..
    
    # Build Agents Service
    log_info "Building Agents service image..."
    cd services/agents
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-agents:${GIT_COMMIT} .
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-agents:latest .
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-agents:${GIT_COMMIT}
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-agents:latest
    cd ../..
    
    # Build Guardrails Service
    log_info "Building Guardrails service image..."
    cd services/guardrails
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-guardrails:${GIT_COMMIT} .
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-guardrails:latest .
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-guardrails:${GIT_COMMIT}
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-guardrails:latest
    cd ../..
    
    # Build Processing Service
    log_info "Building Processing service image..."
    cd services/processing
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-processing:${GIT_COMMIT} .
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-processing:latest .
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-processing:${GIT_COMMIT}
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-processing:latest
    cd ../..
    
    # Build Retrieval Service
    log_info "Building Retrieval service image..."
    cd services/retrieval
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-retrieval:${GIT_COMMIT} .
    docker build -t ${ECR_REGISTRY}/${PROJECT_NAME}-retrieval:latest .
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-retrieval:${GIT_COMMIT}
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-retrieval:latest
    cd ../..
    
    log_success "All images built and pushed successfully"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    log_info "Deploying infrastructure with Terraform..."
    
    cd infrastructure/terraform/environments/${ENVIRONMENT}
    
    # Initialize Terraform
    terraform init
    
    # Plan deployment
    log_info "Planning Terraform deployment..."
    terraform plan \
        -var="api_gateway_image=${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:latest" \
        -var="agents_image=${ECR_REGISTRY}/${PROJECT_NAME}-agents:latest" \
        -var="guardrails_image=${ECR_REGISTRY}/${PROJECT_NAME}-guardrails:latest" \
        -var="processing_image=${ECR_REGISTRY}/${PROJECT_NAME}-processing:latest" \
        -var="retrieval_image=${ECR_REGISTRY}/${PROJECT_NAME}-retrieval:latest" \
        -out=tfplan
    
    # Apply deployment
    log_info "Applying Terraform configuration..."
    terraform apply tfplan
    
    cd ../../../..
    
    log_success "Infrastructure deployment completed"
}

# Wait for services to be healthy
wait_for_services() {
    log_info "Waiting for services to become healthy..."
    
    # Get the load balancer URL
    ALB_URL=$(aws elbv2 describe-load-balancers \
        --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
        --region ${AWS_REGION} \
        --query 'LoadBalancers[0].DNSName' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$ALB_URL" ]; then
        log_warning "Could not get ALB URL. Services may still be deploying."
        return
    fi
    
    log_info "Load Balancer URL: http://${ALB_URL}"
    
    # Wait for health check
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Checking health (attempt $attempt/$max_attempts)..."
        
        if curl -f -s "http://${ALB_URL}/health" > /dev/null; then
            log_success "Services are healthy!"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_warning "Services may still be starting up. Check the AWS console for status."
            break
        fi
        
        sleep 30
        attempt=$((attempt + 1))
    done
}

# Deploy monitoring stack
deploy_monitoring() {
    log_info "Deploying monitoring stack..."
    
    # Create CloudWatch dashboard
    aws cloudwatch put-dashboard \
        --dashboard-name "${PROJECT_NAME}-${ENVIRONMENT}-overview" \
        --dashboard-body file://monitoring/cloudwatch-dashboard.json \
        --region ${AWS_REGION} 2>/dev/null || log_warning "CloudWatch dashboard creation failed"
    
    # Set up CloudWatch alarms
    log_info "Setting up CloudWatch alarms..."
    
    # High CPU alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name "${PROJECT_NAME}-${ENVIRONMENT}-high-cpu" \
        --alarm-description "High CPU utilization" \
        --metric-name CPUUtilization \
        --namespace AWS/ECS \
        --statistic Average \
        --period 300 \
        --threshold 80 \
        --comparison-operator GreaterThanThreshold \
        --evaluation-periods 2 \
        --region ${AWS_REGION} 2>/dev/null || log_warning "CPU alarm creation failed"
    
    # High memory alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name "${PROJECT_NAME}-${ENVIRONMENT}-high-memory" \
        --alarm-description "High memory utilization" \
        --metric-name MemoryUtilization \
        --namespace AWS/ECS \
        --statistic Average \
        --period 300 \
        --threshold 85 \
        --comparison-operator GreaterThanThreshold \
        --evaluation-periods 2 \
        --region ${AWS_REGION} 2>/dev/null || log_warning "Memory alarm creation failed"
    
    log_success "Monitoring setup completed"
}

# Print deployment summary
print_summary() {
    log_success "🎉 VESPER Enhanced Services Deployment Complete!"
    
    echo ""
    echo "📊 Deployment Summary:"
    echo "  Environment: ${ENVIRONMENT}"
    echo "  Region: ${AWS_REGION}"
    echo "  Services Deployed: 5 (API Gateway, Agents, Guardrails, Processing, Retrieval)"
    echo ""
    
    # Get ALB URL
    ALB_URL=$(aws elbv2 describe-load-balancers \
        --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
        --region ${AWS_REGION} \
        --query 'LoadBalancers[0].DNSName' \
        --output text 2>/dev/null || echo "Not available")
    
    if [ "$ALB_URL" != "Not available" ]; then
        echo "🔗 Service URLs:"
        echo "  API Gateway: http://${ALB_URL}"
        echo "  Health Check: http://${ALB_URL}/health"
        echo "  API Docs: http://${ALB_URL}/docs"
        echo "  Metrics: http://${ALB_URL}/metrics"
        echo ""
    fi
    
    echo "🔧 Management URLs:"
    echo "  AWS ECS Console: https://${AWS_REGION}.console.aws.amazon.com/ecs/v2/clusters/${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    echo "  CloudWatch Logs: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups"
    echo "  CloudWatch Metrics: https://${AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#metricsV2:"
    echo ""
    
    echo "📈 Next Steps:"
    echo "  1. Test the API: curl http://${ALB_URL}/health"
    echo "  2. Check service logs in CloudWatch"
    echo "  3. Monitor metrics in CloudWatch dashboard"
    echo "  4. Set up Grafana dashboards (optional)"
    echo ""
}

# Main deployment function
main() {
    log_info "🚀 Starting VESPER Enhanced Services Deployment..."
    
    check_prerequisites
    ecr_login
    create_ecr_repositories
    build_and_push_images
    deploy_infrastructure
    deploy_monitoring
    wait_for_services
    print_summary
}

# Handle script arguments
case "${1:-deploy}" in
    "build-only")
        log_info "Building images only..."
        check_prerequisites
        ecr_login
        create_ecr_repositories
        build_and_push_images
        ;;
    "deploy-only")
        log_info "Deploying infrastructure only..."
        check_prerequisites
        deploy_infrastructure
        deploy_monitoring
        wait_for_services
        print_summary
        ;;
    "destroy")
        log_warning "🔥 Destroying VESPER infrastructure..."
        read -p "Are you sure you want to destroy the ${ENVIRONMENT} environment? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            cd infrastructure/terraform/environments/${ENVIRONMENT}
            terraform destroy -auto-approve
            cd ../../../..
            log_success "Infrastructure destroyed"
        else
            log_info "Destruction cancelled"
        fi
        ;;
    "deploy"|*)
        main
        ;;
esac