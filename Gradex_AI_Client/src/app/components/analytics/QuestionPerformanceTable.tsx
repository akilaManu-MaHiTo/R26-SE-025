import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { AlertTriangle, FileQuestion } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

interface Question {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: string;
  average_percentage: number;
}

interface Props {
  questions: Question[];
  onSelectQuestion: (q: Question) => void;
}

export function QuestionPerformanceTable({ questions, onSelectQuestion }: Props) {
  if (!questions.length) return null;

  const lowestId = questions.reduce((min, q) =>
    q.average_percentage < min.average_percentage ? q : min
  ).question_id;

  return (
    <Card className="p-5">
      <SectionHeader icon={FileQuestion} title="Question Performance" subtitle="Individual question analysis" />
      <div className="space-y-3">
        {questions.map((q) => {
          const isLowest = q.question_id === lowestId;
          const status = q.average_percentage >= 75 ? "Strong"
            : q.average_percentage >= 60 ? "Developing"
            : q.average_percentage >= 40 ? "Needs Improvement"
            : "Critical";

          return (
            <button
              key={q.question_id}
              onClick={() => onSelectQuestion(q)}
              className="w-full text-left p-4 rounded-xl border bg-card hover:bg-accent/50 transition-all hover:shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{q.question_id}</span>
                  {isLowest && (
                    <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0 text-xs">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Lowest
                    </Badge>
                  )}
                </div>
                <span className="text-sm font-mono font-semibold">{q.average_percentage.toFixed(1)}%</span>
              </div>
              <div className="text-xs text-muted-foreground mb-2">
                {q.topic} · {q.bloom_level}
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    isLowest ? "bg-amber-500" : status === "Strong" ? "bg-emerald-500" : status === "Developing" ? "bg-amber-500" : "bg-orange-500"
                  }`}
                  style={{ width: `${Math.min(q.average_percentage, 100)}%` }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
