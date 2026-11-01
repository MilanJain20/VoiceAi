"""Apply an agent's memory_config to a LangChain message list."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage


def approximate_tokens(text: str) -> int:
    """Rough budget: four characters per token. Not a model tokenizer."""
    return max(1, len(text) // 4) if text else 0


def _content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return str(content or "")


def _is_system(message: Any) -> bool:
    return isinstance(message, SystemMessage) or getattr(message, "type", "") == "system"


def summary_text(messages: list[Any], limit: int = 800) -> str:
    parts: list[str] = []
    for message in messages:
        text = _content(message).strip()
        if text:
            parts.append(text[:200])
    body = " ".join(parts)[:limit]
    return f"Summary of earlier turns: {body}" if body else ""


def apply_memory(
    messages: list[Any],
    memory_config: dict | None,
) -> list[Any]:
    """Trim history to the window and the approximate token budget.

    When summarize is true, dropped turns become one system note placed
    after the original system prompt. This is an extractive summary of the
    dropped text, not a second model call.
    """
    cfg = memory_config or {}
    window = int(cfg.get("window_size") or 20)
    budget = int(cfg.get("max_context_tokens") or 8000)
    summarize = bool(cfg.get("summarize"))

    if not messages:
        return messages

    system = [messages[0]] if _is_system(messages[0]) else []
    rest = list(messages[len(system) :])

    dropped: list[Any] = []
    if window > 0 and len(rest) > window:
        dropped = rest[:-window]
        rest = rest[-window:]

    def total(items: list[Any]) -> int:
        return sum(approximate_tokens(_content(item)) for item in system + items)

    while len(rest) > 1 and total(rest) > budget:
        dropped.append(rest.pop(0))

    if summarize and dropped:
        note = summary_text(dropped)
        if note:
            system = system + [SystemMessage(content=note)]
    return system + rest
