/**
 * API client for the Agent Studio backend.
 */

import { getApiUrl } from "./utils";

const API = getApiUrl();

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ───────────────────────────────────────────────────────────

export interface AgentSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  status: string;
  tts_voice: string;
  language: string;
  total_calls: number;
  total_duration_ms: number;
  avg_rating: number;
  current_version: number;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentDetail extends AgentSummary {
  system_prompt: string;
  welcome_message: string;
  tts_rate: string;
  tts_pitch: string;
  tts_volume: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  tools_config: Record<string, any>;
  memory_config: Record<string, any>;
  workflow_config: Record<string, any>;
  total_duration_ms: number;
}

export interface AgentVersion {
  id: string;
  version: number;
  change_note: string | null;
  created_at: string;
  config_snapshot: Record<string, any>;
}

export interface VoiceOption {
  voice_id: string;
  name: string;
  language: string;
  gender: string;
  style: string;
  preview_url: string;
}

export interface CallLogEntry {
  id: string;
  agent_id: string;
  session_id: string;
  duration_ms: number;
  message_count: number;
  total_tokens: number;
  avg_latency_ms: number;
  status: string;
  rating: number | null;
  created_at: string;
}

export interface AgentAnalytics {
  total_calls: number;
  total_duration_ms: number;
  avg_duration_ms: number;
  avg_rating: number;
  calls_today: number;
  calls_this_week: number;
  top_intents: any[];
  latency_p50_ms: number;
  latency_p95_ms: number;
  recent_calls: CallLogEntry[];
}

// ── Agent CRUD ──────────────────────────────────────────────────────

export const agentApi = {
  list: (params?: { status?: string; category?: string; search?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.category) qs.set("category", params.category);
    if (params?.search) qs.set("search", params.search);
    const q = qs.toString();
    return request<AgentSummary[]>(`/api/v1/agents${q ? `?${q}` : ""}`);
  },

  get: (id: string) => request<AgentDetail>(`/api/v1/agents/${id}`),

  create: (data: Partial<AgentDetail>) =>
    request<AgentDetail>("/api/v1/agents", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<AgentDetail> & { change_note?: string }) =>
    request<AgentDetail>(`/api/v1/agents/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    request<void>(`/api/v1/agents/${id}`, { method: "DELETE" }),

  duplicate: (id: string, name: string) =>
    request<AgentDetail>(`/api/v1/agents/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  publish: (id: string) =>
    request<AgentDetail>(`/api/v1/agents/${id}/publish`, { method: "POST" }),

  templates: () => request<AgentSummary[]>("/api/v1/agents/templates"),

  voices: () => request<VoiceOption[]>("/api/v1/agents/voices"),

  versions: (id: string) =>
    request<AgentVersion[]>(`/api/v1/agents/${id}/versions`),

  rollback: (id: string, version: number) =>
    request<AgentDetail>(`/api/v1/agents/${id}/rollback/${version}`, {
      method: "POST",
    }),

  analytics: (id: string) =>
    request<AgentAnalytics>(`/api/v1/agents/${id}/analytics`),
};

export interface AnalyticsOverview {
  total_agents: number;
  active_agents: number;
  total_calls: number;
  total_duration_ms: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  turn_count: number;
}

export interface CallRecord {
  id: string;
  agent_id: string;
  agent_name: string;
  session_id: string;
  duration_ms: number;
  message_count: number;
  total_tokens: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  status: string;
  rating: number | null;
  created_at: string | null;
}

export const analyticsApi = {
  overview: () => request<AnalyticsOverview>("/api/v1/analytics/overview"),
};

export const callsApi = {
  list: () => request<CallRecord[]>("/api/v1/calls"),
};
