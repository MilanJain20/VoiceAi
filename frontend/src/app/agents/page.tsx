"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { agentApi, type AgentSummary } from "@/lib/api";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "general", label: "General" },
  { value: "sales", label: "Sales" },
  { value: "support", label: "Support" },
  { value: "hr", label: "HR" },
  { value: "interview", label: "Interview" },
  { value: "education", label: "Education" },
  { value: "healthcare", label: "Healthcare" },
  { value: "custom", label: "Custom" },
];

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-400",
  draft: "bg-amber-500/20 text-amber-400",
  paused: "bg-gray-500/20 text-gray-400",
  archived: "bg-red-500/20 text-red-400",
};

const CATEGORY_ICONS: Record<string, string> = {
  general: "🤖",
  sales: "💼",
  support: "🎧",
  hr: "👔",
  interview: "🎤",
  education: "📚",
  healthcare: "🏥",
  custom: "⚙️",
};

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");

  useEffect(() => {
    loadAgents();
  }, [search, category]);

  async function loadAgents() {
    setLoading(true);
    try {
      const data = await agentApi.list({
        search: search || undefined,
        category: category || undefined,
      });
      setAgents(data);
    } catch {
      // API might not be running yet
      setAgents([]);
    }
    setLoading(false);
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Your Agents</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Create, configure, and deploy voice AI agents
          </p>
        </div>
        <button
          onClick={() => router.push("/agents/create")}
          className="px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white rounded-lg text-sm font-medium transition-colors"
        >
          + Create Agent
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Search agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-xs px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm placeholder:text-[var(--color-text-dim)] focus:outline-none focus:border-[var(--color-primary)]"
        />
        <div className="flex gap-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setCategory(cat.value)}
              className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                category === cat.value
                  ? "bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Agent Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-[var(--color-text-dim)]">Loading agents...</div>
        </div>
      ) : agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <div className="text-5xl">🤖</div>
          <h2 className="text-lg font-medium">No agents yet</h2>
          <p className="text-sm text-[var(--color-text-muted)]">
            Create your first voice AI agent to get started
          </p>
          <button
            onClick={() => router.push("/agents/create")}
            className="px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white rounded-lg text-sm font-medium transition-colors"
          >
            + Create Agent
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <div
              key={agent.id}
              onClick={() => router.push(`/agents/${agent.id}`)}
              className="group cursor-pointer bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 hover:border-[var(--color-primary)]/50 transition-all hover:shadow-lg hover:shadow-[var(--color-primary)]/5"
            >
              {/* Top row */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl">
                    {CATEGORY_ICONS[agent.category] || "🤖"}
                  </span>
                  <div>
                    <h3 className="font-semibold text-sm group-hover:text-[var(--color-primary)] transition-colors">
                      {agent.name}
                    </h3>
                    <p className="text-[10px] text-[var(--color-text-dim)]">
                      v{agent.current_version} · {agent.tts_voice.split("-").slice(-1)}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                    STATUS_COLORS[agent.status] || STATUS_COLORS.draft
                  }`}
                >
                  {agent.status}
                </span>
              </div>

              {/* Description */}
              <p className="text-xs text-[var(--color-text-muted)] mb-4 line-clamp-2 min-h-[2.5em]">
                {agent.description || "No description"}
              </p>

              {/* Stats */}
              <div className="flex items-center gap-4 text-[10px] text-[var(--color-text-dim)]">
                <span>📞 {agent.total_calls} calls</span>
                <span>
                  ⭐ {agent.avg_rating > 0 ? agent.avg_rating.toFixed(1) : "—"}
                </span>
                <span className="ml-auto text-[var(--color-text-dim)]">
                  {new Date(agent.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
