# Implementation Summary

## Current scope

The repository implements automated answer grading, question-level learning
analytics, existing-topic matching, and descriptive historical trend analysis.

Two names are deliberately distinguished:

- `match_topics()` ranks existing exam topics for supplied answer text using
  content-token overlap.
- `analyze_trends()` summarizes historical learning-score changes with yearly
  averages and a linear slope.

Neither function forecasts future exam topics or generates future questions.
`predict_topics()` remains as a compatibility alias for older callers.

## Shared services

Core calculations are separated from HTTP and filesystem adapters:

- `src/analysis/exam_analysis.py` builds student reports and runs question,
  student, misunderstood-question, cognitive-gap, and weak-topic analytics.
- `src/analysis/grading/service.py` owns v1/v2 grading policies.
- `src/analysis/reporting.py` creates output paths and writes JSON reports.
- `src/api/routers/` validates requests and formats service results.

The command-line scripts in `src/analysis/grading/` call the same services as
the API instead of maintaining separate grading and analysis implementations.

## Concept scoring

Concept keywords are selected independently from the student response:

1. year-specific model answer, when available;
2. model/reference answer embedded in an exam part;
3. question text as an explicit fallback.

Every student report includes `concept_reference_source`, `score`, and
`max_marks` for traceability. The question-text fallback should be replaced
with verified model answers as they become available for additional years.

## API endpoints

- `POST /grade` - grade one answer.
- `POST /grade/batch` - grade multiple answers.
- `POST /grade/with-feedback` - use the v2 feedback policy.
- `POST /analyze/exam` - run the complete analytical pipeline.
- `POST /predict/topic-match` - match text to existing topics.
- `POST /predict/topics` - deprecated compatibility alias.
- `POST /predict/trends` - summarize historical trends.
- `POST /agent-workflows/analyze-exam` - run the typed three-agent workflow.
- `GET /health` and `GET /models` - inspect service/model status.

## Agent workflow foundation

The Phase 1 workflow organizes current deterministic capabilities behind
three typed agents:

- `QuestionKnowledgeAgent` maps each question part to its current topic and
  required Bloom level.
- `AnswerMisconceptionAgent` preserves the existing marks, concept score,
  cognitive score, and learning score while defining the boundary for future
  misconception extraction.
- `CohortPredictionAgent` runs the existing question, student, weak-topic,
  misunderstood-question, cognitive-gap, and historical-trend analytics.

`ExamAnalysisOrchestrator` executes the three agents in that order, reuses one
question mapping across all answers for that part, records an input hash and
model versions, and isolates item-level failures. The expected Phase 1 status
is `partial` because knowledge retrieval, structured misconception extraction,
and validated future-topic forecasting are explicit capability gaps.

Historical trends remain descriptive. `future_topic_probabilities` stays empty
until a temporally evaluated and calibrated forecasting model is configured.
The existing `/grade`, `/analyze/exam`, and `/predict/*` endpoints remain
supported without behavioral changes.
## Verification

Run the automated regression suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the original demonstration scripts:

```powershell
.\.venv\Scripts\python.exe examples\test_predictions_trends.py
.\.venv\Scripts\python.exe examples\test_all_years.py
```

## Research work still required

- semantic topic discovery and clustering;
- temporally validated future-topic and question-structure forecasting;
- an intelligent question generator;
- reliable model answers for all historical years;
- Bloom-model improvement and independent evaluation;
- dashboards, recommendations, security, LMS integration, and persistence.
