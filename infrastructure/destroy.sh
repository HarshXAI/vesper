#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}========================================${NC}"
echo -e "${RED}VESPER Infrastructure Destruction${NC}"
echo -e "${RED}========================================${NC}"
echo ""

# Get environment (default: dev)
ENVIRONMENT=${1:-dev}
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Safety check for production
if [ "$ENVIRONMENT" == "prod" ] || [ "$ENVIRONMENT" == "production" ]; then
    echo -e "${RED}WARNING: You are about to destroy the PRODUCTION environment!${NC}"
    echo -e "${RED}This action is IRREVERSIBLE and will delete ALL data!${NC}"
    echo ""
    read -p "Type 'destroy-production' to confirm: " CONFIRM
    if [ "$CONFIRM" != "destroy-production" ]; then
        echo -e "${YELLOW}Destruction cancelled${NC}"
        exit 0
    fi
fi

# Navigate to environment directory
cd "$(dirname "$0")/terraform/environments/${ENVIRONMENT}" || { echo -e "${RED}Environment directory not found${NC}"; exit 1; }

# Check if Terraform is initialized
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Terraform not initialized. Running init...${NC}"
    terraform init
fi

# Show what will be destroyed
echo -e "${YELLOW}Planning destruction...${NC}"
echo ""
terraform plan -destroy

echo ""
echo -e "${RED}========================================${NC}"
echo -e "${RED}WARNING: This will destroy:${NC}"
echo -e "${RED}========================================${NC}"
echo -e "- ECS Cluster and API Gateway tasks"
echo -e "- RDS PostgreSQL database (and all data)"
echo -e "- ElastiCache Redis cluster"
echo -e "- S3 buckets (if force_destroy=true)"
echo -e "- Application Load Balancer"
echo -e "- Cognito User Pool and users"
echo -e "- All secrets in Secrets Manager"
echo -e "- VPC and networking resources"
echo ""

# Final confirmation
read -p "Are you absolutely sure you want to destroy everything? (yes/no): " FINAL_CONFIRM

if [ "$FINAL_CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Destruction cancelled${NC}"
    exit 0
fi

# Destroy infrastructure
echo ""
echo -e "${RED}Destroying infrastructure...${NC}"
terraform destroy -auto-approve

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Infrastructure Destroyed${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Remaining cleanup tasks:${NC}"
echo -e "1. Check for any orphaned resources in AWS Console"
echo -e "2. Remove local Terraform state backups if needed"
echo -e "3. Delete S3 bucket with Terraform state if this was final environment"
echo ""
