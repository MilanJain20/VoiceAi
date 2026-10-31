"""
LLM service — Azure OpenAI GPT-4o streaming integration with tool calling.

Manages conversational context and streams AI responses token-by-token.
Uses LangChain's AzureChatOpenAI for structured interactions.
When the model requests a tool call, it pauses streaming, executes the tool,
feeds the result back, and resumes streaming the final response.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Awaitable

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import AzureChatOpenAI

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default system prompt for the voice agent
DEFAULT_SYSTEM_PROMPT = """You are a helpful, friendly AI voice assistant. You are having a real-time voice conversation with a human.

Guidelines:
- Keep responses concise and conversational (1-3 sentences typically)
- Be natural and engaging, like a human conversation partner
- If you don't understand something, ask for clarification
- Avoid markdown formatting, bullet points, or numbered lists since this is spoken
- Use simple, clear language appropriate for speech
- If the user's speech seems cut off or unclear, acknowledge it naturally"""

# Max tool-call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5


@dataclass
class ToolCallRequest:
    """Represents a tool call the LLM wants to make."""
    id: str
    name: str
    arguments: dict[str, Any]


# Type for the tool executor callback provided by the pipeline
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


class LLMService:
    """
    Manages Azure OpenAI chat completions with conversation memory
    and tool/function calling support.

    Each voice session maintains its own conversation history.
    Responses are streamed token-by-token for minimal latency.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, list[Any]] = {}
        self._llm: AzureChatOpenAI | None = None
        self._session_tools: dict[str, list[dict[str, Any]]] = {}

    def _get_llm(self) -> AzureChatOpenAI:
        """Lazy-init the LLM client."""
        if self._llm is None:
            settings = get_settings()
            self._llm = AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                azure_deployment=settings.azure_openai_deployment,
                api_version=settings.azure_openai_api_version,
                temperature=settings.azure_openai_temperature,
                max_tokens=settings.azure_openai_max_tokens,
                streaming=True,
            )
        return self._llm

    def create_session(
        self,
        session_id: str,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize conversation history for a session, optionally with tools."""
        self._conversations[session_id] = [
            SystemMessage(content=system_prompt or DEFAULT_SYSTEM_PROMPT)
        ]
        if tools:
            self._session_tools[session_id] = tools
        logger.info(
            "llm_session_created",
            session_id=session_id,
            tool_count=len(tools) if tools else 0,
        )

    def destroy_session(self, session_id: str) -> None:
        """Clean up conversation history and tools."""
        history = self._conversations.pop(session_id, None)
        self._session_tools.pop(session_id, None)
        msg_count = len(history) if history else 0
        logger.info(
            "llm_session_destroyed",
            session_id=session_id,
            message_count=msg_count,
        )

    def get_history(self, session_id: str) -> list[Any]:
        """Get conversation history for a session."""
        return self._conversations.get(session_id, [])

    async def generate_response(
        self,
        session_id: str,
        user_text: str,
        tool_executor: ToolExecutor | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream an AI response for the given user text.

        Yields text chunks as they arrive from Azure OpenAI.
        If the model requests tool calls, executes them via tool_executor
        and continues generating the final response.
        """
        history = self._conversations.get(session_id)
        if history is None:
            self.create_session(session_id)
            history = self._conversations[session_id]

        # Add user message to history
        history.append(HumanMessage(content=user_text))

        llm = self._get_llm()

        # Bind tools if this session has them
        tools = self._session_tools.get(session_id)
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        full_response = ""
        start_time = time.time()
        first_token_time = 0.0
        token_count = 0
        tool_rounds = 0

        try:
            while True:
                # Accumulate the streamed response and check for tool calls
                accumulated_chunks: list[AIMessageChunk] = []
                text_yielded_this_round = ""

                async for chunk in llm_with_tools.astream(history):
                    accumulated_chunks.append(chunk)
                    content = chunk.content
                    if content:
                        if token_count == 0:
                            first_token_time = time.time() - start_time
                        token_count += 1
                        full_response += content
                        text_yielded_this_round += content
                        yield content

                # Merge accumulated chunks to get the full AI message
                if accumulated_chunks:
                    merged = accumulated_chunks[0]
                    for c in accumulated_chunks[1:]:
                        merged = merged + c  # type: ignore[operator]
                else:
                    break

                # Check if there are tool calls
                tool_calls = getattr(merged, "tool_calls", None) or []

                if not tool_calls:
                    # No tool calls — add final message and we're done
                    history.append(AIMessage(content=full_response))
                    break

                # Handle tool calls
                tool_rounds += 1
                if tool_rounds > MAX_TOOL_ROUNDS:
                    logger.warning(
                        "llm_max_tool_rounds",
                        session_id=session_id,
                        rounds=tool_rounds,
                    )
                    history.append(AIMessage(content=full_response))
                    break

                # Add the AI message with tool calls to history
                ai_msg = AIMessage(
                    content=text_yielded_this_round,
                    tool_calls=tool_calls,
                )
                history.append(ai_msg)

                # Execute each tool call
                for tc in tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc["args"]
                    tool_call_id = tc["id"]

                    logger.info(
                        "llm_tool_call",
                        session_id=session_id,
                        tool=tool_name,
                        args=tool_args,
                    )

                    if tool_executor:
                        result_str = await tool_executor(tool_name, tool_args)
                    else:
                        result_str = f"Tool '{tool_name}' is not available."

                    # Add tool result to history so LLM can continue
                    history.append(
                        ToolMessage(
                            content=result_str,
                            tool_call_id=tool_call_id,
                        )
                    )

                # Loop back to stream the LLM's follow-up response
                # after incorporating tool results

            total_time = time.time() - start_time
            logger.info(
                "llm_response_complete",
                session_id=session_id,
                tokens=token_count,
                first_token_ms=round(first_token_time * 1000, 1),
                total_ms=round(total_time * 1000, 1),
                response_length=len(full_response),
                tool_rounds=tool_rounds,
            )

        except Exception as e:
            logger.error(
                "llm_generation_error",
                session_id=session_id,
                error=str(e),
            )
            yield "I'm sorry, I encountered an error. Could you try again?"

    def trim_history(self, session_id: str, max_messages: int = 20) -> None:
        """Trim conversation history to prevent token overflow."""
        history = self._conversations.get(session_id)
        if not history:
            return
        if len(history) > max_messages:
            # Keep system prompt + last N messages
            system = history[0]
            self._conversations[session_id] = [system] + history[-(max_messages - 1):]


# Global singleton
llm_service = LLMService()
