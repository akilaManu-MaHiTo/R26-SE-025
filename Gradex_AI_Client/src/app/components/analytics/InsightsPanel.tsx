import React from "react";
import { Card } from "../ui/card";
import { TrendingDown, TrendingUp, AlertTriangle } from "lucide-react";

interface Props { insights: string[]; }

const insightStyle = (text: string) => {
  if (text.toLowerCase().includes("weakest")) return {
    icon: TrendingDown,
    bg: "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20",
    iconColor: "text-red-500",
  };
  if (text.toLowerCase().includes("strongest")) return {
    icon: TrendingUp,
    bg: "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20",
    iconColor: "text-emerald-500",
  };
  return {
    icon: AlertTriangle,
    bg: "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20",
    iconColor: "text-amber-500",
  };
};

export function InsightsPanel({ insights }: Props) {
  if (!insights.length) return null;
  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-3">Key Insights</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {insights.map((insight, i) => {
          const { icon: Icon, bg, iconColor } = insightStyle(insight);
          return (
            <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${bg}`}>
              <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${iconColor}`} />
              <p className="text-sm">{insight}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
