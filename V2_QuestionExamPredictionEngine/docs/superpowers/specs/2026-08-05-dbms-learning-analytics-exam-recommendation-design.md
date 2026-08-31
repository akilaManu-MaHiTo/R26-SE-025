# DBMS Predictive Learning Analytics and Intelligent Question Generator

**Date:** 2026-08-05  
**Status:** Approved design, pending written-spec review  
**System:** Multi-agent LMS research platform  
**Component:** Predictive Learning Analytics and Intelligent Question Generator

## 1. Purpose

This component converts graded DBMS examinations and historical examination papers into explainable learning analytics for lecturers and students. It also helps lecturers plan the next examination by recommending concepts and cognitive levels that deserve assessment, then generating candidate questions for lecturer approval.

The component is an **evidence-based exam recommendation system**. It is not described as a system that can accurately predict the exact questions in a future examination.

## 2. Scope

### 2.1 Subject scope

The initial research implementation supports one subject: Database Management Systems. Its controlled topic taxonomy is:

1. Introduction to DBMS and Conceptual Database Design
2. Logical Database Design
3. Schema Refinement
4. SQL
5. Database Programming
6. Java Database Connectivity (JDBC)
7. Database Utilities
8. Database Security

The cognitive taxonomy uses all six revised Bloom levels:

1. Remember
2. Understand
3. Apply
4. Analyze
5. Evaluate
6. Create

### 2.2 Users

- **Lecturer:** sees anonymized cohort analytics, topic and Bloom-level strengths and weaknesses, historical coverage, recommendation evidence, and generated question candidates.
- **Student:** sees only their last-exam results, personal topic and Bloom-level performance, missed criteria, evidence-based explanations, and recommended study actions.

### 2.3 Inputs

- Five historical DBMS examination papers. Each question part contains its text and maximum marks. These papers do not have historical student answers.
- `courses`, `rubricCollection`, and graded `submissions` MongoDB collections produced by other LMS components.
- Lecturer-defined course settings, including pass threshold and optional topic-importance and examination-blueprint targets.

### 2.4 Non-goals

- Training a new foundation model.
- Fine-tuning Qwen using the five historical papers.
- Automatically publishing an examination without lecturer approval.
- Diagnosing permanent student ability from one examination or one question.
- Using LDA as the production topic classifier.
- Hosting the live LMS backend in Google Colab.

## 3. Constraints and design principles

- Five historical papers are sufficient for descriptive recurrence and coverage analysis but insufficient for reliable probabilistic future-question prediction.
- Historical paper analysis and student weakness analysis are separate evidence streams. Only graded submissions support claims about student weaknesses.
- Numeric conclusions come from deterministic and reproducible calculations. An LLM may enrich, classify, explain, and generate, but it does not calculate marks or mastery.
- Every recommendation must expose its supporting metrics and sample size.
- Low-sample findings are labelled as insufficient or possible evidence rather than definite weaknesses.
- Lecturer validation remains the authority for topic labels, Bloom labels, and generated questions.

## 4. Chosen architecture

The approved solution is a hybrid, explainable pipeline with four layers:

1. **Evidence analytics:** score normalization, descriptive statistics, mastery calculation, historical coverage, grade distribution, and recommendation scoring.
2. **Semantic analysis:** pretrained sentence embeddings, cosine similarity, and hierarchical clustering for question similarity and recurring sub-concepts.
3. **Qwen semantic assistant:** structured topic and Bloom classification, misconception summaries, study actions, and candidate-question generation.
4. **Human validation:** lecturers confirm ambiguous classifications and approve or edit generated questions.

The live system uses a Python FastAPI backend, an asynchronous PyMongo data layer, and a React/TypeScript frontend built with Vite. Google Colab is an on-demand batch worker for GPU-dependent experiments and Qwen inference. It is not a permanent API host.

## 5. End-to-end data flow

1. Ingest historical papers, rubrics, and graded submissions.
2. Split every examination question into its smallest independently scored part.
3. Transform each graded submission into one record per student-question part.
4. Classify each question part by topic, Bloom level, question type, and key concepts.
5. Calculate student and cohort metrics from awarded and maximum marks.
6. Compute embeddings and semantic clusters for historical and current questions.
7. Identify cohort weaknesses, strengths, topic coverage gaps, and Bloom gaps.
8. Produce immutable, versioned analytics snapshots.
9. Show role-filtered dashboards through FastAPI response schemas.
10. Produce ranked examination recommendations with evidence.
11. Generate multiple candidate questions from an approved recommendation.
12. Require lecturer approval or revision before a candidate enters an exam blueprint.

## 6. Canonical analysis record

The central analytical unit is a student attempt at one question part:

```json
{
  "attempt_id": "stable-derived-id",
  "analysis_run_id": "run-id",
  "course_code": "SE2032",
  "exam_id": "exam-id",
  "student_key": "pseudonymous-student-key",
  "question_id": "question-id",
  "question_number": "02",
  "part": "b",
  "question_text": "Find the primary key using attribute closure.",
  "topic_assignments": [
    { "topic": "Schema Refinement", "weight": 0.8 },
    { "topic": "Logical Database Design", "weight": 0.2 }
  ],
  "bloom_level": "Analyze",
  "question_type": "problem_solving",
  "key_concepts": ["functional dependency", "attribute closure"],
  "awarded_marks": 1.0,
  "max_marks": 2.0,
  "normalized_score": 0.5,
  "criteria_breakdown": [],
  "answer_text": "...",
  "feedback": "...",
  "classification_status": "model_suggested",
  "classification_confidence": "medium",
  "algorithm_version": "analytics-v1"
}
```

Topic weights for a question must sum to 1.0. The lecturer can replace model-suggested topic and Bloom labels; the validated value and the original suggestion are both retained for audit and evaluation.

## 7. Question classification and topic analysis

### 7.1 Production classification

The eight known DBMS topics form a controlled, multi-label taxonomy. Production classification therefore uses:

1. Verb and concept rules as a transparent baseline.
2. Similarity between question embeddings and curated topic descriptions/examples.
3. Qwen structured classification as an adjudicating semantic signal.
4. Lecturer validation for disagreement or low-confidence cases.

The Qwen classification response must conform to a schema containing:

- Primary topic
- Secondary topic weights
- One Bloom level
- Question type
- Key concepts
- Evidence-based rationale
- Review flag

The model's self-reported confidence is not treated as a calibrated probability.

### 7.2 Semantic clustering

- Primary embedding model: `sentence-transformers/all-mpnet-base-v2`
- Faster baseline: `sentence-transformers/all-MiniLM-L6-v2`
- Similarity measure: cosine similarity
- Production clustering: agglomerative hierarchical clustering
- Use: discover recurring concepts and sub-concepts within or across the controlled topics

BERTopic is an optional experimental comparison with parameters adapted to the small number of question parts. LDA and TF-IDF/K-Means are classical baselines, not production decision-makers.

## 8. Qwen model strategy

- Default Colab model: `Qwen/Qwen2.5-7B-Instruct` using 4-bit quantization.
- Low-memory fallback: Qwen2.5-3B-Instruct using 4-bit quantization.
- Optional experiment: Qwen2.5-14B-Instruct when adequate GPU memory is available.
- Fine-tuning is excluded because the available historical dataset is too small.
- Classification uses deterministic or near-deterministic decoding.
- Candidate generation may use controlled sampling to create diverse alternatives.

Qwen has four bounded roles:

1. Topic, Bloom, question-type, and key-concept extraction.
2. Evidence-grounded misconception summaries.
3. Evidence-grounded student study actions.
4. Candidate-question, model-answer, and rubric generation from an approved blueprint entry.

All outputs are validated against Pydantic schemas. Qwen never awards marks, changes grades, or creates a final examination without lecturer approval.

## 9. Mastery and performance calculations

For each attempt:

```text
normalized_score = awarded_marks / maximum_marks
```

For student or cohort entity `e`, topic `t`, and optionally Bloom level `b`:

```text
mastery(e,t,b) =
  sum(normalized_score_i × maximum_marks_i × topic_weight_i)
  / sum(maximum_marks_i × topic_weight_i)
```

Only attempts matching the requested entity, topic, and optional Bloom level enter the sum. Mark weighting prevents a one-mark item from contributing as much as a ten-mark item.

Each topic/Bloom cell reports:

- Mean normalized score
- Median normalized score
- Pass and failure rates
- Number of students and attempts
- Standard deviation
- Grade distribution where applicable
- Missed-criterion rate where criterion evidence exists
- Evidence status based on sample size

The initial pass threshold is 50% and is configurable per course or examination. The system does not silently change this threshold.

### 9.1 Evidence statuses

- `confirmed_weakness`: below threshold with sufficient student and attempt counts.
- `possible_weakness`: below threshold with insufficient supporting attempts.
- `strength`: consistently above threshold with sufficient evidence.
- `coverage_gap`: the syllabus topic or configured blueprint target is absent or materially underrepresented.
- `bloom_gap`: a required configured Bloom level is absent or underrepresented.
- `insufficient_evidence`: no reliable conclusion is permitted.

Minimum student and attempt counts are configuration values recorded with each analysis run. The initial research defaults are 10 students and 2 independently scored question parts. Sensitivity analysis must report how findings change under alternative thresholds.

## 10. Rubric-criterion evidence

Criterion-level feedback requires the grading component to populate structured evidence:

```json
{
  "criterion": "Correctly applies attribute closure",
  "awarded_marks": 0.5,
  "max_marks": 2.0,
  "met": false,
  "evidence": "The answer stopped before the closure stabilized."
}
```

When `criteria_breakdown` is empty, the component may infer likely misconceptions from the answer, rubric, justification, and feedback. Such results must be labelled `inferred_low_confidence` and must not be presented as confirmed rubric failures.

## 11. Examination recommendation logic

The recommender ranks a topic/Bloom/question-type combination, not a copied historical question. Each scoring component is normalized to `[0,1]`:

- **Weakness:** combines low cohort mastery, failure rate, and available missed-criterion evidence.
- **Coverage gap:** difference between observed historical/current coverage and the lecturer's configured topic target.
- **Bloom gap:** difference between observed assessment distribution and the lecturer's configured cognitive-level target.
- **Topic importance:** lecturer-defined curriculum importance.

The initial configurable priority score is:

```text
priority =
  0.40 × weakness
  + 0.25 × coverage_gap
  + 0.20 × bloom_gap
  + 0.15 × topic_importance
```

If the lecturer has not configured topic or Bloom targets, the system shows historical distributions and weakness evidence but does not label differences from an unknown target as gaps. Equal topic importance is used only as a visible initial UI default, not as an academic claim.

Every recommendation displays:

- Recommended topic and Bloom level
- Suggested question type and mark range
- Priority score and component breakdown
- Cohort mastery, failure rate, and sample sizes
- Historical frequency and most recent assessment year
- Recurring missed criteria or misconceptions
- Evidence status and limitations

The lecturer selects a recommendation before Qwen generates candidates. Each candidate includes the question, target topic, Bloom rationale, marks, model answer, rubric criteria, and similarity to historical questions. Candidates over a configurable semantic-similarity threshold are rejected or flagged for revision.

## 12. Lecturer experience

The lecturer dashboard includes:

- Overall cohort mean, median, pass rate, and grade distribution
- Topic-by-Bloom performance heatmap
- Strongest and weakest topics with evidence and sample size
- Frequently failed rubric criteria
- Historical topic, Bloom, question-type, and mark coverage
- Possible coverage and Bloom gaps relative to configured targets
- Ranked next-exam recommendations with factor explanations
- Candidate generation, editing, approval, and rejection workflow
- Drill-down from aggregate evidence to anonymized question-level patterns

The dashboard never exposes student identities in aggregate analytics unless an authorized lecturer deliberately opens an institution-approved individual view.

## 13. Student experience

The student dashboard includes:

- Last-exam score and grade
- Question-by-question score and feedback
- Personal topic-by-Bloom performance
- Strong, developing, and weak concepts from that examination
- Missed rubric criteria when structured evidence exists
- Low-confidence inferred issues clearly distinguished from confirmed evidence
- Specific study actions and practice-question suggestions

Student-facing language is bounded to the observed examination. It uses wording such as, "Evidence from this exam suggests difficulty with attribute closure," and never asserts a permanent lack of ability.

Students cannot see cohort identities, lecturer-only recommendations, candidate future-exam questions, model prompts, or another student's results.

## 14. MongoDB persistence

Existing source collections remain unchanged:

- `courses`
- `rubricCollection`
- `submissions`
- `historical_exams`

New derived collections are:

### 14.1 `question_catalog`

One document per question part with normalized text, source exam, marks, topic/Bloom/type labels, key concepts, embedding reference, model output, validation state, and lecturer correction.

### 14.2 `question_attempts`

One document per student-question part with scores, topic weights, Bloom level, criterion evidence, pseudonymous student key, and source references.

### 14.3 `analytics_snapshots`

Immutable published results for a run, including student/cohort metrics, topic-Bloom matrices, evidence statuses, grade distributions, and source record counts.

### 14.4 `exam_recommendations`

Ranked recommendation evidence, candidate questions, generated rubrics, similarity checks, and lecturer decisions.

### 14.5 `analysis_runs`

Run status, input filters, data counts, algorithm/model/embedding versions, quantization, prompt versions, thresholds, timestamps, checkpoints, errors, and publication state.

Unique compound indexes prevent duplicate attempts and duplicate snapshots for the same exam and algorithm version. Source collections are treated as read-only by this component.

## 15. FastAPI service boundary

The backend is separated into API routers, Pydantic schemas, repositories, analytics services, ML adapters, authorization dependencies, and audit services.

Core endpoints:

```http
POST /api/v1/analysis/runs
GET  /api/v1/analysis/runs/{run_id}

GET  /api/v1/lecturer/courses/{course_code}/exams/{exam_id}/dashboard
GET  /api/v1/lecturer/courses/{course_code}/exams/{exam_id}/recommendations
POST /api/v1/lecturer/recommendations/{recommendation_id}/generate-questions
PATCH /api/v1/lecturer/recommendations/{recommendation_id}/decision

GET  /api/v1/students/me/exams/{exam_id}/dashboard
GET  /api/v1/students/me/exams/{exam_id}/questions/{question_id}
```

FastAPI response models provide strict role-specific output filtering. The authenticated identity and role come from the LMS token. Student routes derive the student identifier from the token and never accept an arbitrary browser-supplied student ID.

Long-running ML work uses an `analysis_runs` job record. FastAPI creates or reads job state; it does not keep a request open while Qwen runs.

## 16. React/Vite frontend boundary

- React with TypeScript consumes the versioned FastAPI API.
- The API URL comes from `VITE_API_URL`; the development server uses a proxy where appropriate.
- Lecturer and student routes use distinct authorization guards and response types.
- Dashboards show loading, stale-snapshot, insufficient-evidence, partial-analysis, and failed-analysis states explicitly.
- The client displays metric definitions and sample sizes through accessible details/tooltips.
- The browser never calculates authoritative mastery or recommendation scores.

## 17. Colab batch worker

The Colab notebook is a reproducible research worker that:

1. Loads configuration and credentials from protected environment secrets.
2. Claims a pending `analysis_runs` job or accepts an explicit run ID.
3. Reads only required, pseudonymized records from MongoDB.
4. Loads the embedding model and quantized Qwen model.
5. Processes records in bounded batches.
6. Validates all structured model output.
7. Stores checkpoints after each batch.
8. Writes derived results using idempotent upserts.
9. Records model and prompt metadata.
10. Marks the job ready for deterministic analytics and publication.

The notebook contains no committed database credentials. Raw student identifiers are excluded from Colab input because they are not needed for semantic analysis.

## 18. Reliability and failure handling

- Invalid Qwen JSON is validated, retried once with the schema error, then placed in lecturer review.
- Rule, embedding, and Qwen label disagreement produces a review flag.
- Colab checkpoints allow processing to resume after disconnection.
- Database writes are idempotent and guarded by unique indexes.
- Deterministic analytics remain available when the LLM or embedding service fails.
- Missing criterion data degrades to question-level analysis with an explicit confidence label.
- Too few attempts produce `insufficient_evidence`, not a weakness or strength.
- A failed run never replaces the last published analytics snapshot.
- Candidate-question similarity checks reduce accidental copying from historical papers.
- Model, prompt, threshold, and lecturer edits are retained in the audit trail.

## 19. Privacy, security, and fairness

- Use institutional authentication and role-based authorization.
- Use pseudonymous student keys in derived analytics and Colab processing.
- Keep MongoDB credentials and model-access tokens in environment secret stores.
- Encrypt transport connections and restrict MongoDB network access.
- Apply an institution-approved retention policy to raw answers and derived explanations.
- Obtain the required research ethics and student-data approvals before experimentation.
- Never send unnecessary identity fields to third-party or hosted services.
- Report subgroup fairness only when relevant demographic data may be used ethically and lawfully; otherwise do not infer protected characteristics.
- Require lecturer oversight for all high-impact exam-planning decisions.

## 20. Testing and research evaluation

### 20.1 Deterministic unit testing

Use manually calculated fixtures to verify score normalization, topic weighting, mastery matrices, pass/failure rates, evidence statuses, coverage calculations, priority ranking, and missing-data behavior.

### 20.2 API and persistence testing

Test Pydantic validation, role-filtered response models, MongoDB transformations, unique indexes, idempotent reruns, job recovery, and student/lecturer authorization boundaries.

### 20.3 Topic, Bloom, and type classification

Two DBMS lecturers independently label a representative set of question parts. Resolve disagreements to create a consensus evaluation set. Report:

- Accuracy
- Macro precision, recall, and F1
- Per-class confusion matrices
- Cohen's kappa between lecturers
- Lecturer-correction rate for each model configuration

### 20.4 Semantic clustering

Compare hierarchical sentence-embedding clusters with TF-IDF/K-Means, LDA, and optional BERTopic using:

- Silhouette score
- Cluster purity against lecturer topic labels
- Lecturer ratings of discovered sub-concept coherence
- Stability under resampling and parameter changes

### 20.5 Weakness detection

Lecturers independently identify weaknesses from anonymized marked scripts. Compare the system with lecturer consensus using precision, recall, macro-F1, and qualitative disagreement analysis.

### 20.6 Question generation

At least two lecturers rate blinded question candidates on five-point scales for:

- Technical correctness
- Curriculum relevance
- Bloom alignment
- Difficulty suitability
- Mark-allocation suitability
- Clarity
- Novelty
- Absence of answer leakage

Report agreement and score distributions, not only averages.

### 20.7 Baselines and ablation

Compare:

1. Keyword/rule classification
2. TF-IDF with LDA or K-Means
3. Sentence embeddings with hierarchical clustering
4. Qwen without deterministic evidence analytics
5. Embeddings and statistics without Qwen
6. Complete hybrid system

This demonstrates whether each component adds measurable value.

## 21. Acceptance criteria

The research prototype is successful when:

- It imports the five historical papers and graded submission schema without manual record rewriting.
- Every scored question part is traceable from source submission to published metric.
- Lecturer and student dashboards show the approved role-specific outputs.
- Topic/Bloom classifications are evaluated against dual-lecturer labels.
- Weakness claims display supporting attempts, scores, and evidence status.
- Generated questions include a rationale, model answer, rubric, similarity check, and lecturer decision.
- Rerunning an unchanged analysis is idempotent and reproducible.
- Student routes cannot retrieve another student's results.
- The prototype continues to provide deterministic analytics if Qwen is unavailable.
- The final report states the five-paper limitation and uses recommendation rather than exact-prediction claims.

## 22. Implementation sequence

1. Define Pydantic and MongoDB schemas and create deterministic fixture data.
2. Build ingestion and canonical question-attempt transformation.
3. Implement and test mastery and cohort analytics.
4. Build topic/Bloom rules and lecturer-labelled evaluation set.
5. Add embeddings and hierarchical clustering.
6. Add Qwen structured classification through the Colab worker.
7. Implement recommendation scoring and evidence explanations.
8. Build lecturer and student FastAPI endpoints.
9. Build the approved React dashboards.
10. Add candidate-question generation and lecturer workflow.
11. Run baseline, ablation, reliability, privacy, and research evaluations.

