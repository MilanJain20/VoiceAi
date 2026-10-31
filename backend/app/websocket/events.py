"""
WebSocket event definitions.

Typed event constructors for building consistent WebSocket messages.
This acts as a protocol layer — neither the sender nor receiver needs
to worry about JSON structure, just call the appropriate factory.
"""

from __future__ import annotations

from typing import Any

from app.schemas.websocket import WSMessage, WSMessageType


def session_started(session_id: str, config: dict[str, Any] | None = None) -> WSMessage:
    return WSMessage(
        type=WSMessageType.SESSION_STARTED,
        session_id=session_id,
        data={"config": config or {}},
    )


def session_ended(session_id: str, reason: str = "completed") -> WSMessage:
    return WSMessage(
        type=WSMessageType.SESSION_ENDED,
        session_id=session_id,
        data={"reason": reason},
    )


def transcript_partial(session_id: str, text: str, confidence: float = 0.0) -> WSMessage:
    return WSMessage(
        type=WSMessageType.TRANSCRIPT_PARTIAL,
        session_id=session_id,
        data={"text": text, "confidence": confidence, "is_final": False},
    )


def transcript_final(
    session_id: str, text: str, confidence: float = 0.0, speech_final: bool = True
) -> WSMessage:
    return WSMessage(
        type=WSMessageType.TRANSCRIPT_FINAL,
        session_id=session_id,
        data={
            "text": text,
            "confidence": confidence,
            "is_final": True,
            "speech_final": speech_final,
        },
    )


def ai_response_start(session_id: str) -> WSMessage:
    return WSMessage(
        type=WSMessageType.AI_RESPONSE_START,
        session_id=session_id,
        data={},
    )


def ai_response_chunk(session_id: str, text: str, is_final: bool = False) -> WSMessage:
    return WSMessage(
        type=WSMessageType.AI_RESPONSE_CHUNK,
        session_id=session_id,
        data={"text": text, "is_final": is_final},
    )


def ai_response_end(session_id: str, full_text: str, token_count: int = 0) -> WSMessage:
    return WSMessage(
        type=WSMessageType.AI_RESPONSE_END,
        session_id=session_id,
        data={"full_text": full_text, "token_count": token_count},
    )


def error_message(session_id: str, code: str, message: str, recoverable: bool = True) -> WSMessage:
    return WSMessage(
        type=WSMessageType.ERROR,
        session_id=session_id,
        data={"code": code, "message": message, "recoverable": recoverable},
    )


def pong(session_id: str) -> WSMessage:
    return WSMessage(
        type=WSMessageType.PONG,
        session_id=session_id,
        data={},
    )


def vad_event(session_id: str, speech_detected: bool, barge_in: bool = False) -> WSMessage:
    return WSMessage(
        type=WSMessageType.VAD_EVENT,
        session_id=session_id,
        data={"speech_detected": speech_detected, "barge_in": barge_in},
    )


def audio_sentence_start(session_id: str, seq: int, codec: str, text: str) -> WSMessage:
    return WSMessage(
        type=WSMessageType.AUDIO_SENTENCE_START,
        session_id=session_id,
        data={"seq": seq, "codec": codec, "text": text},
    )


def audio_sentence_end(session_id: str, seq: int) -> WSMessage:
    return WSMessage(
        type=WSMessageType.AUDIO_SENTENCE_END,
        session_id=session_id,
        data={"seq": seq},
    )


def latency_report(
    session_id: str,
    stt_ms: float = 0,
    llm_first_token_ms: float = 0,
    llm_total_ms: float = 0,
    tts_first_byte_ms: float = 0,
    total_pipeline_ms: float = 0,
    turn_id: str = "",
) -> WSMessage:
    return WSMessage(
        type=WSMessageType.LATENCY_REPORT,
        session_id=session_id,
        data={
            "stt_ms": stt_ms,
            "llm_first_token_ms": llm_first_token_ms,
            "llm_total_ms": llm_total_ms,
            "tts_first_byte_ms": tts_first_byte_ms,
            "total_pipeline_ms": total_pipeline_ms,
            "turn_id": turn_id,
        },
    )


def tool_call_start(session_id: str, tool_name: str, arguments: dict[str, Any]) -> WSMessage:
    return WSMessage(
        type=WSMessageType.TOOL_CALL_START,
        session_id=session_id,
        data={"tool_name": tool_name, "arguments": arguments},
    )


def tool_call_result(
    session_id: str, tool_name: str, result: Any, success: bool = True
) -> WSMessage:
    return WSMessage(
        type=WSMessageType.TOOL_CALL_RESULT,
        session_id=session_id,
        data={"tool_name": tool_name, "result": result, "success": success},
    )
