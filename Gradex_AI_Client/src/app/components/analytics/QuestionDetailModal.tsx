import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { X, Lock } from "lucide-react";

interface Question {
  question_id: string;
  question_no: string;
  topic: string;
  bloom_level: string;
  average_percentage: number;
}

interface Props {
  question: Question | null;
  open: boolean;
  onClose: () => void;
}

export function QuestionDetailModal({ question, open, onClose }: Props) {
  if (!open || !question) return null;

  const status = question.average_percentage >= 75 ? "Strong"
    : question.average_percentage >= 60 ? "Developing"
    : question.average_percentage >= 40 ? "Needs Improvement"
    : "Critical";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-background rounded-lg shadow-lg max-w-lg w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{question.question_id}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">Class Average</div>
              <div className="text-2xl font-bold">{question.average_percentage.toFixed(2)}%</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Status</div>
              <Badge className="mt-1">{status}</Badge>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Topic</div>
              <div className="text-sm">{question.topic}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Bloom Level</div>
              <div className="text-sm">{question.bloom_level}</div>
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t">
            <Button variant="outline" size="sm" className="w-full justify-start" disabled>
              <Lock className="h-4 w-4 mr-2" />
              View Mark Distribution
              <span className="ml-auto text-xs text-muted-foreground">Requires additional data</span>
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start" disabled>
              <Lock className="h-4 w-4 mr-2" />
              View Question Text
              <span className="ml-auto text-xs text-muted-foreground">Requires additional data</span>
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start" disabled>
              <Lock className="h-4 w-4 mr-2" />
              View Student Responses
              <span className="ml-auto text-xs text-muted-foreground">Requires additional data</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
