import React, { useState } from "react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { CanonicalAttentionArea } from "../../api/lecturerApi";
import { Badge } from "../ui/badge";


interface Props { areas: CanonicalAttentionArea[]; }

const priorityConfig = [
  { priority: "Critical", badge: "destructive" },
  { priority: "High", badge: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300" },
  { priority: "Medium", badge: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
];

export function AttentionAreasPanel({ areas }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="font-medium">Needs Attention</div>
      </div>
      <div className="space-y-4">
        {priorityConfig.map(({ priority, badge }) => {
          const items = areas.filter((a) => a.priority === priority);
          const isExpanded = expanded[priority];

          const badgeProps = ["destructive", "secondary", "default", "outline"].includes(badge)
            ? { variant: badge }
            : { className: badge };

          return (
            <div key={priority} className="p-3">
              <div className="flex items-center justify-between mb-2">
                <Badge {...badgeProps}>{priority} Priority</Badge>
                {items.length > 0 && (
                  <span className="text-xs text-muted-foreground">{items.length} items</span>
                )}
              </div>

              {items.length === 0 ? (
                <div className="text-xs text-muted-foreground italic py-1">
                  No {priority.toLowerCase()} areas
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    {(isExpanded ? items : items.slice(0, 2)).map((a) => (
                      <div key={a.name} className="flex items-center justify-between text-sm">
                        <span>{a.name}</span>
                        <span className="font-mono font-semibold">{a.average_percentage.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                  {items.length > 2 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-6 mt-2"
                      onClick={() => setExpanded((prev) => ({ ...prev, [priority]: !prev[priority] }))}
                    >
                      {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      {isExpanded ? "Show less" : `View all (${items.length})`}
                    </Button>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
