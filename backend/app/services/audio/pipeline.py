"""
Audio pipeline — realtime audio processing: STT → LLM → TTS.

This is the central orchestration layer that:
1. Receives PCM16 audio chunks from WebSocket
2. Streams them to Deepgram STT for live transcription
3. On final transcript, sends to Azure OpenAI for response
4. Streams LLM response text to edge-tts for synthesis
5. Sends TTS audio back through the WebSocket as binary frames

Each voice session has independent STT/LLM/TTS state.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from app.core.logging import get_logger
from app.services.agent.agent_config import AgentConfig, agent_registry
from app.services.llm.chat_service import llm_service
from app.services.stt.deepgram_stt import DeepgramSTTSession
from app.services.tools import tool_registry
from app.services.tts.edge_tts_service import tts_service
from app.websocket.events import (
    ai_response_chunk,
    ai_response_end,
    ai_response_start,
    latency_report,
    tool_call_result,
    tool_call_start,
    transcript_final,
    transcript_partial,
    vad_event,
)

if TYPE_CHECKING:
    from app.websocket.connection import VoiceConnection
    from app.services.conversation_service import ConversationService

logger = get_logger(__name__)

DEFAULT_SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


@dataclass
class AudioSessionState:
    """Per-session audio bookkeeping and pipeline handles."""

    session_id: str
    sample_rate: int = DEFAULT_SAMPLE_RATE
    started_at: float = field(default_factory=time.time)
    total_bytes: int = 0
    total_chunks: int = 0

    # Pipeline handles
    stt_session: DeepgramSTTSession | None = None
    _current_llm_task: asyncio.Task | None = None
    _is_speaking: bool = False  # True while TTS is streaming back audio

    # Per-agent TTS overrides (loaded from DB or registry)
    tts_voice: str | None = None
    tts_rate: str | None = None
    tts_volume: str | None = None
    tts_pitch: str | None = None
    agent_id_resolved: str = "default"

    @property
    def uptime_s(self) -> float:
        return time.time() - self.started_at


class AudioPipeline:
    """
    Orchestrates the full voice pipeline per session.

    Audio chunks → Deepgram STT → transcript → Azure OpenAI LLM → edge-tts → WebSocket audio
    """

    def __init__(self) -> None:
        self._sessions: dict[str, AudioSessionState] = {}
        self._conversation_service: "ConversationService | None" = None
        self._db_manager: Any = None  # DatabaseManager, set at startup

    def set_db_manager(self, db_manager: Any) -> None:
        """Set the DatabaseManager (called during app startup)."""
        self._db_manager = db_manager

    def set_conversation_service(self, service: "ConversationService") -> None:
        """Set the conversation service (called during app startup)."""
        self._conversation_service = service

    async def _resolve_agent(self, agent_id: str) -> AgentConfig:
        """
        Resolve agent config — checks DB first, falls back to in-memory registry.

        If agent_id is a UUID or slug that exists in the `agents` table,
        we build an AgentConfig from the DB row. Otherwise we use the
        built-in presets (default, concise, creative, technical).
        """
        if self._db_manager:
            try:
                from sqlalchemy import select as sa_select
                from app.models.agent import Agent as AgentModel

                async for session in self._db_manager.get_session():
                    # Try UUID lookup
                    stmt = None
                    try:
                        import uuid as _uuid
                        _uuid.UUID(agent_id)
                        stmt = sa_select(AgentModel).where(AgentModel.id == agent_id)
                    except (ValueError, AttributeError):
                        # Not a UUID — try slug
                        stmt = sa_select(AgentModel).where(AgentModel.slug == agent_id)

                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        tools_cfg = row.tools_config or {}
                        enabled = tools_cfg.get("enabled_tools", [])
                        return AgentConfig(
                            agent_id=str(row.id),
                            name=row.name,
                            description=row.description or "",
                            system_prompt=row.system_prompt,
                            tts_voice=row.tts_voice,
                            tts_rate=row.tts_rate,
                            temperature=row.temperature,
                            max_tokens=row.max_tokens,
                            tools=enabled if enabled else [],
                            metadata={
                                "tts_volume": row.tts_volume,
                                "tts_pitch": row.tts_pitch,
                                "language": row.language,
                            },
                        )
                    break  # only one iteration
            except Exception as e:
                logger.warning("pipeline_db_agent_resolve_error", error=str(e))

        # Fallback to in-memory registry
        return agent_registry.get(agent_id)

    async def handle_session_start(
        self, connection: "VoiceConnection", config: dict
    ) -> None:
        """Initialize all pipeline components for a new voice session."""
        session_id = connection.session_id
        sample_rate = config.get("sample_rate", DEFAULT_SAMPLE_RATE)
        agent_id = config.get("agent_id", "default")
        stt_mode = config.get("stt_mode", "browser")  # "browser" or "deepgram"

        # Don't re-initialize if session already exists
        if session_id in self._sessions:
            return

        # Load agent configuration — try DB first, fall back to registry
        agent = await self._resolve_agent(agent_id)

        state = AudioSessionState(
            session_id=session_id,
            sample_rate=sample_rate,
            tts_voice=agent.tts_voice,
            tts_rate=agent.tts_rate,
            tts_volume=agent.metadata.get("tts_volume") if agent.metadata else None,
            tts_pitch=agent.metadata.get("tts_pitch") if agent.metadata else None,
            agent_id_resolved=agent.agent_id,
        )

        # Only start Deepgram STT if explicitly requested (not in browser STT mode)
        if stt_mode == "deepgram":
            try:
                state.stt_session = DeepgramSTTSession(
                    session_id=session_id,
                    on_transcript_partial=lambda text, conf: self._on_transcript_partial(
                        connection, text, conf
                    ),
                    on_transcript_final=lambda text, conf, speech_final: self._on_transcript_final(
                        connection, text, conf, speech_final
                    ),
                )
                await state.stt_session.start()
            except Exception as e:
                logger.warning(
                    "pipeline_deepgram_start_failed",
                    session_id=session_id,
                    error=str(e),
                )
                state.stt_session = None
        else:
            logger.info(
                "pipeline_browser_stt_mode",
                session_id=session_id,
            )

        # Resolve agent tools → OpenAI function specs
        agent_tool_names = agent.tools if agent.tools else None  # None = all tools
        openai_tools = tool_registry.get_openai_functions(agent_tool_names)

        # Create LLM session with agent's system prompt and tools
        llm_service.create_session(
            session_id,
            system_prompt=agent.system_prompt,
            tools=openai_tools if openai_tools else None,
        )

        self._sessions[session_id] = state
        logger.info(
            "pipeline_session_started",
            session_id=session_id,
            sample_rate=sample_rate,
            stt_mode=stt_mode,
            agent_id=agent.agent_id,
            agent_name=agent.name,
        )

        # Persist conversation to DB
        if self._conversation_service:
            try:
                await self._conversation_service.create_conversation(session_id)
            except Exception as e:
                logger.warning("pipeline_db_create_error", error=str(e))

    async def handle_session_end(self, connection: "VoiceConnection") -> None:
        """Shut down all pipeline components for a session."""
        await self.destroy_session(connection.session_id)

    async def destroy_session(self, session_id: str) -> None:
        """Clean up everything for a session."""
        state = self._sessions.pop(session_id, None)
        if not state:
            return

        # Cancel any in-flight LLM task
        if state._current_llm_task and not state._current_llm_task.done():
            state._current_llm_task.cancel()

        # Stop STT
        if state.stt_session:
            await state.stt_session.stop()

        # Destroy LLM session
        llm_service.destroy_session(session_id)

        # Mark conversation as completed in DB
        if self._conversation_service:
            try:
                duration_ms = int(state.uptime_s * 1000) if state else 0
                await self._conversation_service.end_conversation(session_id, duration_ms)
            except Exception as e:
                logger.warning("pipeline_db_end_error", error=str(e))

        logger.info(
            "pipeline_session_destroyed",
            session_id=session_id,
            total_bytes=state.total_bytes,
            total_chunks=state.total_chunks,
            uptime_s=round(state.uptime_s, 2),
        )

    async def process_chunk(
        self, connection: "VoiceConnection", audio_data: bytes
    ) -> None:
        """Forward audio chunk to STT."""
        session_id = connection.session_id
        state = self._sessions.get(session_id)

        if state is None:
            # Auto-start session if needed
            await self.handle_session_start(connection, {})
            state = self._sessions.get(session_id)
            if not state:
                return

        state.total_bytes += len(audio_data)
        state.total_chunks += 1

        # Forward to Deepgram STT
        if state.stt_session:
            await state.stt_session.send_audio(audio_data)

        # Log periodically
        if state.total_chunks % 100 == 0:
            logger.debug(
                "pipeline_stats",
                session_id=session_id,
                total_chunks=state.total_chunks,
                total_bytes=state.total_bytes,
            )

    async def handle_interrupt(self, connection: "VoiceConnection") -> None:
        """Handle user interruption — cancel LLM/TTS, keep STT running."""
        state = self._sessions.get(connection.session_id)
        if not state:
            return

        # Cancel in-flight LLM generation
        if state._current_llm_task and not state._current_llm_task.done():
            state._current_llm_task.cancel()
            state._current_llm_task = None

        state._is_speaking = False
        logger.info("pipeline_interrupted", session_id=connection.session_id)

    # ── Browser STT (Web Speech API) ─────────────────────────────────

    async def handle_user_transcript(
        self, connection: "VoiceConnection", text: str
    ) -> None:
        """
        Handle a final transcript sent from the browser's Web Speech API.

        Bypasses Deepgram entirely — the browser did STT locally.
        We send the transcript events to the client, then kick off LLM → TTS.
        """
        session_id = connection.session_id
        state = self._sessions.get(session_id)

        if state is None:
            # Auto-start session in browser STT mode (no Deepgram needed)
            await self.handle_session_start(connection, {"stt_mode": "browser"})
            state = self._sessions.get(session_id)
            if not state:
                return

        # Send transcript_final to the client for display
        await connection.send_message(
            transcript_final(session_id, text, confidence=1.0, speech_final=True)
        )

        # Cancel any existing LLM task
        if state._current_llm_task and not state._current_llm_task.done():
            state._current_llm_task.cancel()

        # Start LLM → TTS pipeline
        state._current_llm_task = asyncio.create_task(
            self._run_llm_tts_pipeline(connection, text)
        )
        logger.info(
            "pipeline_browser_stt_trigger",
            session_id=session_id,
            text=text[:80],
        )

    # ── STT Callbacks ────────────────────────────────────────────────

    async def _on_transcript_partial(
        self, connection: "VoiceConnection", text: str, confidence: float
    ) -> None:
        """Send partial transcript to the client."""
        if not connection.is_connected:
            return
        await connection.send_message(
            transcript_partial(connection.session_id, text, confidence)
        )

    async def _on_transcript_final(
        self, connection: "VoiceConnection", text: str, confidence: float, speech_final: bool
    ) -> None:
        """Handle final transcript — send to client and kick off LLM if speech is final."""
        if not connection.is_connected:
            return

        await connection.send_message(
            transcript_final(connection.session_id, text, confidence, speech_final)
        )

        # Only trigger LLM when Deepgram says the user is done speaking
        if speech_final and text.strip():
            state = self._sessions.get(connection.session_id)
            if state:
                # Cancel any existing LLM task
                if state._current_llm_task and not state._current_llm_task.done():
                    state._current_llm_task.cancel()

                # Start LLM → TTS pipeline in background
                state._current_llm_task = asyncio.create_task(
                    self._run_llm_tts_pipeline(connection, text)
                )

    # ── LLM → TTS Pipeline ──────────────────────────────────────────

    async def _run_llm_tts_pipeline(
        self, connection: "VoiceConnection", user_text: str
    ) -> None:
        """
        Run the full LLM → TTS pipeline:
        1. Stream LLM response
        2. Accumulate into sentences
        3. Synthesize each sentence via TTS
        4. Stream audio back to client
        """
        session_id = connection.session_id
        state = self._sessions.get(session_id)
        if not state:
            return

        pipeline_start = time.time()
        llm_first_token_time = 0.0
        tts_first_byte_time = 0.0
        full_response = ""
        token_count = 0

        try:
            # Signal AI response starting
            await connection.send_message(ai_response_start(session_id))
            state._is_speaking = True

            # Persist user message
            if self._conversation_service:
                try:
                    from app.models.conversation import MessageRole
                    await self._conversation_service.add_message(
                        session_id=session_id,
                        role=MessageRole.USER,
                        content=user_text,
                    )
                except Exception as e:
                    logger.warning("pipeline_db_user_msg_error", error=str(e))

            # Stream LLM response, accumulate sentences for TTS
            sentence_buffer = ""

            async for text_chunk in llm_service.generate_response(
                session_id, user_text, tool_executor=self._make_tool_executor(connection)
            ):
                if connection.is_cancelled or not connection.is_connected:
                    break

                if token_count == 0:
                    llm_first_token_time = time.time() - pipeline_start

                token_count += 1
                full_response += text_chunk
                sentence_buffer += text_chunk

                # Send text chunk to client for display
                await connection.send_message(
                    ai_response_chunk(session_id, text_chunk)
                )

                # Check if we have a complete sentence to synthesize
                sentence, remainder = self._split_sentence(sentence_buffer)
                if sentence:
                    sentence_buffer = remainder
                    # Synthesize and stream audio
                    audio_sent = await self._synthesize_and_send(
                        connection, sentence, state
                    )
                    if audio_sent and tts_first_byte_time == 0.0:
                        tts_first_byte_time = time.time() - pipeline_start

            # Synthesize any remaining text
            if sentence_buffer.strip() and not connection.is_cancelled:
                await self._synthesize_and_send(connection, sentence_buffer.strip(), state)
                if tts_first_byte_time == 0.0:
                    tts_first_byte_time = time.time() - pipeline_start

            # Signal AI response complete
            if connection.is_connected and not connection.is_cancelled:
                await connection.send_message(
                    ai_response_end(session_id, full_response, token_count)
                )

                # Send latency report
                total_time = time.time() - pipeline_start
                await connection.send_message(
                    latency_report(
                        session_id,
                        stt_ms=0,
                        llm_first_token_ms=round(llm_first_token_time * 1000, 1),
                        llm_total_ms=round((time.time() - pipeline_start) * 1000, 1),
                        tts_first_byte_ms=round(tts_first_byte_time * 1000, 1),
                        total_pipeline_ms=round(total_time * 1000, 1),
                    )
                )

                # Persist assistant message
                if self._conversation_service and full_response:
                    try:
                        from app.models.conversation import MessageRole
                        await self._conversation_service.add_message(
                            session_id=session_id,
                            role=MessageRole.ASSISTANT,
                            content=full_response,
                            token_count=token_count,
                            latency_ms=int(total_time * 1000),
                        )
                    except Exception as e:
                        logger.warning("pipeline_db_assistant_msg_error", error=str(e))

        except asyncio.CancelledError:
            logger.info("pipeline_llm_tts_cancelled", session_id=session_id)
        except Exception as e:
            logger.error(
                "pipeline_llm_tts_error",
                session_id=session_id,
                error=str(e),
            )
        finally:
            state._is_speaking = False
            if connection.is_connected:
                connection.reset_cancel()

    # ── Tool Execution ─────────────────────────────────────────────

    def _make_tool_executor(
        self, connection: "VoiceConnection"
    ) -> Callable[..., Awaitable[str]]:
        """Create a tool executor callback bound to the current connection."""
        async def executor(tool_name: str, tool_args: dict) -> str:
            return await self._execute_tool(connection, tool_name, tool_args)
        return executor

    async def _execute_tool(
        self, connection: "VoiceConnection", tool_name: str, tool_args: dict
    ) -> str:
        """Execute a tool and notify the client."""
        from app.services.tools import tool_registry as tr

        # Notify client that a tool call is starting
        await connection.send_message(
            tool_call_start(connection.session_id, tool_name, tool_args)
        )

        tool = tr.get(tool_name)
        if tool is None:
            result_str = f"Tool '{tool_name}' not found."
            await connection.send_message(
                tool_call_result(connection.session_id, tool_name, result_str, success=False)
            )
            return result_str

        try:
            result = await tool.execute(**tool_args)
            await connection.send_message(
                tool_call_result(
                    connection.session_id, tool_name, result.to_dict(), success=result.success
                )
            )
            logger.info(
                "pipeline_tool_executed",
                session_id=connection.session_id,
                tool=tool_name,
                success=result.success,
            )
            return result.output
        except Exception as e:
            error_str = f"Tool '{tool_name}' error: {e}"
            logger.error(
                "pipeline_tool_error",
                session_id=connection.session_id,
                tool=tool_name,
                error=str(e),
            )
            await connection.send_message(
                tool_call_result(connection.session_id, tool_name, error_str, success=False)
            )
            return error_str

    # ── TTS Synthesis ────────────────────────────────────────────────

    async def _synthesize_and_send(
        self, connection: "VoiceConnection", text: str, state: AudioSessionState
    ) -> bool:
        """Synthesize text to speech and send audio chunks over WebSocket."""
        if not text.strip():
            return False

        sent_any = False
        try:
            async for audio_chunk in tts_service.synthesize_stream(
                text,
                voice=state.tts_voice,
                rate=state.tts_rate,
                volume=state.tts_volume,
                pitch=state.tts_pitch,
            ):
                if connection.is_cancelled or not connection.is_connected:
                    break
                await connection.send_audio(audio_chunk)
                sent_any = True
        except Exception as e:
            logger.error(
                "pipeline_tts_send_error",
                session_id=connection.session_id,
                error=str(e),
            )
        return sent_any

    @staticmethod
    def _split_sentence(text: str) -> tuple[str, str]:
        """
        Split text at sentence boundaries for incremental TTS.
        Returns (complete_sentence, remainder).

        Requires at least 40 chars before splitting so that very short
        fragments aren't synthesized separately (which sounds choppy).
        """
        # Only split if we have enough text for clear speech
        MIN_LEN = 40
        for i, char in enumerate(text):
            if char in ".!?" and i >= MIN_LEN - 1 and i < len(text) - 1 and text[i + 1] == " ":
                return text[: i + 1].strip(), text[i + 2 :]
        if len(text) > MIN_LEN and "\n" in text:
            idx = text.index("\n")
            if idx >= MIN_LEN:
                return text[:idx].strip(), text[idx + 1 :]
        return "", text

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)


# ── Global singleton ─────────────────────────────────────────────────

audio_pipeline = AudioPipeline()
