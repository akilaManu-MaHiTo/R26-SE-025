import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";

export interface TopicBloomCell {
  topic: string;
  bloom_level: string;
  average_percentage: number;
  student_count: number;
  attempt_count: number;
  evidence_status: string;
}

interface Props {
  topic_bloom_matrix: TopicBloomCell[];
}

const BLOOM_ORDER = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"] as const;

function cellBg(pct: number): string {
  const intensity = 1 - pct / 100;
  // Use primary hue with opacity = intensity clamped 0..1, plus light fallback
  // intensity 0 (100%) -> very light, intensity 1 (0%) -> strong
  // Map to hsl(var(--primary)) with alpha
  const alpha = Math.max(0.05, Math.min(0.92, intensity * 0.85 + 0.08));
  return `hsl(var(--primary) / ${alpha})`;
}

function evidenceBadgeVariant(status: string): string {
  if (status === "confirmed_weakness") return "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300";
  if (status === "possible_weakness") return "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300";
  if (status === "strength") return "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300";
  return "bg-muted text-muted-foreground";
}

export function TopicBloomHeatmap({ topic_bloom_matrix }: Props) {
  if (!topic_bloom_matrix || topic_bloom_matrix.length === 0) return null;

  const topics = Array.from(new Set(topic_bloom_matrix.map((c) => c.topic))).sort();
  // Keep Bloom order, only include levels present
  const presentBlooms = Array.from(new Set(topic_bloom_matrix.map((c) => c.bloom_level)));
  const bloomLevels = BLOOM_ORDER.filter((b) => presentBlooms.includes(b));
  // Append any unknown levels not in order
  for (const b of presentBlooms) if (!bloomLevels.includes(b as typeof BLOOM_ORDER[number])) bloomLevels.push(b as typeof BLOOM_ORDER[number]);

  const cellMap = new Map<string, TopicBloomCell>();
  for (const c of topic_bloom_matrix) cellMap.set(`${c.topic}|${c.bloom_level}`, c);

  return (
    <Card className="p-5 overflow-x-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Topic × Bloom Heatmap</div>
        <Badge variant="outline" className="text-xs">darker = weaker</Badge>
      </div>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th className="text-left p-2 text-xs text-muted-foreground font-medium border-b">Topic \ Bloom</th>
            {bloomLevels.map((lvl) => (
              <th key={lvl} className="p-2 text-xs font-medium text-center border-b min-w-[90px]">
                {lvl}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {topics.map((topic) => (
            <tr key={topic} className="border-b last:border-0">
              <td className="p-2 font-medium text-xs whitespace-nowrap">{topic}</td>
              {bloomLevels.map((lvl) => {
                const cell = cellMap.get(`${topic}|${lvl}`);
                if (!cell) {
                  return (
                    <td key={lvl} className="p-1 text-center">
                      <div className="rounded-md bg-muted/50 text-muted-foreground text-xs py-3">—</div>
                    </td>
                  );
                }
                const bg = cellBg(cell.average_percentage);
                const textColor = cell.average_percentage < 45 ? "text-white" : "text-foreground";
                // Tooltip content: avg% + n + evidence_status
                const tooltip = `${cell.average_percentage.toFixed(1)}% (n=${cell.student_count}, ${cell.attempt_count} attempts) - ${cell.evidence_status}`;
                const showWeakBadge = cell.evidence_status === "confirmed_weakness" || cell.evidence_status === "possible_weakness";
                return (
                  <td key={lvl} className="p-1">
                    <div
                      title={tooltip}
                      className={`rounded-md px-2 py-3 text-center text-xs font-mono relative ${textColor}`}
                      style={{ background: bg }}
                    >
                      <div>{cell.average_percentage.toFixed(1)}%</div>
                      <div className="text-[10px] opacity-80">n={cell.student_count}</div>
                      {showWeakBadge && (
                        <span className={`absolute -top-1 -right-1 text-[9px] px-1 py-0 rounded ${evidenceBadgeVariant(cell.evidence_status)} border`}>
                          {cell.evidence_status === "confirmed_weakness" ? "weak" : "?"}
                        </span>
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-2 mt-3 text-[10px] text-muted-foreground">
        <span>Low</span>
        <span className="inline-block h-2 w-16 rounded" style={{ background: `linear-gradient(to right, ${cellBg(100)}, ${cellBg(0)})` }} />
        <span>High weakness</span>
      </div>
    </Card>
  );
}
