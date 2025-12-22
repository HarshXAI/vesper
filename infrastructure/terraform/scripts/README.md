# Terraform Cleanup Scripts

Scripts for safely destroying all AWS resources created by Terraform.

## Scripts

### 1. destroy-all.sh (Recommended)

**Comprehensive, safe destruction with multiple safeguards.**

Features:

- ✅ Multiple confirmation prompts
- ✅ Pre-flight checks (AWS credentials, Terraform state)
- ✅ Automatic resource preparation (disable protections, empty S3)
- ✅ Detailed logging to file
- ✅ Post-destruction verification
- ✅ Destruction report generation
- ✅ Orphaned resource cleanup

Usage:

```bash
cd infrastructure/terraform/scripts
chmod +x destroy-all.sh
./destroy-all.sh
```

What it does:

1. Checks prerequisites (Terraform, AWS CLI, credentials)
2. Counts resources to be destroyed
3. Requires typing "DELETE EVERYTHING" and "YES" to confirm
4. Scales down ECS services to 0
5. Terminates all ECS tasks
6. Disables deletion protection on RDS and ALB
7. Empties all S3 buckets (including versioned objects)
8. Runs `terraform destroy -auto-approve`
9. Deletes CloudWatch log groups
10. Cleans up orphaned ENIs and security groups
11. Removes local Terraform state files
12. Verifies all resources are deleted
13. Generates destruction report

**Estimated Time:** 15-25 minutes

### 2. quick-destroy.sh

**Fast destruction for dev environments with minimal interaction.**

⚠️ **WARNING:** Only one confirmation prompt. Use only for dev!

Features:

- Minimal prompts (single y/N confirmation)
- Empties S3 buckets
- Disables RDS deletion protection
- Runs Terraform destroy
- Cleans up local state

Usage:

```bash
cd infrastructure/terraform/scripts
chmod +x quick-destroy.sh
./quick-destroy.sh
```

**Estimated Time:** 10-15 minutes

## When to Use Each Script

### Use destroy-all.sh when:

- Destroying production or staging environments
- You want detailed logs and reports
- You need verification of cleanup
- You want safeguards against accidental deletion
- You're new to Terraform destruction

### Use quick-destroy.sh when:

- Destroying dev/test environments repeatedly
- You're comfortable with the risks
- You want fast iteration during development
- You trust your backups

## Pre-Destruction Checklist

Before running either script:

1. **Backup Critical Data**

   ```bash
   # Backup RDS
   aws rds create-db-snapshot \
     --db-instance-identifier vesper-db \
     --db-snapshot-identifier vesper-backup-$(date +%Y%m%d)

   # Backup S3
   aws s3 sync s3://vesper-data-lake-dev ./backup/data-lake/
   ```

2. **Export Terraform State**

   ```bash
   cd infrastructure/terraform/environments/dev
   terraform show -json > terraform-state-backup.json
   ```

3. **Verify AWS Account**

   ```bash
   aws sts get-caller-identity
   # Make sure you're in the correct AWS account!
   ```

4. **Check for External Dependencies**
   - DNS records pointing to ALB
   - External services using RDS/Redis endpoints
   - Scheduled jobs accessing S3 buckets
   - API keys/credentials stored in Secrets Manager

## What Gets Deleted

Both scripts will delete:

**Networking:**

- VPC and all subnets
- Internet Gateway
- NAT Gateways (2)
- Route tables and associations
- Security groups
- Network ACLs
- VPC endpoints

**Compute:**

- ECS Fargate cluster
- All running ECS tasks
- ECS task definitions
- Application Load Balancer
- Target groups
- ALB listeners

**Database:**

- RDS PostgreSQL instance
- All databases and data (PERMANENT)
- Automated backups
- DB subnet group
- DB parameter group

**Cache:**

- ElastiCache Redis cluster
- All cached data (PERMANENT)
- Cache subnet group
- Cache parameter group

**Storage:**

- All S3 buckets
- All files and objects (PERMANENT)
- Versioned objects and delete markers

**Monitoring:**

- CloudWatch log groups
- CloudWatch alarms
- Metric filters

**Security:**

- IAM roles and policies
- Secrets Manager secrets (with recovery window)

**Other:**

- CloudWatch Logs
- ENI attachments
- Elastic IPs

## Troubleshooting

### Script Fails with "State Lock" Error

```bash
# Force unlock (use with caution)
cd infrastructure/terraform/environments/dev
terraform force-unlock <LOCK_ID>
```

### Resources Still Exist After Script

Some resources may have dependencies preventing deletion:

```bash
# Manually delete VPC
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Project,Values=vesper" --query "Vpcs[0].VpcId" --output text)
aws ec2 delete-vpc --vpc-id $VPC_ID

# Manually delete security groups
aws ec2 describe-security-groups --filters "Name=group-name,Values=*vesper*" --query "SecurityGroups[].GroupId" --output text | \
xargs -I {} aws ec2 delete-security-group --group-id {}
```

### S3 Bucket Won't Delete

```bash
# Force empty and delete
BUCKET="vesper-data-lake-dev"
aws s3 rm s3://$BUCKET --recursive
aws s3api delete-bucket --bucket $BUCKET
```

### RDS Snapshot Prevention

If you see "Cannot delete with SkipFinalSnapshot=false":

```bash
# Delete with snapshot
aws rds delete-db-instance \
  --db-instance-identifier vesper-db \
  --skip-final-snapshot

# Or create snapshot first
aws rds delete-db-instance \
  --db-instance-identifier vesper-db \
  --final-db-snapshot-identifier vesper-final-snapshot
```

### ElastiCache Won't Delete

```bash
# Force delete replication group
aws elasticache delete-replication-group \
  --replication-group-id vesper-redis \
  --no-retain-primary-cluster
```

## Cost Savings

After destruction:

- **Immediate:** ECS tasks stop (saves ~$58/month per task)
- **Within 1 hour:** NAT Gateway released (saves ~$32/month per AZ)
- **Within 24 hours:** RDS instance deleted (saves ~$61-584/month)
- **Within 24 hours:** Redis deleted (saves ~$12-260/month)

Total savings: **$226-1,211/month** depending on configuration

## Recovery After Destruction

To recreate infrastructure:

```bash
cd infrastructure/terraform/environments/dev

# Restore from backup (if needed)
cp terraform.tfvars.backup terraform.tfvars

# Deploy
terraform init
terraform plan
terraform apply

# Restore data
aws s3 sync ./backup/data-lake/ s3://vesper-data-lake-dev/
```

## Safety Features in destroy-all.sh

1. **Multiple Confirmations:** Requires typing exact phrases
2. **5-second Countdown:** Final chance to Ctrl+C
3. **Pre-flight Checks:** Verifies credentials and state
4. **Detailed Logging:** All actions logged to timestamped file
5. **Post-Verification:** Checks for remaining resources
6. **Destruction Report:** Summary of what was deleted

## Log Files

Both scripts create log files in the `scripts/` directory:

- `destroy-YYYYMMDD-HHMMSS.log` - Detailed execution log
- `destruction-report-YYYYMMDD-HHMMSS.txt` - Final summary

Keep these logs for audit and troubleshooting purposes.

## Emergency Stop

If the script is running and you need to stop:

1. Press **Ctrl+C** to interrupt
2. Check for partially deleted resources:
   ```bash
   aws ec2 describe-vpcs --filters "Name=tag:Project,Values=vesper"
   aws rds describe-db-instances --query "DBInstances[?contains(DBInstanceIdentifier, 'vesper')]"
   ```
3. Run the script again to complete deletion, or manually clean up

## Best Practices

1. **Always backup before destroying:**

   - Export Terraform state
   - Snapshot RDS databases
   - Download critical S3 data

2. **Run during off-hours:**

   - Less chance of active users
   - Easier to monitor

3. **Verify AWS account:**

   - Double-check you're in the right account
   - Use separate AWS profiles for dev/prod

4. **Review costs first:**

   - Check current monthly spend
   - Understand what you're deleting

5. **Keep logs:**
   - Store destruction logs for compliance
   - Document reason for destruction

## Support

If you encounter issues:

1. Check log files in `scripts/` directory
2. Review [TROUBLESHOOTING.md](../../../TROUBLESHOOTING.md)
3. Manually inspect resources: `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=vesper`
4. Open GitHub issue with logs attached

---

**Remember:** Destruction is permanent. There is no undo button!
