# Live Interviewer Copilot — process document

Technical click-through for the isolated **Live Interviewer Copilot**. This is **not** Viva Assessment (upload/record-then-grade). The two features share only the sidebar group and FastAPI `include_router`.

| Product | UI | Backend | Engine |
|---|---|---|---|
| **Viva Assessment** | `VivaPage.tsx` | `POST /api/viva-analyze` | `VivaEvaluationEngine` + Mongo marks |
| **Live Interviewer Copilot** | `viva-copilot/*` | `/api/viva-copilot/*` | In-memory session + Groq STT/chat |

Copilot does **not** write Mongo, does **not** import `viva_service.py`, and does **not** score the student.

---

## 1. How to run

| Process | Command | Default |
|---|---|---|
| FastAPI | From repo root: `.venv\Scripts\python.exe -m uvicorn Gradex_AI_Server.app.main:app --host 0.0.0.0 --port 8001` | **8001** (do not use `--reload`) |
| Vite client | `Gradex_AI_Client` → `npm run dev` | **5173** |
| Open | Lecturer login → **Viva Evaluation → Live Interviewer Copilot** | `http://localhost:5173/viva-evaluation/live-copilot` |

Env:

- Client: `VITE_BACKEND_URL` (fallback `http://localhost:8001`) in `copilotApi.ts`.
- Server: `Gradex_AI_Server/app/.env` — `AI_API_KEY` or `GROQ_API_KEY`. Optional `VIVA_COPILOT_LLM_MODEL`, `VIVA_COPILOT_STT_MODEL`.

Restart uvicorn after Python changes.

---

## 2. Architecture

```
Browser (LiveCopilotPage)
  │
  │ REST  (lecturer buttons only)
  │   POST /api/viva-copilot/sessions
  │   POST /sessions/{id}/phase | /finalize | /ask | /context
  │   DELETE /sessions/{id}
  │
  │ WebSocket  (live path — no polling)
  │   WS  /api/viva-copilot/ws/{id}
  │   → binary audio slices (~12s WebM)
  │   ← JSON events (transcript, suggestions, errors)
  │
  ▼
Gradex_AI_Server  (FastAPI, port 8001)
  router.py  →  pipeline.py  →  session_store.py  (RAM dict, not Mongo)
                     │
                     ├─ stt.py  → Groq Whisper  POST .../audio/transcriptions
                     └─ followup_llm.py  → Groq Chat  POST .../chat/completions
```

**Why WebSocket for live work:** the browser never polls. Audio and suggestion delivery stay on one socket. REST is only for explicit lecturer actions (create, phase, ask, end). The “database” for this feature is `SessionStore` in RAM. Mongo used by the rest of Gradex is unused here.

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
| `groq_client.py` | Groq HTTP (isolated; not `llm_judge.py`) |
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
| Client | `streaming` becomes true. Camera records **12s** audio slices (`SLICE_MS = 12000`). |

Each slice: `MediaRecorder` → `Blob` → `WebSocket.send(ArrayBuffer)` (binary, not JSON).

---

### Step 5 — Student talks (automatic loop)

This is the live path. No extra clicks.

```
Camera 12s WebM
  → WS binary
  → router.copilot_ws
  → pipeline.ingest_audio_chunk
       if STT already busy: keep latest pending bytes (coalesce)
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
  → groq_client.groq_chat
     POST https://api.groq.com/openai/v1/chat/completions
     default model openai/gpt-oss-20b
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
3. **One LLM call** for that answer (unless `busy_llm`)
4. WS `followup.suggestions.generated` → toasts + panel

**Answer complete** (optional): `POST /sessions/{id}/finalize` forces flush of `utterance_buffer` if the pause detector is slow.

---

### Step 8 — Ask this

| Actor | Action |
|---|---|
| User | **Ask this** on a toast or the side panel |
| Client | `POST /sessions/{id}/ask` `{ "question": "…" }` |
| Server | `ask_question()` — sets `currentQuestion`, appends interviewer turn, WS `interviewer.question.asked` + `transcript.final` (speaker interviewer) |
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
- `ws_clients`, `busy_llm`, `stt_busy`, `pending_audio`
- `last_suggest_at`, `last_suggest_word_count`

Lost on process restart. Not written to Mongo.

---

## 8. Groq models and keys

Loaded from `Gradex_AI_Server/app/.env` by `groq_client._load_env()`.

| Setting | Default |
|---|---|
| Key search order | `VIVA_COPILOT_API_KEY`, `VIVA_LLM_API_KEY`, `GROQ_API_KEY`, `AI_API_KEY`, `BACKUP_API_KEY` |
| Chat model | `VIVA_COPILOT_LLM_MODEL` or `openai/gpt-oss-20b` |
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
