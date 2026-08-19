import { Sparkles, Volume2, ScanText } from "lucide-react";
import { AudioAnalysis, ConversationTurn, formatTime } from "./types";

interface TranscriptPanelProps {
  audioAnalysis?: AudioAnalysis;
  onSeek?: (time: number) => void;
}

const PHASE_LABELS: Record<string, string> = {
  presentation: "presentation",
  return_to_presentation: "presentation",
  qa: "Q&A",
  panel_question: "Q&A",
  student_answer: "Q&A",
  follow_up_question: "follow-up",
  follow_up_answer: "follow-up",
  panel_interruption: "interruption",
  student_question: "student question",
  instruction: "instruction",
};

function phaseLabel(phase?: string): string {
  if (!phase) return "";
  return PHASE_LABELS[phase] || phase.replace(/_/g, " ");
}

function turnClock(turn: ConversationTurn): string {
  if (turn.start == null) return "—";
  if (turn.end == null) return formatTime(turn.start);
  return `${formatTime(turn.start)}–${formatTime(turn.end)}`;
}

export function TranscriptPanel({ audioAnalysis, onSeek }: TranscriptPanelProps) {
  const turns = audioAnalysis?.conversation?.turns ?? [];
  const fullTranscript =
    audioAnalysis?.conversation?.labeled_transcript?.trim() ||
    audioAnalysis?.full_transcript?.trim() ||
    audioAnalysis?.conversation?.full_transcript?.trim() ||
    audioAnalysis?.mixed_transcript?.trim() ||
    audioAnalysis?.transcript?.trim() ||
    audioAnalysis?.transcript_excerpt?.trim();
  const hasPanel = Boolean(audioAnalysis?.conversation?.has_panel) || (audioAnalysis?.diarization?.speaker_count ?? 0) >= 2;
  const emotion = audioAnalysis?.audio_emotion?.predicted_emotion;
  const emotionConfidence = audioAnalysis?.audio_emotion?.confidence;
  const pitchLevel = audioAnalysis?.pitch_profile?.level;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Full recording transcript
          {hasPanel ? " · student and panel" : " · student only"}
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
        {turns.length > 0 ? (
          <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
            {turns.map((turn, index) => {
              const label = phaseLabel(turn.phase);
              const clickable = turn.start != null && onSeek;
              const inner = (
                <>
                  <div className="text-xs text-muted-foreground">
                    {turnClock(turn)} · {turn.label || (turn.role === "panel" ? "PANEL_01" : "STUDENT")}
                    {label ? ` · ${label}` : ""}
                  </div>
                  <p className="text-sm leading-6 text-foreground/90">{turn.text}</p>
                </>
              );
              return clickable ? (
                <button
                  type="button"
                  key={`${turn.start ?? index}-${index}`}
                  className="block w-full text-left hover:bg-muted/60 rounded-md px-1 -mx-1"
                  onClick={() => onSeek(turn.start as number)}
                >
                  {inner}
                </button>
              ) : (
                <div key={`${turn.start ?? index}-${index}`}>{inner}</div>
              );
            })}
          </div>
        ) : fullTranscript ? (
          <p className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-foreground/90 pr-1">
            {fullTranscript}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">No transcript was generated for this recording.</p>
        )}
      </div>
    </div>
  );
}
