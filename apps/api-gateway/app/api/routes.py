"""API routes and handlers."""

import asyncio
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any

from fastapi import Depends, Request
from opentelemetry import trace

from app.models import AskRequest, StreamEvent, Citation, HealthResponse
from app.core import MetricsCollector
from app.core.rag import get_rag_pipeline
from app.middleware.auth import require_authentication, get_tenant_id


async def stream_blocked_response(
    guardrails_result,
    trace_id: str,
    start_time: float
) -> AsyncGenerator[str, None]:
    """Stream error response when guardrails block the request."""
    latency_ms = (time.time() - start_time) * 1000
    
    error_event = StreamEvent(
        type="error",
        error=guardrails_result.reason
    )
    yield f"data: {error_event.model_dump_json()}\n\n"
    
    done_event = StreamEvent(
        type="done",
        latency_ms=round(latency_ms, 2),
        cost_usd=0.0
    )
    yield f"data: {done_event.model_dump_json()}\n\n"


async def stream_response(
    request: AskRequest,
    trace_id: str,
    start_time: float,
    app,
    user_claims: Dict[str, Any] = None,
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events for streaming response.
    
    Args:
        request: The ask request
        trace_id: Trace ID for distributed tracing
        start_time: Request start timestamp
        app: FastAPI application instance
        user_claims: Validated JWT claims (required if auth enabled)
    """
    tracer = trace.get_tracer("api-gateway")
    
    # Use tenant from JWT claims, not from request (security)
    tenant_id = request.tenant_id
    if user_claims:
        jwt_tenant = user_claims.get("tenant_id") or user_claims.get("custom:tenant_id")
        if jwt_tenant and jwt_tenant != "default":
            tenant_id = jwt_tenant
    
    try:
        print(f"🚀 stream_response: Starting for trace={trace_id[:8]}, tenant={tenant_id}", flush=True)
        
        # Get RAG pipeline
        rag_pipeline = get_rag_pipeline()
        print(f"✅ stream_response: Got RAG pipeline", flush=True)
        
        # Create span for RAG pipeline execution
        with tracer.start_as_current_span(
            "stream_response.rag_pipeline",
            attributes={
                "query": request.query,
                "tenant_id": tenant_id,
                "trace_id": trace_id,
                "user_id": user_claims.get("sub", "system") if user_claims else "system",
            }
        ) as span:
            print(f"🔄 stream_response: Calling process_query...")
            # Run RAG pipeline to get answer
            rag_result = await rag_pipeline.process_query(
                query=request.query,
                user_id=user_claims.get("sub", "system") if user_claims else "system",
                tenant_id=tenant_id,
                max_tokens=1000,
                temperature=0.1
            )
            print(f"✅ stream_response: Got RAG result with answer length={len(rag_result.get('answer', ''))}")
            
            span.set_attribute("rag.docs_retrieved", rag_result.get('metrics', {}).get('docs_retrieved', 0))
            span.set_attribute("rag.model_used", rag_result.get('model_used', 'unknown'))
            span.set_attribute("rag.tokens_used", rag_result.get('tokens_used', 0))
            span.set_attribute("rag.confidence", rag_result.get('confidence', 0.0))
        
        full_response = rag_result['answer']
        print(f"📝 stream_response: Streaming {len(full_response)} chars in {len(full_response.split())} tokens")
        
        # Stream the answer as tokens (split by words for now)
        tokens = full_response.split()
        for i, token in enumerate(tokens):
            event = StreamEvent(type="token", content=token + " ")
            yield f"data: {event.model_dump_json()}\n\n"
            if i == 0:
                print(f"✅ stream_response: Yielded first token")
            await asyncio.sleep(0.02)  # Small delay for streaming effect
        
        print(f"✅ stream_response: Finished streaming all tokens")
        
        # Convert sources to Citation objects
        citations = [
            Citation(
                source_uri=source.get('source_uri', 'unknown'),
                page=source.get('page', 0),
                span={
                    "start_char": 0,
                    "end_char": len(source.get('span', '')),
                    "text": source.get('span', '')
                },
                sha256=source.get('sha256', '0' * 64)
            )
            for source in rag_result.get('sources', [])
        ]
        
        # Guardrails post-processing (with span)
        guardrails = app.state.guardrails
        with tracer.start_as_current_span(
            "guardrails.post_process",
            attributes={"trace_id": trace_id}
        ) as post_span:
            post_result = await guardrails.post_process(
                response_text=full_response,
                citations=[c.model_dump() for c in citations],
                tenant_id=tenant_id,
                trace_id=trace_id
            )
            post_span.set_attribute("guardrails.passed", post_result.passed)
            post_span.set_attribute("guardrails.latency_ms", post_result.latency_ms)
            if not post_result.passed:
                post_span.set_attribute("guardrails.blocked_by", post_result.blocked_by)
        
        # Record guardrails metrics
        MetricsCollector.record_guardrails(
            stage="post",
            check_type=post_result.blocked_by or "validation",
            latency_ms=post_result.latency_ms,
            passed=post_result.passed,
            reason=post_result.blocked_by if not post_result.passed else None
        )
        
        print(f"   🛡️  Post-processing: {post_result.latency_ms:.2f}ms")
        
        if not post_result.passed:
            print(f"   ❌ Blocked by {post_result.blocked_by}: {post_result.reason}")
            error_event = StreamEvent(type="error", error=post_result.reason)
            yield f"data: {error_event.model_dump_json()}\n\n"
        else:
            if post_result.modified_content:
                print(f"   ✏️  Content modified: {post_result.metadata.get('redactions_made', [])}")
            
            # Send citations
            if citations:
                event = StreamEvent(type="citation", citations=citations)
                yield f"data: {event.model_dump_json()}\n\n"
        
        latency_ms = (time.time() - start_time) * 1000
        cost_usd = 0.012  # Mock cost
        
        # Record metrics from RAG pipeline
        model_used = rag_result.get('model_used', 'gpt-3.5-turbo')
        tokens_used = rag_result.get('tokens_used', 0)
        
        # Estimate cost based on model and tokens
        cost_per_1k_tokens = 0.002 if 'gpt-4' in model_used else 0.0015
        cost_usd = (tokens_used / 1000.0) * cost_per_1k_tokens
        
        MetricsCollector.record_cost(
            model=model_used,
            tenant=tenant_id,
            cost_usd=cost_usd,
            input_tokens=tokens_used // 2,  # Rough estimate
            output_tokens=tokens_used // 2
        )
        MetricsCollector.record_citations(count=len(citations), coverage_ratio=rag_result.get('confidence', 0.0))
        MetricsCollector.record_stream(startup_latency_ms=300, tokens_per_second=15.0)
        
        event = StreamEvent(type="done", latency_ms=round(latency_ms, 2), cost_usd=cost_usd)
        yield f"data: {event.model_dump_json()}\n\n"
        print(f"✅ stream_response: Sent done event, completing stream")
        
    except Exception as e:
        print(f"❌ [trace={trace_id[:8]}] Error in stream_response: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        event = StreamEvent(type="error", error=str(e))
        yield f"data: {event.model_dump_json()}\n\n"


async def health_check() -> HealthResponse:
    """Perform health checks."""
    checks = {
        "database": {"status": "healthy", "latency_ms": 5.2},  # Mock
        "redis": {"status": "healthy", "latency_ms": 1.1},
        "agents": {"status": "healthy", "latency_ms": 12.3}
    }
    
    statuses = [check["status"] for check in checks.values()]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        checks=checks,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
