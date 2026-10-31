"use client";

import { useState } from "react";

interface MarketplaceAgent {
  id: string;
  title: string;
  tagline: string;
  description: string;
  icon: string;
  category: string;
  publisher: string;
  downloads: number;
  avgRating: number;
  totalRatings: number;
  tags: string[];
  isFeatured: boolean;
  price: "free" | "premium";
}

const CATEGORIES = ["All", "Customer Support", "Sales", "HR", "Marketing", "Engineering", "Legal", "Finance", "Education"];

const MOCK_AGENTS: MarketplaceAgent[] = [
  { id: "1", title: "Enterprise Support Pro", tagline: "Handle tickets like a fortune 500 company", description: "AI agent trained on 10k+ support conversations. Handles refunds, password resets, billing inquiries, and escalations automatically.", icon: "🎯", category: "Customer Support", publisher: "AgentForge", downloads: 12400, avgRating: 4.8, totalRatings: 342, tags: ["support", "enterprise", "tickets"], isFeatured: true, price: "premium" },
  { id: "2", title: "Cold Caller AI", tagline: "Never miss a lead again", description: "Outbound sales agent with objection handling, BANT qualification, and CRM syncing. Closes 3x more meetings than SDRs.", icon: "📞", category: "Sales", publisher: "SalesBot Inc", downloads: 8900, avgRating: 4.6, totalRatings: 201, tags: ["sales", "outbound", "qualification"], isFeatured: true, price: "premium" },
  { id: "3", title: "HR Onboarding Buddy", tagline: "Welcome new hires with a personal touch", description: "Walks new employees through onboarding steps, answers policy questions, sets up systems access, and books intro meetings.", icon: "🎓", category: "HR", publisher: "PeopleAI", downloads: 5600, avgRating: 4.9, totalRatings: 89, tags: ["onboarding", "hr", "automation"], isFeatured: true, price: "free" },
  { id: "4", title: "Legal Contract Reviewer", tagline: "Find risks before they find you", description: "Reviews contracts, flags risky clauses, suggests amendments, and generates summaries. Trained on 50k+ legal documents.", icon: "⚖️", category: "Legal", publisher: "LegalMind", downloads: 3200, avgRating: 4.7, totalRatings: 56, tags: ["legal", "contracts", "compliance"], isFeatured: false, price: "premium" },
  { id: "5", title: "Code Review Agent", tagline: "Your AI pair programmer", description: "Reviews PRs for bugs, security issues, performance problems, and style violations. Integrates with GitHub/GitLab.", icon: "🔍", category: "Engineering", publisher: "DevTools Co", downloads: 15800, avgRating: 4.5, totalRatings: 478, tags: ["code", "review", "github"], isFeatured: true, price: "free" },
  { id: "6", title: "Content Marketing Writer", tagline: "SEO-optimized content at scale", description: "Writes blog posts, social media content, email campaigns, and landing pages. Maintains brand voice consistency.", icon: "✍️", category: "Marketing", publisher: "ContentAI", downloads: 7200, avgRating: 4.3, totalRatings: 167, tags: ["content", "seo", "marketing"], isFeatured: false, price: "free" },
  { id: "7", title: "Finance Data Analyst", tagline: "Turn numbers into narratives", description: "Analyzes financial reports, calculates KPIs, generates executive summaries, and builds projections.", icon: "📊", category: "Finance", publisher: "FinBot", downloads: 4100, avgRating: 4.6, totalRatings: 92, tags: ["finance", "analytics", "reporting"], isFeatured: false, price: "premium" },
  { id: "8", title: "Course Tutor AI", tagline: "Personalized learning at every level", description: "Adaptive tutoring agent that adjusts difficulty, provides explanations, and tracks progress across subjects.", icon: "📚", category: "Education", publisher: "EduAI Labs", downloads: 9400, avgRating: 4.8, totalRatings: 234, tags: ["education", "tutoring", "adaptive"], isFeatured: false, price: "free" },
];

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={`text-[10px] ${star <= Math.round(rating) ? "text-amber-400" : "text-[var(--color-border)]"}`}>
          ★
        </span>
      ))}
    </div>
  );
}

export default function MarketplacePage() {
  const [category, setCategory] = useState("All");
  const [search, setSearch] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const filtered = MOCK_AGENTS.filter((a) => {
    if (category !== "All" && a.category !== category) return false;
    if (search && !a.title.toLowerCase().includes(search.toLowerCase()) && !a.tags.some((t) => t.includes(search.toLowerCase()))) return false;
    return true;
  });

  const featured = MOCK_AGENTS.filter((a) => a.isFeatured);
  const detail = MOCK_AGENTS.find((a) => a.id === selectedAgent);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[var(--color-border)]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-lg font-bold">🏪 Agent Marketplace</h1>
            <p className="text-xs text-[var(--color-text-dim)]">Browse, clone & deploy community agents — like the GPT Store for voice agents</p>
          </div>
          <button className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-lg text-xs font-medium">
            📤 Publish Agent
          </button>
        </div>

        {/* Search + Categories */}
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search agents, categories, tags..."
            className="px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs w-64 focus:outline-none focus:border-[var(--color-primary)]"
          />
          <div className="flex items-center gap-1 overflow-x-auto">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={`px-2.5 py-1 rounded-full text-[10px] font-medium whitespace-nowrap transition-colors ${
                  category === cat
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-text-dim)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Featured Section */}
        {category === "All" && !search && (
          <div className="mb-8">
            <p className="text-xs font-semibold mb-3">⭐ Featured Agents</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {featured.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent.id)}
                  className="text-left p-4 bg-gradient-to-br from-[var(--color-primary)]/5 to-transparent border border-[var(--color-primary)]/20 rounded-xl hover:border-[var(--color-primary)]/40 transition-all"
                >
                  <span className="text-2xl">{agent.icon}</span>
                  <p className="text-xs font-bold mt-2">{agent.title}</p>
                  <p className="text-[9px] text-[var(--color-text-dim)] mt-0.5">{agent.tagline}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <StarRating rating={agent.avgRating} />
                    <span className="text-[9px] text-[var(--color-text-dim)]">({agent.totalRatings})</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* All Agents Grid */}
        <div>
          <p className="text-xs font-semibold mb-3">
            {category === "All" ? "All Agents" : category} ({filtered.length})
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((agent) => (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(agent.id)}
                className={`text-left p-4 rounded-xl border transition-all ${
                  selectedAgent === agent.id
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-hover)] bg-[var(--color-surface)]"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-2xl">{agent.icon}</span>
                    <div>
                      <p className="text-xs font-bold">{agent.title}</p>
                      <p className="text-[9px] text-[var(--color-text-dim)]">by {agent.publisher}</p>
                    </div>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                    agent.price === "free" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                  }`}>
                    {agent.price}
                  </span>
                </div>
                <p className="text-[10px] text-[var(--color-text-dim)] mt-2 line-clamp-2">{agent.tagline}</p>
                <div className="flex items-center justify-between mt-3">
                  <div className="flex items-center gap-1.5">
                    <StarRating rating={agent.avgRating} />
                    <span className="text-[9px] text-[var(--color-text-dim)]">{agent.avgRating}</span>
                  </div>
                  <span className="text-[9px] text-[var(--color-text-dim)]">⬇ {(agent.downloads / 1000).toFixed(1)}k</span>
                </div>
                <div className="flex items-center gap-1 mt-2">
                  {agent.tags.slice(0, 3).map((t) => (
                    <span key={t} className="px-1.5 py-0.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded text-[8px]">
                      {t}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail Modal */}
        {detail && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-8" onClick={() => setSelectedAgent(null)}>
            <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-2xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-4xl">{detail.icon}</span>
                  <div>
                    <h2 className="text-sm font-bold">{detail.title}</h2>
                    <p className="text-[10px] text-[var(--color-text-dim)]">by {detail.publisher} · {detail.category}</p>
                  </div>
                </div>
                <button onClick={() => setSelectedAgent(null)} className="text-[var(--color-text-dim)] hover:text-white">✕</button>
              </div>

              <p className="text-xs text-[var(--color-text-dim)] mb-4">{detail.description}</p>

              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="p-2.5 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] text-center">
                  <p className="text-sm font-bold">{(detail.downloads / 1000).toFixed(1)}k</p>
                  <p className="text-[9px] text-[var(--color-text-dim)]">Downloads</p>
                </div>
                <div className="p-2.5 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] text-center">
                  <p className="text-sm font-bold">{detail.avgRating}</p>
                  <p className="text-[9px] text-[var(--color-text-dim)]">Rating</p>
                </div>
                <div className="p-2.5 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] text-center">
                  <p className="text-sm font-bold">{detail.totalRatings}</p>
                  <p className="text-[9px] text-[var(--color-text-dim)]">Reviews</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button className="flex-1 px-4 py-2.5 bg-[var(--color-primary)] text-white rounded-xl text-xs font-semibold hover:opacity-90">
                  🚀 Clone & Deploy
                </button>
                <button className="px-4 py-2.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl text-xs hover:border-[var(--color-border-hover)]">
                  Preview
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
