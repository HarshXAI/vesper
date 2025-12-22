"use client";

import { useEffect, useState } from "react";
import {
  X,
  Clock,
  AlertCircle,
  CheckCircle,
  Loader2,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import type { Trace, TraceSpan } from "@/lib/types";

interface TraceViewProps {
  traceId: string;
  onClose?: () => void;
}

export default function TraceView({ traceId, onClose }: TraceViewProps) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrace();
  }, [traceId]);

  const fetchTrace = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch trace from Jaeger API
      const jaegerUrl =
        process.env.NEXT_PUBLIC_JAEGER_UI_URL || "http://localhost:16686";
      const response = await fetch(`${jaegerUrl}/api/traces/${traceId}`);

      if (!response.ok) {
        throw new Error("Failed to fetch trace");
      }

      const data = await response.json();
      const parsedTrace = parseJaegerTrace(data);
      setTrace(parsedTrace);
    } catch (err) {
      console.error("Error fetching trace:", err);
      // Create a mock trace for demo purposes
      setTrace(createMockTrace(traceId));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-vesper-600" />
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-2 text-red-500">
          <AlertCircle className="w-5 h-5" />
          <span>{error || "Failed to load trace"}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
        <div>
          <h2 className="font-semibold text-slate-900 dark:text-white">
            Trace Details
          </h2>
          <p className="text-xs text-slate-500 font-mono">{traceId}</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-semibold text-slate-900 dark:text-white">
              {trace.spans.length}
            </p>
            <p className="text-xs text-slate-500">Spans</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-slate-900 dark:text-white">
              {trace.total_duration_ms.toFixed(0)}ms
            </p>
            <p className="text-xs text-slate-500">Duration</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-slate-900 dark:text-white">
              {new Set(trace.spans.map((s) => s.service_name)).size}
            </p>
            <p className="text-xs text-slate-500">Services</p>
          </div>
        </div>
      </div>

      {/* Spans */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {trace.spans.map((span, index) => (
            <SpanItem
              key={span.span_id}
              span={span}
              totalDuration={trace.total_duration_ms}
              depth={0}
            />
          ))}
        </div>
      </div>

      {/* Footer with Jaeger link */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-700">
        <a
          href={`${
            process.env.NEXT_PUBLIC_JAEGER_UI_URL || "http://localhost:16686"
          }/trace/${traceId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-vesper-600 hover:underline"
        >
          View in Jaeger →
        </a>
      </div>
    </div>
  );
}

interface SpanItemProps {
  span: TraceSpan;
  totalDuration: number;
  depth: number;
}

function SpanItem({ span, totalDuration, depth }: SpanItemProps) {
  const [expanded, setExpanded] = useState(depth < 2);

  const percentage = (span.duration_ms / totalDuration) * 100;
  const hasChildren = span.children && span.children.length > 0;

  const getStatusIcon = () => {
    switch (span.status) {
      case "OK":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "ERROR":
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getServiceColor = (service: string) => {
    const colors: Record<string, string> = {
      "api-gateway": "bg-blue-500",
      retriever: "bg-green-500",
      reranker: "bg-purple-500",
      llm: "bg-orange-500",
      embedder: "bg-pink-500",
    };
    return colors[service] || "bg-slate-500";
  };

  return (
    <div style={{ marginLeft: depth * 16 }}>
      <div
        className={`flex items-center gap-2 p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-700 
                   cursor-pointer ${
                     expanded ? "bg-slate-50 dark:bg-slate-800" : ""
                   }`}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Expand/collapse button */}
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )
        ) : (
          <div className="w-4" />
        )}

        {/* Status icon */}
        {getStatusIcon()}

        {/* Service badge */}
        <span
          className={`px-2 py-0.5 text-xs text-white rounded ${getServiceColor(
            span.service_name
          )}`}
        >
          {span.service_name}
        </span>

        {/* Operation name */}
        <span className="flex-1 text-sm text-slate-700 dark:text-slate-300 truncate">
          {span.operation_name}
        </span>

        {/* Duration */}
        <span className="text-xs text-slate-500 font-mono">
          {span.duration_ms.toFixed(1)}ms
        </span>

        {/* Duration bar */}
        <div className="w-24 h-2 bg-slate-200 dark:bg-slate-600 rounded-full overflow-hidden">
          <div
            className="h-full bg-vesper-500 rounded-full"
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      </div>

      {/* Attributes (when expanded) */}
      {expanded &&
        span.attributes &&
        Object.keys(span.attributes).length > 0 && (
          <div className="ml-10 mb-2 p-2 bg-slate-50 dark:bg-slate-800 rounded text-xs">
            {Object.entries(span.attributes).map(([key, value]) => (
              <div key={key} className="flex gap-2">
                <span className="text-slate-500">{key}:</span>
                <span className="text-slate-700 dark:text-slate-300 font-mono">
                  {String(value)}
                </span>
              </div>
            ))}
          </div>
        )}

      {/* Children */}
      {expanded && hasChildren && (
        <div className="border-l border-slate-200 dark:border-slate-600">
          {span.children!.map((child) => (
            <SpanItem
              key={child.span_id}
              span={child}
              totalDuration={totalDuration}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Helper functions
function parseJaegerTrace(data: any): Trace {
  // Parse Jaeger API response format
  const traceData = data.data?.[0] || data;
  const spans =
    traceData.spans?.map((s: any) => ({
      span_id: s.spanID,
      operation_name: s.operationName,
      service_name:
        traceData.processes?.[s.processID]?.serviceName || "unknown",
      start_time: s.startTime / 1000, // Convert microseconds to milliseconds
      duration_ms: s.duration / 1000,
      status:
        s.tags?.find((t: any) => t.key === "otel.status_code")?.value || "OK",
      attributes: Object.fromEntries(
        (s.tags || []).map((t: any) => [t.key, t.value])
      ),
    })) || [];

  const startTime = Math.min(...spans.map((s: TraceSpan) => s.start_time));
  const endTime = Math.max(
    ...spans.map((s: TraceSpan) => s.start_time + s.duration_ms)
  );

  return {
    trace_id: traceData.traceID || "",
    spans,
    start_time: startTime,
    end_time: endTime,
    total_duration_ms: endTime - startTime,
  };
}

function createMockTrace(traceId: string): Trace {
  const now = Date.now();

  return {
    trace_id: traceId,
    start_time: now,
    end_time: now + 450,
    total_duration_ms: 450,
    spans: [
      {
        span_id: "span-1",
        operation_name: "POST /v1/ask",
        service_name: "api-gateway",
        start_time: now,
        duration_ms: 450,
        status: "OK",
        attributes: { "http.method": "POST", "http.status_code": 200 },
        children: [
          {
            span_id: "span-2",
            operation_name: "guardrails.pre_check",
            service_name: "api-gateway",
            start_time: now + 5,
            duration_ms: 15,
            status: "OK",
            attributes: { "guardrails.passed": true },
          },
          {
            span_id: "span-3",
            operation_name: "retrieve_documents",
            service_name: "retriever",
            start_time: now + 20,
            duration_ms: 120,
            status: "OK",
            attributes: {
              "documents.count": 10,
              "embedding.model": "text-embedding-3-small",
            },
          },
          {
            span_id: "span-4",
            operation_name: "rerank_documents",
            service_name: "reranker",
            start_time: now + 140,
            duration_ms: 80,
            status: "OK",
            attributes: {
              "reranker.model": "cohere-rerank-v3",
              "reranker.top_n": 5,
            },
          },
          {
            span_id: "span-5",
            operation_name: "generate_response",
            service_name: "llm",
            start_time: now + 220,
            duration_ms: 200,
            status: "OK",
            attributes: {
              model: "gpt-4o-mini",
              "tokens.input": 1500,
              "tokens.output": 350,
            },
          },
          {
            span_id: "span-6",
            operation_name: "guardrails.post_check",
            service_name: "api-gateway",
            start_time: now + 420,
            duration_ms: 25,
            status: "OK",
            attributes: { "guardrails.passed": true },
          },
        ],
      },
    ],
  };
}
