import { Sparkles } from "lucide-react";
import { Card } from "../ui/card";

interface AISummaryProps {
  notes: string[];
}

/** Plain-language interpretation of the AI analysis — no raw model terminology. */
export function AISummary({ notes }: AISummaryProps) {
  if (notes.length === 0) return null;

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-primary" />
        <div className="text-sm font-medium text-foreground">AI interpretation</div>
      </div>
      <ul className="mt-2.5 space-y-1.5">
        {notes.map((note, i) => (
          <li key={i} className="text-sm text-muted-foreground leading-relaxed pl-3 relative before:content-['·'] before:absolute before:left-0 before:text-muted-foreground/60">
            {note}
          </li>
        ))}
      </ul>
    </Card>
  );
}
