import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import type { CanonicalTopic } from "../../api/lecturerApi";

interface Props {
  topics: CanonicalTopic[];
  onSelectTopic: (topic: CanonicalTopic) => void;
}

const priorityDot: Record<string, string> = {
  Critical: "bg-red-500", High: "bg-orange-500",
  Medium: "bg-amber-500", Low: "bg-emerald-500",
};

const statusBadge: Record<string, string> = {
  Critical: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  "Needs Improvement": "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  Developing: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

const progressBarColor: Record<string, string> = {
  Critical: "bg-red-500",
  "Needs Improvement": "bg-orange-500",
  Developing: "bg-amber-500",
  Strong: "bg-emerald-500",
};

function getProgressColor(pct: number): string {
  if (pct >= 80) return "bg-emerald-500";
  if (pct >= 60) return "bg-amber-500";
  if (pct >= 40) return "bg-orange-500";
  return "bg-red-500";
}

export function CanonicalTopicTable({ topics, onSelectTopic }: Props) {
  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-3">Topic Performance (Canonical)</h3>
      <div className="space-y-2">
        {topics.map((t) => {
          const barColor = progressBarColor[t.status] || getProgressColor(t.average_percentage);
          return (
            <button
              key={t.topic}
              onClick={() => onSelectTopic(t)}
              className="w-full text-left p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${priorityDot[t.priority] || "bg-gray-400"}`} />
                  <div>
                    <div className="font-medium">{t.topic}</div>
                    <div className="text-xs text-muted-foreground">
                      {t.question_count} questions, {t.student_count} students
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono">{t.average_percentage.toFixed(2)}%</span>
                  <Badge className={statusBadge[t.status] || ""}>{t.status}</Badge>
                </div>
              </div>
              <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ease-out ${barColor}`}
                  style={{ width: `${Math.min(t.average_percentage, 100)}%` }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
