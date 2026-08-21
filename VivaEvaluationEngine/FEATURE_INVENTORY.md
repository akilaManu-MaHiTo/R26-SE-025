# Viva Evaluation Engine — feature inventory

Source of truth: **current code** (2026-08-20). Project documents describe the intended set; this file records what is actually extracted, stored, scored, or missing.

Legend: **YES** / **NO** / **PARTIAL**. Scoring columns: **FC** = feature-complete family mix; **S1** = official Stage-1 `/100`.

Should-score answers use only: `YES` | `NO` | `ONLY THROUGH DOWNSTREAM MODEL` | `NOT YET — REQUIRES VALIDATION`.

---

## Complete feature matrix

| Feature | Documented | Extracted | Raw stored | Normalized | FC score | Stage-1 | Other model | Diagnostic only | Unavailable | Should score? | Reason | File/function |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Facial emotion | YES | YES | timeline + video_features.emotion | emotion map 0–1 | YES 30% | NO | diagnostic_engagement blend | NO | NO | YES (FC only) | Label map is the documented engagement term | `emotion_detector.py`, `engagement_scoring.aggregate_emotion` |
| Eye gaze (iris vs corners) | YES | YES | per-frame gaze_ok/x/y | ratio | YES 30% as ratio | NO | diagnostic_engagement | PARTIAL | NO | YES (FC ratio) | Ratio is documented; x/y/direction are raw | `gaze_head_analyser.gaze_metrics_from_landmarks` |
| gaze_on_camera_ratio | YES | YES | video_features.gaze | identity | YES | NO | diagnostic_engagement | NO | NO | YES | Direct FC term | `engagement_scoring.aggregate_gaze` |
| gaze x / y / direction | YES | YES | per-frame + means + direction_counts | NO as grade | NO | NO | NO | YES | NO | NO | Position/direction are measurements, not a mark | same |
| Head yaw/pitch/roll **proxy** | YES | YES | per-frame + std | stability 0–1 | YES 20% via stability | NO | diagnostic_engagement | proxies YES | NO | YES (stability only) | **Not Euler degrees** | `gaze_head_analyser`, `normalization.head_pose_stability_score` |
| Head stability | YES | YES | derived | 1/(1+(std/S)^2) | YES 20% | NO | diagnostic_engagement | NO | NO | YES | Documented 20% | same |
| Blink count | YES | YES | blink.blink_count | NO | NO | NO | NO | YES | NO | NO | Count is evidence; rate is scored | `blink_sampler.py` |
| Blink rate | YES | YES | blink_rate_per_minute | 1 − extra×0.01 after 25/min | YES 10% | NO | diagnostic_engagement | NO | NO | YES | Documented 10%; short windows noisy (`measurement_quality`) | `blink_sampler`, `normalization.blink_rate_score` |
| Blink score | YES | derived | components.blink.normalized | YES | YES | NO | diagnostic_engagement | NO | NO | YES | Same as rate map | same |
| CNN frame engagement | YES | YES | engagement_summary.average_engagement_score | 0–1 mean | NO | **YES (only S1 engagement)** | NO | NO | NO | YES (S1) | Official family is CNN mean only | `engagement_detector.py`, `assessment_scoring._engagement_family` |
| CNN-LSTM temporal | YES | interface | temporal_engagement | null | omitted/renorm | NO | NO | YES (status) | **YES** | NOT YET — REQUIRES VALIDATION | No trained checkpoint | `temporal_engagement.py` |
| Face coverage | YES | YES | coverage.* | gate | NO | gate only | NO | YES | NO | NO | Quality gate, not a skill score | `analysis_service.py` |
| Pitch mean/min/max | YES | YES | acoustic_features | NO | NO | NO | heuristic SER fallback | YES | NO | NO | Level is not viva quality | `extract_features._safe_pitch_stats` |
| Pitch std / stability | YES | YES | pitch_std_hz | 1−clamp(std/120) | YES 35% | YES | audio_grade | NO | NO | YES | Same bound S1 and FC | `normalization.pitch_stability_score` |
| Pitch range | derived | YES | pitch_range_hz | NO | NO | NO | NO | YES | NO | NO | Diagnostic span | `viva_analysis._pack_audio_payload` |
| RMS mean/std | YES | YES | rms_mean, rms_std | energy_consistency | **NO** | gate only | audio_grade energy | YES | NO | NOT YET — REQUIRES VALIDATION | Louder ≠ better; CV needs domain validation | `extract_features`, `normalization.energy_consistency_score` |
| Energy consistency | derived | YES | energy_consistency | 1/(1+CV) | stored, **not in mix** | NO | NO | YES | NO | NOT YET — REQUIRES VALIDATION | Formula exists; not in AUDIO_FEATURE_WEIGHTS | `audio_scoring.py` |
| Speech rate | YES | YES | speech_rate_wpm | 120–160 = 1.0 | YES 25% transcript | YES (band) | NO | NO | NO | YES (transcript family only) | Not in audio FC (no double count in FC) | `transcript_features`, `normalization.speech_rate_score` |
| Pause count (>0.5s) | YES | YES | pause_count | NO | NO | NO | NO | YES | NO | NO | Short pauses are diagnostic | `transcript_features._pause_stats` |
| Long pause count (>2s) | YES | YES | long_pause_count | 1−min(1,n/6) | YES 15% | YES | NO | NO | NO | YES | Documented pause term | same + `transcript_scoring` |
| Total / max pause duration | YES | YES | stored | NO | NO | NO | NO | YES | NO | NOT YET — REQUIRES VALIDATION | Duration stats lack a validated map | same |
| MFCC (13) | YES | YES | mfcc_mean[13], mfcc_std[13] | NO score | NO | NO | diarization k-means in memory | YES | NO | ONLY THROUGH DOWNSTREAM MODEL | Feature representation, not a grade | `extract_features.py` (n_mfcc=13, sr=16000, librosa defaults n_fft=2048 hop=512) |
| Jitter | YES | YES | jitter_local | quality map | YES 12.5% via articulation | YES | audio_grade | NO | NO | YES | Voice quality | parselmouth |
| Shimmer | YES | YES | shimmer_local | quality map | YES 12.5% via articulation | YES | audio_grade | NO | NO | YES | Voice quality | parselmouth |
| HNR | YES | YES | hnr_mean_db | clamp(hnr/30) | YES 25% | YES | audio_grade | NO | NO | YES | Clarity | parselmouth |
| SER emotion / probs / conf | YES | YES | audio_emotion | NO | NO | NO | heuristic fallback if worker fails | YES | NO | NOT YET — REQUIRES VALIDATION | IEMOCAP domain mismatch on presentations | `extract_emotion.py`, `ser_worker.py` |
| Word count | YES | YES | word_count | coverage only | NO | gate | NO | YES | NO | NO | Evidence quantity (`transcript_coverage`) | `transcript_features` |
| Hedges | YES | YES | hedge_count | 1−min(1,n/8) | YES 20% | YES | NO | NO | NO | YES | Documented | lists in `transcript_features.py` (`like` not filler) |
| Fillers | YES | YES | filler_count | 1−min(1,n/12) | YES 20% | YES | NO | NO | NO | YES | Documented | same |
| Sentence completion | YES | YES | ratio | clamp | YES 10% | YES | NO | heuristic | NO | YES (heuristic) | Whisper punctuation | `_sentence_completion_ratio` |
| Fragmented sentences | YES | YES | fragmented_sentence_count | 1−min(1,n/6) | YES 10% | **NO** | NO | heuristic | NO | YES (FC only) | Same punctuation heuristic | `_fragmented_sentence_count` |
| Response structure | YES (PRD) | PARTIAL | sentence_count diagnostic | NO | NO | NO | conversation structure if panel | YES | **schema missing** | NOT YET — REQUIRES VALIDATION | No validated monologue schema | `transcript_features._response_structure` |

---

# MISSING / INCOMPLETE FEATURES

- **CNN-LSTM temporal engagement** — interface present; `score = null` until a labeled checkpoint exists (`temporal_engagement.py`). Should score: **NOT YET — REQUIRES VALIDATION**.
- **Response structure (scored)** — diagnostic object only (`no_validated_schema`). Should score: **NOT YET — REQUIRES VALIDATION**.
- **Gaze looking-away validation** — operational numbers; `validated = false` (`no_looking_away_recording`).
- **Head turn/tilt validation** — operational proxies; `validated = false` (`no_turn_tilt_recording`).
- **Trained fusion / technical-accuracy model** — out of scope (future PRD).

# EXTRACTED BUT CURRENTLY NOT SCORED

- RMS mean / std (gate + diagnostic energy_consistency)
- Energy consistency (normalized, **not** in FC mix)
- MFCC mean/std 13 (representation + in-memory diarization)
- SER label / probabilities / confidence / backend / model
- Pitch mean / min / max / range
- Pause count (>0.5s), total pause duration, max pause duration
- Gaze x / y / direction counts
- Raw head proxies (means); **std → stability is scored**
- Blink count (rate is scored)
- Blink `measurement_quality`
- Transcript coverage (insufficient / limited / adequate)
- Response structure sentence_count
- Face coverage (gate, not skill)

# Scoring decisions (diagnostic-only items)

| Feature | Directly affect a score? | Why |
|---|---|---|
| MFCC | ONLY THROUGH DOWNSTREAM MODEL | Cepstra are input to SER/diarization, not a performance grade |
| RMS / energy_consistency | NOT YET — REQUIRES VALIDATION | Formula `1/(1+CV)` is defensible but mixed viva audio includes silence/panel; **not** louder=better. **Not added to FC mix.** |
| SER | NOT YET — REQUIRES VALIDATION | Real videos: angry at >0.97 on normal presentations (IEMOCAP) |
| Pitch mean/min/max/range | NO | Pitch **variability** (std) is the documented quality term |
| Pause duration totals | NOT YET — REQUIRES VALIDATION | FC/S1 already use **long_pause_count (>2s)** |
| Gaze x/y/direction | NO | Ratio is the documented on-camera term |
| Blink count | NO | Rate is the documented term; count is evidence |
| Response structure | NOT YET — REQUIRES VALIDATION | No labeled schema |

---

## Official Stage-1 (locked)

Equal-weight **available** families → `ai_performance` /100:

- Engagement = **frame CNN mean** (`average_engagement_score`)
- Audio = pitch stability + HNR + jitter/shimmer (omit missing)
- Transcript = speech-rate **band** + hedges + fillers + long pauses + sentence completion

Fixture lock (`tests.test_assessment_scoring._sample_result`): **73.76 / B+ / VALID**.

Quality gates, Mode A/B, Q&A/Groq: unchanged.

---

## Feature-complete mixes (not official)

**Engagement** 30/30/20/10/10 emotion/gaze/head/blink/temporal; missing omitted and renormalized.

**Audio** 35/25/25 pitch_stability / HNR / articulation. Speech rate **not** mixed (transcript only). Energy/SER/MFCC **not** mixed.

**Transcript** 25/20/20/15/10/10 speech_rate / hedges / fillers / long pauses / completion / fragmentation. Empty transcript → family unavailable.

---

## Duplicate-contribution graph

```
raw pitch_std  → pitch_stability  → S1 audio family AND FC audio  (parallel layers, not summed into one mark)
raw HNR        → clarity          → S1 audio AND FC audio
raw jitter/shimmer → articulation → S1 audio AND FC audio
raw WPM        → S1 uses band (optimal=1 / else 0.65); FC uses continuous 120–160 map  (same family, two layers)
raw long_pause_count → S1 transcript AND FC transcript
raw hedges/fillers/completion → S1 AND FC transcript
CNN frame mean → S1 engagement ONLY
emotion CNN labels → FC engagement (map) AND diagnostic_engagement 0–100; NOT S1
gaze/head/blink → FC engagement AND diagnostic_engagement; NOT S1
speech rate → FC transcript ONLY (explicitly excluded from FC audio)
RMS → S1 speech gate / audio_grade diagnostic energy; NOT S1 family; NOT FC mix
SER → stored diagnostic only
MFCC → stored; diarization uses a separate in-memory 13-D MFCC
fragmentation → FC transcript only (not S1)
```

No raw variable is added twice **inside** Stage-1. FC and Stage-1 are separate reported scores.

---

## Layer names in API (`feature_complete.layers`)

- `raw_measurements`
- `derived_features`
- `normalized_features`
- `feature_complete_family_scores`
- `current_stage1_score` / `final_score`

---

## Gaze / head validation

Operational on MediaPipe Tasks FaceLandmarker (478 pts, iris 468–477). Threshold `GAZE_ON_CAMERA_THRESHOLD = 0.04`. **validated = false**: no looking-away / turn-tilt fixtures in `videos/`.

## Blink

Sample ~10 fps; closed if `EAR < max(0.15, 0.55×median)`; isolated deep troughs count. `measurement_quality`: low (&lt;15s or &lt;30 eye frames), medium (&lt;30s), adequate.

## SER

HuggingFace `superb/wav2vec2-base-superb-er`, 16 kHz mono, first 12 s. Provenance stored. `domain_note` when model source.

## MFCC

Persisted **mean/std of 13 coefficients only** (not frame matrix). Sample rate 16 kHz. Role: `feature_representation`.
