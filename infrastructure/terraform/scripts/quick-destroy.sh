#!/bin/bash

################################################################################
# Quick Destroy Script - Minimal Interaction
# 
# WARNING: This will destroy ALL resources with minimal prompts!
# Use only for development/testing environments.
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../environments/dev"

echo -e "${RED}"
echo "╔════════════════════════════════════════╗"
echo "║  QUICK DESTROY - DEV ENVIRONMENT ONLY  ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

read -p "Destroy all resources? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled."
    exit 0
fi

cd "$TERRAFORM_DIR"

AWS_REGION=$(aws configure get region || echo "us-east-1")

echo -e "${GREEN}Scaling down ECS services...${NC}"
for cluster in $(aws ecs list-clusters --region "$AWS_REGION" --query "clusterArns[?contains(@, 'vesper')]" --output text 2>/dev/null); do
    for service in $(aws ecs list-services --cluster "$cluster" --region "$AWS_REGION" --query 'serviceArns' --output text 2>/dev/null); do
        echo "  → $(basename $service)"
        aws ecs update-service --cluster "$cluster" --region "$AWS_REGION" --service "$service" --desired-count 0 --no-cli-pager 2>/dev/null || true
    done
done

echo -e "${GREEN}Emptying S3 buckets...${NC}"
for bucket in $(aws s3 ls --region "$AWS_REGION" | grep vesper | awk '{print $3}'); do
    echo "  → $bucket"
    aws s3 rm "s3://$bucket" --recursive --region "$AWS_REGION" --quiet 2>/dev/null || true
done

echo -e "${GREEN}Disabling deletion protection...${NC}"
for db in $(aws rds describe-db-instances --region "$AWS_REGION" --query "DBInstances[?contains(DBInstanceIdentifier, 'vesper')].DBInstanceIdentifier" --output text 2>/dev/null); do
    echo "  → $db"
    aws rds modify-db-instance --region "$AWS_REGION" --db-instance-identifier "$db" --no-deletion-protection --apply-immediately --no-cli-pager 2>/dev/null || true
done

for alb in $(aws elbv2 describe-load-balancers --region "$AWS_REGION" --query "LoadBalancers[?contains(LoadBalancerName, 'vesper')].LoadBalancerArn" --output text 2>/dev/null); do
    echo "  → $(basename $alb)"
    aws elbv2 modify-load-balancer-attributes --region "$AWS_REGION" --load-balancer-arn "$alb" --attributes Key=deletion_protection.enabled,Value=false --no-cli-pager 2>/dev/null || true
done

echo -e "${GREEN}Running terraform destroy...${NC}"
terraform init -upgrade > /dev/null 2>&1
terraform destroy -auto-approve

echo -e "${GREEN}Cleaning up DB parameter groups...${NC}"
for pg in $(aws rds describe-db-parameter-groups --region "$AWS_REGION" --query "DBParameterGroups[?contains(DBParameterGroupName, 'vesper')].DBParameterGroupName" --output text 2>/dev/null); do
    echo "  → $pg"
    aws rds delete-db-parameter-group --region "$AWS_REGION" --db-parameter-group-name "$pg" --no-cli-pager 2>/dev/null || true
done

echo -e "${GREEN}Cleanup complete!${NC}"
rm -rf .terraform terraform.tfstate* .terraform.lock.hcl

echo ""
echo -e "${GREEN}✓ All resources destroyed${NC}"
