"""
Voice WebSocket endpoint — the primary realtime entry point.

This is the main WebSocket route that browsers connect to for voice sessions.
In Phase 1, it establishes connection management, session lifecycle,
and the message routing loop. The actual STT/LLM/TTS pipeline
is wired in Phases 2-5.

Flow:
1. Client connects to /api/v1/ws/voice
2. Server accepts, creates VoiceConnection
3. Client sends start_session message
4. Server registers session, begins heartbeat
5. Client streams audio chunks (binary frames)
6. Server routes audio through pipeline: STT → LLM → TTS
7. Server streams audio response back
8. Either side can end session or client can interrupt

Message routing:
- Binary frames → audio pipeline
- JSON frames → control message handler (start, end, interrupt, ping, config)
"""

from __future__ import annotations

import contextlib
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.schemas.websocket import WSMessage, WSMessageType
from app.services.audio.pipeline import audio_pipeline
from app.websocket.connection import ConnectionState, VoiceConnection
from app.websocket.events import error_message, pong, session_ended, session_started
from app.websocket.manager import connection_manager

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    """
    Main voice session WebSocket endpoint.

    Each connection represents one voice conversation session.
    """
    settings = get_settings()
    if settings.auth_enabled:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Not authenticated")
            return
        try:
            decode_access_token(token)
        except Exception:
            await websocket.close(code=1008, reason="Invalid token")
            return

    connection = VoiceConnection(websocket)

    try:
        # Register and accept the connection
        await connection_manager.connect(connection)

        # Send session started confirmation
        await connection.send_message(
            session_started(connection.session_id, config={"sample_rate": 16000})
        )

        # Main message loop
        await _message_loop(connection)

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=connection.session_id)
    except Exception as e:
        logger.error(
            "ws_unexpected_error",
            session_id=connection.session_id,
            error=str(e),
            traceback=traceback.format_exc(),
        )
        with contextlib.suppress(Exception):
            await connection.send_message(
                error_message(
                    connection.session_id,
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                    recoverable=False,
                )
            )
    finally:
        await audio_pipeline.destroy_session(connection.session_id)
        await connection_manager.disconnect(connection.session_id)


async def _message_loop(connection: VoiceConnection) -> None:
    """
    Core message routing loop.

    Handles three types of incoming data:
    1. Binary (bytes) → audio chunks, routed to STT pipeline
    2. JSON with type field → control messages
    3. Ping → pong response for heartbeat
    """
    while connection.is_connected:
        try:
            raw = await connection.receive_message()

            if isinstance(raw, bytes):
                # Audio chunk — route to processing pipeline
                await _handle_audio_chunk(connection, raw)
                continue

            if isinstance(raw, WSMessage):
                await _handle_control_message(connection, raw)
                continue

        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(
                "ws_message_error",
                session_id=connection.session_id,
                error=str(e),
            )
            await connection.send_message(
                error_message(
                    connection.session_id,
                    code="MESSAGE_ERROR",
                    message=f"Error processing message: {str(e)}",
                )
            )


async def _handle_audio_chunk(connection: VoiceConnection, audio_data: bytes) -> None:
    """
    Process an incoming audio chunk.

    Routes audio through the pipeline: buffer → STT → LLM → TTS.
    """
    # Track bytes for metrics
    logger.debug(
        "ws_audio_chunk",
        session_id=connection.session_id,
        bytes=len(audio_data),
    )

    await audio_pipeline.process_chunk(connection, audio_data)


async def _handle_control_message(connection: VoiceConnection, message: WSMessage) -> None:
    """Route control messages to appropriate handlers."""
    match message.type:
        case WSMessageType.PING:
            connection.touch_ping()
            await connection.send_message(pong(connection.session_id))

        case WSMessageType.START_SESSION:
            connection.state = ConnectionState.STREAMING
            logger.info(
                "ws_session_started",
                session_id=connection.session_id,
                config=message.data,
            )
            resolved = await audio_pipeline.handle_session_start(connection, message.data or {})
            await connection.send_message(session_started(connection.session_id, config=resolved))

        case WSMessageType.END_SESSION:
            logger.info("ws_session_ending", session_id=connection.session_id)
            await audio_pipeline.handle_session_end(connection)
            await connection.send_message(
                session_ended(connection.session_id, reason="client_requested")
            )
            await connection.close()

        case WSMessageType.INTERRUPT:
            logger.info("ws_interrupt", session_id=connection.session_id)
            connection.cancel()
            await audio_pipeline.handle_interrupt(connection)
            connection.reset_cancel()

        case WSMessageType.CONFIG_UPDATE:
            logger.info(
                "ws_config_update",
                session_id=connection.session_id,
                config=message.data,
            )
            # TODO Phase 3+: Update audio config, STT config, etc.

        case WSMessageType.USER_TRANSCRIPT:
            # Browser-side STT (Web Speech API) — text arrives directly
            text = (message.data or {}).get("text", "").strip()
            client_stt_ms = float((message.data or {}).get("client_stt_ms") or 0)
            if text:
                logger.info(
                    "ws_user_transcript",
                    session_id=connection.session_id,
                    text=text[:80],
                )
                await audio_pipeline.handle_user_transcript(connection, text, stt_ms=client_stt_ms)

        case _:
            logger.warning(
                "ws_unknown_message_type",
                session_id=connection.session_id,
                type=message.type,
            )
