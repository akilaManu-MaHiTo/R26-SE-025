import React, { useState } from "react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { CanonicalAttentionArea } from "../../api/lecturerApi";

interface Props { areas: CanonicalAttentionArea[]; }

const priorityOrder = ["Critical", "High", "Medium"];
const priorityColor: Record<string, string> = {
  Critical: "text-red-600 dark:text-red-400",
  High: "text-orange-600 dark:text-orange-400",
  Medium: "text-amber-600 dark:text-amber-400",
};

export function AttentionAreasPanel({ areas }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const grouped = priorityOrder.map((p) => ({
    priority: p,
    items: areas.filter((a) => a.priority === p),
  }));

  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-3">Attention Areas</h3>
      {grouped.map(({ priority, items }) => (
        <div key={priority} className="mb-3">
          <div className={`text-sm font-medium mb-1 ${priorityColor[priority] || ""}`}>
            {priority} Priority
          </div>
          {items.length === 0 ? (
            <div className="text-xs text-muted-foreground italic">No {priority.toLowerCase()} areas</div>
          ) : (
            <>
              {items.slice(0, expanded[priority] ? items.length : 2).map((a) => (
                <div key={a.name} className="flex items-center justify-between py-1.5 text-sm">
                  <span>{a.name}</span>
                  <span className="font-mono text-xs">{a.average_percentage.toFixed(2)}%</span>
                </div>
              ))}
              {items.length > 2 && (
                <Button
                  variant="ghost" size="sm" className="text-xs h-6"
                  onClick={() => setExpanded((prev) => ({ ...prev, [priority]: !prev[priority] }))}
                >
                  {expanded[priority] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  {expanded[priority] ? "Show less" : `View all (${items.length})`}
                </Button>
              )}
            </>
          )}
        </div>
      ))}
    </Card>
  );
}
