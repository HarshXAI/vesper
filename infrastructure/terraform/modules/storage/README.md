# Storage Module

Creates S3 buckets for data lake, model artifacts, and application logs.

## Features

- **Data Lake Bucket**: Raw and processed financial data with lifecycle policies
- **Model Artifacts Bucket**: ML model weights and embeddings
- **Logs Bucket**: Application and ALB access logs
- **Encryption**: Server-side encryption with AES256 or KMS
- **Versioning**: Enabled for data lake and model artifacts
- **Lifecycle Policies**: Automatic transitions to cheaper storage tiers
- **Public Access Block**: All buckets are private by default

## Usage

```hcl
module "storage" {
  source = "../../modules/storage"

  project_name       = "vesper"
  environment        = "dev"
  enable_versioning  = true
  
  tags = {
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Project name | string | - | yes |
| environment | Environment name | string | - | yes |
| enable_versioning | Enable bucket versioning | bool | true | no |
| kms_key_id | KMS key for encryption | string | null | no |

## Outputs

| Name | Description |
|------|-------------|
| data_lake_bucket_name | Data lake bucket name |
| data_lake_bucket_arn | Data lake bucket ARN |
| model_artifacts_bucket_name | Model artifacts bucket name |
| logs_bucket_name | Logs bucket name |

## Bucket Structure

**Data Lake Bucket:**
```
vesper-data-lake-dev/
├── raw/
│   ├── sec-filings/
│   │   ├── 10-K/
│   │   ├── 10-Q/
│   │   └── 8-K/
│   └── market-data/
├── processed/
│   ├── tables/
│   └── embeddings/
└── archives/
```

**Model Artifacts Bucket:**
```
vesper-model-artifacts-dev/
├── embeddings/
│   ├── all-mpnet-base-v2/
│   └── custom-models/
├── models/
│   └── checkpoints/
└── configs/
```

## Lifecycle Policies

**Data Lake:**
- Day 0-90: STANDARD
- Day 90-180: STANDARD_IA (50% cheaper)
- Day 180-365: GLACIER_IR (70% cheaper)
- Day 365+: GLACIER (80% cheaper)

**Logs:**
- Expire after 90 days
- No versioning (logs are append-only)

## Cost Considerations

**Monthly Storage Costs (1TB total):**
- STANDARD (0-90 days): ~$23/TB/month
- STANDARD_IA (90-180 days): ~$12.50/TB/month
- GLACIER_IR (180-365 days): ~$4/TB/month
- GLACIER (365+ days): ~$1/TB/month

**Additional Costs:**
- PUT/COPY/POST requests: $0.005 per 1,000
- GET/SELECT requests: $0.0004 per 1,000
- Data transfer out: $0.09/GB

## Security

- All buckets encrypted at rest (AES256 or KMS)
- Public access blocked on all buckets
- Versioning enabled for data protection
- Bucket policies restrict access to AWS services only
- Optional KMS encryption for compliance requirements

## Usage Examples

**Python (boto3):**
```python
import boto3

s3 = boto3.client('s3')

# Upload file
s3.upload_file(
    'local_file.json',
    'vesper-data-lake-dev',
    'raw/sec-filings/10-K/AAPL-2024.json'
)

# Download file
s3.download_file(
    'vesper-data-lake-dev',
    'processed/embeddings/doc_123.npy',
    'local_embeddings.npy'
)
```

## Monitoring

CloudWatch metrics to monitor:
- **BucketSizeBytes**: Total storage used
- **NumberOfObjects**: Object count
- **AllRequests**: Request rate
- **4xxErrors**: Client errors
- **5xxErrors**: Server errors
