"use client";

import { useEffect, useState } from "react";
import { callsApi, type CallRecord } from "@/lib/api";

export default function CallsPage() {
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    callsApi
      .list()
      .then(setCalls)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-lg font-bold mb-1">Calls</h1>
      <p className="text-xs text-[var(--color-text-muted)] mb-6">
        Sessions recorded by the voice pipeline. Empty until an agent with a saved id finishes a call.
      </p>
      {loading && <p className="text-sm text-[var(--color-text-dim)]">Loading calls...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && calls.length === 0 && (
        <p className="text-sm text-[var(--color-text-dim)]">No calls yet.</p>
      )}
      <div className="space-y-2">
        {calls.map((call) => (
          <div key={call.id} className="rounded-xl border border-[var(--color-border)] p-4 text-sm">
            <div className="flex justify-between gap-3">
              <span className="font-medium">{call.agent_name}</span>
              <span className="text-[var(--color-text-dim)]">{call.created_at}</span>
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-2">
              {Math.round(call.duration_ms / 1000)}s · {call.message_count} messages · {call.total_tokens} chunks · avg {call.avg_latency_ms} ms · p95 {call.p95_latency_ms} ms
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
