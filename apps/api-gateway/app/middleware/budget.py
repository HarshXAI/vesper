"""
Cost Governor / Budget Middleware for VESPER API Gateway.

Implements per-tenant budget enforcement with:
- Budget tracking and utilization monitoring
- Model routing restrictions based on budget state
- Automatic fallback to cheaper models when budget is tight
- Metrics for cost visibility

Budget States:
- NORMAL: < 80% utilized - all models available
- WARNING: 80-90% utilized - expensive models restricted
- CRITICAL: > 90% utilized - only cheap models allowed
- EXHAUSTED: 100% utilized - requests may be rejected
"""

import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
import asyncio
import structlog

from app.core.config import settings, TenantBudgetConfig
from app.core.metrics import (
    MetricsCollector,
    cost_budget_total,
    cost_budget_used,
    cost_budget_remaining,
    cost_budget_utilization,
    router_fallback_total,
)

logger = structlog.get_logger(__name__)


class BudgetState(str, Enum):
    """Budget utilization state."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


@dataclass
class TenantBudget:
    """Per-tenant budget tracking."""
    tenant_id: str
    monthly_budget_usd: float
    spent_usd: float = 0.0
    last_reset: datetime = field(default_factory=lambda: datetime.now(datetime.UTC))
    last_updated: datetime = field(default_factory=lambda: datetime.now(datetime.UTC))
    
    @property
    def remaining_usd(self) -> float:
        return max(0, self.monthly_budget_usd - self.spent_usd)
    
    @property
    def utilization(self) -> float:
        if self.monthly_budget_usd <= 0:
            return 0.0
        return min(1.0, self.spent_usd / self.monthly_budget_usd)
    
    @property
    def state(self) -> BudgetState:
        config = settings.default_tenant_budget
        if self.utilization >= 1.0:
            return BudgetState.EXHAUSTED
        elif self.utilization >= config.critical_threshold:
            return BudgetState.CRITICAL
        elif self.utilization >= config.warning_threshold:
            return BudgetState.WARNING
        return BudgetState.NORMAL
    
    def should_reset(self) -> bool:
        """Check if budget should be reset for new month."""
        now = datetime.now(datetime.UTC)
        return (now.year, now.month) != (self.last_reset.year, self.last_reset.month)
    
    def reset(self):
        """Reset budget for new month."""
        self.spent_usd = 0.0
        self.last_reset = datetime.now(datetime.UTC)
        self.last_updated = datetime.now(datetime.UTC)
    
    def add_cost(self, cost_usd: float):
        """Add cost to budget."""
        self.spent_usd += cost_usd
        self.last_updated = datetime.now(datetime.UTC)


@dataclass
class BudgetCheckResult:
    """Result of budget check."""
    allowed: bool
    state: BudgetState
    utilization: float
    remaining_usd: float
    allowed_models: List[str]
    original_model: Optional[str] = None
    recommended_model: Optional[str] = None
    message: Optional[str] = None


class CostGovernor:
    """
    Cost governor for per-tenant budget enforcement.
    
    Tracks spending per tenant and enforces model restrictions
    based on budget utilization.
    """
    
    def __init__(self):
        self.enabled = settings.cost_governor.enabled
        self.budgets: Dict[str, TenantBudget] = {}
        self.model_costs = settings.cost_governor.model_costs
        self.default_budget = settings.cost_governor.default_budget_usd
        self._lock = asyncio.Lock()
        
        logger.info(
            "cost_governor_initialized",
            enabled=self.enabled,
            default_budget=self.default_budget
        )
    
    async def get_or_create_budget(self, tenant_id: str) -> TenantBudget:
        """Get or create budget for tenant."""
        async with self._lock:
            if tenant_id not in self.budgets:
                self.budgets[tenant_id] = TenantBudget(
                    tenant_id=tenant_id,
                    monthly_budget_usd=self.default_budget
                )
            
            budget = self.budgets[tenant_id]
            
            # Check for monthly reset
            if budget.should_reset():
                logger.info("budget_reset", tenant_id=tenant_id)
                budget.reset()
            
            return budget
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost for a model invocation.
        
        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
        
        Returns:
            Cost in USD
        """
        if model not in self.model_costs:
            logger.warning("unknown_model_cost", model=model)
            return 0.0
        
        costs = self.model_costs[model]
        input_cost = (input_tokens / 1000) * costs.get("input", 0)
        output_cost = (output_tokens / 1000) * costs.get("output", 0)
        
        return input_cost + output_cost
    
    async def check_budget(
        self,
        tenant_id: str,
        requested_model: str
    ) -> BudgetCheckResult:
        """
        Check if request is allowed under budget constraints.
        
        Args:
            tenant_id: Tenant identifier
            requested_model: Requested model name
        
        Returns:
            BudgetCheckResult with allowed status and recommendations
        """
        if not self.enabled:
            return BudgetCheckResult(
                allowed=True,
                state=BudgetState.NORMAL,
                utilization=0.0,
                remaining_usd=float('inf'),
                allowed_models=list(self.model_costs.keys()),
                message="Cost governor disabled"
            )
        
        budget = await self.get_or_create_budget(tenant_id)
        config = settings.default_tenant_budget
        
        # Determine allowed models based on state
        if budget.state == BudgetState.NORMAL:
            allowed_models = config.allowed_models_normal
        elif budget.state == BudgetState.WARNING:
            allowed_models = config.allowed_models_warning
        elif budget.state == BudgetState.CRITICAL:
            allowed_models = config.allowed_models_critical
        else:  # EXHAUSTED
            allowed_models = []
        
        # Check if requested model is allowed
        model_allowed = requested_model in allowed_models
        
        # Find recommended model if current not allowed
        recommended_model = None
        if not model_allowed and allowed_models:
            # Recommend cheapest allowed model
            recommended_model = self._get_cheapest_model(allowed_models)
        
        # Update metrics
        MetricsCollector.update_budget(
            tenant=tenant_id,
            budget_total=budget.monthly_budget_usd,
            budget_used=budget.spent_usd
        )
        
        # Log budget state changes
        if budget.state != BudgetState.NORMAL:
            logger.warning(
                "budget_constraint",
                tenant_id=tenant_id,
                state=budget.state.value,
                utilization=budget.utilization,
                requested_model=requested_model,
                model_allowed=model_allowed
            )
        
        return BudgetCheckResult(
            allowed=model_allowed or bool(recommended_model),
            state=budget.state,
            utilization=budget.utilization,
            remaining_usd=budget.remaining_usd,
            allowed_models=allowed_models,
            original_model=requested_model if not model_allowed else None,
            recommended_model=recommended_model,
            message=self._get_budget_message(budget.state, model_allowed, recommended_model)
        )
    
    def _get_cheapest_model(self, models: List[str]) -> Optional[str]:
        """Get the cheapest model from a list."""
        cheapest = None
        cheapest_cost = float('inf')
        
        for model in models:
            if model in self.model_costs:
                # Use output cost as proxy for total cost
                cost = self.model_costs[model].get("output", float('inf'))
                if cost < cheapest_cost:
                    cheapest_cost = cost
                    cheapest = model
        
        return cheapest
    
    def _get_budget_message(
        self,
        state: BudgetState,
        model_allowed: bool,
        recommended_model: Optional[str]
    ) -> str:
        """Generate human-readable budget message."""
        if state == BudgetState.NORMAL:
            return "Budget healthy"
        elif state == BudgetState.WARNING:
            if model_allowed:
                return "Budget at warning level - expensive models restricted"
            return f"Model not available at current budget level. Use: {recommended_model}"
        elif state == BudgetState.CRITICAL:
            if model_allowed:
                return "Budget critical - only essential models available"
            return f"Budget critical. Please use: {recommended_model}"
        else:
            return "Budget exhausted - requests restricted"
    
    async def record_cost(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "completion"
    ) -> float:
        """
        Record cost for a completed request.
        
        Args:
            tenant_id: Tenant identifier
            model: Model used
            input_tokens: Input tokens consumed
            output_tokens: Output tokens generated
            operation: Type of operation
        
        Returns:
            Cost in USD
        """
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        if cost > 0:
            budget = await self.get_or_create_budget(tenant_id)
            budget.add_cost(cost)
            
            # Record metrics
            MetricsCollector.record_cost(
                model=model,
                tenant=tenant_id,
                cost_usd=cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation=operation
            )
            
            logger.debug(
                "cost_recorded",
                tenant_id=tenant_id,
                model=model,
                cost_usd=cost,
                total_spent=budget.spent_usd,
                utilization=budget.utilization
            )
        
        return cost
    
    async def apply_model_fallback(
        self,
        tenant_id: str,
        requested_model: str
    ) -> Tuple[str, bool]:
        """
        Apply model fallback if budget constraints require it.
        
        Args:
            tenant_id: Tenant identifier
            requested_model: Originally requested model
        
        Returns:
            Tuple of (actual_model, was_fallback_applied)
        """
        check = await self.check_budget(tenant_id, requested_model)
        
        if requested_model in check.allowed_models:
            return requested_model, False
        
        if check.recommended_model:
            # Record fallback
            router_fallback_total.labels(
                from_model=requested_model,
                to_model=check.recommended_model,
                reason=f"budget_{check.state.value}"
            ).inc()
            
            logger.info(
                "model_fallback_applied",
                tenant_id=tenant_id,
                from_model=requested_model,
                to_model=check.recommended_model,
                reason=check.state.value
            )
            
            return check.recommended_model, True
        
        # No fallback available
        raise BudgetExhaustedException(
            f"Budget exhausted for tenant {tenant_id}. No models available."
        )


class BudgetExhaustedException(Exception):
    """Exception raised when budget is exhausted."""
    pass


# Global cost governor instance
cost_governor = CostGovernor()


async def get_cost_governor() -> CostGovernor:
    """Get the global cost governor instance."""
    return cost_governor
