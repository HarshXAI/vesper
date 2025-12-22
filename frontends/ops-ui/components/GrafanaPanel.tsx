"use client";

import { useState, useEffect } from "react";
import { ExternalLink, RefreshCw, AlertCircle } from "lucide-react";

interface GrafanaPanelProps {
  title: string;
  dashboardId: string;
  dashboardSlug?: string;
  panelId: number;
  height?: number;
  timeRange?: string;
}

export default function GrafanaPanel({
  title,
  dashboardId,
  dashboardSlug,
  panelId,
  height = 300,
  timeRange = "now-1h",
}: GrafanaPanelProps) {
  const [loading, setLoading] = useState(true);
  const [key, setKey] = useState(0);

  const grafanaUrl =
    process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3003";

  // Construct Grafana panel embed URL - include slug if provided for proper routing
  const slug = dashboardSlug || dashboardId;
  const panelUrl = `${grafanaUrl}/d-solo/${dashboardId}/${slug}?orgId=1&panelId=${panelId}&from=${timeRange}&to=now&theme=dark`;

  // Auto-hide loading after a short delay since cross-origin iframes don't fire onLoad reliably
  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1500);
    return () => clearTimeout(timer);
  }, [key]);

  const refresh = () => {
    setLoading(true);
    setKey((k) => k + 1);
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <h3 className="font-medium text-slate-900 dark:text-white">{title}</h3>

        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>

          <a
            href={`${grafanaUrl}/d/${dashboardId}/${slug}?panelId=${panelId}&fullscreen`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded"
            title="Open in Grafana"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Panel content */}
      <div className="relative" style={{ height }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-700 z-10">
            <RefreshCw className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        )}

        <iframe
          key={key}
          id={`grafana-${dashboardId}-${panelId}`}
          src={panelUrl}
          className="w-full h-full border-0"
          style={{ background: "#1e293b" }}
          allow="fullscreen"
        />
      </div>
    </div>
  );
}

/**
 * Component for displaying multiple Grafana panels in a grid
 */
export function GrafanaDashboard({ panels }: { panels: GrafanaPanelProps[] }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {panels.map((panel, index) => (
        <GrafanaPanel key={index} {...panel} />
      ))}
    </div>
  );
}
