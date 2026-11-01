"""
WebSocket message schemas.

Defines the typed protocol for all WebSocket communication.
Every message has a `type` discriminator field for routing.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WSMessageType(str, Enum):
    # Client → Server
    AUDIO_CHUNK = "audio_chunk"
    START_SESSION = "start_session"
    END_SESSION = "end_session"
    INTERRUPT = "interrupt"
    CONFIG_UPDATE = "config_update"
    PING = "ping"
    USER_TRANSCRIPT = "user_transcript"  # Browser STT text (Web Speech API)

    # Server → Client
    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    AI_RESPONSE_START = "ai_response_start"
    AI_RESPONSE_CHUNK = "ai_response_chunk"
    AI_RESPONSE_END = "ai_response_end"
    AUDIO_RESPONSE = "audio_response"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    ERROR = "error"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    PONG = "pong"
    VAD_EVENT = "vad_event"
    LATENCY_REPORT = "latency_report"
    AUDIO_SENTENCE_START = "audio_sentence_start"
    AUDIO_SENTENCE_END = "audio_sentence_end"


class WSMessage(BaseModel):
    """Base WebSocket message — all messages conform to this shape."""

    type: WSMessageType
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    data: dict[str, Any] = Field(default_factory=dict)


class StartSessionData(BaseModel):
    agent_id: str | None = None
    audio_config: AudioConfig = Field(default_factory=lambda: AudioConfig())
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudioConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "linear16"  # linear16 | opus | mp3
    chunk_duration_ms: int = 100


class TranscriptData(BaseModel):
    text: str
    confidence: float = 0.0
    is_final: bool = False
    speech_final: bool = False
    start_time: float = 0.0
    duration: float = 0.0


class AIResponseChunkData(BaseModel):
    text: str
    is_final: bool = False
    token_count: int = 0


class ErrorData(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = True


class LatencyReport(BaseModel):
    stt_ms: float = 0.0
    llm_first_token_ms: float = 0.0
    llm_total_ms: float = 0.0
    tts_first_byte_ms: float = 0.0
    total_pipeline_ms: float = 0.0
