import { Sparkles, Volume2, ScanText } from "lucide-react";
import { AudioAnalysis } from "./types";

interface TranscriptPanelProps {
  audioAnalysis?: AudioAnalysis;
}

export function TranscriptPanel({ audioAnalysis }: TranscriptPanelProps) {
  const transcript = audioAnalysis?.transcript?.trim() || audioAnalysis?.transcript_excerpt?.trim();
  const emotion = audioAnalysis?.audio_emotion?.predicted_emotion;
  const emotionConfidence = audioAnalysis?.audio_emotion?.confidence;
  const pitchLevel = audioAnalysis?.pitch_profile?.level;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {audioAnalysis?.transcript_word_count ?? 0} words · {audioAnalysis?.segment_count ?? 0} segments
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 dark:bg-blue-500/10 px-2.5 py-1 text-xs text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20">
          <Sparkles className="size-3" /> AI generated
        </span>
      </div>

      {(emotion || pitchLevel) && (
        <div className="flex flex-wrap gap-2 mt-3">
          {emotion && (
            <span className="inline-flex items-center rounded-full bg-orange-50 dark:bg-orange-500/10 px-2.5 py-1 text-xs text-orange-700 dark:text-orange-400 border border-orange-200 dark:border-orange-500/20">
              <Volume2 className="size-3 mr-1" />
              Emotion: {emotion}
              {emotionConfidence != null ? ` (${Math.round(emotionConfidence * 100)}%)` : ""}
            </span>
          )}
          {pitchLevel && (
            <span className="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-500/10 px-2.5 py-1 text-xs text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20 capitalize">
              <ScanText className="size-3 mr-1" />
              Pitch: {pitchLevel}
            </span>
          )}
        </div>
      )}

      <div className="mt-3 rounded-lg border border-border bg-muted/40 p-4">
        {transcript ? (
          <p className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-foreground/90 pr-1">
            {transcript}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">No transcript was generated for this recording.</p>
        )}
      </div>
    </div>
  );
}
