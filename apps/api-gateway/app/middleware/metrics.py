"""
Metrics middleware for tracking all API requests.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import MetricsCollector


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track metrics for all HTTP requests.
    
    Records:
    - Total requests
    - Request latency
    - Status codes
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and record metrics."""
        # Skip metrics endpoint to avoid circular recording
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            latency = time.time() - start_time
            
            # Record metrics
            MetricsCollector.record_request(
                route=request.url.path,
                method=request.method,
                status_code=response.status_code,
                latency_seconds=latency
            )
            
            return response
            
        except Exception as e:
            latency = time.time() - start_time
            
            # Record error metrics
            MetricsCollector.record_request(
                route=request.url.path,
                method=request.method,
                status_code=500,
                latency_seconds=latency
            )
            
            raise e
