# Case-study evidence

Facts from this repository only. Each claim names the function that does the work. "Stored" means a column or route exists. "Runs" means a voice session or HTTP handler executes it.

History scanned: one commit on `main`, `9e1cbac` (`Initial project upload`), plus this branch. No other branches.

## Voice pipeline

Entry: `voice_websocket` in `backend/app/api/v1/websockets/voice.py`.

- Connect registers a `VoiceConnection` and sends `session_started`.
- Binary frames go to `AudioPipeline.process_chunk`. JSON frames go to `_handle_control_message`.
- `START_SESSION` calls `handle_session_start`. `END_SESSION` destroys the session. `INTERRUPT` calls `connection.cancel()` and `handle_interrupt`. `USER_TRANSCRIPT` calls `handle_user_transcript`. `CONFIG_UPDATE` logs and returns (TODO comment in `voice.py`).

`AudioPipeline.handle_session_start` (`backend/app/services/audio/pipeline.py`):

- Default `stt_mode` is `"browser"`. Deepgram starts only when `stt_mode == "deepgram"`.
- Agent lookup is `_resolve_agent`: UUID or slug against the `agents` table, else `AgentRegistry.get` (`backend/app/services/agent/agent_config.py`). Presets: `default` (Aria), `concise` (Echo), `creative` (Lyra), `technical` (Nova).
- TTS voice, rate, volume, and pitch from the row are copied onto `AudioSessionState`. Temperature, max tokens, model, memory, and workflow JSON are not copied.
- `tool_registry.get_openai_functions` builds the tool schema. An empty tool list becomes `None`, and `get_tools` treats `None` or `[]` as every registered tool (`backend/app/services/tools/registry.py`).
- `llm_service.create_session` stores a `SystemMessage` and the tool schema in process memory.
- `ConversationService.create_conversation` inserts a row. Exceptions are logged and the session continues.

Browser turn: `handle_user_transcript` echoes `transcript_final`, cancels `_current_llm_task` if one is running, and schedules `_run_llm_tts_pipeline`.

Deepgram turn: `DeepgramSTTSession` (`backend/app/services/stt/deepgram_stt.py`) opens `client.listen.v1.connect` with `interim_results=True`, `utterance_end_ms=1500`, `vad_events=True`, `endpointing=300`, `smart_format=True`, linear16, 16 kHz, mono. Partials call `_on_transcript_partial`. Finals call `_on_transcript_final`. The LLM starts only when `speech_final` is true. `UtteranceEnd` promotes a pending final that was not yet `speech_final`. `SpeechStarted` is a debug log. The audio queue holds 500 chunks and drops the oldest when full. A keepalive task sleeps 8 seconds. `stop()` waits up to 5 seconds. Missing `DEEPGRAM_API_KEY` logs `deepgram_no_api_key` and returns without connecting. The playground never selects this mode: `voice-store.ts` `startListening` sends `stt_mode: "browser"`.

LLM: `LLMService.generate_response` (`backend/app/services/llm/chat_service.py`).

- Client is a process-wide `AzureChatOpenAI` built from `azure_openai_endpoint`, `azure_openai_api_key`, `azure_openai_deployment` (default `gpt-4o`), `api_version` `2024-02-01`, `azure_openai_temperature` (default 0.2), `azure_openai_max_tokens` (default 4096), `streaming=True`.
- The user text is appended, then `astream` yields content. Tool calls are collected from the merged chunk. Up to `MAX_TOOL_ROUNDS = 5`. Each call is `tool_executor(name, args)`, then a `ToolMessage`, then another stream. On exception the generator yields the string `I'm sorry, I encountered an error. Could you try again?`
- `trim_history` keeps the system message plus the last `max_messages - 1` (default 20). No caller references it.

TTS: `EdgeTTSService.synthesize_stream` (`backend/app/services/tts/edge_tts_service.py`) collects every MP3 chunk for the sentence, then yields the buffer once. `_split_sentence` will not cut before 40 characters, and only on `.!?` followed by a space, or a newline after 40 characters. `_run_llm_tts_pipeline` `await`s `_synthesize_and_send` before reading more tokens.

Client:

- `useSpeechRecognition` (`frontend/src/hooks/use-speech-recognition.ts`): `continuous`, `interimResults`, language `en-US`, silence timer default 1500 ms that finalizes the last interim text.
- `useVoiceStore.sendUserTranscript` appends the user line and sets `voiceState` to `processing`.
- Binary frames go to `AudioPlayer.enqueue`, which `decodeAudioData`s a complete MP3 (`frontend/src/lib/audio-player.ts`).
- Avatar state is derived in `PlaygroundInner`: `processing` → `thinking`, `speaking` → `speaking`, `listening` → `listening`. `speaking` is set from `audioPlayer.onPlaybackStart`, not from the first token. `onPlaybackEnd` returns to `listening` (`voice-store.ts`).
- `useFaceTracking` drives the SVG eyes while the session is active (`frontend/src/components/ai-avatar.tsx`). The mouth cycles a fixed viseme list during `speaking`. It is not phoneme-aligned to the MP3.

### Interruptions

Implemented, not wired to the playground button path:

- Server: `WSMessageType.INTERRUPT` → `handle_interrupt` cancels `_current_llm_task` and clears `_is_speaking`. STT is left running. The pipeline loop also breaks when `connection.is_cancelled`.
- A later `user_transcript` or Deepgram `speech_final` also cancels the current task before starting another.
- Client store: `sendInterrupt` calls `audioPlayer.stop()` and sends `interrupt`. No component in `frontend/src` calls `sendInterrupt`. Speech recognition is not stopped while the avatar is speaking, so a new final transcript can cancel the server and still leave decoded audio playing.
- `vad_event` is defined in `websocket/events.py` and imported in `pipeline.py`. Nothing sends it. Deepgram VAD events are not forwarded.

## Agent lifecycle

Twelve handlers on `backend/app/api/v1/routes/agents.py`, mounted at `/api/v1/agents`.

| # | Handler | Method and path | What it does |
| --- | --- | --- | --- |
| 1 | `create_agent` | POST `/agents` | Inserts `Agent` and `AgentVersion` 1 with `config_snapshot`. |
| 2 | `list_agents` | GET `/agents` | Non-templates. Optional status, category, name search. |
| 3 | `list_templates` | GET `/agents/templates` | `is_template == True`. |
| 4 | `list_voices` | GET `/agents/voices` | Returns `VOICE_CATALOG` from `schemas/agent.py`. No network call. |
| 5 | `get_agent` | GET `/agents/{id}` | UUID, else slug. |
| 6 | `update_agent` | PUT `/agents/{id}` | Applies fields. New version only if `change_note` is non-empty. |
| 7 | `delete_agent` | DELETE `/agents/{id}` | Deletes the row. Versions cascade. |
| 8 | `duplicate_agent` | POST `/agents/{id}/duplicate` | New draft copy, version 1. This is the studio clone. |
| 9 | `publish_agent` | POST `/agents/{id}/publish` | Sets `AgentStatus.ACTIVE`. No snapshot. |
| 10 | `list_versions` | GET `/agents/{id}/versions` | Version descending, snapshot included. |
| 11 | `rollback_agent` | POST `/agents/{id}/rollback/{version}` | Copies snapshot keys onto the row, increments `current_version`, inserts a new snapshot. |
| 12 | `get_analytics` | GET `/agents/{id}/analytics` | Counts and recent `CallLog` rows. |

There is no handler named clone on this router. Marketplace clone is separate (`clone_marketplace_agent`).

The agent editor (`frontend/src/app/agents/[id]/page.tsx`) calls get, update, publish, delete, versions, rollback, voices, and analytics. The list page calls `agentApi.list`. The create page calls `agentApi.create`. `agentApi.duplicate` and `agentApi.templates` have no caller.

### Snapshots and rollback

`_agent_to_snapshot` writes name, description, category, system prompt, welcome message, TTS fields, language, llm model, temperature, max tokens, top_p, tools, memory, and workflow config.

`AgentVersion` (`backend/app/models/agent.py`) has no update route. Immutability is "the API never edits a row", not a database revoke or trigger.

Rollback does not delete later versions. It creates a higher version whose snapshot is the old one. If `change_note` was omitted on earlier saves, those edits exist only on the live row and are missing from history.

`created_by` exists on `Agent` and `AgentVersion` and is not set by these handlers.

## Memory

`Agent.memory_config` is JSONB. `AgentCreate` defaults to `{type: window, window_size: 20, summarize: false, max_context_tokens: 8000}` (`schemas/agent.py`). The editor can change it. `_resolve_agent` does not read it. History is a Python list on `LLMService._conversations` for the life of the process. It grows by one user message and one assistant message per turn, plus tool messages. Nothing summarizes. Restarting the process drops it. The database messages are not reloaded into the LLM on the next session.

## Tools and permissions

Registered in `register_builtin_tools` during lifespan (`backend/app/core/events.py`):

- `GetCurrentTimeTool` uses `zoneinfo`. Unknown zones fall back to UTC.
- `GetWeatherTool` docstring says simulated data. Eight cities are fixed. Other cities use `sum(ord(c) for c in city)`.
- `CalculatorTool` checks the expression against `^[\d\s\+\-\*/\.\(\)\,\^a-zA-Z_]+$`, replaces `^` with `**`, and `eval`s with `__builtins__` empty and a math whitelist.

Enforcement:

- The model only receives the JSON schema from `get_openai_functions`.
- `_execute_tool` does not check that the name was in the agent allow-list. It runs any registered tool the executor is given.
- Empty `enabled_tools` means all tools, not none (`pipeline.py`: `agent.tools if agent.tools else None`).
- `tools_config.custom_tools` is not read.
- HTTP `GET /tools` lists the registry. There is no invoke endpoint.
- The client is notified with `tool_call_start` and `tool_call_result`.

## Errors, retries, timeouts

No retry library and no retry loop around Azure, Deepgram, or Edge TTS.

| Site | Behavior |
| --- | --- |
| `generate_response` | Logs `llm_generation_error`, yields one apology sentence. |
| `_run_llm_tts_pipeline` | Logs `pipeline_llm_tts_error`. Does not send a WebSocket error frame. `CancelledError` is logged at info. |
| `synthesize_stream` | Logs `tts_synthesis_error` and yields nothing. |
| Deepgram `start` | Failure is caught in `handle_session_start`; the session continues with `stt_session = None`. |
| Deepgram `stop` | `asyncio.wait_for` 5 s, then cancel. |
| Deepgram recv | `wait_for` 2 s, then loop. |
| DB writes in the pipeline | Caught, logged, ignored. |
| `voice_websocket` | Unexpected errors send `INTERNAL_ERROR` and then `destroy_session`. |
| `ConnectionManager._heartbeat_loop` | Ping every 15 s. Disconnect if `ping_age_seconds > 45` or `idle_seconds > 300`. |
| Redis client | `socket_connect_timeout=5`, `socket_timeout=5`, `retry_on_timeout=True` (`backend/app/db/redis.py`). |
| HTTP exceptions | `VoiceAIError` subclasses map to JSON. `RateLimitError` is never raised. |

`STTError`, `TTSError`, and `LLMError` are defined in `exceptions.py` and not raised by the pipeline.

## Analytics

Written on the voice path:

- `Conversation.total_duration_ms` from session uptime at destroy.
- `Conversation.message_count` and `total_tokens`. `token_count` in the pipeline is the number of streamed text chunks, not tokenizer tokens.
- `Message.latency_ms` is the whole pipeline clock for the assistant turn.
- `Message.stt_confidence` and `audio_duration_ms` are parameters on `add_message` and are not passed by the pipeline.
- `latency_report` on the socket (see `docs/latency-instrumentation.md`). `stt_ms` is 0.

Not written:

- `CallLog` inserts. `Agent.total_calls`, `total_duration_ms`, and `avg_rating` stay at the column default unless something outside this process updates them.
- `get_analytics` therefore reports zeros for percentiles and an empty `top_intents`, and `calls_today` / `calls_this_week` stay 0 until a `CallLog` exists.
- The analytics page sums `total_calls` and `total_duration_ms` from `GET /agents`. It does not call `/analytics`.

Ratings that do run: `rate_marketplace_agent` updates `MarketplaceAgent.avg_rating` from posted 1–5 scores. That is not the agent studio `avg_rating`.

Evaluations: `create_evaluation` stores the floats in the body, including `judge_model` default `gpt-4o`. It does not call a model. The evaluations page uses `MOCK_EVALS` and does not call the API. Calls, coaching, knowledge, and marketplace pages use the same pattern (`MOCK_CALLS`, `MOCK_SESSIONS`, `MOCK_KBS`, `MOCK_AGENTS`).

## Auth

`backend/app/core/security.py`:

- `hash_password` / `verify_password` use `bcrypt` if importable, else SHA-256 of the password with no salt.
- Access and refresh tokens are HS256 JWTs signed with `jwt_secret_key`.
- `get_current_user` returns `TokenPayload(sub="dev-user", email="dev@localhost", role="admin")` when `auth_enabled` is false.
- The only route that depends on it is `GET /auth/me`.
- `require_admin` is unused.
- Register and login write the `users` table (`backend/app/api/v1/routes/auth.py`). They are open when the process is reachable.

`UserRole` has `admin`, `operator`, `viewer`. Nothing checks operator or viewer.

## Tests

| File | Covers |
| --- | --- |
| `backend/tests/test_health.py` | GET `/api/v1/health` returns `healthy`. GET `/api/v1/metrics` has `active_connections` and `total_served`. |
| `backend/tests/test_websocket_manager.py` | Connect/disconnect, duplicate session id replacement, cancel flag, empty metrics. |
| `backend/tests/test_config.py` | Development JWT is generated, production JWT is required, database credential is required. |

`conftest.py` builds an httpx `AsyncClient` and a Postgres session fixture. No test uses `db_session`. No test opens a voice socket.

## Decisions that matter, and where time goes

These are structural, not benchmark results.

1. Browser STT is the default, with a 1500 ms silence fallback, specifically to avoid a proxy in front of Deepgram (`use-speech-recognition.ts` module comment: "No external API calls, no proxy issues."). Deepgram's 300 ms endpointing never runs on the playground path. Server `stt_ms` is hardcoded 0, so this wait is invisible.
2. Sentence TTS is synchronous inside the token loop (`_run_llm_tts_pipeline`). The next token is not read until Edge TTS has finished the current sentence and the MP3 has been sent. `synthesize_stream` also buffers the whole MP3 before the first yield. First audio cannot start until both the 40-character splitter and a full synthesis have finished.
3. Avatar state follows playback, not tokens (`voice-store.ts` comments and `AudioPlayer.onPlaybackStart`). The UI can show a transcript while the avatar is still `thinking`, which matches the buffer above. The visemes are a timer, not the audio.
4. Version history is an append-only JSON snapshot, and only when the client sends `change_note`. Rollback is "copy forward", so the version number always increases. That is a real audit trail for the fields inside `_agent_to_snapshot`, and a hole for saves that omit the note.
5. The Azure client is one object per process, built from environment temperature and max tokens. Per-agent knobs in the studio do not change the call. Tool rounds run inline, so a weather or calculator call sits on the critical path before more speech is streamed.
6. Sockets, LLM histories, and the tool registry live in the process. Redis pub/sub is optional and off. `ConnectionManager`'s own docstring still says cross-instance delivery is Phase 12. `events.py` does start a broadcaster when `use_redis` is true.
7. HTTP middleware is hand-written ASGI so WebSocket upgrade is not wrapped (`middleware.py`). Request IDs and `x-response-time-ms` apply to HTTP only.

Likely latency bottlenecks, in causal order, with no timings attached:

1. Serial TTS await inside the LLM reader.
2. Full-sentence MP3 buffering before the first socket byte, after a 40-character gate.
3. Browser end-of-speech detection plus the 1500 ms silence timer, unmeasured on the server.
4. Tool rounds blocking the same stream (up to 5), on the same task as speech.
5. Session-start database work (`_resolve_agent`, `create_conversation`) and a global 4096 max-token setting that the voice prompts themselves say should be one to three sentences. The pool size does not fix the serial await.

## Security notes relevant to a public write-up

See the pull request for the scan. Do not describe the TLS bypass as a feature that is on by default. It is off unless `INSECURE_SKIP_TLS_VERIFY=true`. Do not quote the old database password or the old JWT default as configuration you still ship.
