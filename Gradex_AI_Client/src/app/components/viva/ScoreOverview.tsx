import { Award, ScanFace, AudioLines } from "lucide-react";
import { Card } from "../ui/card";
import { AnalysisResult, AssessmentMode, VivaAssessment } from "./types";
import { resolveOfficialMark } from "./officialMark";
import { ScoreExplainHover } from "./ScoreExplainHover";
import type { ScoreExplainTopic } from "./scoreExplainers";

interface ScoreCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  hint?: string;
  tone: "violet" | "emerald" | "amber";
  explainTopic?: ScoreExplainTopic;
  assessment?: VivaAssessment;
  assessmentMode?: AssessmentMode;
}

const toneClasses: Record<ScoreCardProps["tone"], { icon: string; ring: string }> = {
  violet: { icon: "text-violet-600 bg-violet-50 dark:bg-violet-500/10", ring: "border-border" },
  emerald: { icon: "text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10", ring: "border-border" },
  amber: { icon: "text-amber-600 bg-amber-50 dark:bg-amber-500/10", ring: "border-border" },
};

function ScoreCard({
  icon,
  label,
  value,
  unit,
  hint,
  tone,
  explainTopic,
  assessment,
  assessmentMode,
}: ScoreCardProps) {
  const t = toneClasses[tone];
  const labelNode = explainTopic ? (
    <ScoreExplainHover
      topic={explainTopic}
      assessment={assessment}
      assessmentMode={assessmentMode}
      className="text-xs uppercase tracking-wide text-muted-foreground font-medium"
    >
      {label}
    </ScoreExplainHover>
  ) : (
    <div className="text-xs uppercase tracking-wide text-muted-foreground font-medium">{label}</div>
  );

  return (
    <Card className={`p-4 gap-1 ${t.ring}`}>
      <div className="flex items-center gap-2">
        <div className={`size-8 rounded-lg flex items-center justify-center shrink-0 ${t.icon}`}>{icon}</div>
        {labelNode}
      </div>
      <div className="text-foreground">
        <span className="text-2xl font-semibold tracking-tight">{value}</span>
        <span className="text-sm text-muted-foreground font-normal ml-0.5">{unit}</span>
      </div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </Card>
  );
}

interface ScoreOverviewProps {
  assessment?: VivaAssessment;
  analysisResult?: Pick<AnalysisResult, "final_score" | "final_grade"> | null;
  assessmentMode: AssessmentMode;
  technicalAccuracy: number | null;
  published: boolean;
  videoStatus?: string;
  faceCoverageRatio?: number;
  confidenceScore?: number | null;
  engagementScore?: number | null;
  audioGrade?: number | null;
}

export function ScoreOverview({
  assessment,
  analysisResult,
  assessmentMode,
  technicalAccuracy,
  published,
  videoStatus,
  faceCoverageRatio,
  confidenceScore,
  engagementScore,
  audioGrade,
}: ScoreOverviewProps) {
  const incomplete = assessment?.status === "INCOMPLETE";
  const { finalScore: official, grade, isPreview } = resolveOfficialMark({
    assessment,
    analysisResult,
    assessmentMode,
    technicalAccuracy,
    published,
  });
  const coveragePct =
    faceCoverageRatio != null ? `${Math.round(faceCoverageRatio * 100)}%` : "—";
  const faceHint =
    videoStatus === "insufficient_face_coverage" || incomplete
      ? "Required — no official mark without a visible face"
      : undefined;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <ScoreCard
          icon={<Award className="size-4" />}
          label="Official mark"
          value={official != null ? official.toFixed(1) : "—"}
          unit="/ 100"
          hint={
            incomplete
              ? assessment?.validation?.message || "Incomplete — face required"
              : isPreview
                ? "Preview with technical accuracy — publish to save"
                : undefined
          }
          tone="violet"
          explainTopic="official_mark"
          assessment={assessment}
          assessmentMode={assessmentMode}
        />
        <ScoreCard
          icon={<ScanFace className="size-4" />}
          label="Face coverage"
          value={coveragePct}
          unit={faceCoverageRatio != null ? "" : ""}
          hint={faceHint}
          tone="emerald"
          explainTopic="face_coverage"
          assessment={assessment}
          assessmentMode={assessmentMode}
        />
        <ScoreCard
          icon={<AudioLines className="size-4" />}
          label="Grade"
          value={grade ?? "—"}
          unit=""
          hint={incomplete ? "Withheld until a face is on camera" : undefined}
          tone="amber"
          explainTopic="grade"
          assessment={assessment}
          assessmentMode={assessmentMode}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        <ScoreExplainHover
          topic="supporting_signals"
          assessment={assessment}
          assessmentMode={assessmentMode}
          className="text-xs text-muted-foreground"
        >
          Supporting signals
        </ScoreExplainHover>
        {" "}
        (not the full official mark): facial positivity{" "}
        {confidenceScore != null ? confidenceScore.toFixed(1) : "—"}/100 · engagement blend{" "}
        {engagementScore != null ? engagementScore.toFixed(1) : "—"}
        {engagementScore != null ? "%" : ""} · audio quality{" "}
        {audioGrade != null ? audioGrade.toFixed(2) : "—"}/10
      </p>
    </div>
  );
}
