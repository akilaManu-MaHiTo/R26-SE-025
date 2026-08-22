# V2 Engine + Gradex Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose V2 exam recommendations and per-student dashboards through Gradex_AI_Server and surface them in `ExamCreator.tsx` (advisory recommendations) and `AnalyticsPage.tsx` (student drill-down).

**Architecture:** `Gradex_AI_Server` adds the V2 engine root to `sys.path` and a new read-only `predict_api.py` router (Approach A — reads the latest analysis run from MongoDB; no run bootstrap). The client adds two additive UI panels that call the new endpoints. V2 already degrades gracefully when Ollama is down (deterministic study actions).

**Tech Stack:** Python FastAPI (server), motor/PyMongo + pydantic (V2 engine), React + TypeScript + Vite (client), shadcn/ui + recharts.

## Global Constraints

- Copy verbatim from spec where given; keep V2 semantics (`404` unknown student/run; Ollama down while `include_llm=true` → deterministic actions).
- No run → `200 {"status":"no_run","recommendations":[]}` (never `404` for recommendations).
- Never mutate the question bank from recommendations (advisory only).
- Do not change existing `Gradex_AI_Server` `/api/analytics/*` endpoints or the existing AnalyticsPage upload/historical flows.
- V2 is imported as a top-level `app` package; `Gradex_AI_Server.app` is namespaced — no rename of either package.
- Client reuse existing `Card`/`Badge`/`Button`/`Progress`/`Select`/`Separator` patterns; no new UI library.

---

### Task 1: V2 repository — `find_recommendations`

**Files:**
- Modify: `V2_QuestionExamPredictionEngine/app/db/repository.py`
- Test: `V2_QuestionExamPredictionEngine/tests/test_repository.py`

**Interfaces:**
- Consumes: `save_recommendations(db, docs)` (already exists in the same file).
- Produces: `find_recommendations(db, run_id) -> list[dict]` — returns stored `exam_recommendations` for a run, sorted by `priority_score` descending. Consumed by Task 2/3.

- [ ] **Step 1: Write the failing test**

Append to `V2_QuestionExamPredictionEngine/tests/test_repository.py`:

```python
from app.db.repository import find_recommendations, save_recommendations


async def test_find_recommendations_returns_sorted_by_priority(test_db):
    await save_recommendations(
        test_db,
        [
            {
                "recommendation_id": "r-low",
                "run_id": "run-1",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "SQL",
                "bloom_level": "Apply",
                "priority_score": 0.3,
            },
            {
                "recommendation_id": "r-high",
                "run_id": "run-1",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "Schema Refinement",
                "bloom_level": "Analyze",
                "priority_score": 0.9,
            },
        ],
    )
    recs = await find_recommendations(test_db, "run-1")
    assert [r["recommendation_id"] for r in recs] == ["r-high", "r-low"]


async def test_find_recommendations_other_run_returns_empty(test_db):
    await save_recommendations(
        test_db,
        [
            {
                "recommendation_id": "r-other",
                "run_id": "run-other",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "SQL",
                "bloom_level": "Apply",
                "priority_score": 0.5,
            }
        ],
    )
    assert await find_recommendations(test_db, "run-1") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `V2_QuestionExamPredictionEngine`, using its `.venv`):
`& .\.venv\Scripts\python.exe -m pytest tests/test_repository.py::test_find_recommendations_returns_sorted_by_priority -v`
Expected: FAIL — `ImportError: cannot import name 'find_recommendations'`.

- [ ] **Step 3: Add `find_recommendations` to the repository**

In `V2_QuestionExamPredictionEngine/app/db/repository.py`, after `save_recommendations`:

```python
async def find_recommendations(db: AsyncIOMotorDatabase, run_id: str) -> list[dict]:
    cursor = db["exam_recommendations"].find({"run_id": run_id}).sort("priority_score", -1)
    return await cursor.to_list(length=None)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest tests/test_repository.py -v`
Expected: both new tests PASS, existing repository tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add V2_QuestionExamPredictionEngine/app/db/repository.py V2_QuestionExamPredictionEngine/tests/test_repository.py
git commit -m "feat(v2): add find_recommendations repository helper"
```

---

### Task 2: Gradex server — import V2 and add the predict router

**Files:**
- Modify: `Gradex_AI_Server/app/main.py`
- Create: `Gradex_AI_Server/app/predict_api.py`
- Modify: `Gradex_AI_Server/app/requirements.txt`

**Interfaces:**
- Consumes: `latest_run_id(db)`, `find_recommendations(db, run_id)` (Task 1); `build_student_dashboard(db, student_key, run_id, include_llm)` and `StudentDashboardNotFound` from `app.services.student_dashboard`; `get_db` from `app.api.deps` (all V2, top-level `app` package).
- Produces: router with routes `GET /api/predict/exam-recommendations` and `GET /api/predict/students/{student_key}/dashboard`. Module-level names `latest_run_id`, `find_recommendations`, `build_student_dashboard`, `StudentDashboardNotFound`, `get_db` must stay patchable by Task 3's monkeypatch.

- [ ] **Step 1: Write the router module**

Create `Gradex_AI_Server/app/predict_api.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.db.repository import find_recommendations, latest_run_id
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard

router = APIRouter(prefix="/api/predict", tags=["predict"])


def _trim_recommendation(rec: dict) -> dict:
    return {
        "topic": rec.get("topic"),
        "bloom_level": rec.get("bloom_level"),
        "question_type": rec.get("question_type"),
        "mark_range": list(rec.get("mark_range") or []),
        "priority_score": rec.get("priority_score"),
        "component_breakdown": rec.get("component_breakdown"),
        "evidence": rec.get("evidence"),
    }


@router.get("/exam-recommendations")
async def exam_recommendations(db=Depends(get_db)) -> dict:
    try:
        run_id = await latest_run_id(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Prediction backend unavailable: {exc}")
    if run_id is None:
        return {"status": "no_run", "run_id": None, "recommendations": []}
    try:
        run_doc = await db["analysis_runs"].find_one(
            {"run_id": run_id}, {"course_code": 1, "exam_id": 1}
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Prediction backend unavailable: {exc}")
    recs = await find_recommendations(db, run_id)
    return {
        "status": "ok",
        "run_id": run_id,
        "course_code": (run_doc or {}).get("course_code"),
        "exam_id": (run_doc or {}).get("exam_id"),
        "recommendations": [_trim_recommendation(r) for r in recs],
    }


@router.get("/students/{student_key}/dashboard")
async def student_dashboard(
    student_key: str,
    run_id: str | None = None,
    include_llm: bool = False,
    db=Depends(get_db),
):
    try:
        return await build_student_dashboard(db, student_key, run_id, include_llm)
    except StudentDashboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

- [ ] **Step 2: Wire the router into the server**

Edit `Gradex_AI_Server/app/main.py`:

Replace the `sys.path` block (lines ~10–15):

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT, V2_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)
```

Then after the existing `from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis` import, add:

```python
from Gradex_AI_Server.app.predict_api import router as predict_router
```

And after `app = FastAPI(...)` / the CORS middleware block, register the router (place after the CORS middleware so middleware applies):

```python
app.include_router(predict_router)
```

- [ ] **Step 3: Add server dependencies**

Append to `Gradex_AI_Server/app/requirements.txt`:

```
motor>=3.7.1
pydantic-settings>=2.14.2
httpx>=0.28.1
```

- [ ] **Step 4: Smoke-test the import**

Run from repo root with the V2 venv (which already has fastapi/motor/pydantic-settings/httpx):
`V2_QuestionExamPredictionEngine\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'V2_QuestionExamPredictionEngine'); from Gradex_AI_Server.app.predict_api import router; print('ok', router.prefix)"`
Expected: prints `ok /api/predict`. (If `module 'Gradex_AI_Server' has no attribute 'app'`, run from the repo root so `Gradex_AI_Server` is importable.)

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Server/app/main.py Gradex_AI_Server/app/predict_api.py Gradex_AI_Server/app/requirements.txt
git commit -m "feat(server): add V2 predict router and sys.path wiring"
```

---

### Task 3: Server endpoint tests

**Files:**
- Create: `Gradex_AI_Server/tests/test_predict_api.py`
- Create: `Gradex_AI_Server/tests/conftest.py`

**Interfaces:**
- Consumes: the `router` from `Gradex_AI_Server.app.predict_api` (Task 2). Patches module-level `latest_run_id`, `find_recommendations`, `build_student_dashboard`, `StudentDashboardNotFound`, and overrides `get_db`.

- [ ] **Step 1: Write the conftest**

Create `Gradex_AI_Server/tests/conftest.py`:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
for path in (PROJECT_ROOT, V2_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)
```

- [ ] **Step 2: Write the failing tests**

Create `Gradex_AI_Server/tests/test_predict_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Gradex_AI_Server.app.predict_api as predict_api
from Gradex_AI_Server.app.predict_api import router


def _make_client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[predict_api.get_db] = lambda: None
    return TestClient(app)


def test_exam_recommendations_ok(monkeypatch):
    async def fake_run(db):
        return "run-1"

    async def fake_find(db, run_id):
        return [
            {
                "topic": "SQL",
                "bloom_level": "Apply",
                "question_type": "problem_solving",
                "mark_range": [1.0, 4.0],
                "priority_score": 0.9,
                "component_breakdown": {"weakness": 0.8},
                "evidence": {"mastery": 0.4},
            }
        ]

    async def fake_run_doc(db, run_id, projection):
        return {"course_code": "SE2032", "exam_id": "e1"}

    class FakeRunCollection:
        async def find_one(self, *args, **kwargs):
            return {"course_code": "SE2032", "exam_id": "e1"}

    class FakeDb:
        def __getitem__(self, key):
            return FakeRunCollection()

    monkeypatch.setattr(predict_api, "latest_run_id", fake_run)
    monkeypatch.setattr(predict_api, "find_recommendations", fake_find)
    db = FakeDb()

    client = _make_client(monkeypatch)
    client.app.dependency_overrides[predict_api.get_db] = lambda: db
    response = client.get("/api/predict/exam-recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["run_id"] == "run-1"
    assert body["recommendations"][0]["topic"] == "SQL"
    assert body["recommendations"][0]["priority_score"] == 0.9


def test_exam_recommendations_no_run(monkeypatch):
    async def fake_run(db):
        return None

    monkeypatch.setattr(predict_api, "latest_run_id", fake_run)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/exam-recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_run"
    assert body["recommendations"] == []


def test_student_dashboard_ok(monkeypatch):
    async def fake_build(db, student_key, run_id, include_llm):
        return {
            "student_key": student_key,
            "weakest_topics": ["SQL"],
            "recommendations": [{"action": "Review SQL", "topic": "SQL", "source": "deterministic"}],
        }

    monkeypatch.setattr(predict_api, "build_student_dashboard", fake_build)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/students/stu-001/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["student_key"] == "stu-001"
    assert body["recommendations"][0]["action"] == "Review SQL"


def test_student_dashboard_not_found(monkeypatch):
    async def fake_build(db, student_key, run_id, include_llm):
        raise predict_api.StudentDashboardNotFound("no attempts found for student")

    monkeypatch.setattr(predict_api, "build_student_dashboard", fake_build)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/students/nobody/dashboard")
    assert response.status_code == 404
```

Note: `test_exam_recommendations_ok` overrides `get_db` with a fake db object whose `analysis_runs` supports `find_one`. The `no_run` and student tests pass `None`; they never touch `analysis_runs`.

- [ ] **Step 3: Run tests to verify they pass**

Run from repo root with V2 venv:
`V2_QuestionExamPredictionEngine\.venv\Scripts\python.exe -m pytest Gradex_AI_Server/tests/test_predict_api.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add Gradex_AI_Server/tests/conftest.py Gradex_AI_Server/tests/test_predict_api.py
git commit -m "test(server): predict endpoints happy path, no_run, and 404"
```

---

### Task 4: Client — ExamCreator.tsx AI recommendations panel

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/ExamCreator.tsx`

**Interfaces:**
- Consumes: `GET /api/predict/exam-recommendations` → `{status, run_id, recommendations: Array<{topic, bloom_level, question_type, mark_range, priority_score, component_breakdown, evidence}>}`.
- Produces: advisory panel + working "Auto-balance" button (loads recommendations).

- [ ] **Step 1: Add state, types, and loader**

In `ExamCreator.tsx`, after the existing `const [selected, setSelected] = useState<string[]>(["Q-1041", "Q-1042", "Q-1043", "Q-1045"]);` add:

```tsx
interface ExamRecommendation {
  topic?: string;
  bloom_level?: string;
  question_type?: string;
  mark_range?: number[];
  priority_score?: number;
  evidence?: Record<string, unknown>;
}

const backendBaseUrl =
  (import.meta as ImportMeta & { env?: { VITE_BACKEND_URL?: string } }).env?.VITE_BACKEND_URL ??
  "http://localhost:8000";

const [recs, setRecs] = useState<ExamRecommendation[]>([]);
const [recStatus, setRecStatus] = useState<"idle" | "loading" | "loaded" | "no_run" | "error">("idle");
const [recError, setRecError] = useState<string | null>(null);

const loadRecommendations = async () => {
  setRecStatus("loading");
  setRecError(null);
  try {
    const response = await fetch(`${backendBaseUrl}/api/predict/exam-recommendations`);
    if (!response.ok) {
      throw new Error((await response.text()) || "Failed to load recommendations.");
    }
    const data = await response.json();
    setRecs(data.recommendations ?? []);
    setRecStatus(data.status === "no_run" ? "no_run" : "loaded");
  } catch (error) {
    setRecStatus("error");
    setRecError(error instanceof Error ? error.message : "Failed to load recommendations.");
  }
};
```

- [ ] **Step 2: Wire the Auto-balance button**

Replace the existing Auto-balance button (line ~140):

```tsx
<Button
  variant="outline"
  size="sm"
  onClick={() => void loadRecommendations()}
  disabled={recStatus === "loading"}
>
  <Sparkles className="size-4 mr-1.5 text-primary" />
  {recStatus === "loading" ? "Loading…" : "Auto-balance"}
</Button>
```

- [ ] **Step 3: Add the recommendations panel**

Insert a new `Card` immediately **after** the header `div` that contains the "Compose, balance and export structured exams." paragraph (i.e., between that header block and the `{/* Filters */}` card):

```tsx
{/* AI exam recommendations */}
<Card className="p-4 border-border">
  <div className="flex items-center justify-between">
    <div>
      <div className="text-foreground">AI recommendations</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        Evidence-based topic × Bloom targets from the predictive engine.
      </div>
    </div>
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void loadRecommendations()}
      disabled={recStatus === "loading"}
    >
      <Sparkles className="size-4 mr-1.5 text-primary" />
      {recStatus === "loading" ? "Loading…" : "Refresh"}
    </Button>
  </div>
  <div className="mt-3">
    {recStatus === "idle" && (
      <p className="text-xs text-muted-foreground">
        Click Auto-balance to load topic × Bloom recommendations.
      </p>
    )}
    {recStatus === "no_run" && (
      <p className="text-xs text-muted-foreground">
        Run analytics first — upload exam + answers in Student Analytics.
      </p>
    )}
    {recStatus === "error" && (
      <p className="text-xs text-red-500">{recError}</p>
    )}
    {recStatus === "loaded" && recs.length === 0 && (
      <p className="text-xs text-muted-foreground">
        No recommendations available for the latest run.
      </p>
    )}
    {recStatus === "loaded" && recs.length > 0 && (
      <div className="grid sm:grid-cols-2 gap-2">
        {recs.map((r, i) => (
          <div key={`rec-${i}`} className="rounded-lg border border-border p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary" className="bg-accent text-primary border-0">{r.topic ?? "—"}</Badge>
              <Badge variant="outline" className="border-border text-muted-foreground">{r.bloom_level ?? "—"}</Badge>
              <Badge className="bg-primary text-primary-foreground border-0 ml-auto">
                {r.priority_score != null ? r.priority_score.toFixed(2) : "—"}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground mt-2">
              {r.question_type ?? "problem_solving"} · {r.mark_range?.[0] ?? 1}–{r.mark_range?.[1] ?? 4} marks
            </div>
            {r.evidence && (
              <div className="text-xs text-muted-foreground mt-1">
                mastery {typeof r.evidence.mastery === "number" ? r.evidence.mastery.toFixed(2) : "—"} ·{" "}
                {String(r.evidence.evidence_status ?? "")}
              </div>
            )}
          </div>
        ))}
      </div>
    )}
  </div>
</Card>
```

- [ ] **Step 4: Typecheck the client**

Run from `Gradex_AI_Client`:
`npm run build`
Expected: Vite build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Client/src/app/components/ExamCreator.tsx
git commit -m "feat(client): AI recommendations panel in ExamCreator"
```

---

### Task 5: Client — AnalyticsPage.tsx student drill-down

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx`

**Interfaces:**
- Consumes: `GET /api/predict/students/{student_key}/dashboard?include_llm=false` → V2 `StudentDashboard` JSON (`student_key`, `weakest_topics`, `bloom_skills`, `topic_skills`, `cohort_comparison`, `recommendations`, `exams`).
- Produces: additive student drill-down panel using the already-computed `students` list. Does not alter existing upload/historical flows.

- [ ] **Step 1: Add the Select import**

In `AnalyticsPage.tsx`, add to the existing shadcn imports (near the `Tabs` import):

```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
```

- [ ] **Step 2: Add state and loader inside the component**

Add right after `const [selectedStudent, setSelectedStudent] = useState<any | null>(null);`:

```tsx
const [drillStudent, setDrillStudent] = useState<string>("");
const [drillData, setDrillData] = useState<any | null>(null);
const [drillLoading, setDrillLoading] = useState(false);
const [drillError, setDrillError] = useState<string | null>(null);

const loadDrill = async (studentKey: string) => {
  setDrillStudent(studentKey);
  setDrillLoading(true);
  setDrillError(null);
  setDrillData(null);
  try {
    const response = await fetch(
      `${backendBaseUrl}/api/predict/students/${encodeURIComponent(studentKey)}/dashboard?include_llm=false`,
    );
    if (!response.ok) {
      throw new Error((await response.text()) || "Dashboard load failed.");
    }
    setDrillData(await response.json());
  } catch (error) {
    setDrillError(error instanceof Error ? error.message : "Dashboard load failed.");
  } finally {
    setDrillLoading(false);
  }
};
```

- [ ] **Step 3: Add the drill-down panel JSX**

Insert a new `Card` immediately **after** the executive summary grid (the `{summary.map(...)}` block) and **before** the `{selectedSession && (...)}` block:

```tsx
{/* Student drill-down */}
<Card className="border-border">
  <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
    <div>
      <div className="text-foreground">Student drill-down</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        Per-student evidence, study actions, and cohort comparison from the V2 engine.
      </div>
    </div>
    <div className="flex items-center gap-2">
      <Select value={drillStudent} onValueChange={(v) => void loadDrill(v)}>
        <SelectTrigger className="w-48"><SelectValue placeholder="Select a student" /></SelectTrigger>
        <SelectContent>
          {students.map((s: { id: string }) => (
            <SelectItem key={s.id} value={s.id}>{s.id}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {drillLoading && (
        <Badge className="bg-accent text-primary border-0">
          <RefreshCw className="size-3 mr-1 animate-spin" /> Loading
        </Badge>
      )}
    </div>
  </div>

  <div className="p-5">
    {!drillStudent && (
      <p className="text-sm text-muted-foreground">
        Select a student to load their V2 dashboard.
      </p>
    )}
    {drillError && (
      <p className="text-sm text-red-500">{drillError}</p>
    )}
    {drillData && (
      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-4 border-border bg-card">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Study actions</div>
          <div className="mt-2 space-y-2">
            {(drillData.recommendations ?? []).map((rec: any, i: number) => (
              <div key={`drill-action-${i}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-foreground">{rec.action}</span>
                  <Badge className="bg-accent text-primary border-0 ml-auto">
                    {rec.source ?? "deterministic"}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {rec.topic}
                  {rec.rationale ? ` — ${rec.rationale}` : ""}
                </div>
                {rec.practice_topics?.length > 0 && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Practice: {(rec.practice_topics ?? []).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 border-border bg-card">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Weakest topics</div>
          <div className="mt-2 space-y-2">
            {(drillData.weakest_topics ?? []).map((t: string, i: number) => (
              <div key={`drill-weak-${i}`} className="flex items-center gap-2">
                <span className="size-5 rounded-md bg-accent text-primary flex items-center justify-center text-xs shrink-0">
                  {i + 1}
                </span>
                <span className="text-sm text-foreground">{t}</span>
              </div>
            ))}
          </div>
          <Separator className="my-3" />
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Topic skills</div>
          <div className="mt-2 space-y-2">
            {(drillData.topic_skills ?? []).map((t: any, i: number) => (
              <div key={`drill-topic-${i}`}>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-foreground">{t.topic}</span>
                  <span className="text-muted-foreground">
                    {t.mastery != null ? `${Math.round(t.mastery * 100)}%` : "—"} · {t.evidence_status}
                  </span>
                </div>
                <Progress value={t.mastery != null ? Math.round(t.mastery * 100) : 0} className="h-1.5 mt-1.5" />
              </div>
            ))}
          </div>
        </Card>

        {(drillData.exams ?? []).length > 0 && (
          <Card className="p-4 border-border bg-card lg:col-span-2">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Exams</div>
            <div className="mt-2 grid sm:grid-cols-2 gap-2">
              {(drillData.exams ?? []).map((e: any, i: number) => (
                <div key={`drill-exam-${i}`} className="rounded-lg border border-border p-3">
                  <div className="text-sm text-foreground">{e.exam_id}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {Math.round(e.percentage * 100)}% · {e.grade} · {e.total_awarded}/{e.total_max} marks
                  </div>
                </div>
              ))}
            </div>
            {drillData.cohort_comparison && (
              <div className="text-xs text-muted-foreground mt-3">
                Cohort comparison: {JSON.stringify(drillData.cohort_comparison)}
              </div>
            )}
          </Card>
        )}
      </div>
    )}
  </div>
</Card>
```

- [ ] **Step 4: Typecheck the client**

Run from `Gradex_AI_Client`:
`npm run build`
Expected: Vite build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Client/src/app/components/AnalyticsPage.tsx
git commit -m "feat(client): student drill-down panel in AnalyticsPage"
```

---

### Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the V2 test suite**

Run from `V2_QuestionExamPredictionEngine`:
`& .\.venv\Scripts\python.exe -m pytest -v`
Expected: all tests PASS (including new `find_recommendations` tests).

- [ ] **Step 2: Run the server predict tests**

Run from repo root:
`V2_QuestionExamPredictionEngine\.venv\Scripts\python.exe -m pytest Gradex_AI_Server/tests/test_predict_api.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 3: Typecheck the client**

Run from `Gradex_AI_Client`:
`npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual end-to-end (with Mongo + Ollama running)**

1. Seed Mongo: `& .\V2_QuestionExamPredictionEngine\.venv\Scripts\python.exe run_sample.py dbms_analytics` (writes a run + recommendations).
2. Start the server: `V2_QuestionExamPredictionEngine\.venv\Scripts\python.exe -m uvicorn Gradex_AI_Server.app.main:app --port 8000`.
3. `curl http://localhost:8000/api/predict/exam-recommendations` → `status: "ok"` with recommendations.
4. Pick a student id from the run (e.g. `it22100001` if present) → `curl "http://localhost:8000/api/predict/students/it22100001/dashboard?include_llm=true"` → dashboard JSON with `recommendations`.
5. In the client, `ExamCreator` → Auto-balance shows the recommendation panel; `AnalyticsPage` → select a student → drill-down renders.

- [ ] **Step 5: No uncommitted changes (if this is the final review gate)**

```bash
git status --short
```
Expected: clean (or only intentional files).
