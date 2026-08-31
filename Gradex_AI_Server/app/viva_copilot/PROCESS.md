# Live Interviewer Copilot — process document

Technical click-through for the isolated **Live Interviewer Copilot**. This is **not** Viva Assessment (upload/record-then-grade). The two features share only the sidebar group and FastAPI `include_router`.

| Product | UI | Backend | Engine |
|---|---|---|---|
| **Viva Assessment** | `VivaPage.tsx` | `POST /api/viva-analyze` | `VivaEvaluationEngine` + Mongo marks |
| **Live Interviewer Copilot** | `viva-copilot/*` | `/api/viva-copilot/*` | In-memory session + Groq STT/chat, **plus** `VivaEvaluationEngine` + Mongo marks at end-of-session analyze |

**During the session** the copilot does not write Mongo and does not score the student: the live
path is STT + follow-up-question suggestion only, held in `SessionStore` in RAM.

**At end of session** that changed. `POST /sessions/{id}/analyze` (`analysis.py::analyze_live_session`)
runs the **same** scoring chain as an uploaded recording — via `viva_analysis_runner`, which calls
`viva_service.analyze_video_file` — and persists a mark to Mongo. The only live-specific
differences are `source="live_copilot"`, the `copilot_session_id`, and the live transcript
attached as `live_session` / `live_transcript`. Scoring itself is identical, so a live viva and an
uploaded one are graded on the same basis.

Scoring is still driven by the **recording**, not the live transcript: the Stage-1 families
(engagement CNN, Praat acoustics, face coverage) are all video/waveform-derived, and the quality
gates in `assessment_scoring` depend on them, so a transcript-only mark would be voided.

---

## 1. How to run

| Process | Command | Default |
|---|---|---|
| FastAPI | From repo root: `.venv\Scripts\python.exe -m uvicorn Gradex_AI_Server.app.main:app --host 0.0.0.0 --port 8000` | **8000** (do not use `--reload`) |
| Vite client | `Gradex_AI_Client` → `npm run dev` | **5173** |
| Open | Lecturer login → **Viva Evaluation → Live Interviewer Copilot** | `http://localhost:5173/viva-evaluation/live-copilot` |

Env:

- Client: `VITE_BACKEND_URL` (fallback `http://localhost:8000`) and `VITE_GRADEX_API_KEY` (must match server `GRADEX_API_KEY`).
- Server: `Gradex_AI_Server/app/.env` — `GRADEX_API_KEY`, `AI_API_KEY` or `GROQ_API_KEY`. Optional `VIVA_COPILOT_LLM_MODEL` (fallback `openai/gpt-oss-20b`; Llama chat ids retired 16 Aug 2026), `VIVA_COPILOT_STT_MODEL`.
- REST sends `X-API-Key`. WebSocket uses `?api_key=`.
- STT chunks queue FIFO (cap 8). Follow-up LLM jobs queue (cap 4). Oldest is dropped only if the cap is exceeded.

Restart uvicorn after Python changes. Restart Vite after changing `.env.local`.

---

## 2. Architecture

```
Browser (LiveCopilotPage)
  │
  │ REST  (lecturer buttons only)
  │   POST /api/viva-copilot/sessions
  │   POST /sessions/{id}/phase | /finalize | /ask | /context
  │   POST /sessions/{id}/analyze   (end of session — grades + saves the mark)
  │   GET  /sessions/{id}/transcript
  │   DELETE /sessions/{id}
  │
  │ WebSocket  (live path — no polling)
  │   WS  /api/viva-copilot/ws/{id}
  │   → binary audio slices (~4s WebM, Groq Whisper accuracy backstop)
  │   → JSON {"type":"speech", text, isFinal} (Web Speech API, fast path)
  │   ← JSON events (transcript, suggestions, errors)
  │
  ▼
Gradex_AI_Server  (FastAPI, port 8000)
  router.py  →  pipeline.py  →  session_store.py  (RAM dict — live phase only)
       │             │
       │             ├─ ingest_text()     → bypasses STT entirely (fast path)
       │             ├─ stt.py            → Groq Whisper  POST .../audio/transcriptions (pooled httpx client)
       │             └─ followup_llm.py   → Groq Chat  POST .../chat/completions (streamed, pooled httpx client)
       │
       └─ /analyze → analysis.py::analyze_live_session
                          → viva_analysis_runner.run_analysis
                              → viva_service.analyze_video_file   (VivaEvaluationEngine)
                          → attach_subject_technical_accuracy     (optional, advisory)
                          → persist_and_autopublish               (Mongo: vivamark.marks)
```

**Why WebSocket for live work:** the browser never polls. Audio and suggestion delivery stay on one socket. REST is only for explicit lecturer actions (create, phase, ask, end). The “database” for the *live* phase is `SessionStore` in RAM — Mongo is not touched while the session is running. It is written once, at the end, by `POST /sessions/{id}/analyze` (see §2 above).

**Latency optimizations (dual-path transcription + streaming):**

- **Browser Web Speech API (`CopilotCamera.tsx`)** produces interim/final transcripts with near-zero network latency and sends them as JSON text frames (`{"type":"speech", ...}`) over the same WebSocket. `pipeline.ingest_text()` consumes these directly — no Groq Whisper round-trip needed for the fast path. Supported in Chromium-based browsers; unsupported browsers silently fall back to Whisper-only.
- **Groq Whisper (`stt.py` / `groq_client.py`)** keeps running on 4s audio slices in parallel as an accuracy backstop (technical vocabulary, unclear audio, unsupported browsers). Both paths call the same `detect_final_answer()` de-dupe logic, so whichever finalizes an utterance first "wins" and the other is naturally ignored as a duplicate.
- **Persistent `httpx.Client`** (module-level, connection-pooled) replaces per-request `urllib.urlopen()` calls for both STT and chat completions, removing repeated TCP/TLS handshake overhead.
- **Streamed chat completions** (`groq_chat(..., on_delta=...)`) let `followup_llm.generate_followups()` detect and emit the *first* valid suggestion object as soon as it appears in the SSE token stream, broadcast via a new `followup.suggestion.partial` event — well before the full 2-3 suggestion JSON response finishes.
- **Tuned timers:** `SLICE_MS` (client audio slice) 2500→4000ms, `AUTO_FINALIZE_IDLE_MS` 2200→1200ms, `VIVA_COPILOT_MIN_STT_GAP` 1.2→0.4s, presentation refresh threshold 6 words/5s → 5 words/3s.

---

## 3. Files

### Frontend (`Gradex_AI_Client/src/app/components/viva-copilot/`)

| File | Role |
|---|---|
| `LiveCopilotPage.tsx` | Buttons, WS client, toast stack, applies events |
| `CopilotCamera.tsx` | Camera preview + 12s `MediaRecorder` slices |
| `copilotApi.ts` | REST helpers + WS URL |
| `SuggestionToasts.tsx` | Top-right stacked popups |
| `SuggestionPanel.tsx` | Persistent suggestion list + Ask |
| `CopilotTranscript.tsx` | Live transcript |
| `CopilotErrorBoundary.tsx` | Catches render crashes |

Route: `routeConfig.tsx` → path `/viva-evaluation/live-copilot`.

### Backend (`Gradex_AI_Server/app/viva_copilot/`)

| File | Role |
|---|---|
| `router.py` | FastAPI REST + WebSocket |
| `pipeline.py` | STT ingest → pause detect → bulk LLM |
| `session_store.py` | In-memory `CopilotSession` + `broadcast()` |
| `stt.py` | Whisper wrapper + hallucination filter |
| `groq_client.py` | Multi-provider LLM HTTP (Groq/Gemini/OpenRouter chain; not `llm_judge.py`) |
| `followup_llm.py` | Chat prompt → JSON suggestions (max 3) |
| `answer_detector.py` | Min words, duplicate hash |
| `context_builder.py` | Sliding context (last 5 Q/A, 4000-char excerpt) |
| `events.py` | WS event payloads |

Mounted in `Gradex_AI_Server/app/main.py`: `app.include_router(viva_copilot_router)`.

---

## 4. Click-by-click process

Phases: `idle` → `presentation` → `viva` → `ended`.

### Step 0 — Open the page

| Actor | Action |
|---|---|
| User | Sidebar **Viva Evaluation → Live Interviewer Copilot** |
| Client | Renders `LiveCopilotPage`. No network yet. |
| Server | Idle. |

Optional fields (Project / Module / Notes) stay in React state until Create or Save notes.

---

### Step 1 — Enable camera

| Actor | Action |
|---|---|
| User | **Enable camera** on `CopilotCamera` |
| Client | `navigator.mediaDevices.getUserMedia({ video, audio })`. Preview only. **No STT yet.** |
| Server | Not called. |

Transcription starts only after a session exists **and** phase is `presentation` or `viva` **and** the WebSocket is open (`streaming && wsReady`).

---

### Step 2 — Create session

| Actor | Action |
|---|---|
| User | **Create session** |
| Client | `POST {VITE_BACKEND_URL}/api/viva-copilot/sessions` body `{ projectContext }` |
| Server | `router.create_session` → `store.create()` → `{ sessionId: "session_<12 hex>", phase: "idle" }` |
| Client | `new WebSocket(ws://…/api/viva-copilot/ws/{sessionId})` |
| Server | Accept WS, register socket on session, push `session.state` snapshot |

**Groq:** none. **Mongo:** none.

---

### Step 3 — Save notes (optional, after session exists)

| Actor | Action |
|---|---|
| User | **Save notes** |
| Client | `POST /api/viva-copilot/sessions/{id}/context` |
| Server | Overwrites `session.project_context` in RAM |

Used later as LLM context. No Groq call.

---

### Step 4 — Start presentation

| Actor | Action |
|---|---|
| User | **Start presentation** (enabled only when `phase === "idle"`) |
| Client | `POST /sessions/{id}/phase` `{ "phase": "presentation" }` |
| Server | `start_presentation()` → `session.phase = "presentation"` → WS `session.phase` |
| Client | `streaming` becomes true. Camera records **4s** audio slices (`SLICE_MS = 4000`) and, in parallel, runs the browser Web Speech API for instant interim/final text. |

Each audio slice: `MediaRecorder` → `Blob` → `WebSocket.send(ArrayBuffer)` (binary, not JSON).
Each speech result: `WebSocket.send(JSON.stringify({type:"speech", text, isFinal}))` (text frame, fast path — see §2).

---

### Step 5 — Student talks (automatic loop)

This is the live path. No extra clicks.

```
Camera 12s WebM
  → WS binary
  → router.copilot_ws
  → pipeline.ingest_audio_chunk
       if STT already busy: enqueue FIFO (cap 8 slices; drop oldest only if full)
       else asyncio.to_thread(stt.transcribe_chunk)
            → groq_client.groq_transcribe
               POST https://api.groq.com/openai/v1/audio/transcriptions
               model whisper-large-v3-turbo (or VIVA_COPILOT_STT_MODEL)
               min gap 4s between STT calls; retry once on HTTP 429
       if text: append utterance_buffer, WS transcript.partial
       if empty after speech (pause): _finalize_utterance
```

**Finalize utterance (presentation):**

1. `detect_final_answer` — ≥4 words, not a duplicate hash.
2. Append to `presentation_parts`, WS `transcript.final`.
3. `_maybe_presentation_followups` — **bulk LLM, not every slice.**

LLM runs only if:

- presentation word count ≥ **28**
- **≥28 new words** since last LLM
- **≥40 seconds** since `last_suggest_at`

Then:

```
followup_llm.generate_followups
  → groq_client.groq_chat (provider chain: Groq -> Gemini -> OpenRouter)
     POST to whichever provider has a configured key and available model
     default Groq model openai/gpt-oss-20b
     fallbacks: openai/gpt-oss-120b, qwen/qwen3.6-27b
  → JSON { analysis, main_points, suggestions[≤3] }
  → WS presentation.points.extracted
  → WS followup.suggestions.generated
```

**UI on `followup.suggestions.generated`:**

- Side panel `SuggestionPanel` updates.
- Top-right `SuggestionToasts`: new cards **prepended**, older cards **push down**, max **6**, auto-dismiss **16s**. **Ask this** or dismiss.

**Groq load while presenting (free tier):**

| API | Cadence | Approx RPM |
|---|---|---|
| Whisper | ~1 per 12s audio + 4s server gap | ~5 (limit ~20) |
| Chat | ~1 per 40s **and** 28 new words | far below chat RPM |

Not one LLM call per STT chunk.

---

### Step 6 — Panel enters / start viva

| Actor | Action |
|---|---|
| User | **Panel enters / start viva** (only in `presentation`) |
| Client | `POST /sessions/{id}/finalize` then `POST /sessions/{id}/phase` `{ "phase": "viva" }` |
| Server | Flush leftover buffer into presentation text. Set `phase = viva`. |
| Server | If suggestions exist and last LLM was **&lt;90s** ago: **no second Groq chat** — rebroadcast existing suggestions over WS. Else run LLM once on full presentation. |

Audio slices continue over the same WebSocket.

---

### Step 7 — Viva answers (automatic + optional click)

After a finalized pause (≥5 words, not duplicate):

1. WS `candidate.answer.final`
2. Pair with `currentQuestion` into `recent_qa` (max 5 pairs)
3. **One LLM call** for that answer (queued FIFO, cap 4, if `busy_llm`)
   Ask this is REST **409** during presentation / idle.
4. WS `followup.suggestions.generated` → toasts + panel

**Answer complete** (optional): `POST /sessions/{id}/finalize` forces flush of `utterance_buffer` if the pause detector is slow.

---

### Step 8 — Ask this

| Actor | Action |
|---|---|
| User | **Ask this** on a toast or the side panel |
| Client | `POST /sessions/{id}/ask` `{ "question": "…" }` |
| Server | **409** unless `phase === viva`. Else `ask_question()` — sets `currentQuestion`, appends interviewer turn, WS `interviewer.question.asked` + `transcript.final` (speaker interviewer) |
| Client | Pins the question; dismisses matching toast |

**Groq:** none. Human-in-the-loop: the AI never asks the student.

---

### Step 9 — End session

| Actor | Action |
|---|---|
| User | **End session** |
| Client | Close WebSocket, `DELETE /sessions/{id}` |
| Server | WS `session.phase` = `ended`, `store.delete(id)` — RAM gone |

---

## 5. REST vs WebSocket

| Channel | When | Who starts it |
|---|---|---|
| REST | Create, save notes, start presentation, panel enters, answer complete, Ask this, end | Lecturer click |
| WebSocket binary | 12s audio | Camera loop |
| WebSocket JSON | Transcript, points, suggestions, errors, phase, snapshot | Server `broadcast()` |

There is **no** `setInterval` poll of `/sessions/{id}` during the live session. `GET /sessions/{id}` exists for debug/reconnect snapshots; the page uses WS `session.state` on connect instead.

---

## 6. WebSocket event catalog

| `event` | Direction | UI effect |
|---|---|---|
| `session.state` | S→C on connect | Restore phase, transcript, suggestions |
| `session.phase` | S→C | `idle` / `presentation` / `viva` / `ended` |
| `transcript.partial` | S→C | Grey in-progress line |
| `transcript.final` | S→C | Append turn |
| `presentation.points.extracted` | S→C | Main-points list |
| `followup.suggestion.partial` | S→C | First suggestion, streamed early (before the full LLM turn finishes) |
| `followup.suggestions.generated` | S→C | Panel + **top-right toasts** |
| `candidate.answer.final` | S→C | Answer id (viva) |
| `interviewer.question.asked` | S→C | Current question banner |
| `copilot.error` | S→C | Error card + sonner toast (throttled) |
| `pong` | S→C | Reply to text `ping` |

---

## 7. Session object (RAM)

`CopilotSession` in `session_store.py`:

- `phase`, `project_context`
- `presentation_parts`, `main_points`, `analysis`, `suggestions`
- `utterance_buffer`, `transcript_log` (capped 200)
- `current_question`, `asked_questions`, `recent_qa`
- `ws_clients`, `busy_llm`, `stt_busy`, `pending_audio` (deque), `pending_followups`
- `last_suggest_at`, `last_suggest_word_count`
- `created_at`, `last_activity_at` — idle expiry via `VIVA_COPILOT_SESSION_TTL_SECONDS` (default **14400** = 4 h). Set **0** to disable. Purged on `store.get()` / `store.create()` and when WebSocket or STT sees an expired session.

Lost on process restart. Not written to Mongo.

---

## 8. LLM providers and keys (multi-provider chain)

Chat completions use a **Groq → Gemini → OpenRouter** free-tier fallback chain.
No local gateway (`localhost:20128`) is required — all providers are remote APIs.

Loaded from `Gradex_AI_Server/app/.env` by `groq_client._load_env()`.

| Provider | Base URL | Key search order | Default models |
|---|---|---|---|
| **Groq** | `https://api.groq.com/openai/v1/chat/completions` | `VIVA_COPILOT_API_KEY`, `VIVA_LLM_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, `BACKUP_API_KEY` | `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b` |
| **Gemini** | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `GEMINI_API_KEY`, `GOOGLE_API_KEY` | `gemini-2.0-flash`, `gemini-1.5-flash` |
| **OpenRouter** | `https://openrouter.ai/api/v1/chat/completions` | `OPENROUTER_API_KEY` | `meta-llama/llama-3.1-8b-instruct:free`, `google/gemma-2-9b-it:free`, `mistralai/mistral-7b-instruct:free` |

- If a provider has **no key configured**, it is skipped entirely.
- Within each provider, every model candidate is tried; 404/429/5xx triggers the next candidate.
- When all models of a provider fail, the chain moves to the next provider.
- Override default models with `VIVA_COPILOT_LLM_MODEL` (Groq preferred), `GEMINI_MODEL`, `OPENROUTER_MODEL`.

**STT** stays on Groq Whisper only:

| Setting | Default |
|---|---|
| STT key search | `VIVA_COPILOT_STT_API_KEY`, `STT_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, ... |
| STT model | `VIVA_COPILOT_STT_MODEL` or `whisper-large-v3-turbo` |

Copilot **ignores** `GROQ_MODEL` used by other Gradex features.

---

## 9. Isolation rules (do not mix)

Do **not** import from:

- `VivaPage.tsx`, `components/viva/*`
- `viva_service.py`
- `VivaEvaluationEngine`

Glue only: `routeConfig.tsx` + `app.include_router` in `main.py`.

---

## 10. Tests

From repo root:

```
python -m unittest Gradex_AI_Server.app.viva_copilot.tests.test_copilot_pipeline
```

Covers answer detection, context builder, presentation bulk-refresh gates, panel-enter skip of a second LLM when suggestions are fresh.
