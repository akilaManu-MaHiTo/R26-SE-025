import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props {
  bloomPerformance: { level: string; average_percentage: number; evidence_status?: string; student_count?: number }[];
}

const COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary)/0.8)",
  "hsl(var(--primary)/0.6)",
  "hsl(var(--primary)/0.4)",
  "hsl(var(--primary)/0.3)",
  "hsl(var(--primary)/0.2)",
];

const BLOOM_ORDER = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"] as const;

export function BloomChart({ bloomPerformance }: Props) {
  // Show all 6 levels; missing ones as 0% (insufficient_evidence) per request
  const bloomMap = new Map(bloomPerformance.map((b) => [b.level, b]));
  const data = BLOOM_ORDER.map((level) => {
    const found = bloomMap.get(level);
    if (found) return found;
    return { level, average_percentage: 0, evidence_status: "insufficient_evidence", student_count: 0 } as Props["bloomPerformance"][number];
  });

  const hasInsufficient = data.some((b) => b.evidence_status === "insufficient_evidence");
  const hasWeak = data.some((b) => b.evidence_status === "confirmed_weakness" || b.evidence_status === "possible_weakness");

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Cognitive Analysis</div>
        <div className="flex items-center gap-2">
          {hasInsufficient && (
            <Badge variant="outline" className="text-xs bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200">
              insufficient evidence
            </Badge>
          )}
          {hasWeak && !hasInsufficient && (
            <Badge variant="outline" className="text-xs bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-red-200">
              weak
            </Badge>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="level" width={80} />
          <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
          <Bar dataKey="average_percentage" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
