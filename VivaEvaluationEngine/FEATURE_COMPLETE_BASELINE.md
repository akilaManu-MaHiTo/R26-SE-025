# VIVA FEATURE-COMPLETE BASELINE VALIDATION

Date: 2026-08-20  
Command: `python -m unittest discover -s VivaEvaluationEngine/tests -q` from repo root  
Result: **114 tests OK**

| Feature | Status | Kind |
|---|---|---|
| Emotion | PASS | measured (existing CNN) + derived map |
| Eye gaze | PASS | measured (iris) + derived ratio |
| Head pose | PASS | measured landmark proxies + derived stability |
| Blink | PASS | measured EAR; unavailable ≠ 0 |
| CNN-LSTM | UNAVAILABLE | interface only; **untrained**; no checkpoint |
| Pitch | PASS | measured (librosa YIN) |
| RMS | PASS | measured; std/consistency stored, not louder=better |
| Speech rate | PASS | derived from Whisper timestamps; 120–160 WPM |
| Pauses | PASS | derived; >0.5s count, >2s long |
| MFCC | PASS | measured 13-coeff mean/std (not full matrix) |
| Jitter | PASS | measured Parselmouth |
| Shimmer | PASS | measured Parselmouth |
| SER | PASS | existing model path or explicit heuristic/unavailable |
| Hedges | PASS | configured phrase list |
| Fillers | PASS | configured tokens (`like` excluded) |
| Sentence completion | PASS | heuristic (Whisper punctuation) |
| Fragmentation | PASS | derived fragmented_sentence_count |
| Official Stage-1 score | PRESERVED | `assessment.final_score` unchanged |
| Q&A/Groq | PRESERVED | modules not modified for this task |
| Quality gates | PRESERVED | face / speech / audio still required |

CNN-LSTM: **untrained**, **unavailable**, checkpoint **not loaded**.
