import { Badge } from "../ui/badge";
import { LlmEvaluation, TranscriptFeatures } from "./types";

interface LlmJudgePanelProps {
  evaluation?: LlmEvaluation;
  transcriptFeatures?: TranscriptFeatures;
}

const CRITERIA: Array<{ key: keyof LlmEvaluation; label: string }> = [
  { key: "communication_clarity", label: "Communication Clarity" },
  { key: "confidence", label: "Confidence" },
  { key: "engagement", label: "Engagement" },
];

export function LlmJudgePanel({ evaluation, transcriptFeatures }: LlmJudgePanelProps) {
  if (!evaluation && !transcriptFeatures) {
    return <p className="text-sm text-muted-foreground">LLM evaluation is not available for this recording.</p>;
  }

  const source = evaluation?.source;
  const isFallback = source === "formula_fallback" || evaluation?.status === "fallback";

  return (
    <div className="space-y-5">
      {evaluation && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="text-sm font-medium text-foreground">Supporting analysis (not the official grade)</div>
            {/* Model name omitted: "did an LLM or the formula produce this"
                changes how an examiner reads the numbers; which LLM does not. */}
            <Badge variant="outline" className="text-xs">
              {isFallback ? "Formula fallback" : "LLM"}
            </Badge>
          </div>
          {isFallback && evaluation.error && (
            <p className="text-xs text-amber-700 dark:text-amber-400">{evaluation.error}</p>
          )}
          <div className="space-y-3">
            {CRITERIA.map(({ key, label }) => {
              const item = evaluation[key];
              if (!item || typeof item !== "object" || !("score" in item)) return null;
              const score = item as { score: number; justification: string };
              return (
                <div key={key} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">{label}</div>
                    <div className="text-sm font-semibold text-foreground">
                      {score.score.toFixed(1)}
                      <span className="text-xs font-normal text-muted-foreground"> / 10</span>
                    </div>
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{score.justification}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {transcriptFeatures && (
        <div className="space-y-3">
          <div className="text-sm font-medium text-foreground">Transcript quality signals</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            <Metric label="Hedge phrases" value={String(transcriptFeatures.hedge_count ?? 0)} />
            <Metric label="Fillers" value={String(transcriptFeatures.filler_count ?? 0)} />
            <Metric
              label="Speech rate"
              value={
                transcriptFeatures.speech_rate_wpm != null
                  ? `${transcriptFeatures.speech_rate_wpm.toFixed(0)} WPM`
                  : "—"
              }
            />
            <Metric label="Rate band" value={formatBand(transcriptFeatures.speech_rate_band)} />
            <Metric label="Pauses >0.5s" value={String(transcriptFeatures.pause_count ?? 0)} />
            <Metric label="Long pauses >2s" value={String(transcriptFeatures.long_pause_count ?? 0)} />
          </div>
          {transcriptFeatures.sentence_completion_ratio != null && (
            <p className="text-xs text-muted-foreground">
              Sentence completion ratio {Math.round(transcriptFeatures.sentence_completion_ratio * 100)}%
              {transcriptFeatures.sentence_completion_is_heuristic ? " (heuristic)" : ""}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/40 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function formatBand(band?: string | null): string {
  if (!band) return "—";
  return band.replace(/_/g, " ");
}
