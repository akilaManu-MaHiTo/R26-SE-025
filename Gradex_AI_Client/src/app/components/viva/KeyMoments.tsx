import { Play } from "lucide-react";
import { KeyMoment } from "./types";

interface KeyMomentsProps {
  moments: KeyMoment[];
  onSeek?: (seconds: number) => void;
}

const TONE_DOT: Record<KeyMoment["tone"], string> = {
  positive: "bg-emerald-500",
  negative: "bg-red-500",
  neutral: "bg-blue-500",
};

export function KeyMoments({ moments, onSeek }: KeyMomentsProps) {
  if (moments.length === 0) {
    return <p className="text-sm text-muted-foreground">No notable moments were detected in this recording.</p>;
  }

  return (
    <ul className="space-y-1">
      {moments.map((m) => (
        <li key={m.time}>
          <button
            type="button"
            onClick={() => onSeek?.(m.time)}
            disabled={!onSeek}
            className="w-full flex items-start gap-3 px-2.5 py-2 rounded-lg text-left hover:bg-muted transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:cursor-default"
          >
            <span className={`mt-1.5 size-2 rounded-full shrink-0 ${TONE_DOT[m.tone]}`} aria-hidden="true" />
            <span className="text-xs font-mono text-muted-foreground w-11 pt-0.5 shrink-0">{m.timeLabel}</span>
            <span className="flex-1 min-w-0">
              <span className="block text-sm text-foreground font-medium">{m.title}</span>
              <span className="block text-xs text-muted-foreground mt-0.5">{m.detail}</span>
            </span>
            {onSeek && <Play className="size-3.5 text-muted-foreground shrink-0 mt-1" aria-hidden="true" />}
          </button>
        </li>
      ))}
    </ul>
  );
}
