"use client";

import { TrendingUp, TrendingDown } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  target?: string;
  status?: "healthy" | "warning" | "critical";
  icon?: React.ReactNode;
  trend?: {
    value: number;
    label: string;
  };
}

export default function MetricCard({
  title,
  value,
  target,
  status = "healthy",
  icon,
  trend,
}: MetricCardProps) {
  const statusColors = {
    healthy: "bg-green-500",
    warning: "bg-yellow-500",
    critical: "bg-red-500",
  };

  const statusBgColors = {
    healthy: "bg-green-50 dark:bg-green-900/20",
    warning: "bg-yellow-50 dark:bg-yellow-900/20",
    critical: "bg-red-50 dark:bg-red-900/20",
  };

  return (
    <div
      className={`rounded-xl p-4 border border-slate-200 dark:border-slate-700 
                    dashboard-card ${statusBgColors[status]}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {icon && (
            <div
              className={`p-2 rounded-lg ${
                status === "healthy"
                  ? "bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400"
                  : status === "warning"
                  ? "bg-yellow-100 text-yellow-600 dark:bg-yellow-900/50 dark:text-yellow-400"
                  : "bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400"
              }`}
            >
              {icon}
            </div>
          )}
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {title}
            </p>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">
              {value}
            </p>
          </div>
        </div>

        <div
          className={`w-2 h-2 rounded-full ${statusColors[status]} status-${status}`}
        />
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-200 dark:border-slate-600">
        {target && (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Target: {target}
          </span>
        )}

        {trend && (
          <span
            className={`flex items-center gap-1 text-xs font-medium ${
              trend.value >= 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            {trend.value >= 0 ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {Math.abs(trend.value)}% {trend.label}
          </span>
        )}
      </div>
    </div>
  );
}
