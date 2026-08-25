import { Badge } from "../ui/badge";
import { TechnicalAccuracyAI } from "./types";

interface TechnicalAccuracyPanelProps {
  evaluation?: TechnicalAccuracyAI;
}

/**
 * Advisory panel showing the AI's suggested technical-accuracy score and its
 * per-concept evidence, computed against a lecturer-uploaded subject rubric
 * (see /api/subject-content). This never publishes anything itself — it is
 * shown next to the examiner's own "Technical Knowledge" slider in
 * EvaluationPanel.tsx, which pre-fills from overall_score but stays editable.
 */
export function TechnicalAccuracyPanel({ evaluation }: TechnicalAccuracyPanelProps) {
  if (!evaluation || evaluation.status === "skipped") {
    return (
      <p className="text-sm text-muted-foreground">
        {evaluation?.error ??
          "No subject content was linked to this viva, so no AI technical-accuracy suggestion is available."}
      </p>
    );
  }

  if (evaluation.status === "unavailable") {
    return (
      <p className="text-sm text-amber-700 dark:text-amber-400">
        {evaluation.error ?? "AI technical-accuracy scoring was unavailable for this recording."}
      </p>
    );
  }

  const concepts = evaluation.concepts ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="text-sm font-medium text-foreground">AI-suggested technical accuracy</div>
        <Badge variant="outline" className="text-xs">
          {evaluation.model ? `LLM · ${evaluation.model}` : "LLM"}
        </Badge>
        {evaluation.status === "partial" && (
          <Badge variant="outline" className="text-xs text-amber-700 dark:text-amber-400">
            Partial
          </Badge>
        )}
      </div>
      {evaluation.overall_score != null && (
        <div className="text-sm font-semibold text-foreground">
          {evaluation.overall_score.toFixed(1)}
          <span className="text-xs font-normal text-muted-foreground"> / 10 — suggestion only, review before publishing</span>
        </div>
      )}
      {evaluation.error && <p className="text-xs text-amber-700 dark:text-amber-400">{evaluation.error}</p>}

      <div className="space-y-2">
        {concepts.map((concept) => (
          <div key={concept.concept_id} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-foreground">{concept.name}</div>
              <div className="flex items-center gap-1.5">
                <Badge variant={concept.covered ? "default" : "outline"} className="text-xs">
                  {concept.covered ? "Covered" : "Not covered"}
                </Badge>
                {concept.covered && concept.correct != null && (
                  <Badge
                    variant={concept.correct ? "default" : "outline"}
                    className={concept.correct ? "text-xs" : "text-xs text-red-700 dark:text-red-400"}
                  >
                    {concept.correct ? "Correct" : "Incorrect"}
                  </Badge>
                )}
              </div>
            </div>
            {concept.evidence_quote && (
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">"{concept.evidence_quote}"</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
