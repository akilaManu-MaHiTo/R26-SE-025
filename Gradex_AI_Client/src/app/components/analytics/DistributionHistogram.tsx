import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

interface Statistics {
  total_students: number;
  attempted_students: number;
  average_score: number;
  average_percentage: number;
  pass_rate: number;
  highest_score: number;
  lowest_score: number;
  median_score?: number;
  median_percentage?: number;
  std_score?: number;
  std_percentage?: number;
  iqr_percentage?: number;
  grade_distribution?: Record<string, number>;
}

interface Props {
  statistics: Statistics;
}

const BINS: { label: string; grade: string; key: string }[] = [
  { label: "0-40", grade: "F", key: "F" },
  { label: "40-50", grade: "D", key: "D" },
  { label: "50-65", grade: "C", key: "C" },
  { label: "65-80", grade: "B", key: "B" },
  { label: "80-100", grade: "A", key: "A" },
];

const BIN_COLORS: Record<string, string> = {
  F: "hsl(var(--destructive))",
  D: "#f97316",
  C: "#eab308",
  B: "hsl(var(--primary) / 0.7)",
  A: "hsl(var(--primary))",
};

function medianBinLabel(median?: number): string | null {
  if (median == null || Number.isNaN(median)) return null;
  for (const b of BINS) {
    const [lo, hi] = b.label.split("-").map(Number);
    // first bin includes 0, last includes 100
    if (median >= lo && median <= hi) return `${b.label} (${b.grade})`;
    // edge: 40 boundary belongs to D per spec (0-40 F exclusive upper? we map inclusive lower)
  }
  // fallback clamp
  if (median < 0) return `${BINS[0].label} (${BINS[0].grade})`;
  if (median > 100) return `${BINS[BINS.length - 1].label} (${BINS[BINS.length - 1].grade})`;
  return null;
}

export function DistributionHistogram({ statistics }: Props) {
  const gradeDist = statistics.grade_distribution ?? { A: 0, B: 0, C: 0, D: 0, F: 0 };
  const data = BINS.map((b) => ({
    bin: `${b.label} (${b.grade})`,
    count: Number(gradeDist[b.key] ?? 0),
    grade: b.grade,
  }));

  const total = data.reduce((s, d) => s + d.count, 0);
  const median = statistics.median_percentage;
  const medianLabel = medianBinLabel(median);

  if (total === 0 && !median) {
    return (
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="font-medium">Score Distribution</div>
          {median != null && <Badge variant="outline" className="text-xs">Median {median.toFixed(1)}%</Badge>}
        </div>
        <div className="text-sm text-muted-foreground py-8 text-center">No distribution data</div>
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Score Distribution</div>
        <div className="flex items-center gap-2">
          {median != null && (
            <Badge variant="outline" className="text-xs">Median {median.toFixed(1)}%</Badge>
          )}
          <Badge variant="secondary" className="text-xs">n={statistics.total_students}</Badge>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bin" tick={{ fontSize: 11 }} interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => [`${v} students`, "Count"]} labelFormatter={(l) => `Bin ${l}`} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={BIN_COLORS[entry.grade] ?? "hsl(var(--primary))"} />
            ))}
          </Bar>
          {medianLabel && <ReferenceLine x={medianLabel} stroke="hsl(var(--primary))" strokeDasharray="4 4" label={{ value: `median ${median?.toFixed(0)}%`, position: "top", fontSize: 10, fill: "hsl(var(--primary))" }} />}
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-2 mt-2 flex-wrap">
        {BINS.map((b) => (
          <span key={b.key} className="text-[10px] text-muted-foreground flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: BIN_COLORS[b.grade] }} />
            {b.label}={b.grade}
          </span>
        ))}
      </div>
    </Card>
  );
}
