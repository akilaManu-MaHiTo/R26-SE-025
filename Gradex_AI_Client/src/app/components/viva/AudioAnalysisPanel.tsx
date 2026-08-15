import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../ui/collapsible";
import { AudioAnalysis } from "./types";

interface AudioAnalysisPanelProps {
  audioAnalysis?: AudioAnalysis;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/40 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

const ADVANCED_METRIC_LABELS: Record<string, string> = {
  pitch_mean_hz: "Mean pitch",
  pitch_min_hz: "Min pitch",
  pitch_max_hz: "Max pitch",
  pitch_std_hz: "Pitch variation",
  jitter_local: "Jitter",
  shimmer_local: "Shimmer",
  hnr_mean_db: "Harmonics-to-noise ratio",
  rms_mean: "RMS energy",
  tempo_bpm: "Tempo",
  duration_seconds: "Duration",
};

const GRADE_BREAKDOWN_LABELS: Record<string, string> = {
  pitch_score: "Pitch",
  pitch_stability: "Pitch stability",
  clarity_score: "Clarity",
  articulation_score: "Articulation",
  energy_score: "Energy",
  emotion_score: "Emotion",
  transcript_score: "Transcript",
  segment_score: "Segmentation",
};

function formatMetric(key: string, value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "unmeasured";
  if (key === "duration_seconds") return `${value.toFixed(1)} s`;
  if (key === "tempo_bpm") return `${value.toFixed(0)} BPM`;
  if (key.endsWith("_hz")) return `${value.toFixed(1)} Hz`;
  if (key === "hnr_mean_db") return `${value.toFixed(1)} dB`;
  return value.toFixed(4);
}

export function AudioAnalysisPanel({ audioAnalysis }: AudioAnalysisPanelProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  if (!audioAnalysis || (audioAnalysis.status !== "success" && audioAnalysis.status !== "insufficient_audio" && audioAnalysis.status !== "degraded")) {
    return (
      <p className="text-sm text-muted-foreground">
        {audioAnalysis?.error || "Audio analysis is not available for this recording."}
      </p>
    );
  }

  const { audio_grade, pitch_profile, audio_emotion, acoustic_features, grade_breakdown, status, degraded_reasons } = audioAnalysis;
  const advancedFeatures = acoustic_features
    ? Object.entries(acoustic_features).filter(([k]) => k in ADVANCED_METRIC_LABELS)
    : [];
  const numericBreakdown = grade_breakdown
    ? Object.entries(grade_breakdown).filter(([k, v]) => k in GRADE_BREAKDOWN_LABELS && typeof v === "number")
    : [];

  return (
    <div className="space-y-4">
      {status === "insufficient_audio" && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          {audioAnalysis.error || "Insufficient voiced audio — no numeric audio grade was assigned."}
        </p>
      )}
      {status === "degraded" && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          Partial audio analysis
          {degraded_reasons && degraded_reasons.length > 0
            ? ` (${degraded_reasons.join(", ").replace(/_/g, " ")})`
            : ""}
          . Treat the grade as approximate.
        </p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        <Stat label="Audio Grade" value={audio_grade != null ? `${audio_grade.toFixed(2)} / 10` : "—"} />
        <Stat label="Pitch Profile" value={pitch_profile?.level ? capitalize(pitch_profile.level) : "—"} />
        <Stat label="Predicted Emotion" value={audio_emotion?.predicted_emotion ? capitalize(audio_emotion.predicted_emotion) : "—"} />
        <Stat label="Valence" value={audio_emotion?.valence ? capitalize(audio_emotion.valence) : "—"} />
        <Stat
          label="Audio Confidence"
          value={
            audio_emotion?.confidence != null
              ? `${Math.round(audio_emotion.confidence * 100)}%${
                  audio_emotion.source && audio_emotion.source !== "model" ? " (heuristic)" : ""
                }`
              : "—"
          }
        />
        <Stat label="Duration" value={acoustic_features?.duration_seconds != null ? `${acoustic_features.duration_seconds.toFixed(0)} sec` : "—"} />
      </div>

      {(advancedFeatures.length > 0 || numericBreakdown.length > 0) && (
        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <CollapsibleTrigger className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ChevronDown className={`size-4 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
            Advanced audio metrics
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-3 space-y-4">
            {advancedFeatures.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {advancedFeatures.map(([key, value]) => (
                  <Stat
                    key={key}
                    label={ADVANCED_METRIC_LABELS[key]}
                    value={formatMetric(key, typeof value === "number" ? value : null)}
                  />
                ))}
              </div>
            )}
            {numericBreakdown.length > 0 && (
              <div>
                <div className="text-xs text-muted-foreground mb-2">Grade breakdown</div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {numericBreakdown.map(([key, value]) => (
                    <Stat
                      key={key}
                      label={GRADE_BREAKDOWN_LABELS[key] ?? key}
                      value={typeof value === "number" ? value.toFixed(3) : "—"}
                    />
                  ))}
                </div>
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
