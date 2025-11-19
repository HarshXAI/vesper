#!/bin/bash

# Simple script to enable pgvector extension using EC2 as bastion
# This will create a temporary t3.nano instance in public subnet, run the command, and terminate

INSTANCE_TYPE="t3.nano"
SUBNET_ID="subnet-01549c5660bddf18a"  # Public subnet
SECURITY_GROUP="sg-0f5ef264b5357d6e1"  # ECS security group (has RDS access)
KEY_NAME="vesper-dev-key"  # We'll create this

echo "🚀 Setting up temporary EC2 bastion to enable pgvector..."

# Create a key pair if it doesn't exist
echo "Creating key pair..."
aws ec2 create-key-pair --key-name $KEY_NAME --region ap-south-1 --query 'KeyMaterial' --output text > ~/.ssh/vesper-dev-key.pem 2>/dev/null || echo "Key pair already exists"
chmod 600 ~/.ssh/vesper-dev-key.pem 2>/dev/null

# Get the latest Amazon Linux 2 AMI
echo "Getting latest Amazon Linux 2 AMI..."
AMI_ID=$(aws ec2 describe-images --owners amazon --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' --output text --region ap-south-1)

echo "Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --count 1 \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SECURITY_GROUP \
  --subnet-id $SUBNET_ID \
  --associate-public-ip-address \
  --user-data '#!/bin/bash
yum update -y
yum install -y postgresql
export PGPASSWORD="HlB0cSV9iJ+Nu4V740oGSo73HJAMR9KI"
psql -h vesper-dev-postgres.cho6qo6o2am7.ap-south-1.rds.amazonaws.com -U vesper_admin -d vesper -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -h vesper-dev-postgres.cho6qo6o2am7.ap-south-1.rds.amazonaws.com -U vesper_admin -d vesper -c "SELECT extname FROM pg_extension WHERE extname = '\''vector'\'';"
echo "pgvector extension setup complete!" > /var/log/pgvector-setup.log
shutdown -h +2' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=vesper-pgvector-setup},{Key=Purpose,Value=temporary-setup}]' \
  --region ap-south-1 \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "✅ Instance launched: $INSTANCE_ID"
echo "⏳ Waiting for instance to initialize and run setup..."
echo "📝 You can monitor progress with:"
echo "   aws logs get-log-events --log-group-name /aws/ec2/user-data --log-stream-name $INSTANCE_ID --region ap-south-1"

# Wait for instance to be running
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region ap-south-1

echo "✅ Instance is running. Setup script should complete in ~2 minutes."
echo "🗑️  Instance will auto-terminate after setup completes."
echo ""
echo "To check if pgvector was enabled successfully, run:"
echo "aws ec2 get-console-output --instance-id $INSTANCE_ID --region ap-south-1"