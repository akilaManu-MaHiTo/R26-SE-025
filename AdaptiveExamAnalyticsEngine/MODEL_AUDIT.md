# Model audit and cleanup — 2026-10-15

## Inventory before changes

The working tree was clean. Scope is AdaptiveExamAnalyticsEngine only.

| Component | Traced execution path | Disposition |
| --- | --- | --- |
| ModernBERT | `classifier/rules.py`, `services/llm_service.py`, `services/student_pipeline.py`, and `/api/lecturer/bloom-predict` call `classifier/bloom_classifier.py` | Required runtime model; retain weights, config and tokenizer. |
| Cognitive Bloom joblib | No references to `cognitive_bloom` or `joblib` in repository Python code | Retain: training provenance and research value are unknown; no unsafe deserialization attempted. |
| Ollama | `llm/ollama.py` is shared by semantic analysis, insights, misconceptions, actions and generation | Retain local/Colab switching, schema validation, retries and timeouts. |
| SentenceTransformer | Lazy service singleton in `llm_service.py`, used for candidate similarity checks | Retain optional backend; reuse historical vectors within each request. |
| Hierarchical clustering | Only `tests/test_embeddings_cluster.py` calls `embeddings/cluster.py` | Retain research implementation and tests. |
| Unsloth Qwen3 training | `unsloth_training/train_bloom.py`, validator, notebook and synthetic examples | Retain; separate experiment, not the producer of the deployed ModernBERT checkpoint. |
| Datasets and evaluation | `datasets/bloom_dataset/`, `bloom_test_results.json`, `docs/validation/`, weight-tuning and rater scripts | Retain all versions, including `temp.csv`; filenames alone do not establish redundancy. |
| Archives/sample versions | `archive/`, `scripts/archive/`, sample loaders/migration and v2/v3/v4 fixtures | Retain for research and migration reproducibility. |

## Verified findings

- ModernBERT already uses local-only loading, CPU checkpoint loading, `eval()`, and `torch.inference_mode()`. Application import does not load it. Configuration and project-relative model path resolution already exist; another configuration layer is unnecessary.
- Its singleton initialization is not synchronized, despite inference being dispatched with `asyncio.to_thread` in the student pipeline. Concurrent first requests can each allocate the model.
- `classify_question` and `bloom_predict` each infer once through `classify_by_rules`, then infer the same text again. The student pipeline already avoids this extra inference through direct topic matching.
- Similarity checks re-encode each historical question for every candidate. Request-local reuse avoids stale cross-request caches and keeps single-text encoding and comparison order unchanged.
- The classifier docstring and environment comments incorrectly describe a confidence fallback. Runtime Bloom classification requires ModernBERT; the threshold remains meaningful for low-confidence review in exam analytics.
- Only `models/bloom_modernbert/config.json` is tracked. The subproject's blanket `models` ignore overrides the root exceptions for weights/tokenizers. Local weights are 1,583,368,040 bytes; cognitive joblib is 79,455 bytes. No artifacts will be added to Git automatically.
- Root `docs` ignore also excludes local validation evidence. Existing Python caches, baseline caches and graphify output are already ignored and untracked. No cache deletion is required for Git hygiene.
- Core requirements already include Torch. The embeddings requirements repeat it, although sentence-transformers also requires it. NumPy is imported directly but only supplied transitively.
- `.env.example` contains local placeholders and an empty API key. Real `.env` was not inspected directly or modified; application settings loaded normally during tests.
- Installed Python 3.12 libraries differ from requirements: Transformers 5.16.1 versus pinned 4.55.4 and sentence-transformers 6.0.0 versus pinned 5.6.1. The project `.venv` identifies Python 3.14.4 and an older external checkout path. Do not silently upgrade/downgrade either environment.

## Cleanup plan and scope

1. Add regression tests for single Bloom inference, unchanged rule output, concurrent model initialization, similarity results, request-local reuse and degraded behavior.
2. Allow rules to consume a previously computed Bloom level, updating the service and direct API caller. Preserve mandatory ModernBERT failure behavior; do not add rule/LLM fallback.
3. Serialize model initialization/reset with a standard-library lock; keep inference outside the lock.
4. Reuse historical embeddings per similarity call without changing thresholds, text preprocessing or output schemas.
5. Correct documentation and local ignore rules; make NumPy explicit and remove duplicate Torch declaration. Preserve every artifact and research script.
6. Run focused and broad offline tests, inspect application imports and artifact hashes, then record actual results here.

## Reproducibility limits

The config records ModernBERT, Transformers 4.55.4, Unsloth 2025.8.10, six BT1–BT6 labels, 28 layers and an 8192-position limit. Runtime defaults remain CPU, max length 512 and model version `modernbert-bloom-v1`. The exact source training run, split, seed and original checkpoint download location are not recorded alongside the weights. Do not infer them from the config or retrain to fill the gap. Keep the original artifacts backed up separately, and record a stable download location plus training manifest before treating a fresh clone as reproducible.

## Validation

Initial bounded baseline: 18 passed, one pre-existing failure in `test_llm_base_url_resolves_to_localhost_in_local_env`, one temporary-directory permission error, 44 MongoDB tests deselected. The configuration test supplies a stale endpoint and expects local mode to replace it, but the current property returns the configured endpoint. This cleanup leaves routing policy unchanged. Subsequent runs use a writable workspace `--basetemp`.

The async hang was traced with pytest's faulthandler to Windows asyncio's
`socketpair` setup inside the sandbox, before the test body. Offline tests ran
successfully with host permissions. Database tests remain excluded rather than
connecting to or dropping an existing local database.

The comparable host baseline executed the four original committed Python modules
in memory using `git show HEAD:...`, leaving working files intact. It produced
**240 passed, 7 failed, 1 skipped**, with 44 database tests and the new regression
file deselected. The first post-cleanup broad run produced **246 passed, 7 failed,
1 skipped, 44 deselected**. After adding three final characterization cases,
the final broad offline run produced **249 passed, 7 failed, 1 skipped,
44 deselected in 7.89 seconds**. All seven failures are the same:

| Existing failure | Observed cause |
| --- | --- |
| `test_config_ollama.py::test_llm_base_url_resolves_to_localhost_in_local_env` | Local routing expectation disagrees with the configured-endpoint property. |
| `test_llm_generate.py::test_valid_candidate` | Fixture uses `SQL`, rejected by the canonical topic validator. |
| `test_loader.py::test_load_real_builds_course_from_courses_json` | Rubric/evaluated criteria count mismatch for question 01. |
| `test_sample_data_structure.py::test_submissions_have_v2_shape_and_graded_status` | Fixture expects 5 submissions; current sample contains 9. |
| `test_sample_data_structure.py::test_migrate_sample_v2_is_idempotent` | Archived migration expects a document where the current sample contains a list. |
| `test_student_data_ingestion.py::test_normalize_submission_joins_questions_and_criteria` | Fixture supplies a list where a rubric dictionary is expected. |
| `test_switch_llm.py::test_preserves_lf_line_endings` | Fixture expects 6 lines; switcher writes 7. |

Final focused cleanup/classifier/service/creator/reanalysis/clustering run:
**54 passed in 4.98 seconds**, including endpoint-error and strict-threshold
characterization checks.
`python -m pip check`: no broken installed requirements. The Unsloth dataset
validator accepted all 18 synthetic records (12 train, 6 validation, three per
Bloom level); no training was run.

Real checkpoint smoke test with Hugging Face network access disabled: on CPU,
`Write a SQL SELECT query that joins two tables.` returned **BT3 / Apply**, confidence
**0.845485**. Repeating the prediction produced an identical complete result.
Cold loading plus the first inference took **55.308 seconds**; warm inference took
**0.157 seconds**. These are post-change single-sample timings on the installed
environment, not an accuracy evaluation or a before/after performance comparison.
A 45-second diagnostic stack showed the existing constructor still spending time
randomly initializing weights before loading the checkpoint. Changing that loader
strategy requires compatibility checks against the pinned Transformers release
and is left as a measured follow-up.

Importing `app.main` left Torch, Transformers and sentence-transformers absent
from `sys.modules`. Independent code review found no actionable correctness
defects. It specifically checked first-inference failure propagation, load/reset
locking, similarity tie/negative-score behavior and artifact ignore rules.

Final diff checks found no unrelated edits, weight/dataset changes, real credential
changes or deleted research files. Changed Python files parse, and
`git diff --check` passes. Database integration, live Ollama, GPU execution,
training and full held-out accuracy evaluation were not run.
The original and current application OpenAPI documents have identical SHA-256
`128e1f1a50eb8a6ad0075cda6871de17ba9e9b81e40118c9f59e24aade7ed0f1`.

## Changed files and measured work reduction

- `app/classifier/rules.py`, `app/services/llm_service.py`, `app/api/lecturer.py`:
  reuse the same ModernBERT result for topic/question-type enrichment. The service
  retains its existing first-inference exception behavior. Its old `bloom_error`
  branch could only handle failure of the redundant second inference and was
  removed with that inference. The endpoint now also consistently wraps an
  inference exception as HTTP 500; previously the first, rule-triggered inference
  escaped its explicit handler. Availability still returns HTTP 503.
- `app/classifier/bloom_classifier.py`: standard-library lock around first load
  and reset, leaving inference concurrent. Existing local-only loading, device
  fallback, error caching and inference-mode settings remain.
- `app/services/llm_service.py`: request-local historical-vector dictionary;
  failures still return an empty similarity-check list. No persistent vector cache.
- `tests/test_model_cleanup.py`: regression and error-path coverage with external
  models mocked, including a coordinated concurrent first-load check.
- `.gitignore`: allow existing ModernBERT tokenizer/config metadata to be included
  in a future commit, while weights/cognitive model stay ignored. Add local model
  cache ignore. No artifacts were rewritten, removed, downloaded, or staged.
- `requirements.txt`, `requirements-embeddings.txt`: declare direct NumPy use and
  remove the duplicate Torch declaration. No package installation or version change.
- `README.md`, `.env.example`, `app/config.py`, classifier docstring and this
  audit: correct fallback claims and document setup, memory and provenance limits.

Regression probes measured Bloom inference calls dropping **2 → 1** per service
or direct endpoint request, historical/candidate encode calls dropping **6 → 3**
for two candidates and two identical historical texts, and simultaneous first-load
constructions dropping **2 → 1**. These are measured operation counts, not claimed
wall-clock speedups. No model accuracy or research metrics were changed.

## Artifact fingerprints

SHA-256 of the retained local files, recorded during this audit:

```text
195643c2317081cf6d46fd821c7018be7376a6c54ef5b2cd54626c77c2e22524  models/bloom_modernbert/bloom.safetensors
822e20d52618b556c7237733977692932643833713b874de73cb4fcccd66bf0e  models/bloom_modernbert/config.json
e386620cb5e9f6570fe98481fde86167b4236cdebdcc42308652574122561619  models/bloom_modernbert/tokenizer/special_tokens_map.json
6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30  models/bloom_modernbert/tokenizer/tokenizer.json
e7cb600a544347011cd31309043438c57b4fe30d53bbd18d1ad337a044a02bd3  models/bloom_modernbert/tokenizer/tokenizer_config.json
e8438156f53e8a3d9a4c93110956d834d1413841f7d16788f403f6c4a510144e  models/cognitive_bloom/cognitive_bloom_model.joblib
```

## Follow-up work

Fix the seven baseline failures as a separate fixture/migration/routing task, with
explicit decisions about canonical topics and sample version. Supply a checkpoint
download location and original training manifest. Validate in an environment
matching the pinned Transformers version before comparing research metrics.
Back up ignored datasets and validation evidence independently of Git. Benchmark
real multi-request workloads before introducing persistent embedding caches,
batching changes or a different model-loading strategy. Each server process still
owns its model allocation; the new lock only coordinates threads in one process.
