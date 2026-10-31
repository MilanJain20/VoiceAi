/**
 * Voice button — primary microphone control.
 *
 * States:
 * - idle: ready to start (grey mic icon)
 * - listening: capturing audio (pulsing blue indicator)
 * - processing: AI is thinking (loading state)
 * - speaking: AI is responding (animated waveform)
 */

"use client";

import { useVoiceStore } from "@/stores/voice-store";

interface VoiceButtonProps {
  onToggle: () => void;
}

export function VoiceButton({ onToggle }: VoiceButtonProps) {
  const voiceState = useVoiceStore((s) => s.voiceState);

  const isActive =
    voiceState === "listening" ||
    voiceState === "processing" ||
    voiceState === "speaking";

  return (
    <button
      onClick={onToggle}
      className={`
        group relative flex h-24 w-24 items-center justify-center rounded-full
        border-2 transition-all duration-300 ease-out
        ${
          isActive
            ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 shadow-[0_0_40px_rgba(99,102,241,0.3)]"
            : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border-hover)] hover:bg-[var(--color-surface-hover)]"
        }
      `}
      aria-label={isActive ? "Stop listening" : "Start listening"}
    >
      {/* Mic / Stop icon */}
      {isActive ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="text-[var(--color-primary)]"
        >
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
      ) : (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="32"
          height="32"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-[var(--color-text-muted)] group-hover:text-[var(--color-text)] transition-colors"
        >
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" x2="12" y1="19" y2="22" />
        </svg>
      )}

      {/* Pulse ring when listening */}
      {voiceState === "listening" && (
        <span className="absolute inset-0 animate-ping rounded-full border-2 border-[var(--color-primary)] opacity-20" />
      )}

      {/* Processing spinner */}
      {voiceState === "processing" && (
        <span className="absolute inset-[-4px] animate-spin rounded-full border-2 border-transparent border-t-[var(--color-primary)]" />
      )}
    </button>
  );
}
