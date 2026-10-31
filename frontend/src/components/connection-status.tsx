/**
 * Connection status indicator component.
 *
 * Shows a colored dot and label reflecting the WebSocket connection state.
 */

interface ConnectionStatusProps {
  state: "disconnected" | "connecting" | "connected" | "error";
}

const stateConfig = {
  disconnected: { color: "bg-zinc-500", label: "Disconnected" },
  connecting: { color: "bg-yellow-500 animate-pulse", label: "Connecting..." },
  connected: { color: "bg-green-500", label: "Connected" },
  error: { color: "bg-red-500", label: "Connection Error" },
};

export function ConnectionStatus({ state }: ConnectionStatusProps) {
  const config = stateConfig[state];

  return (
    <div className="flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2">
      <div className={`h-2 w-2 rounded-full ${config.color}`} />
      <span className="text-sm text-[var(--color-text-muted)]">
        {config.label}
      </span>
    </div>
  );
}
