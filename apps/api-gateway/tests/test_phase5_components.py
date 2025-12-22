"""
Phase 5 Component Tests
========================

Tests for validating Phase 5 monitoring components work correctly.

Run with:
    cd apps/api-gateway
    pytest tests/test_phase5_components.py -v
"""

import pytest
import sys
import os

# Get absolute paths - more reliably find vesper root
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
API_GATEWAY_DIR = os.path.dirname(TEST_DIR)
APPS_DIR = os.path.dirname(API_GATEWAY_DIR)
VESPER_ROOT = os.path.dirname(APPS_DIR)

# Add app to path
sys.path.insert(0, API_GATEWAY_DIR)


def get_vesper_path(*parts):
    """Get path relative to vesper root."""
    return os.path.join(VESPER_ROOT, *parts)


class TestMetricsModule:
    """Test Prometheus metrics module."""

    def test_metrics_import(self):
        """Test that metrics module imports without errors."""
        from app.core.metrics import (
            api_requests_total,
            api_latency_seconds,
            retrieval_requests_total,
            retrieval_latency_ms,
            rerank_latency_ms,
            router_route_total,
            guardrails_checks_total,
            tokens_input_total,
            cost_usd_total,
            MetricsCollector,
        )
        assert api_requests_total is not None
        assert MetricsCollector is not None

    def test_metrics_collector_record_request(self):
        """Test MetricsCollector.record_request()."""
        from app.core.metrics import MetricsCollector
        
        # Should not raise - uses latency_seconds not latency
        MetricsCollector.record_request(
            route="/v1/ask",
            method="POST",
            status_code=200,
            latency_seconds=0.5
        )

    def test_metrics_collector_record_retrieval(self):
        """Test MetricsCollector.record_retrieval()."""
        from app.core.metrics import MetricsCollector
        
        MetricsCollector.record_retrieval(
            tenant="test-tenant",
            search_type="hybrid",
            latency_ms=100.0,
            docs_returned=10
        )

    def test_metrics_collector_record_cost(self):
        """Test MetricsCollector.record_cost()."""
        from app.core.metrics import MetricsCollector
        
        MetricsCollector.record_cost(
            model="gpt-4",
            tenant="test-tenant",
            cost_usd=0.05,
            input_tokens=100,
            output_tokens=50
        )

    def test_get_metrics_output(self):
        """Test that get_metrics() returns valid Prometheus format."""
        from app.core.metrics import get_metrics
        
        output = get_metrics()
        assert isinstance(output, bytes)
        # Should contain at least service info
        assert b"vesper_api_gateway_info" in output


class TestTracingModule:
    """Test OpenTelemetry tracing module."""

    def test_tracing_import(self):
        """Test that tracing module imports without errors."""
        from app.core.tracing import (
            get_trace_headers,
            get_current_trace_id,
            add_span_attributes,
        )
        assert get_trace_headers is not None

    def test_get_trace_headers(self):
        """Test get_trace_headers returns a dict."""
        from app.core.tracing import get_trace_headers
        
        headers = get_trace_headers()
        assert isinstance(headers, dict)

    def test_get_current_trace_id(self):
        """Test get_current_trace_id returns valid ID."""
        from app.core.tracing import get_current_trace_id
        
        trace_id = get_current_trace_id()
        # May be "0" * 32 if no active span
        assert isinstance(trace_id, str)
        assert len(trace_id) == 32


class TestConfigModule:
    """Test configuration module."""

    def test_config_import(self):
        """Test that config imports without errors."""
        from app.core.config import settings, TenantBudgetConfig, CostGovernorConfig
        
        assert settings is not None
        assert TenantBudgetConfig is not None
        assert CostGovernorConfig is not None

    def test_settings_has_required_fields(self):
        """Test settings has all required fields."""
        from app.core.config import settings
        
        assert hasattr(settings, "api_title")
        assert hasattr(settings, "api_version")
        assert hasattr(settings, "database_url")
        assert hasattr(settings, "redis_url")

    def test_tenant_budget_config_defaults(self):
        """Test TenantBudgetConfig has sensible defaults."""
        from app.core.config import TenantBudgetConfig
        
        config = TenantBudgetConfig()
        assert config.warning_threshold > 0
        assert config.critical_threshold > config.warning_threshold
        assert config.monthly_budget_usd > 0

    def test_cost_governor_config_model_costs(self):
        """Test CostGovernorConfig has model costs."""
        from app.core.config import CostGovernorConfig
        
        config = CostGovernorConfig()
        assert "gpt-4o" in config.model_costs
        assert "gpt-3.5-turbo" in config.model_costs


class TestBudgetMiddleware:
    """Test budget/cost governor middleware."""

    def test_budget_module_import(self):
        """Test that budget module imports without errors."""
        from app.middleware.budget import (
            BudgetState,
            TenantBudget,
            BudgetCheckResult,
            CostGovernor,
        )
        assert BudgetState is not None
        assert CostGovernor is not None

    def test_budget_state_enum(self):
        """Test BudgetState enum values."""
        from app.middleware.budget import BudgetState
        
        assert BudgetState.NORMAL.value == "normal"
        assert BudgetState.WARNING.value == "warning"
        assert BudgetState.CRITICAL.value == "critical"
        assert BudgetState.EXHAUSTED.value == "exhausted"

    def test_tenant_budget_utilization(self):
        """Test TenantBudget utilization calculation."""
        from app.middleware.budget import TenantBudget
        
        budget = TenantBudget(
            tenant_id="test",
            monthly_budget_usd=100.0,
            spent_usd=50.0
        )
        assert budget.utilization == 0.5
        assert budget.remaining_usd == 50.0

    def test_tenant_budget_state_normal(self):
        """Test TenantBudget state detection - normal."""
        from app.middleware.budget import TenantBudget, BudgetState
        
        budget = TenantBudget(
            tenant_id="test",
            monthly_budget_usd=100.0,
            spent_usd=50.0  # 50% - should be NORMAL
        )
        assert budget.state == BudgetState.NORMAL

    def test_tenant_budget_state_warning(self):
        """Test TenantBudget state detection - warning."""
        from app.middleware.budget import TenantBudget, BudgetState
        
        budget = TenantBudget(
            tenant_id="test",
            monthly_budget_usd=100.0,
            spent_usd=85.0  # 85% - should be WARNING
        )
        assert budget.state == BudgetState.WARNING

    def test_tenant_budget_state_critical(self):
        """Test TenantBudget state detection - critical."""
        from app.middleware.budget import TenantBudget, BudgetState
        
        budget = TenantBudget(
            tenant_id="test",
            monthly_budget_usd=100.0,
            spent_usd=95.0  # 95% - should be CRITICAL
        )
        assert budget.state == BudgetState.CRITICAL

    def test_tenant_budget_add_cost(self):
        """Test TenantBudget.add_cost()."""
        from app.middleware.budget import TenantBudget
        
        budget = TenantBudget(
            tenant_id="test",
            monthly_budget_usd=100.0,
            spent_usd=0.0
        )
        budget.add_cost(25.0)
        assert budget.spent_usd == 25.0
        budget.add_cost(10.0)
        assert budget.spent_usd == 35.0


class TestEvaluatorRunner:
    """Test evaluation runner module."""

    @pytest.fixture
    def evaluator_path(self):
        return get_vesper_path("services", "evaluator")

    def test_runner_import(self, evaluator_path):
        """Test that runner module imports without errors."""
        sys.path.insert(0, evaluator_path)
        
        from runner import (
            EvalConfig,
            EvalQuery,
            RetrievalResult,
            GenerationResult,
            EvalReport,
        )
        assert EvalConfig is not None
        assert EvalQuery is not None

    def test_eval_config_defaults(self, evaluator_path):
        """Test EvalConfig has sensible defaults."""
        sys.path.insert(0, evaluator_path)
        
        from runner import EvalConfig
        
        config = EvalConfig()
        assert config.ndcg10_threshold > 0
        assert config.recall5_threshold > 0
        assert config.mrr_threshold > 0

    def test_eval_query_dataclass(self, evaluator_path):
        """Test EvalQuery dataclass."""
        sys.path.insert(0, evaluator_path)
        
        from runner import EvalQuery
        
        query = EvalQuery(
            id="q1",
            query="What is Apple's revenue?",
            expected_doc_ids=["doc1", "doc2"],
            category="factual"
        )
        assert query.id == "q1"
        assert len(query.expected_doc_ids) == 2


class TestQueriesJsonl:
    """Test evaluation queries file."""

    @pytest.fixture
    def queries_path(self):
        return get_vesper_path("data", "eval", "queries.jsonl")

    def test_queries_file_exists(self, queries_path):
        """Test that queries.jsonl exists."""
        assert os.path.exists(queries_path), f"queries.jsonl not found at {queries_path}"

    def test_queries_file_valid_jsonl(self, queries_path):
        """Test that queries.jsonl contains valid JSONL."""
        import json
        
        queries = []
        with open(queries_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        query = json.loads(line)
                        queries.append(query)
                    except json.JSONDecodeError as e:
                        pytest.fail(f"Invalid JSON at line {line_num}: {e}")
        
        assert len(queries) > 0, "queries.jsonl is empty"

    def test_queries_have_required_fields(self, queries_path):
        """Test that each query has required fields."""
        import json
        
        with open(queries_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    query = json.loads(line)
                    assert "id" in query, f"Missing 'id' at line {line_num}"
                    assert "query" in query, f"Missing 'query' at line {line_num}"
                    assert "category" in query, f"Missing 'category' at line {line_num}"


class TestPrometheusAlerts:
    """Test Prometheus alerts configuration."""

    @pytest.fixture
    def alerts_path(self):
        return get_vesper_path("monitoring", "prometheus", "alerts", "vesper-alerts.yml")

    def test_alerts_file_exists(self, alerts_path):
        """Test that vesper-alerts.yml exists."""
        assert os.path.exists(alerts_path), f"vesper-alerts.yml not found at {alerts_path}"

    def test_alerts_valid_yaml(self, alerts_path):
        """Test that vesper-alerts.yml is valid YAML."""
        import yaml
        
        with open(alerts_path, "r") as f:
            try:
                alerts = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML: {e}")
        
        assert "groups" in alerts, "Missing 'groups' key in alerts"
        assert len(alerts["groups"]) > 0, "No alert groups defined"


class TestGrafanaDashboards:
    """Test Grafana dashboard JSON files."""

    @pytest.fixture
    def dashboards_dir(self):
        return get_vesper_path("monitoring", "grafana", "dashboards")

    def test_api_overview_dashboard_exists(self, dashboards_dir):
        """Test that vesper-api-overview.json exists."""
        path = os.path.join(dashboards_dir, "vesper-api-overview.json")
        assert os.path.exists(path), f"Dashboard not found at {path}"

    def test_retrieval_quality_dashboard_exists(self, dashboards_dir):
        """Test that vesper-retrieval-quality.json exists."""
        path = os.path.join(dashboards_dir, "vesper-retrieval-quality.json")
        assert os.path.exists(path), f"Dashboard not found at {path}"

    def test_costs_dashboard_exists(self, dashboards_dir):
        """Test that vesper-costs.json exists."""
        path = os.path.join(dashboards_dir, "vesper-costs.json")
        assert os.path.exists(path), f"Dashboard not found at {path}"

    def test_airflow_sla_dashboard_exists(self, dashboards_dir):
        """Test that vesper-airflow-sla.json exists."""
        path = os.path.join(dashboards_dir, "vesper-airflow-sla.json")
        assert os.path.exists(path), f"Dashboard not found at {path}"

    def test_dashboards_valid_json(self, dashboards_dir):
        """Test that all dashboards are valid JSON."""
        import json
        
        dashboards = [
            "vesper-api-overview.json",
            "vesper-retrieval-quality.json",
            "vesper-costs.json",
            "vesper-airflow-sla.json",
        ]
        
        for dashboard in dashboards:
            path = os.path.join(dashboards_dir, dashboard)
            if os.path.exists(path):
                with open(path, "r") as f:
                    try:
                        data = json.load(f)
                        assert "title" in data or "dashboard" in data, \
                            f"Missing title in {dashboard}"
                    except json.JSONDecodeError as e:
                        pytest.fail(f"Invalid JSON in {dashboard}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
