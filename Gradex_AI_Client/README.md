# Gradex AI Client

React + Vite + Tailwind front end for Gradex AI: Diagram Evaluation, Grading, Question and Exam Prediction (analytics, exam creator,
course materials, taxonomy) and Viva Evaluation (Viva Workspace, Viva Assessment, Live Viva, Viva Results). Originally generated from a
Figma design.

## Run

```
pnpm install      # or npm i
npm run dev       # http://localhost:5173
npm test          # node tests + vitest
npm run build
```

The dev server proxies `/api` (including WebSockets) and `/courses` to the main server (`VITE_PROXY_TARGET`, default
`http://127.0.0.1:8000`). Leave `VITE_BACKEND_URL` and `VITE_API_BASE_URL` unset for this same-origin setup; if you set them, use the
same value for both and the same hostname as the page, because cookies are per site. Login uses a session cookie, so there are no API
keys in the browser. See the root [README](../README.md) for authentication and deployment (nginx and Vercel rewrites).

## Where things are

- `src/app/routeConfig.tsx`: the four agents and their pages.
- `src/app/components/viva/`: Viva Assessment and results components, mark and scale helpers (`officialMark.ts`, `markingScale.ts`).
  The mark scale and grade bands come from the server (`GET /api/viva-config`) and each viva's total marks.
- `src/app/components/viva-copilot/`: Live Viva.
- `src/app/api/`: API clients (`apiFetch` adds credentials).
