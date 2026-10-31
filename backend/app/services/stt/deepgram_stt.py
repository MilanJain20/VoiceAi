"""
Deepgram STT service — realtime streaming speech-to-text (SDK v7).

Uses Deepgram's WebSocket streaming API for low-latency transcription.
Each voice session gets its own Deepgram connection that receives
PCM16 audio chunks and emits partial/final transcript events.

Architecture:
- One DeepgramSTTSession per VoiceConnection
- Audio chunks are forwarded directly (no re-buffering)
- Transcript callbacks invoke VoiceConnection.send_message()
- Supports interim results for real-time display

Deepgram SDK v7 uses async context managers for WebSocket connections.
We run the connection in a background task and feed audio via a queue.
"""

from __future__ import annotations

import asyncio
import contextlib
import ssl
import time
from collections.abc import Callable, Coroutine
from typing import Any

import websockets
from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.types.listen_v1metadata import ListenV1Metadata
from deepgram.listen.v1.types.listen_v1results import ListenV1Results
from deepgram.listen.v1.types.listen_v1speech_started import ListenV1SpeechStarted
from deepgram.listen.v1.types.listen_v1utterance_end import ListenV1UtteranceEnd

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Optional transport that skips TLS verification.
# Used only when INSECURE_SKIP_TLS_VERIFY=true (intercepting proxies).
# ---------------------------------------------------------------------------
_no_verify_ssl_ctx = ssl.create_default_context()
_no_verify_ssl_ctx.check_hostname = False
_no_verify_ssl_ctx.verify_mode = ssl.CERT_NONE


class _NoVerifySSLTransport:
    """Async WebSocket transport that skips SSL certificate verification.

    Satisfies deepgram.transport_interface.AsyncTransport protocol:
      async send(data), async recv(), __aiter__(), async close()

    Only constructed when insecure_skip_tls_verify is enabled.
    """

    def __init__(self, url: str, headers: dict):
        self._url = url
        self._headers = headers
        self._ws: Any = None

    async def _ensure_connected(self):
        if self._ws is None:
            self._ws = await websockets.connect(
                self._url,
                extra_headers=self._headers,
                ssl=_no_verify_ssl_ctx,
            )

    async def send(self, data: Any) -> None:
        await self._ensure_connected()
        await self._ws.send(data)

    async def recv(self) -> Any:
        await self._ensure_connected()
        return await self._ws.recv()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._ensure_connected()
        try:
            return await self._ws.recv()
        except websockets.exceptions.ConnectionClosed:
            raise StopAsyncIteration from None

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()


def _no_verify_ssl_transport(url: str, headers: dict) -> _NoVerifySSLTransport:
    """Factory for the no-SSL-verify transport (sync callable, lazy connect)."""
    return _NoVerifySSLTransport(url, headers)


class DeepgramSTTSession:
    """
    Manages a single Deepgram live transcription session (SDK v7).

    Lifecycle:
    1. start() — opens WebSocket to Deepgram in a background task
    2. send_audio(bytes) — queues PCM16 chunks for sending
    3. Background task receives transcripts and fires callbacks
    4. stop() — signals the connection to close
    """

    def __init__(
        self,
        session_id: str,
        on_transcript_partial: Callable[[str, float], Coroutine[Any, Any, None]],
        on_transcript_final: Callable[[str, float, bool], Coroutine[Any, Any, None]],
        on_speech_started: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_error: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self.session_id = session_id
        self._on_transcript_partial = on_transcript_partial
        self._on_transcript_final = on_transcript_final
        self._on_speech_started = on_speech_started
        self._on_error = on_error
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=500)
        self._task: asyncio.Task | None = None
        self._started = False
        self._start_time = 0.0
        self._stop_event = asyncio.Event()
        # Track the last final transcript for UtteranceEnd handling
        self._last_final_text: str = ""
        self._last_final_confidence: float = 0.0
        self._last_final_fired: bool = True  # True = already sent to LLM
        self.last_audio_at: float = 0.0

    async def start(self) -> None:
        """Open a live transcription connection to Deepgram."""
        settings = get_settings()
        if not settings.deepgram_api_key:
            logger.warning("deepgram_no_api_key", session_id=self.session_id)
            return

        self._start_time = time.time()
        self._task = asyncio.create_task(self._run(settings))
        self._started = True
        logger.info(
            "deepgram_session_started",
            session_id=self.session_id,
            model=settings.deepgram_model,
        )

    async def send_audio(self, audio_data: bytes) -> None:
        """Queue PCM16 audio bytes for sending to Deepgram (non-blocking)."""
        if not self._started:
            return
        self.last_audio_at = time.time()
        try:
            self._audio_queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            # Drop oldest chunk to prevent blocking the WS receive loop
            with contextlib.suppress(asyncio.QueueEmpty):
                self._audio_queue.get_nowait()
            self._audio_queue.put_nowait(audio_data)

    async def stop(self) -> None:
        """Signal the session to close and wait for cleanup."""
        if not self._started:
            return
        self._started = False
        self._stop_event.set()
        # Push sentinel to unblock the sender
        await self._audio_queue.put(None)
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        duration = round(time.time() - self._start_time, 2) if self._start_time else 0
        logger.info(
            "deepgram_session_stopped",
            session_id=self.session_id,
            duration_s=duration,
        )

    async def _run(self, settings: Any) -> None:
        """Background task: maintain WebSocket connection, send audio, receive transcripts."""
        attempts = 3
        delay = 0.3
        for attempt in range(attempts):
            try:
                await self._connect(settings)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "deepgram_connection_error",
                    session_id=self.session_id,
                    attempt=attempt + 1,
                    error=str(e),
                )
                if self._stop_event.is_set() or attempt >= attempts - 1:
                    if self._on_error:
                        await self._on_error(str(e))
                    return
                await asyncio.sleep(delay)
                delay *= 2

    async def _connect(self, settings: Any) -> None:
        client_kwargs: dict[str, Any] = {"api_key": settings.deepgram_api_key}
        if settings.insecure_skip_tls_verify:
            logger.warning("deepgram_tls_verification_disabled", session_id=self.session_id)
            client_kwargs["transport_factory"] = _no_verify_ssl_transport
        client = AsyncDeepgramClient(**client_kwargs)

        async with client.listen.v1.connect(
            model=settings.deepgram_model,
            language=settings.deepgram_language,
            sample_rate=settings.deepgram_sample_rate,
            encoding="linear16",
            channels=1,
            punctuate=True,
            interim_results=True,
            utterance_end_ms=1500,
            vad_events=True,
            endpointing=300,
            smart_format=True,
        ) as ws:
            sender_task = asyncio.create_task(self._sender(ws))
            receiver_task = asyncio.create_task(self._receiver(ws))
            keepalive_task = asyncio.create_task(self._keepalive(ws))

            done, pending = await asyncio.wait(
                [sender_task, receiver_task, keepalive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            for task in done:
                if task.exception():
                    logger.error(
                        "deepgram_task_error",
                        session_id=self.session_id,
                        error=str(task.exception()),
                    )

    async def _keepalive(self, ws: Any) -> None:
        """Send periodic keepalive to prevent Deepgram 1011 timeout."""
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(8)  # Deepgram timeout is ~15-20s
                if self._stop_event.is_set():
                    break
                try:
                    await ws.send_keep_alive()
                    logger.debug("deepgram_keepalive_sent", session_id=self.session_id)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def _sender(self, ws: Any) -> None:
        """Send queued audio chunks to Deepgram."""
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if chunk is None:
                    break
                await ws.send_media(chunk)
        except Exception as e:
            logger.error("deepgram_sender_error", session_id=self.session_id, error=str(e))
        finally:
            # Signal Deepgram we're done sending
            with contextlib.suppress(Exception):
                await ws.send_close_stream()

    async def _receiver(self, ws: Any) -> None:
        """Receive transcripts from Deepgram."""
        try:
            while not self._stop_event.is_set():
                try:
                    result = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except TimeoutError:
                    continue
                except Exception:
                    if self._stop_event.is_set():
                        break
                    raise

                logger.debug(
                    "deepgram_recv_message",
                    session_id=self.session_id,
                    msg_type=type(result).__name__,
                    is_results=isinstance(result, ListenV1Results),
                    is_utterance_end=isinstance(result, ListenV1UtteranceEnd),
                    is_speech_started=isinstance(result, ListenV1SpeechStarted),
                )

                if isinstance(result, ListenV1Results):
                    await self._handle_transcript(result)
                elif isinstance(result, ListenV1UtteranceEnd):
                    await self._handle_utterance_end()
                elif isinstance(result, ListenV1SpeechStarted):
                    logger.debug("deepgram_speech_started", session_id=self.session_id)
                    if self._on_speech_started is not None:
                        await self._on_speech_started()
                elif isinstance(result, ListenV1Metadata):
                    logger.debug("deepgram_metadata", session_id=self.session_id)
                else:
                    logger.debug(
                        "deepgram_other_message",
                        session_id=self.session_id,
                        msg_type=type(result).__name__,
                    )

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error("deepgram_receiver_error", session_id=self.session_id, error=str(e))

    async def _handle_utterance_end(self) -> None:
        """Handle UtteranceEnd — fire final transcript if we have pending text."""
        logger.debug(
            "deepgram_utterance_end",
            session_id=self.session_id,
            pending_text=self._last_final_text[:60] if self._last_final_text else "",
            already_fired=self._last_final_fired,
        )
        # If we have a pending final transcript that hasn't triggered the LLM yet,
        # fire it now with speech_final=True
        if self._last_final_text and not self._last_final_fired:
            self._last_final_fired = True
            logger.info(
                "deepgram_utterance_end_trigger",
                session_id=self.session_id,
                text=self._last_final_text[:80],
            )
            await self._on_transcript_final(
                self._last_final_text, self._last_final_confidence, True
            )
            self._last_final_text = ""

    async def _handle_transcript(self, result: ListenV1Results) -> None:
        """Process a transcript result from Deepgram."""
        try:
            channel = result.channel
            if channel is None:
                logger.debug("deepgram_no_channel", session_id=self.session_id)
                return
            alternatives = channel.alternatives
            if not alternatives:
                logger.debug("deepgram_no_alternatives", session_id=self.session_id)
                return

            transcript = alternatives[0].transcript
            logger.debug(
                "deepgram_raw_transcript",
                session_id=self.session_id,
                transcript=transcript[:80] if transcript else "<empty>",
                is_final=result.is_final,
                speech_final=result.speech_final,
            )
            if not transcript or not transcript.strip():
                return

            confidence = alternatives[0].confidence or 0.0
            is_final = result.is_final or False
            speech_final = result.speech_final or False

            if is_final:
                logger.debug(
                    "deepgram_transcript_final",
                    session_id=self.session_id,
                    text=transcript[:80],
                    confidence=round(confidence, 3),
                    speech_final=speech_final,
                )
                # Track for UtteranceEnd handling
                self._last_final_text = transcript
                self._last_final_confidence = confidence

                if speech_final:
                    # Deepgram is sure the user finished — trigger LLM immediately
                    self._last_final_fired = True
                    await self._on_transcript_final(transcript, confidence, True)
                else:
                    # Mark as pending — UtteranceEnd will trigger it
                    self._last_final_fired = False
                    await self._on_transcript_final(transcript, confidence, False)
            else:
                await self._on_transcript_partial(transcript, confidence)

        except Exception as e:
            logger.error(
                "deepgram_transcript_handler_error",
                session_id=self.session_id,
                error=str(e),
            )
