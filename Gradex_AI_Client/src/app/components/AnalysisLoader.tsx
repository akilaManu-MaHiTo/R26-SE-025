import React, { useEffect, useState } from "react";
import { BrandOrb } from "./BrandOrb";

export function AnalysisLoader({ label = "Analyzing exam", complete = false, onComplete }: {
  label?: string;
  complete?: boolean;
  onComplete?: () => void;
}) {
  const [progress, setProgress] = useState(1);

  useEffect(() => {
    if (complete) {
      const timer = window.setInterval(() => setProgress(value => Math.min(100, value + 8)), 20);
      const finish = window.setTimeout(() => {
        window.clearInterval(timer);
        onComplete?.();
      }, 420);
      return () => {
        window.clearInterval(timer);
        window.clearTimeout(finish);
      };
    }
    const startedAt = Date.now();
    // shortcut: time-based estimate capped at 99%, use backend percentages when available.
    const timer = window.setInterval(() => {
      const next = Math.min(99, 1 + (Date.now() - startedAt) / 1000);
      setProgress(next);
      if (next === 99) window.clearInterval(timer);
    }, 100);
    return () => window.clearInterval(timer);
  }, [complete, onComplete]);

  return (
    <div className="flex flex-col items-center justify-center gap-5 py-16">
      <BrandOrb state="solving" size={64} aria-label={label} />
      <div className="w-full max-w-xs space-y-3">
        <div className="flex items-center justify-between text-sm">
          <p className="font-medium">{label}…</p>
          <span className="tabular-nums text-muted-foreground">{Math.floor(progress)}%</span>
        </div>
        <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={Math.floor(progress)} aria-valuetext={`Approximately ${Math.floor(progress)}%`}
          className="h-1.5 overflow-hidden rounded-full bg-primary/10">
          <div className="h-full w-full origin-left rounded-full bg-primary transition-transform duration-100 ease-linear motion-reduce:transition-none"
            style={{ transform: `scaleX(${progress / 100})` }} />
        </div>
      </div>
    </div>
  );
}
