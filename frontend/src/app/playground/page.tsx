"use client";

import { Suspense, useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ConnectionStatus } from "@/components/connection-status";
import { VoiceButton } from "@/components/voice-button";
import { WebcamFeed, type WebcamFeedHandle } from "@/components/webcam-feed";
import { AIAvatar } from "@/components/ai-avatar";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useFaceTracking } from "@/hooks/use-face-tracking";
import { useVoiceStore } from "@/stores/voice-store";

export default function PlaygroundPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen text-[var(--color-text-dim)]">Loading playground...</div>}>
      <PlaygroundInner />
    </Suspense>
  );
}

function PlaygroundInner() {
  const searchParams = useSearchParams();
  const agentParam = searchParams.get("agent");

  const {
    connectionState,
    voiceState,
    transcript,
    latency,
    amplitude,
    connect,
    disconnect,
    startListening,
    stopListening,
    sendUserTranscript,
    setAmplitude,
    setAgentId,
  } = useVoiceStore();

  const [mounted, setMounted] = useState(false);
  const [agentName, setAgentName] = useState<string>("Aria AI");
  const [sttError, setSttError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const webcamRef = useRef<WebcamFeedHandle>(null);
  const videoElRef = useRef<HTMLVideoElement | null>(null);

  const isActive =
    voiceState === "listening" ||
    voiceState === "processing" ||
    voiceState === "speaking";

  // Face tracking — avatar watches you through the webcam
  const faceTracking = useFaceTracking(videoElRef, isActive);

  // Keep videoElRef in sync with webcam component
  useEffect(() => {
    if (webcamRef.current) {
      videoElRef.current = webcamRef.current.getVideoElement();
    }
  });

  // Browser-side STT via Web Speech API
  const {
    isListening: isSpeechListening,
    isSupported: isSpeechSupported,
    start: startSpeechRecognition,
    stop: stopSpeechRecognition,
  } = useSpeechRecognition({
    onInterimTranscript: (text) => {
      // Update amplitude based on text length for visual feedback
      setAmplitude(Math.min(text.length * 0.02, 1.0));

      // Show interim text in the transcript (as partial user message)
      useVoiceStore.setState((state) => {
        const existing = state.transcript.findIndex(
          (t) => t.role === "user" && !t.isFinal
        );
        const entry = {
          id: `user-partial-${Date.now()}`,
          role: "user" as const,
          content: text,
          timestamp: Date.now(),
          isFinal: false,
          confidence: 0.5,
        };
        if (existing >= 0) {
          const updated = [...state.transcript];
          updated[existing] = entry;
          return { transcript: updated };
        }
        return { transcript: [...state.transcript, entry] };
      });
    },
    onFinalTranscript: (text) => {
      if (text.trim()) {
        sendUserTranscript(text.trim());
      }
      setAmplitude(0);
    },
    onError: (error) => {
      setSttError(`Speech recognition error: ${error}`);
    },
  });

  const handleToggle = useCallback(async () => {
    if (voiceState === "idle") {
      setSttError(null);
      if (connectionState !== "connected") {
        connect();
      }
      // Use browser STT (no audio streaming needed)
      startSpeechRecognition();
      startListening();
    } else {
      stopSpeechRecognition();
      stopListening();
      setAmplitude(0);
    }
  }, [voiceState, connectionState, connect, startSpeechRecognition, startListening, stopSpeechRecognition, stopListening, setAmplitude]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  useEffect(() => {
    setMounted(true);
    // Set agent_id from URL param so WS start_session includes it
    if (agentParam) {
      setAgentId(agentParam);
      // Fetch agent name for display
      fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/agents/${agentParam}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.name) setAgentName(data.name); })
        .catch(() => {});
    } else {
      setAgentId(null);
    }
  }, [agentParam, setAgentId]);

  if (!mounted) return null;

  // Map voiceState to avatar state
  const avatarState = (
    voiceState === "processing"
      ? "thinking"
      : voiceState === "speaking"
      ? "speaking"
      : voiceState === "listening"
      ? "listening"
      : "idle"
  ) as "idle" | "listening" | "thinking" | "speaking";

  return (
    <main className="flex h-screen flex-col bg-[var(--color-bg)]">
      {/* Top Bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          {agentParam && (
            <a href={`/agents`} className="text-xs text-[var(--color-text-dim)] hover:text-[var(--color-text)]">
              ← Agents
            </a>
          )}
          <h1 className="text-lg font-bold tracking-tight">
            {agentParam ? agentName : <>Voice <span className="text-[var(--color-primary)]">AI</span></>}
          </h1>
          <span className="text-xs text-[var(--color-text-dim)] hidden sm:inline">
            {agentParam ? "Test Playground" : "Realtime AI Voice Agent"}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <ConnectionStatus state={connectionState} />
          {isActive && (
            <div className="flex gap-3 text-[10px] text-[var(--color-text-dim)] font-mono">
              <span>STT Browser</span>
              <span>LLM {latency?.llm_first_token_ms ?? "—"}ms</span>
              <span>E2E {latency?.total_pipeline_ms ?? "—"}ms</span>
            </div>
          )}
        </div>
      </header>

      {/* Main Content — Video Call Layout */}
      <div className="flex-1 flex flex-col lg:flex-row gap-4 p-4 overflow-hidden">
        {/* Left: Video Feeds */}
        <div className="flex-1 flex flex-col gap-4 min-w-0">
          {/* Video Grid */}
          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 min-h-0">
            {/* AI Avatar — video-call style frame */}
            <div className="relative rounded-2xl bg-gradient-to-b from-[#141420] to-[#0c0c14] overflow-hidden flex items-center justify-center">
              {/* Recording-style indicator */}
              <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
                <span className={`flex h-2 w-2 rounded-full ${isActive ? "bg-red-500 animate-pulse" : "bg-white/20"}`} />
                <span className="text-xs font-medium text-white/60 backdrop-blur-sm">
                  {agentName}
                </span>
              </div>
              {/* Subtle ambient light overlay */}
              <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/[0.015] to-transparent pointer-events-none" />
              <AIAvatar state={avatarState} amplitude={amplitude} faceTracking={faceTracking} className="w-full h-full p-3" />
            </div>

            {/* User Webcam */}
            <WebcamFeed ref={webcamRef} isActive={isActive} className="min-h-[200px] md:min-h-0" />
          </div>

          {/* Controls Bar */}
          <div className="flex items-center justify-center gap-4 py-3">
            <VoiceButton onToggle={handleToggle} />

            {!isSpeechSupported && (
              <p className="text-xs text-amber-400 max-w-[200px]">
                Speech recognition not supported in this browser. Use Chrome or Edge.
              </p>
            )}
            {sttError && (
              <p className="text-xs text-red-400 max-w-[200px]">{sttError}</p>
            )}
          </div>
        </div>

        {/* Right: Chat Transcript */}
        <div className="w-full lg:w-[380px] flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
          {/* Chat Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="text-sm font-medium text-[var(--color-text-muted)]">
              Conversation
            </h2>
            {transcript.length > 0 && (
              <span className="text-[10px] text-[var(--color-text-dim)]">
                {transcript.filter((t) => t.isFinal).length} messages
              </span>
            )}
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <div className="text-4xl">🎙️</div>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Click the mic to start chatting with {agentName}
                </p>
                <p className="text-xs text-[var(--color-text-dim)]">
                  Ask anything — she&apos;s got jokes!
                </p>
              </div>
            ) : (
              transcript.map((entry) => (
                <div
                  key={entry.id}
                  className={`flex ${entry.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                      entry.role === "user"
                        ? "bg-[var(--color-primary)]/20 text-[var(--color-text)] rounded-br-sm"
                        : "bg-[var(--color-surface-hover)] text-[var(--color-text)] rounded-bl-sm"
                    } ${!entry.isFinal ? "opacity-50" : ""}`}
                  >
                    <span className="block text-[9px] uppercase tracking-wider text-[var(--color-text-dim)] mb-0.5">
                      {entry.role === "user" ? "You" : agentName}
                    </span>
                    {entry.content}
                  </div>
                </div>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>

          {/* Chat Footer — status */}
          <div className="px-4 py-2 border-t border-[var(--color-border)] text-[10px] text-[var(--color-text-dim)] flex items-center gap-2">
            {voiceState === "listening" && (
              <>
                <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Listening...
              </>
            )}
            {voiceState === "processing" && (
              <>
                <span className="flex h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                Thinking...
              </>
            )}
            {voiceState === "speaking" && (
              <>
                <span className="flex h-1.5 w-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" />
                Speaking...
              </>
            )}
            {voiceState === "idle" && <span>Ready to chat</span>}
          </div>
        </div>
      </div>
    </main>
  );
}
