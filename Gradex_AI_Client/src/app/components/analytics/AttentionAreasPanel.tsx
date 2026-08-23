import React, { useState } from "react";
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import type { CanonicalAttentionArea } from "../../api/lecturerApi";
import { SectionHeader } from "./SectionHeader";

interface Props { areas: CanonicalAttentionArea[]; }

const priorityConfig = [
  { priority: "Critical", color: "border-l-red-500", bg: "bg-red-50 dark:bg-red-500/5", icon: "🔴" },
  { priority: "High", color: "border-l-orange-500", bg: "bg-orange-50 dark:bg-orange-500/5", icon: "🟠" },
  { priority: "Medium", color: "border-l-amber-500", bg: "bg-amber-50 dark:bg-amber-500/5", icon: "🟡" },
];

export function AttentionAreasPanel({ areas }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <Card className="p-5">
      <SectionHeader icon={AlertTriangle} title="Needs Attention" subtitle="Topics requiring focus" />
      <div className="space-y-4">
        {priorityConfig.map(({ priority, color, bg, icon }) => {
          const items = areas.filter((a) => a.priority === priority);
          const isExpanded = expanded[priority];

          return (
            <div key={priority} className={`border-l-4 ${color} rounded-r-lg ${bg} p-3`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">
                  {icon} {priority} Priority
                </span>
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
