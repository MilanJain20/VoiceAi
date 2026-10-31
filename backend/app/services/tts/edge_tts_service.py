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

import asyncio
import io
import ssl
from collections.abc import AsyncGenerator

import edge_tts
import edge_tts.communicate as _edge_comm

from app.config import get_settings
from app.core.exceptions import TTSError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _maybe_disable_tls_verify() -> None:
    """Skip certificate checks only when explicitly opted in.

    Some intercepting proxies present their own certificate and cause
    edge-tts to fail with CERTIFICATE_VERIFY_FAILED. Leave this off
    unless INSECURE_SKIP_TLS_VERIFY=true.
    """
    if not get_settings().insecure_skip_tls_verify:
        return
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    _edge_comm._SSL_CTX = ssl_ctx
    logger.warning("edge_tts_tls_verification_disabled")


_maybe_disable_tls_verify()


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

        settings = get_settings()
        attempts = max(1, settings.tts_max_retries)
        delay = 0.2
        last_error: Exception | None = None
        for attempt in range(attempts):
            yielded = False
            try:
                communicate = edge_tts.Communicate(
                    text=text.strip(),
                    voice=voice or self.voice,
                    rate=rate or self.rate,
                    volume=volume or self.volume,
                    pitch=pitch or self.pitch,
                )
                async with asyncio.timeout(settings.tts_timeout_s):
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio" and chunk["data"]:
                            yielded = True
                            yield chunk["data"]
                if not yielded:
                    raise TTSError("Edge TTS returned no audio")
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                if yielded or attempt >= attempts - 1:
                    logger.error("tts_synthesis_error", error=str(exc), text=text[:50])
                    raise TTSError(str(exc)) from exc
                logger.warning("tts_retry", attempt=attempt + 1, error=str(exc))
                await asyncio.sleep(delay)
                delay *= 2
        raise TTSError(str(last_error))

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
