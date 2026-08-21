"""Two-speaker diarization and student-role assignment for viva audio.

Default backend is MFCC + k-means (k<=2). Optional pyannote if
VIVA_DIARIZATION_BACKEND=pyannote and a Hugging Face token is set.

Scoring must use only the student track: Whisper still runs on the mixed
wav (so word times stay aligned), then words/acoustics/SER are restricted
to the assigned student speaker.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


WINDOW_S = 0.80
HOP_S = 0.40
MIN_VOICED_WINDOWS = 6
MIN_CLUSTER_FRACTION = 0.08
SINGLE_SPEAKER_INERTIA_RATIO = 0.88
DEFAULT_MAX_SPEAKERS = 4
MOUTH_ASSIGN_MIN_SAMPLES = 2
PINGPONG_MIN_CHANGES = 6
PINGPONG_MAX_MEDIAN_S = 2.5
PINGPONG_CHANGE_RATE = 0.22
MOUTH_SAME_VOICE_RATIO = 1.4


def _backend_name() -> str:
    return str(os.getenv("VIVA_DIARIZATION_BACKEND", "mfcc_kmeans")).strip().lower() or "mfcc_kmeans"


def _max_speakers(requested: Optional[int] = None) -> int:
    if requested is not None:
        return max(1, min(6, int(requested)))
    try:
        return max(2, min(6, int(os.getenv("VIVA_MAX_SPEAKERS", str(DEFAULT_MAX_SPEAKERS)))))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SPEAKERS


def speaker_at(time_s: float, segments: Sequence[Dict[str, Any]]) -> Optional[str]:
    for segment in segments:
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        if start <= time_s < end:
            speaker = segment.get("speaker")
            return str(speaker) if speaker is not None else None
    return None


def collapse_excluded_gaps(
    timed_words: Sequence[Dict[str, Any]],
    exclude_segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Shift word times so excluded (examiner) intervals do not count as pauses."""
    excludes = sorted(
        (
            (float(item["start"]), float(item["end"]))
            for item in exclude_segments
            if item.get("end") is not None and float(item["end"]) > float(item.get("start", 0.0))
        ),
        key=lambda pair: pair[0],
    )

    def subtracted(t: float) -> float:
        removed = 0.0
        for start, end in excludes:
            if end <= t:
                removed += end - start
            elif start < t:
                removed += t - start
            else:
                break
        return max(0.0, t - removed)

    remapped: List[Dict[str, Any]] = []
    for item in timed_words:
        row = dict(item)
        try:
            start = float(item["start"])
            end = float(item.get("end", start))
        except (TypeError, ValueError, KeyError):
            continue
        row["start"] = round(subtracted(start), 4)
        row["end"] = round(max(subtracted(end), row["start"]), 4)
        remapped.append(row)
    return remapped


def assign_words_to_speakers(
    words: Sequence[Dict[str, Any]],
    segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    labeled: List[Dict[str, Any]] = []
    for item in words:
        row = dict(item)
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
        except (TypeError, ValueError):
            continue
        mid = 0.5 * (start + end)
        row["speaker"] = speaker_at(mid, segments)
        labeled.append(row)
    return labeled


def filter_whisper_segments(
    segments: Sequence[Dict[str, Any]],
    diar_segments: Sequence[Dict[str, Any]],
    speaker_id: Optional[str],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for segment in segments:
        row = dict(segment)
        try:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
        except (TypeError, ValueError):
            continue
        mid = 0.5 * (start + end)
        row["speaker"] = speaker_at(mid, diar_segments)
        if row["speaker"] == speaker_id:
            filtered.append(row)
    return filtered


def words_and_text_for_speaker(
    words: Sequence[Dict[str, Any]],
    whisper_segments: Sequence[Dict[str, Any]],
    diar_segments: Sequence[Dict[str, Any]],
    speaker_id: Optional[str],
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    labeled_words = assign_words_to_speakers(words, diar_segments)
    speaker_words = [item for item in labeled_words if item.get("speaker") == speaker_id]
    text = " ".join(str(item.get("word", "")).strip() for item in speaker_words).strip()
    text = " ".join(text.split())
    speaker_segments = filter_whisper_segments(whisper_segments, diar_segments, speaker_id)
    if not text and speaker_segments:
        text = " ".join(str(seg.get("text", "")).strip() for seg in speaker_segments).strip()
        text = " ".join(text.split())
    return text, speaker_words, speaker_segments


def _kmeans(features: np.ndarray, k: int, n_init: int = 6, max_iter: int = 40) -> Tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(42)
    n = int(features.shape[0])
    k = max(1, min(k, n))
    if k == 1:
        labels = np.zeros(n, dtype=int)
        center = features.mean(axis=0, keepdims=True)
        inertia = float(((features - center) ** 2).sum())
        return labels, center, inertia

    best_inertia = float("inf")
    best_labels = np.zeros(n, dtype=int)
    best_centers = features[:k].copy()

    for _ in range(n_init):
        idx = rng.choice(n, size=k, replace=False)
        centers = features[idx].copy()
        labels = np.zeros(n, dtype=int)
        for _ in range(max_iter):
            dists = ((features[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            labels = dists.argmin(axis=1)
            new_centers = centers.copy()
            for cluster in range(k):
                members = features[labels == cluster]
                if members.size:
                    new_centers[cluster] = members.mean(axis=0)
            if np.allclose(new_centers, centers):
                centers = new_centers
                break
            centers = new_centers
        inertia = float(((features - centers[labels]) ** 2).sum())
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()
            best_centers = centers.copy()
    return best_labels, best_centers, best_inertia


def _window_features(y: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    import librosa

    hop_length = max(1, int(HOP_S * sr))
    win_length = max(hop_length, int(WINDOW_S * sr))
    if y.size < win_length:
        return np.zeros((0, 1)), np.zeros(0), np.zeros(0, dtype=bool)

    starts = np.arange(0, y.size - win_length + 1, hop_length)
    feats: List[np.ndarray] = []
    voiced_flags: List[bool] = []

    for start in starts:
        chunk = y[int(start) : int(start) + win_length]
        rms = float(np.sqrt(np.mean(np.square(chunk))) + 1e-12)
        is_voiced = rms >= max(0.008, float(np.percentile(np.abs(y), 40)) * 0.15)
        voiced_flags.append(is_voiced)
        if not is_voiced:
            feats.append(np.zeros(28, dtype=np.float64))
            continue
        mfcc = librosa.feature.mfcc(y=chunk, sr=sr, n_mfcc=13)
        centroid = librosa.feature.spectral_centroid(y=chunk, sr=sr)
        feat = np.concatenate(
            [
                mfcc.mean(axis=1),
                mfcc.std(axis=1),
                np.array([float(np.mean(centroid)), rms], dtype=np.float64),
            ]
        )
        feats.append(feat.astype(np.float64))

    return np.vstack(feats), starts.astype(np.float64) / float(sr), np.asarray(voiced_flags, dtype=bool)


def _smooth_labels(labels: np.ndarray, width: int = 3) -> np.ndarray:
    if labels.size == 0:
        return labels
    width = max(1, int(width))
    if width == 1:
        return labels
    pad = width // 2
    padded = np.pad(labels, (pad, pad), mode="edge")
    out = labels.copy()
    for i in range(labels.size):
        window = padded[i : i + width]
        counts = np.bincount(window, minlength=int(labels.max()) + 1)
        out[i] = int(np.argmax(counts))
    return out


def _segments_from_windows(
    times: np.ndarray,
    labels: np.ndarray,
    voiced: np.ndarray,
    duration: float,
    hop_s: float,
) -> List[Dict[str, Any]]:
    if times.size == 0 or not np.any(voiced):
        return []

    raw: List[Dict[str, Any]] = []
    for time_s, label, is_voiced in zip(times, labels, voiced):
        if not is_voiced:
            continue
        speaker = f"SPEAKER_{int(label):02d}"
        start = float(time_s)
        end = min(duration, float(time_s) + hop_s)
        if raw and raw[-1]["speaker"] == speaker and start <= raw[-1]["end"] + hop_s * 0.6:
            raw[-1]["end"] = end
        else:
            raw.append({"start": round(start, 3), "end": round(end, 3), "speaker": speaker})

    merged: List[Dict[str, Any]] = []
    for item in raw:
        if item["end"] - item["start"] < 0.12:
            continue
        if merged and merged[-1]["speaker"] == item["speaker"] and item["start"] <= merged[-1]["end"] + 0.35:
            merged[-1]["end"] = item["end"]
        else:
            merged.append(item)
    return merged


def _relabel_by_first_appearance(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapping: Dict[str, str] = {}
    next_id = 0
    relabeled: List[Dict[str, Any]] = []
    for item in segments:
        old = str(item["speaker"])
        if old not in mapping:
            mapping[old] = f"SPEAKER_{next_id:02d}"
            next_id += 1
        row = dict(item)
        row["speaker"] = mapping[old]
        relabeled.append(row)
    return relabeled


def _collapse_segments_to_one(
    segments: Sequence[Dict[str, Any]],
    duration: float,
    speaker_id: str = "SPEAKER_00",
) -> List[Dict[str, Any]]:
    if duration and duration > 0:
        end = float(duration)
    elif segments:
        end = max(float(item.get("end") or 0.0) for item in segments)
    else:
        end = 0.0
    if end <= 0:
        return []
    return [{"start": 0.0, "end": round(end, 3), "speaker": speaker_id}]


def looks_like_same_voice_overcluster(
    segments: Sequence[Dict[str, Any]],
    face_cues: Optional[Sequence[Dict[str, Any]]] = None,
) -> bool:
    """True when clustering chopped one talker into interleaved fake speakers.

    Rapid 1–2s A/B/A/B turns are almost never a real viva panel. Two sequential
    blocks (student then lecturer) are kept.
    """
    if not segments:
        return False
    speakers = {str(item.get("speaker")) for item in segments if item.get("speaker")}
    if len(speakers) < 2:
        return False

    durations = [max(0.0, float(item["end"]) - float(item["start"])) for item in segments]
    median = float(np.median(durations)) if durations else 0.0
    changes = sum(
        1
        for i in range(1, len(segments))
        if str(segments[i].get("speaker")) != str(segments[i - 1].get("speaker"))
    )
    span = max(float(segments[-1].get("end") or 0.0) - float(segments[0].get("start") or 0.0), 1e-6)
    pingpong = (changes >= PINGPONG_MIN_CHANGES and median < PINGPONG_MAX_MEDIAN_S) or (
        changes / span >= PINGPONG_CHANGE_RATE and median < 3.0 and changes >= 5
    )
    if pingpong:
        return True

    cues = list(face_cues or [])
    if not cues:
        return False
    mouth_means: Dict[str, List[float]] = {sid: [] for sid in speakers}
    for cue in cues:
        try:
            time_s = float(cue.get("time"))
            mouth = cue.get("mouth_open")
            if mouth is None:
                continue
            mouth_val = float(mouth)
        except (TypeError, ValueError):
            continue
        sid = speaker_at(time_s, segments)
        if sid in mouth_means:
            mouth_means[sid].append(mouth_val)
    scored = {
        sid: sum(vals) / len(vals)
        for sid, vals in mouth_means.items()
        if len(vals) >= MOUTH_ASSIGN_MIN_SAMPLES
    }
    if len(scored) < 2:
        return False
    values = list(scored.values())
    return max(values) / max(min(values), 1e-6) < MOUTH_SAME_VOICE_RATIO


def _min_center_distance(centers: np.ndarray) -> float:
    if centers.shape[0] < 2:
        return 0.0
    best = float("inf")
    for i in range(centers.shape[0]):
        for j in range(i + 1, centers.shape[0]):
            dist = float(np.linalg.norm(centers[i] - centers[j]))
            if dist < best:
                best = dist
    return best if best != float("inf") else 0.0


def _select_speaker_labels(normalized: np.ndarray, max_speakers: int) -> Tuple[np.ndarray, int, Optional[str]]:
    n = int(normalized.shape[0])
    total_ss = float(((normalized - normalized.mean(axis=0)) ** 2).sum())
    if total_ss < 8.0 or n < MIN_VOICED_WINDOWS:
        return np.zeros(n, dtype=int), 1, "clusters_not_separated"

    chosen_k = 1
    chosen_labels = np.zeros(n, dtype=int)
    prev_inertia = total_ss
    upper = min(max(1, max_speakers), n // 3 if n >= 6 else 2, 6)
    upper = max(2, upper) if n >= MIN_VOICED_WINDOWS else 1

    for k in range(2, upper + 1):
        labels, centers, inertia = _kmeans(normalized, k=k)
        counts = np.bincount(labels, minlength=k)
        min_frac = float(counts.min()) / float(max(counts.sum(), 1))
        center_dist = _min_center_distance(centers)
        inertia_ratio = float(inertia) / max(total_ss, 1e-9)
        improved = (prev_inertia - float(inertia)) / max(prev_inertia, 1e-9)
        valid = (
            center_dist >= 1.5
            and inertia_ratio <= SINGLE_SPEAKER_INERTIA_RATIO
            and min_frac >= MIN_CLUSTER_FRACTION
            and (k == 2 or improved >= 0.12)
        )
        if not valid:
            break
        chosen_k = k
        chosen_labels = labels
        prev_inertia = float(inertia)

    if chosen_k <= 1:
        return np.zeros(n, dtype=int), 1, "clusters_not_separated"
    return chosen_labels, chosen_k, None


def diarize_waveform(y: np.ndarray, sr: int, max_speakers: int = DEFAULT_MAX_SPEAKERS) -> Dict[str, Any]:
    duration = float(y.size) / float(sr) if sr else 0.0
    features, times, voiced = _window_features(y, sr)
    voiced_features = features[voiced] if features.size else features

    if voiced_features.shape[0] < MIN_VOICED_WINDOWS:
        segments = [{"start": 0.0, "end": round(duration, 3), "speaker": "SPEAKER_00"}] if duration > 0 else []
        return {
            "status": "single_speaker",
            "backend": "mfcc_kmeans",
            "speaker_count": 1 if segments else 0,
            "segments": segments,
            "duration_seconds": round(duration, 3),
            "reason": "too_few_voiced_windows",
        }

    mean = voiced_features.mean(axis=0)
    std = voiced_features.std(axis=0)
    std = np.where(std < 1e-6, 1.0, std)
    normalized = (voiced_features - mean) / std

    labels_k, speaker_count, reason = _select_speaker_labels(normalized, _max_speakers(max_speakers))
    window_labels = np.zeros(times.shape[0], dtype=int)
    if speaker_count >= 2:
        window_labels[voiced] = _smooth_labels(labels_k, width=3)
        status = "success"
    else:
        status = "single_speaker"
        reason = reason or "clusters_not_separated"

    segments = _segments_from_windows(times, window_labels, voiced, duration, HOP_S)
    segments = _relabel_by_first_appearance(segments)
    if looks_like_same_voice_overcluster(segments):
        segments = _collapse_segments_to_one(segments, duration)
        speaker_count = 1
        status = "single_speaker"
        reason = "collapsed_overcluster"
    if not segments and duration > 0:
        segments = [{"start": 0.0, "end": round(duration, 3), "speaker": "SPEAKER_00"}]
        speaker_count = 1
        status = "single_speaker"

    unique = sorted({item["speaker"] for item in segments})
    return {
        "status": status,
        "backend": "mfcc_kmeans",
        "speaker_count": len(unique) or speaker_count,
        "segments": segments,
        "duration_seconds": round(duration, 3),
        "reason": reason,
    }


def _diarize_pyannote(wav_path: str, max_speakers: int = DEFAULT_MAX_SPEAKERS) -> Dict[str, Any]:
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    from pyannote.audio import Pipeline  # type: ignore

    pipeline = Pipeline.from_pretrained(
        os.getenv("VIVA_PYANNOTE_PIPELINE", "pyannote/speaker-diarization-3.1"),
        token=token,
    )
    annotation = pipeline(wav_path, min_speakers=1, max_speakers=max_speakers)
    segments: List[Dict[str, Any]] = []
    duration = 0.0
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        start = float(turn.start)
        end = float(turn.end)
        duration = max(duration, end)
        segments.append({"start": round(start, 3), "end": round(end, 3), "speaker": str(speaker)})
    segments = sorted(segments, key=lambda item: item["start"])
    segments = _relabel_by_first_appearance(segments)
    unique = sorted({item["speaker"] for item in segments})
    return {
        "status": "success" if len(unique) >= 2 else "single_speaker",
        "backend": "pyannote",
        "speaker_count": len(unique),
        "segments": segments,
        "duration_seconds": round(duration, 3),
        "reason": None if unique else "pyannote_empty",
    }


def diarize_wav(wav_path: str, max_speakers: Optional[int] = None) -> Dict[str, Any]:
    import librosa

    backend = _backend_name()
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    duration = float(y.size) / float(sr) if sr else 0.0
    max_speakers = _max_speakers(max_speakers)

    if backend in {"off", "none", "disabled"}:
        return {
            "status": "skipped",
            "backend": "off",
            "speaker_count": 1,
            "segments": [{"start": 0.0, "end": round(duration, 3), "speaker": "SPEAKER_00"}] if duration else [],
            "duration_seconds": round(duration, 3),
            "reason": "disabled",
            "_waveform": (y, sr),
        }

    if backend in {"pyannote", "auto"}:
        try:
            result = _diarize_pyannote(wav_path, max_speakers=max_speakers)
            result["_waveform"] = (y, sr)
            if backend == "pyannote" or result.get("speaker_count", 0) >= 1:
                if result.get("segments"):
                    return result
        except Exception as exc:
            if backend == "pyannote":
                result = diarize_waveform(y, sr, max_speakers=max_speakers)
                result["backend"] = "mfcc_kmeans"
                result["reason"] = f"pyannote_failed:{exc}"
                result["_waveform"] = (y, sr)
                return result

    result = diarize_waveform(y, sr, max_speakers=max_speakers)
    result["_waveform"] = (y, sr)
    return result


def _speaker_stats(
    y: np.ndarray,
    sr: int,
    segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    ids = []
    for item in segments:
        sid = str(item.get("speaker"))
        if sid not in ids:
            ids.append(sid)

    stats: List[Dict[str, Any]] = []
    for sid in ids:
        mask = np.zeros(y.size, dtype=bool)
        speaking = 0.0
        for item in segments:
            if str(item.get("speaker")) != sid:
                continue
            start = int(max(0, float(item["start"]) * sr))
            end = int(min(y.size, float(item["end"]) * sr))
            if end > start:
                mask[start:end] = True
                speaking += (end - start) / float(sr)
        samples = y[mask]
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
        stats.append(
            {
                "id": sid,
                "speaking_seconds": round(speaking, 3),
                "speaking_ratio": round(speaking / max(float(y.size) / float(sr), 1e-6), 4),
                "rms_mean": round(rms, 6),
            }
        )
    return stats


def assign_student_speaker(
    speakers: Sequence[Dict[str, Any]],
    segments: Sequence[Dict[str, Any]],
    face_times: Optional[Iterable[float]] = None,
    face_cues: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[str, str]:
    """On-camera face is the student. Loudness is never used.

    The student voice is the diarized speaker whose talk turns line up with
    the on-camera mouth opening. Every other cluster is panel/examiner.
    """
    if not speakers:
        return "SPEAKER_00", "default"

    override = str(os.getenv("VIVA_STUDENT_SPEAKER", "")).strip()
    ids = {str(item["id"]) for item in speakers}
    if override and override in ids:
        return override, "manual"

    if len(speakers) == 1:
        return str(speakers[0]["id"]), "single_speaker"

    cues = list(face_cues or [])
    mouth_means: Dict[str, List[float]] = {str(item["id"]): [] for item in speakers}
    for cue in cues:
        try:
            time_s = float(cue.get("time"))
            mouth = cue.get("mouth_open")
            if mouth is None:
                continue
            mouth_val = float(mouth)
        except (TypeError, ValueError):
            continue
        sid = speaker_at(time_s, segments)
        if sid in mouth_means:
            mouth_means[sid].append(mouth_val)

    scored = {
        sid: (sum(vals) / len(vals), len(vals))
        for sid, vals in mouth_means.items()
        if len(vals) >= MOUTH_ASSIGN_MIN_SAMPLES
    }
    if scored:
        winner = max(scored.items(), key=lambda pair: pair[1][0])[0]
        return winner, "on_camera_mouth"

    talking_hits: Dict[str, int] = {str(item["id"]): 0 for item in speakers}
    for cue in cues:
        if not cue.get("talking"):
            continue
        try:
            time_s = float(cue.get("time"))
        except (TypeError, ValueError):
            continue
        sid = speaker_at(time_s, segments)
        if sid in talking_hits:
            talking_hits[sid] += 1
    if max(talking_hits.values() or [0]) >= MOUTH_ASSIGN_MIN_SAMPLES:
        winner = max(talking_hits.items(), key=lambda pair: pair[1])[0]
        return winner, "on_camera_mouth"

    # Camera-on-student but no usable mouth track: do not use loudness.
    winner = max(speakers, key=lambda item: float(item.get("speaking_seconds") or 0.0))
    return str(winner["id"]), "longest_speech"


def write_speaker_track(
    y: np.ndarray,
    sr: int,
    segments: Sequence[Dict[str, Any]],
    speaker_id: str,
    out_path: str,
) -> float:
    import soundfile as sf

    pieces: List[np.ndarray] = []
    for item in segments:
        if str(item.get("speaker")) != speaker_id:
            continue
        start = int(max(0, float(item["start"]) * sr))
        end = int(min(y.size, float(item["end"]) * sr))
        if end > start:
            pieces.append(y[start:end])
    if pieces:
        track = np.concatenate(pieces)
    else:
        track = np.zeros(int(0.2 * sr), dtype=np.float32)
    sf.write(out_path, track.astype(np.float32), sr)
    return float(track.size) / float(sr)


def diarize_and_select_student(
    wav_path: str,
    face_times: Optional[Iterable[float]] = None,
    face_cues: Optional[Sequence[Dict[str, Any]]] = None,
    student_track_path: Optional[str] = None,
) -> Dict[str, Any]:
    raw = diarize_wav(wav_path)
    y, sr = raw.pop("_waveform")
    segments = list(raw.get("segments") or [])
    duration = float(raw.get("duration_seconds") or (y.size / float(sr) if sr else 0.0))
    if looks_like_same_voice_overcluster(segments, face_cues=face_cues):
        segments = _collapse_segments_to_one(segments, duration)
        raw["segments"] = segments
        raw["speaker_count"] = 1
        raw["status"] = "single_speaker"
        raw["reason"] = "collapsed_overcluster"
    speakers = _speaker_stats(y, sr, segments)
    student_id, method = assign_student_speaker(
        speakers,
        segments,
        face_times=face_times,
        face_cues=face_cues,
    )
    if raw.get("reason") == "collapsed_overcluster":
        method = "single_on_camera"
        student_id = "SPEAKER_00"

    examiner_ids = [item["id"] for item in speakers if item["id"] != student_id]
    exclude_segments = [
        item for item in (raw.get("segments") or []) if str(item.get("speaker")) != student_id
    ]

    track_duration = None
    if student_track_path:
        track_duration = write_speaker_track(
            y, sr, raw.get("segments") or [], student_id, student_track_path
        )

    student_stats = next((item for item in speakers if item["id"] == student_id), None)
    for item in speakers:
        item["role"] = "student" if item["id"] == student_id else "panel"
    payload = {
        "status": raw.get("status") or "failed",
        "backend": raw.get("backend"),
        "speaker_count": int(raw.get("speaker_count") or len(speakers)),
        "student_speaker": student_id,
        "examiner_speakers": examiner_ids,
        "assignment_method": method,
        "speakers": speakers,
        "segments": raw.get("segments") or [],
        "recording_duration_seconds": raw.get("duration_seconds"),
        "student_speaking_seconds": student_stats["speaking_seconds"] if student_stats else 0.0,
        "student_speaking_ratio": student_stats["speaking_ratio"] if student_stats else 0.0,
        "student_track_duration_seconds": round(track_duration, 3) if track_duration is not None else None,
        "reason": raw.get("reason"),
        "scored_track": "student",
        "exclude_segments": exclude_segments,
    }
    return payload
