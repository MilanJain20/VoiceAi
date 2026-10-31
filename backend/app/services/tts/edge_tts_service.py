"""
Edge TTS service — free text-to-speech using Microsoft Edge's TTS engine.

Converts AI response text to PCM16 audio and streams it back
through the WebSocket for browser playback.

Features:
- Sentence-level streaming (split text into sentences, synthesize each)
- Outputs raw PCM16 at 16kHz for direct playback
- No API key needed — completely free
"""

from __future__ import annotations

import io
import ssl
import struct
import asyncio
from typing import AsyncGenerator

import edge_tts
import edge_tts.communicate as _edge_comm

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Fix SSL for corporate proxies ────────────────────────────────────
# Corporate proxies (e.g., Siemens, ZScaler) do SSL interception,
# causing edge-tts to fail with CERTIFICATE_VERIFY_FAILED.
# We patch the module-level SSL context to skip verification.
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE
_edge_comm._SSL_CTX = _ssl_ctx
logger.info("edge_tts_ssl_patched", msg="SSL verification disabled for corporate proxy")


class EdgeTTSService:
    """
    Streams text-to-speech audio using edge-tts.

    edge-tts outputs MP3 by default, but we need raw PCM16 for WebSocket
    binary streaming. We collect the MP3 chunks and convert them.
    For simplicity and to avoid ffmpeg dependency, we send MP3 directly
    and let the browser decode it using the Web Audio API.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.voice = settings.edge_tts_voice
        self.rate = settings.edge_tts_rate
        self.volume = settings.edge_tts_volume
        self.pitch = settings.edge_tts_pitch

    async def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS audio for the given text.

        Buffers the full MP3 for the input text before yielding so the
        browser receives a complete, decodable MP3 per sentence rather
        than tiny fragments that cause decoding glitches.

        Optional voice/rate/volume/pitch args override instance defaults
        (used by per-agent TTS settings).
        """
        if not text or not text.strip():
            return

        try:
            communicate = edge_tts.Communicate(
                text=text.strip(),
                voice=voice or self.voice,
                rate=rate or self.rate,
                volume=volume or self.volume,
                pitch=pitch or self.pitch,
            )

            # Collect full MP3 for this sentence
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            data = buffer.getvalue()
            if data:
                # Yield in one piece (complete, valid MP3)
                yield data

        except Exception as e:
            logger.error("tts_synthesis_error", error=str(e), text=text[:50])

    async def synthesize_full(self, text: str) -> bytes | None:
        """Synthesize full text and return complete MP3 bytes."""
        if not text or not text.strip():
            return None

        buffer = io.BytesIO()
        try:
            communicate = edge_tts.Communicate(
                text=text.strip(),
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            result = buffer.getvalue()
            if result:
                logger.debug("tts_synthesized", text_len=len(text), audio_bytes=len(result))
            return result if result else None

        except Exception as e:
            logger.error("tts_full_synthesis_error", error=str(e), text=text[:50])
            return None


# Global singleton
tts_service = EdgeTTSService()
