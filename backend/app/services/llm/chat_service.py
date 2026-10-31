"""
LLM service — streaming chat with tool calling.

Each voice session has its own model, temperature, and max tokens.
Azure OpenAI and OpenAI both go through LangChain. With no key configured,
a local fake provider streams a reply so the pipeline can run offline.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.config import get_settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.services.llm.fake_provider import TextDelta, ToolRequest, stream_reply
from app.services.llm.memory import apply_memory

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a helpful, friendly AI voice assistant. You are having a real-time voice conversation with a human.

Guidelines:
- Keep responses concise and conversational (1-3 sentences typically)
- Be natural and engaging, like a human conversation partner
- If you don't understand something, ask for clarification
- Avoid markdown formatting, bullet points, or numbered lists since this is spoken
- Use simple, clear language appropriate for speech
- If the user's speech seems cut off or unclear, acknowledge it naturally"""

MAX_TOOL_ROUNDS = 5
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


class LLMService:
    """Per-session conversation memory and streaming completions."""

    def __init__(self) -> None:
        self._conversations: dict[str, list[Any]] = {}
        self._session_tools: dict[str, list[dict[str, Any]]] = {}
        self._session_cfg: dict[str, dict[str, Any]] = {}
        self._clients: dict[str, Any] = {}

    def create_session(
        self,
        session_id: str,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        memory_config: dict | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self._conversations[session_id] = [
            SystemMessage(content=system_prompt or DEFAULT_SYSTEM_PROMPT)
        ]
        if tools:
            self._session_tools[session_id] = tools
        self._session_cfg[session_id] = {
            "temperature": settings.azure_openai_temperature
            if temperature is None
            else temperature,
            "max_tokens": settings.azure_openai_max_tokens if max_tokens is None else max_tokens,
            "model": model or "",
            "memory": memory_config
            or {
                "type": "window",
                "window_size": 20,
                "summarize": False,
                "max_context_tokens": 8000,
            },
            "provider": provider or settings.resolved_llm_provider,
        }
        logger.info(
            "llm_session_created",
            session_id=session_id,
            tool_count=len(tools) if tools else 0,
            provider=self._session_cfg[session_id]["provider"],
            model=self._session_cfg[session_id]["model"] or None,
            temperature=self._session_cfg[session_id]["temperature"],
            max_tokens=self._session_cfg[session_id]["max_tokens"],
        )

    def destroy_session(self, session_id: str) -> None:
        history = self._conversations.pop(session_id, None)
        self._session_tools.pop(session_id, None)
        self._session_cfg.pop(session_id, None)
        self._clients.pop(session_id, None)
        logger.info(
            "llm_session_destroyed",
            session_id=session_id,
            message_count=len(history) if history else 0,
        )

    def get_history(self, session_id: str) -> list[Any]:
        return self._conversations.get(session_id, [])

    def load_messages(self, session_id: str, rows: list[tuple[str, str]]) -> None:
        """Reload persisted turns so a resumed session keeps its context."""
        history = self._conversations.get(session_id)
        if history is None:
            self.create_session(session_id)
            history = self._conversations[session_id]
        for role, content in rows:
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                history.append(AIMessage(content=content))
            elif role == "system":
                history.append(SystemMessage(content=content))
        self._remember(session_id)

    def _remember(self, session_id: str) -> list[Any]:
        history = self._conversations.get(session_id, [])
        cfg = self._session_cfg.get(session_id, {})
        trimmed = apply_memory(history, cfg.get("memory"))
        self._conversations[session_id] = trimmed
        return trimmed

    def _build_client(self, session_id: str) -> Any:
        settings = get_settings()
        cfg = self._session_cfg.get(session_id, {})
        provider = cfg.get("provider") or settings.resolved_llm_provider
        temperature = cfg.get("temperature", settings.azure_openai_temperature)
        max_tokens = cfg.get("max_tokens", settings.azure_openai_max_tokens)
        model = cfg.get("model") or ""
        timeout = settings.llm_timeout_s
        if provider == "openai":
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=model or settings.openai_model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=True,
                timeout=timeout,
                max_retries=0,
            )
        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=model or settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            timeout=timeout,
            max_retries=0,
        )

    def _client(self, session_id: str) -> Any:
        if session_id not in self._clients:
            self._clients[session_id] = self._build_client(session_id)
        return self._clients[session_id]

    async def generate_response(
        self,
        session_id: str,
        user_text: str,
        tool_executor: ToolExecutor | None = None,
    ) -> AsyncGenerator[str, None]:
        history = self._conversations.get(session_id)
        if history is None:
            self.create_session(session_id)
            history = self._conversations[session_id]
        history.append(HumanMessage(content=user_text))
        self._remember(session_id)

        cfg = self._session_cfg.get(session_id, {})
        provider = cfg.get("provider") or get_settings().resolved_llm_provider
        start_time = time.perf_counter()
        first_token_time = 0.0
        token_count = 0
        full_response = ""
        try:
            if provider == "fake":
                generator = self._generate_fake(session_id, user_text, tool_executor)
            else:
                generator = self._generate_live(session_id, tool_executor)
            async for text in generator:
                if token_count == 0:
                    first_token_time = time.perf_counter() - start_time
                token_count += 1
                full_response += text
                yield text
            logger.info(
                "llm_response_complete",
                session_id=session_id,
                tokens=token_count,
                first_token_ms=round(first_token_time * 1000, 1),
                total_ms=round((time.perf_counter() - start_time) * 1000, 1),
                response_length=len(full_response),
                provider=provider,
                model=cfg.get("model") or None,
            )
        except LLMError:
            raise
        except Exception as exc:
            logger.error("llm_generation_error", session_id=session_id, error=str(exc))
            raise LLMError(str(exc)) from exc

    async def _generate_fake(
        self,
        session_id: str,
        user_text: str,
        tool_executor: ToolExecutor | None,
    ) -> AsyncGenerator[str, None]:
        tools = self._session_tools.get(session_id)
        tool_result: str | None = None
        for _round in range(MAX_TOOL_ROUNDS + 1):
            history = self._remember(session_id)
            full = ""
            saw_tool = False
            async for event in stream_reply(user_text, tools=tools, tool_result=tool_result):
                if isinstance(event, ToolRequest):
                    saw_tool = True
                    history.append(
                        AIMessage(
                            content=full,
                            tool_calls=[
                                {"id": event.id, "name": event.name, "args": event.arguments}
                            ],
                        )
                    )
                    if tool_executor is None:
                        result = f"Tool '{event.name}' is not available."
                    else:
                        result = await tool_executor(event.name, event.arguments)
                    history.append(ToolMessage(content=result, tool_call_id=event.id))
                    tool_result = result
                    break
                if isinstance(event, TextDelta) and event.text:
                    full += event.text
                    yield event.text
            if not saw_tool:
                history.append(AIMessage(content=full))
                return
        history = self._remember(session_id)
        history.append(AIMessage(content="I hit the tool-call limit for this turn."))

    async def _generate_live(
        self,
        session_id: str,
        tool_executor: ToolExecutor | None,
    ) -> AsyncGenerator[str, None]:
        tools = self._session_tools.get(session_id)
        llm = self._client(session_id)
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        tool_rounds = 0
        while True:
            history = self._remember(session_id)
            accumulated: list[AIMessageChunk] = []
            text_this_round = ""
            async for chunk in self._astream_with_retry(llm_with_tools, history, session_id):
                accumulated.append(chunk)
                content = chunk.content
                if content:
                    text_this_round += content
                    yield content
            if not accumulated:
                break
            merged = accumulated[0]
            for chunk in accumulated[1:]:
                merged = merged + chunk  # type: ignore[operator]
            tool_calls = getattr(merged, "tool_calls", None) or []
            history = self._conversations[session_id]
            if not tool_calls:
                history.append(AIMessage(content=text_this_round))
                break
            tool_rounds += 1
            if tool_rounds > MAX_TOOL_ROUNDS:
                logger.warning("llm_max_tool_rounds", session_id=session_id, rounds=tool_rounds)
                history.append(AIMessage(content=text_this_round))
                break
            history.append(AIMessage(content=text_this_round, tool_calls=tool_calls))
            for tc in tool_calls:
                logger.info(
                    "llm_tool_call", session_id=session_id, tool=tc["name"], args=tc["args"]
                )
                if tool_executor:
                    result_str = await tool_executor(tc["name"], tc["args"])
                else:
                    result_str = f"Tool '{tc['name']}' is not available."
                history.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))

    async def _astream_with_retry(self, llm: Any, history: list[Any], session_id: str):
        settings = get_settings()
        attempts = max(1, settings.llm_max_retries)
        delay = 0.2
        last: Exception | None = None
        for attempt in range(attempts):
            yielded = False
            try:
                async for chunk in llm.astream(history):
                    yielded = True
                    yield chunk
                return
            except Exception as exc:
                last = exc
                if yielded or attempt >= attempts - 1:
                    raise LLMError(f"Language model failed: {exc}") from exc
                logger.warning(
                    "llm_retry",
                    session_id=session_id,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
                delay *= 2
        raise LLMError(f"Language model failed: {last}")


llm_service = LLMService()
