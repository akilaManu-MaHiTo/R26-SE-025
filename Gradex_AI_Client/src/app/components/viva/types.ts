// Shared types + view-model mapping for the Viva Assessment workspace.
// Mirrors the response of POST /api/viva-analyze (Gradex_AI_Server) — see
// Gradex_AI_Server/CLAUDE.md for the authoritative shape. Do not fabricate
// fields that aren't actually returned by the backend.

export interface TimelineItem {
  time: number;
  emotion: string;
  emotion_confidence: number;
  engagement_label?: string;
  engagement_confidence?: number;
  engagement_model_score?: number;
  valid: boolean;
}

export interface PitchProfile {
  level?: string;
  mean_hz?: number;
  min_hz?: number;
  max_hz?: number;
  std_hz?: number;
}

export interface AudioEmotion {
  predicted_emotion?: string;
  valence?: string;
  confidence?: number;
  source?: string;
  probabilities?: Record<string, number>;
}

export interface AcousticFeatures {
  duration_seconds?: number;
  tempo_bpm?: number;
  rms_mean?: number;
  pitch_mean_hz?: number;
  pitch_min_hz?: number;
  pitch_max_hz?: number;
  pitch_std_hz?: number;
  jitter_local?: number | null;
  shimmer_local?: number | null;
  hnr_mean_db?: number | null;
  voice_quality_measured?: boolean;
}

export interface TranscriptFeatures {
  hedge_count?: number;
  hedge_phrases?: Array<{ phrase: string; time?: number | null }>;
  filler_count?: number;
  filler_words?: Array<{ word: string; time?: number | null }>;
  word_count?: number;
  speech_rate_wpm?: number | null;
  speech_rate_band?: string | null;
  pause_count?: number;
  long_pause_count?: number;
  long_pauses?: Array<{ start: number; end: number }>;
  sentence_completion_ratio?: number | null;
  pause_detection_granularity?: string;
  sentence_completion_is_heuristic?: boolean;
}

export interface LlmCriterionScore {
  score: number;
  justification: string;
}

export interface LlmEvaluation {
  source?: string;
  status?: string;
  model?: string | null;
  error?: string;
  communication_clarity?: LlmCriterionScore;
  confidence?: LlmCriterionScore;
  engagement?: LlmCriterionScore;
  formula_fallback?: Record<string, LlmCriterionScore>;
}

export interface AudioAnalysis {
  status?: string;
  transcript?: string;
  transcript_excerpt?: string;
  transcript_word_count?: number;
  segment_count?: number;
  audio_grade?: number | null;
  pitch_profile?: PitchProfile;
  audio_emotion?: AudioEmotion;
  acoustic_features?: AcousticFeatures;
  transcript_features?: TranscriptFeatures;
  grade_breakdown?: Record<string, number | string | string[] | boolean | null>;
  degraded_reasons?: string[];
  error?: string;
}

export interface CoverageInfo {
  frames_sampled?: number;
  frames_with_face?: number;
  face_coverage_ratio?: number;
  min_face_frames?: number;
  min_face_coverage_ratio?: number;
  blinks_measured?: boolean;
  blinks_per_minute?: number | null;
  scores_emitted?: boolean;
}

export interface EngagementSummary {
  very_low_ratio?: number;
  low_ratio?: number;
  high_ratio?: number;
  very_high_ratio?: number;
  average_engagement_score?: number;
}

export interface EmotionSummary {
  positive_ratio: number;
  neutral_ratio: number;
  negative_ratio: number;
}

export interface AnalysisResult {
  timeline: TimelineItem[];
  confidence_score: number | null;
  engagement_score: number | null;
  engagement_summary?: EngagementSummary;
  summary: EmotionSummary;
  coverage?: CoverageInfo;
  video_status?: string;
  audio_analysis?: AudioAnalysis;
  llm_evaluation?: LlmEvaluation;
  mark_id?: string;
}

/* ─── Evaluator rubric (local, evaluator-entered — not returned by the API) ─── */

export interface RubricCriterion {
  id: string;
  name: string;
  description: string;
  score: number;
  max: number;
}

export const DEFAULT_RUBRIC: RubricCriterion[] = [
  { id: "communication", name: "Communication Skills", description: "Clarity, articulation and pacing of the response", score: 0, max: 10 },
  { id: "presentation", name: "Presentation Quality", description: "Confidence, composure and delivery on camera", score: 0, max: 10 },
  { id: "engagement", name: "Engagement", description: "Attentiveness and sustained engagement during the viva", score: 0, max: 10 },
  { id: "technical", name: "Technical Knowledge", description: "Depth and accuracy of the subject-matter content — examiner only", score: 0, max: 10 },
];

export const GRADE_BANDS: Array<{ grade: string; minPercent: number }> = [
  { grade: "A+", minPercent: 90 },
  { grade: "A", minPercent: 80 },
  { grade: "B+", minPercent: 70 },
  { grade: "B", minPercent: 60 },
  { grade: "C+", minPercent: 50 },
  { grade: "C", minPercent: 40 },
  { grade: "F", minPercent: 0 },
];

export function suggestGrade(totalScore: number, maxScore: number): string {
  if (maxScore <= 0) return "—";
  const percent = (totalScore / maxScore) * 100;
  const band = GRADE_BANDS.find((b) => percent >= b.minPercent);
  return band?.grade ?? "F";
}

/* ─── Formatting helpers ─── */

export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

const POSITIVE_EMOTIONS = ["happy", "surprise"];
const NEGATIVE_EMOTIONS = ["sad", "angry", "anger", "fear", "disgust", "contempt"];

export function emotionValence(emotion: string): "positive" | "negative" | "neutral" {
  const e = emotion.toLowerCase();
  if (POSITIVE_EMOTIONS.includes(e)) return "positive";
  if (NEGATIVE_EMOTIONS.includes(e)) return "negative";
  return "neutral";
}

export function engagementLabelRank(label?: string): number {
  switch (label) {
    case "very_high": return 3;
    case "high": return 2;
    case "low": return 1;
    case "very_low": return 0;
    default: return -1;
  }
}

export function engagementLabelText(label?: string): string {
  switch (label) {
    case "very_high": return "Very High";
    case "high": return "High";
    case "low": return "Low";
    case "very_low": return "Very Low";
    default: return "Unknown";
  }
}

export interface KeyMoment {
  time: number;
  timeLabel: string;
  title: string;
  detail: string;
  tone: "positive" | "negative" | "neutral";
}

/** Derives a short, scannable list of noteworthy moments from the raw per-second timeline. */
export function buildKeyMoments(timeline: TimelineItem[]): KeyMoment[] {
  const valid = timeline.filter((item) => item.valid);
  if (valid.length === 0) return [];

  const moments: KeyMoment[] = [];

  let peakIndex = 0;
  let peakConfidence = 0;
  valid.forEach((item, i) => {
    if (item.emotion_confidence > peakConfidence) {
      peakConfidence = item.emotion_confidence;
      peakIndex = i;
    }
  });

  if (peakConfidence > 0.5) {
    const peak = valid[peakIndex];
    moments.push({
      time: peak.time,
      timeLabel: formatTime(peak.time),
      title: `Strong ${peak.emotion} detected`,
      detail: `${(peakConfidence * 100).toFixed(0)}% confidence — the most pronounced emotional response in the recording`,
      tone: emotionValence(peak.emotion),
    });
  }

  for (let i = 1; i < valid.length; i++) {
    if (valid[i].emotion !== valid[i - 1].emotion) {
      moments.push({
        time: valid[i].time,
        timeLabel: formatTime(valid[i].time),
        title: "Emotional shift",
        detail: `${valid[i - 1].emotion} → ${valid[i].emotion}`,
        tone: emotionValence(valid[i].emotion),
      });
      if (moments.length >= 6) break;
    }
  }

  return moments.sort((a, b) => a.time - b.time).slice(0, 6);
}

/** Plain-language AI interpretation built only from fields actually present in the response. */
export function buildAIInterpretation(result: AnalysisResult): string[] {
  const notes: string[] = [];
  const { summary, engagement_summary, audio_analysis, video_status, coverage } = result;

  if (video_status === "insufficient_face_coverage") {
    const ratio = coverage?.face_coverage_ratio;
    notes.push(
      `Facial scores were withheld because face coverage was too low` +
        (ratio != null ? ` (${Math.round(ratio * 100)}% of sampled frames).` : "."),
    );
  }

  if (summary) {
    if (summary.positive_ratio >= 0.5) {
      notes.push(`Emotional tone was predominantly positive (${Math.round(summary.positive_ratio * 100)}% of the recording).`);
    } else if (summary.negative_ratio >= 0.3) {
      notes.push(`Some negative emotional signal was detected (${Math.round(summary.negative_ratio * 100)}% of the recording).`);
    } else {
      notes.push(`Emotional tone was mostly neutral (${Math.round(summary.neutral_ratio * 100)}% of the recording).`);
    }
  }

  if (engagement_summary) {
    const veryHigh = engagement_summary.very_high_ratio ?? 0;
    const high = engagement_summary.high_ratio ?? 0;
    if (veryHigh + high >= 0.6) {
      notes.push(`Engagement was consistently high — ${Math.round((veryHigh + high) * 100)}% of the session showed high or very high engagement.`);
    } else if ((engagement_summary.low_ratio ?? 0) + (engagement_summary.very_low_ratio ?? 0) >= 0.4) {
      notes.push("Engagement dipped for a notable portion of the recording.");
    }
  }

  if (audio_analysis?.pitch_profile?.level) {
    notes.push(`Vocal pitch profile was ${audio_analysis.pitch_profile.level}.`);
  }

  if (audio_analysis?.transcript_word_count != null) {
    notes.push(`Transcript captured ${audio_analysis.transcript_word_count} words across ${audio_analysis.segment_count ?? 0} segment${audio_analysis.segment_count === 1 ? "" : "s"}.`);
  }

  if (audio_analysis?.status === "degraded" && audio_analysis.degraded_reasons?.length) {
    notes.push(
      `Audio grade is approximate due to: ${audio_analysis.degraded_reasons.join(", ").replace(/_/g, " ")}.`,
    );
  }

  const llm = result.llm_evaluation;
  if (llm?.communication_clarity && llm?.confidence && llm?.engagement) {
    const sourceLabel = llm.source === "llm" ? "LLM judge" : "formula fallback judge";
    notes.push(
      `${sourceLabel}: clarity ${llm.communication_clarity.score}/10, confidence ${llm.confidence.score}/10, engagement ${llm.engagement.score}/10.`,
    );
  }

  return notes;
}
