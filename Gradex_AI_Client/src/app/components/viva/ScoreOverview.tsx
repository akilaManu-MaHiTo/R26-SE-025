import { Gauge, Activity, AudioLines } from "lucide-react";
import { Card } from "../ui/card";

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
  confidenceScore: number | null;
  engagementScore: number | null;
  audioGrade?: number | null;
  videoStatus?: string;
  faceCoverageRatio?: number;
  framesRejectedQuality?: number;
  framesEnhanced?: number;
  framesQualityWarning?: number;
}

export function ScoreOverview({
  confidenceScore,
  engagementScore,
  audioGrade,
  videoStatus,
  faceCoverageRatio,
  framesRejectedQuality,
  framesEnhanced,
  framesQualityWarning,
}: ScoreOverviewProps) {
  const coveragePct =
    faceCoverageRatio != null ? `${Math.round(faceCoverageRatio * 100)}% face coverage` : "Facial affect positivity";
  const notes: string[] = [];
  if (framesEnhanced && framesEnhanced > 0) {
    notes.push(`${framesEnhanced} frame${framesEnhanced === 1 ? "" : "s"} enhanced`);
  }
  if (framesQualityWarning && framesQualityWarning > 0) {
    notes.push(`${framesQualityWarning} still soft/dark`);
  }
  if (framesRejectedQuality && framesRejectedQuality > 0) {
    notes.push(`${framesRejectedQuality} too small to score`);
  }
  const extra = notes.length ? ` · ${notes.join(" · ")}` : "";
  const confidenceHint =
    videoStatus === "insufficient_face_coverage"
      ? "Withheld — face coverage too low"
      : `${coveragePct}${extra}`;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <ScoreCard
        icon={<Gauge className="size-4" />}
        label="Facial Positivity"
        value={confidenceScore != null ? confidenceScore.toFixed(1) : "—"}
        unit="/ 100"
        hint={confidenceHint}
        tone="violet"
      />
      <ScoreCard
        icon={<Activity className="size-4" />}
        label="Engagement"
        value={engagementScore != null ? engagementScore.toFixed(1) : "—"}
        unit={engagementScore != null ? "%" : ""}
        hint={
          videoStatus === "insufficient_face_coverage"
            ? "Withheld — face coverage too low"
            : "Overall engagement"
        }
        tone="emerald"
      />
      <ScoreCard
        icon={<AudioLines className="size-4" />}
        label="Audio Quality"
        value={audioGrade != null ? audioGrade.toFixed(2) : "—"}
        unit="/ 10"
        hint="Voice analysis"
        tone="amber"
      />
    </div>
  );
}
