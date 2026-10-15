# Bloom classification: scientific baseline audit

Audit date: 2026-10-15. This audit reads the current working tree, including the existing staged cleanup. It changes no production classifier, datasets, weights, predictions or annotation files. All computations below use stored files and Python's standard library. They do not evaluate a fresh inference run.

## What actually assigns Bloom labels

| Evidence | Current behavior and implication |
| --- | --- |
| `app/classifier/bloom_classifier.py:28` `BLOOM_ID2LEVEL` | BT1 Remember, BT2 Understand, BT3 Apply, BT4 Analyze, BT5 Evaluate, BT6 Create. This is the runtime six-class contract. |
| `app/classifier/bloom_classifier.py:126` `predict_bloom_batch` | Tokenizes question text, truncates at configured length, takes softmax then argmax. Confidence is the top softmax value, not demonstrated calibration or probability of educational correctness. |
| `app/config.py:30-35` | Default CPU, max input length 512, review threshold 0.6. Config checkpoint capacity is 8192 positions; that does not mean runtime preserves all 8192 tokens. |
| `app/classifier/bloom_classifier.py:88-105` `_load_model_unlocked` | Local-only config/tokenizer and checkpoint loading, eval mode. No network or LLM classification fallback. |
| `app/classifier/rules.py:7,64,191` | `BLOOM_VERBS` is an empty compatibility export; `_bloom_level` requires ModernBERT, while `classify_by_rules` can accept a previously inferred level. Active rules concern topic/question type, not a Bloom verb classifier. |
| `app/services/llm_service.py:28,48` `_try_bloom_model`, `classify_question` | Mandatory ModernBERT top-1; failure raises. The service's name does not make Bloom classification LLM based. |
| `app/api/lecturer.py:155-179` `bloom_predict` | Direct prediction endpoint uses ModernBERT and enriches with rules. Missing model returns 503. |
| `app/services/student_pipeline.py:140,198-224,300-303` `classify_questions` | Reuses cached semantics or batches text through ModernBERT. Cache keys contain text hash, fixed model version and course; they do not fingerprint weights/tokenizer/max-length/taxonomy. Research reruns must bypass stale cached semantics or record the cache conditions. |
| `app/services/exam_analytics.py:74-94` | Confidence <0.6 flags review; the top class still enters analytics. It is not abstention, lecturer adjudication, or a validated 60% correctness boundary. |

`model_version` is the literal `modernbert-bloom-v1` (`bloom_classifier.py:183`). It cannot establish checkpoint identity across replacements. Training metadata next to the checkpoint does not contain a split manifest, seed, source revision or exclusion list. `models/bloom_modernbert/config.json:25-32,65-76` establishes six labels, 28 layers and library metadata, not trained accuracy. `MODEL_AUDIT.md` records a previous real checkpoint smoke test and hashes; that single prediction/timing is not a held-out evaluation. No unsafe joblib deserialization was used: the local cognitive Bloom joblib is not an active classification path traced here.

## Data inventory and leakage evidence

### Training-source clarification (2026-10-15)

The user confirmed that `models/bloom_modernbert` was trained only from `C:\Users\liyan\OneDrive\Documents\SLIIT\Y4\Research\Dataset\bloom model\blooms_taxonomy_dataset.csv`. Independent file comparison verified that this file is **byte-identical** to the repository's source CSV: SHA256 `399916f9715753ab7ccd011e1fb5f8f177dc153cc7f95704257d47a6847b50f0`, 8,767 rows. All 500 gold-v2 texts occur in that confirmed training-source pool. [Comparison evidence](audit_evidence/training_source_comparison.json) records the hashes and overlap.

This establishes training-source provenance by user confirmation plus file identity; it does not establish which rows reached model fitting. If all CSV rows were used for fitting, gold-v2 is entirely training-overlapping and cannot measure unseen accuracy. If a train/validation/test split was applied first, recover its row/text membership and check gold-v2 against the actual fitting and model-selection subsets. Merely originating from the same CSV does not prove a row was used for fitting. No second training source is assumed.

The audit script reads quoted CSV records intact, normalizes only Unicode case plus whitespace, and preserves punctuation. Counts do not include CSV headers.

| Artifact | Measured result | Interpretation |
| --- | --- | --- |
| `datasets/bloom_dataset/bloom/blooms_taxonomy_dataset.csv` | 8,767 records; 8,721 normalized distinct questions; 46 duplicate records; 13 distinct texts with more than one BT label | Contains noisy/ambiguous labels and multiple subject domains. No per-record annotator, adjudication or source-document split fields. |
| `.../gold_bloom_v2.csv` | 500 records, 500 normalized distinct questions; BT1=84, BT2=84, BT3=83, BT4=83, BT5=83, BT6=83 | Balanced sample with `Questions,Category` only. Filename alone does not establish gold provenance. |
| Confirmed training source versus gold v2 | **500/500** gold texts occur in the byte-identical user-confirmed training-source CSV; one normalized text has differing label sets | Not an independently collected test set. If all source rows were fitted, this is training/test leakage. Actual fitting/model-selection split membership remains unavailable, so overlap with fitting rows is not yet independently established. |
| `.../gold_bloom_v1.csv` | **0 bytes** | No usable labels in current local artifact. Retained unchanged. |
| `datasets/bloom_dataset/question_bank.json` | 179 stored question records including inherited `bloom_level` | Candidate bank labels are not paired fresh model predictions plus independent annotations. |
| `combined_100_lec01.csv`, `combined_100_lec02.csv` | Each 100 rows, labels Apply=82, Understand=15, Analyze=3 | Recommendation usefulness ratings; not six-class Bloom annotation evidence. |

Source BT counts are BT1=2,582, BT2=1,801, BT3=1,508, BT4=1,293, BT5=783, BT6=800. The majority-class fraction is 2,582/8,767 = 29.45%; gold-v2's balanced sampling has different priors and cannot establish deployment accuracy. Source-label conflict example: `With suitable diagram explain construction and working of McLeod Gauge.` appears as BT2 at source line 1629 and BT3 at 2013 (capitalization differs); gold-v2 line 223 chooses BT3. These are existing labels, not newly adjudicated corrections.

Usefulness workshop files repeat `bloom_level` alongside lecturer usefulness/clarity/fit scores, not separate lecturer Bloom verdicts. Archived generator `scripts/archive/make_v2_distinct.py:45` copies `cand['bloom_level']` into ratings rows; `combine_100.py:8-9` concatenates workshop versions. Two rater files sharing this copied column do not establish independent Bloom inter-rater agreement. Several usefulness CSVs have non-UTF8 bytes; they were inventoried with explicit decoding replacement for counts only, never relabeled. The reproducible script's source/gold CSV path uses strict UTF8.

Source CSV SHA256: `399916f9715753ab7ccd011e1fb5f8f177dc153cc7f95704257d47a6847b50f0`.
Gold-v2 SHA256: `c8e186ce1cf9c57ac383ef2b4b171fab833d724fcba0ce0ee1db67984341f198`.

## Stored pilot: target agreement, not classification accuracy

`docs/validation/bloom_20/bloom_results.json:5,21-24,49-60` states synthetic pilot, simulated answers, lecturer gold **not collected**, question text with verbal diagram descriptions, and exploratory answer/combined interpretation. There are 20 questions, not 60 independent students/items. `requested_bloom` is the generator's requested target and may disagree with the cognitive demand of its output. It is **not gold**. Therefore the following arithmetic diagnoses generator/classifier disagreement only; no reliable gold is available here for accuracy, precision, recall or F1 claims about the current model.

| Stored input role | Predictions | Agree with requested target | Target-agreement macro F1, all six classes | Confidence <0.6 |
| --- | --- | --- | --- | --- |
| Revised question text | 20 | 9/20 = 0.45 | 0.306349 | 8/20 |
| Simulated answer text only | 20 | 6/20 = 0.30 | 0.172222 | 10/20 |
| Question + simulated answer | 20 | 7/20 = 0.35 | 0.187831 | 7/20 |
| Original question text, before diagram revision | 20 | 11/20 = 0.55 | 0.327561 | 7/20 |

All saved input hashes match the text fields across the three pilot versions; all stored truncation flags are false. Token counts/absence of truncation are recorded historical metadata, not independently retokenized here. The revised current artifact and `before_combined_scores` have identical question predictions. Treat archived versions as dependent revisions, not replicate experiments. Answer-only and combined-target agreement lack even a justified answer-attainment gold definition, so they must not be interpreted as a grade or measured student cognition.

Revised question confusion counts (rows **requested targets**, columns predictions), order Remember, Understand, Apply, Analyze, Evaluate, Create:

```text
1 0 0 1 0 0
0 2 1 0 0 1
0 0 6 2 0 0
0 0 4 0 0 0
0 1 0 0 0 0
0 0 1 0 0 0
```

| Requested target | Support | Predicted count | Target precision | Target recall | Target F1 |
| --- | --- | --- | --- | --- | --- |
| Remember | 2 | 1 | 1.0000 | 0.5000 | 0.6667 |
| Understand | 4 | 3 | 0.6667 | 0.5000 | 0.5714 |
| Apply | 8 | 12 | 0.5000 | 0.7500 | 0.6000 |
| Analyze | 4 | 3 | 0.0000 | 0.0000 | 0.0000 |
| Evaluate | 1 | 0 | 0.0000 | 0.0000 | 0.0000 |
| Create | 1 | 1 | 0.0000 | 0.0000 | 0.0000 |

Zero denominators use zero by convention. One or two items per target cannot support robust subgroup conclusions. Model softmax values alone cannot repair this missing annotation evidence.

Root and subproject `bloom_test_results.json` are byte-identical (SHA256 `c41d759086cd0f07c3b675d05541f76a976ad888810152ef9638086a1dec70e5`): eight illustrative predictions, no gold field, no held-out split. They are one duplicated smoke artifact, not 16 independent evaluated samples. Example stored output `Discuss the history of computing.` is Remember with confidence 0.499778. No correct alternative is invented here.

## Why keyword-only evidence would mislead

There is no active Bloom verb classifier to benchmark. Existing data illustrate why restoring one would need contextual annotation: source line 917 asks `What are the parameters considered for writing a good defect report?` with BT1 despite containing `writing`; source lines 1629/2013 give different labels for the same `explain` question; the pilot's first `Explain...` prompt also requests use of SQL Server syntax and multiple subtasks (`bloom_results.json:75-109`). A word inside a quoted task, embedded subtask or recalled description need not describe the required response. These are ambiguity probes and repository inconsistencies, **not fabricated gold test failures** for ModernBERT.

## Training and research evidence

The three local notebooks contain 8, 8 and 16 cells respectively and **zero saved output cells**: `notebooks/colab_ollama.ipynb`, `colab_ollama_v2.ipynb`, and `unsloth_training/Qwen3_8B_Bloom_Unsloth_Colab.ipynb`. They supply no recorded held-out classification results. The Qwen3 script is a separate generative semantics fine-tuning experiment, not a ModernBERT training recipe: `unsloth_training/train_bloom.py:25,58-67,96-102,134` uses Qwen3, explicit train/validation JSONL and `trainer.train()`.

`unsloth_training/README.md:19,27-35` expressly describes bundled records as examples and requires independent lecturer annotation and group separation. `validate_dataset.py:58-75,154-162` checks IDs, annotations and group leakage. These safeguards support future experiments; they do not retroactively establish provenance for the installed ModernBERT checkpoint. A validation set used each epoch is model-selection data; an untouched source-group-held-out test is still necessary for a final claim. No training, model download, inference or live LLM request was executed by this audit.

## Smallest defensible next validation

1. Recover the checkpoint training manifest: source hash, excluded question/source groups, seed, split membership, tokenizer, library versions and checkpoint hash. If unavailable, disclose that the existing source/gold overlap prevents a defensible independence claim.
2. Collect a separate DBMS question sample by source exam/tutorial and retain context/diagram description. Have two lecturers label cognitive demand independently with documented rubric, record disagreement and adjudication. Treat multi-part mixed-demand questions consistently; report label coverage and class counts.
3. Freeze splits by source group and deduplicate within/across them before any tuning. Use a validation split for threshold/calibration/model decisions; evaluate the untouched test once. Compare the actual current checkpoint, an explicit majority baseline and any proposed alternative on the same inputs.
4. Report accuracy, six-class macro F1, per-class precision/recall/support and confusion, along with sample uncertainty, low-confidence coverage, disagreement cases and domain limits. Separate answer-attainment research from question-demand classification.

## Reproduce the offline audit

From repository root:

```powershell
python AdaptiveExamAnalyticsEngine/scripts/audit_bloom_evidence.py
python -m unittest discover -s AdaptiveExamAnalyticsEngine/tests -p test_bloom_evidence_audit.py
```

Result: **4 diagnostic tests passed**. Tests cover confusion arithmetic and absent classes, invalid pair rejection, whitespace/case normalization and multiline CSV preservation. Script output includes all archived pilot distributions, role-specific matrices and input-hash checks. These tests validate audit arithmetic, not educational labels or model accuracy.

Skipped: fresh model inference, retraining, downloads, PDF/Word rendering, live endpoints, secrets and unsafe model deserialization. Risk: historical predictions plus copied/requested labels cannot validate current checkpoint held-out accuracy, calibrated confidence or student cognitive attainment.
