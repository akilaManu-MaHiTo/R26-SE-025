import React from "react";
import { Card } from "../ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props {
  bloomPerformance: { level: string; average_percentage: number }[];
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export function BloomChart({ bloomPerformance }: Props) {
  if (!bloomPerformance.length) return null;

  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-1">Bloom's Taxonomy</h3>
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
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
