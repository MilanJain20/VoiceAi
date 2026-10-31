"""Pydantic schemas for Agent Studio API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Request schemas ──────────────────────────────────────────────────


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    category: str = "general"
    system_prompt: str = ""
    welcome_message: str = "Hello! How can I help you today?"

    # Voice
    tts_voice: str = "en-US-AriaNeural"
    tts_rate: str = "-5%"
    tts_pitch: str = "+0Hz"
    tts_volume: str = "+10%"
    language: str = "en-US"

    # LLM
    llm_model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    top_p: float = 1.0

    # Tools
    tools_config: dict[str, Any] = Field(
        default_factory=lambda: {"enabled_tools": [], "allow_all": True, "custom_tools": []}
    )

    # Memory
    memory_config: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "window",
            "window_size": 20,
            "summarize": False,
            "max_context_tokens": 8000,
        }
    )

    # Workflow
    workflow_config: dict[str, Any] = Field(default_factory=dict)

    is_template: bool = False


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    system_prompt: str | None = None
    welcome_message: str | None = None

    tts_voice: str | None = None
    tts_rate: str | None = None
    tts_pitch: str | None = None
    tts_volume: str | None = None
    language: str | None = None

    llm_model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None

    tools_config: dict[str, Any] | None = None
    memory_config: dict[str, Any] | None = None
    workflow_config: dict[str, Any] | None = None

    # Optional version note (triggers a version snapshot)
    change_note: str | None = None


class AgentDuplicate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


# ── Response schemas ─────────────────────────────────────────────────


class AgentSummary(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    status: str
    tts_voice: str
    language: str
    total_calls: int
    avg_rating: float
    current_version: int
    is_template: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentDetail(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    status: str
    system_prompt: str
    welcome_message: str

    tts_voice: str
    tts_rate: str
    tts_pitch: str
    tts_volume: str
    language: str

    llm_model: str
    temperature: float
    max_tokens: int
    top_p: float

    tools_config: dict[str, Any]
    memory_config: dict[str, Any]
    workflow_config: dict[str, Any]

    total_calls: int
    total_duration_ms: int
    avg_rating: float
    current_version: int
    is_template: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentVersionResponse(BaseModel):
    id: str
    version: int
    change_note: str | None
    created_at: datetime
    config_snapshot: dict[str, Any]

    class Config:
        from_attributes = True


class CallLogResponse(BaseModel):
    id: str
    agent_id: str
    session_id: str
    duration_ms: int
    message_count: int
    total_tokens: int
    avg_latency_ms: int
    status: str
    rating: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentAnalytics(BaseModel):
    total_calls: int
    total_duration_ms: int
    avg_duration_ms: float
    avg_rating: float
    calls_today: int
    calls_this_week: int
    top_intents: list[dict[str, Any]] = []
    latency_p50_ms: float = 0
    latency_p95_ms: float = 0
    recent_calls: list[CallLogResponse] = []


# ── Voice catalog ────────────────────────────────────────────────────


class VoiceOption(BaseModel):
    voice_id: str
    name: str
    language: str
    gender: str
    style: str = ""
    preview_url: str = ""


# ── Available edge-tts voices ────────────────────────────────────────

VOICE_CATALOG: list[VoiceOption] = [
    VoiceOption(
        voice_id="en-US-AriaNeural",
        name="Aria",
        language="en-US",
        gender="Female",
        style="friendly, warm",
    ),
    VoiceOption(
        voice_id="en-US-JennyNeural",
        name="Jenny",
        language="en-US",
        gender="Female",
        style="conversational",
    ),
    VoiceOption(
        voice_id="en-US-GuyNeural",
        name="Guy",
        language="en-US",
        gender="Male",
        style="professional",
    ),
    VoiceOption(
        voice_id="en-US-DavisNeural",
        name="Davis",
        language="en-US",
        gender="Male",
        style="calm, authoritative",
    ),
    VoiceOption(
        voice_id="en-US-JaneNeural",
        name="Jane",
        language="en-US",
        gender="Female",
        style="warm, empathetic",
    ),
    VoiceOption(
        voice_id="en-US-JasonNeural",
        name="Jason",
        language="en-US",
        gender="Male",
        style="energetic",
    ),
    VoiceOption(
        voice_id="en-US-NancyNeural",
        name="Nancy",
        language="en-US",
        gender="Female",
        style="expressive",
    ),
    VoiceOption(
        voice_id="en-US-TonyNeural", name="Tony", language="en-US", gender="Male", style="casual"
    ),
    VoiceOption(
        voice_id="en-US-SaraNeural",
        name="Sara",
        language="en-US",
        gender="Female",
        style="clear, articulate",
    ),
    VoiceOption(
        voice_id="en-GB-SoniaNeural",
        name="Sonia",
        language="en-GB",
        gender="Female",
        style="British, refined",
    ),
    VoiceOption(
        voice_id="en-GB-RyanNeural",
        name="Ryan",
        language="en-GB",
        gender="Male",
        style="British, professional",
    ),
    VoiceOption(
        voice_id="en-AU-NatashaNeural",
        name="Natasha",
        language="en-AU",
        gender="Female",
        style="Australian, friendly",
    ),
    VoiceOption(
        voice_id="en-IN-NeerjaNeural",
        name="Neerja",
        language="en-IN",
        gender="Female",
        style="Indian English",
    ),
    VoiceOption(
        voice_id="en-IN-PrabhatNeural",
        name="Prabhat",
        language="en-IN",
        gender="Male",
        style="Indian English",
    ),
    VoiceOption(
        voice_id="hi-IN-SwaraNeural", name="Swara", language="hi-IN", gender="Female", style="Hindi"
    ),
    VoiceOption(
        voice_id="hi-IN-MadhurNeural", name="Madhur", language="hi-IN", gender="Male", style="Hindi"
    ),
]
