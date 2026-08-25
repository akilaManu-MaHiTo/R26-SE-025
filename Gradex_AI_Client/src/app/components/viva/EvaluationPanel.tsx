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
  TechnicalAccuracyAI,
  VivaAssessment,
} from "./types";
import {
  formatFusionLabel,
  parseFusionWeights,
  resolveOfficialMark,
} from "./officialMark";
import { TechnicalAccuracyPanel } from "./TechnicalAccuracyPanel";

interface EvaluationPanelProps {
  assessment?: VivaAssessment;
  /** Chosen upfront (before upload/recording) via the selector on VivaPage; read-only here. */
  assessmentMode: AssessmentMode;
  technicalAccuracy: number | null;
  onChangeTechnicalAccuracy: (value: number) => void;
  /** AI-suggested score + per-concept evidence; pre-fills the slider above but never publishes on its own. */
  technicalAccuracyAI?: TechnicalAccuracyAI;
  studentId: string;
  onChangeStudentId: (value: string) => void;
  aiRecommendation: string;
  markId?: string | null;
  persistenceError?: string | null;
  autoPublishedWithoutTech?: boolean;
  published: boolean;
  publishing?: boolean;
  onPublish: () => void;
  analysisResult?: {
    final_score?: number | null;
    final_grade?: string | null;
    auto_published?: boolean;
  } | null;
}

export function EvaluationPanel({
  assessment,
  assessmentMode,
  technicalAccuracy,
  onChangeTechnicalAccuracy,
  technicalAccuracyAI,
  studentId,
  onChangeStudentId,
  aiRecommendation,
  markId,
  persistenceError,
  autoPublishedWithoutTech = false,
  published,
  publishing = false,
  onPublish,
  analysisResult,
}: EvaluationPanelProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const incomplete = assessment?.status === "INCOMPLETE";
  const aiScore = assessment?.ai_performance?.score ?? null;
  const withTech = assessmentMode === "WITH_TECHNICAL_ACCURACY";
  const fusionWeights = parseFusionWeights(assessment?.fusion);

  const preview = useMemo(
    () =>
      resolveOfficialMark({
        assessment,
        analysisResult,
        assessmentMode,
        technicalAccuracy,
        published,
      }),
    [assessment, analysisResult, assessmentMode, technicalAccuracy, published],
  );

  const canPublish =
    withTech &&
    Boolean(markId) &&
    !incomplete &&
    aiScore != null &&
    technicalAccuracy != null;

  /** Lock inputs only after a manual publish in technical-accuracy mode. */
  const lockedAfterTechPublish = published && withTech;

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

      {markId ? (
        <div className="mt-4 rounded-lg border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/70 dark:bg-emerald-500/10 px-3 py-2 text-xs text-emerald-800 dark:text-emerald-300">
          {!withTech && autoPublishedWithoutTech
            ? "Score saved automatically."
            : published
              ? "Score saved to MongoDB."
              : withTech
                ? "Draft saved — set technical accuracy and publish when ready."
                : "Score saved to MongoDB."}
        </div>
      ) : persistenceError ? (
        <div className="mt-4 rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/70 dark:bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          {persistenceError}
        </div>
      ) : null}

      <div className="mt-5">
        <div className="flex items-center justify-between">
          <div className="text-sm text-foreground">Assessment type</div>
          <Badge variant="outline" className="text-xs">
            {withTech ? "Technical" : "Non-technical"}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {withTech
            ? "Technical module — this mark stays a draft until you set a technical accuracy score and publish."
            : "Communication / presentation viva — the AI performance score saves automatically."}
          {" "}Chosen before this recording was analyzed; start a new recording to change it.
        </p>
      </div>

      {withTech && technicalAccuracyAI && (
        <div className="mt-4 rounded-lg border border-border p-3">
          <TechnicalAccuracyPanel evaluation={technicalAccuracyAI} />
        </div>
      )}

      {withTech && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm gap-2">
            <div>
              <div className="text-foreground">Technical accuracy</div>
              <div className="text-xs text-muted-foreground">
                {technicalAccuracyAI?.overall_score != null
                  ? "Pre-filled from the AI suggestion above — examiner decides the final score"
                  : "Examiner only — not inferred from video"}
              </div>
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
            disabled={lockedAfterTechPublish}
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
          disabled={lockedAfterTechPublish}
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
                {preview.finalScore != null ? preview.finalScore.toFixed(1) : "—"}
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
            {formatFusionLabel(fusionWeights)}
            {preview.isPreview ? " Preview updates as you move the slider." : ""}
          </p>
        )}
      </div>

      {!withTech && autoPublishedWithoutTech && published ? (
        <div className="w-full mt-4 flex items-center justify-center gap-2 rounded-lg border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="size-4" />
          Score saved automatically
        </div>
      ) : withTech && published ? (
        <div className="w-full mt-4 flex items-center justify-center gap-2 rounded-lg border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="size-4" />
          Assessment published
        </div>
      ) : withTech ? (
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
                Publishes final score {preview.finalScore != null ? preview.finalScore.toFixed(1) : "—"}/100
                (grade {preview.grade ?? "—"}) with your technical accuracy input.
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
      ) : null}
      {!published && !canPublish && !incomplete && !markId && (
        <p className="mt-2 text-xs text-muted-foreground text-center">
          Mark was not saved — check MongoDB connection on the server.
        </p>
      )}
      {!published && withTech && !canPublish && !incomplete && markId && technicalAccuracy == null && (
        <p className="mt-2 text-xs text-muted-foreground text-center">Set technical accuracy to publish.</p>
      )}
    </div>
  );
}
