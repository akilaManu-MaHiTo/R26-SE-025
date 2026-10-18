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
