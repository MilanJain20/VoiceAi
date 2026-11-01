"""TTS stand-in that yields short WAV clips. No network and no API key."""

from __future__ import annotations

import asyncio
import io
import math
import struct
import wave
from collections.abc import AsyncGenerator

# Tests and the benchmark overwrite these.
chunk_delay_s = 0.0
chunks_per_sentence = 2


def _wav(duration_s: float = 0.12, freq: float = 440.0, rate: int = 16000) -> bytes:
    n = max(1, int(duration_s * rate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            sample = int(8000 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", sample)
        handle.writeframes(bytes(frames))
    return buf.getvalue()


class FakeTTSService:
    """Each sentence becomes a few self-contained WAV chunks."""

    codec = "wav"

    async def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        del voice, rate, volume, pitch
        if not text or not text.strip():
            return
        count = max(1, chunks_per_sentence)
        for index in range(count):
            if chunk_delay_s:
                await asyncio.sleep(chunk_delay_s)
            freq = 440.0 + (index * 40)
            yield _wav(freq=freq)


fake_tts_service = FakeTTSService()
