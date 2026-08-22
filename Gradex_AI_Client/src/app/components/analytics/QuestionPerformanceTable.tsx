import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { AlertTriangle } from "lucide-react";

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
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-3">Question Performance</h3>
      <div className="space-y-2">
        {questions.map((q) => {
          const isLowest = q.question_id === lowestId;
          return (
            <button
              key={q.question_id}
              onClick={() => onSelectQuestion(q)}
              className="w-full text-left p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{q.question_id}</span>
                  {isLowest && (
                    <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 border-0 text-xs">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Lowest
                    </Badge>
                  )}
                </div>
                <span className="font-mono text-sm">{q.average_percentage.toFixed(2)}%</span>
              </div>
              <div className="text-xs text-muted-foreground">{q.topic} · {q.bloom_level}</div>
              <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${q.average_percentage}%`,
                    backgroundColor: isLowest ? "#f59e0b" : "#3b82f6",
                  }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
