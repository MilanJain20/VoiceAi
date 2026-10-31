"use client";

import { useState } from "react";

interface CallReplayItem {
  id: string;
  agentName: string;
  agentIcon: string;
  sessionId: string;
  duration: string;
  durationMs: number;
  date: string;
  summary: string;
  tags: string[];
  overallScore: number;
  sentiment: "positive" | "neutral" | "negative";
}

interface TimelineEvent {
  timeMs: number;
  type: "user_speech" | "agent_speech" | "tool_call" | "silence" | "emotion";
  content: string;
  duration?: number;
  metadata?: Record<string, any>;
}

const MOCK_CALLS: CallReplayItem[] = [
  { id: "1", agentName: "Support Agent", agentIcon: "🤖", sessionId: "sess_a9f23c", duration: "3:42", durationMs: 222000, date: "Today, 2:35 PM", summary: "User reset password and updated billing info", tags: ["password", "billing"], overallScore: 92, sentiment: "positive" },
  { id: "2", agentName: "Sales Rep", agentIcon: "💼", sessionId: "sess_b7d41a", duration: "8:15", durationMs: 495000, date: "Today, 11:20 AM", summary: "Product demo for enterprise plan, user interested", tags: ["demo", "enterprise"], overallScore: 87, sentiment: "positive" },
  { id: "3", agentName: "HR Assistant", agentIcon: "👔", sessionId: "sess_c3e82f", duration: "2:08", durationMs: 128000, date: "Yesterday", summary: "PTO request inquiry - agent couldn't find policy", tags: ["pto", "escalated"], overallScore: 61, sentiment: "negative" },
  { id: "4", agentName: "Support Agent", agentIcon: "🤖", sessionId: "sess_d1f95b", duration: "5:30", durationMs: 330000, date: "Yesterday", summary: "Complex refund case, successful resolution", tags: ["refund", "resolved"], overallScore: 95, sentiment: "positive" },
  { id: "5", agentName: "Onboarding", agentIcon: "🎓", sessionId: "sess_e4a27d", duration: "12:45", durationMs: 765000, date: "2 days ago", summary: "Full onboarding walkthrough, user activated", tags: ["onboarding", "activated"], overallScore: 98, sentiment: "positive" },
];

const MOCK_TIMELINE: TimelineEvent[] = [
  { timeMs: 0, type: "user_speech", content: "Hi, I need help resetting my password", duration: 2400 },
  { timeMs: 3000, type: "agent_speech", content: "Of course! I can help you reset your password. Let me pull up your account. Can you confirm your email address?", duration: 4200 },
  { timeMs: 8000, type: "user_speech", content: "Sure, it's john@example.com", duration: 1800 },
  { timeMs: 10500, type: "tool_call", content: "lookup_account(email='john@example.com')", duration: 1200 },
  { timeMs: 12000, type: "agent_speech", content: "I found your account. I'm sending a password reset link to your email now.", duration: 3500 },
  { timeMs: 16000, type: "tool_call", content: "send_password_reset(user_id='usr_123')", duration: 800 },
  { timeMs: 17500, type: "agent_speech", content: "Done! You should receive the reset link within a minute. Is there anything else I can help with?", duration: 4000 },
  { timeMs: 22000, type: "emotion", content: "User sentiment: satisfied (0.89)", duration: 0 },
  { timeMs: 23000, type: "user_speech", content: "Actually yes, I also need to update my billing address", duration: 2800 },
  { timeMs: 26500, type: "agent_speech", content: "Sure! What's the new billing address you'd like to use?", duration: 2200 },
  { timeMs: 30000, type: "user_speech", content: "123 Main Street, San Francisco, CA 94102", duration: 3000 },
  { timeMs: 34000, type: "tool_call", content: "update_billing(user_id='usr_123', address='123 Main St, SF, CA 94102')", duration: 900 },
  { timeMs: 35500, type: "agent_speech", content: "Your billing address has been updated successfully. Anything else?", duration: 2800 },
  { timeMs: 39000, type: "user_speech", content: "No, that's all. Thanks!", duration: 1500 },
  { timeMs: 41000, type: "agent_speech", content: "You're welcome! Have a great day!", duration: 1800 },
  { timeMs: 43000, type: "emotion", content: "User sentiment: very satisfied (0.95)", duration: 0 },
];

function formatTime(ms: number): string {
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function CallReplayPage() {
  const [selectedCall, setSelectedCall] = useState<string | null>("1");
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [filter, setFilter] = useState("");

  const call = MOCK_CALLS.find((c) => c.id === selectedCall);
  const totalDuration = call?.durationMs || 222000;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div>
          <h1 className="text-lg font-bold">📞 Call Replay</h1>
          <p className="text-xs text-[var(--color-text-dim)]">Replay conversations with full timeline, transcripts, tool calls & sentiment</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search calls..."
            className="px-2.5 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-xs w-48 focus:outline-none focus:border-[var(--color-primary)]"
          />
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Call List */}
        <div className="w-80 border-r border-[var(--color-border)] overflow-y-auto p-4">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-3">
            Recent Calls ({MOCK_CALLS.length})
          </p>
          <div className="space-y-2">
            {MOCK_CALLS.filter((c) => c.summary.toLowerCase().includes(filter.toLowerCase()) || c.agentName.toLowerCase().includes(filter.toLowerCase())).map((c) => (
              <button
                key={c.id}
                onClick={() => { setSelectedCall(c.id); setCurrentTime(0); }}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selectedCall === c.id
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">{c.agentIcon}</span>
                    <span className="text-xs font-semibold">{c.agentName}</span>
                  </div>
                  <span className="text-[9px] text-[var(--color-text-dim)]">{c.duration}</span>
                </div>
                <p className="text-[10px] text-[var(--color-text-dim)] line-clamp-2 mb-1.5">{c.summary}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    {c.tags.map((t) => (
                      <span key={t} className="px-1.5 py-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded text-[8px]">
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${c.sentiment === "positive" ? "bg-emerald-500" : c.sentiment === "negative" ? "bg-red-500" : "bg-amber-500"}`} />
                    <span className={`text-[9px] font-bold ${c.overallScore >= 90 ? "text-emerald-400" : c.overallScore >= 70 ? "text-amber-400" : "text-red-400"}`}>
                      {c.overallScore}%
                    </span>
                  </div>
                </div>
                <p className="text-[9px] text-[var(--color-text-dim)] mt-1">{c.date}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Replay Panel */}
        {call && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Playback Controls */}
            <div className="px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]/50">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-xs font-semibold">{call.agentIcon} {call.agentName} — {call.summary}</p>
                  <p className="text-[9px] text-[var(--color-text-dim)]">{call.date} · Session: {call.sessionId}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-medium ${
                    call.sentiment === "positive" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                  }`}>
                    {call.sentiment}
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)] text-[9px] font-bold">
                    Score: {call.overallScore}%
                  </span>
                </div>
              </div>

              {/* Timeline Scrubber */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="w-8 h-8 flex items-center justify-center bg-[var(--color-primary)] rounded-full text-white text-sm"
                >
                  {isPlaying ? "⏸" : "▶"}
                </button>
                <span className="text-[10px] font-mono w-8">{formatTime(currentTime)}</span>
                <div className="flex-1 relative h-6 group cursor-pointer" onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const pct = (e.clientX - rect.left) / rect.width;
                  setCurrentTime(Math.floor(pct * totalDuration));
                }}>
                  {/* Timeline visualization */}
                  <div className="absolute inset-y-1 inset-x-0 bg-[var(--color-bg)] rounded-full overflow-hidden">
                    {/* Progress */}
                    <div
                      className="absolute inset-y-0 left-0 bg-[var(--color-primary)]/20 rounded-full"
                      style={{ width: `${(currentTime / totalDuration) * 100}%` }}
                    />
                    {/* Event markers */}
                    {MOCK_TIMELINE.map((evt, i) => (
                      <div
                        key={i}
                        className={`absolute top-1/2 -translate-y-1/2 w-1 h-3 rounded-full ${
                          evt.type === "user_speech" ? "bg-blue-500" :
                          evt.type === "agent_speech" ? "bg-emerald-500" :
                          evt.type === "tool_call" ? "bg-amber-500" :
                          "bg-purple-500"
                        }`}
                        style={{ left: `${(evt.timeMs / totalDuration) * 100}%` }}
                        title={`${formatTime(evt.timeMs)} - ${evt.type}`}
                      />
                    ))}
                    {/* Playhead */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-white"
                      style={{ left: `${(currentTime / totalDuration) * 100}%` }}
                    />
                  </div>
                </div>
                <span className="text-[10px] font-mono w-8">{call.duration}</span>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-4 mt-2">
                {[
                  { color: "bg-blue-500", label: "User" },
                  { color: "bg-emerald-500", label: "Agent" },
                  { color: "bg-amber-500", label: "Tool" },
                  { color: "bg-purple-500", label: "Emotion" },
                ].map((l) => (
                  <div key={l.label} className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${l.color}`} />
                    <span className="text-[9px] text-[var(--color-text-dim)]">{l.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline Events */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-2">
                {MOCK_TIMELINE.map((evt, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-3 p-2.5 rounded-lg transition-all cursor-pointer ${
                      currentTime >= evt.timeMs && currentTime < (MOCK_TIMELINE[i + 1]?.timeMs || totalDuration)
                        ? "bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20"
                        : "hover:bg-[var(--color-surface)]"
                    }`}
                    onClick={() => setCurrentTime(evt.timeMs)}
                  >
                    <span className="text-[9px] font-mono text-[var(--color-text-dim)] w-8 pt-0.5 flex-shrink-0">
                      {formatTime(evt.timeMs)}
                    </span>
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 ${
                      evt.type === "user_speech" ? "bg-blue-500/10 text-blue-400" :
                      evt.type === "agent_speech" ? "bg-emerald-500/10 text-emerald-400" :
                      evt.type === "tool_call" ? "bg-amber-500/10 text-amber-400" :
                      "bg-purple-500/10 text-purple-400"
                    }`}>
                      {evt.type === "user_speech" ? "👤" : evt.type === "agent_speech" ? "🤖" : evt.type === "tool_call" ? "🔧" : "💭"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[9px] font-semibold uppercase text-[var(--color-text-dim)] mb-0.5">
                        {evt.type.replace("_", " ")}
                        {evt.duration ? ` · ${(evt.duration / 1000).toFixed(1)}s` : ""}
                      </p>
                      <p className={`text-xs ${evt.type === "tool_call" ? "font-mono text-amber-300" : ""}`}>
                        {evt.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
