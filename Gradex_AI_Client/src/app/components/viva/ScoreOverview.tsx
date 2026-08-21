import { Award, ScanFace, AudioLines } from "lucide-react";
import { Card } from "../ui/card";
import { VivaAssessment } from "./types";

interface ScoreCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  hint: string;
  tone: "violet" | "emerald" | "amber";
}

const toneClasses: Record<ScoreCardProps["tone"], { icon: string; ring: string }> = {
  violet: { icon: "text-violet-600 bg-violet-50 dark:bg-violet-500/10", ring: "border-border" },
  emerald: { icon: "text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10", ring: "border-border" },
  amber: { icon: "text-amber-600 bg-amber-50 dark:bg-amber-500/10", ring: "border-border" },
};

function ScoreCard({ icon, label, value, unit, hint, tone }: ScoreCardProps) {
  const t = toneClasses[tone];
  return (
    <Card className={`p-4 ${t.ring}`}>
      <div className="flex items-center gap-2">
        <div className={`size-8 rounded-lg flex items-center justify-center shrink-0 ${t.icon}`}>{icon}</div>
        <div className="text-xs uppercase tracking-wide text-muted-foreground font-medium">{label}</div>
      </div>
      <div className="mt-3 text-foreground">
        <span className="text-2xl font-semibold tracking-tight">{value}</span>
        <span className="text-sm text-muted-foreground font-normal ml-0.5">{unit}</span>
      </div>
      <div className="text-xs text-muted-foreground mt-1">{hint}</div>
    </Card>
  );
}

interface ScoreOverviewProps {
  assessment?: VivaAssessment;
  videoStatus?: string;
  faceCoverageRatio?: number;
  framesRejectedQuality?: number;
  framesEnhanced?: number;
  framesQualityWarning?: number;
  confidenceScore?: number | null;
  engagementScore?: number | null;
  audioGrade?: number | null;
}

export function ScoreOverview({
  assessment,
  videoStatus,
  faceCoverageRatio,
  framesRejectedQuality,
  framesEnhanced,
  framesQualityWarning,
  confidenceScore,
  engagementScore,
  audioGrade,
}: ScoreOverviewProps) {
  const incomplete = assessment?.status === "INCOMPLETE";
  const official = assessment?.final_score ?? assessment?.ai_performance?.score ?? null;
  const grade = assessment?.grade ?? null;
  const coveragePct =
    faceCoverageRatio != null ? `${Math.round(faceCoverageRatio * 100)}%` : "—";
  const notes: string[] = [];
  if (framesEnhanced && framesEnhanced > 0) {
    notes.push(`${framesEnhanced} enhanced`);
  }
  if (framesQualityWarning && framesQualityWarning > 0) {
    notes.push(`${framesQualityWarning} still soft/dark`);
  }
  if (framesRejectedQuality && framesRejectedQuality > 0) {
    notes.push(`${framesRejectedQuality} too small`);
  }
  const extra = notes.length ? ` · ${notes.join(" · ")}` : "";
  const faceHint =
    videoStatus === "insufficient_face_coverage" || incomplete
      ? "Required — no official mark without a visible face"
      : `Face on camera${extra}`;

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
              : "Stage-1 engine score (not LLM rubric cards)"
          }
          tone="violet"
        />
        <ScoreCard
          icon={<ScanFace className="size-4" />}
          label="Face coverage"
          value={coveragePct}
          unit={faceCoverageRatio != null ? "" : ""}
          hint={faceHint}
          tone="emerald"
        />
        <ScoreCard
          icon={<AudioLines className="size-4" />}
          label="Grade"
          value={grade ?? "—"}
          unit=""
          hint={incomplete ? "Withheld until a face is on camera" : "From the official mark"}
          tone="amber"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Supporting signals (not the official mark): facial positivity{" "}
        {confidenceScore != null ? confidenceScore.toFixed(1) : "—"}/100 · engagement blend{" "}
        {engagementScore != null ? engagementScore.toFixed(1) : "—"}
        {engagementScore != null ? "%" : ""} · audio quality{" "}
        {audioGrade != null ? audioGrade.toFixed(2) : "—"}/10
      </p>
    </div>
  );
}
