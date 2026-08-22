import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import type { CopilotAnalysis, CopilotSuggestion } from "./copilotApi";

interface SuggestionPanelProps {
  suggestions: CopilotSuggestion[];
  analysis?: CopilotAnalysis | null;
  currentQuestion?: string | null;
  onAsk: (question: string) => void;
  disabled?: boolean;
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-rose-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-slate-500 text-white",
};

export function SuggestionPanel({
  suggestions,
  analysis,
  currentQuestion,
  onAsk,
  disabled = false,
}: SuggestionPanelProps) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <div className="text-sm font-medium text-foreground">AI Follow-up Suggestions</div>
        <p className="text-xs text-muted-foreground mt-1">
            Suggestions appear as the student presents. The AI never asks — the panel chooses.
        </p>
      </div>

      {currentQuestion ? (
        <div className="px-4 py-2.5 bg-primary/5 border-b border-border text-xs">
          <span className="text-muted-foreground">Current question: </span>
          <span className="text-foreground">{currentQuestion}</span>
        </div>
      ) : null}

      <div className="divide-y divide-border">
        {suggestions.length === 0 ? (
          <div className="px-4 py-8 text-sm text-muted-foreground">
            Suggestions appear as the student presents, and after each answer.
          </div>
        ) : (
          suggestions.map((item, index) => (
            <div key={`${item.question || "q"}-${index}`} className="px-4 py-4 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.medium}`}>
                  {item.priority}
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {item.difficulty}
                </span>
              </div>
              <p className="text-sm text-foreground leading-snug">{item.question}</p>
              <p className="text-xs text-muted-foreground">Why: {item.reason}</p>
              <Button size="sm" type="button" disabled={disabled} onClick={() => onAsk(item.question)}>
                Ask this
              </Button>
            </div>
          ))
        )}
      </div>

      {analysis && ((analysis.topics?.length ?? 0) > 0 || (analysis.gaps?.length ?? 0) > 0) ? (
        <div className="px-4 py-3 border-t border-border space-y-2">
          {(analysis.topics ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(analysis.topics ?? []).map((topic) => (
                <Badge key={topic} variant="secondary">
                  {topic}
                </Badge>
              ))}
            </div>
          )}
          {(analysis.gaps ?? []).length > 0 && (
            <p className="text-xs text-muted-foreground">Gaps: {(analysis.gaps ?? []).join(", ")}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
