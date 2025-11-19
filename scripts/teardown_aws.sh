#!/bin/bash
# AWS Teardown Script - Delete all vesper-dev resources
# Run with: bash scripts/teardown_aws.sh

set -e

REGION="ap-south-1"
CLUSTER="vesper-dev-cluster"

echo "🔥 Starting AWS teardown for vesper-dev..."
echo "Region: $REGION"
echo ""

# 1. Stop and delete ECS service
echo "1️⃣  Stopping ECS service..."
aws ecs update-service \
  --cluster $CLUSTER \
  --service vesper-dev-api-gateway \
  --desired-count 0 \
  --region $REGION 2>/dev/null || echo "  ⚠️  Service not found or already stopped"

sleep 10

aws ecs delete-service \
  --cluster $CLUSTER \
  --service vesper-dev-api-gateway \
  --force \
  --region $REGION 2>/dev/null || echo "  ⚠️  Service not found"

echo "  ✅ ECS service stopped"

# 2. Delete ECS cluster
echo "2️⃣  Deleting ECS cluster..."
aws ecs delete-cluster \
  --cluster $CLUSTER \
  --region $REGION 2>/dev/null || echo "  ⚠️  Cluster not found"
echo "  ✅ ECS cluster deleted"

# 3. Delete RDS instance
echo "3️⃣  Deleting RDS instance (this takes ~10 minutes)..."
aws rds delete-db-instance \
  --db-instance-identifier vesper-dev-postgres \
  --skip-final-snapshot \
  --region $REGION 2>/dev/null || echo "  ⚠️  RDS instance not found"
echo "  ✅ RDS deletion initiated"

# 4. Delete ElastiCache Redis
echo "4️⃣  Deleting ElastiCache Redis..."
aws elasticache delete-replication-group \
  --replication-group-id vesper-dev-redis \
  --region $REGION 2>/dev/null || echo "  ⚠️  Redis not found"
echo "  ✅ Redis deletion initiated"

# 5. Delete Application Load Balancer
echo "5️⃣  Deleting Application Load Balancer..."
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --region $REGION \
  --query "LoadBalancers[?contains(LoadBalancerName, 'vesper-dev')].LoadBalancerArn" \
  --output text 2>/dev/null)

if [ ! -z "$ALB_ARN" ]; then
  aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $REGION
  echo "  ✅ ALB deleted"
else
  echo "  ⚠️  ALB not found"
fi

# 6. Delete Target Groups
echo "6️⃣  Deleting Target Groups..."
TG_ARNS=$(aws elbv2 describe-target-groups \
  --region $REGION \
  --query "TargetGroups[?contains(TargetGroupName, 'vesper-dev')].TargetGroupArn" \
  --output text 2>/dev/null)

for TG_ARN in $TG_ARNS; do
  sleep 10  # Wait for ALB deletion
  aws elbv2 delete-target-group --target-group-arn $TG_ARN --region $REGION 2>/dev/null || echo "  ⚠️  TG already deleted"
done
echo "  ✅ Target groups deleted"

# 7. Delete S3 buckets (except terraform state)
echo "7️⃣  Deleting S3 buckets..."
for BUCKET in vesper-dev-bronze vesper-dev-docs vesper-dev-artifacts vesper-dev-logs; do
  echo "  Emptying $BUCKET..."
  aws s3 rm s3://$BUCKET --recursive --region $REGION 2>/dev/null || echo "  ⚠️  Bucket not found"
  aws s3 rb s3://$BUCKET --region $REGION 2>/dev/null || echo "  ⚠️  Bucket not found"
done
echo "  ✅ S3 buckets deleted (kept vesper-terraform-state-dev)"

# 8. Delete Secrets Manager secrets
echo "8️⃣  Deleting Secrets Manager secrets..."
aws secretsmanager delete-secret \
  --secret-id vesper-dev-db-credentials \
  --force-delete-without-recovery \
  --region $REGION 2>/dev/null || echo "  ⚠️  Secret not found"
echo "  ✅ Secrets deleted"

# 9. Delete Cognito User Pool
echo "9️⃣  Deleting Cognito User Pool..."
USER_POOL_ID=$(aws cognito-idp list-user-pools \
  --max-results 50 \
  --region $REGION \
  --query "UserPools[?contains(Name, 'vesper-dev')].Id" \
  --output text 2>/dev/null)

if [ ! -z "$USER_POOL_ID" ]; then
  aws cognito-idp delete-user-pool --user-pool-id $USER_POOL_ID --region $REGION
  echo "  ✅ Cognito User Pool deleted"
else
  echo "  ⚠️  User Pool not found"
fi

# 10. Delete CloudWatch Log Groups
echo "🔟 Deleting CloudWatch Log Groups..."
for LOG_GROUP in $(aws logs describe-log-groups --region $REGION --query "logGroups[?contains(logGroupName, 'vesper')].logGroupName" --output text); do
  aws logs delete-log-group --log-group-name "$LOG_GROUP" --region $REGION 2>/dev/null || echo "  ⚠️  Log group not found"
done
echo "  ✅ CloudWatch logs deleted"

# 11. Delete NAT Gateways
echo "1️⃣1️⃣  Deleting NAT Gateways..."
VPC_ID=$(aws ec2 describe-vpcs \
  --region $REGION \
  --filters "Name=tag:Name,Values=vesper-dev*" \
  --query "Vpcs[0].VpcId" \
  --output text 2>/dev/null)

if [ ! -z "$VPC_ID" ] && [ "$VPC_ID" != "None" ]; then
  NAT_IDS=$(aws ec2 describe-nat-gateways \
    --region $REGION \
    --filter "Name=vpc-id,Values=$VPC_ID" \
    --query "NatGateways[*].NatGatewayId" \
    --output text)
  
  for NAT_ID in $NAT_IDS; do
    aws ec2 delete-nat-gateway --nat-gateway-id $NAT_ID --region $REGION 2>/dev/null || echo "  ⚠️  NAT Gateway not found"
  done
  echo "  ✅ NAT Gateways deleted"
else
  echo "  ⚠️  VPC not found"
fi

echo ""
echo "⏳ Waiting for resources to delete (RDS, Redis, NAT take 5-15 minutes)..."
echo "   You can monitor deletion with:"
echo "   - RDS: aws rds describe-db-instances --region $REGION"
echo "   - Redis: aws elasticache describe-replication-groups --region $REGION"
echo ""
echo "After resources are deleted, run Terraform destroy for VPC:"
echo "   cd infrastructure/terraform/environments/dev"
echo "   terraform destroy"
echo ""
echo "✅ AWS teardown initiated!"
echo "   Estimated time to complete: 10-15 minutes"
echo "   Estimated cost savings: ~$150-200/month"
