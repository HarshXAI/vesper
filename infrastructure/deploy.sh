#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VESPER Infrastructure Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for required tools
command -v terraform >/dev/null 2>&1 || { echo -e "${RED}terraform is required but not installed. Aborting.${NC}" >&2; exit 1; }
command -v aws >/dev/null 2>&1 || { echo -e "${RED}aws CLI is required but not installed. Aborting.${NC}" >&2; exit 1; }

# Get environment (default: dev)
ENVIRONMENT=${1:-dev}
echo -e "${GREEN}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Check AWS credentials
echo -e "${YELLOW}Checking AWS credentials...${NC}"
aws sts get-caller-identity > /dev/null 2>&1 || { echo -e "${RED}AWS credentials not configured. Run 'aws configure' first.${NC}" >&2; exit 1; }
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
echo -e "${GREEN}✓ AWS Account: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${GREEN}✓ AWS Region: ${AWS_REGION}${NC}"
echo ""

# Navigate to environment directory
cd "$(dirname "$0")/terraform/environments/${ENVIRONMENT}" || { echo -e "${RED}Environment directory not found${NC}"; exit 1; }

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init
echo ""

# Validate configuration
echo -e "${YELLOW}Validating Terraform configuration...${NC}"
terraform validate
echo -e "${GREEN}✓ Configuration is valid${NC}"
echo ""

# Plan deployment
echo -e "${YELLOW}Planning deployment...${NC}"
echo -e "${BLUE}NOTE: Review the plan carefully before applying${NC}"
echo ""
terraform plan -out=tfplan

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Plan saved to tfplan${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Ask for confirmation
read -p "Do you want to apply this plan? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    rm -f tfplan
    exit 0
fi

# Apply deployment
echo ""
echo -e "${GREEN}Applying deployment...${NC}"
terraform apply tfplan

# Clean up plan file
rm -f tfplan

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Show outputs
echo -e "${BLUE}Infrastructure Outputs:${NC}"
terraform output

echo ""
echo -e "${BLUE}Quick reference:${NC}"
terraform output -raw connection_instructions

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "1. Update API keys in Secrets Manager:"
echo -e "   ${BLUE}aws secretsmanager put-secret-value --secret-id vesper-${ENVIRONMENT}-api-keys --secret-string '{\"openai_key\":\"YOUR_KEY\",\"anthropic_key\":\"YOUR_KEY\"}'${NC}"
echo ""
echo -e "2. Build and push Docker image:"
echo -e "   ${BLUE}cd ../../apps/api-gateway${NC}"
echo -e "   ${BLUE}docker build -t vesper-api-gateway:latest .${NC}"
echo -e "   ${BLUE}docker tag vesper-api-gateway:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/vesper-${ENVIRONMENT}-api-gateway:latest${NC}"
echo -e "   ${BLUE}aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com${NC}"
echo -e "   ${BLUE}docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/vesper-${ENVIRONMENT}-api-gateway:latest${NC}"
echo ""
echo -e "3. Deploy API Gateway to ECS:"
echo -e "   ${BLUE}aws ecs update-service --cluster vesper-${ENVIRONMENT}-cluster --service vesper-${ENVIRONMENT}-api-gateway --force-new-deployment${NC}"
echo ""
echo -e "4. Test API Gateway:"
echo -e "   ${BLUE}curl http://\$(terraform output -raw alb_dns_name)/health${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
