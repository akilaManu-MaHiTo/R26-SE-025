# AdaptiveExamAnalyticsEngine viva preparation

Prepared from the current repository on 21 October 2026. This is a study guide, not a new evaluation report. Source code establishes implemented behavior; saved experiment reports establish only the results of those particular experiments.

## 1. Your two-minute opening answer

“My contribution is the Adaptive Exam Analytics Engine in Gradex AI. Its purpose is to turn graded assessment results into evidence that students and lecturers can act on. A total mark tells us how well a student performed overall, but it does not explain which topics or cognitive tasks need attention.

“My engine takes question definitions, marking rubrics, course information, and saved grading results. It normalizes that evidence, classifies examination questions into the six revised Bloom levels using a local ModernBERT classifier, and assigns topics using lecturer-approved metadata or course taxonomy rules.

“Python calculates the numerical results: overall performance, performance by question, topic and Bloom level, and class-level statistics. Qwen provides qualitative action text and generates practice or examination question candidates. The numerical calculations remain controlled by the backend.

“For lecturers, the system summarizes cohort weaknesses and ranks suitable assessment questions using weakness, curriculum coverage, tutorial evidence, exam history, and Bloom needs. The Exam Creator also retrieves course material to ground new questions and checks them against the paper blueprint. For students, it provides evidence-linked learning gaps and targeted practice.

“The contribution is the feedback loop from assessment evidence to targeted learning and assessment support. It is a hybrid system combining a task-specific classifier, deterministic analytics, retrieval, and generative AI. Lecturer review remains necessary, and I distinguish prototype consistency tests from independently validated model accuracy.”

Adapt “my contribution” to the work you personally performed. Do not claim teammates’ grading, diagram recognition, or viva scoring models as your own.

## 2. Explain the architecture in order

```text
Course information + question/rubric definitions + saved grading evidence
                                  |
                    Normalize and validate joins
                                  |
           Question text ------> ModernBERT ------> Bloom level
           Approved metadata / taxonomy rules ---> Topic
                                  |
                   Python numerical calculations
                                  |
              Saved student and cohort analytics
                      /                      \
          Student learning support      Lecturer assessment support
          Gaps and action text          Cohort statistics and weak topics
          Targeted practice             Ranked questions and exam blueprint
                      \                      /
                     Qwen generation where needed
                                  ^
                 Retrieved lecture/course evidence
                                  |
                 MiniLM + keyword search + SQLite
```

- MongoDB stores the assessment records and materialized analytics. Materialized means calculated results are saved so the dashboard does not recompute everything on every read.
- FastAPI exposes the analytics, dashboard, taxonomy, and course-material endpoints.
- The shared web client displays student and lecturer views.
- The RAG index is analytics-owned SQLite storage, separate from MongoDB and the grading engine’s indexes.
- The engine consumes grading evidence from the assessment system. It does not establish correctness by asking its Bloom classifier to grade answers.

Useful code: `app/ingestion/student_data.py`, `app/services/student_pipeline.py`, `app/analytics/student_document.py`, `app/services/exam_analytics.py`, `app/services/course_rag.py`, `app/main.py`.

## 3. Memorize the model responsibilities

| Component | Actual responsibility | What to say |
|---|---|---|
| Local ModernBERT checkpoint | Six-class Bloom classification of question text | “A supervised text classifier specialized for cognitive demand.” |
| Qwen through Ollama | Qualitative insights, practice questions, exam candidates | “A generative language model constrained by supplied evidence and schemas.” |
| all-MiniLM-L6-v2 | Text embeddings for semantic retrieval and candidate similarity | “It represents text as vectors so we can compare meaning.” |
| Python analytics and ranking | Percentages, aggregates, evidence-based priorities, weighted scores | “An explicit deterministic algorithm, not a trained prediction model.” |
| Topic metadata and rules | Canonical course-topic assignment | “Approved lecturer topics take precedence; rules use the course taxonomy.” |

The current `.env` selects `ENV=colab`, `COLAB_MODEL=qwen3:8b`, CPU Bloom inference, and enabled MiniLM embeddings. The local LLM override is `qwen2.5:7b-instruct`; the code default differs. Configuration selection does not prove a Colab endpoint is currently online.

### ModernBERT: explain the actual inference

1. The tokenizer converts the question into token IDs and an attention mask.
2. Questions are padded for batching and truncated to the configured maximum of 512 tokens.
3. The bidirectional encoder builds contextual token representations.
4. The checkpoint uses mean pooling and a classification head that outputs six logits.
5. Softmax converts logits into six normalized class scores.
6. Argmax selects the largest score and maps BT1–BT6 to Bloom names.

Softmax: `p(i) = exp(z_i) / sum(exp(z_j))`.

The local config specifies 28 layers, hidden size 1024, 16 attention heads, mean pooling, and six labels. This matches the dimensions of the ModernBERT-large family; the config alone does not prove the exact original checkpoint or training history. The model supports up to 8192 positions, but this application normally uses 512 tokens.

The loader is lazy and cached within each process. It checks checkpoint compatibility, calls `model.eval()`, and uses `torch.inference_mode()`. Multiple server workers each need their own loaded model memory.

**Confidence:** a top score of 0.90 is not proof that the prediction has a 90% chance of being correct. Calibration must be evaluated separately. The configured review threshold is 0.60. Low-confidence analytics can be flagged while retaining the top prediction; this does not trigger a switch to Qwen or keyword Bloom classification. Review handling should not be assumed identical in every route.

**If asked why this model:** “A fixed six-class task benefits from a specialized classifier with structured output and reusable inference. The generative model handles tasks requiring new text. This is my architectural rationale; I would need comparative measurements to claim ModernBERT is more accurate or faster than every alternative.”

### Qwen: explain the generation

Qwen3-8B is a causal language model: it generates output tokens conditioned on the prompt and preceding output. Ollama serves it over HTTP; Ollama is a runtime, not the model. Colab supplies remote compute.

The application supplies authoritative backend evidence and requests structured JSON. Pydantic validates the response; retry and degraded-response paths handle failures. The backend accepts supported action text while retaining control over calculated metrics, gaps, priorities, and practice targets in the student assembly path.

Generation temperature is configured as 0.8; the lower classification-style setting is 0.2. Higher temperature increases sampling variation; it does not establish better educational quality. Thinking is disabled in the Ollama request. The saved 17 October generation experiment used Q4_K_M quantization, which reduces weight storage and memory requirements with possible quality tradeoffs.

Do not say Qwen is fine-tuned just because `unsloth_training/` exists. That directory is a Qwen LoRA training scaffold with synthetic examples. Its existence does not establish that a resulting adapter is deployed. The main student analytics path uses ModernBERT for Bloom, even though a separate LLM classification helper remains in the code.

### MiniLM: explain embeddings and cosine similarity

MiniLM maps text into a 384-dimensional vector. Cosine similarity compares vector directions:

`similarity(a,b) = dot(a,b) / (norm(a) * norm(b))`.

Similar meaning can produce similar vectors even when words differ. This supports finding relevant course passages and detecting questions resembling historical ones. The configured candidate threshold is 0.85. In the shared generation path, exceeding it produces a similarity flag; it does not prove plagiarism or guarantee rejection. The Exam Creator separately filters strong lexical duplicates.

MiniLM does not calculate marks or output Bloom labels in this engine. Its own sequence limit also matters: a character-bounded retrieval chunk can still exceed the embedding model’s token window.

Primary background references: [ModernBERT model card](https://huggingface.co/answerdotai/ModernBERT-large), [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B), [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

## 4. Understand Bloom with one DBMS example per level

| Level | Meaning | Example |
|---|---|---|
| Remember | Retrieve a fact | Define a primary key. |
| Understand | Explain meaning | Explain why foreign keys support referential integrity. |
| Apply | Use a known method | Write an SQL query for the supplied schema. |
| Analyze | Examine parts and relationships | Identify functional dependencies and diagnose anomalies in this relation. |
| Evaluate | Make a justified judgment against criteria | Compare two indexing strategies and recommend one for a stated workload. |
| Create | Produce a coherent new design | Design a database for the supplied hospital requirements. |

These are illustrative teaching examples, not measured classifier outputs. A verb alone does not determine the level. Context, constraints, and the reasoning actually required matter.

**Bloom versus difficulty:** Bloom describes the type of cognitive process; difficulty describes how challenging an item is for learners. They are related in some settings but are not interchangeable.

**Question demand versus student ability:** labeling a question Analyze does not establish that the student has mastered Analyze. The engine combines question classification with marks as evidence about performance on assessed tasks. It does not directly measure the student’s mental process or their complete cognitive ability.

## 5. Calculations you should explain without looking

### Performance

`percentage = awarded marks / available marks * 100`.

For a topic, add awarded marks and available marks across its questions before dividing. Example: 2/5 and 18/20 give 20/25 = 80%, rather than the unweighted mean of 40% and 90%, which would be 65%.

Student performance statuses are Strong at 80% or above, Developing at 60–<80%, Needs Improvement at 40–<60%, and Critical below 40%. Status thresholds are application choices, not universal educational standards. The default pass threshold is a separate setting, 50%.

Do not present an unassessed topic as a demonstrated weakness. A missing or pending grade is different from an awarded zero. Combined essay/diagram results depend on matched grading evidence and verified maxima; incomplete or conflicting evidence needs pending/review handling.

### Weakness

The basic weakness score is `W = 1 - percentage/100`.

Example: 40% performance gives W = 0.60.

Where additional rates are supplied, the shared helper uses:

`W = 0.60 * (1 - percentage/100) + 0.25 * failure_rate + 0.15 * missed_criterion_rate`.

Example: percentage 40, failure rate 0.50, missed-criterion rate 0.40 gives `0.36 + 0.125 + 0.06 = 0.545`. If neither extra rate is supplied, the helper uses the basic score. Do not claim every dashboard path supplies every component.

### Recommendation ranking

`R = 0.35W + 0.20L + 0.15T + 0.15E + 0.15B`.

All inputs are between 0 and 1. The weights sum to 1.

- W: observed topic weakness.
- L: lecture coverage, currently based on topic presence in lecture records.
- T: tutorial evidence: one item gives 0.6, two give 0.8, three or more give 1.0.
- E: exam-history signal that favors topics less represented in recent exams. It is not a prediction of tomorrow’s exam.
- B: measured Bloom weakness where available; otherwise the relative shortfall from a target Bloom distribution.

Example: W=0.6, L=1, T=0.8, E=0.5, B=0.4 gives `R=0.21+0.20+0.12+0.075+0.06=0.665`, classified High. High begins at 0.65; Medium at 0.40.

“These are transparent heuristic weights, not learned weights. Their educational usefulness requires lecturer evaluation and sensitivity analysis.”

The lecturer Exam Creator also has draft-aware reranking using remaining topic and Bloom allocations. Do not claim every ranking screen uses only the five-term score.

### Cohort and item analysis

The engine calculates class mean, median, population standard deviation, pass rate, and grouped performance. The question difficulty index is based on average achievement: a higher value means students found the question easier. Discrimination compares question performance in upper and lower overall-performance groups. The implementation uses approximately 27% groups for n>=10 and half-groups for smaller cohorts.

Small cohorts make these estimates unstable. A low mark can reflect teaching gaps, ambiguity, marking problems, or difficult content; it does not establish a single cause. Evidence thresholds are operational rules, not statistical significance tests.

## 6. Explain RAG and the Exam Creator

RAG means retrieval-augmented generation: relevant source passages are supplied in the generation prompt without retraining model weights.

1. Extract PDF text page by page using PyMuPDF.
2. Split text into word-aligned chunks, approximately 1400 characters with 200-character overlap, keeping pages separate.
3. Store document metadata, text chunks, and optional vectors in SQLite.
4. Retrieve with SQLite FTS5/BM25 keyword ranking and optional MiniLM cosine similarity, scoped to the course and material types.
5. Combine rankings using reciprocal rank fusion: each rank contributes `1/(60+rank)`.
6. Supply bounded evidence, learning outcomes, target topic, Bloom level, marks, and historical questions to Qwen.
7. Validate the returned structure, topic, marks, source IDs, and count. Apply duplicate checks and mark accepted candidates `needs_review`.

The creator checks remaining paper marks and topic allocations. If source material is unavailable, lecturer notes or bank lecture objectives can supply evidence; without lecture evidence, generation is blocked rather than invented.

The RAG importer does not include OCR. Scanned PDFs may require transcription or another OCR stage. Semantic retrieval can fall back to keyword search. Sources reduce unsupported generation but cannot guarantee correctness. A valid source ID proves a reference exists, not that every claim in an answer is supported by it. Generated Bloom labels remain provisional unless independently checked.

## 7. Research evidence: be precise

### What the saved evidence establishes

- The reported source CSV has 8767 rows and 8721 unique normalized question texts.
- It contains 46 duplicate rows and 13 normalized texts with conflicting labels.
- Class counts are BT1=2582, BT2=1801, BT3=1508, BT4=1293, BT5=783, BT6=800. The data is imbalanced.
- The saved provenance audit says the user identified that CSV as the sole training source; actual training split membership was not supplied.
- All 500 questions in `gold_bloom_v2.csv` overlap that source. This does not establish an independent test set or prove which specific rows were used in training.
- Fourteen final-exam holdout candidates were prepared with no exact normalized source overlap, but the saved report identifies them as unlabeled and not independent gold data. Exact deduplication also does not exclude paraphrase leakage.
- The 17 October report generated and classified 20 questions. Requested/generated labels agreed with ModernBERT for 15/20 (75%). Four predictions were below 60% confidence. Both Evaluate-targeted questions were classified Analyze.

**Your safe answer:** “The 75% result measures agreement between requested generation labels and classifier predictions on that 20-item experiment. It is not classification accuracy against independent expert labels. The saved 500-item set overlaps the reported training source, so I cannot use it as proof of unseen-data generalization.”

Different saved pilot files contain other agreement values. Always identify the date, input set, input role, and metric; do not mix question-text predictions with answer-text or combined-input experiments.

### What is needed for a defensible model evaluation

1. Clean duplicate/conflicting labels and document how disagreements are resolved.
2. Obtain independent lecturer labels, ideally from two raters with adjudication.
3. Split by source exam/document or question family before training, preventing related questions crossing splits.
4. Keep an untouched test set. Use validation data for model and threshold selection.
5. Report accuracy, six-class macro-F1, per-class precision/recall, and confusion matrix. Macro-F1 gives each class equal weight, which matters for this imbalance.
6. Compare suitable baselines such as a majority classifier, keyword approach, TF-IDF classifier, or base-model prompting under the same test conditions.
7. Evaluate recommendation usefulness separately: weakness fit, curriculum fit, difficulty fit, clarity, would-use/would-edit ratings, and agreement between raters.
8. Measure latency and resource use on specified hardware. Test whether learning improves through a separate learner study before claiming educational impact.

Precision asks how many predictions of a class were correct; recall asks how many real examples of that class were found. F1 is their harmonic mean. Cohen’s kappa measures agreement adjusted for chance; it does not by itself prove labels are correct.

The exact ModernBERT training optimizer, learning rate, epochs, split seed, and checkpoint-selection procedure were not verified from a training run artifact in this review. Do not substitute the Qwen LoRA scaffold’s settings. Bring your original training notebook/logs and explain only what they establish.

## 8. Likely examiner questions with short answers

**What is adaptive here?** Recommendations and practice targets respond to observed topic/Bloom weaknesses. The model is not retrained after each student submission, and this is not established as item-response-theory computerized adaptive testing.

**What is your research contribution?** An assessment-to-feedback pipeline connecting graded evidence, cognitive-demand classification, explainable prioritization, and course-grounded assessment support. The underlying Transformer architectures are reused. Claim novelty beyond this only where supported by your literature comparison.

**Why not use a total mark?** Two students can have equal totals but different topic and cognitive-task weaknesses; targeted feedback needs the breakdown.

**Why separate classification, calculation and generation?** Each task needs different behavior. Fixed labels use the classifier, reproducible arithmetic uses Python, and open-ended explanations use Qwen. This makes errors easier to trace.

**Why not use only Bloom keywords?** A verb does not describe all the reasoning needed. Contextual classification can use the full question, although comparative gains must be measured.

**What if ModernBERT is missing?** Main Bloom classification fails with an explicit model-availability error. Qwen or rules do not silently replace it in that path.

**What if Qwen is offline?** Deterministic analytics and fallback action structures can remain available in the student pipeline; fresh generation returns a degraded/error result. The exact behavior depends on the endpoint.

**What if topic assignment is ambiguous?** Prefer approved metadata. Otherwise use taxonomy matches; unresolved or tied matches can remain Unclassified for review rather than assigning an arbitrary topic.

**How do you prevent hallucinations?** Restrict prompts to backend evidence, retrieve course sources, validate outputs, reject unsupported targets, retain backend control of numbers, and require review. These reduce risk; they do not eliminate it.

**Does schema validation ensure correctness?** It checks structure and permitted values. An answer can be valid JSON and still be educationally wrong.

**How do you know recommendations work?** Explicit scores explain why an item was ranked. Lecturer usefulness ratings and learner-outcome studies are needed to establish usefulness and impact.

**Why those recommendation weights?** They are interpretable initial design choices emphasizing observed weakness. They need empirical validation; I do not present them as optimal learned values.

**What about other subjects?** Course taxonomy support exists, but DBMS is the demonstrated domain. Other subjects need appropriate metadata, materials, and validation; adding a course code is not proof of generalization.

**Can it scale?** Batching, reusable model instances, classification caching, and saved analytics reduce repeated work. The single-student analysis queue is in memory and per process; shared distributed scheduling would be needed across multiple workers. Scaling claims require measurements.

**How is student data protected?** The current API integrates the shared session authentication and student/lecturer access controls. Remote inference sends prompt evidence to its configured host, so data minimization, endpoint security, and deployment review still matter. Do not claim a complete privacy/security audit.

**What is the main limitation?** Independent educational validation and training reproducibility need stronger evidence. Classification ambiguity, incomplete assessment coverage, generated-content errors, small cohorts, and remote-runtime availability also matter.

**What would you improve first?** Build an independently labeled test set, preserve the exact training recipe and splits, analyze class-specific errors, and evaluate recommendation usefulness with lecturers. Then use evidence to choose further model or ranking changes.

## 9. Demo narrative: approximately five minutes

1. Open a prepared graded exam. Explain which records came from grading and which results your engine produces.
2. Show one student’s overall mark, then the topic breakdown. Explain why the total alone is insufficient.
3. Show a question’s Bloom classification. State that it describes question demand, and explain confidence/review.
4. Point to an evidence-linked gap: question identifier, awarded marks, available marks, and recommended action.
5. Open the lecturer cohort view. Explain a weak topic, sample size, and why low performance is evidence rather than a diagnosis of cause.
6. Show a recommended question and explain the score components.
7. In Exam Creator, show blueprint constraints, retrieved material, and one generated candidate with sources and review status.
8. Finish with one known limitation and the evaluation that would address it.

Before the viva, manually verify the selected exam, MongoDB, local model files, and current Colab endpoint. Have prepared screenshots and saved results as a fallback. Label saved outputs honestly. Do not run disposable-database test fixtures against a demonstration database.

## 10. Revision plan

- 20 minutes: rehearse the opening answer and draw the pipeline from memory.
- 30 minutes: explain ModernBERT, Qwen, MiniLM, softmax, and cosine similarity aloud.
- 20 minutes: calculate the percentage, weakness and recommendation examples without notes.
- 20 minutes: rehearse evaluation limits, leakage, macro-F1, and the difference between agreement and accuracy.
- 20 minutes: practise the demo and failure explanation.
- 20 minutes: answer the examiner questions aloud in 30–60 seconds each.
- Before bed: write one page containing model roles, pipeline, formulas, evidence caveats, and your contribution. Prioritize sleep over memorizing file names.

Use this answer pattern when you get stuck: **purpose -> input -> method -> output -> limitation**.

## 11. Code map for follow-up questions

| Examiner topic | File |
|---|---|
| Actual Bloom inference | `app/classifier/bloom_classifier.py` |
| Model dimensions and labels | `models/bloom_modernbert/config.json` |
| Normalize assessment evidence | `app/ingestion/student_data.py` |
| Classification cache and student pipeline | `app/services/student_pipeline.py` |
| Student metrics and fallback targets | `app/analytics/student_document.py` |
| Cohort metrics and item analysis | `app/analytics/exam_analytics.py` |
| Weakness formula | `app/analytics/weakness.py` |
| Recommendation formula | `app/analytics/recommendation_score.py` |
| Recommendation signal definitions | `app/services/recommendation.py` |
| Prompts and candidate generation | `app/services/llm_service.py` |
| Ollama requests and validation | `app/llm/ollama.py` |
| Embeddings and cosine similarity | `app/embeddings/embedder.py` |
| Hybrid retrieval | `app/services/course_rag.py` |
| Paper constraints and generated-candidate checks | `app/services/exam_creator.py` |
| Accuracy, macro-F1, rater agreement | `app/evaluation/metrics.py` |
| Source-data overlap evidence | `audit_evidence/training_source_comparison.json` |
| Specific 20-question experiment | `QUESTION_GENERATION_BLOOM_VALIDATION_20_2026-10-17.md` |

Scope: reviewed implementation and saved evidence; did not run models, databases, or the demo, verify the original ModernBERT training run, or establish new accuracy results. Existing application changes were left untouched.
