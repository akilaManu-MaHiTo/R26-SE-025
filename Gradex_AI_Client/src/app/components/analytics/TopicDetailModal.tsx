import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { X } from "lucide-react";
import type { CanonicalTopic } from "../../api/lecturerApi";

interface Props {
  topic: CanonicalTopic | null;
  open: boolean;
  onClose: () => void;
}

export function TopicDetailModal({ topic, open, onClose }: Props) {
  if (!open || !topic) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-background rounded-lg shadow-lg max-w-lg w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{topic.topic}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">Average</div>
              <div className="text-2xl font-bold">{topic.average_percentage.toFixed(2)}%</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Status</div>
              <Badge className="mt-1">{topic.status}</Badge>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Priority</div>
              <Badge className="mt-1">{topic.priority}</Badge>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Sample Size</div>
              <div className="text-sm">{topic.question_count} questions, {topic.student_count} students</div>
            </div>
          </div>

          {topic.contributing_fragments.length > 1 && (
            <div>
              <div className="text-sm font-medium mb-1">Contributing Fragments (merged)</div>
              <ul className="list-disc list-inside text-sm text-muted-foreground">
                {topic.contributing_fragments.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {topic.is_estimated && (
            <div className="text-xs text-amber-600 dark:text-amber-400">
              This value is estimated from weighted fragment averages.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
