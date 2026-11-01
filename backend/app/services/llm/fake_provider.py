"""Deterministic streaming stand-in for Azure OpenAI and OpenAI.

The words arrive on a timer so tests can measure pipeline overlap and can
cancel a turn while tokens are still being produced. Weather, time, and
calculator phrases emit a tool call when that tool is in the allowed schema.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

# Tests and the benchmark overwrite this.
token_delay_s = 0.0


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolRequest:
    id: str
    name: str
    arguments: dict


def _tool_names(tools: list[dict] | None) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        fn = tool.get("function") or tool
        name = fn.get("name")
        if name:
            names.add(name)
    return names


def reply_for(user_text: str, tool_result: str | None) -> str:
    if tool_result:
        return f"Here is what I found. {tool_result}"
    text = user_text.strip() or "Hello"
    return (
        f"Sure, I can help with that. You said: {text}. "
        "I am a local stand-in voice, so this reply is generated without an API key."
    )


def maybe_tool(user_text: str, allowed: set[str]) -> ToolRequest | None:
    lowered = user_text.lower()
    if "get_weather" in allowed and "weather" in lowered:
        match = re.search(r"weather (?:in|for) ([a-zA-Z .'-]+)", user_text, re.I)
        city = match.group(1).strip(" ?.!") if match else "Paris"
        return ToolRequest(id="call_weather", name="get_weather", arguments={"city": city})
    if "get_current_time" in allowed and "time" in lowered:
        return ToolRequest(id="call_time", name="get_current_time", arguments={})
    if (
        "calculator" in allowed
        and any(ch.isdigit() for ch in user_text)
        and ("calculate" in lowered or "what is" in lowered)
    ):
        match = re.search(r"(-?\d[\d\s.+\-*/^()]*)", user_text)
        expr = match.group(1).strip() if match else "2+2"
        return ToolRequest(id="call_calc", name="calculator", arguments={"expression": expr})
    return None


async def stream_reply(
    user_text: str,
    *,
    tools: list[dict] | None,
    tool_result: str | None,
) -> AsyncIterator[TextDelta | ToolRequest]:
    if tool_result is None:
        request = maybe_tool(user_text, _tool_names(tools))
        if request is not None:
            if token_delay_s:
                await asyncio.sleep(token_delay_s)
            yield request
            return
    words = reply_for(user_text, tool_result).split(" ")
    for index, word in enumerate(words):
        if token_delay_s:
            await asyncio.sleep(token_delay_s)
        suffix = "" if index == len(words) - 1 else " "
        yield TextDelta(text=word + suffix)
