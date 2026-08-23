import React from "react";
import { Card } from "../ui/card";
import { TrendingDown, TrendingUp, AlertTriangle, Lightbulb } from "lucide-react";

interface Props { insights: string[]; }

const insightConfig = [
  {
    keyword: "weakest",
    icon: TrendingDown,
    bg: "bg-muted",
    iconColor: "text-red-500",
  },
  {
    keyword: "strongest",
    icon: TrendingUp,
    bg: "bg-muted",
    iconColor: "text-emerald-500",
  },
  {
    keyword: "gap",
    icon: AlertTriangle,
    bg: "bg-muted",
    iconColor: "text-amber-500",
  },
];

const getInsightStyle = (text: string) => {
  const lower = text.toLowerCase();
  return insightConfig.find((c) => lower.includes(c.keyword)) || {
    keyword: "default",
    icon: Lightbulb,
    bg: "bg-muted",
    iconColor: "text-blue-500",
  };
};

export function InsightsPanel({ insights }: Props) {
  if (!insights.length) return null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Insights</div>
      </div>
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
