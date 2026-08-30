import { HelpCircle } from "lucide-react";
import { ReactNode } from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "../ui/hover-card";
import { AssessmentMode, VivaAssessment } from "./types";
import { ScoreExplainTopic, buildScoreExplain } from "./scoreExplainers";

interface ScoreExplainHoverProps {
  topic: ScoreExplainTopic;
  assessment?: VivaAssessment;
  assessmentMode?: AssessmentMode;
  children: ReactNode;
  /** Extra class on the trigger wrapper */
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
  showIcon?: boolean;
}

export function ScoreExplainHover({
  topic,
  assessment,
  assessmentMode,
  children,
  className,
  side = "top",
  showIcon = true,
}: ScoreExplainHoverProps) {
  const content = buildScoreExplain(topic, { assessment, assessmentMode });

  return (
    <HoverCard openDelay={120} closeDelay={80}>
      <HoverCardTrigger asChild>
        <span
          tabIndex={0}
          className={`inline-flex items-center gap-1 text-left rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            showIcon ? "cursor-help border-b border-dotted border-muted-foreground/50" : "cursor-help"
          } ${className || ""}`}
          aria-label={`${content.title} — show how this score is calculated`}
        >
          {children}
          {showIcon ? (
            <HelpCircle className="size-3.5 shrink-0 text-muted-foreground/80" aria-hidden />
          ) : null}
        </span>
      </HoverCardTrigger>
      <HoverCardContent
        side={side}
        align="start"
        className="w-80 max-w-[min(20rem,calc(100vw-1.5rem))] p-3 text-xs leading-relaxed"
      >
        <div className="font-medium text-foreground text-sm">{content.title}</div>
        {content.summary ? (
          <p className="mt-1 text-muted-foreground">{content.summary}</p>
        ) : null}
        {content.formula ? (
          <div className="mt-2 rounded-md bg-muted/60 px-2 py-1.5 font-mono text-[11px] text-foreground">
            {content.formula}
          </div>
        ) : null}
        <ul className="mt-2 space-y-1 text-muted-foreground">
          {content.lines.map((line) => (
            <li key={line} className="pl-3 relative before:absolute before:left-0 before:content-['·']">
              {line}
            </li>
          ))}
        </ul>
      </HoverCardContent>
    </HoverCard>
  );
}
