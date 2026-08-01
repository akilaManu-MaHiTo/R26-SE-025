# Agent Workflow Architecture Design

**Date:** 2026-08-02  
**Status:** Approved design  
**Project:** QuestionExamPredictionEngine

## 1. Purpose

Organize the repository's existing grading, cognitive-analysis, weak-topic, question-analysis, and trend-analysis capabilities behind three stable agent-style interfaces. Future retrieval, misconception, clustering, and forecasting models must plug into the same interfaces without rewriting the API or current analytical services.

The agents are typed workflow components, not autonomous chatbots. Models remain independently testable tools. Agents coordinate those tools, validate their outputs, attach evidence, and return Pydantic models. A central orchestrator controls execution order, persistence, retries, and audit metadata.

## 2. Goals

- Reuse current models and analytical functions without duplicating their logic.
- Separate question mapping, answer analysis, and cohort prediction into clear responsibilities.
- Allow future models to replace or extend current tools through stable adapter interfaces.
- Preserve source citations for semantic mappings and misconception explanations.
- Keep deterministic scoring and analytics available when retrieval or language-model services fail.
- Distinguish descriptive historical trends from validated future-topic forecasts.
- Make every workflow run reproducible through input hashes, model versions, and immutable result bundles.

## 3. Non-goals

- The first implementation will not create free-running or mutually conversational LLM agents.
- It will not replace the current grading formulas merely to make them appear agentic.
- It will not label `analyze_trends()` or topic matching as future prediction.
- It will not store student answers in the lecture-material ChromaDB collection.
- It will not generate future-topic probabilities until a forecasting model has passed temporal evaluation.
- It will not introduce a distributed task queue in the first implementation.

## 4. Existing capabilities to preserve

The design wraps the following current capabilities:

- `src/analysis/grading/service.py`: semantic similarity, concept scoring, marks, and feedback.
- `src/analysis/exam_analysis.py`: per-answer report construction and analytical orchestration.
- `src/analysis/scoring/cognitive.py`: Bloom-level and cognitive-alignment scoring.
- `src/analytics/question_analysis.py`: question-level summaries.
- `src/analytics/misunderstood_questions.py`: frequently misunderstood question detection.
- `src/analytics/weak_topic_analysis.py` and `weak_topic_model.py`: weak-topic features and classification.
- `src/analytics/cognitive_gap_analysis.py`: cognitive-gap analysis.
- `src/analytics/student_analysis.py`: student summaries.
- `src/prediction/topic_prediction.py`: existing-topic text matching only.
- `src/prediction/trend_analysis.py`: descriptive historical trend summaries only.

Existing functions remain domain services. Agent classes call them through adapters instead of copying their calculations.

## 5. Selected approach

Use a typed hybrid workflow with three agents and one orchestrator.

This approach was selected over thin wrappers because thin wrappers would not establish durable contracts for future models. It was selected over autonomous LLM agents because grading, aggregation, and forecasting must be reproducible and independently evaluable.

An LLM may be used only for bounded semantic tasks such as rubric mapping or misconception explanation. Its output must validate against a Pydantic schema, cite retrieved evidence, and have deterministic fallbacks. The forecasting probability must come from an evaluated statistical or machine-learning model, not an LLM assertion.

## 6. Proposed package organization

```text
src/
├── agents/
│   ├── __init__.py
│   ├── contracts.py
│   ├── model_registry.py
│   ├── orchestrator.py
│   ├── question_knowledge_agent.py
│   ├── answer_misconception_agent.py
│   └── cohort_prediction_agent.py
├── retrieval/
│   ├── __init__.py
│   ├── contracts.py
│   ├── chroma_repository.py
│   └── lecture_ingestion.py
├── forecasting/
│   ├── __init__.py
│   ├── contracts.py
│   ├── features.py
│   ├── topic_forecaster.py
│   └── evaluation.py
└── analysis/
    └── existing modules remain domain services
```

API request and response schemas remain under `src/api/schemas/`. Agent contracts belong under `src/agents/` because they are internal workflow interfaces and should not be coupled directly to HTTP.

## 7. Agent responsibilities

### 7.1 Question Knowledge Agent

**Purpose:** Convert an exam question and its rubric into a normalized, evidence-backed question mapping.

**Current tools:**

- Exam JSON parsing.
- Canonical topic resolution through `resolve_topic()`.
- Current Bloom classification.
- Existing-topic matching as a fallback candidate generator.

**Future tools:**

- ChromaDB lecture-material retrieval.
- Semantic topic discovery or clustering.
- Structured rubric-criterion mapping.
- Optional LLM mapping constrained by retrieved sources.

**Output:** `QuestionMappingResult`.

The agent runs once per question part for a given exam and input version. Its result is cached and reused for every student answer to that question part.

### 7.2 Answer and Misconception Agent

**Purpose:** Evaluate one student answer against the mapped question, rubric, and evidence sources.

**Current tools:**

- `grade_answer()`.
- Concept-keyword extraction and concept scoring.
- Cognitive scoring.
- Existing per-answer report fields from `build_student_reports()`.

**Future tools:**

- Structured misconception extraction.
- Evidence-backed feedback generation.
- A lecturer-labelled misconception classifier or a bounded LLM adapter.

**Output:** `AnswerAnalysisResult`.

Deterministic marks and scores remain authoritative unless a separately validated grading model is introduced. An LLM may explain a result but must not silently modify the mark.

### 7.3 Cohort Analytics and Prediction Agent

**Purpose:** Aggregate question mappings and answer analyses into cohort insights and, when available, validated future-topic forecasts.

**Current tools:**

- Question summaries.
- Student summaries.
- Weak-topic analysis.
- Misunderstood-question analysis.
- Cognitive-gap analysis.
- Descriptive historical trends.

**Future tools:**

- Topic recurrence and interval features.
- Marks, Bloom-level, difficulty, and cluster trends.
- Temporally evaluated topic-ranking or probability model.
- Forecast calibration and baseline comparison.

**Output:** `CohortPredictionResult`.

If the forecast model is missing, unvalidated, or operating outside its supported data range, the agent omits `future_topic_probabilities` and returns a warning. It continues returning descriptive cohort analytics.

## 8. Orchestrator

`ExamAnalysisOrchestrator` is the only component allowed to coordinate agents and persist a complete workflow result.

Execution order:

1. Validate and normalize the exam, rubric, answer, and existing-mark inputs.
2. Create an `AgentRunContext` containing `run_id`, input hash, timestamps, and model versions.
3. Run the Question Knowledge Agent once for every question part.
4. Run the Answer and Misconception Agent for each student-answer part using the cached question mapping.
5. Run the Cohort Analytics and Prediction Agent after all available answer results have been collected.
6. Persist the immutable workflow result bundle and final run status.

Agents do not write files, databases, or ChromaDB records during analysis. Ingestion and persistence are explicit orchestrator-level operations. This keeps agents deterministic and easy to test.

## 9. Model registry and adapters

`ModelRegistry` provides lazy access to models and services through stable protocols. It records a name, semantic version, artifact identifier, load status, and supported operation for every model.

Initial registry entries:

- Similarity model.
- Cognitive Bloom model.
- Weak-topic model.

Future registry entries:

- Lecture retrieval embedding model.
- Rubric mapper.
- Misconception extractor.
- Topic clustering model.
- Future-topic forecasting model.

Agents depend on protocols such as `SimilarityScorer`, `KnowledgeRetriever`, `MisconceptionExtractor`, and `TopicForecaster`, not concrete model classes. A missing optional adapter produces a typed capability warning rather than an import failure for the whole API.

## 10. Core contracts

### 10.1 AgentRunContext

- `run_id`: unique immutable identifier.
- `input_hash`: hash of normalized workflow inputs.
- `exam_id`: normalized exam identifier.
- `started_at`: timezone-aware timestamp.
- `model_versions`: mapping of capability to model version.
- `warnings`: run-level warnings.

### 10.2 SourceCitation

- `source_id`: stable document or chunk identifier.
- `source_path`: original lecture or rubric path.
- `page`: optional page or slide number.
- `chunk_id`: stable ChromaDB chunk identifier.
- `excerpt`: short supporting excerpt.
- `retrieval_distance`: optional raw retrieval distance.

### 10.3 QuestionMappingResult

- `exam_id`, `question_id`, and `part_id`.
- `question_text` and `max_marks`.
- `topic_ids` and optional topic scores.
- `rubric_criteria`.
- `required_bloom_level`.
- `source_citations`.
- `mapping_confidence` in the range 0 to 1.
- `status`: `success`, `partial`, or `failed`.
- `warnings`.

### 10.4 AnswerAnalysisResult

- `student_id`, `question_id`, and `part_id`.
- `marks_obtained` and `max_marks`.
- `similarity_score`, `concept_score`, and `cognitive_score`.
- `misconceptions`.
- `weak_concepts`.
- `feedback`.
- `analysis_confidence`.
- `status` and `warnings`.

Every misconception contains a normalized concept identifier, misconception type, answer evidence, expected understanding, source citations, and confidence.

### 10.5 CohortPredictionResult

- `exam_id`.
- `question_summaries`.
- `student_summaries`.
- `weak_topics`.
- `misunderstood_questions`.
- `cognitive_gaps`.
- `historical_trends`.
- `future_topic_probabilities`.
- `forecast_model_version`.
- `status` and `warnings`.

Every future-topic result contains a topic, probability, forecast year, supporting features, training-year range, model version, and calibration status.

## 11. ChromaDB knowledge storage

Lecture materials and rubric sources are ingested before analysis. Text is split into stable chunks, embedded, and upserted into a persistent collection.

Each chunk uses a deterministic identifier derived from the course, source checksum, page or slide, and chunk index. Metadata contains:

- `course_id`.
- `module_id`.
- `topic_id`, when known.
- `source_type`: lecture, textbook, rubric, or model answer.
- `source_path`.
- `page` or slide number.
- `source_checksum`.
- `ingestion_version`.

The Question Knowledge Agent retrieves documents with metadata filters for the relevant course and, where applicable, module or source type. Query results include documents, metadata, and distances so citations can be reconstructed and validated.

Student identifiers, answers, scores, and cohort results are not stored in the lecture-material collection. They remain in the operational data store.

## 12. Error handling and fallbacks

- Invalid top-level inputs fail the workflow before any model runs.
- Item-level failures produce failed or partial item results and do not abort unrelated questions or students.
- If ChromaDB retrieval fails or returns insufficient evidence, Agent 1 falls back to exam topic metadata and question text, marks the result partial, and emits a warning.
- If misconception extraction fails, Agent 2 still returns current deterministic grading and analytical scores.
- If the forecast model is unavailable or not validated, Agent 3 returns descriptive analytics and omits probabilities.
- Low-confidence semantic mappings include warnings and can be routed for lecturer review.
- Optional model failures never cause the application to misrepresent fallback output as model output.

The orchestrator records error type, affected item, capability, model version, and whether a fallback was used. Logs must not contain full student answers by default.

## 13. Persistence and idempotency

The first implementation may continue reading existing JSON through adapters. The workflow API must not depend directly on file paths, allowing a later PostgreSQL or MongoDB adapter.

An input hash is calculated from normalized exam, rubric, answer, and configuration data. Repeating the same request with the same model versions may return the existing completed result. A changed model version creates a new run even when the input data is unchanged.

Persisted result bundles are immutable. Corrections or lecturer approvals create a new revision linked to the original run.

## 14. API boundary

Preserve all existing endpoints and behavior. Add a workflow endpoint:

`POST /agent-workflows/analyze-exam`

The endpoint accepts an exam identifier or supplied exam data, optional rubric data, student answers or their dataset identifier, existing marks, and workflow thresholds. It returns a run identifier, overall status, agent summaries, warnings, and the combined result when processing is synchronous.

The initial dataset size supports synchronous execution. A later asynchronous job adapter may be added without changing agent contracts.

## 15. Security and privacy

- Separate academic-source retrieval data from student operational data.
- Avoid putting full student answers or personally identifying data in logs.
- Validate file types and sizes during source ingestion.
- Store source checksums and ingestion versions for auditability.
- Restrict lecturer review and model-management operations separately from student-facing results.
- Treat LLM providers as optional external processors and send only the minimum necessary text when one is configured.

## 16. Testing and evaluation

### Unit and contract tests

- Validate every Pydantic contract, including score bounds and required warning behavior.
- Test every adapter independently from agent orchestration.
- Test fallback paths for missing models, retrieval failures, invalid model output, and low confidence.
- Ensure agents have no persistence side effects.

### Regression tests

- Existing grading, weak-topic, cognitive, question, student, and trend tests continue passing.
- Agent wrappers return the same underlying current-model scores for the same inputs.
- Existing API endpoints remain backward compatible.

### Integration tests

- Run a small exam with several questions and student answers through all three agents.
- Confirm Agent 1 executes once per question part and its mapping is reused.
- Confirm a single-answer failure does not stop cohort analysis.
- Confirm citations resolve to actual indexed chunks.
- Confirm persisted model versions and input hashes match the run.

### Misconception evaluation

Use lecturer-labelled answers containing known misconceptions. Measure misconception-label precision, recall, and citation validity. Explanations are reviewed separately from grading accuracy.

### Forecast evaluation

Use temporal validation only: train through year `Y` and predict topics for `Y+1`. Report Precision@K, Recall@K, Brier score, calibration, and performance relative to frequency and recency baselines. A model may publish future probabilities only when its evaluation artifact records the supported course, training years, metrics, and calibration status.

## 17. Delivery phases

### Phase 1: Agent foundation

Introduce contracts, model protocols, registry, thin adapters over current services, orchestrator, and regression tests. No current scoring behavior changes.

### Phase 2: Knowledge mapping

Add lecture and rubric ingestion, ChromaDB retrieval, citations, and the Question Knowledge Agent's semantic mapping capability.

### Phase 3: Misconception analysis

Add structured misconception extraction, lecturer-labelled evaluation data, citation-backed feedback, and deterministic fallbacks.

### Phase 4: Forecasting

Build the temporal feature table, baselines, forecast model, calibration, evaluation artifact, and future-topic output.

### Phase 5: Product integration

Add the workflow endpoint, persistent operational storage, audit records, lecturer review, and role-specific presentation.

## 18. Acceptance criteria

- All existing regression tests pass without changing current scoring semantics.
- Each agent exposes one typed `run` interface and depends only on declared protocols.
- Agent 1 returns stable source citations or an explicit partial-result warning.
- Agent 2 always preserves deterministic grading when optional misconception analysis fails.
- Agent 3 never presents historical slopes or LLM text as forecast probabilities.
- One orchestrated integration test exercises all three agents and partial-failure behavior.
- Every persisted run records its normalized input hash and model versions.
- Future-topic probabilities are disabled until temporal evaluation and calibration metadata are available.

