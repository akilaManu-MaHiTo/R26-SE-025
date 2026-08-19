import { useMemo, useState } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { Slider } from "../ui/slider";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import {
  AssessmentMode,
  VivaAssessment,
  resolveGradeFromPercent,
} from "./types";

interface EvaluationPanelProps {
  assessment?: VivaAssessment;
  assessmentMode: AssessmentMode;
  onChangeMode: (mode: AssessmentMode) => void;
  technicalAccuracy: number | null;
  onChangeTechnicalAccuracy: (value: number) => void;
  studentId: string;
  onChangeStudentId: (value: string) => void;
  aiRecommendation: string;
  published: boolean;
  publishing?: boolean;
  onPublish: () => void;
}

const FUSION_AI = 0.5;
const FUSION_TECH = 0.5;

export function EvaluationPanel({
  assessment,
  assessmentMode,
  onChangeMode,
  technicalAccuracy,
  onChangeTechnicalAccuracy,
  studentId,
  onChangeStudentId,
  aiRecommendation,
  published,
  publishing = false,
  onPublish,
}: EvaluationPanelProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const incomplete = assessment?.status === "INCOMPLETE";
  const aiScore = assessment?.ai_performance?.score ?? null;
  const withTech = assessmentMode === "WITH_TECHNICAL_ACCURACY";

  const preview = useMemo(() => {
    if (aiScore == null || incomplete) return { final: null as number | null, grade: null as string | null };
    if (!withTech) {
      return { final: aiScore, grade: resolveGradeFromPercent(aiScore) };
    }
    if (technicalAccuracy == null) return { final: null, grade: null };
    const technical100 = (technicalAccuracy / 10) * 100;
    const final = FUSION_AI * aiScore + FUSION_TECH * technical100;
    return { final: Math.round(final * 100) / 100, grade: resolveGradeFromPercent(final) };
  }, [aiScore, incomplete, withTech, technicalAccuracy]);

  const canPublish =
    !incomplete &&
    aiScore != null &&
    (!withTech || technicalAccuracy != null);

  const familyScores = assessment?.ai_performance?.family_scores || {};

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-foreground">AI Performance</div>
        <Badge variant="outline" className="text-xs">
          {assessment?.scoring_version ? `scorer ${assessment.scoring_version}` : "engine"}
        </Badge>
      </div>

      {incomplete && (
        <p className="mt-3 text-xs text-amber-700 dark:text-amber-400">
          {assessment?.validation?.message ||
            `Incomplete analysis — no official grade.${
              (assessment?.validation?.reasons || []).length > 0
                ? ` ${assessment?.validation?.reasons?.join(", ")}`
                : ""
            }`}
        </p>
      )}

      <div className="mt-4">
        <div className="text-xs text-muted-foreground uppercase tracking-wide">AI performance score</div>
        <div className="tracking-tight text-foreground mt-0.5">
          <span className="text-3xl font-semibold">{aiScore != null ? aiScore.toFixed(1) : "—"}</span>
          <span className="text-muted-foreground"> / 100</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">Locked engine score — not LLM rubric values.</p>
      </div>

      <div className="mt-4 space-y-1.5 text-xs text-muted-foreground">
        {(["engagement", "audio_acoustics", "transcript"] as const).map((family) => (
          <div key={family} className="flex justify-between gap-2">
            <span className="capitalize">{family.replace("_", " ")}</span>
            <span>
              {familyScores[family] != null ? `${(familyScores[family]! * 100).toFixed(0)} / 100` : "—"}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 p-3 rounded-lg bg-primary/5 border border-primary/10 text-xs text-foreground/90">
        <span className="font-medium text-foreground">AI interpretation: </span>
        {aiRecommendation}
      </div>

      <div className="mt-5 space-y-2">
        <div className="text-sm text-foreground">Assessment mode</div>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="radio"
            name="viva-mode"
            className="mt-1"
            disabled={published}
            checked={!withTech}
            onChange={() => onChangeMode("WITHOUT_TECHNICAL_ACCURACY")}
          />
          <span>
            Without technical accuracy
            <span className="block text-xs text-muted-foreground">Communication / presentation vivas</span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="radio"
            name="viva-mode"
            className="mt-1"
            disabled={published}
            checked={withTech}
            onChange={() => onChangeMode("WITH_TECHNICAL_ACCURACY")}
          />
          <span>
            With technical accuracy
            <span className="block text-xs text-muted-foreground">Technical modules — examiner enters subject knowledge</span>
          </span>
        </label>
      </div>

      {withTech && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm gap-2">
            <div>
              <div className="text-foreground">Technical accuracy</div>
              <div className="text-xs text-muted-foreground">Examiner only — not inferred from video</div>
            </div>
            <span className="font-medium shrink-0">
              {technicalAccuracy != null ? `${technicalAccuracy} / 10` : "— / 10"}
            </span>
          </div>
          <Slider
            className="mt-2"
            value={[technicalAccuracy ?? 0]}
            min={0}
            max={10}
            step={1}
            disabled={published}
            onValueChange={([v]) => onChangeTechnicalAccuracy(v)}
            aria-label="Technical accuracy"
          />
        </div>
      )}

      <div className="mt-4">
        <label className="text-xs text-muted-foreground" htmlFor="viva-student-id">
          Student ID (optional, for training rows)
        </label>
        <Input
          id="viva-student-id"
          className="mt-1"
          value={studentId}
          disabled={published}
          onChange={(e) => onChangeStudentId(e.target.value)}
          placeholder="e.g. STU-001"
        />
      </div>

      <div className="mt-5 pt-4 border-t border-border">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Final score</div>
            <div className="tracking-tight text-foreground mt-0.5">
              <span className="text-3xl font-semibold">
                {preview.final != null ? preview.final.toFixed(1) : "—"}
              </span>
              <span className="text-muted-foreground"> / 100</span>
            </div>
          </div>
          <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border-0">
            Grade {preview.grade ?? "—"}
          </Badge>
        </div>
        {withTech && (
          <p className="mt-2 text-xs text-muted-foreground">
            Fusion v1: 50% AI performance + 50% technical accuracy (0–10 scaled to 100).
          </p>
        )}
      </div>

      {published ? (
        <div className="w-full mt-4 flex items-center justify-center gap-2 rounded-lg border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="size-4" />
          Assessment published
        </div>
      ) : (
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <Button
            className="w-full mt-4"
            disabled={!canPublish || publishing}
            onClick={() => setConfirmOpen(true)}
          >
            <Lock className="size-4" />
            {publishing ? "Publishing…" : "Save & publish"}
          </Button>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Publish this assessment?</AlertDialogTitle>
              <AlertDialogDescription>
                Publishes final score {preview.final != null ? preview.final.toFixed(1) : "—"}/100
                (grade {preview.grade ?? "—"}) and stores a training row. AI performance stays locked.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                disabled={publishing}
                onClick={() => {
                  setConfirmOpen(false);
                  onPublish();
                }}
              >
                Publish
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
      {!published && !canPublish && !incomplete && withTech && technicalAccuracy == null && (
        <p className="mt-2 text-xs text-muted-foreground text-center">Set technical accuracy to publish.</p>
      )}
    </div>
  );
}
