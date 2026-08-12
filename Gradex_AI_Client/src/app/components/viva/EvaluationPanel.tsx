import { useMemo, useState } from "react";
import { CheckCircle2, Lock, PenLine } from "lucide-react";
import { Slider } from "../ui/slider";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
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
import { GRADE_BANDS, RubricCriterion, suggestGrade } from "./types";

interface EvaluationPanelProps {
  criteria: RubricCriterion[];
  onChangeCriteria: (criteria: RubricCriterion[]) => void;
  aiRecommendation: string;
  finalGrade: string;
  onChangeFinalGrade: (grade: string) => void;
  published: boolean;
  onPublish: () => void;
}

export function EvaluationPanel({
  criteria,
  onChangeCriteria,
  aiRecommendation,
  finalGrade,
  onChangeFinalGrade,
  published,
  onPublish,
}: EvaluationPanelProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const total = useMemo(() => criteria.reduce((sum, c) => sum + c.score, 0), [criteria]);
  const max = useMemo(() => criteria.reduce((sum, c) => sum + c.max, 0), [criteria]);
  const suggested = suggestGrade(total, max);
  const allScored = criteria.every((c) => c.score > 0);

  const updateScore = (id: string, score: number) => {
    onChangeCriteria(criteria.map((c) => (c.id === id ? { ...c, score } : c)));
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-foreground">Evaluation</div>
        <Badge variant="outline" className="gap-1 text-xs">
          <PenLine className="size-3" /> Evaluator-entered
        </Badge>
      </div>

      <div className="mt-4 space-y-5">
        {criteria.map((c) => (
          <div key={c.id}>
            <div className="flex items-center justify-between text-sm gap-2">
              <div>
                <div className="text-foreground">{c.name}</div>
                <div className="text-xs text-muted-foreground">{c.description}</div>
              </div>
              <span className="text-foreground font-medium shrink-0">
                {c.score} / {c.max}
              </span>
            </div>
            <Slider
              className="mt-2"
              value={[c.score]}
              min={0}
              max={c.max}
              step={1}
              disabled={published}
              onValueChange={([v]) => updateScore(c.id, v)}
              aria-label={c.name}
            />
          </div>
        ))}
      </div>

      <div className="mt-5 pt-4 border-t border-border">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Total (calculated)</div>
            <div className="tracking-tight text-foreground mt-0.5">
              <span className="text-3xl font-semibold">{total}</span>
              <span className="text-muted-foreground">/{max}</span>
            </div>
          </div>
          <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border-0">
            Suggested: {suggested}
          </Badge>
        </div>
      </div>

      <div className="mt-4 p-3 rounded-lg bg-primary/5 border border-primary/10 text-xs text-foreground/90">
        <span className="font-medium text-foreground">AI recommendation: </span>
        {aiRecommendation}
      </div>

      <div className="mt-4">
        <label className="text-sm text-foreground" htmlFor="viva-final-grade">
          Final grade
        </label>
        <Select value={finalGrade} onValueChange={onChangeFinalGrade} disabled={published}>
          <SelectTrigger className="mt-1.5" id="viva-final-grade">
            <SelectValue placeholder="Select grade" />
          </SelectTrigger>
          <SelectContent>
            {GRADE_BANDS.map((b) => (
              <SelectItem key={b.grade} value={b.grade}>
                {b.grade}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
            disabled={!allScored}
            onClick={() => setConfirmOpen(true)}
          >
            <Lock className="size-4" />
            Save & publish
          </Button>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Publish this assessment?</AlertDialogTitle>
              <AlertDialogDescription>
                Publishing finalizes the score ({total}/{max}, grade {finalGrade}) and locks the rubric from
                further edits. This action cannot be undone in this session.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
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
      {!published && !allScored && (
        <p className="mt-2 text-xs text-muted-foreground text-center">Score every criterion to publish.</p>
      )}
    </div>
  );
}
