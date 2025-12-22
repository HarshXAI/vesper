"use client";

import { useState, useEffect } from "react";
import { format, parseISO } from "date-fns";
import {
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  ExternalLink,
  Filter,
} from "lucide-react";
import type { EvalRun } from "@/lib/types";

export default function EvalsPage() {
  const [evalRuns, setEvalRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "success" | "failure">("all");

  useEffect(() => {
    fetchEvalRuns();
  }, []);

  const fetchEvalRuns = async () => {
    setLoading(true);
    try {
      // Fetch from API or mock data
      const response = await fetch("/api/evals");
      if (response.ok) {
        const data = await response.json();
        setEvalRuns(data);
      } else {
        // Use mock data for demo
        setEvalRuns(getMockEvalRuns());
      }
    } catch (error) {
      console.error("Error fetching eval runs:", error);
      setEvalRuns(getMockEvalRuns());
    } finally {
      setLoading(false);
    }
  };

  const filteredRuns = evalRuns.filter((run) => {
    if (filter === "all") return true;
    return run.status === filter;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Evaluation Runs
          </h1>
          <p className="text-slate-500 dark:text-slate-400">
            Nightly evaluation results from MLflow
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Filter */}
          <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1.5 rounded text-sm ${
                filter === "all"
                  ? "bg-white dark:bg-slate-600 shadow text-slate-900 dark:text-white"
                  : "text-slate-600 dark:text-slate-400"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter("success")}
              className={`px-3 py-1.5 rounded text-sm ${
                filter === "success"
                  ? "bg-white dark:bg-slate-600 shadow text-green-600"
                  : "text-slate-600 dark:text-slate-400"
              }`}
            >
              Success
            </button>
            <button
              onClick={() => setFilter("failure")}
              className={`px-3 py-1.5 rounded text-sm ${
                filter === "failure"
                  ? "bg-white dark:bg-slate-600 shadow text-red-600"
                  : "text-slate-600 dark:text-slate-400"
              }`}
            >
              Failure
            </button>
          </div>

          {/* Refresh */}
          <button
            onClick={fetchEvalRuns}
            className="flex items-center gap-2 px-4 py-2 bg-vesper-600 text-white rounded-lg hover:bg-vesper-700"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Runs"
          value={evalRuns.length}
          subtitle="Last 30 days"
        />
        <SummaryCard
          title="Success Rate"
          value={`${Math.round(
            (evalRuns.filter((r) => r.status === "success").length /
              evalRuns.length) *
              100
          )}%`}
          subtitle={`${
            evalRuns.filter((r) => r.status === "success").length
          } passed`}
          color="green"
        />
        <SummaryCard
          title="Avg Faithfulness"
          value={calculateAverage(evalRuns, "faithfulness").toFixed(2)}
          subtitle="Target: ≥ 0.90"
          color={
            calculateAverage(evalRuns, "faithfulness") >= 0.9
              ? "green"
              : "yellow"
          }
        />
        <SummaryCard
          title="Avg Latency p95"
          value={`${calculateAverage(evalRuns, "latency_p95_ms").toFixed(0)}ms`}
          subtitle="Target: < 2500ms"
          color={
            calculateAverage(evalRuns, "latency_p95_ms") < 2500
              ? "green"
              : "yellow"
          }
        />
      </div>

      {/* Eval Runs Table */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50 dark:bg-slate-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Faithfulness
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Relevance
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Recall@10
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Latency p95
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Cost
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Samples
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {filteredRuns.map((run) => (
                <tr
                  key={run.id}
                  className="hover:bg-slate-50 dark:hover:bg-slate-700/50"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                    {format(parseISO(run.timestamp), "MMM d, yyyy HH:mm")}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <MetricValue
                      value={run.metrics.faithfulness}
                      target={0.9}
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <MetricValue value={run.metrics.relevance} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <MetricValue value={run.metrics.recall_at_10} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <MetricValue
                      value={run.metrics.latency_p95_ms}
                      target={2500}
                      higherIsBetter={false}
                      suffix="ms"
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                    ${run.metrics.cost_usd.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                    {run.sample_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {run.mlflow_run_id && (
                      <a
                        href={`${process.env.NEXT_PUBLIC_MLFLOW_URL}/#/experiments/0/runs/${run.mlflow_run_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-vesper-600 hover:text-vesper-700 flex items-center gap-1 text-sm"
                      >
                        MLflow <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Helper components
function SummaryCard({
  title,
  value,
  subtitle,
  color = "default",
}: {
  title: string;
  value: string | number;
  subtitle: string;
  color?: "default" | "green" | "yellow" | "red";
}) {
  const colorClasses = {
    default: "text-slate-900 dark:text-white",
    green: "text-green-600",
    yellow: "text-yellow-600",
    red: "text-red-600",
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-4">
      <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
      <p className={`text-2xl font-bold ${colorClasses[color]}`}>{value}</p>
      <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: "success" | "failure" | "running";
}) {
  const config = {
    success: { icon: CheckCircle, bg: "bg-green-100", text: "text-green-700" },
    failure: { icon: XCircle, bg: "bg-red-100", text: "text-red-700" },
    running: { icon: Clock, bg: "bg-blue-100", text: "text-blue-700" },
  };

  const { icon: Icon, bg, text } = config[status];

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${bg} ${text}`}
    >
      <Icon className="w-3 h-3" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function MetricValue({
  value,
  target,
  higherIsBetter = true,
  suffix = "",
}: {
  value: number;
  target?: number;
  higherIsBetter?: boolean;
  suffix?: string;
}) {
  const meetsTarget =
    target === undefined ||
    (higherIsBetter ? value >= target : value <= target);

  return (
    <span
      className={`text-sm font-medium ${
        meetsTarget ? "text-green-600" : "text-yellow-600"
      }`}
    >
      {typeof value === "number" && value < 10
        ? value.toFixed(2)
        : Math.round(value)}
      {suffix}
    </span>
  );
}

function calculateAverage(
  runs: EvalRun[],
  metric: keyof EvalRun["metrics"]
): number {
  if (runs.length === 0) return 0;
  const sum = runs.reduce((acc, run) => acc + (run.metrics[metric] || 0), 0);
  return sum / runs.length;
}

function getMockEvalRuns(): EvalRun[] {
  return [
    {
      id: "eval-001",
      timestamp: "2024-12-21T02:00:00Z",
      status: "success",
      metrics: {
        faithfulness: 0.94,
        relevance: 0.88,
        recall_at_10: 0.82,
        ndcg_at_10: 0.79,
        latency_p95_ms: 1850,
        cost_usd: 12.45,
      },
      sample_count: 100,
      mlflow_run_id: "run-abc123",
    },
    {
      id: "eval-002",
      timestamp: "2024-12-20T02:00:00Z",
      status: "success",
      metrics: {
        faithfulness: 0.92,
        relevance: 0.87,
        recall_at_10: 0.8,
        ndcg_at_10: 0.77,
        latency_p95_ms: 1920,
        cost_usd: 11.8,
      },
      sample_count: 100,
      mlflow_run_id: "run-def456",
    },
    {
      id: "eval-003",
      timestamp: "2024-12-19T02:00:00Z",
      status: "failure",
      metrics: {
        faithfulness: 0.85,
        relevance: 0.82,
        recall_at_10: 0.75,
        ndcg_at_10: 0.72,
        latency_p95_ms: 2100,
        cost_usd: 10.2,
      },
      sample_count: 100,
      mlflow_run_id: "run-ghi789",
    },
    {
      id: "eval-004",
      timestamp: "2024-12-18T02:00:00Z",
      status: "success",
      metrics: {
        faithfulness: 0.91,
        relevance: 0.86,
        recall_at_10: 0.79,
        ndcg_at_10: 0.76,
        latency_p95_ms: 1780,
        cost_usd: 11.5,
      },
      sample_count: 100,
      mlflow_run_id: "run-jkl012",
    },
    {
      id: "eval-005",
      timestamp: "2024-12-17T02:00:00Z",
      status: "success",
      metrics: {
        faithfulness: 0.93,
        relevance: 0.89,
        recall_at_10: 0.83,
        ndcg_at_10: 0.8,
        latency_p95_ms: 1650,
        cost_usd: 12.1,
      },
      sample_count: 100,
      mlflow_run_id: "run-mno345",
    },
  ];
}
