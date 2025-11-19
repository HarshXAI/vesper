#!/bin/bash

# Create Lambda deployment package with psycopg2
echo "Creating Lambda deployment package for pgvector enablement..."

# Create temporary directory
mkdir -p /tmp/lambda_package
cd /tmp/lambda_package

# Copy the Python script
cp /Users/harshkanani/Desktop/vesper/scripts/enable_pgvector.py lambda_function.py

# Install psycopg2 for Lambda (compiled for Amazon Linux)
pip install psycopg2-binary -t .

# Create zip package
zip -r /Users/harshkanani/Desktop/vesper/scripts/enable_pgvector.zip .

# Clean up
cd /Users/harshkanani/Desktop/vesper
rm -rf /tmp/lambda_package

echo "Lambda package created: scripts/enable_pgvector.zip"