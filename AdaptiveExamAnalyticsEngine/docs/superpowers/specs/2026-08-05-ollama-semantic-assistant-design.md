# Local Ollama Semantic Assistant and Embedding Layer Design

**Date:** 2026-08-05
**Status:** Approved design, pending written-spec review
**System:** Multi-agent LMS research platform
**Component:** Predictive Learning Analytics and Intelligent Question Generator — local LLM and embedding layers

## 1. Purpose

This component wires a locally hosted Ollama Qwen model and local sentence embeddings into the existing deterministic analytics core. It delivers the four bounded Qwen roles from the approved design (classification, misconception summaries, study actions, candidate-question generation) plus embedding similarity and hierarchical clustering for recurring sub-concept discovery and candidate-question similarity gating.

The integration replaces the original Colab-batch-worker plan (spec section 17) with an in-process, local-first architecture. There is no GPU requirement and no cloud dependency.

## 2. Scope

### 2.1 In scope

- Async Ollama HTTP client against the native `/api/generate` endpoint with JSON-mode output.
- Pydantic-validated structured outputs for four roles:
  1. Topic / Bloom / question-type / key-concept classification (adjudication layer).
  2. Evidence-grounded misconception summaries.
  3. Evidence-grounded student study actions.
  4. Candidate-question, model-answer, and rubric generation.
- Embedding service using `sentence-transformers/all-MiniLM-L6-v2` (CPU-friendly).
- Agglomerative hierarchical clustering for recurring sub-concept discovery.
- Candidate-question semantic-similarity gate against historical questions.
- Graceful degradation: deterministic analytics continue when Ollama or the embedding model is unavailable.
- New environment configuration for Ollama and embedding settings.

### 2.2 Out of scope

- Fine-tuning Qwen (dataset too small; explicitly excluded by the approved design).
- Training a new embedding model.
- Google Colab worker notebook.
- Embedding index scaling or vector database.
- BERTopic, LDA, TF-IDF clustering in production (these remain research baselines only).
- FastAPI HTTP endpoints and React dashboards (separate subsequent iteration).

## 3. Constraints and design principles

- The LLM enriches, classifies, explains, and generates; it never calculates marks, mastery, coverage, or recommendation scores. All numeric conclusions remain deterministic (approved design section 3).
- Qwen classification is an adjudicating signal layered over the rules-based baseline, not a replacement.
- Invalid or non-conforming LLM JSON is retried once with the schema error, then routed to lecturer review.
- Model self-reported confidence is never treated as a calibrated probability.
- Inferred misconceptions are labelled `inferred_low_confidence` and never presented as confirmed rubric failures.
- Student-facing language is bounded to the observed examination and never asserts permanent inability.
- The embedding model is optional; its absence must not break deterministic analytics.
- Both rules output and Qwen output are retained for the ablation/evaluation study.
- No committed credentials; Ollama runs on `localhost`.

## 4. Chosen architecture

In-process async service layers over the existing deterministic core:

```
app/llm/
  ollama.py          # async httpx client, JSON-mode generate, retry logic
  schemas.py         # shared Pydantic response models
  roles/
    __init__.py
    classify.py      # ClassificationResponse
    misconceptions.py# MisconceptionSummary
    study_actions.py # StudyActions
    generate.py      # CandidateQuestions
app/embeddings/
  __init__.py
  embedder.py        # MiniLM wrapper, cosine similarity
  cluster.py         # agglomerative hierarchical clustering
app/services/
  llm_service.py     # orchestrates roles with degradation
```

`app/services/analytics.py` continues to own deterministic math. `app/services/llm_service.py` owns LLM/embedding orchestration and exposes degraded-mode fallbacks.

## 5. Configuration

New settings in `app/config.py` (all with `.env` overrides):

- `OLLAMA_BASE_URL` = `http://localhost:11434`
- `OLLAMA_MODEL` = `qwen2.5:3b-instruct`
- `OLLAMA_TIMEOUT` = `120` (seconds)
- `OLLAMA_CLASSIFY_TEMPERATURE` = `0.2`
- `OLLAMA_GENERATE_TEMPERATURE` = `0.8`
- `EMBEDDING_MODEL` = `sentence-transformers/all-MiniLM-L6-v2`
- `EMBEDDING_AVAILABLE` = `true` (runtime flag; `false` skips embedding steps)
- `CANDIDATE_SIMILARITY_THRESHOLD` = `0.85` (candidates above this are flagged/rejected)

`.env.example` gains the Ollama/embedding keys. The embedding runtime dependency set is declared in `requirements-embeddings.txt` so the deterministic core does not require torch.

## 6. Ollama client

`app/llm/ollama.py` provides an async client:

- `generate(prompt: str, *, schema_name: str, temperature: float) -> dict`
- Uses `httpx.AsyncClient` against `{OLLAMA_BASE_URL}/api/generate` with JSON body: `{"model", "prompt", "stream": false, "format": "json", "options": {"temperature", "num_predict": 2048}}`.
- On non-200 response or network error: raises `OllamaUnavailable`.
- On 200 but JSON that fails schema validation: caller retries once, appending the validation error to the prompt; second failure returns a `review_flag` result.

Classification decoding is near-deterministic (`temperature=0.2`); candidate generation uses controlled sampling (`temperature=0.8`) for diverse alternatives.

## 7. Qwen roles and response schemas

All role outputs are validated by Pydantic. Field names follow the approved design's canonical vocabulary.

### 7.1 Classification (`roles/classify.py`)

`ClassificationResponse`:
- `primary_topic: str` — must be one of the eight controlled topics.
- `topic_weights: dict[str, float]` — weights must sum to 1.0; keys within the taxonomy.
- `bloom_level: str` — one of the six revised Bloom levels.
- `question_type: str` — one of the controlled question types.
- `key_concepts: list[str]`
- `rationale: str`
- `review_flag: bool`

### 7.2 Misconceptions (`roles/misconceptions.py`)

`MisconceptionSummary`:
- `topic: str`
- `misconceptions: list[{"statement", "evidence", "confidence"}]` where `confidence ∈ {"confirmed", "inferred_low_confidence"}`.
- `source_summary: str` (which evidence stream informed the result).

Inputs: a low-mastery topic, its criteria breakdown, and anonymized answer excerpts. When criteria evidence exists, output may be `confirmed`; when inferred from answers/feedback only, it must be `inferred_low_confidence`.

### 7.3 Study actions (`roles/study_actions.py`)

`StudyActions`:
- `student_key: str`
- `actions: list[{"action", "topic", "rationale", "practice_topics"}]` ordered by weakness.
- `bounded_language: bool` (flag enforced by prompt; surfaced for audit).

Inputs: a student's weak topics and evidence (never cohort data or another student's data).

### 7.4 Candidate generation (`roles/generate.py`)

`CandidateQuestions`:
- `candidates: list[{text, topic, bloom_level, marks, rationale, model_answer, rubric_criteria: list[str]}]`
- `target_topic: str`, `target_bloom: str`, `requested_count: int`

Inputs: an approved `exam_recommendation` (topic, Bloom, question type, mark range) plus a small set of historical questions in the same topic for novelty context.

## 8. Classification adjudication flow

1. `app/classifier/rules.py` classifies the question text.
2. If rules confidence is `high` → rules output is used; no Ollama call.
3. If rules confidence is `medium` or `low` → `llm_service.classify_question` calls Ollama.
4. Both rules and Qwen outputs are stored in `question_catalog.model_output` for the ablation study; lecturer validation remains the authority for the final label.

## 9. Embeddings and clustering

- `app/embeddings/embedder.py`:
  - Lazy-loads `sentence-transformers/all-MiniLM-L6-v2` on first use.
  - `embed(text: str) -> np.ndarray` and `embed_batch(texts: list[str]) -> np.ndarray`.
  - `similarity(a: np.ndarray, b: np.ndarray) -> float` via cosine.
- `app/embeddings/cluster.py`:
  - `hierarchical_clusters(vectors, distance_threshold) -> list[Cluster]` using scikit-learn `AgglomerativeClustering`.
  - Returns per-question cluster labels and a dominant-topic summary per cluster.
- Wiring: `question_catalog.embedding_ref` is populated when embeddings are available; clustering runs across a course's questions to surface recurring sub-concepts (approved design section 7.2).
- If `EMBEDDING_AVAILABLE` is false, `embedding_ref` stays null and the candidate-similarity gate is skipped.

## 10. Candidate-generation similarity gate

After Qwen generates candidates, `llm_service.generate_candidates` embeds each candidate and the historical questions for the target topic. Any candidate whose maximum cosine similarity to a historical question exceeds `CANDIDATE_SIMILARITY_THRESHOLD` (0.85) is flagged for revision or rejected. The similarity check and source question reference are recorded with each candidate (approved design section 11).

## 11. Orchestration and degradation

`app/services/llm_service.py` exposes:

- `classify_question(question_text) -> ClassifyResult` — rules → (maybe) Qwen; always returns rules output on Qwen failure.
- `misconception_summary(topic, criteria, answers) -> MisconceptionSummary | DegradedResult`
- `study_actions(student_key, weak_topics, evidence) -> StudyActions | DegradedResult`
- `generate_candidates(recommendation) -> CandidateQuestions | DegradedResult`
- `embed_and_cluster(questions) -> ClusteringResult`

Degradation contract (approved design section 18):
- `OllamaUnavailable` → role returns `{"status": "degraded", "reason": "ollama_unavailable"}`; callers surface this state and continue with deterministic outputs.
- Invalid schema after one retry → `review_flag: true` with raw output retained.
- Embedding model missing → clustering and similarity gate skipped; analytics unaffected.

## 12. Persistence impact

No new collections. Existing derived collections gain optional fields:

- `question_catalog.embedding_ref: str | None`
- `question_catalog.model_output: dict | None` (already present; now populated with rules + Qwen outputs)
- `analytics_snapshots` may carry per-topic `misconception_summary` and per-student `study_actions` sub-documents.
- `exam_recommendations.candidates[]` carries `similarity_check` and `decision` (already present in the schema).

## 13. Testing and research evaluation

### 13.1 Unit tests (no live model)

- `tests/test_llm_ollama.py` — client request/retry logic against mocked `httpx`.
- `tests/test_llm_classify.py`, `tests/test_llm_misconceptions.py`, `tests/test_llm_study_actions.py`, `tests/test_llm_generate.py` — Pydantic schema validation with sample Ollama JSON fixtures; retry-once behavior; review-flag behavior.
- `tests/test_embeddings_cluster.py` — clustering on tiny synthetic vectors without loading a model.
- `tests/test_llm_service.py` — adjudication flow (high-confidence rules skip Ollama; medium/low calls it; degraded mode returns rules output).

### 13.2 Optional live integration

- `tests/test_ollama_live.py` — gated behind `RUN_OLLAMA_TESTS=1`; requires Ollama running with the configured model.

### 13.3 Research evaluation (deferred to evaluation iteration)

- Dual-lecturer consensus labels compared against rules-only, Qwen-only, and hybrid outputs (approved design section 20.3).
- Candidate-question lecturer ratings (section 20.6) once the frontend workflow exists.

## 14. Implementation order

1. Add Ollama/embedding config keys and `.env.example` entries.
2. Build `app/llm/ollama.py` client with retry logic.
3. Build role schemas and `app/llm/roles/*`.
4. Build `app/embeddings/` (embedder + clustering) and `requirements-embeddings.txt`.
5. Build `app/services/llm_service.py` orchestration with degradation.
6. Wire into `app/services/analytics.py` (classification adjudication; snapshot enrichment).
7. Add unit tests; run full suite.

## 15. Acceptance criteria

- A question with high-confidence rules output is classified without calling Ollama.
- A medium/low-confidence question is classified via Ollama, with both rules and Qwen outputs retained.
- Invalid Qwen JSON is retried once and then flagged for review.
- With Ollama stopped, all deterministic analytics and tests still pass; role calls return degraded status.
- `embed_and_cluster` produces clusters on synthetic vectors; missing embedding model yields a skipped-gate result, not a crash.
- Candidate generation applies the similarity threshold and records `similarity_check`.
- Misconception and study-action outputs conform to their Pydantic schemas and respect the `inferred_low_confidence` rule.
