# VESPER Infrastructure - Development Environment
# Creates all AWS resources for dev environment

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment for remote state management
  # backend "s3" {
  #   bucket         = "vesper-terraform-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "vesper-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Local variables
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Networking Module
module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones

  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs

  enable_nat_gateway = var.enable_nat_gateway
  enable_flow_logs   = var.enable_flow_logs

  tags = local.common_tags
}

# Database Module
module "database" {
  source = "../../modules/database"

  project_name = var.project_name
  vpc_id       = module.networking.vpc_id
  subnet_ids   = module.networking.private_subnet_ids

  allowed_security_groups = [module.compute.ecs_security_group_id]

  instance_class            = var.db_instance_class
  engine_version            = var.db_engine_version
  allocated_storage         = var.db_allocated_storage
  max_allocated_storage     = var.db_max_allocated_storage
  database_name             = var.db_name
  master_username           = var.db_master_username

  multi_az                    = var.db_multi_az
  backup_retention_period     = var.db_backup_retention_period
  enable_deletion_protection  = var.db_deletion_protection
  skip_final_snapshot         = var.db_skip_final_snapshot
  enable_cloudwatch_alarms    = var.db_enable_alarms

  tags = local.common_tags
}

# Cache Module
module "cache" {
  source = "../../modules/cache"

  project_name = var.project_name
  vpc_id       = module.networking.vpc_id
  subnet_ids   = module.networking.private_subnet_ids

  allowed_security_groups = [module.compute.ecs_security_group_id]

  node_type                  = var.redis_node_type
  engine_version             = var.redis_engine_version
  num_cache_nodes            = var.redis_num_nodes
  maxmemory_policy           = var.redis_maxmemory_policy
  snapshot_retention_limit   = var.redis_snapshot_retention
  transit_encryption_enabled = var.redis_transit_encryption
  enable_cloudwatch_alarms   = var.redis_enable_alarms

  tags = local.common_tags
}

# Storage Module
module "storage" {
  source = "../../modules/storage"

  project_name      = var.project_name
  environment       = var.environment
  enable_versioning = var.s3_enable_versioning

  tags = local.common_tags
}

# Compute Module
module "compute" {
  source = "../../modules/compute"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids

  logs_bucket_name    = module.storage.logs_bucket_name
  database_secret_arn = module.database.secret_arn
  redis_secret_arn    = module.cache.auth_token_secret_arn != null ? module.cache.auth_token_secret_arn : ""

  api_gateway_image         = var.api_gateway_image
  api_gateway_cpu           = var.api_gateway_cpu
  api_gateway_memory        = var.api_gateway_memory
  api_gateway_desired_count = var.api_gateway_desired_count
  api_gateway_min_count     = var.api_gateway_min_count
  api_gateway_max_count     = var.api_gateway_max_count

  enable_container_insights  = var.ecs_enable_container_insights
  enable_deletion_protection = var.alb_deletion_protection

  tags = local.common_tags

  depends_on = [module.database, module.cache]
}
