# Cache Module - ElastiCache Redis Cluster
# Creates a production-ready Redis cluster for caching and session storage

terraform {
  required_version = ">= 1.0"
}

# Security Group for Redis
resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-redis-"
  vpc_id      = var.vpc_id
  description = "Security group for Redis cluster"

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
    description     = "Redis access from application"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-redis-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = var.subnet_ids

  tags = var.tags
}

# ElastiCache Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name        = "${var.project_name}-redis-${var.environment != "" ? var.environment : "default"}"
  family      = "redis7"
  description = "Custom parameter group for ${var.project_name} Redis"

  parameter {
    name  = "maxmemory-policy"
    value = var.maxmemory_policy
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ElastiCache Replication Group (Redis Cluster)
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-redis"
  description          = "Redis cluster for ${var.project_name}"
  
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
  
  # High availability
  automatic_failover_enabled = var.num_cache_nodes > 1 ? true : false
  multi_az_enabled           = var.num_cache_nodes > 1 ? true : false
  
  # Backup and maintenance
  snapshot_retention_limit   = var.snapshot_retention_limit
  snapshot_window            = var.snapshot_window
  maintenance_window         = var.maintenance_window
  
  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = var.transit_encryption_enabled
  auth_token                 = var.transit_encryption_enabled ? random_password.redis_auth[0].result : null
  kms_key_id                 = var.kms_key_id
  
  # Notifications
  notification_topic_arn = var.notification_topic_arn
  
  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }
  
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-redis"
    }
  )
}

# Random auth token for Redis
resource "random_password" "redis_auth" {
  count   = var.transit_encryption_enabled ? 1 : 0
  length  = 32
  special = false
}

# Store auth token in Secrets Manager
resource "aws_secretsmanager_secret" "redis_auth" {
  count                   = var.transit_encryption_enabled ? 1 : 0
  name_prefix             = "${var.project_name}-redis-auth-"
  recovery_window_in_days = 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  count     = var.transit_encryption_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.redis_auth[0].id
  secret_string = jsonencode({
    auth_token           = random_password.redis_auth[0].result
    primary_endpoint     = aws_elasticache_replication_group.main.primary_endpoint_address
    reader_endpoint      = aws_elasticache_replication_group.main.reader_endpoint_address
    configuration_endpoint = aws_elasticache_replication_group.main.configuration_endpoint_address
    port                 = 6379
  })
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "slow_log" {
  name              = "/aws/elasticache/${var.project_name}-redis/slow-log"
  retention_in_days = 7

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "engine_log" {
  name              = "/aws/elasticache/${var.project_name}-redis/engine-log"
  retention_in_days = 7

  tags = var.tags
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-redis-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "Redis CPU utilization over 75%"

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "memory" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-redis-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "90"
  alarm_description   = "Redis memory usage over 90%"

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "evictions" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-redis-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "100"
  alarm_description   = "Redis evictions over 100 in 5 minutes"

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = var.tags
}
