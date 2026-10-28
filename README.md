# Adaptive Exam Analytics Engine

### AI-Assisted Exam Analysis and Adaptive Practice Recommendation

Research repository **R26-SE-025**, focused on the [AdaptiveExamAnalyticsEngine](AdaptiveExamAnalyticsEngine/) module of the GradeX assessment platform. The module connects graded assessment evidence, Bloom's taxonomy, course content, and question generation to support lecturer decisions and student practice. Database Management Systems (DBMS / IT2040) is the primary example domain in this repository.

This is a research prototype. Generated questions, cognitive-level predictions, and recommendations require lecturer review before use in assessment.

## Research focus

The project investigates how assessment evidence can support three connected tasks:

1. Identify student and cohort weaknesses by question, topic, subtopic, and Bloom level.
2. Rank practice and assessment candidates using weakness scores, course coverage, tutorial evidence, historical exam relevance, and cognitive-level gaps.
3. Generate course-grounded question alternatives and marking guidance for lecturer review.

The implementation combines deterministic analytics with model-assisted interpretation and generation. Research assets include datasets, notebooks, evaluation scripts, audit evidence, and a separate fine-tuning scaffold. Their presence does not establish improved learning outcomes or generalization beyond the evaluated data.

## Module capabilities

| Area | Implemented functionality |
| --- | --- |
| Assessment analytics | Question and topic performance, cohort summaries, student learning gaps, and saved analytics snapshots from graded submissions. |
| Bloom classification | A local ModernBERT classifier for Remember, Understand, Apply, Analyze, Evaluate, and Create; confidence thresholds flag predictions for review. |
| Course taxonomy | Course-specific topics and subtopics with taxonomy version history. |
| Adaptive recommendations | Candidate ranking informed by performance evidence, teaching materials, historical coverage, and Bloom distribution. |
| Student practice | Generated practice questions, saved practice records, and access to course study materials. |
| Lecturer Exam Creator | Saved drafts and blueprints, recommendations, generated alternatives, and separate marking-scheme exports. |
| Course retrieval | PDF text extraction and an analytics-owned SQLite index for keyword and semantic retrieval of source material. |
| Grading evidence | Read-only exam-paper reconstruction and integration of saved essay and diagram grades, including pending and review-needed statuses. |

## Processing workflow

```text
Graded submissions + rubrics + course taxonomy
                     |
          Evidence matching and validation
                     |
       Bloom classification + numeric analytics
                     |
       Student gaps and cohort weakness scores
                     |
       Candidate retrieval and recommendation ranking
                     |
       Practice questions / lecturer exam drafts
                     |
                Lecturer review

Course PDFs -> extraction -> course index -> source evidence for generation
```

MongoDB stores assessment data and analytics results. Ollama serves the language model used for interpretation and generation. ModernBERT supplies Bloom predictions; SentenceTransformers supports semantic retrieval and similarity checks. FastAPI routes expose the module to the GradeX web client.

## Repository layout

```text
AdaptiveExamAnalyticsEngine/
  app/
    analytics/          Numeric analytics, weakness and recommendation scores
    api/                Lecturer, student, taxonomy and material endpoints
    classifier/         Local Bloom classifier
    db/                 MongoDB repository layer
    embeddings/         Semantic embedding utilities
    evaluation/         Classification and annotation metrics
    ingestion/          Assessment data ingestion
    llm/                Ollama integration
    schemas/            Request, response and evidence contracts
    services/           Analytics, retrieval, practice and exam creation
    taxonomy/           Course taxonomy support
    sample_data/        Sample assessment fixtures
  datasets/             Research datasets and question-bank assets
  notebooks/            Local/Colab research workflows
  scripts/              Dataset, retrieval, evaluation and audit utilities
  tests/                Unit, API and integration tests
  audit_evidence/       Saved research audit outputs
  docs/                 Research planning and validation notes
  unsloth_training/     Separate Qwen3-8B LoRA fine-tuning scaffold
  models/               Local model artifact location
  storage/              Local retrieval storage
```

The surrounding platform includes [Gradex_AI_Client](Gradex_AI_Client/) (web interface), [Gradex_AI_Server](Gradex_AI_Server/) (integrated API and authentication), [GradingEngine](GradingEngine/), [DiagramEvaluationEngine](DiagramEvaluationEngine/), and [VivaEvaluationEngine](VivaEvaluationEngine/). This README concentrates on the analytics research module. See the [module README](AdaptiveExamAnalyticsEngine/README.md) for additional operational notes and the [viva guide](VivaEvaluationEngine/README.md) for that subsystem.

## Local setup

The commands below use PowerShell from the repository root. You need Python compatible with the module dependencies, MongoDB, Ollama, and separately supplied Bloom model artifacts. Node.js is also needed for the web client.

### 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r AdaptiveExamAnalyticsEngine/requirements.txt
```

The core requirements currently include `requirements-embeddings.txt`, so this also installs embedding dependencies.

### 2. Configure the module

Copy the example only when creating a new configuration; keep an existing `.env` file.

```powershell
Copy-Item AdaptiveExamAnalyticsEngine/.env.example AdaptiveExamAnalyticsEngine/.env
```

Edit `AdaptiveExamAnalyticsEngine/.env` for your environment:

| Setting | Purpose |
| --- | --- |
| `MONGODB_MODE=local` | Select local MongoDB; other values select `MONGODB_URI`. |
| `MONGODB_LOCAL_URI=mongodb://127.0.0.1:27017` | Local connection string. |
| `MONGODB_URI` | Connection string used in non-local mode. |
| `MONGODB_DB=dbms_analytics` | Application database; choose a dedicated research database. |
| `ENV=local` | Run against local Ollama; `colab` selects the remote setup. |
| `OLLAMA_MODEL=qwen2.5:3b-instruct` | Default local generation model. |
| `COLAB_MODEL=qwen3:8b` | Model selected in Colab mode. |
| `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` | Remote Ollama endpoint and authentication in Colab mode. |
| `BLOOM_MODEL_DIR=models/bloom_modernbert` | Bloom checkpoint directory, relative to the analytics module. |
| `BLOOM_MODEL_THRESHOLD=0.6` | Confidence threshold for review flags. |
| `BLOOM_DEVICE=cpu` | Inference device. |
| `EMBEDDING_AVAILABLE=true` | Enable embedding similarity support. |
| `COURSE_RAG_INDEX` | Optional override for the course index path. |

See [the example configuration](AdaptiveExamAnalyticsEngine/.env.example) and [settings implementation](AdaptiveExamAnalyticsEngine/app/config.py) for all settings and defaults. In local mode the Ollama endpoint resolves to `http://localhost:11434`.

### 3. Supply models

Place Bloom artifacts in this structure; model weights are supplied separately from Git:

```text
AdaptiveExamAnalyticsEngine/models/bloom_modernbert/
  bloom.safetensors       # model.safetensors is also accepted
  config.json
  tokenizer/
    ... tokenizer files
```

Start Ollama and make the configured generation model available. The embedding model defaults to `sentence-transformers/all-MiniLM-L6-v2` and may download on first use. Bloom loading is lazy; each backend worker needs its own model memory. Low confidence flags predictions for review without switching to an Ollama or rule-based fallback.

For remote generation, see the [Colab notebook](AdaptiveExamAnalyticsEngine/notebooks/colab_ollama.ipynb) and [backend switching utility](AdaptiveExamAnalyticsEngine/switch_llm.py). Keep API-key protection enabled on remote tunnels.

### 4. Run the analytics API

With MongoDB and Ollama running:

```powershell
$env:AUTH_COOKIE_SECURE = "false"
Set-Location AdaptiveExamAnalyticsEngine
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API documentation is available at [localhost:8000/docs](http://localhost:8000/docs). Routes include `/api/lecturers/*`, `/api/students/*`, `/api/courses/*`, and `/api/lecturers/materials/*`.

The standalone API uses shared GradeX session authentication. From the repository root, provision a lecturer account; the command prompts privately for a password:

```powershell
python -m Gradex_AI_Server.scripts.provision_user lecturer@university.edu --role lecturer
```

Lecturer routes require a lecturer session; students may access only their own data. Exam analysis can provision missing student accounts. The current student default password is `Student@123`; anyone who knows the default and a student's email can access an account that still uses it. Use controlled research accounts and provision individual passwords before exposing real student data.

For the integrated web application, install the [server requirements](Gradex_AI_Server/app/requirements.txt), configure its [environment](Gradex_AI_Server/app/.env.example), and run the main API **instead of** the standalone API on port 8000:

```powershell
python -m uvicorn Gradex_AI_Server.app.main:app --host 127.0.0.1 --port 8000
```

Run `npm install` and `npm run dev` in `Gradex_AI_Client`. Vite proxies `/api` and `/courses` to the main server; leave `VITE_BACKEND_URL` and `VITE_API_BASE_URL` unset for that setup. Use the same hostname for frontend and backend, and configure `CORS_ORIGINS` for other frontend origins. `AUTH_COOKIE_SECURE=false` is for local HTTP; use secure cookies with HTTPS deployments.

## Research workflows

Run these commands from `AdaptiveExamAnalyticsEngine` with the Python environment activated.

### Sample analytics

```powershell
python run_sample.py dbms_analytics_test
```

This upserts sample courses, rubrics, and submissions, then writes student analytics and exam snapshots. Use a disposable database: this is a data-writing workflow and requires the configured models and services.

### Course-material indexing

```powershell
python scripts/index_course_materials.py --course IT2040
```

The importer uses the bundled DBMS corpus by default. Other courses require `--root` pointing to a directory with `lectures/`, `tutorial/`, and `Final exam/` subdirectories. `--keyword-only` skips semantic embeddings. Extraction is text-only; it does not perform OCR or interpret diagrams.

### Exam reconstruction

```powershell
python scripts/reconstruct_exam_paper.py EXAM-2025-S1-Apr
```

This read-only workflow checks available question definitions, rubric references, and grading evidence. Missing or ambiguous records are reported rather than silently resolved. Student-data export requires explicit flags; exported assessment evidence is private.

### Evaluation and fine-tuning

- [Evaluation metrics](AdaptiveExamAnalyticsEngine/app/evaluation/metrics.py) include accuracy, macro F1, confusion matrices, and Cohen's kappa.
- [Holdout evaluation](AdaptiveExamAnalyticsEngine/scripts/evaluate_bloom_holdout.py) validates recorded labels and text overlap before optional frozen-model inference. Supply a separately annotated holdout and additional training/tuning exclusion sources. Automated overlap checks do not prove independent annotation or rule out semantic duplicates.
- [Qwen3-8B fine-tuning guide](AdaptiveExamAnalyticsEngine/unsloth_training/README.md) documents the separate Unsloth/LoRA workflow. Its bundled examples are synthetic smoke-test data, not adjudicated evaluation labels. This scaffold does not replace the runtime ModernBERT classifier.

## Validation evidence and limitations

The saved [20-question generation and Bloom validation report](AdaptiveExamAnalyticsEngine/QUESTION_GENERATION_BLOOM_VALIDATION_20_2026-10-17.md), dated 17 October 2026, records:

| Measure | Recorded result |
| --- | --- |
| Fresh DBMS questions generated and classified | 20 / 20 |
| Agreement between requested/generated Bloom labels and classifier predictions | 15 / 20 (75%) |
| Predictions below the 60% confidence threshold | 4 / 20 |
| Evaluate-targeted questions predicted as Evaluate | 0 / 2 |

These are agreement results for one generation run, **not independent classification accuracy**. Model confidence is not a calibrated probability of correctness. The report also identifies generated-content issues requiring review. Independent lecturer labels, adjudication, leakage checks, and broader evaluation are needed before making accuracy or educational-effectiveness claims.

Individual student analysis uses an in-memory FIFO queue per backend process. Use one worker when shared ordering matters; queued work is not restored after restart. Saved analytics can become stale, and missing or inconsistent grading evidence may prevent a complete result.

## Tests

From `AdaptiveExamAnalyticsEngine`:

```powershell
python -m pytest
```

Tests using the `test_db` fixture require a disposable MongoDB database named `dbms_analytics_test`; the fixture drops that database on teardown. It connects using `MONGODB_URI`, so configure a test connection explicitly. Live model tests are opt-in, and the shared fixture disables Bloom by default; an ordinary test run does not establish live model quality.

## Research materials and responsible reuse

See [research documents](docs/), [module research notes](AdaptiveExamAnalyticsEngine/docs/), and [audit evidence](AdaptiveExamAnalyticsEngine/audit_evidence/) for supporting material. Record dataset versions, source provenance, train/validation/test grouping, model artifacts, configuration, and human-review procedures when reproducing an experiment.

Keep real student identifiers, answers, credentials, and database exports out of public research artifacts. Distinguish synthetic fixtures from real observations, obtain the necessary permissions for assessment and course materials, and report limitations alongside results.
