# Live Viva (Live Interviewer Copilot) — process document

Technical click-through for the **Live Viva** feature (`/viva-evaluation/live-copilot`). It sits beside **Viva Assessment**
(upload a recording, then grade) and ends in the same grading chain.

| Product | UI | Backend | Engine |
|---|---|---|---|
| **Viva Assessment** | `VivaPage.tsx` | `POST /api/viva-analyze` | `VivaEvaluationEngine` + Mongo marks |
| **Live Viva** | `viva-copilot/*` | `/api/viva-copilot/*` | In-memory session + Groq STT/chat while live, then `VivaEvaluationEngine` + Mongo marks at end-of-session analyze |

**During the session** the copilot does not write Mongo and does not score the student. The live path is speech-to-text plus
follow-up-question suggestions for the examiner, held in `SessionStore` in RAM. The AI never asks the student anything; the
examiner decides what to ask.

**At end of session** `POST /sessions/{id}/analyze` (`analysis.py::analyze_live_session`) runs the **same** scoring chain as an
uploaded recording, through `viva_analysis_runner` and `viva_service.analyze_video_file`, then saves a mark to Mongo. The only
differences are `source="live_copilot"`, the `copilot_session_id`, and the live transcript attached as `live_session` /
`live_transcript`. Scoring is driven by the **recording**, not the live transcript: the Stage-1 families (engagement CNN, Praat
acoustics, face coverage) are video/waveform-derived and the quality gates depend on them, so a transcript-only mark would be voided.

A live session is always filed under a viva created in the Viva Workspace (`viva_id`). The viva fixes the category
(technical or non-technical), the subject, the total marks and, for technical vivas, the technical percentage.

---

## 1. How to run

| Process | Command | Default |
|---|---|---|
| FastAPI | From repo root: `.venv\Scripts\python.exe -m uvicorn Gradex_AI_Server.app.main:app --host 0.0.0.0 --port 8000` | **8000** (do not use `--reload`) |
| Vite client | `Gradex_AI_Client` → `npm run dev` | **5173** (proxies `/api`, including WebSockets) |
| Open | Lecturer login → **Viva Evaluation → Live Viva** | `http://localhost:5173/viva-evaluation/live-copilot` |

Auth: a lecturer **login session cookie** (`gradex_session`). REST calls use `apiFetch`; the WebSocket sends the same cookie and
must come from a trusted `Origin`. There are no API keys in the browser. For plain-HTTP local development set
`AUTH_COOKIE_SECURE=false` on the server.

Server env (`Gradex_AI_Server/app/.env`, see `.env.example`):

- LLM key: first set of `VIVA_COPILOT_API_KEY`, `VIVA_LLM_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, `BACKUP_API_KEY`.
- `VIVA_COPILOT_LLM_MODEL` (default `openai/gpt-oss-20b`), `VIVA_COPILOT_STT_MODEL` (default `whisper-large-v3-turbo`).
- `VIVA_COPILOT_MIN_STT_GAP` (default `0.4` s), `VIVA_COPILOT_SESSION_TTL_SECONDS` (default `14400`, `0` disables expiry).
- Cadence: `COPILOT_SUGGEST_MIN_WORDS` (15), `COPILOT_SUGGEST_MIN_SECONDS` (8), `COPILOT_VIVA_SUGGEST_MIN_WORDS`,
  `COPILOT_VIVA_SUGGEST_MIN_SECONDS`, `COPILOT_MIN_ANSWER_WORDS` (6).
- `VIVA_KEEP_UPLOADS=1` keeps the end-of-session recording for debugging (it is deleted otherwise).

Restart uvicorn after Python changes and Vite after changing `.env.local`.

---

## 2. Architecture

```
Browser (LiveCopilotPage + CopilotCamera)
  │
  │ REST  (lecturer buttons only)
  │   POST   /api/viva-copilot/sessions
  │   POST   /sessions/{id}/phase | /finalize | /ask | /context
  │   POST   /sessions/{id}/analyze      (end of session: grades and saves the mark)
  │   GET    /sessions/{id} | /sessions/{id}/transcript
  │   DELETE /sessions/{id}
  │
  │ WebSocket  (live path, no polling)
  │   WS  /api/viva-copilot/ws/{id}
  │   → binary audio slices (~4 s WebM, Groq Whisper backstop)
  │   → JSON {"type":"speech", text, isFinal} (browser Web Speech API, fast path)
  │   → text "ping"
  │   ← JSON events (transcript, suggestions, errors, phase)
  │
  ▼
Gradex_AI_Server  (FastAPI, port 8000)
  router.py  →  pipeline.py  →  session_store.py  (RAM dict, live phase only)
       │             │
       │             ├─ ingest_text()     → bypasses STT (fast path)
       │             ├─ stt.py            → Groq Whisper  POST .../audio/transcriptions
       │             └─ followup_llm.py   → chat completions (streamed)
       │
       └─ /analyze → analysis.py::analyze_live_session
                          → viva_analysis_runner.run_analysis
                              → viva_service.analyze_video_file   (VivaEvaluationEngine)
                          → attach_subject_technical_accuracy     (technical vivas, advisory)
                          → persist_and_autopublish               (Mongo marks collection)
```

**Why WebSocket for live work:** the browser never polls. Audio and suggestion delivery share one socket. REST is only for
explicit lecturer actions. The database for the *live* phase is `SessionStore` in RAM; Mongo is written once, at the end.

**Dual-path transcription:**

- **Browser Web Speech API** (`CopilotCamera.tsx`) gives interim and final text with near-zero latency, sent as `{"type":"speech"}`
  frames. `pipeline.ingest_text()` consumes them directly. Chromium-based browsers only; others fall back to Whisper only.
- **Groq Whisper** (`stt.py` / `groq_client.py`) runs on 4 s audio slices (`SLICE_MS = 4000`) in parallel as an accuracy backstop
  for technical vocabulary and unsupported browsers. A hallucination filter drops junk transcripts.
- Both paths call `detect_final_answer()`, which de-dupes by content hash and by prefix/overlap, so whichever path finalizes an
  utterance first wins.
- `CopilotCamera` also records the whole session (`MediaRecorder`, flushed every 5 s via `SESSION_TIMESLICE_MS`) so a crash still
  leaves a usable recording. That recording is what `/analyze` uploads.

**Streaming suggestions:** `groq_chat(..., on_delta=...)` lets `followup_llm.generate_followups()` emit the first complete
suggestion as soon as it appears in the token stream (`followup.suggestion.partial`), before the full response finishes.
HTTP clients are pooled (`httpx`).

---

## 3. Files

### Frontend (`Gradex_AI_Client/src/app/components/viva-copilot/`)

| File | Role |
|---|---|
| `LiveCopilotPage.tsx` | Page, Start Session / End buttons, WebSocket client, idle auto-finalize timer, suggestion panel and toasts (sonner), applies events, end-of-session upload and progress polling |
| `CopilotCamera.tsx` | Camera preview, 4 s audio slices, whole-session recorder, Web Speech API |
| `copilotApi.ts` | REST helpers, WebSocket URL, suggestion normalization |
| `CopilotErrorBoundary.tsx` | Catches render crashes |

Route: `routeConfig.tsx` → `/viva-evaluation/live-copilot` ("Live Viva").

### Backend (`Gradex_AI_Server/app/viva_copilot/`)

| File | Role |
|---|---|
| `router.py` | REST + WebSocket routes (lecturer-only; WebSocket checks session and `Origin`) |
| `pipeline.py` | STT ingest, pause detection, cadence gates, queues, follow-up generation |
| `session_store.py` | In-memory `CopilotSession`, `broadcast()`, idle expiry |
| `stt.py` | Whisper wrapper + hallucination filter |
| `groq_client.py` | Multi-provider LLM and STT HTTP (Groq → Gemini → OpenRouter) |
| `followup_llm.py` | Chat prompt → JSON suggestions (max 3) |
| `answer_detector.py` | Minimum words, exact and near-duplicate detection |
| `context_builder.py` | Sliding context (last 5 Q/A pairs, 4000-char excerpt, last 10 turns) |
| `events.py` | WebSocket event payloads |
| `analysis.py` | End-of-session transcript record and analyze chain |

Shared with Viva Assessment: `viva_sessions.py` (viva lookup, duplicate-mark check), `viva_analysis_runner.py` (the grading chain),
`viva_progress.py` (progress events), `viva_student_id.py`.

`VivaEvaluationEngine/services/live_question_recommender.py` is a standalone engine module with its own tests; the server does
**not** call it (the copilot uses `followup_llm.py`).

---

## 4. Click-by-click process

Server phases: `idle` → `presentation` → `viva` → `analyzing` → `analyzed` → `ended`.

**What the shipped UI does.** `LiveCopilotPage.tsx` uses a shortcut: **Start Session** creates the session and immediately sets the phase
to `viva` (it never uses `presentation`). There are no Save-notes, Panel-enters or Answer-complete buttons: the project context is a fixed
string, and an answer is finalized automatically when the partial transcript has been idle for 1.2 s (`AUTO_FINALIZE_IDLE_MS`, which calls
`POST /sessions/{id}/finalize`). The `presentation` phase, `/context`, and the 90 s skip rule below are still implemented on the server
and covered by tests, but only an API client that drives them would exercise them. Steps 3, 4 and 6 describe that server capability.

### Step 0 — Open the page
No network. Optional Project / Module / Notes stay in React state until Create or Save notes. The page needs a viva selected from
the Viva Workspace and a valid Student ID before a session is analyzed.

### Step 1 — Enable camera
`getUserMedia({ video, audio })`. Preview only. No STT yet. Transcription starts only once a session exists, the phase is
`presentation` or `viva`, and the WebSocket is open.

### Step 2 — Create session
`POST /api/viva-copilot/sessions` → `{ sessionId: "session_<12 hex>", phase: "idle" }`. The client opens
`WS /api/viva-copilot/ws/{sessionId}`; the server registers the socket and pushes `session.state`. No Groq, no Mongo.

### Step 3 — Save notes (server capability, no button in the current UI)
`POST /sessions/{id}/context` overwrites `project_context` in RAM; used later as LLM context.

### Step 4 — Start presentation (server capability; the current UI skips it)
`POST /sessions/{id}/phase {"phase":"presentation"}` (only from `idle`). Audio slices go over the socket as binary frames; Web
Speech results go as JSON text frames.

### Step 5 — Student talks (automatic loop)

```
Audio slice (4 s WebM) → WS binary → pipeline.ingest_audio_chunk
     if STT is busy: queue FIFO (cap 8; oldest dropped only when full, with an error event)
     else asyncio.to_thread(stt.transcribe_chunk) → Groq Whisper
     text → append to utterance_buffer, WS transcript.partial
     empty after speech (a pause) → _finalize_utterance
```

**Finalize utterance:** `detect_final_answer` keeps it only if it has at least **6 words** (`COPILOT_MIN_ANSWER_WORDS`) and is not a
duplicate. In `presentation` it is appended to `presentation_parts` and `transcript.final` is sent; then
`_maybe_presentation_followups` runs.

**Suggestion cadence (both phases).** The LLM runs only when there are at least **15 words** (new words, for presentation) and at
least **8 s** since the last request started (`COPILOT_SUGGEST_MIN_WORDS` / `COPILOT_SUGGEST_MIN_SECONDS`). The clock is stamped
when a request starts, so failures cannot cause bursts. A request that arrives while one is running is queued (cap 4), and the
queue is drained at the same spacing.

```
followup_llm.generate_followups
  → groq_client.groq_chat (provider chain: Groq -> Gemini -> OpenRouter)
  → JSON { analysis, main_points, suggestions[≤3] }
  → WS presentation.points.extracted
  → WS followup.suggestions.generated
```

The UI updates the suggestion panel (newest first, at most 6 kept) and shows a sonner toast ("New question suggested", 4.5 s); the examiner can **Ask this** or dismiss it.

### Step 6 — Panel enters / start viva (the current UI sets `viva` directly at Start Session)
`POST /sessions/{id}/finalize`, then `POST /sessions/{id}/phase {"phase":"viva"}`. Leftover buffered speech (4 or more words) is
added to the presentation. If suggestions exist and the last LLM call was under **90 s** ago, they are re-broadcast without a new
call; otherwise the LLM runs once on the full presentation. If there is no presentation transcript yet, an error event says
suggestions will wait for an answer.

### Step 7 — Viva answers
After each finalized answer: `candidate.answer.final` is sent and the answer is paired with `current_question` into `recent_qa`
(max 5 pairs). Answers accumulate in `pending_answer_parts`, and one LLM call covers the window once the cadence gate opens.
**Answer complete** (`POST /sessions/{id}/finalize`) forces a flush of the buffer.

### Step 8 — Ask this
`POST /sessions/{id}/ask {"question": "..."}`. Returns **409** unless the phase is `viva`. Sets `current_question`, logs an
interviewer turn, broadcasts `interviewer.question.asked` and `transcript.final` (speaker `interviewer`). No Groq call.

### Step 9 — End session and analyze
The client stops the recorder and uploads the whole recording to `POST /sessions/{id}/analyze` (multipart: `video`, `viva_id`,
`student_id`, optional `allow_duplicate`, `progress_id`). The server broadcasts phase `analyzing`, runs the grading chain, saves the
mark, then broadcasts `analyzed`. The Live Viva page polls `GET /api/viva-analyze/progress/{progress_id}` every 400 ms for the checklist (Viva Assessment uses the SSE `/stream` variant instead). Then the client
calls `DELETE /sessions/{id}`: the phase becomes `ended` and the RAM session is removed.

Notes on `/analyze`: it enforces the 1 GB cap and the viva ownership and duplicate-mark rules. A non-technical viva is auto-published;
a technical viva stays a draft until the examiner enters the technical score and publishes (Viva Results). If no recording was
captured the client shows "No recording was captured, so no score could be produced."

---

## 5. REST vs WebSocket

| Channel | When | Who starts it |
|---|---|---|
| REST | Create, notes, phase changes, answer complete, Ask this, analyze, end | Lecturer action |
| WebSocket binary | ~4 s audio slices | Camera loop |
| WebSocket JSON (client → server) | `speech` frames, `ping` | Browser speech recognition, keep-alive |
| WebSocket JSON (server → client) | Transcript, points, suggestions, errors, phase, snapshot | Server `broadcast()` |

There is no polling of `/sessions/{id}` during the live session; the page uses the WebSocket `session.state` on connect.

---

## 6. WebSocket event catalog

| `event` | Direction | UI effect |
|---|---|---|
| `session.state` | S→C on connect | Restore phase, transcript, suggestions |
| `session.phase` | S→C | `presentation` / `viva` / `analyzing` / `analyzed` / `ended` |
| `session.expired` | S→C | Session idle past its TTL; socket closes |
| `transcript.partial` | S→C | In-progress line |
| `transcript.final` | S→C | Append turn |
| `presentation.points.extracted` | S→C | Main-points list |
| `followup.suggestion.partial` | S→C | First suggestion, streamed early |
| `followup.suggestions.generated` | S→C | Suggestion panel and toast |
| `candidate.answer.final` | S→C | Answer id (viva phase) |
| `interviewer.question.asked` | S→C | Current question banner |
| `copilot.error` | S→C | Error card and toast (throttled) |
| `pong` | S→C | Reply to text `ping` |

---

## 7. Session object (RAM)

`CopilotSession` in `session_store.py`:

- `phase`, `project_context`
- `presentation_parts`, `main_points`, `analysis`, `suggestions`
- `utterance_buffer`, `pending_answer_parts`, `transcript_log` (capped at 200 turns; snapshots send the last 80)
- `current_question`, `asked_questions`, `recent_qa`, `recent_hashes`, `recent_texts`
- `ws_clients`, `busy_llm`, `stt_busy`, `pending_audio` (deque), `pending_followups`
- `last_suggest_at`, `last_suggest_word_count`
- `created_at`, `last_activity_at`: idle expiry via `VIVA_COPILOT_SESSION_TTL_SECONDS` (default **14400** = 4 h; `0` disables).
  Purged on `store.get()` / `store.create()` and when the WebSocket or STT sees an expired session.

Lost on process restart. Not written to Mongo.

---

## 8. LLM providers and keys

Chat completions use a **Groq → Gemini → OpenRouter** fallback chain. Every provider is a remote API; no local gateway is needed.
Keys load from `Gradex_AI_Server/app/.env` via `groq_client._load_env()`.

| Provider | Key search order | Default models |
|---|---|---|
| **Groq** (`https://api.groq.com/openai/v1`) | `VIVA_COPILOT_API_KEY`, `VIVA_LLM_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, `BACKUP_API_KEY` | `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b` |
| **Gemini** | `GEMINI_API_KEY`, `GOOGLE_API_KEY` | `gemini-2.0-flash`, `gemini-1.5-flash` |
| **OpenRouter** | `OPENROUTER_API_KEY` | `meta-llama/llama-3.1-8b-instruct:free`, `google/gemma-2-9b-it:free`, `mistralai/mistral-7b-instruct:free` |

- A provider with no key is skipped. Within a provider every model is tried; 404, 429 and 5xx move to the next candidate, then the
  next provider.
- Overrides: `VIVA_COPILOT_LLM_MODEL` (Groq), `GEMINI_MODEL`, `OPENROUTER_MODEL`; base URLs via `VIVA_COPILOT_LLM_BASE_URL`,
  `OPENAI_BASE_URL`, `LLM_BASE_URL`, `VIVA_LLM_BASE_URL`, `GEMINI_BASE_URL`, `OPENROUTER_BASE_URL`.
- **STT** is Groq Whisper only: key from `VIVA_COPILOT_STT_API_KEY`, `STT_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, ...; model from
  `VIVA_COPILOT_STT_MODEL` (default `whisper-large-v3-turbo`); at least `VIVA_COPILOT_MIN_STT_GAP` seconds between calls; one retry on 429.

The copilot ignores `GROQ_MODEL`, which other Gradex features use.

---

## 9. Boundaries

The live-phase modules (`router`, `pipeline`, `session_store`, `stt`, `groq_client`, `followup_llm`, `answer_detector`,
`context_builder`, `events`) do not import `VivaEvaluationEngine` or the Viva Assessment UI. Only `analysis.py` (and the router's
upload handling) reach the shared grading chain through `viva_analysis_runner`, `viva_sessions` and `viva_student_id`.

---

## 10. Tests

From the repo root, using the project venv:

```
python -m unittest Gradex_AI_Server.app.viva_copilot.tests.test_copilot_pipeline
python -m unittest Gradex_AI_Server.app.viva_copilot.tests.test_session_store
python -m unittest Gradex_AI_Server.app.viva_copilot.tests.test_groq_client_endpoints
```

They cover answer detection, the context builder, suggestion cadence gates, the panel-enter skip of a second LLM call, session
expiry, and provider endpoint selection.
