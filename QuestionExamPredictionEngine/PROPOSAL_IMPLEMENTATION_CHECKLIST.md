# Proposal-to-Codebase Implementation Checklist

Audit date: 2026-07-21  
Proposal: `IT22134776 Research Proposal Report.pdf` (27 pages)  
Module: Predictive Learning Analytics and Intelligent Question Analysis / Generator

## Scope and status rules

This checklist maps the proposal's main objective, six specific objectives, technical methodology, FR1-FR10, non-functional requirements, validation strategy, named platform components, stakeholder capabilities, and commercialization-facing product commitments to the current repository.

- **Done** means an end-to-end implementation exists in the repository and there is direct code/output evidence.
- **Partial** means useful code or scaffolding exists, but part of the proposal requirement, integration, quality target, or user experience is missing.
- **Not started** means no substantive implementation was found after source, dependency, model, data, output, and keyword inspection.
- The PDF does not define automated question generation as FR1-FR10. It discusses it in the literature review, while the requested module name explicitly includes an "Intelligent Question Generator". It is therefore tracked below as an additional required module capability.

## Done

### Data and core analytics

- [x] **Historical exam-question datasets are present for 2021-2025.** JSON files exist under `data/exams/`, with corresponding student-answer files under `data/answers/`.
- [x] **Fixed-file exam and student-performance ingestion exists.** The API loads year-specific exam and answer JSON through `src/api/dependencies.py`.
- [x] **Student performance is aligned to individual exam question parts (Specific Objective 4 / FR5).** `src/api/routers/analytics.py:36` joins exam question text, topic, score, maximum marks, student answer, student ID, and year into per-attempt records.
- [x] **Deep question-level analytics exists.** `src/analytics/question_analysis.py:33` calculates average learning, performance, concept and cognitive scores, attempt counts, weak-attempt counts, and EASY/MEDIUM/HARD difficulty per question part.
- [x] **Frequently misunderstood questions are detected (FR5).** `src/analytics/misunderstood_questions.py:33` aggregates results per student and question, counts students below a threshold, and labels questions `Misunderstood` or `Review`.
- [x] **Weak-topic diagnosis exists (FR6).** `src/analytics/weak_topic_model.py` builds topic-level performance, concept, cognitive, variance, weak-student-share, and level-gap features; `src/analytics/weak_topic_analysis.py` returns ranked weak/review topics.
- [x] **Conceptual/cognitive gap summaries exist (FR6).** `src/analytics/cognitive_gap_analysis.py:62` compares required and observed Bloom levels per question and assigns LOW/MEDIUM/HIGH gaps.
- [x] **Per-student analytics exists.** `src/analytics/student_analysis.py:43` returns average learning score, weak questions, dominant cognitive level, and performance band per student.
- [x] **Historical performance trend analytics exists.** `src/prediction/trend_analysis.py:30` produces per-year averages/counts, least-squares slope, earliest/latest values, and overall change by topic, question, or student.
- [x] **Canonical topic resolution exists.** `src/analytics/topic_utils.py` maps question/part topics to the canonical list in `data/topics.json`.

### Supporting platform components

- [x] **A Python/FastAPI service layer exists.** `src/api/app.py` exposes grading, analytics, prediction, model, health, Swagger, and ReDoc routes.
- [x] **Automated semantic answer grading and feedback exists as an enabling component.** `src/api/routers/grading.py` combines a local SentenceTransformer similarity model with keyword/concept scoring and provides single, batch, and feedback endpoints.
- [x] **Machine-learning training and saved-model infrastructure exists.** Training code and saved artifacts exist for weak-topic detection, Bloom classification, and answer similarity under `src/analysis/training/` and `model/`.
- [x] **Machine-readable analytical reports are generated.** The exam pipeline writes `student_report.json`, `question_summary.json`, `student_summary.json`, `misunderstood_questions.json`, `cognitive_gap_analysis.json`, and `weak_topics.json` (`src/api/routers/analytics.py:111`). Existing outputs cover 2021, 2023, 2024, and 2025.
- [x] **Basic service/model health reporting exists.** `GET /health` reports API status, Python version, and the presence of similarity, weak-topic, and Bloom model artifacts.

## Partial

### Proposal functional requirements

- [ ] **FR1 - Administrators can provide historical exam and performance datasets.** The repository contains JSON datasets and year-based loaders, but no upload endpoint, administrator workflow, schema-validation report, or dataset-management interface.
- [ ] **FR2 - Data cleaning, normalization, and preparation.** Lowercasing, regex tokenization, basic stop-word filtering, word-boundary matching, JSON normalization, and score normalization exist. Missing are a reusable preprocessing pipeline with lemmatization, robust tokenization, configurable stop words, duplicate/missing-value handling, and standardized attempts/timestamps.
- [ ] **FR3 - NLP concept and keyword extraction.** Basic keyword extraction and a SentenceTransformer model exist, but semantic embeddings are used for grading rather than systematic exam-question analysis. Key concepts, semantic relationships, and explainable concept extraction from question text are not fully implemented.
- [ ] **Bloom's Taxonomy / cognitive-skill analysis.** Six Bloom levels, a TF-IDF + logistic-regression classifier, rule-based fallback, question/answer comparison, and gap summaries are integrated. However, the saved model's metadata reports only **16.68% validation accuracy** on 4,855 rows, so this component is not yet research-valid; it also does not use the proposed BERT/RoBERTa approach.
- [ ] **Question-type analysis.** Bloom classification and heuristic difficulty bands exist, but there is no separate classifier/taxonomy for question structures or types.
- [ ] **FR4 - Group similar questions into concept clusters.** Questions can be grouped by pre-existing topic labels and matched with token overlap, but topics are not discovered and questions are not algorithmically clustered by semantic similarity.
- [ ] **FR5/FR6 - Concept-gap reliability.** The self-referential scoring defect has been corrected: reports now use a model/reference answer when available and record `concept_reference_source`. Only 2021 currently has a separate model-answer dataset; other years fall back to question text, so verified reference answers and instructor validation are still required.
- [ ] **FR7 - Predictive analytics.** `/predict/topics` and `/predict/trends` provide useful scaffolding, but the former ranks current exam topics from a student's answer using token overlap and the latter fits descriptive score slopes. Neither forecasts future exam topics or future question structures.
- [ ] **FR8 - Analytical reporting.** JSON report generation is complete, but visual reports, charts, heatmaps, concept-cluster views, and an interactive dashboard are absent.
- [ ] **FR9 - Lecturer insight access.** The generic analytics API returns weaknesses and trends that a lecturer could consume, but there is no lecturer-specific authenticated view, cohort/course filtering, dashboard, export, or teaching-action workflow.
- [ ] **FR10 - Personalized student insights.** Per-student weak-question and cognitive-level summaries exist, but there is no student-facing view, topic-level learning plan, recommended study areas/resources, or progress tracking.
- [ ] **Recurring exam-pattern analysis.** Multi-year score slopes exist, but historical topic recurrence rates, appearance intervals, marks/weight trends, Bloom-distribution trends, and question-structure trends are not calculated.

### Evaluation and non-functional requirements

- [ ] **Predictive-model evaluation and >=80% accuracy target.** Example scripts run across 2021-2025, but they are demonstrations without held-out temporal prediction, ground-truth future-topic labels, Precision/Recall/F1, confidence calibration, or evidence of >=80% forecasting accuracy.
- [ ] **Bloom-model evaluation.** Accuracy and a classification report are stored, but the current 16.68% result requires dataset/label review and model redesign before acceptance.
- [ ] **Weakness-detection validation.** Thresholds, weak-student shares, and a weak score exist, but results have not been compared with instructor judgments or historical failure rates.
- [ ] **Performance and large-dataset support.** Batch grading, cached model loading, and lightweight aggregations provide a base, but no benchmark, load test, asynchronous job processing, pagination, queue, or acceptable-processing-time target is defined or verified.
- [ ] **Reliability and data integrity.** Typed API schemas, error responses, deterministic analytics, local artifacts, and health checks exist. Missing are transactional persistence, retries, audit trails, backup/recovery, integrity constraints, availability monitoring, and reliability tests.
- [ ] **Scalability.** FastAPI and stateless analytical functions are a reasonable starting point, but the current local JSON/file-output design has not been proven for increasing exam and student volumes.
- [ ] **Usability.** Swagger/ReDoc make the API inspectable for developers, but they do not satisfy the simple, intuitive instructor/student interface or clear visualization requirements.
- [ ] **Iterative model improvement.** Training and diagnostic scripts exist, but there is no experiment tracking, model/version registry, feedback ingestion, approval gate, drift monitoring, or retraining pipeline.

## Not started

### Core analytical and generation capabilities

- [ ] **LDA or BERTopic topic discovery.** Build a question-text preprocessing/embedding pipeline, train topic models across historical papers, label the discovered topics, and persist model/version metadata.
- [ ] **K-Means or hierarchical semantic clustering.** Build question embeddings, cluster them, select/tune cluster counts, expose membership and centroids, and link clusters to student results.
- [ ] **Clustering validation.** Add Silhouette Score and Davies-Bouldin Index calculation, baselines, experiment reports, and acceptance thresholds.
- [ ] **Future exam-topic forecasting.** Create a time-aware training table containing topic recurrence, year, marks, frequency, cognitive level, difficulty, and cluster features; train and temporally cross-validate an actual forecast/ranking model.
- [ ] **Future question-structure prediction.** Define a structure schema (for example question type, Bloom level, marks, parts, and wording pattern), extract historical labels, and train/evaluate a model that predicts that structure.
- [ ] **Intelligent question generator.** Build controlled generation from predicted topic, Bloom level, difficulty, marks, and structure; add answer/rubric generation, duplication/leakage checks, factual validation, lecturer review/approval, and generation-quality evaluation.
- [ ] **Personalized study recommendations.** Map diagnosed weak concepts and cognitive gaps to ranked study topics/resources, explanations, practice questions, and measurable follow-up activities.

### Data, architecture, interfaces, and stakeholders

- [ ] **Administrator upload and dataset management.** Add authenticated multipart/CSV/JSON upload APIs and UI, schema mapping, validation/error previews, versioning, deduplication, and import status/history.
- [ ] **PostgreSQL or MongoDB persistence.** Design and implement storage for exams, questions, parts, topics/clusters, student attempts, scores, model predictions, reports, users, roles, and audit records; replace fixed local JSON as the operational store.
- [ ] **University LMS integration.** Add an LMS-facing API/connector and mapping for courses, assessments, questions, attempts, users, and grades, with synchronization and error handling.
- [ ] **Interactive dashboards (Plotly, Dash, Streamlit, or equivalent).** Build exam-pattern, cluster, question-difficulty, misunderstood-question, cohort weakness, Bloom-distribution, and prediction-confidence views.
- [ ] **Student, lecturer, university-administration, system-administration, and researcher experiences.** Build role-specific screens and workflows for personalized learning, cohort teaching insights, curriculum monitoring, dataset/system management, and model experimentation.

### Security, privacy, ethics, and operations

- [ ] **Authentication and role-based access control.** Add identity integration and enforce permissions for students, lecturers, administrators, system administrators, and researchers at API and data-query levels.
- [ ] **Encryption and secrets management.** Add TLS deployment configuration, encryption at rest for sensitive records/backups, managed keys/secrets, and rotation procedures.
- [ ] **Privacy, anonymization, and no-PII controls.** Define permitted fields, pseudonymize student identifiers, remove/directly block PII, apply retention/deletion rules, and test re-identification risk.
- [ ] **Consent and university ethical-compliance workflow.** Record consent/legal basis where required, ethics approval, dataset provenance, allowed research use, access history, and withdrawal/deletion handling.
- [ ] **Restricted raw-data access and secure storage.** Implement least-privilege database/storage policies, environment isolation, audit logs, and access reviews.
- [ ] **Production availability and monitoring.** Add deployment configuration, background jobs for long analysis, centralized logs/metrics/traces, alerts, uptime objectives, incident handling, backups, and disaster recovery.
- [ ] **User evaluation.** Conduct and record instructor/student surveys or studies covering usability, interpretability, usefulness, targeted learning, and curriculum planning; feed outcomes into iteration.

### Commercial/product commitments described in the proposal

- [ ] **SaaS tenancy and institutional subscriptions.** Build tenant isolation, institution/course administration, metering, plans, billing/subscription integration, and entitlement enforcement.
- [ ] **Basic, Professional, and Enterprise tiers.** Define and enforce feature limits for basic analytics, advanced clustering/prediction, API integration, custom analytics, and dedicated support, including user/dataset-size limits.
- [ ] **LMS integration, premium analytics, customization, consulting, licensing, and support operations.** Productize APIs/SDKs, configuration, service-management workflows, licensing terms, documentation, onboarding, and support processes.

## Verification performed

- Extracted all 27 PDF pages and reviewed the objective, methodology, tools/platforms, validation, stakeholder, FR1-FR10, non-functional, and commercialization sections.
- Inspected all tracked source files plus ignored/local `data/`, `output/`, and saved model artifacts.
- `python -m compileall -q src`: **passed**.
- `python -m unittest discover -s tests -v`: **9 regression tests passed** after the cleanup.
- `examples/test_predictions_trends.py`: **passed**.
- `examples/test_all_years.py`: **passed** across the 2021-2025 datasets. Note: these scripts print demonstrations and do not contain research-grade assertions or held-out forecasting evaluation.
- Existing generated analytical outputs were found for 2021, 2023, 2024, and 2025. A complete generated analysis output for 2022 was not found.

