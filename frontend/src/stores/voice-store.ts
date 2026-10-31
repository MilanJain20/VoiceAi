/**
 * Voice session store — global state for the voice UI.
 *
 * Uses Zustand for lightweight, performant state management.
 * All WebSocket events update this store, and React components
 * subscribe to the slices they need.
 */

import { create } from "zustand";
import { WebSocketClient } from "@/lib/websocket-client";
import { audioPlayer } from "@/lib/audio-player";
import { getWsUrl } from "@/lib/utils";
import type {
  ConnectionState,
  LatencyMetrics,
  TranscriptEntry,
  VoiceState,
  WSMessage,
} from "@/types/voice";

interface VoiceStore {
  // State
  connectionState: ConnectionState;
  voiceState: VoiceState;
  sessionId: string | null;
  agentId: string | null;
  transcript: TranscriptEntry[];
  latency: LatencyMetrics | null;
  amplitude: number;
  bytesSent: number;
  audioChunkCount: number;

  // WebSocket client (not serialized)
  _wsClient: WebSocketClient | null;

  // Actions
  connect: () => void;
  disconnect: () => void;
  setAgentId: (id: string | null) => void;
  startListening: () => void;
  stopListening: () => void;
  sendInterrupt: () => void;
  sendAudioChunk: (pcm16: ArrayBuffer) => void;
  sendUserTranscript: (text: string) => void;
  setAmplitude: (amplitude: number) => void;

  // Internal actions (called by WS event handlers)
  _handleMessage: (message: WSMessage) => void;
  _handleBinary: (data: ArrayBuffer) => void;
}

export const useVoiceStore = create<VoiceStore>((set, get) => {
  // ── Wire AudioPlayer callbacks for avatar-sync ──────────────
  // "speaking" only when audio actually starts playing
  audioPlayer.onPlaybackStart = () => {
    const s = get().voiceState;
    if (s === "processing" || s === "listening") {
      set({ voiceState: "speaking" });
    }
  };
  // "listening" only when all audio finishes playing
  audioPlayer.onPlaybackEnd = () => {
    if (get().voiceState === "speaking") {
      set({ voiceState: "listening" });
    }
  };

  return {
  // Initial state
  connectionState: "disconnected",
  voiceState: "idle",
  sessionId: null,
  agentId: null,
  transcript: [],
  latency: null,
  amplitude: 0,
  bytesSent: 0,
  audioChunkCount: 0,
  _wsClient: null,

  connect: () => {
    const existing = get()._wsClient;
    if (existing?.isConnected) return;

    // Clean up any existing client that may be reconnecting
    if (existing) {
      existing.disconnect();
    }

    const client = new WebSocketClient({
      url: getWsUrl(),
      onMessage: (msg) => get()._handleMessage(msg),
      onBinary: (data) => get()._handleBinary(data),
      onStateChange: (state) => {
        const prevState = get().connectionState;
        set({
          connectionState: state as ConnectionState,
          voiceState: state === "disconnected" ? "idle" : get().voiceState,
        });

        // When WS opens, send start_session if we're in listening mode
        if (state === "connected" && get().voiceState === "listening") {
          get()._wsClient?.sendJSON({
            type: "start_session",
            session_id: get().sessionId || "",
            data: { stt_mode: "browser", agent_id: get().agentId || "default" },
          });
        }
      },
      reconnect: true,
    });

    client.connect();
    set({ _wsClient: client });
  },

  disconnect: () => {
    const client = get()._wsClient;
    if (client) {
      client.disconnect();
      set({
        _wsClient: null,
        connectionState: "disconnected",
        voiceState: "idle",
        sessionId: null,
      });
    }
  },

  setAgentId: (id: string | null) => {
    set({ agentId: id });
  },

  startListening: () => {
    const { connectionState, _wsClient } = get();

    // Auto-connect if not connected
    if (connectionState !== "connected") {
      get().connect();
    }

    set({ voiceState: "listening" });

    // Session is auto-created on the backend when the first user_transcript arrives.
    // If the WS is already open, send start_session for immediate initialization.
    if (_wsClient?.isConnected) {
      _wsClient.sendJSON({
        type: "start_session",
        session_id: get().sessionId || "",
        data: { stt_mode: "browser", agent_id: get().agentId || "default" },
      });
    }
  },

  stopListening: () => {
    const { _wsClient, sessionId } = get();
    set({ voiceState: "idle", amplitude: 0 });

    _wsClient?.sendJSON({
      type: "end_session",
      session_id: sessionId || "",
      data: {},
    });
  },

  sendInterrupt: () => {
    const { _wsClient, sessionId } = get();
    audioPlayer.stop();
    _wsClient?.sendJSON({
      type: "interrupt",
      session_id: sessionId || "",
      data: {},
    });
    set({ voiceState: "listening" });
  },

  sendAudioChunk: (pcm16: ArrayBuffer) => {
    const { _wsClient, connectionState, voiceState } = get();
    if (connectionState !== "connected" || voiceState !== "listening") return;

    _wsClient?.sendAudio(pcm16);
    set((state) => ({
      bytesSent: state.bytesSent + pcm16.byteLength,
      audioChunkCount: state.audioChunkCount + 1,
    }));
  },

  sendUserTranscript: (text: string) => {
    const { _wsClient, connectionState } = get();
    if (connectionState !== "connected" || !text.trim()) return;

    // Immediately show user message and switch to processing
    set((state) => {
      const filtered = state.transcript.filter(
        (t) => !(t.role === "user" && !t.isFinal)
      );
      return {
        transcript: [
          ...filtered,
          {
            id: `user-${Date.now()}`,
            role: "user" as const,
            content: text.trim(),
            timestamp: Date.now(),
            isFinal: true,
            confidence: 1.0,
          },
        ],
        voiceState: "processing" as const,
      };
    });

    _wsClient?.sendJSON({
      type: "user_transcript",
      session_id: get().sessionId || "",
      data: { text: text.trim() },
    });
  },

  setAmplitude: (amplitude: number) => {
    set({ amplitude });
  },

  _handleMessage: (message: WSMessage) => {
    switch (message.type) {
      case "session_started":
        set({ sessionId: message.session_id });
        break;

      case "session_ended":
        set({ voiceState: "idle" });
        break;

      case "transcript_partial":
        // Update or add partial transcript
        set((state) => {
          const existing = state.transcript.findIndex(
            (t) => t.role === "user" && !t.isFinal
          );
          const entry: TranscriptEntry = {
            id: `user-partial-${Date.now()}`,
            role: "user",
            content: (message.data.text as string) || "",
            timestamp: Date.now(),
            isFinal: false,
            confidence: message.data.confidence as number,
          };
          if (existing >= 0) {
            const updated = [...state.transcript];
            updated[existing] = entry;
            return { transcript: updated };
          }
          return { transcript: [...state.transcript, entry] };
        });
        break;

      case "transcript_final":
        set((state) => {
          const text = (message.data.text as string) || "";
          // Skip if we already added this message (browser STT adds it immediately)
          const alreadyExists = state.transcript.some(
            (t) => t.role === "user" && t.isFinal && t.content === text
          );
          if (alreadyExists) {
            // Just ensure we're in processing state
            return { voiceState: "processing" };
          }
          // Replace partial with final
          const filtered = state.transcript.filter(
            (t) => !(t.role === "user" && !t.isFinal)
          );
          return {
            transcript: [
              ...filtered,
              {
                id: `user-${Date.now()}`,
                role: "user",
                content: text,
                timestamp: Date.now(),
                isFinal: true,
                confidence: message.data.confidence as number,
              },
            ],
            voiceState: "processing",
          };
        });
        break;

      case "ai_response_start":
        // Don't switch to "speaking" yet — wait for actual audio playback.
        // Prepare the audio player for a new round so the first chunk
        // triggers the onPlaybackStart callback.
        audioPlayer.resetRound();
        break;

      case "ai_response_chunk":
        set((state) => {
          const lastEntry = state.transcript[state.transcript.length - 1];
          if (lastEntry?.role === "assistant" && !lastEntry.isFinal) {
            const updated = [...state.transcript];
            updated[updated.length - 1] = {
              ...lastEntry,
              content: lastEntry.content + ((message.data.text as string) || ""),
            };
            return { transcript: updated };
          }
          return {
            transcript: [
              ...state.transcript,
              {
                id: `assistant-${Date.now()}`,
                role: "assistant",
                content: (message.data.text as string) || "",
                timestamp: Date.now(),
                isFinal: false,
              },
            ],
          };
        });
        break;

      case "ai_response_end":
        // Mark transcript as final, but do NOT switch voiceState yet.
        // The avatar stays in "speaking" until the AudioPlayer actually
        // finishes playing all queued audio chunks.
        set((state) => {
          const updated = [...state.transcript];
          const lastEntry = updated[updated.length - 1];
          if (lastEntry?.role === "assistant") {
            updated[updated.length - 1] = { ...lastEntry, isFinal: true };
          }
          return { transcript: updated };
        });
        break;

      case "latency_report":
        set({ latency: message.data as unknown as LatencyMetrics });
        break;

      case "error":
        console.error("[Voice] Server error:", message.data);
        break;

      default:
        break;
    }
  },

  _handleBinary: (data: ArrayBuffer) => {
    // TTS audio from server — enqueue for playback
    if (data.byteLength > 0) {
      audioPlayer.enqueue(data);
    }
  },
}; });
