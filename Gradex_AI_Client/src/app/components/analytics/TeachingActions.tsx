import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Lightbulb, Clock } from "lucide-react";

import type { TeachingAction } from "../../api/lecturerApi";

interface Props {
  actions: TeachingAction[];
  loading: boolean;
}

const priorityConfig = [
  { priority: "Critical", color: "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20", iconColor: "text-red-500", textColor: "text-red-800 dark:text-red-300" },
  { priority: "High", color: "bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20", iconColor: "text-orange-500", textColor: "text-orange-800 dark:text-orange-300" },
  { priority: "Medium", color: "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20", iconColor: "text-amber-500", textColor: "text-amber-800 dark:text-amber-300" },
];

const getPriorityConfig = (priority: string) => {
  return priorityConfig.find((p) => p.priority === priority) || priorityConfig[2];
};

const getPerformanceColor = (percentage: number) => {
  if (percentage >= 80) return "bg-emerald-500";
  if (percentage >= 60) return "bg-amber-500";
  return "bg-red-500";
};

export function TeachingActions({ actions, loading }: Props) {
  if (loading) {
    return (
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="font-medium">AI Teaching Recommendations</div>
        </div>
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-28 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      </Card>
    );
  }

  if (!actions.length) return null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">AI Teaching Recommendations</div>
      </div>
      <div className="space-y-4">
        {actions.map((action, i) => {
          const { color, iconColor, textColor } = getPriorityConfig(action.priority);
          return (
            <div key={i} className={`p-4 rounded-xl border ${color}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Lightbulb className={`h-4 w-4 ${iconColor}`} />
                  <span className="font-medium">{action.topic}</span>
                </div>
                <Badge className={`${textColor} border-0 text-xs`}>{action.priority}</Badge>
              </div>
              
              <div className="mb-3">
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                  <span>Performance</span>
                  <span className="font-mono">{action.performance_percentage.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div 
                    className={`h-full ${getPerformanceColor(action.performance_percentage)} rounded-full transition-all`}
                    style={{ width: `${Math.min(action.performance_percentage, 100)}%` }}
                  />
                </div>
              </div>

              <ul className="space-y-1.5 ml-6 mb-3">
                {action.actions.map((a, j) => (
                  <li key={j} className="text-sm text-muted-foreground leading-relaxed list-disc">{a}</li>
                ))}
              </ul>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>Generated {new Date(action.generated_at).toLocaleDateString()}</span>
                </div>
                <Button variant="outline" size="sm" className="text-xs" disabled title="Coming soon">
                  Generate Practice Questions
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
