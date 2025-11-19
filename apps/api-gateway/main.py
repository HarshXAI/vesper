"""
Vesper API Gateway - Main application entry point.

Production API with streaming, guardrails, and observability.
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
import uvicorn

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from app.core import settings, MetricsCollector, get_metrics, get_metrics_content_type
from app.models import AskRequest, StreamEvent, Citation, HealthResponse
from app.middleware import GuardrailsMiddleware
from app.api.routes import stream_response, stream_blocked_response, health_check
from fastapi.responses import Response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print(f"🚀 Starting {settings.api_title}")
    print(f"📍 Version: {settings.api_version}")
    
    # Initialize OpenTelemetry tracing
    resource = Resource.create({"service.name": "api-gateway", "service.version": settings.api_version})
    provider = TracerProvider(resource=resource)
    
    # Add span processor (Console for dev, OTLP for prod)
    if settings.otel_exporter_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # Console exporter for local dev
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    trace.set_tracer_provider(provider)
    app.state.tracer = trace.get_tracer("api-gateway", settings.api_version)
    print(f"🔍 OpenTelemetry tracing enabled (exporter: {settings.otel_exporter_endpoint or 'console'})")
    
    # Initialize guardrails middleware
    guardrails_config = {
        "enabled": settings.guardrails_enabled,
        "pre_checks": ["input_validation", "jailbreak", "policy"],
        "post_checks": ["pii", "moderation", "citation", "policy"]
    }
    app.state.guardrails = GuardrailsMiddleware(guardrails_config)
    
    yield
    
    print("👋 Shutting down API Gateway")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# Automatically instrument FastAPI
FastAPIInstrumentor.instrument_app(app)


@app.post(
    f"/{settings.api_version}/ask",
    response_model=None,
    summary="Ask a question about financial documents",
    description="Submit a query and receive streaming response with citations"
)
async def ask(
    request: AskRequest,
    x_eval: Optional[str] = Header(None, description="Set to 'true' for evaluation mode")
) -> StreamingResponse:
    """Main query endpoint with Server-Sent Events streaming."""
    start_time = time.time()
    trace_id = request.trace_id or str(uuid.uuid4())
    is_eval = x_eval == "true"
    route = f"/{settings.api_version}/ask"
    
    print(f"📬 [trace={trace_id[:8]}] Query: {request.query[:50]}...")
    print(f"   Tenant: {request.tenant_id}, Stream: {request.stream}, Eval: {is_eval}")
    
    # Get tracer and create span
    tracer = app.state.tracer
    current_span = trace.get_current_span()
    current_span.set_attribute("trace_id", trace_id)
    current_span.set_attribute("tenant_id", request.tenant_id)
    current_span.set_attribute("is_eval", is_eval)
    
    # Guardrails pre-processing (with span)
    with tracer.start_as_current_span(
        "guardrails.pre_process",
        attributes={"query": request.query, "trace_id": trace_id}
    ) as pre_span:
        guardrails = app.state.guardrails
        pre_result = await guardrails.pre_process(
            query=request.query,
            tenant_id=request.tenant_id,
            trace_id=trace_id
        )
        pre_span.set_attribute("guardrails.passed", pre_result.passed)
        pre_span.set_attribute("guardrails.latency_ms", pre_result.latency_ms)
        if not pre_result.passed:
            pre_span.set_attribute("guardrails.blocked_by", pre_result.blocked_by)
    
    # Record guardrails metrics
    MetricsCollector.record_guardrails(
        stage="pre",
        latency_ms=pre_result.latency_ms,
        blocked=not pre_result.passed,
        reason=pre_result.blocked_by if not pre_result.passed else None
    )
    
    print(f"   🛡️  Pre-processing: {pre_result.latency_ms:.2f}ms")
    
    if not pre_result.passed:
        print(f"   ❌ Blocked by {pre_result.blocked_by}: {pre_result.reason}")
        # Record request metrics
        latency_seconds = time.time() - start_time
        MetricsCollector.record_request(route, "POST", 400, latency_seconds)
        
        if request.stream:
            return StreamingResponse(
                stream_blocked_response(pre_result, trace_id, start_time),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Trace-ID": trace_id,
                    "X-Guardrails-Blocked": pre_result.blocked_by
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Request blocked by {pre_result.blocked_by}: {pre_result.reason}"
            )
    
    if request.stream:
        print(f"📤 Creating StreamingResponse for trace={trace_id[:8]}", flush=True)
        generator = stream_response(request, trace_id, start_time, app)
        print(f"✅ Got generator: {generator}", flush=True)
        response = StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Trace-ID": trace_id
            }
        )
        print(f"✅ Returning StreamingResponse", flush=True)
        return response
    else:
        raise HTTPException(
            status_code=501,
            detail="Non-streaming mode not yet implemented. Use stream=true."
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check health status of API and dependencies"
)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return await health_check()

@app.get(
    "/v1/debug-stream",
    summary="Debug streaming endpoint",
    description="Minimal SSE stream to isolate framework issues"
)
async def debug_stream():
    async def gen():
        # Emit a few tokens with delays
        for i in range(5):
            yield f"data: {{\"type\": \"token\", \"content\": \"dbg-{i}\"}}\n\n"
            await asyncio.sleep(0.1)
        # Finish
        yield "data: {\"type\": \"done\"}\n\n"
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Export metrics in Prometheus format"
)
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


@app.get(
    "/admin/db-status",
    summary="Database status check",
    description="Check if database tables exist and have data"
)
async def db_status():
    """Check database status - tables and row counts."""
    import json
    import boto3
    import psycopg2
    
    try:
        # Get DB credentials from Secrets Manager
        secret_name = 'vesper-dev-db-credentials'
        region = 'ap-south-1'
        
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        creds = json.loads(response['SecretString'])
        
        # Connect to database
        conn = psycopg2.connect(
            host=creds['host'],
            port=creds['port'],
            user=creds['username'],
            password=creds['password'],
            database=creds['dbname'],
            connect_timeout=5
        )
        
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('document_chunks', 'documents', 'document_metadata')
            ORDER BY table_name;
        """)
        
        tables = {row[0]: 0 for row in cursor.fetchall()}
        
        # Get counts
        for table in tables.keys():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                tables[table] = cursor.fetchone()[0]
            except:
                tables[table] = -1
        
        # Get sample if chunks exist
        samples = []
        if 'document_chunks' in tables and tables['document_chunks'] > 0:
            cursor.execute("""
                SELECT chunk_id, document_id, section_name, 
                       LEFT(content, 100) as content_preview
                FROM document_chunks 
                LIMIT 3;
            """)
            samples = [
                {
                    "chunk_id": row[0][:16] + "...",
                    "document_id": row[1][:16] + "...",
                    "section": row[2],
                    "preview": row[3] + "..."
                }
                for row in cursor.fetchall()
            ]
        
        cursor.close()
        conn.close()
        
        return {
            "status": "connected",
            "database": creds['dbname'],
            "host": creds['host'],
            "tables": tables,
            "samples": samples,
            "has_data": sum(tables.values()) > 0,
            "ready_for_rag": tables.get('document_chunks', 0) > 0
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "has_data": False,
            "ready_for_rag": False
        }


@app.post(
    "/admin/process-bronze",
    summary="Process Bronze documents and embed",
    description="Quick processing endpoint to process Bronze S3 documents and store embeddings"
)
async def process_bronze(bucket: str = "vesper-dev-bronze", prefix: str = "bronze/sec-edgar/"):
    """Process documents from Bronze layer and embed into vector DB."""
    import json
    import boto3
    from bs4 import BeautifulSoup
    import psycopg2
    
    # This will be run async in background
    return {
        "status": "started",
        "message": "Processing job started - check logs for progress",
        "bucket": bucket,
        "prefix": prefix,
        "note": "This endpoint needs to be implemented with proper background task handling"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
