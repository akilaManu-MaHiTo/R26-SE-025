# Lecture mapping and dashboard validation — baseline audit

Audit date: 2026-10-15. Scope: current working-tree analytics engine and `Gradex_AI_Client`, including the existing staged work. No production code, staged changes, credentials, database, remote API, or model service was changed or accessed. This is a source/fixture audit with isolated ASGI probes, not a deployed-system certification. Assumed use: multiple lecturers and students, including simultaneous requests and repeated exam sessions.

## Evidence flow and what is already sound

The lecturer analytics screen is `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx`, not the separately named `LecturerDashboard.tsx` landing page. The screen requests the full course/session/year/month/semester identity, reads cached or newly computed analytics, and fetches students and teaching actions separately. Exam response guards exist at lines 134–247. StudentDashboard has cancellation guards at lines 94–136, and QuestionDetailModal has an identity-keyed fetch and cancellation guard at lines 27–40.

`app/services/exam_analytics.py::compute_exam_analytics` normalizes submissions, uses classification results to compute numeric question evidence, and aggregates canonical topics from that same normalized evidence (lines 45–100 and 154–213). It sums obtained marks and possible marks rather than averaging already rounded topic percentages. For a 1/1 and 0/9 contribution, the intended canonical percentage is `(1+0)/(1+9)*100 = 10%`, not `(100+0)/2 = 50%`. Topic student counts are counts of normalized student records; topic question counts are distinct question numbers. How ingestion deduplicates student submissions determines whether those are unique people.

Unknown topic assignments remain in overall/Bloom calculations and exact `Unclassified` labels get separate coverage (lines 158–169 and 231–247). Named unmapped labels are collected at lines 174–178. Current question evidence includes confidence, model version, source and review flags (lines 89–97), with an insufficient-coverage flag at lines 268–270. These fields have incomplete UI treatment, described below.

`app/api/lecturer.py::lecturer_question_detail` uses full exam identity, checks conflicting rubric references, normalizes question numbers, rejects invalid saved scores, and returns an excluded-response count (lines 192–264). This supports reviewing the saved rubric, answer excerpts and mark distribution. Excerpts are evidence from OCR or saved text, not verified original handwriting.

`app/services/teaching_actions.py::_validate_llm_output` only allows supplied topics or the supplied lowest-question identifier; it overwrites AI priority and percentages with backend values (lines 128–183). The independent positive test verifies that invented topics disappear and 99%/Low generated metadata becomes the supplied 45%/High evidence.

## Must fix

### DASH-01 — P1: login does not establish API authorization; private records are public

**Evidence:** `app/api/deps.py::get_db` (lines 8–16) supplies only a database. `app/main.py` (lines 8–20) installs CORS and routers, with no authentication middleware or router dependency. `app/api/dashboard.py::student_profile` (lines 42–56), dashboard (lines 63–82), exams (lines 34–39) and practice generation (lines 85–107) trust the requested student ID. The lecturer router at `app/api/lecturer.py:34` has no authorization dependency, including question-response, student-detail, reanalysis, provisioning and taxonomy mutation paths.

**Independent reproduction:** an in-memory ASGI GET with no login, headers or cookies to `/api/students/OTHER-STUDENT/profile` returns HTTP 200 and `private@example.invalid` from a mocked private record. Anonymous `/api/lecturers/exams` also returns HTTP 200. These are real route executions with DB dependencies replaced, not only OpenAPI inspection. Both strict expected-failure tests assert 401/403 and fail on the actual 200.

**Additional frontend evidence:** `Gradex_AI_Client/src/app/components/LoginPage.tsx:124–126` accepts any lecturer form submission directly. Lines 135–141 accept an `IT`-prefixed student ID after *any* login error, including invalid credentials. The backend login response (`app/api/dashboard.py:21–30`) returns an ID/email/role and no authorization credential consumed by subsequent API requests. A student can enter another student's known ID through that fallback and the API accepts its reads.

**Impact:** grades, email addresses, OCR answer text and lecturer records are exposed to callers who can reach the service; mutations and account provisioning also lack role protection. The deployment's network exposure was not inspected.

**Smallest complete fix:** establish server-authenticated identity after login; require it on all private routes; enforce student ownership and lecturer course access; remove both frontend bypasses. CORS and UI role switches cannot implement those checks.

### DASH-02 — P1: lecturer student details can arrive under a different student's heading

**Evidence:** `AnalyticsPage.tsx::handleSelectStudent` sets selected identity at line 255 but writes detail at lines 298 and 329 without the request identity check used for exam analytics. Its catch/finally at lines 334–354 likewise overwrite current error/loading state. The heading uses the current URL student at lines 391–399, whereas the score section uses whichever `studentDetail` last arrived.

**Concrete case:** select student A, then navigate to student B while A's stream is pending. B completes first, then A overwrites B's detail. The B heading can display A's grades. The same issue occurs if the exam changes while a student request is pending. This race is confirmed by source tracing; no browser race simulation was run.

**Fix:** guard every student request success, failure, progress and completion with a current full-exam/student request identity, or cancel and ignore obsolete requests. Clear any open question/topic selection when changing exam too.

### DASH-03 — P2: actual zeros and absent Bloom levels are visually conflated

**Evidence:** `components/analytics/BloomChart.tsx:24–29` inserts unobserved levels with `average_percentage: 0`, renders all numeric values into the same radar/bar, and the legend at line 81 says `0% = insufficient evidence`. Tooltip at lines 63 and 72 shows only the percentage. Lines 40–45 hide the weak badge whenever *any* level has insufficient evidence.

**Concrete case:** an exam tests Apply only and its cohort earns a genuine 0%. Five absent levels are manufactured as zero, so all six vertices show zero; the tooltip/legend cannot distinguish a fully observed failure from an untested skill. A confirmed weakness badge also disappears because an unrelated level is absent.

**Impact/fix:** students and lecturers can mistake absence of measurement for demonstrated weakness, and demonstrated zero marks for absent evidence. Render absent levels as missing/N/A, label evidence per point, include sample counts in tooltips, and show weakness/insufficient evidence independently.

### DASH-04 — P2: heatmap/radar color expressions do not match the theme token format

**Evidence:** `TopicBloomHeatmap.tsx::cellBg` line 26 returns `hsl(var(--primary) / alpha)`, while `src/styles/theme.css:14` defines `--primary: #1a1815` (dark mode line 54 is also hex). BloomChart lines 12–17 and 59–72 similarly wrap hex primary, border and text variables in `hsl()`.

**Concrete case:** substitution yields `hsl(#1a1815 / 0.5)`, which is invalid CSS color syntax. The heatmap's darker-equals-weaker encoding cannot use the intended computed background; chart colors can fall back or disappear. This is a source-level CSS validity finding; no rendered screenshot was captured.

**Fix:** use the existing complete color tokens directly, and an alpha-capable CSS color expression compatible with those complete colors (or established chart color tokens). Do not wrap complete hex colors in `hsl()`.

### DASH-05 — P2: question modal assigns a different performance band than the backend

**Evidence:** `QuestionDetailModal.tsx:43` marks 75% and above Strong. `app/analytics/student_document.py:23` and `performance_status` lines 92–100 use Strong at 80%, Developing at 60%, Needs Improvement at 40%.

**Concrete case:** 78% is Developing in backend/topic/student summaries but Strong in the question evidence modal. Fix the modal's cutoff or consume the backend-owned status; keep all displayed bands consistent. The modal still needs its actual evidence counts and review flag, not only a band.

### DASH-06 — P2: cached analytics stay apparently current after evidence or taxonomy changes

**Evidence:** `app/api/lecturer.py::_is_complete_snapshot` lines 114–127 checks version and the *types* of four fields, not a rubric/submission/taxonomy/model revision. Stream fast path at lines 352–356 returns such a snapshot immediately. `app/services/student_dashboard.py::ensure_student_analytics` lines 24–28 returns any cached valid student document before examining the current submission. `compute_exam_analytics` force reanalysis persists class statistics and exam status but does not rebuild already cached student documents.

**Concrete case:** a lecturer changes a topic alias or a score is corrected, then opens existing analytics. A structurally complete old class snapshot still passes; student detail can remain old even after class Reanalyse. The lecturer endpoint's failed legacy rebuild fallback (lines 284–294) also silently keeps cached content without the promised explicit stale flag. The UI shows generated time at `AnalyticsPage.tsx:1003`, but no comparison with current evidence or stale warning.

**Fix:** compare saved evidence/revision identity on reads and return an explicit freshness state; invalidate/rebuild affected student caches when grades/classification are changed or reanalysed. Keep the existing last-good result on failure, visibly stale. The audit did not modify any caches.

## Should fix

### DASH-07 — P2: frontend drops backend evidence qualifiers before presenting mastery and advice

**Evidence:** `QuestionPerformanceTable.tsx:6–12` narrows its interface to question ID/topic/Bloom/percentage; it displays neither `student_count`, `attempt_count`, `coverage_warning` nor `needs_review`. Its reducer at lines 23–25 selects the lowest percentage unconditionally. `CanonicalTopicTable.tsx:61–62` shows question/student counts but labels every computed topic as mastery/status without evidence strength. `exam_analytics.py:194–229` creates critical/weakest/strongest conclusions regardless of sample size. `TeachingActions.tsx:55–59` always titles output AI Teaching Recommendations and never reads provenance, despite `teaching_actions.py:186–219` returning `provenance: template` on outage.

**Concrete cases:** one response on one low-confidence question can show Critical/Lowest and trigger Critical/High topic advice; a generic template returned during an LLM outage is still presented as AI-generated. The heatmap does expose per-cell counts/status, which is a good exception. `AnalyticsPage` also never displays the available `unmapped_topics`, so a named label outside taxonomy can disappear from named-topic conclusions without a visible missing-coverage summary.

**Fix:** expose existing review/coverage/provenance fields on question cards and advice; qualify low-coverage summaries as observed assessment results requiring review. Counts of questions/attempts are not independent observations. Present suggestions as optional educational actions, not validated causal explanations or personalized proof of mastery. Do not impose a new universal sample-size threshold without a documented educational justification.

### DASH-08 — P2: lecturer landing page presents hardcoded operational and risk claims

**Evidence:** `LecturerDashboard.tsx:8–11` fixes the trend; lines 47–52 fix exams graded, grade time, active students and class average; lines 55–59 fix activity. Lines 77–82 show a fixed date/person, 46 waiting papers and four at-risk students. It has no API calls and `App.tsx:73` routes lecturers to it.

**Impact:** users can interpret demonstration numbers and an invented cognitive-risk flag as current evidence. Remove the unconnected values or label the whole section as a demo until real data exists. Do not synthesize an at-risk student classification from assessment topic percentages alone.

### MAP-01 — P2: lecture provenance has two conflicting definitions and no live upload-to-bank connection

**Independent local inventory:** `datasets/bloom_dataset/question_bank.json` has 179 entries: 90 lecture, 16 exam, 55 tutorial and 18 generated. `curriculum_clean.json` has 90 entries covering eight topics. Lecture rows by canonical topic: Introduction 13, Logical Design 14, Schema Refinement 9, SQL 20, Database Programming 5, JDBC 13, Database Utilities 9 and Database Security 7. Canonical display names for recognized IDs agree with `config/topic_taxonomy.json` in this local inventory.

`app/ingestion/question_bank.py::build_question_bank` lines 309–352 prefers the clean curriculum when it exists. Curriculum assigns lec07 to Database Utilities; the fallback filename table at lines 33–42 assigns `IT2040_Lecture07_2024.pdf` to `indexes_storage`. Therefore installing/removing the clean curriculum changes lecture coverage for the same lecture sequence. SQL is split across lec04/lec05 in the curriculum. No lecture rows support Indexes, Transactions or Recovery in the current bank; missing coverage should not imply students were never taught those subjects. Raw PDF content was not verified: system Python lacked `pymupdf`, so this audit reports a provenance discrepancy, not which lecture label is educationally correct.

The frontend `LectureMaterialsPanel.tsx:245–265` uploads materials to the separate grading service `/upload-lecture-notes`. The analytics recommender reads static `question_bank.json` (`services/recommendation.py:28–46`) and derives coverage from `source_type == lecture` at lines 56–58. No caller found connects those live uploads to this bank or taxonomy. Uploading a new lecture through that panel does not establish new analytics lecture-coverage evidence.

**Fix:** reconcile lec07 against the actual source and version/record the selected provenance; state clearly that current coverage is from this fixed IT2040 bank. If uploaded materials are intended to influence analytics, connect their course-scoped ingestion and revision before claiming that behavior. Do not silently promote file existence to instructional effectiveness or student exposure.

### MAP-02 — P2: 18 generated bank entries carry taxonomy IDs not in the taxonomy

**Independent inventory:** all 18 `source_type: generated` rows use six unknown truncated IDs, three rows each: `database_utilit`, `logical_databas`, `java_database_c`, `database_indexe`, `database_transa`, `database_recove`. Display names can appear valid while IDs do not join to the active taxonomy. This is specific to the supplied generated rows; no real DB migration was examined.

**Fix:** validate candidate canonical IDs against their course taxonomy during ingestion, and preserve full IDs. Reject/flag unknown values rather than silently mapping them to a plausible topic. Recommendation consequences are covered by the separate recommendation audit.

## Verification, boundaries and educational interpretation

Added `tests/test_independent_dashboard_audit.py`: two strict expected failures for the actual unauthenticated ASGI reads and one passing test for backend-owned teaching evidence. `xfail(raises=AssertionError, strict=True)` ensures infrastructure errors cannot count as known defects. For these immediate-await ASGI mocks a synchronous coroutine driver avoids Windows event-loop socket initialization; it raises RuntimeError if real I/O is attempted. This driver is audit-only and does not test concurrency.

Verified command: system Python 3.12, bootstrap disables `DotEnvSettingsSource._read_env_files` before app imports, blocks Motor client construction through its `__init__`, and blocks the httpx network transport; `pytest -q tests/test_independent_dashboard_audit.py --tb=short -p no:cacheprovider -rx`. **Actual result: 1 passed, 2 xfailed, 6.16 seconds, exit 0.** Separate ASGI reproduction returned the two HTTP 200 responses described above.

An earlier broad socket block broke Windows asyncio's internal socketpair. That failed harness attempt produced 6 passed/2 xfailed/22 setup errors; those xfails were not counted as defect evidence. Corrected event-loop reruns stalled and were interrupted. Existing async service/question/taxonomy tests were therefore not claimed as passing by this audit; the successful independent tests avoid that infrastructure limitation. Root audit runner results, if available, should be reported separately.

Appropriate supported actions: inspect the rubric and saved answer evidence, verify topic/classification labels, check missing/invalid scores and denominators, then offer worked examples or optional practice tied to observed question/topic results. No source inspected validates prediction of future performance, individual risk, causal diagnosis of misconceptions, teaching effectiveness, or genuine learning improvement. Bloom labels describe the classified question demand; a marks-based percentage by Bloom does not independently establish a student's cognitive capacity.

Not checked: deployed network policy/identity provider, real users and databases, actual LLM/model behavior, raw lecture PDF content, rendered browser accessibility/color output, timed browser races, or longitudinal student outcomes. No production fixes were attempted. Privacy, stale caches, evidence qualifiers and the race must be resolved before treating the screens as authoritative student guidance.

