"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { agentApi, type AgentDetail, type VoiceOption, type AgentVersion, type AgentAnalytics } from "@/lib/api";

type Tab = "prompt" | "voice" | "tools" | "memory" | "analytics" | "versions" | "playground";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "prompt", label: "Prompt", icon: "📝" },
  { id: "voice", label: "Voice", icon: "🎵" },
  { id: "tools", label: "Tools", icon: "🔧" },
  { id: "memory", label: "Memory", icon: "🧠" },
  { id: "analytics", label: "Analytics", icon: "📊" },
  { id: "versions", label: "Versions", icon: "🔄" },
  { id: "playground", label: "Test", icon: "▶️" },
];

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  draft: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  paused: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  archived: "bg-red-500/20 text-red-400 border-red-500/30",
};

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [tab, setTab] = useState<Tab>("prompt");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  // Editable fields
  const [systemPrompt, setSystemPrompt] = useState("");
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [temperature, setTemperature] = useState(0.3);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [ttsVoice, setTtsVoice] = useState("");
  const [ttsRate, setTtsRate] = useState("-5%");
  const [ttsPitch, setTtsPitch] = useState("+0Hz");
  const [ttsVolume, setTtsVolume] = useState("+10%");
  const [language, setLanguage] = useState("en-US");
  const [toolsConfig, setToolsConfig] = useState<Record<string, any>>({});
  const [memoryConfig, setMemoryConfig] = useState<Record<string, any>>({});

  // Sub-data
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [analytics, setAnalytics] = useState<AgentAnalytics | null>(null);

  const loadAgent = useCallback(async () => {
    try {
      const data = await agentApi.get(agentId);
      setAgent(data);
      setSystemPrompt(data.system_prompt);
      setWelcomeMessage(data.welcome_message);
      setTemperature(data.temperature);
      setMaxTokens(data.max_tokens);
      setTtsVoice(data.tts_voice);
      setTtsRate(data.tts_rate);
      setTtsPitch(data.tts_pitch);
      setTtsVolume(data.tts_volume);
      setLanguage(data.language);
      setToolsConfig(data.tools_config || { enabled_tools: [], custom_tools: [] });
      setMemoryConfig(data.memory_config || { type: "window", window_size: 20, summarize: false, max_context_tokens: 8000 });
    } catch {
      setError("Failed to load agent");
    }
    setLoading(false);
  }, [agentId]);

  useEffect(() => {
    loadAgent();
    agentApi.voices().then(setVoices).catch(() => {});
  }, [loadAgent]);

  useEffect(() => {
    if (tab === "versions") {
      agentApi.versions(agentId).then(setVersions).catch(() => {});
    }
    if (tab === "analytics") {
      agentApi.analytics(agentId).then(setAnalytics).catch(() => {});
    }
  }, [tab, agentId]);

  async function handleSave(note?: string) {
    setSaving(true);
    setError("");
    try {
      const updated = await agentApi.update(agentId, {
        system_prompt: systemPrompt,
        welcome_message: welcomeMessage,
        temperature,
        max_tokens: maxTokens,
        tts_voice: ttsVoice,
        tts_rate: ttsRate,
        tts_pitch: ttsPitch,
        tts_volume: ttsVolume,
        language,
        tools_config: toolsConfig,
        memory_config: memoryConfig,
        change_note: note || undefined,
      });
      setAgent(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  }

  async function handlePublish() {
    try {
      const updated = await agentApi.publish(agentId);
      setAgent(updated);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to delete this agent? This cannot be undone.")) return;
    try {
      await agentApi.delete(agentId);
      router.push("/agents");
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleRollback(version: number) {
    try {
      const updated = await agentApi.rollback(agentId, version);
      setAgent(updated);
      setSystemPrompt(updated.system_prompt);
      setWelcomeMessage(updated.welcome_message);
      setTemperature(updated.temperature);
      setMaxTokens(updated.max_tokens);
      setTtsVoice(updated.tts_voice);
      setTtsRate(updated.tts_rate);
      setTtsPitch(updated.tts_pitch);
      setTtsVolume(updated.tts_volume);
      setToolsConfig(updated.tools_config);
      setMemoryConfig(updated.memory_config);
      setTab("prompt");
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[var(--color-text-dim)]">Loading agent...</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-red-400">{error || "Agent not found"}</p>
        <button onClick={() => router.push("/agents")} className="text-sm text-[var(--color-primary)]">
          ← Back to agents
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/agents")}
            className="text-xs text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
          >
            ← Agents
          </button>
          <span className="text-[var(--color-border)]">|</span>
          <h2 className="font-semibold">{agent.name}</h2>
          <span
            className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
              STATUS_COLORS[agent.status] || STATUS_COLORS.draft
            }`}
          >
            {agent.status}
          </span>
          <span className="text-[10px] text-[var(--color-text-dim)]">v{agent.current_version}</span>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="text-xs text-emerald-400">✓ Saved</span>
          )}
          {error && (
            <span className="text-xs text-red-400">{error}</span>
          )}
          {agent.status === "draft" && (
            <button
              onClick={handlePublish}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              Publish
            </button>
          )}
          <button
            onClick={() => handleSave("Manual save")}
            disabled={saving}
            className="px-3 py-1.5 bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 text-red-400 hover:bg-red-500/10 rounded-lg text-xs transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 px-6 pt-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]/50">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-t-lg transition-colors border-b-2 ${
              tab === t.id
                ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-surface)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ═══ PROMPT ═══ */}
        {tab === "prompt" && (
          <div className="max-w-3xl space-y-5">
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                System Prompt
              </label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={14}
                className="w-full px-4 py-3 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl text-sm font-mono leading-relaxed focus:outline-none focus:border-[var(--color-primary)] resize-y"
                placeholder="Define the agent's personality, instructions, guardrails..."
              />
              <div className="flex justify-between mt-1.5">
                <p className="text-[10px] text-[var(--color-text-dim)]">
                  This is the core instruction that shapes your agent&apos;s behavior
                </p>
                <p className="text-[10px] text-[var(--color-text-dim)]">
                  {systemPrompt.length} chars
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                Welcome Message
              </label>
              <input
                type="text"
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                placeholder="First thing the agent says when a call starts"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Temperature: {temperature.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-[var(--color-primary)]"
                />
                <div className="flex justify-between text-[10px] text-[var(--color-text-dim)]">
                  <span>Precise</span>
                  <span>Creative</span>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value) || 4096)}
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
            </div>
          </div>
        )}

        {/* ═══ VOICE ═══ */}
        {tab === "voice" && (
          <div className="max-w-3xl space-y-6">
            <div>
              <h3 className="text-sm font-medium mb-3">Select Voice</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {voices.map((v) => (
                  <button
                    key={v.voice_id}
                    onClick={() => {
                      setTtsVoice(v.voice_id);
                      setLanguage(v.language);
                    }}
                    className={`text-left p-3 rounded-xl border transition-all ${
                      ttsVoice === v.voice_id
                        ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10"
                        : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]/30"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm">{v.gender === "Female" ? "👩" : "👨"}</span>
                      <span className="text-sm font-medium">{v.name}</span>
                    </div>
                    <p className="text-[10px] text-[var(--color-text-dim)]">
                      {v.language} · {v.style}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Speed
                </label>
                <select
                  value={ttsRate}
                  onChange={(e) => setTtsRate(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="-20%">Very Slow</option>
                  <option value="-10%">Slow</option>
                  <option value="-5%">Slightly Slow</option>
                  <option value="+0%">Normal</option>
                  <option value="+10%">Fast</option>
                  <option value="+20%">Very Fast</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Pitch
                </label>
                <select
                  value={ttsPitch}
                  onChange={(e) => setTtsPitch(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="-10Hz">Lower</option>
                  <option value="-5Hz">Slightly Lower</option>
                  <option value="+0Hz">Normal</option>
                  <option value="+5Hz">Slightly Higher</option>
                  <option value="+10Hz">Higher</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Volume
                </label>
                <select
                  value={ttsVolume}
                  onChange={(e) => setTtsVolume(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="-10%">Quiet</option>
                  <option value="+0%">Normal</option>
                  <option value="+10%">Loud</option>
                  <option value="+20%">Very Loud</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* ═══ TOOLS ═══ */}
        {tab === "tools" && (
          <div className="max-w-3xl space-y-5">
            <div>
              <h3 className="text-sm font-medium mb-1">Enabled Tools</h3>
              <p className="text-xs text-[var(--color-text-dim)] mb-3">
                Empty selection allows no tools. Allow all exposes every registered tool. Weather calls Open-Meteo. The calculator walks an AST and does not use eval.
              </p>
              <button
                type="button"
                onClick={() => setToolsConfig({ ...toolsConfig, allow_all: !toolsConfig.allow_all })}
                className={`mb-4 px-3 py-1.5 rounded-lg text-xs border ${
                  toolsConfig.allow_all
                    ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                    : "border-[var(--color-border)] text-[var(--color-text-dim)]"
                }`}
              >
                {toolsConfig.allow_all ? "Allow all tools: on" : "Allow all tools: off"}
              </button>

              {[
                { name: "get_current_time", desc: "Get the current date and time", icon: "🕐" },
                { name: "get_weather", desc: "Get weather for a location", icon: "🌤️" },
                { name: "calculator", desc: "Evaluate math expressions", icon: "🔢" },
              ].map((tool) => {
                const enabled = (toolsConfig.enabled_tools || []).includes(tool.name);
                return (
                  <div
                    key={tool.name}
                    className="flex items-center justify-between p-3 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg mb-2"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{tool.icon}</span>
                      <div>
                        <p className="text-sm font-medium font-mono">{tool.name}</p>
                        <p className="text-[10px] text-[var(--color-text-dim)]">{tool.desc}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        const tools = toolsConfig.enabled_tools || [];
                        setToolsConfig({
                          ...toolsConfig,
                          allow_all: false,
                          enabled_tools: enabled
                            ? tools.filter((t: string) => t !== tool.name)
                            : [...tools, tool.name],
                        });
                      }}
                      className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                        enabled
                          ? "bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                          : "bg-[var(--color-surface-hover)] text-[var(--color-text-dim)]"
                      }`}
                    >
                      {enabled ? "Enabled" : "Disabled"}
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="pt-4 border-t border-[var(--color-border)]">
              <h3 className="text-sm font-medium mb-1">Custom Tools</h3>
              <p className="text-xs text-[var(--color-text-dim)] mb-3">
                Define custom function-calling tools for this agent
              </p>
              <div className="p-8 border border-dashed border-[var(--color-border)] rounded-xl text-center">
                <p className="text-sm text-[var(--color-text-dim)]">
                  Custom tool builder coming soon — define APIs, webhooks, and custom functions
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ═══ MEMORY ═══ */}
        {tab === "memory" && (
          <div className="max-w-3xl space-y-5">
            <div>
              <h3 className="text-sm font-medium mb-1">Conversation Memory</h3>
              <p className="text-xs text-[var(--color-text-dim)] mb-4">
                Configure how the agent remembers conversation context
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Memory Type
                </label>
                <select
                  value={memoryConfig.type || "window"}
                  onChange={(e) =>
                    setMemoryConfig({ ...memoryConfig, type: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="window">Sliding Window</option>
                  <option value="full">Full History</option>
                  <option value="summary">Summarized</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                  Window Size (messages)
                </label>
                <input
                  type="number"
                  value={memoryConfig.window_size || 20}
                  onChange={(e) =>
                    setMemoryConfig({ ...memoryConfig, window_size: parseInt(e.target.value) || 20 })
                  }
                  className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1.5">
                Max Context Tokens
              </label>
              <input
                type="number"
                value={memoryConfig.max_context_tokens || 8000}
                onChange={(e) =>
                  setMemoryConfig({ ...memoryConfig, max_context_tokens: parseInt(e.target.value) || 8000 })
                }
                className="w-full max-w-xs px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-primary)]"
              />
              <p className="text-[10px] text-[var(--color-text-dim)] mt-1">
                Maximum tokens to include from conversation history in each LLM call
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() =>
                  setMemoryConfig({ ...memoryConfig, summarize: !memoryConfig.summarize })
                }
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                  memoryConfig.summarize
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                    : "border-[var(--color-border)] text-[var(--color-text-dim)]"
                }`}
              >
                {memoryConfig.summarize ? "✓ Auto-Summarize ON" : "Auto-Summarize OFF"}
              </button>
              <p className="text-[10px] text-[var(--color-text-dim)]">
                Keep an extractive note of messages that fall outside the window. This does not call a second model.
              </p>
            </div>
          </div>
        )}

        {/* ═══ ANALYTICS ═══ */}
        {tab === "analytics" && (
          <div className="max-w-4xl">
            {analytics ? (
              <div className="space-y-6">
                {/* Stats cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Total Calls", value: analytics.total_calls, icon: "📞" },
                    { label: "Today", value: analytics.calls_today, icon: "📅" },
                    { label: "This Week", value: analytics.calls_this_week, icon: "📆" },
                    { label: "Avg Rating", value: analytics.avg_rating > 0 ? analytics.avg_rating.toFixed(1) : "—", icon: "⭐" },
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

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl">
                    <p className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider mb-1">
                      Avg Duration
                    </p>
                    <p className="text-lg font-semibold">
                      {analytics.avg_duration_ms > 0
                        ? `${(analytics.avg_duration_ms / 1000).toFixed(1)}s`
                        : "—"}
                    </p>
                  </div>
                  <div className="p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl">
                    <p className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider mb-1">
                      Total Duration
                    </p>
                    <p className="text-lg font-semibold">
                      {analytics.total_duration_ms > 0
                        ? `${Math.round(analytics.total_duration_ms / 60000)}m`
                        : "—"}
                    </p>
                  </div>
                </div>

                {/* Recent calls */}
                <div>
                  <h3 className="text-sm font-medium mb-3">Recent Calls</h3>
                  {analytics.recent_calls.length === 0 ? (
                    <p className="text-xs text-[var(--color-text-dim)] p-4 text-center bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                      No calls yet. Test your agent in the Playground tab.
                    </p>
                  ) : (
                    <div className="space-y-1.5">
                      {analytics.recent_calls.map((call) => (
                        <div
                          key={call.id}
                          className="flex items-center justify-between p-3 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                call.status === "completed" ? "bg-emerald-500" : "bg-amber-500"
                              }`}
                            />
                            <span className="font-mono text-[var(--color-text-dim)]">
                              {call.session_id.slice(0, 8)}...
                            </span>
                          </div>
                          <div className="flex items-center gap-4 text-[var(--color-text-dim)]">
                            <span>{call.message_count} msgs</span>
                            <span>{(call.duration_ms / 1000).toFixed(1)}s</span>
                            <span>{new Date(call.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-[var(--color-text-dim)]">Loading analytics...</p>
            )}
          </div>
        )}

        {/* ═══ VERSIONS ═══ */}
        {tab === "versions" && (
          <div className="max-w-3xl">
            <h3 className="text-sm font-medium mb-3">Version History</h3>
            {versions.length === 0 ? (
              <p className="text-xs text-[var(--color-text-dim)]">No versions yet</p>
            ) : (
              <div className="space-y-2">
                {versions.map((v) => (
                  <div
                    key={v.id}
                    className="flex items-center justify-between p-3 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                          v.version === agent.current_version
                            ? "bg-[var(--color-primary)]/20 text-[var(--color-primary)]"
                            : "bg-[var(--color-surface-hover)] text-[var(--color-text-dim)]"
                        }`}
                      >
                        v{v.version}
                      </span>
                      <div>
                        <p className="text-xs">{v.change_note || "No note"}</p>
                        <p className="text-[10px] text-[var(--color-text-dim)]">
                          {new Date(v.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    {v.version !== agent.current_version && (
                      <button
                        onClick={() => handleRollback(v.version)}
                        className="px-2.5 py-1 text-xs text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 rounded-lg transition-colors"
                      >
                        Rollback
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ═══ PLAYGROUND ═══ */}
        {tab === "playground" && (
          <div className="max-w-3xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium">Test Playground</h3>
                <p className="text-xs text-[var(--color-text-muted)]">
                  Talk to your agent in real-time to test its behavior
                </p>
              </div>
              <button
                onClick={() => window.open(`/playground?agent=${agent.slug}`, "_blank")}
                className="px-3 py-1.5 bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white rounded-lg text-xs font-medium transition-colors"
              >
                ▶ Open Full Playground
              </button>
            </div>
            <div className="aspect-video bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl flex items-center justify-center">
              <div className="text-center">
                <p className="text-3xl mb-3">🎙️</p>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Click &quot;Open Full Playground&quot; to test this agent
                </p>
                <p className="text-xs text-[var(--color-text-dim)] mt-1">
                  Opens the voice call UI with this agent&apos;s configuration
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
