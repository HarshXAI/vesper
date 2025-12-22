# EventBridge Rules for VESPER Auto-Remediation
# ==============================================
# Triggers remediation DAGs based on CloudWatch Alarms and quality metrics

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "airflow_api_endpoint" {
  description = "Airflow API endpoint for triggering DAGs"
  type        = string
}

variable "airflow_dag_trigger_lambda_arn" {
  description = "ARN of Lambda function to trigger Airflow DAGs"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# ============================================================================
# EventBridge Event Bus
# ============================================================================

resource "aws_cloudwatch_event_bus" "vesper_remediation" {
  name = "vesper-remediation-${var.environment}"

  tags = merge(var.tags, {
    Name        = "vesper-remediation-${var.environment}"
    Purpose     = "Auto-remediation event routing"
  })
}

# ============================================================================
# EventBridge Rules
# ============================================================================

# Rule: NDCG Drop - Trigger Re-embed Subset DAG
resource "aws_cloudwatch_event_rule" "ndcg_drop" {
  name           = "vesper-ndcg-drop-${var.environment}"
  description    = "Trigger re-embed DAG when NDCG@10 drops below threshold"
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name

  event_pattern = jsonencode({
    source      = ["vesper.evaluation", "aws.cloudwatch"]
    detail-type = ["Metric Alarm State Change", "Quality Degradation"]
    detail = {
      metric_name = ["ndcg10", "NDCG10"]
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "ndcg_drop_target" {
  rule           = aws_cloudwatch_event_rule.ndcg_drop.name
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name
  target_id      = "trigger-reembed-dag"
  arn            = var.airflow_dag_trigger_lambda_arn

  input_transformer {
    input_paths = {
      metric_name  = "$.detail.metric_name"
      metric_value = "$.detail.current_value"
      threshold    = "$.detail.threshold"
      alarm_name   = "$.detail.alarmName"
    }
    input_template = <<EOF
{
  "dag_id": "reembed_subset",
  "conf": {
    "source": "eventbridge",
    "trigger_type": "ndcg_drop",
    "metric_name": <metric_name>,
    "metric_value": <metric_value>,
    "threshold": <threshold>,
    "alarm_name": <alarm_name>,
    "dry_run": false
  }
}
EOF
  }
}

# Rule: Recall Drop - Trigger Re-embed Subset DAG
resource "aws_cloudwatch_event_rule" "recall_drop" {
  name           = "vesper-recall-drop-${var.environment}"
  description    = "Trigger re-embed DAG when Recall@5 drops below threshold"
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name

  event_pattern = jsonencode({
    source      = ["vesper.evaluation", "aws.cloudwatch"]
    detail-type = ["Metric Alarm State Change", "Quality Degradation"]
    detail = {
      metric_name = ["recall5", "Recall5"]
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "recall_drop_target" {
  rule           = aws_cloudwatch_event_rule.recall_drop.name
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name
  target_id      = "trigger-reembed-dag"
  arn            = var.airflow_dag_trigger_lambda_arn

  input_transformer {
    input_paths = {
      metric_name  = "$.detail.metric_name"
      metric_value = "$.detail.current_value"
      threshold    = "$.detail.threshold"
    }
    input_template = <<EOF
{
  "dag_id": "reembed_subset",
  "conf": {
    "source": "eventbridge",
    "trigger_type": "recall_drop",
    "metric_name": <metric_name>,
    "metric_value": <metric_value>,
    "threshold": <threshold>
  }
}
EOF
  }
}

# Rule: Chunk Quality Issues - Trigger Rechunk DAG
resource "aws_cloudwatch_event_rule" "chunk_quality" {
  name           = "vesper-chunk-quality-${var.environment}"
  description    = "Trigger rechunk DAG when chunk quality metrics degrade"
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name

  event_pattern = jsonencode({
    source      = ["vesper.evaluation"]
    detail-type = ["Chunk Quality Alert"]
    detail = {
      issue_type = ["fragmentation", "coherence", "size_variance"]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "chunk_quality_target" {
  rule           = aws_cloudwatch_event_rule.chunk_quality.name
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name
  target_id      = "trigger-rechunk-dag"
  arn            = var.airflow_dag_trigger_lambda_arn

  input_transformer {
    input_paths = {
      issue_type   = "$.detail.issue_type"
      categories   = "$.detail.categories"
      severity     = "$.detail.severity"
    }
    input_template = <<EOF
{
  "dag_id": "rechunk_params",
  "conf": {
    "source": "eventbridge",
    "trigger_type": "chunk_quality",
    "issue_type": <issue_type>,
    "categories": <categories>,
    "severity": <severity>
  }
}
EOF
  }
}

# Rule: Nightly Eval Failure - Send Alert
resource "aws_cloudwatch_event_rule" "nightly_eval_failed" {
  name           = "vesper-nightly-eval-failed-${var.environment}"
  description    = "Alert when nightly evaluation DAG fails"
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name

  event_pattern = jsonencode({
    source      = ["aws.airflow"]
    detail-type = ["DAG Run State Change"]
    detail = {
      dag_id = ["nightly_evaluation"]
      state  = ["failed"]
    }
  })

  tags = var.tags
}

# Rule: Cost Budget Alert - Trigger Model Fallback
resource "aws_cloudwatch_event_rule" "cost_budget_alert" {
  name           = "vesper-cost-budget-${var.environment}"
  description    = "React to cost budget alerts"
  event_bus_name = aws_cloudwatch_event_bus.vesper_remediation.name

  event_pattern = jsonencode({
    source      = ["vesper.cost_governor"]
    detail-type = ["Budget Alert"]
    detail = {
      budget_state = ["warning", "critical", "exhausted"]
    }
  })

  tags = var.tags
}

# ============================================================================
# CloudWatch Alarms that Feed into EventBridge
# ============================================================================

resource "aws_cloudwatch_metric_alarm" "ndcg_low" {
  alarm_name          = "vesper-ndcg10-low-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "vesper_eval_ndcg10"
  namespace           = "VESPER/Evaluation"
  period              = 86400  # 24 hours
  statistic           = "Average"
  threshold           = 0.75
  alarm_description   = "NDCG@10 from nightly eval dropped below threshold"
  
  alarm_actions = [
    aws_sns_topic.remediation_alerts.arn
  ]

  dimensions = {
    Environment = var.environment
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "recall_low" {
  alarm_name          = "vesper-recall5-low-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "vesper_eval_recall5"
  namespace           = "VESPER/Evaluation"
  period              = 86400
  statistic           = "Average"
  threshold           = 0.85
  alarm_description   = "Recall@5 from nightly eval dropped below threshold"
  
  alarm_actions = [
    aws_sns_topic.remediation_alerts.arn
  ]

  dimensions = {
    Environment = var.environment
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "faithfulness_low" {
  alarm_name          = "vesper-faithfulness-low-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "vesper_eval_faithfulness"
  namespace           = "VESPER/Evaluation"
  period              = 86400
  statistic           = "Average"
  threshold           = 0.7
  alarm_description   = "Faithfulness score dropped below threshold"
  
  alarm_actions = [
    aws_sns_topic.remediation_alerts.arn
  ]

  dimensions = {
    Environment = var.environment
  }

  tags = var.tags
}

# ============================================================================
# SNS Topic for Remediation Alerts
# ============================================================================

resource "aws_sns_topic" "remediation_alerts" {
  name = "vesper-remediation-alerts-${var.environment}"
  
  tags = var.tags
}

resource "aws_sns_topic_subscription" "eventbridge" {
  topic_arn = aws_sns_topic.remediation_alerts.arn
  protocol  = "lambda"
  endpoint  = var.airflow_dag_trigger_lambda_arn
}

# ============================================================================
# IAM Permissions
# ============================================================================

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.airflow_dag_trigger_lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_bus.vesper_remediation.arn
}

resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.airflow_dag_trigger_lambda_arn
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.remediation_alerts.arn
}

# ============================================================================
# Outputs
# ============================================================================

output "event_bus_arn" {
  description = "ARN of the remediation EventBridge bus"
  value       = aws_cloudwatch_event_bus.vesper_remediation.arn
}

output "event_bus_name" {
  description = "Name of the remediation EventBridge bus"
  value       = aws_cloudwatch_event_bus.vesper_remediation.name
}

output "sns_topic_arn" {
  description = "ARN of the remediation SNS topic"
  value       = aws_sns_topic.remediation_alerts.arn
}

output "cloudwatch_alarms" {
  description = "List of CloudWatch alarm names"
  value = [
    aws_cloudwatch_metric_alarm.ndcg_low.alarm_name,
    aws_cloudwatch_metric_alarm.recall_low.alarm_name,
    aws_cloudwatch_metric_alarm.faithfulness_low.alarm_name
  ]
}
