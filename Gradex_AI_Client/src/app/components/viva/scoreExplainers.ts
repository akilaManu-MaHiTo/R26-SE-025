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
  /** The same formula with this recording's real numbers substituted in, so a
   * viewer can check the arithmetic themselves rather than trusting the total. */
  workedExample?: string[];
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

/** A family's real applied weight for this recording, e.g. "50%" when one
 * family was dropped. Falls back to the nominal third. */
function familyWeightLabel(
  assessment: VivaAssessment | undefined,
  family: string,
): string {
  const weights = assessment?.ai_performance?.family_weights_applied;
  const w = weights?.[family];
  if (w != null && !Number.isNaN(w)) return pct(w, "≈33.3%");
  return "≈33.3%";
}

/** Substituted arithmetic for the official mark: one line per family showing
 * `score x weight = contribution`, then the total. Returns [] when the scorer
 * produced no mark (INCOMPLETE), where there is no arithmetic to show. */
function officialMarkWorking(
  assessment: VivaAssessment | undefined,
  withTech: boolean,
  fusion: { weightAi: number; weightTechnical: number },
): string[] {
  const perf = assessment?.ai_performance;
  const weights = perf?.family_weights_applied;
  const scores = perf?.family_scores;
  const ai = perf?.score;
  if (!weights || !scores || ai == null) return [];

  const names = Object.keys(weights);
  if (names.length === 0) return [];

  const rows = names.map((name) => {
    const score = Number(scores[name] ?? 0);
    const weight = Number(weights[name] ?? 0);
    const label = FAMILY_LABELS[name] || name;
    // Family scores are 0-1; show them on the same /100 scale as the mark.
    return `${label.padEnd(16)} ${(score * 100).toFixed(1).padStart(5)} x ${pct(
      weight,
      "",
    ).padStart(5)} = ${(score * 100 * weight).toFixed(1).padStart(5)}`;
  });

  rows.push(`${"AI performance".padEnd(16)} ${" ".repeat(16)}= ${ai.toFixed(1).padStart(5)}`);

  if (!withTech) {
    rows.push(`${"Official mark".padEnd(16)} ${" ".repeat(16)}= ${ai.toFixed(1).padStart(5)}`);
    return rows;
  }

  const tech = assessment?.technical_accuracy;
  if (tech == null) {
    rows.push("Technical accuracy not entered yet — final mark is pending.");
    return rows;
  }
  const tech100 = Number(tech) * 10;
  const final = fusion.weightAi * ai + fusion.weightTechnical * tech100;
  rows.push(
    `${"AI".padEnd(16)} ${ai.toFixed(1).padStart(5)} x ${pct(fusion.weightAi, "").padStart(5)} = ${(
      fusion.weightAi * ai
    )
      .toFixed(1)
      .padStart(5)}`,
    `${"Technical".padEnd(16)} ${tech100.toFixed(1).padStart(5)} x ${pct(
      fusion.weightTechnical,
      "",
    ).padStart(5)} = ${(fusion.weightTechnical * tech100).toFixed(1).padStart(5)}`,
    `${"Official mark".padEnd(16)} ${" ".repeat(16)}= ${final.toFixed(1).padStart(5)}`,
  );
  return rows;
}

/** Substituted arithmetic for one family: each component, then the mean. */
function familyWorking(
  assessment: VivaAssessment | undefined,
  family: string,
): string[] {
  const comps = (assessment?.ai_performance?.components || []).filter(
    (c) => String(c.family || "") === family,
  );
  const score = assessment?.ai_performance?.family_scores?.[family];
  if (comps.length === 0 || score == null) return [];

  const rows = comps.map((c) => {
    const key = String(c.feature || "");
    const label = COMPONENT_LABELS[key] || key.replace(/_/g, " ");
    const value = typeof c.normalized === "number" ? Number(c.normalized) * 100 : 0;
    return `${label.slice(0, 24).padEnd(26)} ${value.toFixed(1).padStart(5)}`;
  });
  rows.push(
    `${`average of ${comps.length}`.padEnd(26)} ${(Number(score) * 100).toFixed(1).padStart(5)}`,
  );
  return rows;
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
      // A family with no usable inputs is dropped by the scorer and the rest
      // renormalize, so read the applied weights rather than assuming 33.3%
      // each — otherwise the tooltip's percentages will not reconcile with the
      // mark whenever (say) audio was unmeasurable.
      const familyScores = assessment?.ai_performance?.family_scores;
      const dropped = familyScores
        ? (Object.keys(FAMILY_LABELS) as string[]).filter(
            (name) => familyScores[name] == null,
          )
        : [];
      const applied = weights ? Object.keys(weights).length : 3;
      const evenPct = `≈${Math.round((100 / applied) * 10) / 10}%`;
      const eng = pct(weights?.engagement, evenPct);
      const audio = pct(weights?.audio_acoustics, evenPct);
      const transcript = pct(weights?.transcript, evenPct);
      const lines = [
        `Scorer ${version}`,
        `Engagement ${eng} · Audio ${audio} · Transcript ${transcript}`,
        dropped.length > 0
          ? `Not measurable in this recording, so dropped: ${dropped
              .map((name) => FAMILY_LABELS[name])
              .join(", ")}. The remaining ${applied} ${
              applied === 1 ? "family carries" : "families carry"
            } the whole mark at the percentages above.`
          : "Equal average of available families (missing families are dropped and weights re-balance).",
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
          : weights && Object.keys(weights).length > 0
            ? `AI = (${Object.keys(weights)
                .map((name) => FAMILY_LABELS[name] || name)
                .join(" + ")}) / ${Object.keys(weights).length}`
            : "Final = (Engagement + Audio + Transcript) / 3",
        workedExample: officialMarkWorking(assessment, withTech, fusion),
      };
    }
    case "engagement": {
      const comps = componentLines(assessment, "engagement");
      const lines = [
        familyScoreLine(assessment, "engagement") ||
          `Part of the official mark (${familyWeightLabel(assessment, "engagement")}).`,
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
        title: `Engagement (${familyWeightLabel(assessment, "engagement")} of mark)`,
        summary: "Face CNN engagement + facial confidence (emotion-weighted).",
        lines,
        formula: "Engagement = (CNN + facial confidence) / 2",
        workedExample: familyWorking(assessment, "engagement"),
      };
    }
    case "audio_acoustics": {
      const comps = componentLines(assessment, "audio_acoustics");
      const lines = [
        familyScoreLine(assessment, "audio_acoustics") ||
          `Part of the official mark (${familyWeightLabel(assessment, "audio_acoustics")}).`,
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
        title: `Audio acoustics (${familyWeightLabel(assessment, "audio_acoustics")} of mark)`,
        summary: "Pitch stability, clarity, and articulation.",
        lines,
        formula: "Audio = average of available acoustic parts",
        workedExample: familyWorking(assessment, "audio_acoustics"),
      };
    }
    case "transcript": {
      const comps = componentLines(assessment, "transcript");
      const lines = [
        familyScoreLine(assessment, "transcript") ||
          `Part of the official mark (${familyWeightLabel(assessment, "transcript")}).`,
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
        title: `Transcript (${familyWeightLabel(assessment, "transcript")} of mark)`,
        summary: "Speech rate and delivery features from the transcript.",
        lines,
        formula: "Transcript = average of available delivery parts",
        workedExample: familyWorking(assessment, "transcript"),
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
