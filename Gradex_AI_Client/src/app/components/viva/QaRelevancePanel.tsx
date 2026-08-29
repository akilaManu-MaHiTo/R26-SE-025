import { ConversationStructure, ConversationTurn, QaAnalysis, formatTime } from "./types";

interface QaRelevancePanelProps {
  qaAnalysis?: QaAnalysis;
  turns?: ConversationTurn[];
  structure?: ConversationStructure;
  onSeek?: (time: number) => void;
}

const RELEVANCE_CLASS: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/30",
  medium: "bg-sky-50 text-sky-800 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/30",
  low: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30",
  irrelevant: "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/30",
};

const QA_DIALOGUE_PHASES = new Set([
  "qa",
  "panel_question",
  "student_answer",
  "follow_up_question",
  "follow_up_answer",
]);

const SEGMENT_LABELS: Record<string, string> = {
  presentation: "Presentation",
  return_to_presentation: "Presentation",
  panel_question: "Question",
  student_answer: "Answer",
  follow_up_question: "Follow-up",
  follow_up_answer: "Follow-up answer",
  panel_interruption: "Interruption",
  student_question: "Student question",
  instruction: "Instruction",
  qa: "Q&A",
};

export function QaRelevancePanel({ qaAnalysis, turns, structure, onSeek }: QaRelevancePanelProps) {
  const pairs = qaAnalysis?.pairs ?? [];
  const dialogue = (turns ?? []).filter((turn) => QA_DIALOGUE_PHASES.has(String(turn.phase || "")));
  const hasPanel = (turns ?? []).some((turn) => turn.role === "panel");
  const segments = structure?.segments ?? [];

  if (!qaAnalysis && dialogue.length === 0 && segments.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Q&A relevance is not available for this recording.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-sm font-medium text-foreground">Did the student answer the question?</div>
        <p className="mt-1 text-xs text-muted-foreground">
          Conversation structure first, then semantic relevance of each question–answer pair — not a mark.
          {structure?.source === "llm" ? " · structured by AI" : structure?.source === "heuristic" ? " · heuristic fallback" : ""}
          {qaAnalysis?.model ? ` · ${qaAnalysis.model}` : ""}
          {qaAnalysis?.pair_count != null ? ` · ${qaAnalysis.pair_count} pair${qaAnalysis.pair_count === 1 ? "" : "s"}` : ""}
        </p>
        {qaAnalysis?.status === "empty" && (
          <p className="mt-2 text-sm text-muted-foreground">
            {qaAnalysis.error || "No panel questions were detected in this recording."}
          </p>
        )}
        {qaAnalysis?.status === "unavailable" && qaAnalysis.error && (
          <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">{qaAnalysis.error}</p>
        )}
        {structure?.status === "fallback" && structure.error && (
          <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">{structure.error}</p>
        )}
      </div>

      {segments.length > 0 && (
        <div>
          <div className="text-sm font-medium text-foreground mb-2">Conversation structure</div>
          <div className="flex flex-wrap gap-1.5">
            {segments.map((segment, index) => {
              const seekTime = segment.start;
              const label = SEGMENT_LABELS[String(segment.type || "")] || String(segment.type || "segment").replace(/_/g, " ");
              return (
                <button
                  type="button"
                  key={`${segment.type ?? "seg"}-${segment.start ?? index}-${index}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  onClick={() => seekTime != null && onSeek?.(seekTime)}
                >
                  <span>{seekTime != null ? formatTime(seekTime) : "—"}</span>
                  <span>{label}</span>
                  {segment.speaker ? <span>· {segment.speaker}</span> : null}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {pairs.length > 0 && (
        <div className="space-y-3">
          {pairs.map((pair, index) => {
            const relevance = String(pair.relevance || "").toLowerCase();
            const badgeClass = RELEVANCE_CLASS[relevance] ?? "bg-muted text-foreground border-border";
            const seekTime = pair.question_start;
            return (
              <div key={`${pair.question_start ?? index}-${index}`} className="rounded-lg border border-border p-3 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => seekTime != null && onSeek?.(seekTime)}
                  >
                    {seekTime != null ? formatTime(seekTime) : "—"} · {pair.panel_label || "PANEL_01"}
                  </button>
                  {pair.relevance && (
                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs capitalize ${badgeClass}`}>
                      {String(pair.relevance).replace(/_/g, " ")}
                    </span>
                  )}
                  {pair.answer_type && (
                    <span className="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground capitalize">
                      {String(pair.answer_type).replace(/_/g, " ")}
                    </span>
                  )}
                  {pair.addresses_question != null && (
                    <span className="text-xs text-muted-foreground">
                      {pair.addresses_question ? "Addresses question" : "Does not address question"}
                    </span>
                  )}
                  {pair.confidence != null && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {Math.round(pair.confidence * 100)}%
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground">Question</div>
                  <p className="text-sm text-foreground">{pair.question || "—"}</p>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground">Student answer</div>
                  <p className="text-sm text-foreground/90">{pair.answer?.trim() ? pair.answer : "(no answer)"}</p>
                </div>
                {pair.explanation && (
                  <p className="text-xs text-muted-foreground leading-relaxed">{pair.explanation}</p>
                )}
                {pair.status === "unavailable" && pair.error && (
                  <p className="text-xs text-amber-700 dark:text-amber-400">{pair.error}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {hasPanel && dialogue.length > 0 && (
        <div>
          <div className="text-sm font-medium text-foreground mb-2">Q&A conversation</div>
          <div className="max-h-80 overflow-y-auto rounded-lg border border-border divide-y divide-border">
            {dialogue.map((turn, index) => {
              const isStudent = turn.role === "student";
              return (
                <button
                  type="button"
                  key={`${turn.start ?? index}-${index}`}
                  className="w-full text-left px-3 py-2 hover:bg-muted/50"
                  onClick={() => turn.start != null && onSeek?.(turn.start)}
                >
                  <div className="text-xs text-muted-foreground">
                    {turn.start != null ? formatTime(turn.start) : "—"} · {turn.label || (isStudent ? "STUDENT" : "PANEL_01")}
                  </div>
                  <p className="mt-0.5 text-sm text-foreground/90">{turn.text}</p>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
