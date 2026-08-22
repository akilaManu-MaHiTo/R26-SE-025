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
  mouth_open?: number | null;
  talking?: boolean;
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
  backend?: string | null;
  model?: string | null;
  fallback_reason?: string | null;
  requested_backend?: string;
  probabilities?: Record<string, number>;
  interpretation?: string | null;
  label_margin?: number | null;
  taxonomy?: string;
  domain_note?: string;
  analyzed_duration_seconds?: number | null;
  sample_rate?: number | null;
  input_track?: string | null;
}

export interface AcousticFeatures {
  duration_seconds?: number;
  tempo_bpm?: number;
  rms_mean?: number;
  rms_std?: number;
  pitch_mean_hz?: number;
  pitch_min_hz?: number;
  pitch_max_hz?: number;
  pitch_std_hz?: number;
  pitch_measured?: boolean;
  jitter_local?: number | null;
  shimmer_local?: number | null;
  hnr_mean_db?: number | null;
  voice_quality_measured?: boolean;
  mfcc_mean?: number[];
  mfcc_std?: number[];
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
  long_pauses?: Array<{ start: number; end: number; duration?: number }>;
  total_pause_duration?: number;
  max_pause_duration?: number;
  sentence_completion_ratio?: number | null;
  fragmented_sentence_count?: number;
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

export interface DiarizationSpeaker {
  id?: string;
  role?: string;
  speaking_seconds?: number;
  speaking_ratio?: number;
  rms_mean?: number;
}

export interface DiarizationSegment {
  start?: number;
  end?: number;
  speaker?: string;
}

export interface DiarizationInfo {
  status?: string;
  backend?: string;
  speaker_count?: number;
  student_speaker?: string;
  examiner_speakers?: string[];
  assignment_method?: string;
  speakers?: DiarizationSpeaker[];
  segments?: DiarizationSegment[];
  recording_duration_seconds?: number;
  student_speaking_seconds?: number;
  student_speaking_ratio?: number;
  scored_track?: string;
  reason?: string;
}

export type ConversationSegmentType =
  | "presentation"
  | "panel_interruption"
  | "panel_question"
  | "student_answer"
  | "follow_up_question"
  | "follow_up_answer"
  | "student_question"
  | "instruction"
  | "return_to_presentation"
  | "qa"
  | string;

export interface ConversationTurn {
  start?: number;
  end?: number;
  speaker_id?: string;
  role?: "student" | "panel" | string;
  label?: string;
  text?: string;
  turn_id?: string;
  phase?: ConversationSegmentType;
}

export interface ConversationSegment {
  type?: ConversationSegmentType;
  turn_ids?: string[];
  speaker?: string;
  start?: number | null;
  end?: number | null;
  text?: string;
}

export interface ConversationStructure {
  status?: string;
  source?: "llm" | "heuristic" | string;
  model?: string | null;
  error?: string;
  reason?: string;
  segments?: ConversationSegment[];
  window_count?: number;
}

export interface ConversationInfo {
  turns?: ConversationTurn[];
  pair_candidates?: Array<Record<string, unknown>>;
  turn_count?: number;
  pair_count?: number;
  qa_start?: number | null;
  has_panel?: boolean;
  full_transcript?: string;
  labeled_transcript?: string;
  presentation_turn_count?: number;
  qa_turn_count?: number;
  structure?: ConversationStructure;
}

export type QaRelevance = "high" | "medium" | "low" | "irrelevant";
export type QaAnswerType = "direct" | "partial" | "indirect" | "unclear" | "irrelevant" | "no_answer";

export interface QaPairAnalysis {
  question?: string;
  answer?: string;
  question_start?: number | null;
  question_end?: number | null;
  answer_start?: number | null;
  answer_end?: number | null;
  panel_speaker?: string;
  panel_label?: string;
  status?: string;
  addresses_question?: boolean | null;
  relevance?: QaRelevance | string | null;
  answer_type?: QaAnswerType | string | null;
  explanation?: string | null;
  confidence?: number | null;
  source?: string;
  error?: string;
}

export interface QaAnalysis {
  status?: string;
  model?: string | null;
  pair_count?: number;
  pairs?: QaPairAnalysis[];
  error?: string;
}

export interface AudioAnalysis {
  status?: string;
  transcript?: string;
  transcript_excerpt?: string;
  mixed_transcript?: string;
  full_transcript?: string;
  examiner_transcript?: string;
  transcript_word_count?: number;
  segment_count?: number;
  audio_grade?: number | null;
  pitch_profile?: PitchProfile;
  audio_emotion?: AudioEmotion;
  acoustic_features?: AcousticFeatures;
  transcript_features?: TranscriptFeatures;
  grade_breakdown?: Record<string, number | string | string[] | boolean | null>;
  degraded_reasons?: string[];
  diarization?: DiarizationInfo;
  conversation?: ConversationInfo;
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
  blink_count?: number | null;
  blink_status?: string;
  blink_reason?: string | null;
  blink_note?: string | null;
  scores_emitted?: boolean;
  frames_rejected_quality?: number;
  frames_enhanced?: number;
  frames_quality_warning?: number;
  quality_reject_reasons?: Record<string, number>;
}

export interface EngagementSummary {
  very_low_ratio?: number;
  low_ratio?: number;
  high_ratio?: number;
  very_high_ratio?: number;
  /** stage1_cnn_engagement (0–1). Official Stage-1 engagement family. */
  average_engagement_score?: number;
}

export interface EngagementMetrics {
  stage1_cnn_engagement?: {
    metric_id: "stage1_cnn_engagement";
    value?: number | null;
    scale?: string;
    used_by?: string;
    source?: string;
    result_field?: string;
  };
  diagnostic_engagement?: {
    metric_id: "diagnostic_engagement";
    value?: number | null;
    scale?: string;
    used_by?: string;
    source?: string;
    result_field?: string;
    not_official?: boolean;
  };
  feature_complete_engagement?: {
    metric_id: "feature_complete_engagement";
    value?: number | null;
    scale?: string;
    used_by?: string;
    source?: string;
    result_field?: string;
    not_official?: boolean;
  };
}

export interface EmotionSummary {
  positive_ratio: number;
  neutral_ratio: number;
  negative_ratio: number;
}

export interface AnalysisResult {
  timeline: TimelineItem[];
  confidence_score: number | null;
  /** diagnostic_engagement 0–100. Not official Stage-1. */
  engagement_score: number | null;
  engagement_summary?: EngagementSummary;
  engagement_metrics?: EngagementMetrics;
  summary: EmotionSummary;
  coverage?: CoverageInfo;
  video_status?: string;
  audio_analysis?: AudioAnalysis;
  llm_evaluation?: LlmEvaluation;
  qa_analysis?: QaAnalysis;
  assessment?: VivaAssessment;
  mark_id?: string;
  persistence_error?: string;
  video_features?: Record<string, unknown>;
  feature_complete?: Record<string, unknown>;
  scoring?: {
    current_stage1?: {
      ai_performance?: number | null;
      final_score?: number | null;
      status?: string;
      scoring_version?: string;
    };
    feature_complete?: {
      engagement?: number | null;
      audio?: number | null;
      transcript?: number | null;
    };
  };
}

export type AssessmentMode = "WITHOUT_TECHNICAL_ACCURACY" | "WITH_TECHNICAL_ACCURACY";

export interface VivaAssessment {
  scoring_version?: string;
  feature_schema_version?: string;
  assessment_mode?: AssessmentMode;
  status?: "VALID" | "INCOMPLETE";
  quality?: Record<string, unknown>;
  features?: Record<string, unknown>;
  validation?: { status?: string; reasons?: string[]; message?: string | null };
  ai_performance?: {
    score?: number | null;
    family_scores?: Record<string, number | null>;
    family_weights_applied?: Record<string, number>;
    components?: Array<Record<string, unknown>>;
  };
  technical_accuracy?: number | null;
  fusion?: Record<string, unknown> | null;
  final_score?: number | null;
  grade?: string | null;
}

export function resolveGradeFromPercent(percent: number | null | undefined): string | null {
  if (percent == null || Number.isNaN(percent)) return null;
  const band = GRADE_BANDS.find((b) => percent >= b.minPercent);
  return band?.grade ?? "F";
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
    const twoVoices = (audio_analysis.diarization?.speaker_count ?? 0) >= 2;
    notes.push(
      twoVoices
        ? `Student transcript captured ${audio_analysis.transcript_word_count} words after splitting two speakers.`
        : `Transcript captured ${audio_analysis.transcript_word_count} words across ${audio_analysis.segment_count ?? 0} segment${audio_analysis.segment_count === 1 ? "" : "s"}.`,
    );
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
