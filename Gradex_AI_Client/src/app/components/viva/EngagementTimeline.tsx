import { useMemo } from "react";
import { TimelineItem, engagementLabelRank, engagementLabelText, formatTime } from "./types";

interface EngagementTimelineProps {
  timeline: TimelineItem[];
  onSeek?: (seconds: number) => void;
}

const RANK_COLOR = ["bg-slate-300", "bg-amber-400", "bg-blue-500", "bg-emerald-500"];

/** Compact bar-per-second engagement visualization; click/keyboard-activate a bar to seek the video. */
export function EngagementTimeline({ timeline, onSeek }: EngagementTimelineProps) {
  const frames = useMemo(() => timeline.filter((t) => t.valid && t.engagement_label), [timeline]);

  if (frames.length === 0) {
    return <p className="text-sm text-muted-foreground">No engagement timeline data available for this recording.</p>;
  }

  return (
    <div>
      <div className="flex items-end gap-0.5 h-16" role="list" aria-label="Engagement over time">
        {frames.map((item) => {
          const rank = engagementLabelRank(item.engagement_label);
          const heightPercent = 25 + Math.max(rank, 0) * 25;
          return (
            <button
              key={item.time}
              type="button"
              role="listitem"
              onClick={() => onSeek?.(item.time)}
              disabled={!onSeek}
              className={`flex-1 min-w-[3px] rounded-sm ${RANK_COLOR[Math.max(rank, 0)]} transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:cursor-default`}
              style={{ height: `${heightPercent}%` }}
              title={`${formatTime(item.time)} · ${engagementLabelText(item.engagement_label)} engagement`}
              aria-label={`${formatTime(item.time)}: ${engagementLabelText(item.engagement_label)} engagement`}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
        <span>{formatTime(frames[0].time)}</span>
        <div className="flex items-center gap-3">
          <LegendDot color="bg-slate-300" label="Very low" />
          <LegendDot color="bg-amber-400" label="Low" />
          <LegendDot color="bg-blue-500" label="High" />
          <LegendDot color="bg-emerald-500" label="Very high" />
        </div>
        <span>{formatTime(frames[frames.length - 1].time)}</span>
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`size-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
