import { useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "../ui/button";
import type { CopilotSuggestion } from "./copilotApi";

export interface SuggestionToastItem extends CopilotSuggestion {
  id: string;
}

interface SuggestionToastsProps {
  items: SuggestionToastItem[];
  onAsk: (question: string) => void;
  onDismiss: (id: string) => void;
  askDisabled?: boolean;
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-rose-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-slate-500 text-white",
};

function ToastCard({
  item,
  onAsk,
  onDismiss,
  askDisabled,
}: {
  item: SuggestionToastItem;
  onAsk: (question: string) => void;
  onDismiss: (id: string) => void;
  askDisabled: boolean;
}) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(item.id), 16000);
    return () => window.clearTimeout(timer);
  }, [item.id, onDismiss]);

  return (
    <div className="pointer-events-auto rounded-xl border border-border bg-card/95 shadow-lg backdrop-blur-sm p-3 space-y-2 animate-in fade-in slide-in-from-right-4 duration-300">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.medium}`}>
            {item.priority}
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {item.difficulty}
          </span>
        </div>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground"
          onClick={() => onDismiss(item.id)}
          aria-label="Dismiss suggestion"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <p className="text-sm text-foreground leading-snug">{item.question}</p>
      {item.reason ? <p className="text-xs text-muted-foreground">Why: {item.reason}</p> : null}
      <Button size="sm" type="button" disabled={askDisabled} onClick={() => onAsk(item.question)}>
        Ask this
      </Button>
    </div>
  );
}

export function SuggestionToasts({ items, onAsk, onDismiss, askDisabled = false }: SuggestionToastsProps) {
  if (items.length === 0) return null;
  return (
    <div className="pointer-events-none fixed top-4 right-4 z-50 flex w-[min(100%-2rem,24rem)] flex-col gap-2">
      {items.map((item) => (
        <ToastCard
          key={item.id}
          item={item}
          onAsk={onAsk}
          onDismiss={onDismiss}
          askDisabled={askDisabled}
        />
      ))}
    </div>
  );
}
