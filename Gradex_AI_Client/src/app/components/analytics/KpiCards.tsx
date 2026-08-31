import React from "react";
import { Users, TrendingUp, Target, Award, BarChart3, Sigma, Activity, Scale } from "lucide-react";
import { Card } from "../ui/card";

const GRADE_COLORS: Record<string, string> = {
  A: "#22c55e",
  B: "#3b82f6",
  C: "#eab308",
  D: "#f97316",
  F: "#ef4444",
};

interface KpiCardsProps {
  statistics: {
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
  };
}

const kpis = [
  { key: "total_students", label: "Total Students", icon: Users, suffix: "" },
  { key: "average_score", label: "Average Score", icon: BarChart3, suffix: "" },
  { key: "average_percentage", label: "Average %", icon: TrendingUp, suffix: "%" },
  { key: "pass_rate", label: "Pass Rate", icon: Target, suffix: "%" },
  { key: "highest_score", label: "Highest", icon: Award, suffix: "" },
  { key: "lowest_score", label: "Lowest", icon: TrendingUp, suffix: "" },
  { key: "median_percentage", label: "Median", icon: Scale, suffix: "%" },
  { key: "std_percentage", label: "Std Dev", icon: Activity, suffix: "%" },
  { key: "iqr_percentage", label: "IQR", icon: Sigma, suffix: "%" },
] as const;

export function KpiCards({ statistics }: KpiCardsProps) {
  const showSampleWarning = statistics.total_students < 10;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="font-medium">Performance Overview</div>
        {showSampleWarning && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
            <span title="Based on a small number of responses - interpret with caution">
              Low sample size (n={statistics.total_students})
            </span>
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
        {kpis.map(({ key, label, icon: Icon, suffix }) => {
          const value = (statistics as Record<string, unknown>)[key] as number | undefined;
          const isRate = key === "pass_rate" || key === "average_percentage" || key === "median_percentage" || key === "std_percentage" || key === "iqr_percentage";
          return (
            <Card key={key} className="p-5">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                <div className="size-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                  <Icon className="size-5" />
                </div>
                {label}
              </div>
              <div className="text-2xl font-bold">
                {typeof value === "number" ? value.toFixed(isRate ? 2 : 0) : value ?? "—"}
                {typeof value === "number" ? suffix : ""}
              </div>
              {key === "total_students" && (
                <div className="text-xs text-muted-foreground mt-1">
                  {statistics.attempted_students} attempted
                </div>
              )}
            </Card>
          );
        })}
      </div>
      {statistics.grade_distribution && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Grade distribution:</span>
          {Object.entries(statistics.grade_distribution).map(([grade, count]) => (
            <span
              key={grade}
              className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full"
              style={{ backgroundColor: GRADE_COLORS[grade] ?? "#3b82f6", color: "#fff" }}
            >
              {grade}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
