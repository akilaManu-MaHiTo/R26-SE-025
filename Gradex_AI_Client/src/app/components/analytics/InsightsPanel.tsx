import React from "react";
import { Card } from "../ui/card";
import { TrendingDown, TrendingUp, AlertTriangle, Lightbulb } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

interface Props { insights: string[]; }

const insightConfig = [
  {
    keyword: "weakest",
    icon: TrendingDown,
    bg: "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20",
    iconColor: "text-red-500",
  },
  {
    keyword: "strongest",
    icon: TrendingUp,
    bg: "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20",
    iconColor: "text-emerald-500",
  },
  {
    keyword: "gap",
    icon: AlertTriangle,
    bg: "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20",
    iconColor: "text-amber-500",
  },
];

const getInsightStyle = (text: string) => {
  const lower = text.toLowerCase();
  return insightConfig.find((c) => lower.includes(c.keyword)) || {
    keyword: "default",
    icon: Lightbulb,
    bg: "bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20",
    iconColor: "text-blue-500",
  };
};

export function InsightsPanel({ insights }: Props) {
  if (!insights.length) return null;

  return (
    <Card className="p-5">
      <SectionHeader icon={Lightbulb} title="Key Insights" subtitle="Performance highlights" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {insights.map((insight, i) => {
          const { icon: Icon, bg, iconColor } = getInsightStyle(insight);
          return (
            <div key={i} className={`flex items-start gap-3 p-4 rounded-xl border ${bg}`}>
              <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${iconColor}`} />
              <p className="text-sm leading-relaxed">{insight}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
