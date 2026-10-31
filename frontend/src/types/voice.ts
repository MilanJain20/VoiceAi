/**
 * WebSocket message types — mirrors backend schema.
 */

export type WSMessageType =
  | "ping"
  | "pong"
  | "start_session"
  | "end_session"
  | "session_started"
  | "session_ended"
  | "audio_chunk"
  | "transcript_partial"
  | "transcript_final"
  | "ai_response_start"
  | "ai_response_chunk"
  | "ai_response_end"
  | "interrupt"
  | "config_update"
  | "error"
  | "vad_event"
  | "latency_report"
  | "tool_call_start"
  | "tool_call_result"
  | "user_transcript";

export interface WSMessage {
  type: WSMessageType;
  session_id: string;
  data: Record<string, unknown>;
  timestamp?: string;
}

export type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

export type VoiceState = "idle" | "listening" | "processing" | "speaking";

export interface LatencyMetrics {
  stt_ms: number;
  llm_first_token_ms: number;
  llm_total_ms: number;
  tts_first_byte_ms: number;
  total_pipeline_ms: number;
}

export interface TranscriptEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isFinal: boolean;
  confidence?: number;
}
