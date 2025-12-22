"use client";

import { useSession } from "next-auth/react";
import {
  Activity,
  Database,
  DollarSign,
  Zap,
  TrendingUp,
  Clock,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import MetricCard from "@/components/MetricCard";
import GrafanaPanel from "@/components/GrafanaPanel";

export default function DashboardPage() {
  const { data: session, status } = useSession();

  // Dashboard panels configuration - using actual Grafana dashboard UIDs
  // Panel IDs from vesper-api-gateway: 1=Request Rate, 2=P95 Latency, 3=Guardrails, 4=Citations, 5=Demo Request Rate, 6=Demo Temperature
  const grafanaPanels = [
    {
      id: "api-latency",
      title: "API Latency Distribution",
      dashboardId: "vesper-api-gateway",
      dashboardSlug: "vesper-api-gateway-monitoring",
      panelId: 2,
      width: "full",
    },
    {
      id: "request-rate",
      title: "Request Rate",
      dashboardId: "vesper-api-gateway",
      dashboardSlug: "vesper-api-gateway-monitoring",
      panelId: 1,
      width: "half",
    },
    {
      id: "guardrails",
      title: "Guardrails Checks",
      dashboardId: "vesper-api-gateway",
      dashboardSlug: "vesper-api-gateway-monitoring",
      panelId: 3,
      width: "half",
    },
    {
      id: "citations",
      title: "Citations Extracted",
      dashboardId: "vesper-api-gateway",
      dashboardSlug: "vesper-api-gateway-monitoring",
      panelId: 4,
      width: "half",
    },
    {
      id: "demo-metrics",
      title: "Demo Request Rate",
      dashboardId: "vesper-api-gateway",
      dashboardSlug: "vesper-api-gateway-monitoring",
      panelId: 5,
      width: "half",
    },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Operations Dashboard
          </h1>
          <p className="text-slate-500 dark:text-slate-400">
            Real-time system health and performance metrics
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2 px-3 py-1.5 bg-green-100 text-green-700 rounded-full text-sm">
            <span className="w-2 h-2 bg-green-500 rounded-full status-healthy" />
            All Systems Operational
          </span>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="API p95 Latency"
          value="1.2s"
          target="< 2.5s"
          status="healthy"
          icon={<Zap className="w-5 h-5" />}
          trend={{ value: -8, label: "vs last hour" }}
        />

        <MetricCard
          title="Request Rate"
          value="156/min"
          status="healthy"
          icon={<Activity className="w-5 h-5" />}
          trend={{ value: 12, label: "vs last hour" }}
        />

        <MetricCard
          title="Cache Hit Ratio"
          value="34%"
          target="> 30%"
          status="healthy"
          icon={<Database className="w-5 h-5" />}
          trend={{ value: 5, label: "vs last hour" }}
        />

        <MetricCard
          title="Daily Cost"
          value="$42.50"
          status="healthy"
          icon={<DollarSign className="w-5 h-5" />}
          trend={{ value: -3, label: "vs yesterday" }}
        />
      </div>

      {/* Evaluation Metrics */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Latest Evaluation Metrics
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">0.94</div>
            <div className="text-sm text-slate-500">Faithfulness</div>
            <div className="text-xs text-green-600 flex items-center justify-center gap-1 mt-1">
              <CheckCircle className="w-3 h-3" /> ≥ 0.90 target
            </div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">0.88</div>
            <div className="text-sm text-slate-500">Relevance</div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">0.82</div>
            <div className="text-sm text-slate-500">NDCG@10</div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">0.01</div>
            <div className="text-sm text-slate-500">Hallucination Rate</div>
            <div className="text-xs text-green-600 flex items-center justify-center gap-1 mt-1">
              <CheckCircle className="w-3 h-3" /> ≤ 0.02 target
            </div>
          </div>
        </div>
      </div>

      {/* Grafana Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Full-width API Latency Panel */}
        <div className="lg:col-span-2">
          <GrafanaPanel
            title="API Latency Distribution"
            dashboardId="vesper-api-gateway"
            dashboardSlug="vesper-api-gateway-monitoring"
            panelId={2}
            height={300}
          />
        </div>

        {/* Half-width panels */}
        <GrafanaPanel
          title="Request Rate"
          dashboardId="vesper-api-gateway"
          dashboardSlug="vesper-api-gateway-monitoring"
          panelId={1}
          height={250}
        />

        <GrafanaPanel
          title="Guardrails Checks"
          dashboardId="vesper-api-gateway"
          dashboardSlug="vesper-api-gateway-monitoring"
          panelId={3}
          height={250}
        />

        <GrafanaPanel
          title="Citations Extracted"
          dashboardId="vesper-api-gateway"
          dashboardSlug="vesper-api-gateway-monitoring"
          panelId={4}
          height={250}
        />

        <GrafanaPanel
          title="Demo Request Rate"
          dashboardId="vesper-api-gateway"
          dashboardSlug="vesper-api-gateway-monitoring"
          panelId={5}
          height={250}
        />
      </div>

      {/* Recent Alerts */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Recent Alerts
        </h2>

        <div className="space-y-3">
          <AlertItem
            severity="info"
            message="Nightly evaluation completed successfully"
            time="2 hours ago"
          />
          <AlertItem
            severity="warning"
            message="Cache hit ratio dropped below 30% for 5 minutes"
            time="5 hours ago"
            resolved
          />
          <AlertItem
            severity="info"
            message="New model gpt-4o-mini added to routing"
            time="1 day ago"
          />
        </div>
      </div>
    </div>
  );
}

interface AlertItemProps {
  severity: "info" | "warning" | "error";
  message: string;
  time: string;
  resolved?: boolean;
}

function AlertItem({ severity, message, time, resolved }: AlertItemProps) {
  const icons = {
    info: <Activity className="w-4 h-4 text-blue-500" />,
    warning: <AlertTriangle className="w-4 h-4 text-yellow-500" />,
    error: <AlertTriangle className="w-4 h-4 text-red-500" />,
  };

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg ${
        resolved
          ? "bg-slate-50 dark:bg-slate-700/50"
          : "bg-slate-100 dark:bg-slate-700"
      }`}
    >
      {icons[severity]}
      <div className="flex-1">
        <p
          className={`text-sm ${
            resolved ? "text-slate-500" : "text-slate-700 dark:text-slate-300"
          }`}
        >
          {message}
        </p>
        <p className="text-xs text-slate-400 mt-1">{time}</p>
      </div>
      {resolved && (
        <span className="text-xs text-green-600 flex items-center gap-1">
          <CheckCircle className="w-3 h-3" /> Resolved
        </span>
      )}
    </div>
  );
}
