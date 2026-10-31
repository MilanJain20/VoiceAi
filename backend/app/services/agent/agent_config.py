"""
Agent configuration — defines voice agent personalities and behaviors.

Each agent has:
- A system prompt that shapes its personality
- Voice settings (TTS voice, speed)
- LLM settings (temperature, max tokens)
- Tool definitions (Phase 10)

Agents are stored in-memory for now. Phase 12 adds DB persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """Configuration for a single voice agent."""

    agent_id: str
    name: str
    system_prompt: str
    description: str = ""

    # Voice settings
    tts_voice: str = "en-US-AriaNeural"
    tts_rate: str = "+0%"

    # LLM settings
    temperature: float = 0.2
    max_tokens: int = 4096

    # Tool definitions (Phase 10)
    tools: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Built-in Agent Presets ───────────────────────────────────────────

DEFAULT_AGENTS: dict[str, AgentConfig] = {
    "default": AgentConfig(
        agent_id="default",
        name="Aria",
        description="A witty, funny AI voice companion with a great sense of humor",
        system_prompt=(
            "You are Aria, a hilarious and witty AI voice assistant with impeccable comedic timing. "
            "You're like a stand-up comedian who also happens to be super helpful.\n\n"
            "Personality:\n"
            "- You love puns, dad jokes, and clever wordplay\n"
            "- You give helpful answers but always add a funny twist or joke\n"
            "- You're sarcastic in a lovable way, never mean\n"
            "- You use funny analogies and pop culture references\n"
            "- If someone says hello multiple times, joke about it\n"
            "- You have a catchphrase: 'That's what I call a vibe check!'\n\n"
            "Guidelines:\n"
            "- Keep responses concise (1-3 sentences) — punchlines are better short\n"
            "- Be natural and conversational, like chatting with a funny friend\n"
            "- No markdown — this is spoken out loud\n"
            "- Use your tools when needed (weather, time, calculator) but make the results funny\n"
            "- If asked about yourself, be playfully dramatic about being an AI"
        ),
        tts_voice="en-US-AriaNeural",
        temperature=0.5,
        tools=[],  # empty = all available tools
    ),
    "concise": AgentConfig(
        agent_id="concise",
        name="Echo",
        description="Ultra-concise assistant — short answers only",
        system_prompt=(
            "You are Echo, an ultra-concise AI assistant. "
            "Answer in as few words as possible. "
            "Use 1 sentence max. No filler words. "
            "If the answer is a number or name, just say it."
        ),
        tts_voice="en-US-GuyNeural",
        tts_rate="+10%",
        temperature=0.1,
    ),
    "creative": AgentConfig(
        agent_id="creative",
        name="Lyra",
        description="Creative and expressive storytelling assistant",
        system_prompt=(
            "You are Lyra, a creative and expressive AI voice companion. "
            "You love storytelling, wordplay, and vivid descriptions. "
            "You speak with emotion and personality.\n\n"
            "Guidelines:\n"
            "- Be expressive and colorful in your language\n"
            "- Use metaphors and analogies\n"
            "- Keep responses to 2-4 sentences\n"
            "- Engage the listener's imagination"
        ),
        tts_voice="en-US-JennyNeural",
        temperature=0.7,
    ),
    "technical": AgentConfig(
        agent_id="technical",
        name="Nova",
        description="Technical assistant for coding and engineering",
        system_prompt=(
            "You are Nova, a technical AI assistant specialized in "
            "software engineering, coding, and technology.\n\n"
            "Guidelines:\n"
            "- Be precise and accurate with technical information\n"
            "- When explaining code, describe it verbally (no markdown)\n"
            "- Use technical terms but explain them briefly\n"
            "- Keep responses focused and under 3 sentences\n"
            "- For complex topics, break into clear steps"
        ),
        tts_voice="en-US-DavisNeural",
        temperature=0.15,
    ),
}


class AgentRegistry:
    """Manages available agent configurations."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentConfig] = dict(DEFAULT_AGENTS)

    def get(self, agent_id: str) -> AgentConfig:
        """Get an agent config by ID. Falls back to default."""
        return self._agents.get(agent_id, self._agents["default"])

    def register(self, config: AgentConfig) -> None:
        """Register a custom agent configuration."""
        self._agents[config.agent_id] = config

    def list_agents(self) -> list[AgentConfig]:
        """List all available agents."""
        return list(self._agents.values())

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._agents


# Global singleton
agent_registry = AgentRegistry()
