import React from "react";
import { Users, TrendingUp, Target, Award, BarChart3 } from "lucide-react";
import { Card } from "../ui/card";

interface KpiCardsProps {
  statistics: {
    total_students: number;
    attempted_students: number;
    average_score: number;
    average_percentage: number;
    pass_rate: number;
    highest_score: number;
    lowest_score: number;
  };
}

const kpis = [
  { key: "total_students", label: "Total Students", icon: Users, suffix: "" },
  { key: "average_score", label: "Average Score", icon: BarChart3, suffix: "" },
  { key: "average_percentage", label: "Average %", icon: TrendingUp, suffix: "%" },
  { key: "pass_rate", label: "Pass Rate", icon: Target, suffix: "%" },
  { key: "highest_score", label: "Highest", icon: Award, suffix: "" },
  { key: "lowest_score", label: "Lowest", icon: TrendingUp, suffix: "" },
] as const;

export function KpiCards({ statistics }: KpiCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {kpis.map(({ key, label, icon: Icon, suffix }) => {
        const value = statistics[key];
        const isRate = key === "pass_rate" || key === "average_percentage";
        return (
          <Card key={key} className="p-5">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <div className="size-10 rounded-lg bg-teal-50 dark:bg-teal-500/10 flex items-center justify-center">
                <Icon className="h-5 w-5 text-teal-600 dark:text-teal-400" />
              </div>
              {label}
            </div>
            <div className="text-2xl font-bold">
              {typeof value === "number" ? value.toFixed(isRate ? 2 : 0) : value}
              {suffix}
            </div>
            {key === "total_students" && (
              <div className="text-xs text-muted-foreground mt-1">
                {statistics.attempted_students} attempted
              </div>
            )}
            {statistics.total_students < 10 && (
              <div className="mt-2 flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                <span title="Based on a small number of responses - interpret with caution">
                  Low sample size (n={statistics.total_students})
                </span>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
