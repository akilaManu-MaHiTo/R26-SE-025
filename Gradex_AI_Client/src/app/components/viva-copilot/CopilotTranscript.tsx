import { ScrollArea } from "../ui/scroll-area";
import type { TranscriptTurn } from "./copilotApi";

interface CopilotTranscriptProps {
  turns: TranscriptTurn[];
  partial?: string;
}

export function CopilotTranscript({ turns, partial }: CopilotTranscriptProps) {
  return (
    <ScrollArea className="h-64 rounded-xl border border-border bg-muted/20">
      <div className="p-4 space-y-3 text-sm">
        {turns.length === 0 && !partial && (
          <p className="text-muted-foreground">Live transcript will appear here as the student speaks.</p>
        )}
        {turns.map((turn, index) => (
          <div key={`${turn.timestamp ?? index}-${index}`}>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {turn.speaker === "interviewer" ? "Panel" : "Student"}
            </div>
            <p className="text-foreground leading-relaxed">{turn.text}</p>
          </div>
        ))}
        {partial ? (
          <div>
            <div className="text-[11px] uppercase tracking-wide text-primary">Student (live)</div>
            <p className="text-foreground/80 leading-relaxed italic">{partial}</p>
          </div>
        ) : null}
      </div>
    </ScrollArea>
  );
}
