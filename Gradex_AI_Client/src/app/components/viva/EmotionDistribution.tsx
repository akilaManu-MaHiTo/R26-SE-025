import { EmotionSummary } from "./types";

interface EmotionDistributionProps {
  summary: EmotionSummary;
}

const ROWS: Array<{ key: keyof EmotionSummary; label: string; barClass: string }> = [
  { key: "positive_ratio", label: "Positive", barClass: "bg-emerald-500" },
  { key: "neutral_ratio", label: "Neutral", barClass: "bg-blue-500" },
  { key: "negative_ratio", label: "Negative", barClass: "bg-red-500" },
];

export function EmotionDistribution({ summary }: EmotionDistributionProps) {
  return (
    <div className="space-y-2.5">
      {ROWS.map((row) => {
        const ratio = summary[row.key] ?? 0;
        return (
          <div key={row.key} className="flex items-center gap-3">
            <div className="text-xs text-muted-foreground w-16 shrink-0">{row.label}</div>
            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
              <div className={`h-full ${row.barClass}`} style={{ width: `${Math.round(ratio * 100)}%` }} />
            </div>
            <div className="text-xs font-medium text-foreground w-10 text-right shrink-0">
              {Math.round(ratio * 100)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}
