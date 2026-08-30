import {
  AnalysisResult,
  AssessmentMode,
  VivaAssessment,
  VivaFusion,
  resolveGradeFromPercent,
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

export function fusePreviewScore(
  aiScore: number,
  technicalAccuracy0to10: number,
  weights: FusionWeights = FALLBACK_FUSION,
): number {
  const technical100 = (technicalAccuracy0to10 / 10) * 100;
  const final = weights.weightAi * aiScore + weights.weightTechnical * technical100;
  return Math.round(final * 100) / 100;
}

export function formatFusionLabel(weights: FusionWeights): string {
  const aiPct = Math.round(weights.weightAi * 100);
  const techPct = Math.round(weights.weightTechnical * 100);
  return `Fusion: ${aiPct}% AI performance + ${techPct}% technical accuracy (0–10 scaled to 100).`;
}

export interface ResolveOfficialMarkInput {
  assessment?: VivaAssessment | null;
  analysisResult?: Pick<AnalysisResult, "final_score" | "final_grade"> | null;
  assessmentMode: AssessmentMode;
  technicalAccuracy: number | null;
  published: boolean;
}

export interface ResolvedOfficialMark {
  finalScore: number | null;
  grade: string | null;
  /** True when the UI is estimating before publish (with-tech draft only). */
  isPreview: boolean;
}

/**
 * Single client rule for official marks:
 * 1. INCOMPLETE → no mark
 * 2. Server final_score / final_grade when saved or published
 * 3. With-tech draft → live preview using server fusion weights
 * 4. Without-tech → AI performance score
 */
export function resolveOfficialMark({
  assessment,
  analysisResult,
  assessmentMode,
  technicalAccuracy,
  published,
}: ResolveOfficialMarkInput): ResolvedOfficialMark {
  if (assessment?.status === "INCOMPLETE") {
    return { finalScore: null, grade: null, isPreview: false };
  }

  const serverFinal = analysisResult?.final_score ?? assessment?.final_score ?? null;
  const serverGrade = analysisResult?.final_grade ?? assessment?.grade ?? null;
  const withTech = assessmentMode === "WITH_TECHNICAL_ACCURACY";
  const techPublished = withTech && published;

  // Deliberately does NOT consider auto_published here. Every valid analysis
  // auto-publishes without technical accuracy, so treating that as "saved"
  // would return the without-tech score in with-tech mode and make the live
  // preview below unreachable.
  if (serverFinal != null && (!withTech || techPublished)) {
    return {
      finalScore: serverFinal,
      grade: serverGrade ?? resolveGradeFromPercent(serverFinal),
      isPreview: false,
    };
  }

  const aiScore = assessment?.ai_performance?.score ?? null;
  if (aiScore == null) {
    return { finalScore: null, grade: null, isPreview: false };
  }

  if (!withTech) {
    return {
      finalScore: serverFinal ?? aiScore,
      grade: serverGrade ?? resolveGradeFromPercent(serverFinal ?? aiScore),
      isPreview: false,
    };
  }

  if (technicalAccuracy == null) {
    return { finalScore: null, grade: null, isPreview: false };
  }

  const weights = parseFusionWeights(assessment?.fusion as VivaFusion | undefined);
  const previewFinal = fusePreviewScore(aiScore, technicalAccuracy, weights);
  return {
    finalScore: previewFinal,
    grade: resolveGradeFromPercent(previewFinal),
    isPreview: true,
  };
}
