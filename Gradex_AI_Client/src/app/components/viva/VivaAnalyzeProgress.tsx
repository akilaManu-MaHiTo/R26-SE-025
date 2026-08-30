import { Check, Loader2 } from "lucide-react";

export const VIVA_ANALYZE_STEPS: Array<{ id: string; label: string }> = [
  { id: "face_landmarks", label: "Reading face landmarks" },
  { id: "facial_emotion", label: "Gathering facial expressions" },
  { id: "engagement", label: "Gathering engagement" },
  { id: "extract_audio", label: "Extracting audio" },
  { id: "whisper", label: "Transcribing speech (Whisper)" },
  { id: "audio_emotion", label: "Gathering speech emotion" },
  { id: "acoustics", label: "Measuring voice quality" },
  { id: "llm_judge", label: "Scoring delivery" },
  { id: "qa", label: "Checking Q&A relevance" },
  { id: "assessment", label: "Computing official mark" },
  { id: "technical", label: "Scoring concept coverage" },
  { id: "saving", label: "Saving the mark" },
];

export interface VivaProgressSnapshot {
  stage?: string | null;
  message?: string | null;
  done?: string[];
}

export async function fetchVivaAnalyzeProgress(
  backendBaseUrl: string,
  progressId: string,
  apiKey: string,
): Promise<VivaProgressSnapshot | null> {
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;
    const response = await fetch(
      `${backendBaseUrl.replace(/\/$/, "")}/api/viva-analyze/progress/${encodeURIComponent(progressId)}`,
      { headers },
    );
    if (!response.ok) return null;
    return (await response.json()) as VivaProgressSnapshot;
  } catch {
    return null;
  }
}

export function VivaAnalyzeProgress({
  snapshot,
  elapsedSeconds,
}: {
  snapshot: VivaProgressSnapshot | null;
  elapsedSeconds: number;
}) {
  const done = new Set(snapshot?.done || []);
  const rawStage = snapshot?.stage || "";
  const current =
    rawStage === "starting" || !rawStage ? "face_landmarks" : rawStage;
  const currentIndex = VIVA_ANALYZE_STEPS.findIndex((step) => step.id === current);

  return (
    <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20">
      <div className="flex items-center gap-3 mb-3">
        <Loader2 className="size-5 text-amber-600 dark:text-amber-400 animate-spin shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">
            {snapshot?.message || "Starting video analysis"}
          </div>
          <div className="text-xs text-muted-foreground tabular-nums mt-0.5">
            {elapsedSeconds.toFixed(1)}s elapsed
          </div>
        </div>
      </div>
      <ol className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
        {VIVA_ANALYZE_STEPS.map((step, index) => {
          const isDone = done.has(step.id) && step.id !== current;
          const isCurrent = step.id === current;
          const upcoming = currentIndex >= 0 && index > currentIndex && !isDone;
          return (
            <li
              key={step.id}
              className={
                isCurrent
                  ? "text-xs font-medium text-foreground flex items-center gap-1.5"
                  : isDone
                    ? "text-xs text-muted-foreground flex items-center gap-1.5"
                    : upcoming
                      ? "text-xs text-muted-foreground/60 flex items-center gap-1.5"
                      : "text-xs text-muted-foreground flex items-center gap-1.5"
              }
            >
              {isDone ? (
                <Check className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="size-3.5 animate-spin shrink-0" />
              ) : (
                <span className="size-3.5 rounded-full border border-border shrink-0" />
              )}
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
