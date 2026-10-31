"use client";

import { useState } from "react";

interface EvaluationRow {
  id: string;
  agentName: string;
  agentIcon: string;
  date: string;
  overallScore: number;
  conversationQuality: number;
  taskCompletion: number;
  hallucination: number;
  latencyScore: number;
  toolSuccess: number;
  csat: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  talkRatio: number;
  interruptionCount: number;
  judgeModel: string;
  judgeReasoning: string;
}

const MOCK_EVALS: EvaluationRow[] = [
  { id: "1", agentName: "Support Agent", agentIcon: "🤖", date: "Today", overallScore: 92, conversationQuality: 94, taskCompletion: 96, hallucination: 3, latencyScore: 88, toolSuccess: 100, csat: 4.7, avgLatencyMs: 420, p95LatencyMs: 890, talkRatio: 0.45, interruptionCount: 1, judgeModel: "gpt-4o", judgeReasoning: "Excellent task completion with minimal hallucination. Minor latency spikes on tool calls." },
  { id: "2", agentName: "Sales Rep", agentIcon: "💼", date: "Today", overallScore: 87, conversationQuality: 89, taskCompletion: 84, hallucination: 8, latencyScore: 91, toolSuccess: 85, csat: 4.3, avgLatencyMs: 340, p95LatencyMs: 680, talkRatio: 0.62, interruptionCount: 3, judgeModel: "gpt-4o", judgeReasoning: "Good engagement but overpromised on demo features. Talk ratio too high — agent dominated." },
  { id: "3", agentName: "HR Assistant", agentIcon: "👔", date: "Yesterday", overallScore: 61, conversationQuality: 58, taskCompletion: 42, hallucination: 22, latencyScore: 85, toolSuccess: 67, csat: 3.1, avgLatencyMs: 510, p95LatencyMs: 1200, talkRatio: 0.55, interruptionCount: 0, judgeModel: "gpt-4o", judgeReasoning: "Significant hallucination on PTO policy details. Failed to complete primary task (policy lookup). Needs knowledge base update." },
  { id: "4", agentName: "Onboarding", agentIcon: "🎓", date: "Yesterday", overallScore: 98, conversationQuality: 97, taskCompletion: 100, hallucination: 1, latencyScore: 95, toolSuccess: 100, csat: 4.9, avgLatencyMs: 280, p95LatencyMs: 450, talkRatio: 0.48, interruptionCount: 0, judgeModel: "gpt-4o", judgeReasoning: "Perfect onboarding flow. All steps completed, user activated and engaged throughout." },
  { id: "5", agentName: "Support Agent", agentIcon: "🤖", date: "2 days ago", overallScore: 78, conversationQuality: 75, taskCompletion: 80, hallucination: 12, latencyScore: 82, toolSuccess: 90, csat: 3.8, avgLatencyMs: 590, p95LatencyMs: 1450, talkRatio: 0.52, interruptionCount: 2, judgeModel: "gpt-4o", judgeReasoning: "Moderate hallucination on pricing tiers. Latency degraded during tool execution." },
];

function ScoreBar({ value, max = 100, color }: { value: number; max?: number; color: string }) {
  const pct = (value / max) * 100;
  return (
    <div className="w-full h-1.5 bg-[var(--color-surface)] rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

function getScoreColor(score: number): string {
  if (score >= 90) return "#22c55e";
  if (score >= 70) return "#f59e0b";
  return "#ef4444";
}

export default function EvaluationsPage() {
  const [selectedEval, setSelectedEval] = useState<string | null>("1");
  const [dateRange, setDateRange] = useState("7d");

  const current = MOCK_EVALS.find((e) => e.id === selectedEval);

  // Aggregate stats
  const avgOverall = Math.round(MOCK_EVALS.reduce((a, e) => a + e.overallScore, 0) / MOCK_EVALS.length);
  const avgHallucination = Math.round(MOCK_EVALS.reduce((a, e) => a + e.hallucination, 0) / MOCK_EVALS.length);
  const avgCSAT = (MOCK_EVALS.reduce((a, e) => a + e.csat, 0) / MOCK_EVALS.length).toFixed(1);
  const avgLatency = Math.round(MOCK_EVALS.reduce((a, e) => a + e.avgLatencyMs, 0) / MOCK_EVALS.length);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div>
          <h1 className="text-lg font-bold">🎯 Agent Evaluations</h1>
          <p className="text-xs text-[var(--color-text-dim)]">LLM-as-Judge scoring — quality, hallucination, latency, CSAT, tool success</p>
        </div>
        <div className="flex items-center gap-2">
          {["24h", "7d", "30d", "90d"].map((range) => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium ${
                dateRange === range ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface)] text-[var(--color-text-dim)] border border-[var(--color-border)]"
              }`}
            >
              {range}
            </button>
          ))}
          <button className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-lg text-xs font-medium ml-2">
            Run Evaluation
          </button>
        </div>
      </div>

      {/* Aggregate Stats */}
      <div className="grid grid-cols-4 gap-3 px-6 py-4 border-b border-[var(--color-border)]">
        {[
          { label: "Overall Score", value: `${avgOverall}%`, icon: "🎯", color: getScoreColor(avgOverall) },
          { label: "Hallucination", value: `${avgHallucination}%`, icon: "🌀", color: avgHallucination < 10 ? "#22c55e" : "#ef4444" },
          { label: "CSAT", value: `${avgCSAT}/5`, icon: "⭐", color: "#f59e0b" },
          { label: "Avg Latency", value: `${avgLatency}ms`, icon: "⚡", color: avgLatency < 500 ? "#22c55e" : "#f59e0b" },
        ].map((stat) => (
          <div key={stat.label} className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
            <p className="text-[9px] text-[var(--color-text-dim)]">{stat.icon} {stat.label}</p>
            <p className="text-lg font-bold mt-0.5" style={{ color: stat.color }}>{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Eval List */}
        <div className="w-80 border-r border-[var(--color-border)] overflow-y-auto p-4">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)] mb-3">
            Evaluation Results ({MOCK_EVALS.length})
          </p>
          <div className="space-y-2">
            {MOCK_EVALS.map((ev) => (
              <button
                key={ev.id}
                onClick={() => setSelectedEval(ev.id)}
                className={`w-full text-left p-3 rounded-xl border transition-all ${
                  selectedEval === ev.id
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                    : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span>{ev.agentIcon}</span>
                    <span className="text-xs font-semibold">{ev.agentName}</span>
                  </div>
                  <span className="text-sm font-bold" style={{ color: getScoreColor(ev.overallScore) }}>
                    {ev.overallScore}%
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <div>
                    <p className="text-[8px] text-[var(--color-text-dim)]">Quality</p>
                    <ScoreBar value={ev.conversationQuality} color={getScoreColor(ev.conversationQuality)} />
                  </div>
                  <div>
                    <p className="text-[8px] text-[var(--color-text-dim)]">Tasks</p>
                    <ScoreBar value={ev.taskCompletion} color={getScoreColor(ev.taskCompletion)} />
                  </div>
                  <div>
                    <p className="text-[8px] text-[var(--color-text-dim)]">Halluc.</p>
                    <ScoreBar value={100 - ev.hallucination} color={getScoreColor(100 - ev.hallucination)} />
                  </div>
                </div>
                <p className="text-[9px] text-[var(--color-text-dim)] mt-1.5">{ev.date} · {ev.judgeModel}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        {current && (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-bold">{current.agentIcon} {current.agentName} — Evaluation Detail</h2>
                <p className="text-[10px] text-[var(--color-text-dim)]">{current.date} · Judge: {current.judgeModel}</p>
              </div>
              <span className="text-2xl font-bold" style={{ color: getScoreColor(current.overallScore) }}>
                {current.overallScore}%
              </span>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
              {[
                { label: "Conversation Quality", value: current.conversationQuality, suffix: "%" },
                { label: "Task Completion", value: current.taskCompletion, suffix: "%" },
                { label: "Hallucination Rate", value: current.hallucination, suffix: "%", invert: true },
                { label: "Latency Score", value: current.latencyScore, suffix: "%" },
                { label: "Tool Success Rate", value: current.toolSuccess, suffix: "%" },
                { label: "CSAT Score", value: current.csat, suffix: "/5", max: 5 },
              ].map((metric) => (
                <div key={metric.label} className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                  <p className="text-[9px] text-[var(--color-text-dim)] mb-1">{metric.label}</p>
                  <p className="text-lg font-bold" style={{ color: getScoreColor(metric.invert ? 100 - metric.value : (metric.max === 5 ? metric.value * 20 : metric.value)) }}>
                    {metric.value}{metric.suffix}
                  </p>
                  <ScoreBar
                    value={metric.max === 5 ? metric.value : metric.value}
                    max={metric.max || 100}
                    color={getScoreColor(metric.invert ? 100 - metric.value : (metric.max === 5 ? metric.value * 20 : metric.value))}
                  />
                </div>
              ))}
            </div>

            {/* Performance Metrics */}
            <div className="grid grid-cols-4 gap-3 mb-6">
              <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                <p className="text-[9px] text-[var(--color-text-dim)]">Avg Latency</p>
                <p className="text-sm font-bold">{current.avgLatencyMs}ms</p>
              </div>
              <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                <p className="text-[9px] text-[var(--color-text-dim)]">P95 Latency</p>
                <p className="text-sm font-bold">{current.p95LatencyMs}ms</p>
              </div>
              <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                <p className="text-[9px] text-[var(--color-text-dim)]">Talk Ratio</p>
                <p className="text-sm font-bold">{Math.round(current.talkRatio * 100)}%</p>
              </div>
              <div className="p-3 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
                <p className="text-[9px] text-[var(--color-text-dim)]">Interruptions</p>
                <p className="text-sm font-bold">{current.interruptionCount}</p>
              </div>
            </div>

            {/* Judge Reasoning */}
            <div className="p-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)]">
              <p className="text-xs font-semibold mb-2">🧠 Judge Analysis ({current.judgeModel})</p>
              <p className="text-xs text-[var(--color-text-dim)] leading-relaxed">{current.judgeReasoning}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
