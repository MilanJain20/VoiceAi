"use client";

import { useState, useEffect } from "react";

interface CoachingMetrics {
  sentiment: number;
  confidence: number;
  engagement: number;
  frustration: number;
  emotion: string;
  topic: string;
  talkRatio: number;
  pace: "slow" | "normal" | "fast";
  interruptions: number;
  silencePct: number;
}

interface CoachingAlert {
  id: string;
  time: string;
  type: "warning" | "suggestion" | "success";
  message: string;
}

interface AgentSession {
  id: string;
  agentName: string;
  agentIcon: string;
  status: "live" | "idle";
  currentTopic: string;
  duration: string;
  sentiment: number;
}

const MOCK_SESSIONS: AgentSession[] = [
  { id: "1", agentName: "Support Agent", agentIcon: "🤖", status: "live", currentTopic: "Password Reset", duration: "2:34", sentiment: 0.82 },
  { id: "2", agentName: "Sales Rep", agentIcon: "💼", status: "live", currentTopic: "Enterprise Demo", duration: "6:12", sentiment: 0.71 },
  { id: "3", agentName: "HR Assistant", agentIcon: "👔", status: "idle", currentTopic: "—", duration: "—", sentiment: 0 },
  { id: "4", agentName: "Onboarding", agentIcon: "🎓", status: "live", currentTopic: "Setup Walkthrough", duration: "8:45", sentiment: 0.95 },
];

const MOCK_ALERTS: CoachingAlert[] = [
  { id: "1", time: "0:15 ago", type: "warning", message: "User frustration detected — consider offering escalation" },
  { id: "2", time: "0:42 ago", type: "suggestion", message: "Talk ratio imbalanced (68% agent) — ask open-ended questions" },
  { id: "3", time: "1:20 ago", type: "success", message: "Sentiment recovered after empathy statement" },
  { id: "4", time: "2:05 ago", type: "suggestion", message: "Long silence detected (4.2s) — prompt user with follow-up" },
  { id: "5", time: "3:10 ago", type: "warning", message: "Possible hallucination detected: 'Enterprise plan includes unlimited seats'" },
  { id: "6", time: "4:30 ago", type: "success", message: "Tool call successful: calendar_check() — meeting booked" },
];

function AnimatedGauge({ value, label, color, size = 80 }: { value: number; label: string; color: string; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-surface)" strokeWidth={4} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <p className="text-lg font-bold -mt-12 mb-5" style={{ color }}>{value}%</p>
      <p className="text-[9px] text-[var(--color-text-dim)]">{label}</p>
    </div>
  );
}

export default function LiveCoachingPage() {
  const [selectedSession, setSelectedSession] = useState("1");
  const [metrics, setMetrics] = useState<CoachingMetrics>({
    sentiment: 82,
    confidence: 74,
    engagement: 89,
    frustration: 12,
    emotion: "curious",
    topic: "Password Reset",
    talkRatio: 45,
    pace: "normal",
    interruptions: 1,
    silencePct: 8,
  });

  // Simulate live metric updates
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics((prev) => ({
        ...prev,
        sentiment: Math.max(0, Math.min(100, prev.sentiment + (Math.random() - 0.5) * 6)),
        confidence: Math.max(0, Math.min(100, prev.confidence + (Math.random() - 0.5) * 4)),
        engagement: Math.max(0, Math.min(100, prev.engagement + (Math.random() - 0.5) * 3)),
        frustration: Math.max(0, Math.min(100, prev.frustration + (Math.random() - 0.5) * 5)),
        talkRatio: Math.max(20, Math.min(80, prev.talkRatio + (Math.random() - 0.5) * 3)),
      }));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div>
          <h1 className="text-lg font-bold">🧠 Live Coaching</h1>
          <p className="text-xs text-[var(--color-text-dim)]">Real-time sentiment, emotion & confidence monitoring with AI coaching suggestions</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-medium text-emerald-400">3 Live Sessions</span>
          </span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Session List */}
        <div className="w-60 border-r border-[var(--color-border)] p-4 overflow-y-auto">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-3">Active Sessions</p>
          <div className="space-y-2">
            {MOCK_SESSIONS.map((session) => (
              <button
                key={session.id}
                onClick={() => setSelectedSession(session.id)}
                className={`w-full text-left p-2.5 rounded-xl border transition-all ${
                  selectedSession === session.id
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span>{session.agentIcon}</span>
                    <span className="text-[10px] font-semibold">{session.agentName}</span>
                  </div>
                  <span className={`w-2 h-2 rounded-full ${session.status === "live" ? "bg-emerald-500 animate-pulse" : "bg-zinc-500"}`} />
                </div>
                {session.status === "live" && (
                  <>
                    <p className="text-[9px] text-[var(--color-text-dim)]">{session.currentTopic} · {session.duration}</p>
                    <div className="mt-1 h-1 bg-[var(--color-surface)] rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${session.sentiment * 100}%` }} />
                    </div>
                  </>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Main Coaching Panel */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Real-time Gauges */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <AnimatedGauge value={Math.round(metrics.sentiment)} label="Sentiment" color="#22c55e" />
            <AnimatedGauge value={Math.round(metrics.confidence)} label="Confidence" color="#6366f1" />
            <AnimatedGauge value={Math.round(metrics.engagement)} label="Engagement" color="#f59e0b" />
            <AnimatedGauge value={Math.round(metrics.frustration)} label="Frustration" color="#ef4444" />
          </div>

          {/* Live Metrics Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
            <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-[9px] text-[var(--color-text-dim)]">💭 Emotion</p>
              <p className="text-sm font-bold capitalize mt-0.5">{metrics.emotion}</p>
            </div>
            <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-[9px] text-[var(--color-text-dim)]">📋 Topic</p>
              <p className="text-sm font-bold mt-0.5">{metrics.topic}</p>
            </div>
            <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-[9px] text-[var(--color-text-dim)]">🎙️ Talk Ratio</p>
              <p className="text-sm font-bold mt-0.5">{Math.round(metrics.talkRatio)}% user</p>
            </div>
            <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-[9px] text-[var(--color-text-dim)]">🏃 Pace</p>
              <p className="text-sm font-bold capitalize mt-0.5">{metrics.pace}</p>
            </div>
            <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-[9px] text-[var(--color-text-dim)]">🤫 Silence</p>
              <p className="text-sm font-bold mt-0.5">{metrics.silencePct}%</p>
            </div>
          </div>

          {/* Talk Ratio Visualization */}
          <div className="mb-6 p-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
            <p className="text-xs font-semibold mb-2">🎙️ Talk Distribution</p>
            <div className="flex items-center gap-2 h-6">
              <span className="text-[9px] w-10 text-right text-blue-400">User</span>
              <div className="flex-1 flex h-4 rounded-full overflow-hidden">
                <div className="bg-blue-500 transition-all duration-1000" style={{ width: `${metrics.talkRatio}%` }} />
                <div className="bg-emerald-500 transition-all duration-1000" style={{ width: `${100 - metrics.talkRatio - metrics.silencePct}%` }} />
                <div className="bg-zinc-700 transition-all duration-1000" style={{ width: `${metrics.silencePct}%` }} />
              </div>
              <span className="text-[9px] w-10 text-emerald-400">Agent</span>
            </div>
            <div className="flex items-center justify-center gap-4 mt-2">
              <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /><span className="text-[9px] text-[var(--color-text-dim)]">User ({Math.round(metrics.talkRatio)}%)</span></div>
              <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /><span className="text-[9px] text-[var(--color-text-dim)]">Agent ({Math.round(100 - metrics.talkRatio - metrics.silencePct)}%)</span></div>
              <div className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-zinc-700" /><span className="text-[9px] text-[var(--color-text-dim)]">Silence ({metrics.silencePct}%)</span></div>
            </div>
          </div>

          {/* AI Coaching Alerts */}
          <div className="p-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
            <p className="text-xs font-semibold mb-3">💡 AI Coaching Suggestions</p>
            <div className="space-y-2">
              {MOCK_ALERTS.map((alert) => (
                <div
                  key={alert.id}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border ${
                    alert.type === "warning"
                      ? "bg-amber-500/5 border-amber-500/20"
                      : alert.type === "success"
                      ? "bg-emerald-500/5 border-emerald-500/20"
                      : "bg-blue-500/5 border-blue-500/20"
                  }`}
                >
                  <span className="text-sm flex-shrink-0">
                    {alert.type === "warning" ? "⚠️" : alert.type === "success" ? "✅" : "💡"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px]">{alert.message}</p>
                    <p className="text-[9px] text-[var(--color-text-dim)] mt-0.5">{alert.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
