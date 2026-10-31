"""
Audio pipeline — STT, streaming LLM, and TTS that overlap.

LLM tokens are pushed into sentences on a queue. A consumer synthesizes
those sentences and forwards audio frames while the model is still talking.
Barge-in cancels both tasks.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from app.config import get_settings
from app.core.exceptions import LLMError, TTSError
from app.core.logging import get_logger
from app.services.agent.agent_config import AgentConfig, agent_registry
from app.services.audio.framing import pack_audio_frame
from app.services.audio.sentences import split_sentence
from app.services.llm.chat_service import llm_service
from app.services.metrics import percentile
from app.services.stt.deepgram_stt import DeepgramSTTSession
from app.services.tools import tool_registry
from app.services.tools.base import ToolResult
from app.services.tools.policy import ToolPolicy, policy_from_config
from app.services.tts.edge_tts_service import tts_service
from app.services.tts.fake_tts import fake_tts_service
from app.websocket.events import (
    ai_response_chunk,
    ai_response_end,
    ai_response_start,
    audio_sentence_end,
    audio_sentence_start,
    error_message,
    latency_report,
    tool_call_result,
    tool_call_start,
    transcript_final,
    transcript_partial,
    vad_event,
)

if TYPE_CHECKING:
    from app.services.conversation_service import ConversationService
    from app.websocket.connection import VoiceConnection

logger = get_logger(__name__)

DEFAULT_SAMPLE_RATE = 16000


@dataclass
class AudioSessionState:
    session_id: str
    sample_rate: int = DEFAULT_SAMPLE_RATE
    started_at: float = field(default_factory=time.time)
    total_bytes: int = 0
    total_chunks: int = 0
    stt_session: DeepgramSTTSession | None = None
    _current_llm_task: asyncio.Task | None = None
    _is_speaking: bool = False
    turn_cancel: asyncio.Event = field(default_factory=asyncio.Event)
    tts_voice: str | None = None
    tts_rate: str | None = None
    tts_volume: str | None = None
    tts_pitch: str | None = None
    agent_id_resolved: str = "default"
    agent_db_id: str | None = None
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    memory_config: dict = field(default_factory=dict)
    temperature: float = 0.2
    max_tokens: int = 4096
    llm_model: str = ""
    stt_mode: str = "browser"
    turn_latencies: list[float] = field(default_factory=list)
    message_count: int = 0
    total_tokens: int = 0

    @property
    def uptime_s(self) -> float:
        return time.time() - self.started_at


class AudioPipeline:
    def __init__(self) -> None:
        self._sessions: dict[str, AudioSessionState] = {}
        self._conversation_service: ConversationService | None = None
        self._db_manager: Any = None
        self._redis: Any = None

    def set_db_manager(self, db_manager: Any) -> None:
        self._db_manager = db_manager

    def set_conversation_service(self, service: ConversationService) -> None:
        self._conversation_service = service

    def set_redis(self, redis: Any) -> None:
        self._redis = redis

    def _tts(self) -> Any:
        if get_settings().resolved_tts_provider == "fake":
            return fake_tts_service
        return tts_service

    async def _resolve_agent(self, agent_id: str) -> AgentConfig:
        if self._db_manager:
            try:
                from sqlalchemy import select as sa_select

                from app.models.agent import Agent as AgentModel

                async for session in self._db_manager.get_session():
                    try:
                        uuid.UUID(agent_id)
                        stmt = sa_select(AgentModel).where(AgentModel.id == agent_id)
                    except (ValueError, AttributeError):
                        stmt = sa_select(AgentModel).where(AgentModel.slug == agent_id)
                    result = await session.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        tools_cfg = row.tools_config or {}
                        return AgentConfig(
                            agent_id=str(row.id),
                            name=row.name,
                            description=row.description or "",
                            system_prompt=row.system_prompt,
                            tts_voice=row.tts_voice,
                            tts_rate=row.tts_rate,
                            temperature=row.temperature,
                            max_tokens=row.max_tokens,
                            tools=list(tools_cfg.get("enabled_tools") or []),
                            metadata={
                                "tts_volume": row.tts_volume,
                                "tts_pitch": row.tts_pitch,
                                "language": row.language,
                                "llm_model": row.llm_model,
                                "tools_config": tools_cfg,
                                "memory_config": row.memory_config or {},
                            },
                        )
                    break
            except Exception as exc:
                logger.warning("pipeline_db_agent_resolve_error", error=str(exc))
        return agent_registry.get(agent_id)

    async def handle_session_start(self, connection: VoiceConnection, config: dict) -> dict:
        session_id = connection.session_id
        sample_rate = config.get("sample_rate", DEFAULT_SAMPLE_RATE)
        agent_id = config.get("agent_id", "default")
        requested = config.get("stt_mode") or "deepgram"
        settings = get_settings()
        stt_mode = requested
        if requested == "deepgram" and not settings.deepgram_api_key:
            stt_mode = "browser"
            logger.info("pipeline_deepgram_unavailable", session_id=session_id)

        if session_id in self._sessions:
            state = self._sessions[session_id]
            return {
                "sample_rate": state.sample_rate,
                "stt_mode": state.stt_mode,
                "agent_id": state.agent_id_resolved,
            }

        agent = await self._resolve_agent(agent_id)
        policy = policy_from_config(
            agent.metadata.get("tools_config"),
            explicit_names=agent.tools,
            allow_all_flag=bool(agent.metadata.get("allow_all_tools")),
        )
        agent_db_id = None
        try:
            uuid.UUID(agent.agent_id)
            agent_db_id = agent.agent_id
        except (ValueError, AttributeError):
            agent_db_id = None

        state = AudioSessionState(
            session_id=session_id,
            sample_rate=sample_rate,
            tts_voice=agent.tts_voice,
            tts_rate=agent.tts_rate,
            tts_volume=agent.metadata.get("tts_volume"),
            tts_pitch=agent.metadata.get("tts_pitch"),
            agent_id_resolved=agent.agent_id,
            agent_db_id=agent_db_id,
            tool_policy=policy,
            memory_config=agent.metadata.get("memory_config") or {},
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            llm_model=agent.metadata.get("llm_model") or "",
            stt_mode=stt_mode,
        )

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
                    on_speech_started=lambda: self._on_speech_started(connection),
                    on_error=lambda message: self._on_stt_error(connection, message),
                )
                await state.stt_session.start()
            except Exception as exc:
                logger.warning(
                    "pipeline_deepgram_start_failed", session_id=session_id, error=str(exc)
                )
                state.stt_session = None
                state.stt_mode = "browser"
                stt_mode = "browser"

        if tool_registry.count == 0:
            from app.services.tools.builtin import register_builtin_tools

            register_builtin_tools()
        openai_tools = tool_registry.get_openai_functions(policy.names_or_none)
        llm_service.create_session(
            session_id,
            system_prompt=agent.system_prompt,
            tools=openai_tools or None,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            model=state.llm_model or None,
            memory_config=state.memory_config,
        )
        self._sessions[session_id] = state
        logger.info(
            "pipeline_session_started",
            session_id=session_id,
            stt_mode=stt_mode,
            agent_id=agent.agent_id,
            llm_provider=get_settings().resolved_llm_provider,
            tts_provider=get_settings().resolved_tts_provider,
            tool_allow_all=policy.allow_all,
            tool_count=len(openai_tools),
        )
        await self._touch_session_store(state)
        if self._conversation_service:
            try:
                await self._conversation_service.create_conversation(
                    session_id, agent_id=agent.agent_id
                )
                turns = await self._conversation_service.list_turns(session_id)
                if turns:
                    llm_service.load_messages(session_id, turns)
            except Exception as exc:
                logger.warning("pipeline_db_create_error", error=str(exc))
        return {
            "sample_rate": sample_rate,
            "stt_mode": stt_mode,
            "agent_id": agent.agent_id,
            "llm_provider": get_settings().resolved_llm_provider,
            "tts_provider": get_settings().resolved_tts_provider,
        }

    async def handle_session_end(self, connection: VoiceConnection) -> None:
        await self.destroy_session(connection.session_id)

    async def destroy_session(self, session_id: str) -> None:
        state = self._sessions.pop(session_id, None)
        if not state:
            return
        state.turn_cancel.set()
        if state._current_llm_task and not state._current_llm_task.done():
            state._current_llm_task.cancel()
        if state.stt_session:
            await state.stt_session.stop()
        llm_service.destroy_session(session_id)
        await self._finish_call(state)
        if self._conversation_service:
            try:
                await self._conversation_service.end_conversation(
                    session_id, int(state.uptime_s * 1000)
                )
            except Exception as exc:
                logger.warning("pipeline_db_end_error", error=str(exc))
        if self._redis:
            try:
                await self._redis.delete(f"voice:session:{session_id}")
            except Exception as exc:
                logger.warning("pipeline_redis_delete_error", error=str(exc))
        logger.info(
            "pipeline_session_destroyed",
            session_id=session_id,
            turns=len(state.turn_latencies),
            uptime_s=round(state.uptime_s, 2),
        )

    async def process_chunk(self, connection: VoiceConnection, audio_data: bytes) -> None:
        state = self._sessions.get(connection.session_id)
        if state is None:
            await self.handle_session_start(connection, {"stt_mode": "deepgram"})
            state = self._sessions.get(connection.session_id)
            if not state:
                return
        state.total_bytes += len(audio_data)
        state.total_chunks += 1
        if state.stt_session:
            await state.stt_session.send_audio(audio_data)

    async def handle_interrupt(self, connection: VoiceConnection) -> None:
        state = self._sessions.get(connection.session_id)
        if not state:
            return
        state.turn_cancel.set()
        if state._current_llm_task and not state._current_llm_task.done():
            state._current_llm_task.cancel()
            state._current_llm_task = None
        state._is_speaking = False
        await connection.send_message(vad_event(connection.session_id, True, barge_in=True))
        logger.info("pipeline_interrupted", session_id=connection.session_id)

    async def handle_user_transcript(
        self,
        connection: VoiceConnection,
        text: str,
        stt_ms: float = 0,
    ) -> None:
        session_id = connection.session_id
        state = self._sessions.get(session_id)
        if state is None:
            await self.handle_session_start(connection, {"stt_mode": "browser"})
            state = self._sessions.get(session_id)
            if not state:
                return
        await connection.send_message(
            transcript_final(session_id, text, confidence=1.0, speech_final=True)
        )
        if state._current_llm_task and not state._current_llm_task.done():
            state.turn_cancel.set()
            state._current_llm_task.cancel()
        state.turn_cancel = asyncio.Event()
        connection.reset_cancel()
        state._current_llm_task = asyncio.create_task(
            self._run_llm_tts_pipeline(connection, text, stt_ms=stt_ms)
        )
        logger.info("pipeline_browser_stt_trigger", session_id=session_id, text=text[:80])

    async def _on_transcript_partial(
        self, connection: VoiceConnection, text: str, confidence: float
    ) -> None:
        if connection.is_connected:
            await connection.send_message(
                transcript_partial(connection.session_id, text, confidence)
            )

    async def _on_transcript_final(
        self, connection: VoiceConnection, text: str, confidence: float, speech_final: bool
    ) -> None:
        if not connection.is_connected:
            return
        await connection.send_message(
            transcript_final(connection.session_id, text, confidence, speech_final)
        )
        if not (speech_final and text.strip()):
            return
        state = self._sessions.get(connection.session_id)
        if not state:
            return
        stt_ms = 0.0
        if state.stt_session and state.stt_session.last_audio_at:
            stt_ms = max(0.0, (time.time() - state.stt_session.last_audio_at) * 1000)
        if state._current_llm_task and not state._current_llm_task.done():
            state.turn_cancel.set()
            state._current_llm_task.cancel()
        state.turn_cancel = asyncio.Event()
        connection.reset_cancel()
        state._current_llm_task = asyncio.create_task(
            self._run_llm_tts_pipeline(connection, text, stt_ms=stt_ms)
        )

    async def _on_speech_started(self, connection: VoiceConnection) -> None:
        state = self._sessions.get(connection.session_id)
        if not state:
            return
        busy = state._is_speaking or (
            state._current_llm_task is not None and not state._current_llm_task.done()
        )
        if busy:
            logger.info("barge_in_speech_started", session_id=connection.session_id)
            connection.cancel()
            await self.handle_interrupt(connection)

    async def _on_stt_error(self, connection: VoiceConnection, message: str) -> None:
        logger.error("pipeline_stt_error", session_id=connection.session_id, error=message)
        if connection.is_connected:
            await connection.send_message(
                error_message(
                    connection.session_id,
                    code="STT_ERROR",
                    message="Speech recognition failed. You can keep talking with browser captions.",
                    recoverable=True,
                )
            )

    async def _run_llm_tts_pipeline(
        self, connection: VoiceConnection, user_text: str, stt_ms: float = 0
    ) -> None:
        session_id = connection.session_id
        state = self._sessions.get(session_id)
        if not state:
            return
        turn_id = uuid.uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(session_id=session_id, turn_id=turn_id)
        pipeline_start = time.perf_counter()
        clock = {"llm_first": 0.0, "tts_first": 0.0, "tokens": 0, "origin": pipeline_start}
        sentence_q: asyncio.Queue[str | None] = asyncio.Queue()
        consumer = asyncio.create_task(
            self._tts_consumer(connection, state, sentence_q, clock, turn_id)
        )
        full_response = ""
        try:
            await connection.send_message(ai_response_start(session_id))
            state._is_speaking = True
            await self._save_user_message(session_id, user_text)
            first_chunk = True
            buffer = ""
            llm_started = time.perf_counter()
            async for text_chunk in llm_service.generate_response(
                session_id, user_text, tool_executor=self._make_tool_executor(connection, turn_id)
            ):
                if (
                    connection.is_cancelled
                    or state.turn_cancel.is_set()
                    or not connection.is_connected
                ):
                    break
                if clock["tokens"] == 0:
                    clock["llm_first"] = time.perf_counter() - llm_started
                clock["tokens"] += 1
                full_response += text_chunk
                buffer += text_chunk
                await connection.send_message(ai_response_chunk(session_id, text_chunk))
                while True:
                    piece, buffer = split_sentence(buffer, first_chunk=first_chunk)
                    if not piece:
                        break
                    first_chunk = False
                    await sentence_q.put(piece)
            if buffer.strip() and not connection.is_cancelled and not state.turn_cancel.is_set():
                await sentence_q.put(buffer.strip())
            await sentence_q.put(None)
            await consumer
            total = time.perf_counter() - pipeline_start
            breakdown = {
                "turn_id": turn_id,
                "stt_ms": round(stt_ms, 1),
                "llm_first_token_ms": round(clock["llm_first"] * 1000, 1),
                "tts_first_byte_ms": round(clock["tts_first"] * 1000, 1),
                "total_ms": round(total * 1000, 1),
            }
            if (
                connection.is_connected
                and not connection.is_cancelled
                and not state.turn_cancel.is_set()
            ):
                await connection.send_message(
                    ai_response_end(session_id, full_response, clock["tokens"])
                )
                await connection.send_message(
                    latency_report(
                        session_id,
                        stt_ms=breakdown["stt_ms"],
                        llm_first_token_ms=breakdown["llm_first_token_ms"],
                        llm_total_ms=breakdown["total_ms"],
                        tts_first_byte_ms=breakdown["tts_first_byte_ms"],
                        total_pipeline_ms=breakdown["total_ms"],
                        turn_id=turn_id,
                    )
                )
                state.turn_latencies.append(breakdown["total_ms"])
                state.message_count += 2
                state.total_tokens += clock["tokens"]
                await self._save_assistant_message(
                    session_id, full_response, clock["tokens"], breakdown
                )
            logger.info("pipeline_turn_complete", **breakdown)
        except asyncio.CancelledError:
            logger.info("pipeline_llm_tts_cancelled", session_id=session_id, turn_id=turn_id)
            state.turn_cancel.set()
        except LLMError as exc:
            logger.error(
                "pipeline_llm_error", session_id=session_id, turn_id=turn_id, error=str(exc)
            )
            if connection.is_connected:
                await connection.send_message(
                    error_message(
                        session_id,
                        code="LLM_ERROR",
                        message="The language model is unavailable. Please try again.",
                        recoverable=True,
                    )
                )
        except Exception as exc:
            logger.error(
                "pipeline_llm_tts_error", session_id=session_id, turn_id=turn_id, error=str(exc)
            )
            if connection.is_connected:
                await connection.send_message(
                    error_message(
                        session_id,
                        code="PIPELINE_ERROR",
                        message="This turn failed. Please try again.",
                    )
                )
        finally:
            state.turn_cancel.set()
            if not consumer.done():
                consumer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await consumer
            state._is_speaking = False
            if connection.is_connected:
                connection.reset_cancel()
            structlog.contextvars.unbind_contextvars("turn_id")

    async def _tts_consumer(
        self,
        connection: VoiceConnection,
        state: AudioSessionState,
        sentence_q: asyncio.Queue[str | None],
        clock: dict[str, float],
        turn_id: str,
    ) -> None:
        service = self._tts()
        codec = "wav" if get_settings().resolved_tts_provider == "fake" else "mp3"
        seq = 0
        try:
            while True:
                sentence = await sentence_q.get()
                if sentence is None or connection.is_cancelled or state.turn_cancel.is_set():
                    break
                await connection.send_message(
                    audio_sentence_start(connection.session_id, seq, codec, sentence)
                )
                index = 0
                try:
                    async for audio_chunk in service.synthesize_stream(
                        sentence,
                        voice=state.tts_voice,
                        rate=state.tts_rate,
                        volume=state.tts_volume,
                        pitch=state.tts_pitch,
                    ):
                        if (
                            connection.is_cancelled
                            or state.turn_cancel.is_set()
                            or not connection.is_connected
                        ):
                            break
                        frame = pack_audio_frame(seq, audio_chunk, last=False, codec=codec)
                        await connection.send_audio(frame)
                        if clock["tts_first"] == 0.0:
                            clock["tts_first"] = time.perf_counter() - clock["origin"]
                        index += 1
                except TTSError as exc:
                    logger.error(
                        "pipeline_tts_error",
                        session_id=connection.session_id,
                        turn_id=turn_id,
                        error=str(exc),
                    )
                    if connection.is_connected:
                        await connection.send_message(
                            error_message(
                                connection.session_id,
                                code="TTS_ERROR",
                                message="I could not synthesize that sentence. The text is still in the transcript.",
                                recoverable=True,
                            )
                        )
                    break
                if connection.is_connected and not state.turn_cancel.is_set():
                    await connection.send_message(audio_sentence_end(connection.session_id, seq))
                seq += 1
        except asyncio.CancelledError:
            return

    def _make_tool_executor(
        self, connection: VoiceConnection, turn_id: str
    ) -> Callable[..., Awaitable[str]]:
        async def executor(tool_name: str, tool_args: dict) -> str:
            return await self._execute_tool(connection, tool_name, tool_args, turn_id)

        return executor

    async def _execute_tool(
        self, connection: VoiceConnection, tool_name: str, tool_args: dict, turn_id: str
    ) -> str:
        state = self._sessions.get(connection.session_id)
        policy = state.tool_policy if state else ToolPolicy()
        started = time.perf_counter()
        await connection.send_message(tool_call_start(connection.session_id, tool_name, tool_args))
        if not policy.allows(tool_name):
            message = f"Tool '{tool_name}' is not enabled for this agent."
            await self._audit_tool(connection, turn_id, tool_name, tool_args, False, 0, message)
            await connection.send_message(
                tool_call_result(connection.session_id, tool_name, message, success=False)
            )
            return message
        tool = tool_registry.get(tool_name)
        if tool is None:
            message = f"Tool '{tool_name}' is not registered."
            await connection.send_message(
                tool_call_result(connection.session_id, tool_name, message, success=False)
            )
            await self._audit_tool(connection, turn_id, tool_name, tool_args, False, 0, message)
            return message
        timeout_s = getattr(tool, "timeout_s", None) or get_settings().tool_timeout_s
        try:
            result = await asyncio.wait_for(tool.execute(**tool_args), timeout=timeout_s)
        except TimeoutError:
            result = ToolResult(output=f"Tool '{tool_name}' timed out.", success=False)
        except Exception as exc:
            result = ToolResult(output=f"Tool '{tool_name}' failed: {exc}", success=False)
        duration_ms = int((time.perf_counter() - started) * 1000)
        await connection.send_message(
            tool_call_result(
                connection.session_id, tool_name, result.to_dict(), success=result.success
            )
        )
        await self._audit_tool(
            connection,
            turn_id,
            tool_name,
            tool_args,
            result.success,
            duration_ms,
            None if result.success else result.output,
        )
        return result.output

    async def _audit_tool(
        self,
        connection: VoiceConnection,
        turn_id: str,
        tool_name: str,
        tool_args: dict,
        success: bool,
        duration_ms: int,
        error: str | None,
    ) -> None:
        state = self._sessions.get(connection.session_id)
        logger.info(
            "tool_audit",
            session_id=connection.session_id,
            turn_id=turn_id,
            tool=tool_name,
            success=success,
            duration_ms=duration_ms,
        )
        if not self._conversation_service:
            return
        try:
            from app.models.tool_audit import ToolAuditLog

            factory = self._conversation_service._session_factory
            async with factory() as session:
                session.add(
                    ToolAuditLog(
                        session_id=connection.session_id,
                        agent_id=state.agent_id_resolved if state else None,
                        turn_id=turn_id,
                        tool_name=tool_name,
                        arguments=tool_args,
                        success=success,
                        duration_ms=duration_ms,
                        error=error,
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.warning("tool_audit_persist_error", error=str(exc))

    async def _save_user_message(self, session_id: str, text: str) -> None:
        if not self._conversation_service:
            return
        try:
            from app.models.conversation import MessageRole

            await self._conversation_service.add_message(session_id, MessageRole.USER, text)
        except Exception as exc:
            logger.warning("pipeline_db_user_msg_error", error=str(exc))

    async def _save_assistant_message(
        self, session_id: str, text: str, token_count: int, breakdown: dict
    ) -> None:
        if not self._conversation_service or not text:
            return
        try:
            from app.models.conversation import MessageRole

            await self._conversation_service.add_message(
                session_id,
                MessageRole.ASSISTANT,
                text,
                token_count=token_count,
                latency_ms=int(breakdown["total_ms"]),
                latency_breakdown=breakdown,
                model=self._sessions[session_id].llm_model
                if session_id in self._sessions
                else None,
            )
        except Exception as exc:
            logger.warning("pipeline_db_assistant_msg_error", error=str(exc))

    async def _touch_session_store(self, state: AudioSessionState) -> None:
        if not self._redis:
            return
        try:
            await self._redis.hset(
                f"voice:session:{state.session_id}",
                {
                    "agent_id": state.agent_id_resolved,
                    "stt_mode": state.stt_mode,
                    "llm_model": state.llm_model,
                },
            )
        except Exception as exc:
            logger.warning("pipeline_redis_session_error", error=str(exc))

    async def _finish_call(self, state: AudioSessionState) -> None:
        if not self._conversation_service or not state.agent_db_id:
            return
        try:
            from app.models.agent import Agent, CallLog

            factory = self._conversation_service._session_factory
            turns = list(state.turn_latencies)
            avg = int(sum(turns) / len(turns)) if turns else 0
            p95 = int(percentile(turns, 95)) if turns else 0
            async with factory() as session:
                session.add(
                    CallLog(
                        agent_id=uuid.UUID(state.agent_db_id),
                        session_id=state.session_id,
                        duration_ms=int(state.uptime_s * 1000),
                        message_count=state.message_count,
                        total_tokens=state.total_tokens,
                        avg_latency_ms=avg,
                        p95_latency_ms=p95,
                        turn_latencies=turns,
                        status="completed",
                    )
                )
                agent = await session.get(Agent, uuid.UUID(state.agent_db_id))
                if agent is not None:
                    agent.total_calls = (agent.total_calls or 0) + 1
                    agent.total_duration_ms = (agent.total_duration_ms or 0) + int(
                        state.uptime_s * 1000
                    )
                await session.commit()
        except Exception as exc:
            logger.warning("pipeline_call_log_error", error=str(exc))

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)


audio_pipeline = AudioPipeline()
