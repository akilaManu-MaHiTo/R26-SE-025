import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Sparkles, Lightbulb } from "lucide-react";
import type { TeachingAction } from "../../api/lecturerApi";

interface Props {
  actions: TeachingAction[];
  loading: boolean;
}

const priorityColor: Record<string, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  High: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
};

export function TeachingActions({ actions, loading }: Props) {
  if (loading) {
    return (
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-3">Recommended Teaching Actions</h3>
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
      </Card>
    );
  }

  if (!actions.length) return null;

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-lg font-semibold">Recommended Teaching Actions</h3>
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300 border-0 text-xs">
          <Sparkles className="h-3 w-3 mr-1" />
          AI Generated
        </Badge>
      </div>
      <div className="space-y-3">
        {actions.map((action, i) => (
          <div key={i} className="p-3 rounded-lg border bg-card">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500" />
                <span className="font-medium">{action.topic}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{action.performance_percentage.toFixed(2)}%</span>
                <Badge className={priorityColor[action.priority] || ""}>{action.priority}</Badge>
              </div>
            </div>
            <ul className="space-y-1 ml-6">
              {action.actions.map((a, j) => (
                <li key={j} className="text-sm text-muted-foreground list-disc">{a}</li>
              ))}
            </ul>
            <Button variant="outline" size="sm" className="mt-2 text-xs" disabled title="Coming soon">
              Generate Practice Questions
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}
