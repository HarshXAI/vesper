# Networking Module

Creates a production-ready VPC with public and private subnets across multiple availability zones.

## Features

- **Multi-AZ Architecture**: Subnets across 2+ availability zones for high availability
- **Public Subnets**: For load balancers and bastion hosts with direct internet access
- **Private Subnets**: For application servers and databases with NAT gateway egress
- **NAT Gateway**: Per-AZ NAT gateways for private subnet internet access (configurable)
- **VPC Flow Logs**: Optional network traffic logging for security and troubleshooting

## Usage

```hcl
module "networking" {
  source = "../../modules/networking"

  project_name       = "vesper"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]
  
  enable_nat_gateway = true
  enable_flow_logs   = false
  
  tags = {
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | - | yes |
| vpc_cidr | CIDR block for VPC | string | "10.0.0.0/16" | no |
| availability_zones | List of AZs | list(string) | - | yes |
| public_subnet_cidrs | Public subnet CIDRs | list(string) | - | yes |
| private_subnet_cidrs | Private subnet CIDRs | list(string) | - | yes |
| enable_nat_gateway | Enable NAT Gateway | bool | true | no |
| enable_flow_logs | Enable VPC Flow Logs | bool | false | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC ID |
| vpc_cidr | VPC CIDR block |
| public_subnet_ids | Public subnet IDs |
| private_subnet_ids | Private subnet IDs |
| nat_gateway_ids | NAT Gateway IDs |
| internet_gateway_id | Internet Gateway ID |

## Cost Considerations

- **NAT Gateway**: ~$32/month per AZ ($0.045/hour) + data processing fees
- **VPC Flow Logs**: CloudWatch Logs storage and ingestion costs (if enabled)
- **Total (2 AZs)**: ~$64/month for NAT Gateways + data transfer

## Architecture

```
Internet
    |
    v
[Internet Gateway]
    |
    +-- Public Subnet (AZ-A) -- [NAT Gateway] --+
    |                                             |
    +-- Public Subnet (AZ-B) -- [NAT Gateway] ---+
                                                  |
                                                  v
                                    +-- Private Subnet (AZ-A)
                                    |
                                    +-- Private Subnet (AZ-B)
```

## Security

- Public subnets have direct internet access via Internet Gateway
- Private subnets access internet via NAT Gateway (outbound only)
- No direct inbound access to private subnets from internet
- Flow Logs available for traffic analysis and security monitoring
