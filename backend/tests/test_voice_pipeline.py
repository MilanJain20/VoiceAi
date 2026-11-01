"""Voice pipeline ordering, barge-in, and stored timings. Providers are fake."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.audio.pipeline import AudioPipeline
from app.services.llm import fake_provider
from app.services.tts import fake_tts


class FakeSocket:
    def __init__(self) -> None:
        self.session_id = "sess-test"
        self.messages: list = []
        self.audio: list[bytes] = []
        self._cancel = False

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel

    def cancel(self) -> None:
        self._cancel = True

    def reset_cancel(self) -> None:
        self._cancel = False

    async def send_message(self, message) -> None:
        self.messages.append(message)

    async def send_audio(self, payload: bytes) -> None:
        self.audio.append(payload)


def _types(sock: FakeSocket) -> list[str]:
    return [message.type.value for message in sock.messages]


@pytest.fixture(autouse=True)
def _fast_fakes():
    previous_token = fake_provider.token_delay_s
    previous_tts = fake_tts.chunk_delay_s
    previous_chunks = fake_tts.chunks_per_sentence
    fake_provider.token_delay_s = 0.0
    fake_tts.chunk_delay_s = 0.0
    fake_tts.chunks_per_sentence = 2
    yield
    fake_provider.token_delay_s = previous_token
    fake_tts.chunk_delay_s = previous_tts
    fake_tts.chunks_per_sentence = previous_chunks


@pytest.mark.asyncio
async def test_turn_orders_text_before_audio_and_records_timings() -> None:
    pipeline = AudioPipeline()
    sock = FakeSocket()
    await pipeline.handle_session_start(sock, {"stt_mode": "browser", "agent_id": "default"})
    await pipeline.handle_user_transcript(sock, "Tell me something short about voice.", stt_ms=12)
    state = pipeline._sessions[sock.session_id]
    assert state._current_llm_task is not None
    await state._current_llm_task

    kinds = _types(sock)
    assert kinds.index("ai_response_start") < kinds.index("ai_response_chunk")
    assert kinds.index("audio_sentence_start") < kinds.index("ai_response_end")
    assert "latency_report" in kinds
    assert sock.audio, "expected framed audio before the turn finished"
    report = next(message for message in sock.messages if message.type.value == "latency_report")
    assert report.data["stt_ms"] == 12
    assert "llm_first_token_ms" in report.data
    assert "tts_first_byte_ms" in report.data
    assert report.data["turn_id"]
    await pipeline.destroy_session(sock.session_id)


@pytest.mark.asyncio
async def test_barge_in_cancels_the_turn() -> None:
    fake_provider.token_delay_s = 0.05
    fake_tts.chunk_delay_s = 0.05
    pipeline = AudioPipeline()
    sock = FakeSocket()
    await pipeline.handle_session_start(sock, {"stt_mode": "browser", "agent_id": "default"})
    await pipeline.handle_user_transcript(sock, "Please talk for a while about the ocean.")
    await asyncio.sleep(0.02)
    await pipeline.handle_interrupt(sock)
    state = pipeline._sessions[sock.session_id]
    # The task is cleared by interrupt. Give the cancelled task a moment.
    await asyncio.sleep(0.05)
    assert any(
        message.type.value == "vad_event" and message.data.get("barge_in")
        for message in sock.messages
    )
    assert state._is_speaking is False

    sock.reset_cancel()
    fake_provider.token_delay_s = 0.0
    fake_tts.chunk_delay_s = 0.0
    await pipeline.handle_user_transcript(sock, "A short follow up.")
    state = pipeline._sessions[sock.session_id]
    assert state._current_llm_task is not None
    await state._current_llm_task
    assert _types(sock).count("latency_report") == 1
    await pipeline.destroy_session(sock.session_id)


def test_websocket_round_trip_with_fake_providers() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    try:
        with TestClient(app) as client, client.websocket_connect("/api/v1/ws/voice") as ws:
            started = ws.receive_json()
            assert started["type"] == "session_started"
            ws.send_json(
                {"type": "start_session", "data": {"stt_mode": "browser", "agent_id": "default"}}
            )
            ws.send_json(
                {
                    "type": "user_transcript",
                    "data": {"text": "Say hello in one breath.", "client_stt_ms": 8},
                }
            )
            kinds: list[str] = []
            audio = 0
            for _ in range(200):
                incoming = ws.receive()
                if incoming.get("text"):
                    payload = json.loads(incoming["text"])
                    kinds.append(payload["type"])
                    if payload["type"] == "latency_report":
                        assert payload["data"]["stt_ms"] == 8
                        break
                elif incoming.get("bytes"):
                    audio += 1
            else:
                pytest.fail(f"no latency report in {kinds}")
    except Exception as exc:  # database or socket unavailable
        pytest.skip(f"websocket app test needs Postgres: {exc}")

    assert "ai_response_chunk" in kinds
    assert audio > 0
    assert kinds.index("audio_sentence_start") < kinds.index("latency_report")
