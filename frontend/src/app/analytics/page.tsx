"use client";

import { useEffect, useState } from "react";
import { agentApi, type AgentSummary } from "@/lib/api";

interface GlobalStats {
  total_agents: number;
  active_agents: number;
  total_calls: number;
  total_duration_min: number;
}

export default function AnalyticsDashboard() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    agentApi
      .list()
      .then(setAgents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const stats: GlobalStats = {
    total_agents: agents.length,
    active_agents: agents.filter((a) => a.status === "active").length,
    total_calls: agents.reduce((sum, a) => sum + a.total_calls, 0),
    total_duration_min: agents.reduce((sum, a) => sum + (a.total_duration_ms || 0), 0) / 60000,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[var(--color-text-dim)]">Loading analytics...</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-lg font-bold mb-1">Analytics Dashboard</h1>
      <p className="text-xs text-[var(--color-text-muted)] mb-6">
        Performance overview across all agents
      </p>

      {/* Global stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {[
          { label: "Total Agents", value: stats.total_agents, icon: "🤖" },
          { label: "Active Agents", value: stats.active_agents, icon: "✅" },
          { label: "Total Calls", value: stats.total_calls, icon: "📞" },
          {
            label: "Total Duration",
            value: stats.total_duration_min > 0 ? `${Math.round(stats.total_duration_min)}m` : "—",
            icon: "⏱️",
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl"
          >
            <div className="flex items-center gap-2 mb-2">
              <span>{stat.icon}</span>
              <span className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider">
                {stat.label}
              </span>
            </div>
            <p className="text-2xl font-bold">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Agent performance table */}
      <h2 className="text-sm font-medium mb-3">Agent Performance</h2>
      {agents.length === 0 ? (
        <p className="text-xs text-[var(--color-text-dim)] p-6 text-center bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
          No agents created yet
        </p>
      ) : (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Agent
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Category
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Status
                </th>
                <th className="text-right px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Calls
                </th>
                <th className="text-right px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Rating
                </th>
                <th className="text-right px-4 py-2.5 font-medium text-[var(--color-text-muted)]">
                  Version
                </th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                  onClick={() => (window.location.href = `/agents/${a.id}`)}
                >
                  <td className="px-4 py-2.5 font-medium">{a.name}</td>
                  <td className="px-4 py-2.5 text-[var(--color-text-dim)] capitalize">{a.category}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] ${
                        a.status === "active"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-amber-500/20 text-amber-400"
                      }`}
                    >
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">{a.total_calls}</td>
                  <td className="px-4 py-2.5 text-right">
                    {a.avg_rating > 0 ? `${a.avg_rating.toFixed(1)} ⭐` : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">v{a.current_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
