"""Timeouts and exponential backoff for provider calls."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.exceptions import LLMError


async def call_with_retry[T](
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    timeout_s: float = 20.0,
    base_delay_s: float = 0.2,
    error_type: type[Exception] = LLMError,
    operation: str = "provider call",
) -> T:
    """Run factory() with a timeout. Retry only when it raises before returning."""
    last: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return await asyncio.wait_for(factory(), timeout_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last = exc
            if attempt >= attempts - 1:
                break
            await asyncio.sleep(base_delay_s * (2**attempt))
    raise error_type(f"{operation} failed after {attempts} attempts: {last}") from last
