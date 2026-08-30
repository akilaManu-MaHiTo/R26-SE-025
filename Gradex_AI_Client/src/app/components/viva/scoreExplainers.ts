import type { AssessmentMode, VivaAssessment } from "./types";
import { parseFusionWeights } from "./officialMark";

export type ScoreExplainTopic =
  | "official_mark"
  | "grade"
  | "ai_performance"
  | "engagement"
  | "audio_acoustics"
  | "transcript"
  | "face_coverage"
  | "supporting_signals";

export interface ScoreExplainContent {
  title: string;
  summary: string;
  lines: string[];
  formula?: string;
}

const GRADE_BANDS = [
  "A+ ≥ 90",
  "A ≥ 80",
  "B+ ≥ 70",
  "B ≥ 60",
  "C+ ≥ 50",
  "C ≥ 40",
  "F < 40",
];

const FAMILY_LABELS: Record<string, string> = {
  engagement: "Engagement",
  audio_acoustics: "Audio acoustics",
  transcript: "Transcript",
};

const COMPONENT_LABELS: Record<string, string> = {
  average_engagement_score: "Face CNN engagement",
  facial_confidence: "Facial confidence / positivity",
  pitch_stability_from_std: "Pitch stability",
  clarity_from_hnr: "Voice clarity (HNR)",
  articulation_from_jitter_shimmer: "Articulation (jitter/shimmer)",
  speech_rate_band: "Speech-rate band",
  hedge_count: "Hedge words (fewer is better)",
  filler_count: "Fillers (fewer is better)",
  long_pause_count: "Long pauses (fewer is better)",
  sentence_completion_ratio: "Sentence completion",
};

function pct(weight: number | undefined, fallback: string): string {
  if (weight == null || Number.isNaN(weight)) return fallback;
  return `${Math.round(weight * 1000) / 10}%`;
}

function familyScoreLine(
  assessment: VivaAssessment | undefined,
  family: string,
): string | null {
  const score = assessment?.ai_performance?.family_scores?.[family];
  if (score == null) return null;
  return `This recording: ${Math.round(score * 100)} / 100`;
}

function componentLines(
  assessment: VivaAssessment | undefined,
  family: string,
): string[] {
  const comps = (assessment?.ai_performance?.components || []).filter(
    (c) => String(c.family || "") === family,
  );
  if (comps.length === 0) return [];
  return comps.map((c) => {
    const key = String(c.feature || "");
    const label = COMPONENT_LABELS[key] || key.replace(/_/g, " ");
    const value =
      typeof c.normalized === "number"
        ? `${Math.round(Number(c.normalized) * 100)}/100`
        : "—";
    const w =
      typeof c.weight_within_family === "number"
        ? ` · ${pct(Number(c.weight_within_family), "")} of this family`
        : "";
    return `${label}: ${value}${w}`;
  });
}

export function buildScoreExplain(
  topic: ScoreExplainTopic,
  options: {
    assessment?: VivaAssessment;
    assessmentMode?: AssessmentMode;
  } = {},
): ScoreExplainContent {
  const { assessment, assessmentMode } = options;
  const version = assessment?.scoring_version || "v1.1";
  const weights = assessment?.ai_performance?.family_weights_applied;
  const withTech =
    (assessmentMode || assessment?.assessment_mode) === "WITH_TECHNICAL_ACCURACY";
  const fusion = parseFusionWeights(assessment?.fusion);

  switch (topic) {
    case "official_mark":
    case "ai_performance": {
      const eng = pct(weights?.engagement, "≈33.3%");
      const audio = pct(weights?.audio_acoustics, "≈33.3%");
      const transcript = pct(weights?.transcript, "≈33.3%");
      const lines = [
        `Scorer ${version}`,
        `Engagement ${eng} · Audio ${audio} · Transcript ${transcript}`,
        "Equal average of available families (missing families are dropped and weights re-balance).",
        "Emotion: not a separate % of the mark. It enters inside Engagement as facial confidence/positivity (emotion-weighted face tone), mixed 50/50 with Face CNN engagement.",
        "Still not included: LLM clarity/confidence, audio quality /10, engagement blend %, Positive/Neutral/Negative emotion bars as their own family.",
      ];
      if (withTech) {
        lines.push(
          `Technical mode: final = ${Math.round(fusion.weightAi * 100)}% AI performance + ${Math.round(fusion.weightTechnical * 100)}% technical accuracy.`,
        );
      } else {
        lines.push("Non-technical mode: official mark = AI performance score (100%).");
      }
      const score = assessment?.ai_performance?.score;
      if (score != null) {
        lines.unshift(`This recording: ${score.toFixed(1)} / 100`);
      }
      return {
        title: topic === "official_mark" ? "How the official mark is calculated" : "How AI performance is calculated",
        summary: withTech
          ? "Blend of AI performance and technical accuracy."
          : "Equal mix of engagement, audio acoustics, and transcript. Emotion feeds Engagement via facial confidence.",
        lines,
        formula: withTech
          ? `Final = ${fusion.weightAi}×AI + ${fusion.weightTechnical}×Technical`
          : "Final = (Engagement + Audio + Transcript) / 3",
      };
    }
    case "engagement": {
      const comps = componentLines(assessment, "engagement");
      const lines = [
        familyScoreLine(assessment, "engagement") || "Part of the official mark (≈33.3%).",
        ...(comps.length > 0
          ? ["Inside this family (equal parts when both measured):", ...comps]
          : [
              "Equal mix inside this family (when both are available):",
              "• Face CNN engagement average",
              "• Facial confidence / positivity",
            ]),
        "Not the hero “engagement blend %” — that stays a supporting signal only.",
        "Emotion bars (Positive/Neutral/Negative %) are not scored alone; facial confidence is the emotion input here.",
      ];
      return {
        title: "Engagement (≈33.3% of mark)",
        summary: "Face CNN engagement + facial confidence (emotion-weighted).",
        lines,
        formula: "Engagement = (CNN + facial confidence) / 2",
      };
    }
    case "audio_acoustics": {
      const comps = componentLines(assessment, "audio_acoustics");
      const lines = [
        familyScoreLine(assessment, "audio_acoustics") || "Part of the official mark (≈33.3%).",
        ...(comps.length > 0
          ? ["Acoustic parts used for this recording:", ...comps]
          : [
              "Equal average of measured acoustic parts:",
              "• Pitch stability",
              "• Voice clarity (HNR)",
              "• Articulation (jitter / shimmer)",
            ]),
        "Not the supporting “audio quality /10” grade.",
      ];
      return {
        title: "Audio acoustics (≈33.3% of mark)",
        summary: "Pitch stability, clarity, and articulation.",
        lines,
        formula: "Audio = average of available acoustic parts",
      };
    }
    case "transcript": {
      const comps = componentLines(assessment, "transcript");
      const lines = [
        familyScoreLine(assessment, "transcript") || "Part of the official mark (≈33.3%).",
        ...(comps.length > 0
          ? ["Transcript parts used for this recording:", ...comps]
          : [
              "Equal average of delivery features:",
              "• Speech-rate band",
              "• Fillers / hedges / long pauses (fewer is better)",
              "• Sentence completion",
            ]),
        "Not LLM clarity or English “quality” scores.",
      ];
      return {
        title: "Transcript (≈33.3% of mark)",
        summary: "Speech rate and delivery features from the transcript.",
        lines,
        formula: "Transcript = average of available delivery parts",
      };
    }
    case "grade":
      return {
        title: "How the letter grade is assigned",
        summary: "Letter band from the official mark /100.",
        lines: [
          ...GRADE_BANDS,
          "Example: 66.7 → Grade B (60–69).",
        ],
        formula: "Grade = band for official mark",
      };
    case "face_coverage":
      return {
        title: "Face coverage",
        summary: "Quality gate — not a percentage of the mark.",
        lines: [
          "Share of sampled frames where a usable face was visible.",
          "Without enough face coverage, the recording is INCOMPLETE and no official mark is given.",
          "100% means the face was visible throughout scoring frames.",
        ],
      };
    case "supporting_signals":
      return {
        title: "Supporting signals",
        summary: "Most of these are display-only. Facial positivity also feeds Engagement in scorer v1.1+.",
        lines: [
          "Facial positivity — shown here, and (in v1.1+) half of the Engagement family.",
          "Engagement blend % — diagnostic UI blend only (0% of official mark).",
          "Audio quality /10 — display audio_grade; official mark uses the acoustic family instead.",
          "LLM clarity / confidence / engagement — interpretation only (0% of official mark).",
        ],
      };
    default:
      return {
        title: FAMILY_LABELS[topic] || "Score detail",
        summary: "",
        lines: [],
      };
  }
}
