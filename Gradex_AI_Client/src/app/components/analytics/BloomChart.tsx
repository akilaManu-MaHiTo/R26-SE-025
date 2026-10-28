import React, { useState } from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";

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
  const [view, setView] = useState<"radar" | "bar">("radar");
  const bloomMap = new Map(bloomPerformance.map((b) => [b.level, b]));
  const unassessed = BLOOM_ORDER.filter((level) => !bloomMap.has(level));
  const data = BLOOM_ORDER.map((level) => {
    const found = bloomMap.get(level);
    if (found) return found;
    return { level, average_percentage: null };
  });

  const hasInsufficient = bloomPerformance.some((b) => b.evidence_status === "insufficient_evidence");
  const hasWeak = bloomPerformance.some((b) => b.evidence_status === "confirmed_weakness" || b.evidence_status === "possible_weakness");

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div className="font-medium">Cognitive Analysis</div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {BLOOM_ORDER.length - unassessed.length} of 6 levels assessed
          </Badge>
          {hasInsufficient && (
            <Badge variant="outline" className="text-xs bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200">
              Limited evidence for assessed levels
            </Badge>
          )}
          {hasWeak && (
            <Badge variant="outline" className="text-xs bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300 border-red-200">
              weak
            </Badge>
          )}
          <div className="ml-2 flex rounded-md border p-0.5 bg-muted/30">
            <Button variant={view === "radar" ? "secondary" : "ghost"} size="sm" className="h-6 px-2 text-xs" onClick={() => setView("radar")}>Radar</Button>
            <Button variant={view === "bar" ? "secondary" : "ghost"} size="sm" className="h-6 px-2 text-xs" onClick={() => setView("bar")}>Bar</Button>
          </div>
        </div>
      </div>
      {unassessed.length === BLOOM_ORDER.length ? (
        <p className="text-sm text-muted-foreground text-center py-12">No cognitive assessment results available yet.</p>
      ) : view === "radar" ? (
        <ResponsiveContainer width="100%" height={300}>
          <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke="hsl(var(--border))" />
            <PolarAngleAxis dataKey="level" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} tickCount={5} />
            <Radar dataKey="average_percentage" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / 0.35)" strokeWidth={2} dot={{ r: 3, fill: "hsl(var(--primary))" }} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
          </RadarChart>
        </ResponsiveContainer>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20, top: 5, bottom: 5 }} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
            <YAxis type="category" dataKey="level" width={85} tick={{ fontSize: 12 }} interval={0} />
            <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} cursor={{ fill: "hsl(var(--muted)/0.4)" }} />
            <Bar dataKey="average_percentage" radius={[0, 4, 4, 0]} barSize={22}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
      {unassessed.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">Not assessed: {unassessed.join(", ")}.</p>
      )}
      <div className="text-[10px] text-muted-foreground mt-1 text-center">0% is an assessed score; unassessed levels have no score.</div>
    </Card>
  );
}
