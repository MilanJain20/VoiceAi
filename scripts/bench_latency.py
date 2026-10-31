"""Synthetic latency benchmark.

This does not call Azure, OpenAI, Deepgram, or Edge TTS. Delays are
asyncio sleeps inside the fake providers. Numbers are pipeline overhead
on this machine, not production voice latency.

Usage (from the repo root, with the backend env vars that tests use):

    cd backend && python ../scripts/bench_latency.py --turns 20
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("POSTGRES_PASSWORD", "voiceai_dev_password")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://voiceai:voiceai_dev_password@localhost:5432/voiceai",
)
os.environ.setdefault("JWT_SECRET_KEY", "bench-jwt-secret-not-for-production")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("TTS_PROVIDER", "fake")

from app.services.audio.pipeline import AudioPipeline
from app.services.audio.sentences import split_sentence
from app.services.llm import fake_provider
from app.services.llm.fake_provider import reply_for
from app.services.metrics import percentile
from app.services.tts import fake_tts


class Sink:
    def __init__(self) -> None:
        self.session_id = "bench"
        self.messages: list = []
        self.audio = 0
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

    async def send_audio(self, _payload: bytes) -> None:
        self.audio += 1


def _report(sock: Sink) -> dict:
    for message in sock.messages:
        if message.type.value == "latency_report":
            return message.data
    return {}


async def sequential_ttfa(
    text: str, token_delay: float, chunk_delay: float, chunks: int
) -> tuple[float, float]:
    """Old shape: 40-character first cut, and the full TTS buffer before the first byte.

    TTS is awaited before the token reader continues, so the rest of the
    reply cannot overlap synthesis.
    """
    started = time.perf_counter()
    first_audio = 0.0
    buffer = ""
    words = reply_for(text, None).split(" ")
    for index, word in enumerate(words):
        await asyncio.sleep(token_delay)
        buffer += word if index == len(words) - 1 else word + " "
        while True:
            # Historical splitter waited for 40 characters before the first cut.
            piece, rest = split_sentence(buffer, first_chunk=False)
            if not piece:
                break
            buffer = rest
            for chunk_index in range(chunks):
                await asyncio.sleep(chunk_delay)
                if first_audio == 0.0 and chunk_index == chunks - 1:
                    # The old service yielded only after every chunk was buffered.
                    first_audio = time.perf_counter() - started
    if buffer.strip():
        for chunk_index in range(chunks):
            await asyncio.sleep(chunk_delay)
            if first_audio == 0.0 and chunk_index == chunks - 1:
                first_audio = time.perf_counter() - started
    total = time.perf_counter() - started
    return first_audio * 1000, total * 1000


async def concurrent_turn(text: str) -> dict:
    pipeline = AudioPipeline()
    sock = Sink()
    await pipeline.handle_session_start(
        sock, {"stt_mode": "browser", "agent_id": "default"}
    )
    await pipeline.handle_user_transcript(sock, text, stt_ms=0)
    state = pipeline._sessions[sock.session_id]
    assert state._current_llm_task is not None
    await state._current_llm_task
    data = _report(sock)
    await pipeline.destroy_session(sock.session_id)
    return data


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--token-delay-ms", type=float, default=8)
    parser.add_argument("--tts-chunk-delay-ms", type=float, default=12)
    parser.add_argument("--tts-chunks", type=int, default=4)
    args = parser.parse_args()

    token_delay = args.token_delay_ms / 1000
    chunk_delay = args.tts_chunk_delay_ms / 1000
    fake_provider.token_delay_s = token_delay
    fake_tts.chunk_delay_s = chunk_delay
    fake_tts.chunks_per_sentence = args.tts_chunks

    prompt = "Tell me something short about voice agents."
    sequential_ttfa_ms: list[float] = []
    sequential_total_ms: list[float] = []
    concurrent_ttfa_ms: list[float] = []
    concurrent_total_ms: list[float] = []

    for _ in range(args.turns):
        first, total = await sequential_ttfa(
            prompt, token_delay, chunk_delay, args.tts_chunks
        )
        sequential_ttfa_ms.append(first)
        sequential_total_ms.append(total)
        data = await concurrent_turn(prompt)
        concurrent_ttfa_ms.append(float(data.get("tts_first_byte_ms") or 0))
        concurrent_total_ms.append(float(data.get("total_pipeline_ms") or 0))

    # Expected concurrent first audio: tokens until the short first split, plus one TTS chunk.
    buffer = ""
    produced = 0
    words = reply_for(prompt, None).split(" ")
    for index, word in enumerate(words):
        produced += 1
        buffer += word if index == len(words) - 1 else word + " "
        piece, _rest = split_sentence(buffer, first_chunk=True)
        if piece:
            break
    expected_ms = produced * args.token_delay_ms + args.tts_chunk_delay_ms
    overhead = [value - expected_ms for value in concurrent_ttfa_ms]

    print("SYNTHETIC PROVIDER BENCHMARK")
    print("Not a measurement of Azure, OpenAI, Deepgram, or Edge TTS.")
    print(
        f"turns={args.turns} token_delay_ms={args.token_delay_ms} tts_chunk_delay_ms={args.tts_chunk_delay_ms} tts_chunks={args.tts_chunks}"
    )
    print(
        f"sequential_full_buffer_ttfa_p50_ms={percentile(sequential_ttfa_ms, 50):.1f}"
    )
    print(f"concurrent_streaming_ttfa_p50_ms={percentile(concurrent_ttfa_ms, 50):.1f}")
    print(f"sequential_total_turn_p50_ms={percentile(sequential_total_ms, 50):.1f}")
    print(f"concurrent_total_turn_p50_ms={percentile(concurrent_total_ms, 50):.1f}")
    print(
        f"expected_concurrent_ttfa_ms={expected_ms:.1f} tokens_before_first_piece={produced}"
    )
    print(f"pipeline_overhead_p50_ms={percentile(overhead, 50):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
