import React from "react";
import { Card } from "../ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { BarChart3 } from "lucide-react";

interface Props {
  bloomPerformance: { level: string; average_percentage: number }[];
}

const PULSE_COLORS = [
  "#0d9488",
  "#14b8a6",
  "#2dd4bf",
  "#5eead4",
  "#99f6e4",
  "#ccfbf1",
];

export function BloomChart({ bloomPerformance }: Props) {
  if (!bloomPerformance.length) return null;

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-1">
        <div className="size-8 rounded-lg bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
          <BarChart3 className="h-4 w-4 text-teal-600 dark:text-teal-400" />
        </div>
        <h3 className="text-lg font-semibold">Bloom's Taxonomy</h3>
      </div>
      <p className="text-xs text-muted-foreground mb-3">
        Only {bloomPerformance.map((b) => b.level).join(", ")} levels were assessed in this exam.
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={bloomPerformance} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="level" width={80} />
          <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
          <Bar dataKey="average_percentage" radius={[0, 4, 4, 0]}>
            {bloomPerformance.map((_, i) => (
              <Cell key={i} fill={PULSE_COLORS[i % PULSE_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
