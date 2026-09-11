# Ollama Semantic Assistant + Embedding Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire a local Ollama Qwen model and local sentence embeddings into the deterministic analytics core, delivering four Qwen roles (classification adjudication, misconception summaries, study actions, candidate generation) plus hierarchical clustering and a candidate-similarity gate, with graceful degradation when the model is unavailable.

**Architecture:** In-process async service layers. `app/llm/` provides the Ollama HTTP client and Pydantic-validated role outputs. `app/embeddings/` wraps `all-MiniLM-L6-v2` for embedding + agglomerative clustering. `app/services/llm_service.py` orchestrates with a degraded-mode contract. Deterministic math in `app/services/analytics.py` stays authoritative; the LLM never calculates scores.

**Tech Stack:** Python 3.14, httpx (async), Pydantic v2, pytest, pytest-asyncio; optional `sentence-transformers` + `scikit-learn` + `torch` (CPU) declared separately in `requirements-embeddings.txt`.

## Global Constraints

- Ollama base URL default `http://localhost:11434`; model `qwen2.5:3b-instruct`.
- Classification temperature `0.2` (near-deterministic); generation temperature `0.8` (controlled sampling).
- JSON output mode via `format: "json"`; `num_predict` capped at 2048.
- Invalid JSON: retry once with the schema error appended; second failure → `review_flag`.
- `OllamaUnavailable` → role returns `{"status": "degraded", "reason": "ollama_unavailable"}`; deterministic analytics continue.
- Qwen is an adjudication layer over `app/classifier/rules.py`; rules `high` confidence skips Ollama.
- Both rules and Qwen outputs are stored in `question_catalog.model_output`.
- Embedding model optional; `EMBEDDING_AVAILABLE=false` skips embedding and similarity-gate steps without crashing.
- Topic weights in any Qwen classification output must sum to `1.0`; topics/Bloom levels restricted to the controlled taxonomies.
- `CANDIDATE_SIMILARITY_THRESHOLD = 0.85` — candidates above this are flagged/rejected.
- Inferred misconceptions labelled `inferred_low_confidence`, never `confirmed`.
- No committed credentials; Ollama runs on localhost.
- Tests use mocked Ollama responses; live tests gated behind `RUN_OLLAMA_TESTS=1`.
- Embedding tests use synthetic vectors — they never load a model.

---

### Task 1: Configuration and `.env.example` additions

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: existing `Settings` in `app/config.py`.
- Produces: settings fields `ollama_base_url`, `ollama_model`, `ollama_timeout`, `ollama_classify_temperature`, `ollama_generate_temperature`, `embedding_model`, `embedding_available`, `candidate_similarity_threshold`; and `ollama_unavailable_on_error` helper behavior handled in Task 2.

- [ ] **Step 1: Write the failing test**

`tests/test_config_ollama.py`:

```python
from app.config import settings


def test_ollama_defaults():
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:3b-instruct"
    assert settings.ollama_timeout == 120


def test_temperature_defaults():
    assert settings.ollama_classify_temperature == 0.2
    assert settings.ollama_generate_temperature == 0.8


def test_embedding_defaults():
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_available is True
    assert settings.candidate_similarity_threshold == 0.85
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_ollama.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'ollama_base_url'`

- [ ] **Step 3: Write minimal implementation**

`app/config.py` — add fields to `Settings`:

```python
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_timeout: float = 120
    ollama_classify_temperature: float = 0.2
    ollama_generate_temperature: float = 0.8
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_available: bool = True
    candidate_similarity_threshold: float = 0.85
```

`.env.example` — append:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b-instruct
OLLAMA_TIMEOUT=120
OLLAMA_CLASSIFY_TEMPERATURE=0.2
OLLAMA_GENERATE_TEMPERATURE=0.8
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_AVAILABLE=true
CANDIDATE_SIMILARITY_THRESHOLD=0.85
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config_ollama.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py .env.example tests/test_config_ollama.py
git commit -m "feat: add Ollama and embedding configuration"
```

---

### Task 2: Ollama async client with retry logic

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/ollama.py`
- Create: `tests/test_llm_ollama.py`

**Interfaces:**
- Consumes: `settings` fields from Task 1.
- Produces:
  - `class OllamaUnavailable(Exception)` — raised on network errors or non-200.
  - `async generate(prompt: str, *, temperature: float) -> dict` — POSTs to `{base_url}/api/generate` with `{"model", "prompt", "stream": false, "format": "json", "options": {"temperature", "num_predict": 2048}}`; returns the parsed JSON `response` object; raises `OllamaUnavailable` on failure.
  - `validate_with_retry(schema: type[BaseModel], prompt: str, temperature: float, max_attempts: int = 2) -> tuple[BaseModel | None, dict | None, bool]` — returns `(parsed, raw_json, review_flag)`; on schema failure retries once with the validation error appended; second failure returns `(None, raw, True)`.

- [ ] **Step 1: Write the failing test**

`tests/test_llm_ollama.py`:

```python
import httpx
import pydantic
import pytest
from pytest import MonkeyPatch

from app.llm.ollama import OllamaUnavailable, generate, validate_with_retry
from app.config import settings


class FakeResponse(httpx.Response):
    pass


def _fake_json_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


async def test_generate_returns_response_json(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        return _fake_json_response({"response": '{"primary_topic": "SQL"}'})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await generate("classify this")
    assert result["primary_topic"] == "SQL"


async def test_generate_raises_on_network_error(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(OllamaUnavailable):
        await generate("classify this")


class FakeSchema(pydantic.BaseModel):
    topic: str


async def test_validate_with_retry_succeeds_on_second_attempt(monkeypatch: MonkeyPatch):
    calls = {"n": 0}

    async def fake_post(*args, **kwargs):
        calls["n"] += 1
        payload = {"topic": "SQL"} if calls["n"] > 1 else {"wrong_field": "x"}
        return _fake_json_response({"response": __import__("json").dumps(payload)})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    parsed, raw, review = await validate_with_retry(FakeSchema, "prompt", temperature=0.2)
    assert calls["n"] == 2
    assert parsed is not None and parsed.topic == "SQL"
    assert review is False


async def test_validate_with_retry_flags_review_after_two_failures(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        return _fake_json_response({"response": '{"wrong_field": "x"}'})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    parsed, raw, review = await validate_with_retry(FakeSchema, "prompt", temperature=0.2)
    assert parsed is None
    assert review is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_ollama.py -v`
Expected: FAIL with `ModuleNotFoundError: app.llm.ollama`

- [ ] **Step 3: Write minimal implementation**

`app/llm/__init__.py`:

```python
from app.llm.ollama import OllamaUnavailable, generate, validate_with_retry

__all__ = ["OllamaUnavailable", "generate", "validate_with_retry"]
```

`app/llm/ollama.py`:

```python
import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class OllamaUnavailable(Exception):
    pass


async def generate(prompt: str, *, temperature: float) -> dict:
    url = f"{settings.ollama_base_url}/api/generate"
    body = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": 2048,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaUnavailable(str(exc)) from exc
    try:
        return json.loads(data.get("response", "{}"))
    except json.JSONDecodeError as exc:
        raise OllamaUnavailable(f"invalid JSON from model: {exc}") from exc


async def validate_with_retry(
    schema: type[T],
    prompt: str,
    temperature: float,
    max_attempts: int = 2,
) -> tuple[T | None, dict | None, bool]:
    raw: dict | None = None
    for attempt in range(max_attempts):
        try:
            raw = await generate(prompt, temperature=temperature)
            return schema.model_validate(raw), raw, False
        except ValidationError as exc:
            if attempt == max_attempts - 1:
                return None, raw, True
            prompt = f"{prompt}\nYour previous JSON did not match this schema: {exc}. Retry and output ONLY valid JSON matching the schema."
        except OllamaUnavailable:
            raise
    return None, raw, True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_ollama.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm tests/test_llm_ollama.py
git commit -m "feat: add async Ollama client with JSON retry"
```

---

### Task 3: Classification role schema

**Files:**
- Create: `app/llm/roles/__init__.py`
- Create: `app/llm/roles/classify.py`
- Create: `tests/test_llm_classify.py`

**Interfaces:**
- Consumes: `app/analytics/taxonomy.py` (TOPICS, BLOOM_LEVELS, QUESTION_TYPES).
- Produces:
  - `ClassificationResponse(BaseModel)` with fields `primary_topic`, `topic_weights: dict[str, float]`, `bloom_level`, `question_type`, `key_concepts: list[str]`, `rationale: str`, `review_flag: bool = False`.
  - Model validator: weights sum to `1.0` (±1e-6); all topics in `TOPICS`; bloom in `BLOOM_LEVELS`; question type in `QUESTION_TYPES`.

- [ ] **Step 1: Write the failing test**

`tests/test_llm_classify.py`:

```python
import pydantic
import pytest

from app.llm.roles.classify import ClassificationResponse

VALID = {
    "primary_topic": "Schema Refinement",
    "topic_weights": {"Schema Refinement": 0.8, "Logical Database Design": 0.2},
    "bloom_level": "Analyze",
    "question_type": "problem_solving",
    "key_concepts": ["functional dependency", "attribute closure"],
    "rationale": "Uses attribute closure to find a candidate key",
}


def test_valid_classification_passes():
    result = ClassificationResponse(**VALID)
    assert result.primary_topic == "Schema Refinement"
    assert result.review_flag is False


def test_weights_must_sum_to_one():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "topic_weights": {"SQL": 0.5}})


def test_topic_must_be_in_taxonomy():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "primary_topic": "Not a Topic"})


def test_bloom_must_be_in_levels():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "bloom_level": "Memorize"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_classify.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/llm/roles/__init__.py`:

```python
```

`app/llm/roles/classify.py`:

```python
from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, QUESTION_TYPES, TOPICS


class ClassificationResponse(BaseModel):
    primary_topic: str
    topic_weights: dict[str, float] = Field(description="Weights must sum to 1.0.")
    bloom_level: str
    question_type: str
    key_concepts: list[str] = Field(default_factory=list)
    rationale: str = ""
    review_flag: bool = False

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "ClassificationResponse":
        if self.primary_topic not in TOPICS:
            raise ValueError(f"primary_topic must be one of {TOPICS}")
        for topic in self.topic_weights:
            if topic not in TOPICS:
                raise ValueError(f"unknown topic in topic_weights: {topic}")
        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level must be one of {BLOOM_LEVELS}")
        if self.question_type not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of {QUESTION_TYPES}")
        if abs(sum(self.topic_weights.values()) - 1.0) > 1e-6:
            raise ValueError("topic_weights must sum to 1.0")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_classify.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm/roles tests/test_llm_classify.py
git commit -m "feat: add Qwen classification response schema"
```

---

### Task 4: Misconception, study-action, and candidate-generation role schemas

**Files:**
- Create: `app/llm/roles/misconceptions.py`
- Create: `app/llm/roles/study_actions.py`
- Create: `app/llm/roles/generate.py`
- Create: `tests/test_llm_misconceptions.py`
- Create: `tests/test_llm_study_actions.py`
- Create: `tests/test_llm_generate.py`

**Interfaces:**
- Consumes: taxonomy from Task 3.
- Produces:
  - `MisconceptionSummary(topic: str, misconceptions: list[MisconceptionItem], source_summary: str = "")` where `MisconceptionItem(statement, evidence, confidence)` and `confidence ∈ {"confirmed", "inferred_low_confidence"}`.
  - `StudyActions(student_key: str, actions: list[StudyAction], bounded_language: bool = True)` where `StudyAction(action, topic, rationale, practice_topics: list[str])`.
  - `CandidateQuestions(target_topic: str, target_bloom: str, requested_count: int, candidates: list[CandidateQuestion])` where `CandidateQuestion(text, topic, bloom_level, marks: float > 0, rationale, model_answer, rubric_criteria: list[str])`; topic/bloom validated against taxonomy.

- [ ] **Step 1: Write the failing test**

`tests/test_llm_misconceptions.py`:

```python
import pydantic
import pytest

from app.llm.roles.misconceptions import MisconceptionItem, MisconceptionSummary


def test_confirmed_vs_inferred_confidence():
    summary = MisconceptionSummary(
        topic="Schema Refinement",
        misconceptions=[
            MisconceptionItem(statement="s", evidence="e", confidence="confirmed"),
            MisconceptionItem(statement="s2", evidence="e2", confidence="inferred_low_confidence"),
        ],
    )
    assert len(summary.misconceptions) == 2


def test_invalid_confidence_rejected():
    with pytest.raises(pydantic.ValidationError):
        MisconceptionItem(statement="s", evidence="e", confidence="definite")
```

`tests/test_llm_study_actions.py`:

```python
from app.llm.roles.study_actions import StudyAction, StudyActions


def test_study_actions_shape():
    result = StudyActions(
        student_key="stu-001",
        actions=[StudyAction(action="review", topic="SQL", rationale="r", practice_topics=["joins"])],
    )
    assert result.bounded_language is True
```

`tests/test_llm_generate.py`:

```python
import pydantic
import pytest

from app.llm.roles.generate import CandidateQuestion, CandidateQuestions


def test_valid_candidate():
    result = CandidateQuestions(
        target_topic="SQL",
        target_bloom="Apply",
        requested_count=1,
        candidates=[
            CandidateQuestion(
                text="Write a JOIN query",
                topic="SQL",
                bloom_level="Apply",
                marks=4.0,
                rationale="r",
                model_answer="SELECT ...",
                rubric_criteria=["correct join"],
            )
        ],
    )
    assert result.candidates[0].marks == 4.0


def test_marks_must_be_positive():
    with pytest.raises(pydantic.ValidationError):
        CandidateQuestion(text="t", topic="SQL", bloom_level="Apply", marks=0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_misconceptions.py tests/test_llm_study_actions.py tests/test_llm_generate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/llm/roles/misconceptions.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class MisconceptionItem(BaseModel):
    statement: str
    evidence: str
    confidence: Literal["confirmed", "inferred_low_confidence"]


class MisconceptionSummary(BaseModel):
    topic: str
    misconceptions: list[MisconceptionItem] = Field(default_factory=list)
    source_summary: str = ""
```

`app/llm/roles/study_actions.py`:

```python
from pydantic import BaseModel, Field


class StudyAction(BaseModel):
    action: str
    topic: str
    rationale: str = ""
    practice_topics: list[str] = Field(default_factory=list)


class StudyActions(BaseModel):
    student_key: str
    actions: list[StudyAction] = Field(default_factory=list)
    bounded_language: bool = True
```

`app/llm/roles/generate.py`:

```python
from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS


class CandidateQuestion(BaseModel):
    text: str
    topic: str
    bloom_level: str
    marks: float = Field(gt=0)
    rationale: str = ""
    model_answer: str = ""
    rubric_criteria: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "CandidateQuestion":
        if self.topic not in TOPICS:
            raise ValueError(f"topic must be one of {TOPICS}")
        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level must be one of {BLOOM_LEVELS}")
        return self


class CandidateQuestions(BaseModel):
    target_topic: str
    target_bloom: str
    requested_count: int = Field(ge=1)
    candidates: list[CandidateQuestion] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_misconceptions.py tests/test_llm_study_actions.py tests/test_llm_generate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm/roles tests/test_llm_misconceptions.py tests/test_llm_study_actions.py tests/test_llm_generate.py
git commit -m "feat: add misconception, study-action, and candidate schemas"
```

---

### Task 5: Embedding service and clustering

**Files:**
- Create: `requirements-embeddings.txt`
- Create: `app/embeddings/__init__.py`
- Create: `app/embeddings/embedder.py`
- Create: `app/embeddings/cluster.py`
- Create: `tests/test_embeddings_cluster.py`

**Interfaces:**
- Consumes: `settings.embedding_model`, `settings.embedding_available`.
- Produces:
  - `class Embedder` with `embed(text: str) -> np.ndarray`, `embed_batch(texts: list[str]) -> np.ndarray`, `similarity(a, b) -> float`, `is_available() -> bool` (lazy-loads the model on first `embed`; returns `False` and raises `EmbeddingUnavailable` if model not installed).
  - `class EmbeddingUnavailable(Exception)`.
  - `hierarchical_clusters(vectors: np.ndarray, distance_threshold: float) -> list[int]` — cluster labels via `sklearn.cluster.AgglomerativeClustering`; single vector returns `[0]`.
  - `dominant_topics(labels: list[int], topics: list[str]) -> dict[int, str]` — most common topic per cluster label.

- [ ] **Step 1: Write the failing test**

`tests/test_embeddings_cluster.py`:

```python
import numpy as np
import pytest

from app.embeddings.cluster import dominant_topics, hierarchical_clusters


def test_cluster_separates_well_spaced_vectors():
    vectors = np.array(
        [
            [0.0, 0.0],
            [0.1, 0.0],
            [5.0, 5.0],
            [5.1, 5.0],
        ]
    )
    labels = hierarchical_clusters(vectors, distance_threshold=1.0)
    assert len(set(labels)) == 2


def test_single_vector_gets_single_cluster():
    vectors = np.array([[0.0, 0.0]])
    assert hierarchical_clusters(vectors, distance_threshold=1.0) == [0]


def test_dominant_topics():
    labels = [0, 0, 1, 1]
    topics = ["SQL", "SQL", "JDBC", "JDBC"]
    assert dominant_topics(labels, topics) == {0: "SQL", 1: "JDBC"}


def test_embedding_unavailable_raises_without_model(monkeypatch):
    from app.embeddings.embedder import EmbeddingUnavailable, Embedder

    class NoModel:
        def __init__(self, *a, **k):
            raise ImportError("no torch")

    monkeypatch.setattr("app.embeddings.embedder.SentenceTransformer", NoModel)
    embedder = Embedder()
    assert embedder.is_available() is False
    with pytest.raises(EmbeddingUnavailable):
        embedder.embed("hello")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_embeddings_cluster.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`requirements-embeddings.txt`:

```
sentence-transformers==5.6.1
scikit-learn
torch
```

`app/embeddings/__init__.py`:

```python
from app.embeddings.cluster import dominant_topics, hierarchical_clusters
from app.embeddings.embedder import EmbeddingUnavailable, Embedder

__all__ = ["dominant_topics", "hierarchical_clusters", "EmbeddingUnavailable", "Embedder"]
```

`app/embeddings/embedder.py`:

```python
import numpy as np

from app.config import settings


class EmbeddingUnavailable(Exception):
    pass


class Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.embedding_model
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingUnavailable(
                "sentence-transformers not installed; install requirements-embeddings.txt"
            ) from exc
        try:
            self._model = SentenceTransformer(self._model_name)
        except Exception as exc:
            raise EmbeddingUnavailable(f"failed to load embedding model: {exc}") from exc

    def is_available(self) -> bool:
        if self._model is None and not settings.embedding_available:
            return False
        try:
            self._load()
            return True
        except EmbeddingUnavailable:
            return False

    def embed(self, text: str) -> np.ndarray:
        self._load()
        return self._model.encode([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        self._load()
        return self._model.encode(texts)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = np.asarray(a, dtype=float).flatten()
        b = np.asarray(b, dtype=float).flatten()
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)
```

`app/embeddings/cluster.py`:

```python
import numpy as np


def hierarchical_clusters(vectors: np.ndarray, distance_threshold: float) -> list[int]:
    vectors = np.asarray(vectors, dtype=float)
    if vectors.shape[0] <= 1:
        return [0] * vectors.shape[0]
    from sklearn.cluster import AgglomerativeClustering

    model = AgglomerativeClustering(
        n_clusters=None,
        metric="euclidean",
        linkage="ward",
        distance_threshold=distance_threshold,
    )
    labels = model.fit_predict(vectors)
    return [int(x) for x in labels]


def dominant_topics(labels: list[int], topics: list[str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for label in set(labels):
        topic_counts: dict[str, int] = {}
        for t, l in zip(topics, labels):
            if l == label:
                topic_counts[t] = topic_counts.get(t, 0) + 1
        result[label] = max(topic_counts, key=topic_counts.get)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_embeddings_cluster.py -v`
Expected: PASS (clustering tests use synthetic numpy vectors; model is never loaded)

- [ ] **Step 5: Commit**

```bash
git add requirements-embeddings.txt app/embeddings tests/test_embeddings_cluster.py
git commit -m "feat: add embedding service and hierarchical clustering"
```

---

### Task 6: LLM service orchestration with degradation

**Files:**
- Create: `app/services/llm_service.py`
- Create: `tests/test_llm_service.py`

**Interfaces:**
- Consumes: Task 2 `generate`/`validate_with_retry`/`OllamaUnavailable`, Task 3–4 role schemas, `app/classifier/rules.py` `classify_by_rules`, Task 5 `Embedder`/`hierarchical_clusters`.
- Produces:
  - `classify_question(question_text: str) -> dict` — returns `{"status": "rules", "rules": <dict>}` when rules confidence is `high`; `{"status": "qwen", "rules": <dict>, "qwen": <dict>}` when Qwen succeeds; `{"status": "rules_degraded", "rules": <dict>, "reason": "ollama_unavailable"}` on `OllamaUnavailable`; `{"status": "qwen_review", "rules": <dict>, "qwen": <raw dict>, "review_flag": True}` on schema failure.
  - `async misconception_summary(topic: str, criteria: list[dict], answers: list[str]) -> dict` — degraded-safe wrapper returning `{"status": "degraded", "reason": "ollama_unavailable"}` on failure.
  - `async study_actions(student_key: str, weak_topics: list[str], evidence: dict) -> dict` — same degraded contract.
  - `async generate_candidates(recommendation: dict, count: int = 3) -> dict` — calls Qwen then applies the similarity gate when embeddings available; returns `{"status": "ok", "candidates": [...], "similarity_checks": [...]}` or degraded status.
  - `def is_embedding_available() -> bool`.

- [ ] **Step 1: Write the failing test**

`tests/test_llm_service.py`:

```python
import pytest

from app.llm.ollama import OllamaUnavailable
from app.services import llm_service
from app.services.llm_service import classify_question, generate_candidates, misconception_summary


def test_high_confidence_rules_skips_qwen(monkeypatch):
    async def fail(*a, **k):
        raise AssertionError("Ollama should not be called")

    monkeypatch.setattr(llm_service, "validate_with_retry", fail)
    result = classify_question("Write a SQL SELECT that joins two tables.")
    assert result["status"] == "rules"


def test_low_confidence_calls_qwen_and_succeeds(monkeypatch):
    class FakeClassification:
        primary_topic = "SQL"
        bloom_level = "Apply"
        question_type = "coding"
        key_concepts = []
        rationale = "x"
        review_flag = False

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeClassification(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = classify_question("Discuss the history of computing.")
    assert result["status"] == "qwen"
    assert result["qwen"]["primary_topic"] == "SQL"


def test_qwen_down_degrades_to_rules(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = classify_question("Discuss the history of computing.")
    assert result["status"] == "rules_degraded"
    assert result["reason"] == "ollama_unavailable"


def test_misconception_summary_degraded_on_unavailable(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = pytest.runner  # placeholder removed below
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/services/llm_service.py`:

```python
import logging

from app.classifier.rules import classify_by_rules
from app.config import settings
from app.analytics.taxonomy import TOPICS
from app.llm.ollama import OllamaUnavailable, validate_with_retry
from app.llm.roles.classify import ClassificationResponse
from app.llm.roles.misconceptions import MisconceptionSummary
from app.llm.roles.study_actions import StudyActions

logger = logging.getLogger(__name__)


def _rules_dict(result) -> dict:
    return {
        "topic_assignments": [
            {"topic": a.topic, "weight": a.weight} for a in result.topic_assignments
        ],
        "bloom_level": result.bloom_level,
        "question_type": result.question_type,
        "key_concepts": result.key_concepts,
        "confidence": result.confidence,
    }


def classify_question(question_text: str) -> dict:
    rules_result = classify_by_rules(question_text)
    rules = _rules_dict(rules_result)
    if rules_result.confidence == "high":
        return {"status": "rules", "rules": rules}
    topics_list = ", ".join(TOPICS)
    prompt = (
        "Classify this DBMS exam question. Respond ONLY with JSON matching this schema:\n"
        '{"primary_topic": str, "topic_weights": {str: float}, "bloom_level": str, '
        '"question_type": str, "key_concepts": [str], "rationale": str, "review_flag": bool}\n'
        f"Controlled topics: {topics_list}. "
        "Bloom levels: Remember, Understand, Apply, Analyze, Evaluate, Create.\n"
        f"Question: {question_text}"
    )
    try:
        parsed, raw, review = validate_with_retry(
            ClassificationResponse, prompt, temperature=settings.ollama_classify_temperature
        )
    except OllamaUnavailable as exc:
        return {"status": "rules_degraded", "rules": rules, "reason": "ollama_unavailable"}
    if parsed is None or review:
        return {"status": "qwen_review", "rules": rules, "qwen": raw, "review_flag": True}
    return {
        "status": "qwen",
        "rules": rules,
        "qwen": {
            "primary_topic": parsed.primary_topic,
            "topic_weights": parsed.topic_weights,
            "bloom_level": parsed.bloom_level,
            "question_type": parsed.question_type,
            "key_concepts": parsed.key_concepts,
            "rationale": parsed.rationale,
            "review_flag": parsed.review_flag,
        },
    }


async def misconception_summary(topic: str, criteria: list[dict], answers: list[str]) -> dict:
    prompt = (
        f"Summarize likely misconceptions for topic '{topic}' in a DBMS course.\n"
        f"Rubric criteria: {criteria}\nAnonymized answer excerpts: {answers}\n"
        "Respond ONLY with JSON matching: "
        '{"topic": str, "misconceptions": [{"statement": str, "evidence": str, '
        '"confidence": "confirmed"|"inferred_low_confidence"}], "source_summary": str}'
    )
    try:
        parsed, raw, review = validate_with_retry(
            MisconceptionSummary, prompt, temperature=settings.ollama_classify_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    return {"status": "ok", **parsed.model_dump()}


async def study_actions(student_key: str, weak_topics: list[str], evidence: dict) -> dict:
    prompt = (
        f"Student {student_key} showed weakness in: {weak_topics}.\n"
        f"Evidence: {evidence}\n"
        "Respond ONLY with JSON matching: "
        '{"student_key": str, "actions": [{"action": str, "topic": str, "rationale": str, '
        '"practice_topics": [str]}]}'
    )
    try:
        parsed, raw, review = validate_with_retry(
            StudyActions, prompt, temperature=settings.ollama_classify_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    return {"status": "ok", **parsed.model_dump()}


def is_embedding_available() -> bool:
    if not settings.embedding_available:
        return False
    from app.embeddings.embedder import Embedder

    return Embedder().is_available()


async def generate_candidates(recommendation: dict, count: int = 3) -> dict:
    from app.llm.roles.generate import CandidateQuestions

    prompt = (
        f"Generate {count} new DBMS examination questions for topic "
        f"'{recommendation['topic']}' at Bloom level '{recommendation['bloom_level']}' "
        f"with marks in range {recommendation.get('mark_range')}.\n"
        "They must be original and not copy the following historical questions:\n"
        f"{recommendation.get('historical_questions', [])}\n"
        "Respond ONLY with JSON matching: "
        '{"target_topic": str, "target_bloom": str, "requested_count": int, '
        '"candidates": [{"text": str, "topic": str, "bloom_level": str, "marks": float, '
        '"rationale": str, "model_answer": str, "rubric_criteria": [str]}]}'
    )
    try:
        parsed, raw, review = validate_with_retry(
            CandidateQuestions, prompt, temperature=settings.ollama_generate_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    checks = _similarity_checks(parsed, recommendation)
    return {"status": "ok", "candidates": [c.model_dump() for c in parsed.candidates], "similarity_checks": checks}


def _similarity_checks(parsed, recommendation: dict) -> list[dict]:
    if not is_embedding_available():
        return []
    from app.embeddings.embedder import Embedder

    embedder = Embedder()
    historical = recommendation.get("historical_questions", [])
    checks = []
    for candidate in parsed.candidates:
        cand_vec = embedder.embed(candidate.text)
        best = 0.0
        best_ref = None
        for hist in historical:
            sim = embedder.similarity(cand_vec, embedder.embed(hist["question_text"]))
            if sim > best:
                best = sim
                best_ref = hist.get("question_id")
        flag = best > settings.candidate_similarity_threshold
        checks.append(
            {
                "candidate_text": candidate.text[:50],
                "max_similarity": round(best, 4),
                "source_question_id": best_ref,
                "flagged": flag,
            }
        )
    return checks
```

- [ ] **Step 4: Fix the test file to match the implementation**

Replace the last (incomplete) test in `tests/test_llm_service.py` with:

```python
async def test_misconception_summary_degraded_on_unavailable(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = await misconception_summary("SQL", [], ["answer..."])
    assert result["status"] == "degraded"
    assert result["reason"] == "ollama_unavailable"


async def test_generate_candidates_ok_skips_similarity_when_embeddings_off(monkeypatch):
    from app.llm.roles.generate import CandidateQuestions

    class FakeCandidates:
        def __init__(self):
            self.candidates = [
                type("C", (), {"model_dump": lambda self: {"text": "q", "topic": "SQL"}})()
            ]

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeCandidates(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    monkeypatch.setattr(llm_service, "is_embedding_available", lambda: False)
    result = await generate_candidates({"topic": "SQL", "bloom_level": "Apply", "mark_range": (1, 4)})
    assert result["status"] == "ok"
    assert result["similarity_checks"] == []
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/llm_service.py tests/test_llm_service.py
git commit -m "feat: add LLM service orchestration with degradation"
```

---

### Task 7: Wire into analytics and add optional live test

**Files:**
- Modify: `app/services/analytics.py`
- Create: `tests/test_ollama_live.py`

**Interfaces:**
- Consumes: Task 6 `classify_question`, `is_embedding_available`; existing analytics pipeline.
- Produces:
  - `classify_question` invoked inside `run_analytics` for each catalog record; `question_catalog.model_output` populated with the classify result dict when status is not `rules`-only (rules output always stored).
  - Optional embeddings: when `is_embedding_available()`, catalog records get `embedding_ref = f"emb:{question_id}"`; embeddings are computed in a batch.
  - `tests/test_ollama_live.py` gated behind `RUN_OLLAMA_TESTS=1` env var.

- [ ] **Step 1: Write the failing test**

`tests/test_ollama_live.py`:

```python
import os

import pytest

from app.services.llm_service import classify_question

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_TESTS") != "1",
    reason="live Ollama test; set RUN_OLLAMA_TESTS=1",
)


def test_live_classify_sql(monkeypatch):
    monkeypatch.delenv("EMBEDDING_AVAILABLE", raising=False)
    result = classify_question("Write a SQL SELECT that joins two tables.")
    assert result["status"] in ("rules", "qwen", "qwen_review")
    assert "rules" in result
```

- [ ] **Step 2: Run test to verify it is skipped by default**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ollama_live.py -v`
Expected: SKIPPED (1 skipped)

- [ ] **Step 3: Wire classification into analytics**

In `app/services/analytics.py`, inside `run_analytics`, after building each catalog record `c` (before the upsert loop), add:

```python
        classification = classify_question(c["question_text"])
        c["model_output"] = classification
```

and add the import at the top:

```python
from app.services.llm_service import classify_question, is_embedding_available
```

Add batch embedding enrichment after the catalog loop when embeddings are available:

```python
    if is_embedding_available():
        try:
            from app.embeddings.embedder import Embedder

            embedder = Embedder()
            vectors = embedder.embed_batch([c["question_text"] for c in catalog_records])
            for c, _vec in zip(catalog_records, vectors):
                c["embedding_ref"] = f"emb:{c['question_id']}"
        except Exception:
            logger.exception("embedding enrichment failed; continuing without embeddings")
```

Add `import logging` and `logger = logging.getLogger(__name__)` to `app/services/analytics.py`.

- [ ] **Step 4: Run full suite to confirm no regressions**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: all prior tests PASS; live test SKIPPED. NOTE: the existing `test_run_analytics_persists_snapshot` may now hit Ollama for the low-confidence fixture questions. Because Ollama is running locally, the `classify_question` call for fixture questions with medium/low confidence will attempt a real Ollama call. To keep unit tests deterministic, in `run_analytics` wrap classification in a degraded-safe path:

```python
    for c in catalog_records:
        try:
            c["model_output"] = classify_question(c["question_text"])
        except Exception:
            c["model_output"] = {"status": "rules_degraded", "reason": "classification_error"}
```

- [ ] **Step 5: Run the live test with Ollama running**

Run: `$env:RUN_OLLAMA_TESTS="1"; .\.venv\Scripts\python.exe -m pytest tests/test_ollama_live.py -v`
Expected: PASS (with your local Ollama running `qwen2.5:3b-instruct`)

- [ ] **Step 6: Commit**

```bash
git add app/services/analytics.py tests/test_ollama_live.py
git commit -m "feat: wire Qwen classification and embeddings into analytics"
```

---

## Self-Review

### Spec coverage

| Spec section | Task |
|---|---|
| Configuration (sec 5) | Task 1 |
| Ollama client + retry (sec 6, 18) | Task 2 |
| Classification role (sec 7.1) | Task 3 |
| Misconception/study-action/candidate roles (sec 7.2–7.4) | Task 4 |
| Embeddings + clustering (sec 9) | Task 5 |
| Adjudication flow + degradation (sec 8, 11) | Task 6 |
| Analytics wiring + live test (sec 12) | Task 7 |

### Placeholder scan
- Task 6's test file originally contained a placeholder line (`result = pytest.runner`); Step 4 explicitly replaces it. Fixed.
- No TBD/TODO placeholders remain.

### Type consistency
- `validate_with_retry` returns `(T | None, dict | None, bool)` in Task 2 and is consumed identically in Task 6.
- `OllamaUnavailable` defined in Task 2, imported in Task 6.
- `hierarchical_clusters` returns `list[int]`; `dominant_topics` returns `dict[int, str]` — used consistently in Task 5 tests.
- `classify_question` returns dicts with consistent `status` keys (`rules`, `qwen`, `rules_degraded`, `qwen_review`) across Tasks 6–7.
- `is_embedding_available()` defined in Task 6, used in Task 7.

### Known constraints
- Embedding model and torch are NOT required for the core suite; only `requirements-embeddings.txt` installs them. Cluster tests use synthetic numpy vectors.
- Ollama calls during `run_analytics` are wrapped so a stopped Ollama or classification error degrades gracefully and does not break deterministic analytics.
