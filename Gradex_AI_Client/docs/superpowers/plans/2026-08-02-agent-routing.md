# Agent-Based Routing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the app's `useState`-based page switching with real URL routing so each of the four AI agents owns a clean URL namespace and its own pages, with the sidebar grouped by agent.

**Architecture:** A single typed `AGENT_CONFIG` array in `src/app/routeConfig.tsx` is the source of truth for both the `<Routes>` tree and the grouped `Sidebar`. `App.tsx` renders `<BrowserRouter>` + `<Routes>` with a layout route (`Sidebar` + `TopBar` + `<Outlet>`), keeps the existing `role` state as the auth gate, and redirects unknown/unauthorized paths to a role-appropriate default. Each agent's base route renders a reusable `AgentOverview` page that links to the agent's feature pages.

**Tech Stack:** React 18.3.1, react-router 7.13.0 (already a dependency — do NOT add or remove packages), Vite 6, TypeScript via esbuild.

## Global Constraints

- Import react-router APIs ONLY from `"react-router"` (v7 merged package) — never from `"react-router-dom"`.
- `AGENT_CONFIG` lives in `src/app/routeConfig.tsx`; feature paths are absolute strings like `/grading/handwritten-grading`.
- Agent → model brand mapping (from `src/app/components/AIBrand.tsx`): Diagram Evaluation = `"structr"`, Grading Engine = `"lexo"`, Question & Exam Prediction = `"pulse"`, Viva Evaluation = `"voca"`.
- Page components (`GradingPage`, `AnalyticsPage`, `ExamCreator`, `VivaPage`) keep their current behavior; only route/nav wiring changes.
- No test framework is configured. Verification for every task = `npm run build` (vite) and, where routing is involved, a manual `npm run dev` smoke test. `npm run build` transpiles via esbuild and does NOT typecheck; it still catches broken imports and syntax errors.
- Do not add code comments unless the file being edited already contains them.

---

### Task 1: Create the agent route config (`src/app/routeConfig.tsx`)

**Files:**
- Create: `src/app/routeConfig.tsx`

**Interfaces:**
- Consumes: `AIModel` type and `AIPageBanner`/`AIBadgePill` API surface from `./components/AIBrand` (module exists, unchanged); page components `GradingPage`, `AnalyticsPage`, `ExamCreator`, `VivaPage` (all named exports, unchanged).
- Produces:
  - `export type AgentId = "diagram-evaluation" | "grading" | "question-exam" | "viva-evaluation"`
  - `export interface AgentFeature { path: string; label: string; title: string; subtitle?: string; element: ReactNode }`
  - `export interface AgentConfig { id: AgentId; basePath: string; name: string; description: string; icon: LucideIcon; model: AIModel; features: AgentFeature[] }`
  - `export const AGENT_CONFIG: AgentConfig[]`
  - `export function titleFor(pathname: string): { title: string; subtitle?: string }`

- [ ] **Step 1: Create the file**

Write the full file `src/app/routeConfig.tsx`:

```tsx
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { FileText, Workflow, BarChart3, Video } from "lucide-react";
import type { AIModel } from "./components/AIBrand";
import { GradingPage } from "./components/GradingPage";
import { AnalyticsPage } from "./components/AnalyticsPage";
import { ExamCreator } from "./components/ExamCreator";
import { VivaPage } from "./components/VivaPage";

export type AgentId = "diagram-evaluation" | "grading" | "question-exam" | "viva-evaluation";

export interface AgentFeature {
  path: string;
  label: string;
  title: string;
  subtitle?: string;
  element: ReactNode;
}

export interface AgentConfig {
  id: AgentId;
  basePath: string;
  name: string;
  description: string;
  icon: LucideIcon;
  model: AIModel;
  features: AgentFeature[];
}

export const AGENT_CONFIG: AgentConfig[] = [
  {
    id: "diagram-evaluation",
    basePath: "/diagram-evaluation",
    name: "Diagram Evaluation",
    description: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML submissions.",
    icon: Workflow,
    model: "structr",
    features: [
      {
        path: "/diagram-evaluation/diagram-grading",
        label: "Diagram Grading",
        title: "Diagram Grading",
        subtitle: "AI-assisted assessment of structured diagrams",
        element: <GradingPage mode="diagram" />,
      },
    ],
  },
  {
    id: "grading",
    basePath: "/grading",
    name: "Grading Engine",
    description: "OCR + rubric matching for scanned handwritten answer sheets with AI confidence scoring.",
    icon: FileText,
    model: "lexo",
    features: [
      {
        path: "/grading/handwritten-grading",
        label: "Handwritten Grading",
        title: "Handwritten Grading",
        subtitle: "OCR + rubric matching for scanned papers",
        element: <GradingPage mode="handwritten" />,
      },
    ],
  },
  {
    id: "question-exam",
    basePath: "/question-exam",
    name: "Question & Exam Prediction",
    description: "Predict performance, surface cognitive gaps and compose balanced, level-appropriate exams.",
    icon: BarChart3,
    model: "pulse",
    features: [
      {
        path: "/question-exam/analytics",
        label: "Student Analytics",
        title: "Student Analytics",
        subtitle: "Class, cohort and individual insights",
        element: <AnalyticsPage />,
      },
      {
        path: "/question-exam/exam-creator",
        label: "Exam Creator",
        title: "Exam Creator",
        subtitle: "Compose balanced, level-appropriate exams",
        element: <ExamCreator />,
      },
    ],
  },
  {
    id: "viva-evaluation",
    basePath: "/viva-evaluation",
    name: "Viva Evaluation",
    description: "Upload viva recordings and get transcripts, key moments and rubric-based scoring.",
    icon: Video,
    model: "voca",
    features: [
      {
        path: "/viva-evaluation/viva-assessment",
        label: "Viva Assessment",
        title: "Viva Assessment",
        subtitle: "AI-aided viva voce evaluation",
        element: <VivaPage />,
      },
    ],
  },
];

const PATH_TITLES: Record<string, { title: string; subtitle?: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Your AI-powered command center" },
  "/student-dashboard": { title: "My Dashboard", subtitle: "Track your progress and upcoming work" },
};

for (const agent of AGENT_CONFIG) {
  PATH_TITLES[agent.basePath] = { title: agent.name, subtitle: agent.description };
  for (const feature of agent.features) {
    PATH_TITLES[feature.path] = { title: feature.title, subtitle: feature.subtitle };
  }
}

export function titleFor(pathname: string): { title: string; subtitle?: string } {
  return PATH_TITLES[pathname] ?? { title: "GradeX AI", subtitle: "Learning Suite" };
}
```

- [ ] **Step 2: Verify the build**

Run: `npm run build`
Expected: build succeeds (no unresolved imports). Note the config is not imported anywhere yet, so this only proves the file transpiles and its imports resolve.

- [ ] **Step 3: Commit**

```bash
git add src/app/routeConfig.tsx
git commit -m "feat: add agent route config"
```

---

### Task 2: Create the reusable agent overview page (`src/app/components/AgentOverview.tsx`)

**Files:**
- Create: `src/app/components/AgentOverview.tsx`

**Interfaces:**
- Consumes: `AgentConfig` from `../routeConfig` (Task 1), `AIPageBanner`/`AIBadgePill` from `./AIBrand`, `Card` from `./ui/card`, `Button` from `./ui/button`, `Link` from `"react-router"`.
- Produces: `export function AgentOverview({ agent }: { agent: AgentConfig })` — renders a banner, agent header, and a card per feature page linking to `feature.path`.

- [ ] **Step 1: Create the file**

Write the full file `src/app/components/AgentOverview.tsx`:

```tsx
import { ArrowRight } from "lucide-react";
import { Link } from "react-router";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { AIPageBanner, AIBadgePill } from "./AIBrand";
import type { AgentConfig } from "../routeConfig";

export function AgentOverview({ agent }: { agent: AgentConfig }) {
  const Icon = agent.icon;
  return (
    <div className="p-8 space-y-6">
      <AIPageBanner model={agent.model} />
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Icon className="size-4" /> {agent.name}
          </div>
          <h2 className="tracking-tight text-slate-900 mt-1">{agent.name}</h2>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">{agent.description}</p>
        </div>
        <AIBadgePill model={agent.model} />
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {agent.features.map((feature) => (
          <Link key={feature.path} to={feature.path} className="group">
            <Card className="h-full p-6 border-slate-200 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50 transition-all">
              <div className="tracking-tight text-slate-900">{feature.title}</div>
              {feature.subtitle && (
                <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{feature.subtitle}</p>
              )}
              <Button
                variant="ghost"
                className="mt-3 px-0 text-blue-600 hover:text-blue-700 hover:bg-transparent group-hover:translate-x-1 transition-transform"
              >
                Open <ArrowRight className="size-4 ml-1" />
              </Button>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/app/components/AgentOverview.tsx
git commit -m "feat: add reusable agent overview page"
```

---

### Task 3: Routing cutover — `App.tsx`, `Sidebar.tsx`, `LecturerDashboard.tsx`

**Files:**
- Modify: `src/app/App.tsx` (full rewrite)
- Modify: `src/app/components/Sidebar.tsx` (full rewrite)
- Modify: `src/app/components/LecturerDashboard.tsx` (targeted edits)

**Interfaces:**
- Consumes: `AGENT_CONFIG`, `titleFor`, `AgentConfig` from `../routeConfig` / `../app/routeConfig` (Task 1); `AgentOverview` (Task 2); `LoginPage`, `LecturerDashboard`, `StudentDashboard`, `TopBar` (unchanged modules); react-router `BrowserRouter`, `Routes`, `Route`, `Navigate`, `Outlet`, `useLocation`, `useNavigate`, `NavLink` from `"react-router"`.
- Produces:
  - `Sidebar` new props: `{ role: "lecturer" | "student"; onLogout: () => void }` — no `current`/`onNavigate`, no `Page` export.
  - `LecturerDashboard` takes no props.
  - `App` renders `<BrowserRouter>` with a layout route, role gating, and a catch-all redirect. No `Page` union type remains anywhere.

- [ ] **Step 1: Rewrite `src/app/App.tsx`**

Replace the entire contents of `src/app/App.tsx` with:

```tsx
import { Fragment, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { LoginPage } from "./components/LoginPage";
import { LecturerDashboard } from "./components/LecturerDashboard";
import { StudentDashboard } from "./components/StudentDashboard";
import { AgentOverview } from "./components/AgentOverview";
import { AGENT_CONFIG, titleFor } from "./routeConfig";
import { Toaster } from "./components/ui/sonner";

type Role = "lecturer" | "student";

function Layout({ role, onLogout }: { role: Role; onLogout: () => void }) {
  const location = useLocation();
  const meta = titleFor(location.pathname);
  return (
    <div className="flex bg-slate-50 min-h-screen text-slate-900">
      <Sidebar role={role} onLogout={onLogout} />
      <main className="flex-1 min-w-0 flex flex-col">
        <TopBar title={meta.title} subtitle={meta.subtitle} />
        <div className="flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const [role, setRole] = useState<Role | null>(null);

  if (!role) {
    return (
      <>
        <LoginPage onLogin={(r) => setRole(r)} />
        <Toaster />
      </>
    );
  }

  const defaultPath = role === "lecturer" ? "/dashboard" : "/student-dashboard";

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout role={role} onLogout={() => setRole(null)} />}>
          <Route index element={<Navigate to={defaultPath} replace />} />
          <Route
            path="/dashboard"
            element={
              role === "lecturer" ? <LecturerDashboard /> : <Navigate to={defaultPath} replace />
            }
          />
          <Route
            path="/student-dashboard"
            element={
              role === "student" ? <StudentDashboard /> : <Navigate to={defaultPath} replace />
            }
          />
          {role === "lecturer" &&
            AGENT_CONFIG.map((agent) => (
              <Fragment key={agent.id}>
                <Route path={agent.basePath} element={<AgentOverview agent={agent} />} />
                {agent.features.map((feature) => (
                  <Route key={feature.path} path={feature.path} element={feature.element} />
                ))}
              </Fragment>
            ))}
          <Route path="*" element={<Navigate to={defaultPath} replace />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Rewrite `src/app/components/Sidebar.tsx`**

Replace the entire contents of `src/app/components/Sidebar.tsx` with:

```tsx
import { LayoutDashboard, LogOut, Sparkles } from "lucide-react";
import { NavLink } from "react-router";
import { Button } from "./ui/button";
import { cn } from "./ui/utils";
import { AGENT_CONFIG } from "../routeConfig";

interface SidebarProps {
  role: "lecturer" | "student";
  onLogout: () => void;
}

const itemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
  );

const headerClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium uppercase tracking-wider transition-colors",
    isActive ? "text-blue-700" : "text-slate-400 hover:text-slate-600"
  );

const subItemClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
  );

export function Sidebar({ role, onLogout }: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 bg-white border-r border-slate-200 flex flex-col h-screen sticky top-0">
      <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-2.5">
        <div className="size-9 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center shadow-sm shadow-blue-200">
          <Sparkles className="size-5 text-white" />
        </div>
        <div className="leading-tight">
          <div className="text-slate-900 tracking-tight">GradeX AI</div>
          <div className="text-xs text-slate-500">Learning Suite</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto">
        {role === "lecturer" ? (
          <>
            <NavLink to="/dashboard" end className={itemClass}>
              <LayoutDashboard className="size-4" />
              <span>Dashboard</span>
            </NavLink>

            <div className="space-y-1">
              {AGENT_CONFIG.map((agent) => {
                const Icon = agent.icon;
                return (
                  <div key={agent.id} className="space-y-0.5">
                    <NavLink to={agent.basePath} className={headerClass}>
                      <Icon className="size-4" />
                      <span className="truncate">{agent.name}</span>
                    </NavLink>
                    <div className="ml-4 space-y-0.5 border-l border-slate-100 pl-2">
                      {agent.features.map((feature) => (
                        <NavLink key={feature.path} to={feature.path} end className={subItemClass}>
                          <span className="truncate">{feature.label}</span>
                        </NavLink>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <NavLink to="/student-dashboard" end className={itemClass}>
            <LayoutDashboard className="size-4" />
            <span>My Dashboard</span>
          </NavLink>
        )}
      </nav>

      <div className="p-3 border-t border-slate-100">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50">
          <div className="size-9 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 text-white flex items-center justify-center text-sm">
            {role === "lecturer" ? "DR" : "ST"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-slate-900 truncate">
              {role === "lecturer" ? "Dr. R. Mendis" : "Sahan Perera"}
            </div>
            <div className="text-xs text-slate-500 truncate capitalize">{role}</div>
          </div>
          <Button variant="ghost" size="icon" onClick={onLogout} className="size-8">
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Update `src/app/components/LecturerDashboard.tsx`**

Apply these edits:

1. Replace the import of the `Page` type (line 5) with the router import:

```tsx
import { useNavigate } from "react-router";
```

2. Replace the function signature and add `useNavigate`:

```tsx
export function LecturerDashboard() {
  const navigate = useNavigate();
```

3. In the `cards` array, replace each `id: "..." as Page,` field with a `path` field (keep title/desc/icon/color/tint/stat unchanged):

```tsx
    {
      path: "/diagram-evaluation/diagram-grading",
      title: "Grade Diagram Exams",
      desc: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML.",
      icon: Workflow,
      color: "from-blue-500 to-blue-700",
      tint: "bg-blue-50 text-blue-600",
      stat: "12 pending",
    },
    {
      path: "/grading/handwritten-grading",
      title: "Grade Handwritten Exams",
      desc: "OCR + rubric matching for scanned answer sheets with AI confidence scoring.",
      icon: FileText,
      color: "from-emerald-500 to-emerald-700",
      tint: "bg-emerald-50 text-emerald-600",
      stat: "28 pending",
    },
    {
      path: "/question-exam/analytics",
      title: "Student Analytics",
      desc: "Performance bands, cognitive gaps, topic mastery and at-risk early warnings.",
      icon: BarChart3,
      color: "from-violet-500 to-violet-700",
      tint: "bg-violet-50 text-violet-600",
      stat: "4 alerts",
    },
    {
      path: "/viva-evaluation/viva-assessment",
      title: "Viva Assessment",
      desc: "Upload viva recordings — get transcripts, key moments and rubric scoring.",
      icon: Video,
      color: "from-amber-500 to-amber-600",
      tint: "bg-amber-50 text-amber-600",
      stat: "6 to review",
    },
```

4. Replace the card click handler so the card navigates to its `path` (the line `onClick={() => onNavigate(c.id)}`):

```tsx
              <Card key={c.path} className="group p-6 border-slate-200 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50 transition-all cursor-pointer" onClick={() => navigate(c.path)}>
```

5. Replace the "Resume grading" button handler:

```tsx
          <Button className="bg-white text-blue-700 hover:bg-blue-50" onClick={() => navigate("/grading/handwritten-grading")}>
            Resume grading <ArrowRight className="size-4 ml-1" />
          </Button>
```

- [ ] **Step 4: Verify the build**

Run: `npm run build`
Expected: build succeeds with no unresolved imports or syntax errors.

- [ ] **Step 5: Manual smoke test**

Run: `npm run dev` and open the dev URL. Verify:
- Login as lecturer → lands on `/dashboard`.
- Sidebar shows a "Dashboard" item plus four grouped agent sections (Diagram Evaluation, Grading Engine, Question & Exam Prediction, Viva Evaluation), each with its feature page(s) indented underneath.
- Clicking each sidebar item changes the URL and highlights the active item (group header stays active within its agent).
- `/` redirects to `/dashboard`; typing `/grading` shows the Grading Engine overview; `/grading/handwritten-grading` shows the Handwritten Grading workflow.
- All 12 URLs from the spec route map render the expected page and the `TopBar` shows the right title/subtitle.
- An unknown path (e.g. `/nope`) redirects to `/dashboard`.
- Logout returns to the login screen; login as student → `/student-dashboard`; visiting a lecturer URL as a student (e.g. `/grading`) redirects to `/student-dashboard`.
- Browser back/forward navigate between visited pages.

- [ ] **Step 6: Commit**

```bash
git add src/app/App.tsx src/app/components/Sidebar.tsx src/app/components/LecturerDashboard.tsx
git commit -m "feat: replace state-based nav with URL routing per agent"
```

---

### Task 4: Final verification and stale-reference sweep

**Files:**
- Search only: `src/**/*.ts`, `src/**/*.tsx`

**Interfaces:**
- Consumes: the final state of the codebase after Task 3.
- Produces: confirmation that no references to the removed `Page` union type or old flat page ids remain, and the production build passes.

- [ ] **Step 1: Sweep for stale references**

Run:

```bash
rg -n "grading-diagram|grading-handwritten|as Page\b|: Page\b|type Page|from \"./components/Sidebar\"" src
```

Expected: no matches. (The string `"grading-handwritten"` may legitimately appear inside `routeConfig.tsx` and `LecturerDashboard.tsx` as a URL path — confirm those matches are path strings, not page ids.)

- [ ] **Step 2: Production build**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Final smoke test**

Run: `npm run dev`. Re-check the five core flows from Task 3 Step 5 (lecturer nav, grouped sidebar, all routes, catch-all redirect, student role gating).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: verify routing cutover"
```

(If no files changed in the sweep, skip this commit.)
