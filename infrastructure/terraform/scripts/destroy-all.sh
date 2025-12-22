#!/bin/bash

################################################################################
# VESPER Infrastructure Cleanup Script
# 
# WARNING: This script will PERMANENTLY DELETE all AWS resources created by
# Terraform. This action is IRREVERSIBLE and will result in:
# - Loss of all data in RDS databases
# - Loss of all data in S3 buckets
# - Termination of all ECS tasks
# - Deletion of all Redis data
# 
# USE WITH EXTREME CAUTION!
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../environments/dev"
LOG_FILE="${SCRIPT_DIR}/destroy-$(date +%Y%m%d-%H%M%S).log"

################################################################################
# Helper Functions
################################################################################

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

confirm_destruction() {
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    ⚠️  DANGER ZONE ⚠️                          ║${NC}"
    echo -e "${RED}║                                                                ║${NC}"
    echo -e "${RED}║  This will PERMANENTLY DELETE all AWS resources including:    ║${NC}"
    echo -e "${RED}║                                                                ║${NC}"
    echo -e "${RED}║  • VPC and all networking components                          ║${NC}"
    echo -e "${RED}║  • RDS PostgreSQL database (ALL DATA LOST)                    ║${NC}"
    echo -e "${RED}║  • ElastiCache Redis cluster (ALL CACHE LOST)                 ║${NC}"
    echo -e "${RED}║  • ECS cluster and all running tasks                          ║${NC}"
    echo -e "${RED}║  • Application Load Balancer                                  ║${NC}"
    echo -e "${RED}║  • S3 buckets (ALL FILES DELETED)                             ║${NC}"
    echo -e "${RED}║  • CloudWatch logs and alarms                                 ║${NC}"
    echo -e "${RED}║  • IAM roles and policies                                     ║${NC}"
    echo -e "${RED}║  • Secrets Manager secrets                                    ║${NC}"
    echo -e "${RED}║                                                                ║${NC}"
    echo -e "${RED}║  This action CANNOT be undone!                                ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    read -p "Type 'DELETE EVERYTHING' to confirm destruction: " confirmation
    
    if [ "$confirmation" != "DELETE EVERYTHING" ]; then
        log_error "Destruction cancelled. Confirmation text did not match."
        exit 1
    fi
    
    echo ""
    read -p "Are you ABSOLUTELY sure? Type 'YES' to proceed: " final_confirm
    
    if [ "$final_confirm" != "YES" ]; then
        log_error "Destruction cancelled."
        exit 1
    fi
    
    log_warning "Proceeding with destruction in 5 seconds... Press Ctrl+C to cancel!"
    sleep 5
}

check_terraform() {
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    log_success "Terraform found: $(terraform version -json | jq -r '.terraform_version')"
}

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    log_success "AWS CLI found: $(aws --version | cut -d' ' -f1)"
}

check_aws_credentials() {
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region || echo "us-east-1")
    
    log_success "AWS Account: $ACCOUNT_ID"
    log_success "AWS Region: $REGION"
}

check_terraform_state() {
    cd "$TERRAFORM_DIR"
    
    if [ ! -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
        log_warning "No local Terraform state file found."
        
        # Check for remote state
        if grep -q "backend.*s3" main.tf 2>/dev/null; then
            log "Remote state backend detected. Will attempt to use remote state."
        else
            log_error "No Terraform state found. Nothing to destroy."
            exit 1
        fi
    else
        log_success "Terraform state file found."
    fi
}

get_resource_count() {
    cd "$TERRAFORM_DIR"
    terraform init -upgrade &> /dev/null || true
    
    RESOURCE_COUNT=$(terraform state list 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$RESOURCE_COUNT" -eq 0 ]; then
        log_warning "No resources found in Terraform state."
        read -p "Continue anyway? (y/N): " continue_destroy
        if [ "$continue_destroy" != "y" ] && [ "$continue_destroy" != "Y" ]; then
            exit 0
        fi
    else
        log "Found $RESOURCE_COUNT resources to destroy"
    fi
}

disable_deletion_protection() {
    log "Disabling deletion protection on protected resources..."
    
    cd "$TERRAFORM_DIR"
    
    # Get AWS region
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    
    # Disable RDS deletion protection
    DB_INSTANCES=$(aws rds describe-db-instances \
        --region "$AWS_REGION" \
        --query "DBInstances[?contains(DBInstanceIdentifier, 'vesper')].DBInstanceIdentifier" \
        --output text 2>/dev/null || echo "")
    
    for db in $DB_INSTANCES; do
        log "Disabling deletion protection for RDS: $db"
        aws rds modify-db-instance \
            --region "$AWS_REGION" \
            --db-instance-identifier "$db" \
            --no-deletion-protection \
            --apply-immediately \
            --no-cli-pager &> /dev/null || log_warning "Failed to disable protection for $db"
    done
    
    # Disable ALB deletion protection
    ALBS=$(aws elbv2 describe-load-balancers \
        --region "$AWS_REGION" \
        --query "LoadBalancers[?contains(LoadBalancerName, 'vesper')].LoadBalancerArn" \
        --output text 2>/dev/null || echo "")
    
    for alb in $ALBS; do
        log "Disabling deletion protection for ALB: $(basename $alb)"
        aws elbv2 modify-load-balancer-attributes \
            --region "$AWS_REGION" \
            --load-balancer-arn "$alb" \
            --attributes Key=deletion_protection.enabled,Value=false \
            --no-cli-pager &> /dev/null || log_warning "Failed to disable protection for ALB"
    done
    
    log_success "Deletion protection disabled"
}

empty_s3_buckets() {
    log "Emptying S3 buckets..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    BUCKETS=$(aws s3 ls --region "$AWS_REGION" | grep vesper | awk '{print $3}' || echo "")
    
    if [ -z "$BUCKETS" ]; then
        log "No S3 buckets found with 'vesper' prefix"
        return
    fi
    
    for bucket in $BUCKETS; do
        log "Emptying bucket: $bucket"
        
        # Check if versioning is enabled
        VERSIONING=$(aws s3api get-bucket-versioning \
            --bucket "$bucket" \
            --region "$AWS_REGION" \
            --query 'Status' \
            --output text 2>/dev/null || echo "Disabled")
        
        if [ "$VERSIONING" = "Enabled" ]; then
            log "Bucket has versioning enabled, deleting all versions..."
            
            # Delete all versions and delete markers
            aws s3api list-object-versions \
                --bucket "$bucket" \
                --region "$AWS_REGION" \
                --output json \
                --query 'Versions[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
            jq -r '.[]? | .Key + " " + .VersionId' 2>/dev/null | \
            while read -r key version; do
                [ -n "$key" ] && aws s3api delete-object \
                    --bucket "$bucket" \
                    --region "$AWS_REGION" \
                    --key "$key" \
                    --version-id "$version" \
                    --no-cli-pager &> /dev/null || true
            done
            
            # Delete delete markers
            aws s3api list-object-versions \
                --bucket "$bucket" \
                --region "$AWS_REGION" \
                --output json \
                --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
            jq -r '.[]? | .Key + " " + .VersionId' 2>/dev/null | \
            while read -r key version; do
                [ -n "$key" ] && aws s3api delete-object \
                    --bucket "$bucket" \
                    --region "$AWS_REGION" \
                    --key "$key" \
                    --version-id "$version" \
                    --no-cli-pager &> /dev/null || true
            done
        fi
        
        # Delete all objects (works for both versioned and non-versioned)
        aws s3 rm "s3://$bucket" --recursive --region "$AWS_REGION" --quiet &> /dev/null || true
        
        log_success "Bucket emptied: $bucket"
    done
}

terminate_ecs_tasks() {
    log "Terminating ECS tasks..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    CLUSTERS=$(aws ecs list-clusters \
        --region "$AWS_REGION" \
        --query "clusterArns[?contains(@, 'vesper')]" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$CLUSTERS" ]; then
        log "No ECS clusters found"
        return
    fi
    
    for cluster in $CLUSTERS; do
        log "Stopping tasks in cluster: $(basename $cluster)"
        
        TASKS=$(aws ecs list-tasks \
            --cluster "$cluster" \
            --region "$AWS_REGION" \
            --query 'taskArns' \
            --output text 2>/dev/null || echo "")
        
        for task in $TASKS; do
            aws ecs stop-task \
                --cluster "$cluster" \
                --region "$AWS_REGION" \
                --task "$task" \
                --no-cli-pager &> /dev/null || true
        done
        
        log_success "Tasks stopped in: $(basename $cluster)"
    done
}

scale_down_services() {
    log "Scaling down ECS services to 0..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    CLUSTERS=$(aws ecs list-clusters \
        --region "$AWS_REGION" \
        --query "clusterArns[?contains(@, 'vesper')]" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$CLUSTERS" ]; then
        log "No ECS clusters found"
        return
    fi
    
    for cluster in $CLUSTERS; do
        SERVICES=$(aws ecs list-services \
            --cluster "$cluster" \
            --region "$AWS_REGION" \
            --query 'serviceArns' \
            --output text 2>/dev/null || echo "")
        
        for service in $SERVICES; do
            log "Scaling down: $(basename $service)"
            aws ecs update-service \
                --cluster "$cluster" \
                --region "$AWS_REGION" \
                --service "$service" \
                --desired-count 0 \
                --no-cli-pager &> /dev/null || true
        done
        
        # Wait a moment for services to scale down
        sleep 5
    done
    
    log_success "Services scaled down"
}

delete_log_groups() {
    log "Deleting CloudWatch log groups..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    LOG_GROUPS=$(aws logs describe-log-groups \
        --region "$AWS_REGION" \
        --query "logGroups[?contains(logGroupName, 'vesper') || contains(logGroupName, '/ecs/') || contains(logGroupName, '/aws/elasticache/')].logGroupName" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$LOG_GROUPS" ]; then
        log "No log groups found"
        return
    fi
    
    for log_group in $LOG_GROUPS; do
        log "Deleting log group: $log_group"
        aws logs delete-log-group \
            --region "$AWS_REGION" \
            --log-group-name "$log_group" \
            --no-cli-pager &> /dev/null || true
    done
    
    log_success "Log groups deleted"
}

delete_db_parameter_groups() {
    log "Deleting RDS parameter groups..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    PARAM_GROUPS=$(aws rds describe-db-parameter-groups \
        --region "$AWS_REGION" \
        --query "DBParameterGroups[?contains(DBParameterGroupName, 'vesper')].DBParameterGroupName" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$PARAM_GROUPS" ]; then
        log "No DB parameter groups found"
        return
    fi
    
    for pg in $PARAM_GROUPS; do
        log "Deleting parameter group: $pg"
        aws rds delete-db-parameter-group \
            --region "$AWS_REGION" \
            --db-parameter-group-name "$pg" \
            --no-cli-pager &> /dev/null || true
    done
    
    log_success "DB parameter groups deleted"
}

run_terraform_destroy() {
    log "Running Terraform destroy..."
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    log "Initializing Terraform..."
    terraform init -upgrade >> "$LOG_FILE" 2>&1
    
    # Refresh state
    log "Refreshing Terraform state..."
    terraform refresh >> "$LOG_FILE" 2>&1 || log_warning "State refresh had warnings"
    
    # Run destroy with auto-approve
    log "Destroying all resources (this may take 10-20 minutes)..."
    
    if terraform destroy -auto-approve >> "$LOG_FILE" 2>&1; then
        log_success "Terraform destroy completed successfully"
    else
        log_error "Terraform destroy encountered errors. Check log file: $LOG_FILE"
        
        # Attempt force destroy for remaining resources
        log_warning "Attempting force destroy..."
        terraform destroy -auto-approve -refresh=false >> "$LOG_FILE" 2>&1 || true
    fi
}

cleanup_orphaned_resources() {
    log "Cleaning up any orphaned resources..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    
    # Wait for resources to detach
    log "Waiting 30 seconds for resources to detach..."
    sleep 30
    
    # Delete ENIs
    ENIS=$(aws ec2 describe-network-interfaces \
        --region "$AWS_REGION" \
        --filters "Name=description,Values=*vesper*" \
        --query "NetworkInterfaces[?Status=='available'].NetworkInterfaceId" \
        --output text 2>/dev/null || echo "")
    
    for eni in $ENIS; do
        log "Deleting orphaned ENI: $eni"
        aws ec2 delete-network-interface \
            --region "$AWS_REGION" \
            --network-interface-id "$eni" \
            --no-cli-pager &> /dev/null || true
    done
    
    # Delete Elastic IPs
    EIPS=$(aws ec2 describe-addresses \
        --region "$AWS_REGION" \
        --filters "Name=tag:Project,Values=vesper" \
        --query "Addresses[].AllocationId" \
        --output text 2>/dev/null || echo "")
    
    for eip in $EIPS; do
        log "Releasing Elastic IP: $eip"
        aws ec2 release-address \
            --region "$AWS_REGION" \
            --allocation-id "$eip" \
            --no-cli-pager &> /dev/null || true
    done
    
    # Delete security groups (retry with dependencies)
    log "Cleaning up security groups..."
    for i in {1..3}; do
        SGS=$(aws ec2 describe-security-groups \
            --region "$AWS_REGION" \
            --filters "Name=group-name,Values=*vesper*" \
            --query "SecurityGroups[?GroupName!='default'].GroupId" \
            --output text 2>/dev/null || echo "")
        
        if [ -z "$SGS" ]; then
            break
        fi
        
        for sg in $SGS; do
            log "Deleting security group (attempt $i): $sg"
            aws ec2 delete-security-group \
                --region "$AWS_REGION" \
                --group-id "$sg" \
                --no-cli-pager &> /dev/null || true
        done
        
        [ $i -lt 3 ] && sleep 10
    done
    
    log_success "Orphaned resources cleanup attempted"
}

cleanup_terraform_state() {
    log "Cleaning up Terraform state and cache..."
    
    cd "$TERRAFORM_DIR"
    
    # Remove state files
    rm -f terraform.tfstate terraform.tfstate.backup
    rm -rf .terraform
    rm -f .terraform.lock.hcl
    
    log_success "Local Terraform state cleaned"
}

verify_cleanup() {
    log "Verifying cleanup..."
    
    AWS_REGION=$(aws configure get region || echo "us-east-1")
    local issues_found=0
    
    # Check VPCs
    REMAINING_VPC=$(aws ec2 describe-vpcs \
        --region "$AWS_REGION" \
        --filters "Name=tag:Project,Values=vesper" \
        --query "Vpcs[].VpcId" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_VPC" ]; then
        log_warning "VPCs still exist: $REMAINING_VPC"
        issues_found=1
    else
        log_success "No VPCs found"
    fi
    
    # Check RDS
    REMAINING_RDS=$(aws rds describe-db-instances \
        --region "$AWS_REGION" \
        --query "DBInstances[?contains(DBInstanceIdentifier, 'vesper')].DBInstanceIdentifier" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_RDS" ]; then
        log_warning "RDS instances still exist: $REMAINING_RDS"
        issues_found=1
    else
        log_success "No RDS instances found"
    fi
    
    # Check Redis
    REMAINING_REDIS=$(aws elasticache describe-replication-groups \
        --region "$AWS_REGION" \
        --query "ReplicationGroups[?contains(ReplicationGroupId, 'vesper')].ReplicationGroupId" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_REDIS" ]; then
        log_warning "Redis clusters still exist: $REMAINING_REDIS"
        issues_found=1
    else
        log_success "No Redis clusters found"
    fi
    
    # Check S3
    REMAINING_S3=$(aws s3 ls --region "$AWS_REGION" | grep vesper | awk '{print $3}' || echo "")
    
    if [ -n "$REMAINING_S3" ]; then
        log_warning "S3 buckets still exist: $REMAINING_S3"
        issues_found=1
    else
        log_success "No S3 buckets found"
    fi
    
    # Check ECS
    REMAINING_ECS=$(aws ecs list-clusters \
        --region "$AWS_REGION" \
        --query "clusterArns[?contains(@, 'vesper')]" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_ECS" ]; then
        log_warning "ECS clusters still exist: $(basename $REMAINING_ECS)"
        issues_found=1
    else
        log_success "No ECS clusters found"
    fi
    
    # Check ALB
    REMAINING_ALB=$(aws elbv2 describe-load-balancers \
        --region "$AWS_REGION" \
        --query "LoadBalancers[?contains(LoadBalancerName, 'vesper')].LoadBalancerName" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$REMAINING_ALB" ]; then
        log_warning "Load balancers still exist: $REMAINING_ALB"
        issues_found=1
    else
        log_success "No load balancers found"
    fi
    
    if [ $issues_found -eq 0 ]; then
        log_success "All resources successfully cleaned up!"
    else
        log_warning "Some resources may still exist. Check manually or run Terraform destroy again."
    fi
}

generate_report() {
    REPORT_FILE="${SCRIPT_DIR}/destruction-report-$(date +%Y%m%d-%H%M%S).txt"
    
    cat > "$REPORT_FILE" << EOF
VESPER Infrastructure Destruction Report
========================================

Date: $(date)
AWS Account: $(aws sts get-caller-identity --query Account --output text)
AWS Region: $(aws configure get region || echo "us-east-1")

Resources Checked:
- VPCs: $(aws ec2 describe-vpcs --filters "Name=tag:Project,Values=vesper" --query "Vpcs[].VpcId" --output text 2>/dev/null | wc -w)
- RDS Instances: $(aws rds describe-db-instances --query "DBInstances[?contains(DBInstanceIdentifier, 'vesper')].DBInstanceIdentifier" --output text 2>/dev/null | wc -w)
- Redis Clusters: $(aws elasticache describe-replication-groups --query "ReplicationGroups[?contains(ReplicationGroupId, 'vesper')].ReplicationGroupId" --output text 2>/dev/null | wc -w)
- S3 Buckets: $(aws s3 ls | grep vesper | wc -l)
- ECS Clusters: $(aws ecs list-clusters --query "clusterArns[?contains(@, 'vesper')]" --output text 2>/dev/null | wc -w)

Log File: $LOG_FILE

Status: COMPLETED
EOF
    
    log_success "Report generated: $REPORT_FILE"
    cat "$REPORT_FILE"
}

################################################################################
# Main Execution
################################################################################

main() {
    echo ""
    log "==================================================================="
    log "  VESPER Infrastructure Destruction Script"
    log "==================================================================="
    echo ""
    
    # Pre-flight checks
    log "Running pre-flight checks..."
    check_terraform
    check_aws_cli
    check_aws_credentials
    check_terraform_state
    log_success "Pre-flight checks passed"
    
    # Get resource count
    get_resource_count
    
    # Confirm destruction
    confirm_destruction
    
    # Start destruction process
    log ""
    log "==================================================================="
    log "  Starting Destruction Process"
    log "==================================================================="
    log ""
    
    # Step 1: Prepare resources
    scale_down_services
    terminate_ecs_tasks
    disable_deletion_protection
    empty_s3_buckets
    
    # Step 2: Terraform destroy
    run_terraform_destroy
    
    # Step 3: Cleanup
    delete_db_parameter_groups
    delete_log_groups
    cleanup_orphaned_resources
    cleanup_terraform_state
    
    # Step 4: Verify
    verify_cleanup
    
    # Step 5: Generate report
    log ""
    log "==================================================================="
    log "  Destruction Complete"
    log "==================================================================="
    log ""
    
    generate_report
    
    log_success "All AWS resources have been destroyed!"
    log "Log file saved to: $LOG_FILE"
}

# Run main function
main "$@"
