"""
Cache Warmers for Vesper API Gateway
=====================================

Proactive cache warming to reduce cold-start latencies and ensure
consistent response times for common queries.

This module provides:
- Embedding cache warming for frequently accessed documents
- Query result caching for common question patterns
- Background warming on startup and scheduled intervals
"""

import asyncio
import hashlib
import logging
from datetime import datetime, UTC, timedelta
from typing import Any, Callable, Optional

import httpx
from pydantic import BaseModel

from app.core.config import Settings

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class CacheWarmerConfig(BaseModel):
    """Configuration for cache warming."""
    
    enabled: bool = True
    warmup_on_startup: bool = True
    warmup_interval_minutes: int = 30
    batch_size: int = 10
    concurrent_requests: int = 5
    timeout_seconds: float = 30.0
    
    # Query patterns to warm
    common_query_patterns: list[str] = [
        "What is the revenue for {company}?",
        "What was the operating income for {company}?",
        "What are the risk factors for {company}?",
        "How did {company} perform in Q{quarter} {year}?",
        "What is {company}'s guidance for next quarter?",
        "What are the key metrics for {company}?",
    ]
    
    # Companies to warm queries for
    target_companies: list[str] = [
        "Apple", "Microsoft", "Google", "Amazon", "Meta",
        "Tesla", "Nvidia", "Netflix", "Adobe", "Salesforce",
    ]
    
    # Common document types to pre-fetch
    document_types: list[str] = ["10-K", "10-Q", "8-K"]


# =============================================================================
# Cache Key Generator
# =============================================================================

def generate_cache_key(query: str, tenant_id: str = "default") -> str:
    """Generate a consistent cache key for a query."""
    normalized = query.lower().strip()
    content = f"{tenant_id}:{normalized}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


# =============================================================================
# Warmer Result Tracking
# =============================================================================

class WarmingResult(BaseModel):
    """Result of a cache warming operation."""
    
    query: str
    cache_key: str
    success: bool
    latency_ms: float
    cached: bool = False
    error: Optional[str] = None
    timestamp: datetime = datetime.now(UTC)


class WarmingStats(BaseModel):
    """Statistics for a warming batch."""
    
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_queries: int = 0
    successful: int = 0
    failed: int = 0
    already_cached: int = 0
    total_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_queries == 0:
            return 0.0
        return (self.successful / self.total_queries) * 100
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.successful == 0:
            return 0.0
        return self.total_latency_ms / self.successful


# =============================================================================
# Cache Warmer Implementation
# =============================================================================

class CacheWarmer:
    """
    Proactive cache warming for the Vesper API.
    
    Warms caches by pre-executing common query patterns to ensure
    embeddings and results are cached before user requests.
    """
    
    def __init__(
        self,
        settings: Settings,
        config: Optional[CacheWarmerConfig] = None,
    ):
        self.settings = settings
        self.config = config or CacheWarmerConfig()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_warmup: Optional[datetime] = None
        self._stats_history: list[WarmingStats] = []
        
        # API client for warming requests
        self._client: Optional[httpx.AsyncClient] = None
    
    async def start(self) -> None:
        """Start the cache warmer background task."""
        if not self.config.enabled:
            logger.info("Cache warmer is disabled")
            return
        
        if self._running:
            logger.warning("Cache warmer already running")
            return
        
        self._running = True
        self._client = httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"Content-Type": "application/json"},
        )
        
        logger.info("Starting cache warmer")
        
        # Warm on startup if configured
        if self.config.warmup_on_startup:
            await self._run_warmup()
        
        # Start background task
        self._task = asyncio.create_task(self._background_loop())
    
    async def stop(self) -> None:
        """Stop the cache warmer."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.aclose()
        
        logger.info("Cache warmer stopped")
    
    async def _background_loop(self) -> None:
        """Background loop for periodic warming."""
        interval = self.config.warmup_interval_minutes * 60
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._running:
                    await self._run_warmup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache warmer loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _run_warmup(self) -> WarmingStats:
        """Execute a full warming cycle."""
        stats = WarmingStats(
            started_at=datetime.now(UTC),
            total_queries=0,
        )
        
        logger.info("Starting cache warming cycle")
        
        # Generate queries to warm
        queries = self._generate_warmup_queries()
        stats.total_queries = len(queries)
        
        # Process in batches
        for i in range(0, len(queries), self.config.batch_size):
            batch = queries[i:i + self.config.batch_size]
            results = await self._warm_batch(batch)
            
            for result in results:
                if result.success:
                    stats.successful += 1
                    stats.total_latency_ms += result.latency_ms
                    if result.cached:
                        stats.already_cached += 1
                else:
                    stats.failed += 1
        
        stats.completed_at = datetime.now(UTC)
        self._last_warmup = stats.completed_at
        self._stats_history.append(stats)
        
        # Keep only last 24 hours of history
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        self._stats_history = [
            s for s in self._stats_history
            if s.started_at > cutoff
        ]
        
        logger.info(
            f"Cache warming complete: {stats.successful}/{stats.total_queries} "
            f"({stats.success_rate:.1f}%), avg latency: {stats.avg_latency_ms:.0f}ms"
        )
        
        return stats
    
    def _generate_warmup_queries(self) -> list[str]:
        """Generate the list of queries to warm."""
        queries = []
        
        for pattern in self.config.common_query_patterns:
            for company in self.config.target_companies:
                # Generate variations
                if "{company}" in pattern:
                    query = pattern.replace("{company}", company)
                    
                    # Add quarter/year variations if needed
                    if "{quarter}" in query or "{year}" in query:
                        for quarter in [1, 2, 3, 4]:
                            for year in [2023, 2024]:
                                q = query.replace("{quarter}", str(quarter))
                                q = q.replace("{year}", str(year))
                                queries.append(q)
                    else:
                        queries.append(query)
        
        return queries[:100]  # Limit to 100 queries per warming cycle
    
    async def _warm_batch(self, queries: list[str]) -> list[WarmingResult]:
        """Warm a batch of queries concurrently."""
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)
        
        async def warm_with_limit(query: str) -> WarmingResult:
            async with semaphore:
                return await self._warm_query(query)
        
        tasks = [warm_with_limit(q) for q in queries]
        return await asyncio.gather(*tasks)
    
    async def _warm_query(self, query: str) -> WarmingResult:
        """Execute a single warming request."""
        cache_key = generate_cache_key(query)
        start_time = datetime.now(UTC)
        
        try:
            base_url = f"http://localhost:{self.settings.port}"
            
            response = await self._client.post(
                f"{base_url}/v1/chat",
                json={
                    "query": query,
                    "stream": False,
                    "tenant_id": "cache-warmer",
                    "cache_warmup": True,
                },
            )
            
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                data = response.json()
                cached = data.get("cached", False)
                
                return WarmingResult(
                    query=query,
                    cache_key=cache_key,
                    success=True,
                    latency_ms=latency_ms,
                    cached=cached,
                )
            else:
                return WarmingResult(
                    query=query,
                    cache_key=cache_key,
                    success=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}",
                )
                
        except Exception as e:
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return WarmingResult(
                query=query,
                cache_key=cache_key,
                success=False,
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def get_stats(self) -> dict:
        """Get current warming statistics."""
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "last_warmup": self._last_warmup.isoformat() if self._last_warmup else None,
            "warmup_interval_minutes": self.config.warmup_interval_minutes,
            "recent_runs": [
                {
                    "started_at": s.started_at.isoformat(),
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "total_queries": s.total_queries,
                    "successful": s.successful,
                    "failed": s.failed,
                    "already_cached": s.already_cached,
                    "success_rate": s.success_rate,
                    "avg_latency_ms": s.avg_latency_ms,
                }
                for s in self._stats_history[-10:]
            ],
        }
    
    async def warm_now(self) -> WarmingStats:
        """Trigger immediate cache warming."""
        return await self._run_warmup()


# =============================================================================
# Embedding Warmer
# =============================================================================

class EmbeddingWarmer:
    """
    Pre-compute and cache embeddings for frequently accessed documents.
    """
    
    def __init__(
        self,
        settings: Settings,
        embedding_fn: Callable[[str], list[float]],
    ):
        self.settings = settings
        self.embedding_fn = embedding_fn
        self._cache: dict[str, list[float]] = {}
    
    async def warm_document_embeddings(
        self,
        document_ids: list[str],
        batch_size: int = 100,
    ) -> dict[str, bool]:
        """Pre-compute embeddings for a list of documents."""
        results = {}
        
        for i in range(0, len(document_ids), batch_size):
            batch = document_ids[i:i + batch_size]
            
            for doc_id in batch:
                try:
                    # This would fetch and embed the document
                    # Implementation depends on document storage
                    results[doc_id] = True
                except Exception as e:
                    logger.error(f"Failed to warm embedding for {doc_id}: {e}")
                    results[doc_id] = False
        
        return results
    
    def get_cached_embedding(self, text: str) -> Optional[list[float]]:
        """Get a cached embedding if available."""
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        return self._cache.get(cache_key)


# =============================================================================
# Factory Function
# =============================================================================

def create_cache_warmer(settings: Settings) -> CacheWarmer:
    """Factory function to create a cache warmer instance."""
    config = CacheWarmerConfig(
        enabled=getattr(settings, "cache_warmers_enabled", True),
        warmup_on_startup=getattr(settings, "warmup_on_startup", True),
        warmup_interval_minutes=getattr(settings, "warmup_interval", 30),
    )
    
    return CacheWarmer(settings=settings, config=config)
