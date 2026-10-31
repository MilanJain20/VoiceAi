# Latency instrumentation plan

No stage timings in this document are measurements. The code computes a few durations and ships them on the socket. Nothing in the repo records a benchmark.

## What is already timed

| Clock | Where | Starts | Stops | What it misses |
| --- | --- | --- | --- | --- |
| LLM first chunk | `AudioPipeline._run_llm_tts_pipeline` | `pipeline_start = time.time()` just before `ai_response_start` | First text chunk yielded to the pipeline loop | Time from end of user speech until `user_transcript` is received. Azure HTTP connect is inside this number. |
| LLM first chunk, again | `LLMService.generate_response` | `start_time` after the user message is appended | First non-empty `chunk.content` | Logged as `llm_response_complete.first_token_ms`. Not the same instant as the pipeline clock (tool setup and the DB user-message insert sit between them). |
| Time to first audio byte on the server | `_run_llm_tts_pipeline` | `pipeline_start` | After `_synthesize_and_send` returns true | `_synthesize_and_send` returns only after Edge TTS has produced a full MP3 and the first `send_audio` has been awaited. It is not time-to-first-TTS-chunk from the vendor. |
| Turn total | same function | `pipeline_start` | After the last sentence, before `ai_response_end` | Client decode and playback. `llm_total_ms` is computed with a second `time.time()` call and is not the LLM-only duration. |
| Assistant message | `ConversationService.add_message` | — | `latency_ms=int(total_time * 1000)` on the assistant row | One integer per turn. Stage splits are not columns. |
| HTTP | `RequestLoggingMiddleware` | request start | response headers | WebSocket frames are excluded (`scope["type"] != "http"`). |
| STT | `latency_report(..., stt_ms=0)` | — | — | Hardcoded `0` in `_run_llm_tts_pipeline`. Deepgram logs session duration on stop, not per utterance. |

`latency_report` fields (`backend/app/websocket/events.py`): `stt_ms`, `llm_first_token_ms`, `llm_total_ms`, `tts_first_byte_ms`, `total_pipeline_ms`. The playground prints `llm_first_token_ms` and `total_pipeline_ms` only.

`CallLog.avg_latency_ms` and `p95_latency_ms` are never written. Agent analytics returns `latency_p50_ms: 0` and `latency_p95_ms: 0`.

## Where to add the three clocks

Use `time.perf_counter()` and record milliseconds. Log them with the existing structlog event names. Put the same numbers on `latency_report`. Do not invent a default when a clock did not run.

### 1. STT (`stt_ms`)

Browser path (`frontend/src/hooks/use-speech-recognition.ts` and `voice-store.ts` `sendUserTranscript`):

- Stamp `speech_ended_ms` when a final result arrives, or when the 1500 ms silence timer fires (`silenceTimeoutMs`).
- Send that stamp on the `user_transcript` frame.
- In `handle_user_transcript`, set `stt_ms` to `received_at - speech_ended_ms` when the stamp is present. That is network plus scheduling, not recognition time. Recognition time stays in the browser unless the client also sends `recognition_ms`.

Deepgram path (`DeepgramSTTSession._handle_transcript` / `_handle_utterance_end`):

- Stamp `audio_last_byte` in `send_audio` (last PCM chunk queued).
- Stamp `transcript_final` when `speech_final` is true or when utterance end promotes a pending final.
- `stt_ms = transcript_final - audio_last_byte`. This includes Deepgram endpointing (`endpointing=300`, `utterance_end_ms=1500` in `DeepgramSTTSession._run`). Label it as endpointing plus recognition, not model time alone.

Pass the value into `_run_llm_tts_pipeline` instead of the literal `0`.

### 2. Time to first token (`llm_first_token_ms`)

Keep the pipeline clock. Split it:

- `llm_request_started` immediately before `llm_service.generate_response`.
- `llm_first_token` on the first yielded chunk (already `token_count == 0` in the pipeline loop).
- Report `llm_first_token_ms` as `llm_first_token - llm_request_started`.
- Report `pre_llm_ms` separately for the user-message insert and any tool-schema work, so the Azure wait is visible.

`LLMService` already logs `first_token_ms`. One of the two clocks should be removed from the public report so the UI and the log are the same interval.

### 3. Time to first audio (`tts_first_byte_ms`)

Today the clock stops after the entire sentence MP3 exists (`EdgeTTSService.synthesize_stream` buffers every `audio` chunk, then yields once).

- Inside `synthesize_stream`, record `tts_vendor_first_chunk` on the first `chunk["type"] == "audio"` before writing the buffer.
- In `_synthesize_and_send`, record `tts_ws_send` on the first `connection.send_audio`.
- Report both: `tts_vendor_first_chunk_ms` and `tts_first_byte_ms` (socket send). The second is what the browser can start decoding.
- On the client, stamp `playback_start` in `AudioPlayer` when `onPlaybackStart` fires. `playout_ms = playback_start - tts_ws_send` needs the server timestamp on a small JSON frame sent just before the binary MP3, or a client-side stamp taken when `_handleBinary` runs. Client decode (`decodeAudioData`) is inside that gap.

## How to store it without claiming a baseline

- Add the stage fields to the `latency_report` payload only. The UI already stores `message.data` on `latency`.
- Optional next step: JSONB `messages.latency_breakdown` next to the existing `latency_ms` integer. Do not backfill zeros into `CallLog`.
- Log one structlog event per turn, `pipeline_latency`, with the three clocks and `session_id`. That is enough to compute percentiles later. This plan does not add Prometheus; the dependency is unused.

## What a first experiment should hold constant

When keys are available, one manual call is not a distribution. For each turn record: STT mode, agent id, whether a tool ran, sentence count, and `INSECURE_SKIP_TLS_VERIFY`. Compare browser STT and Deepgram on the same prompt before changing the sentence splitter or the TTS buffer. The serial `await` of `_synthesize_and_send` inside the token loop will dominate any client-side timer until that await is moved off the LLM reader.
