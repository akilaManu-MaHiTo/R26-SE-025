import React from "react";
import { Card } from "../ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props {
  bloomPerformance: { level: string; average_percentage: number }[];
}

const COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary)/0.8)",
  "hsl(var(--primary)/0.6)",
  "hsl(var(--primary)/0.4)",
  "hsl(var(--primary)/0.3)",
  "hsl(var(--primary)/0.2)",
];

export function BloomChart({ bloomPerformance }: Props) {
  if (!bloomPerformance.length) return null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Cognitive Analysis</div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={bloomPerformance} layout="vertical" margin={{ left: 20, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="level" width={80} />
          <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
          <Bar dataKey="average_percentage" radius={[0, 4, 4, 0]}>
            {bloomPerformance.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
