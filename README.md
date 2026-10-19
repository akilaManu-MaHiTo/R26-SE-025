# R26-SE-025

## Authentication

The main server and standalone analytics/grading APIs require a login session.
Accounts and sessions use the existing analytics MongoDB database configured in
`AdaptiveExamAnalyticsEngine/.env` (`MONGODB_MODE`, `MONGODB_LOCAL_URI` or
`MONGODB_URI`, and `MONGODB_DB`). MongoDB must be available before starting the API.

Exam keys use `MONGODB_URL` and `EXAM_KEYS_DATABASE_NAME` from
`Gradex_AI_Server/app/.env`. Set `EXAM_KEYS_DATABASE_NAME=gradev5` for the existing
local exam keys. If omitted, the server uses `DATABASE_NAME` for this collection.

Install the updated requirements in your Python environment. The new password
dependency is `argon2-cffi`.

From the repository root, create accounts (passwords are entered privately):

```powershell
python -m Gradex_AI_Server.scripts.provision_user lecturer@university.edu --role lecturer
python -m Gradex_AI_Server.scripts.provision_user it001@my.sliit.lk --role student --student-id IT001
```

Run the same command to reset an existing account's password; this also revokes
its sessions. Match the existing student ID exactly. Exam analysis creates student
profiles without a login password. Provision them with the command above.
Existing `Student@123` and `admin123` passwords no longer work.

Use the main server on port 8000 for the client. Vite proxies `/api` (including
WebSockets) and `/courses` to it. Leave `VITE_BACKEND_URL` and `VITE_API_BASE_URL`
unset for this same-origin setup. If overriding them, use the same URL for both
and the same hostname as the frontend (`localhost` and `127.0.0.1` are different
cookie sites). Remove the old `VITE_GRADEX_API_KEY`; browser API keys no longer
authenticate requests.

For local HTTP development, set `AUTH_COOKIE_SECURE=false` in the backend process
environment or `Gradex_AI_Server/app/.env`. For a standalone engine, set it in that
engine's process environment. Cookies default to Secure for HTTPS deployments.
`CORS_ORIGINS` is a comma-separated list of exact frontend origins; defaults cover
localhost/127.0.0.1 on ports 5173 and 3000 plus the deployed Vercel frontends
`https://r26-se-025-brown.vercel.app` and `https://gradex-orpin.vercel.app`. Set it explicitly for other ports or
deployed frontends. Deploy the frontend and API under the same HTTPS origin and proxy `/api` and
`/courses` to the main server. The Vercel configuration in
`Gradex_AI_Client/vercel.json` does this before the SPA fallback; keep these
rewrites above the catch-all route. If the API is deployed at a different
host, replace those destinations with that host and add the frontend URL to
the server's `CORS_ORIGINS` setting.

Sessions expire after eight hours. Login is limited to 20 attempts per IP per
15-minute window; behind a reverse proxy, configure Uvicorn to trust forwarded
client IPs only from that proxy. Write requests and WebSocket connections require
a trusted `Origin` header. Backend scripts using HTTP must supply that header too.
Students can access only their own dashboard/profile/exams/practice routes;
teaching, grading, diagram, and viva routes require a lecturer account.

The account script may replace the old student ID index with a partial unique
index so multiple lecturer accounts can exist without a student ID. Back up the
database before applying this to an existing deployment.

Public signup, email password recovery, social login, and MFA are outside this
minimal version. Password resets are performed with the account script.

## Viva Evaluation

The viva stack has four parts: the web client (`Gradex_AI_Client`), the main API (`Gradex_AI_Server`), the scoring library
(`VivaEvaluationEngine`) and MongoDB. Details: [VivaEvaluationEngine/README.md](VivaEvaluationEngine/README.md) (scoring and quality
gates), [VivaEvaluationEngine/FEATURE_INVENTORY.md](VivaEvaluationEngine/FEATURE_INVENTORY.md) (every feature, scored or not) and
[Gradex_AI_Server/app/viva_copilot/PROCESS.md](Gradex_AI_Server/app/viva_copilot/PROCESS.md) (Live Viva).

Workflow (lecturer account required):

1. **Viva Workspace** (`/viva-evaluation/vivas`): create a viva (name, subject code and name, year, semester, category technical or
   non-technical, total marks 1 to 100, and for technical vivas the technical share of the mark, 20 to 90 %, default 50 %). A technical
   viva also needs the subject's concept content (`/api/subject-content`). A viva with marks can no longer be edited or deleted.
2. **Viva Assessment** (upload) or **Live Viva** (record): enter a Student ID, then upload or record. The video must be 1 MB to 1 GB and
   10 seconds to 30 minutes, readable, and not mostly blurry, dark or noisy, with one student clearly on camera. Analysis takes minutes;
   progress streams to the page.
3. **Mark**: a non-technical viva is published automatically. A technical viva stays a draft until the examiner enters the technical
   score (out of the viva's total) and publishes. No grade is issued purely on AI authority for technical vivas.
4. **Viva Results**: saved marks grouped by student.

Install the engine requirements as well as the server's (`pip install -r VivaEvaluationEngine/requirements.txt`) and make sure `ffmpeg` is on
PATH. Start the server from the repo root with `python -m uvicorn Gradex_AI_Server.app.main:app --host 0.0.0.0 --port 8000` (no `--reload`).
Settings are in `Gradex_AI_Server/app/.env` (see `.env.example`): LLM key (`GROQ_API_KEY` or `AI_API_KEY`), `VIVA_WHISPER_MODEL`,
`VIVA_MARK_MAX` (fallback total, default 20), `VIVA_ANALYZE_TIMEOUT_SECONDS` (default 600) and `VIVA_COPILOT_*`.

Viva API (all lecturer-only): `/api/vivas`, `/api/viva-analyze` (+ `/progress/{id}` and `/progress/{id}/stream`), `/api/viva-marks`
(+ `/{id}`, `/{id}/publish`, `/{id}/student`), `/api/viva-config`, `/api/subject-content`, `/api/viva-copilot/*`.

Deployment: the client container's nginx proxies `/api/` (including WebSockets, long timeouts) to the backend on port 8000; on Vercel the
rewrites in `Gradex_AI_Client/vercel.json` do the same. Add every frontend origin, including the production domain, to `CORS_ORIGINS`.

