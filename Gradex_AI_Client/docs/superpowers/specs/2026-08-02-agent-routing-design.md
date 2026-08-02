# Agent-Based Routing Redesign

Date: 2026-08-02

## Problem

The app currently uses `useState`-based navigation (a `Page` union type in `Sidebar.tsx` and a conditional render switch in `App.tsx`). There are no real URLs, so deep-linking and browser back/forward do not work. The four AI engines (Diagram Evaluation, Handwritten Grading, Question/Exam Prediction, Viva Evaluation) are presented as a flat list of unrelated pages, so it is unclear which pages belong to which agent.

## Goal

Give each of the four agents its own clean URL namespace and its own pages, using real URL routing (`react-router` v7, already a dependency), and reorganize the sidebar into grouped sections — one per agent — so the four agents are visually separated and each owns its routes and pages.

## Agent → Page mapping

| Agent | Pages |
|---|---|
| DiagramEvaluationEngine | Diagram Grading |
| GradingEngine | Handwritten Grading |
| QuestionExamPredictionEngine | Student Analytics, Exam Creator |
| VivaEvaluationEngine | Viva Assessment |

## Approach

Approach 1: single declarative agent config. One config array is the single source of truth for both the `<Routes>` renderer and the `Sidebar` groups, so routes and nav cannot drift.

## Route map

| Route | Page |
|---|---|
| `/` | Redirect based on role: lecturer → `/dashboard`, student → `/student-dashboard` |
| `/dashboard` | Lecturer Dashboard (existing) |
| `/student-dashboard` | Student Dashboard (existing) |
| `/diagram-evaluation` | Diagram Evaluation Engine overview |
| `/diagram-evaluation/diagram-grading` | Diagram Grading (`GradingPage mode="diagram"`) |
| `/grading` | Grading Engine overview |
| `/grading/handwritten-grading` | Handwritten Grading (`GradingPage mode="handwritten"`) |
| `/question-exam` | Question & Exam Prediction overview |
| `/question-exam/analytics` | Student Analytics (`AnalyticsPage`) |
| `/question-exam/exam-creator` | Exam Creator (`ExamCreator`) |
| `/viva-evaluation` | Viva Evaluation overview |
| `/viva-evaluation/viva-assessment` | Viva Assessment (`VivaPage`) |
| `*` | Catch-all → redirect to `/dashboard` |

## Architecture

- **Routing library:** `react-router` v7 declarative mode — `<BrowserRouter>` + `<Routes>` rendered inside `App.tsx`. The existing `role` `useState` keeps gating access; on login navigate via `useNavigate`.
- **Single source of truth:** new `src/app/routeConfig.tsx` exporting a typed `AGENT_CONFIG` array — one entry per agent (DiagramEvaluation, Grading, QuestionExamPrediction, Viva). Each entry holds: base path, agent name, icon, description, and its feature pages (path, label, element). Both the `<Routes>` renderer and the `Sidebar` derive from this config.
- **`App.tsx`:** wraps the app in `<BrowserRouter>`. Renders a layout (`Sidebar` + `TopBar` + `<Outlet>`) for logged-in users, `LoginPage` when no role. Builds `<Routes>` from `AGENT_CONFIG` plus dashboard, student-dashboard, and catch-all routes.
- **`Sidebar.tsx`:** rewritten to render grouped sections — one per agent using `<NavLink>` for active highlighting, agent name as the group header. Dashboard remains ungrouped at top.
- **`AgentOverview.tsx` (new):** small reusable page taking an agent config and rendering title, subtitle, description, and cards linking to the agent's feature pages. Used by all four overview routes.

## Data flow

- Login sets `role` → navigate to `/dashboard` (lecturer) or `/student-dashboard` (student).
- Every nav click is a `<NavLink>` to a real URL; browser back/forward and deep-linking work.
- Logout clears `role` → `LoginPage`.
- Role guard: a student hitting a lecturer route is redirected to `/student-dashboard`; unknown paths hit the catch-all `*` → `/dashboard`.

## Error handling

- Catch-all route handles unknown URLs.
- Role-aware wrapper redirects unauthorized access instead of rendering an error.
- No changes to existing page-level error handling (pages keep current behavior).

## Testing

`package.json` has only `build`/`dev` scripts; no test framework is configured. Verification is `npm run build` (typecheck + bundle) plus a manual `npm run dev` smoke check of each route and the sidebar navigation.

## Files touched

- `src/main.tsx` (render `App`, no structural change expected)
- `src/app/App.tsx` (BrowserRouter + Routes + layout)
- `src/app/components/Sidebar.tsx` (grouped by agent, NavLink)
- `src/app/routeConfig.tsx` (new — agent config)
- `src/app/components/AgentOverview.tsx` (new — reusable overview page)
- Page components (`GradingPage`, `AnalyticsPage`, `ExamCreator`, `VivaPage`) unchanged except where their `mode`/props are passed via route config.
