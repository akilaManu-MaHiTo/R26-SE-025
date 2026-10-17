import { getMarkingScale } from "./markingScale";
import {
  AnalysisResult,
  AssessmentMode,
  VivaAssessment,
  VivaFusion,
  percentToMark,
  resolveGradeFromMark,
} from "./types";

/** Fallback only when the server did not attach fusion metadata (should be rare). */
const FALLBACK_FUSION = { weightAi: 0.5, weightTechnical: 0.5 };

export interface FusionWeights {
  weightAi: number;
  weightTechnical: number;
}

/**
 * Weights for a with-technical fusion, taken from the server.
 *
 * A without-technical assessment reports weight_ai 1.0 / weight_technical 0.0 —
 * that describes what it applied, not what a technical publish would apply, so
 * previewing with those would multiply technical accuracy by zero. The server
 * therefore also sends `fusion.with_technical`, which is preferred here.
 */
export function parseFusionWeights(fusion?: VivaFusion | null): FusionWeights {
  const source = fusion?.with_technical ?? fusion;
  const rawAi = source?.weight_ai;
  const rawTechnical = source?.weight_technical;
  const usable =
    typeof rawAi === "number" &&
    Number.isFinite(rawAi) &&
    typeof rawTechnical === "number" &&
    Number.isFinite(rawTechnical) &&
    rawTechnical > 0;
  if (!usable) return { ...FALLBACK_FUSION };
  return { weightAi: rawAi, weightTechnical: rawTechnical };
}

/**
 * Preview of the fused official mark before publish. Mirrors the server: the AI score is a
 * 0-100 percentage, the technical score is out of the scale's technical maximum, and the blend
 * is scaled to the mark scale and rounded to its decimals.
 */
export function fusePreviewMark(
  aiPercent: number,
  technicalAccuracy: number,
  weights: FusionWeights = FALLBACK_FUSION,
): number {
  const technicalPercent = (technicalAccuracy / getMarkingScale().technicalMax) * 100;
  const finalPercent = weights.weightAi * aiPercent + weights.weightTechnical * technicalPercent;
  return percentToMark(finalPercent) ?? 0;
}

export function formatFusionLabel(weights: FusionWeights): string {
  const aiPct = Math.round(weights.weightAi * 100);
  const techPct = Math.round(weights.weightTechnical * 100);
  return `Fusion: ${aiPct}% AI performance + ${techPct}% technical accuracy (out of ${getMarkingScale().technicalMax}).`;
}

export interface ResolveOfficialMarkInput {
  assessment?: VivaAssessment | null;
  analysisResult?: Pick<AnalysisResult, "final_score" | "final_mark" | "final_grade"> | null;
  assessmentMode: AssessmentMode;
  technicalAccuracy: number | null;
  published: boolean;
}

export interface ResolvedOfficialMark {
  /** Official mark, out of `markMax`. */
  finalMark: number | null;
  /** What the mark is out of: the scale it was given on, or the current scale for a new estimate. */
  markMax: number;
  grade: string | null;
  /** True when the UI is estimating before publish (with-tech draft only). */
  isPreview: boolean;
}

/**
 * Single client rule for official marks (all on the configured mark scale):
 * 1. INCOMPLETE → no mark
 * 2. Server final_mark / final_grade when saved or published
 * 3. With-tech draft → live preview using server fusion weights
 * 4. Without-tech → AI performance mark
 * The grade always follows the rounded mark, i.e. the number the examiner sees.
 */
export function resolveOfficialMark({
  assessment,
  analysisResult,
  assessmentMode,
  technicalAccuracy,
  published,
}: ResolveOfficialMarkInput): ResolvedOfficialMark {
  const currentMax = getMarkingScale().markMax;
  // A saved mark keeps the scale it was given on, even if the scale has changed since.
  const savedMax = analysisResult?.final_mark_max ?? assessment?.final_mark_max ?? null;

  if (assessment?.status === "INCOMPLETE") {
    return { finalMark: null, markMax: savedMax ?? currentMax, grade: null, isPreview: false };
  }

  const serverMark =
    analysisResult?.final_mark ??
    assessment?.final_mark ??
    percentToMark(analysisResult?.final_score ?? assessment?.final_score ?? null);
  const serverGrade = analysisResult?.final_grade ?? assessment?.grade ?? null;
  const withTech = assessmentMode === "WITH_TECHNICAL_ACCURACY";
  const techPublished = withTech && published;

  // Deliberately does NOT consider auto_published here. Every valid analysis
  // auto-publishes without technical accuracy, so treating that as "saved"
  // would return the without-tech mark in with-tech mode and make the live
  // preview below unreachable.
  if (serverMark != null && (!withTech || techPublished)) {
    const markedOnSavedScale = (analysisResult?.final_mark ?? assessment?.final_mark) != null && savedMax != null;
    return {
      finalMark: serverMark,
      markMax: markedOnSavedScale ? (savedMax as number) : currentMax,
      grade: serverGrade ?? resolveGradeFromMark(serverMark),
      isPreview: false,
    };
  }

  const aiScore = assessment?.ai_performance?.score ?? null;
  if (aiScore == null) {
    return { finalMark: null, markMax: currentMax, grade: null, isPreview: false };
  }

  if (!withTech) {
    const mark = serverMark ?? assessment?.ai_performance?.mark ?? percentToMark(aiScore);
    return {
      finalMark: mark,
      markMax: currentMax,
      grade: serverGrade ?? resolveGradeFromMark(mark),
      isPreview: false,
    };
  }

  if (technicalAccuracy == null) {
    return { finalMark: null, markMax: currentMax, grade: null, isPreview: false };
  }

  const weights = parseFusionWeights(assessment?.fusion as VivaFusion | undefined);
  const previewMark = fusePreviewMark(aiScore, technicalAccuracy, weights);
  return {
    finalMark: previewMark,
    markMax: currentMax,
    grade: resolveGradeFromMark(previewMark),
    isPreview: true,
  };
}
