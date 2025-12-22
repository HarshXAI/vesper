"use client";

import { useState } from "react";
import {
  Play,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertCircle,
  Calendar,
  FileText,
} from "lucide-react";
import { useToast } from "../providers";

interface DagAction {
  id: string;
  name: string;
  description: string;
  dagId: string;
  icon: React.ReactNode;
  params?: Record<string, any>;
}

export default function ActionsPage() {
  const { showToast } = useToast();
  const [runningDags, setRunningDags] = useState<Set<string>>(new Set());
  const [recentTriggers, setRecentTriggers] = useState<TriggerRecord[]>([]);

  const dagActions: DagAction[] = [
    {
      id: "reembed-24h",
      name: "Re-embed Last 24h",
      description:
        "Re-embed documents modified in the last 24 hours with the current embedding model",
      dagId: "reembed_subset",
      icon: <RefreshCw className="w-6 h-6" />,
      params: { hours_back: 24 },
    },
    {
      id: "rechunk-params",
      name: "Rechunk with New Params",
      description:
        "Rechunk all documents with updated chunking parameters (size, overlap)",
      dagId: "rechunk_params",
      icon: <FileText className="w-6 h-6" />,
      params: { chunk_size: 512, chunk_overlap: 50 },
    },
    {
      id: "nightly-eval",
      name: "Run Nightly Evaluation",
      description: "Trigger the nightly evaluation pipeline manually",
      dagId: "nightly_evaluation_dag",
      icon: <Play className="w-6 h-6" />,
    },
    {
      id: "embedding-backfill",
      name: "Embedding Backfill",
      description:
        "Backfill embeddings for documents missing vector representations",
      dagId: "embedding_backfill_dag",
      icon: <Calendar className="w-6 h-6" />,
    },
  ];

  const triggerDag = async (action: DagAction) => {
    if (runningDags.has(action.id)) return;

    setRunningDags((prev) => new Set(prev).add(action.id));

    try {
      const response = await fetch("/api/trigger-dag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dag_id: action.dagId,
          conf: action.params || {},
        }),
      });

      if (response.ok || response.status === 202) {
        const data = await response.json().catch(() => ({}));

        showToast(`${action.name} triggered successfully!`, "success");

        setRecentTriggers((prev) => [
          {
            id: Date.now().toString(),
            action: action.name,
            dagId: action.dagId,
            timestamp: new Date().toISOString(),
            status: "accepted",
            runId: data.dag_run_id,
          },
          ...prev.slice(0, 9), // Keep last 10
        ]);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error("Error triggering DAG:", error);
      showToast(`Failed to trigger ${action.name}`, "error");

      setRecentTriggers((prev) => [
        {
          id: Date.now().toString(),
          action: action.name,
          dagId: action.dagId,
          timestamp: new Date().toISOString(),
          status: "failed",
        },
        ...prev.slice(0, 9),
      ]);
    } finally {
      setRunningDags((prev) => {
        const next = new Set(prev);
        next.delete(action.id);
        return next;
      });
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Remediation Actions
        </h1>
        <p className="text-slate-500 dark:text-slate-400">
          Trigger Airflow DAGs to remediate issues or update embeddings
        </p>
      </div>

      {/* Warning Banner */}
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-yellow-800 dark:text-yellow-200">
              Production Impact
            </h3>
            <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
              These actions will run on production data. Re-embedding or
              rechunking may temporarily affect search quality while in
              progress. Ensure you have reviewed the runbooks before triggering.
            </p>
          </div>
        </div>
      </div>

      {/* Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {dagActions.map((action) => (
          <ActionCard
            key={action.id}
            action={action}
            isRunning={runningDags.has(action.id)}
            onTrigger={() => triggerDag(action)}
          />
        ))}
      </div>

      {/* Recent Triggers */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Recent Triggers
        </h2>

        {recentTriggers.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            No recent triggers. Actions you trigger will appear here.
          </p>
        ) : (
          <div className="space-y-3">
            {recentTriggers.map((trigger) => (
              <TriggerRow key={trigger.id} trigger={trigger} />
            ))}
          </div>
        )}
      </div>

      {/* Airflow Link */}
      <div className="text-center">
        <a
          href={process.env.NEXT_PUBLIC_AIRFLOW_URL || "http://localhost:8080"}
          target="_blank"
          rel="noopener noreferrer"
          className="text-vesper-600 hover:underline text-sm"
        >
          Open Airflow Dashboard →
        </a>
      </div>
    </div>
  );
}

interface ActionCardProps {
  action: DagAction;
  isRunning: boolean;
  onTrigger: () => void;
}

function ActionCard({ action, isRunning, onTrigger }: ActionCardProps) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 dashboard-card">
      <div className="flex items-start gap-4">
        <div className="p-3 bg-vesper-100 dark:bg-vesper-900/30 text-vesper-600 rounded-lg">
          {action.icon}
        </div>

        <div className="flex-1">
          <h3 className="font-semibold text-slate-900 dark:text-white">
            {action.name}
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {action.description}
          </p>

          {action.params && (
            <div className="mt-3 p-2 bg-slate-50 dark:bg-slate-700 rounded text-xs font-mono text-slate-600 dark:text-slate-400">
              {JSON.stringify(action.params)}
            </div>
          )}
        </div>
      </div>

      <button
        onClick={onTrigger}
        disabled={isRunning}
        className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2.5 
                   bg-vesper-600 text-white rounded-lg hover:bg-vesper-700
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transition-colors"
      >
        {isRunning ? (
          <>
            <RefreshCw className="w-4 h-4 animate-spin" />
            Triggering...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Trigger DAG
          </>
        )}
      </button>
    </div>
  );
}

interface TriggerRecord {
  id: string;
  action: string;
  dagId: string;
  timestamp: string;
  status: "accepted" | "failed";
  runId?: string;
}

function TriggerRow({ trigger }: { trigger: TriggerRecord }) {
  return (
    <div className="flex items-center gap-4 p-3 bg-slate-50 dark:bg-slate-700 rounded-lg">
      {trigger.status === "accepted" ? (
        <CheckCircle className="w-5 h-5 text-green-500" />
      ) : (
        <AlertCircle className="w-5 h-5 text-red-500" />
      )}

      <div className="flex-1">
        <p className="font-medium text-slate-900 dark:text-white text-sm">
          {trigger.action}
        </p>
        <p className="text-xs text-slate-500">
          <code className="bg-slate-200 dark:bg-slate-600 px-1 rounded">
            {trigger.dagId}
          </code>
          {trigger.runId && <span className="ml-2">Run: {trigger.runId}</span>}
        </p>
      </div>

      <div className="text-right">
        <p
          className={`text-xs font-medium ${
            trigger.status === "accepted" ? "text-green-600" : "text-red-600"
          }`}
        >
          {trigger.status === "accepted" ? "202 Accepted" : "Failed"}
        </p>
        <p className="text-xs text-slate-400">
          {new Date(trigger.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
