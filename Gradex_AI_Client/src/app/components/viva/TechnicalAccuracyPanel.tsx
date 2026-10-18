import { useMemo, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Progress } from "../ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../ui/collapsible";
import { TechnicalAccuracyAI, TechnicalAccuracyConcept, suggestedTechnicalMark } from "./types";
import { useMarkingScale } from "./useMarkingScale";

interface TechnicalAccuracyPanelProps {
  evaluation?: TechnicalAccuracyAI;
}

/**
 * Advisory panel showing the AI's suggested technical-accuracy score and its
 * per-concept evidence, computed against a lecturer-uploaded subject rubric
 * (see /api/subject-content). This never publishes anything itself — it is
 * shown next to the examiner's own "Technical Knowledge" slider in
 * EvaluationPanel.tsx, which pre-fills from the suggestion but stays editable.
 *
 * A rubric can hold hundreds of concepts, and a student can cover most of them, so the panel
 * must stay the same height however many concepts there are:
 *   - the score and the coverage summary are always visible and fixed in size;
 *   - the per-concept evidence sits behind one disclosure, closed by default;
 *   - opened, it scrolls inside a height-limited box and each group pages in `PAGE_SIZE` rows at
 *     a time, with search for the big rubrics.
 * Otherwise the examiner's score slider and the Publish button get pushed off the screen.
 */

/** Rows shown per group before "Show more". */
const PAGE_SIZE = 10;
/** Search is only worth its space once the list is longer than a screenful. */
const SEARCH_THRESHOLD = 12;

type Bucket = "incorrect" | "covered" | "missed";

const GROUP_LABELS: Record<Bucket, string> = {
  incorrect: "Answered incorrectly",
  covered: "Covered correctly",
  missed: "Not covered",
};

function bucketOf(concept: TechnicalAccuracyConcept): Bucket {
  if (!concept.covered) return "missed";
  return concept.correct === false ? "incorrect" : "covered";
}

function ConceptRow({ concept }: { concept: TechnicalAccuracyConcept }) {
  const bucket = bucketOf(concept);
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{concept.name}</div>
        <div className="flex items-center gap-1.5 shrink-0">
          {concept.weight != null && (
            <span className="text-xs text-muted-foreground tabular-nums">
              w{concept.weight.toFixed(1)}
            </span>
          )}
          {bucket === "missed" ? (
            <Badge variant="outline" className="text-xs">
              Not covered
            </Badge>
          ) : bucket === "incorrect" ? (
            <Badge variant="outline" className="text-xs text-red-700 dark:text-red-400">
              Incorrect
            </Badge>
          ) : (
            <Badge variant="default" className="text-xs">
              Correct
            </Badge>
          )}
        </div>
      </div>
      {concept.evidence_quote && (
        <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
          "{concept.evidence_quote}"
        </p>
      )}
    </div>
  );
}

/** One group of concepts that reveals `PAGE_SIZE` more rows each time it is asked to. */
function ConceptGroup({
  title,
  concepts,
}: {
  title: string;
  concepts: TechnicalAccuracyConcept[];
}) {
  const [shown, setShown] = useState(PAGE_SIZE);
  if (concepts.length === 0) return null;
  const remaining = concepts.length - shown;
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-foreground pt-1">
        {title} ({concepts.length})
      </div>
      {concepts.slice(0, shown).map((concept) => (
        <ConceptRow key={concept.concept_id} concept={concept} />
      ))}
      {remaining > 0 && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 w-full text-xs"
          onClick={() => setShown((count) => count + PAGE_SIZE)}
        >
          Show {Math.min(PAGE_SIZE, remaining)} more ({remaining} left)
        </Button>
      )}
    </div>
  );
}

export function TechnicalAccuracyPanel({ evaluation }: TechnicalAccuracyPanelProps) {
  const [query, setQuery] = useState("");
  const { technicalMax } = useMarkingScale();

  const concepts = useMemo(() => evaluation?.concepts ?? [], [evaluation]);

  const groups = useMemo(() => {
    const incorrect: TechnicalAccuracyConcept[] = [];
    const covered: TechnicalAccuracyConcept[] = [];
    const missed: TechnicalAccuracyConcept[] = [];
    for (const concept of concepts) {
      const bucket = bucketOf(concept);
      if (bucket === "incorrect") incorrect.push(concept);
      else if (bucket === "covered") covered.push(concept);
      else missed.push(concept);
    }
    // Heaviest first: a missed weight-5 concept matters more than a missed 1.
    const byWeight = (a: TechnicalAccuracyConcept, b: TechnicalAccuracyConcept) =>
      (b.weight ?? 1) - (a.weight ?? 1);
    return {
      incorrect: incorrect.sort(byWeight),
      covered: covered.sort(byWeight),
      missed: missed.sort(byWeight),
    };
  }, [concepts]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return concepts.filter((concept) => concept.name.toLowerCase().includes(q));
  }, [concepts, query]);

  if (!evaluation || evaluation.status === "skipped") {
    return (
      <p className="text-sm text-muted-foreground">
        {evaluation?.error ??
          "No subject content was linked to this viva, so no AI technical-accuracy suggestion is available."}
      </p>
    );
  }

  if (evaluation.status === "unavailable") {
    return (
      <p className="text-sm text-amber-700 dark:text-amber-400">
        {evaluation.error ?? "AI technical-accuracy scoring was unavailable for this recording."}
      </p>
    );
  }

  const total = concepts.length;
  const engaged = groups.covered.length + groups.incorrect.length;
  const coveragePct = total ? Math.round((engaged / total) * 100) : 0;

  return (
    <div className="space-y-3">
      {/* The model name is deliberately not shown here: an examiner grading a
          viva has no use for it, and it competes with the score for attention.
          It is still recorded in the exported report, where the provenance of a
          suggested mark matters. */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="text-sm font-medium text-foreground">AI-suggested technical accuracy</div>
        {evaluation.status === "partial" && (
          <Badge variant="outline" className="text-xs text-amber-700 dark:text-amber-400">
            Partial
          </Badge>
        )}
      </div>

      {suggestedTechnicalMark(evaluation) != null && (
        <div className="text-sm font-semibold text-foreground">
          {suggestedTechnicalMark(evaluation)!.toFixed(1)}
          <span className="text-xs font-normal text-muted-foreground">
            {" "}
            / {technicalMax} — suggestion only, review before publishing
          </span>
        </div>
      )}
      {evaluation.error && (
        <p className="text-xs text-amber-700 dark:text-amber-400">{evaluation.error}</p>
      )}

      {/* Coverage summary: fixed size, readable at any rubric size. */}
      <div className="rounded-lg border border-border p-3 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Concept coverage</span>
          <span className="text-foreground tabular-nums">
            {engaged} of {total} discussed ({coveragePct}%)
          </span>
        </div>
        <Progress value={coveragePct} className="h-1.5" />
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          <Badge variant="default" className="text-xs">
            {groups.covered.length} correct
          </Badge>
          {groups.incorrect.length > 0 && (
            <Badge variant="outline" className="text-xs text-red-700 dark:text-red-400">
              {groups.incorrect.length} incorrect
            </Badge>
          )}
          <Badge variant="outline" className="text-xs">
            {groups.missed.length} not covered
          </Badge>
        </div>
      </div>

      {/* Per-concept evidence: closed by default, and scrolls inside a fixed-height box. */}
      {total > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="group flex w-full items-center justify-between rounded-lg border border-border px-3 py-2 text-left transition-colors hover:bg-muted/50">
            <span className="text-xs font-medium text-foreground">View concept details ({total})</span>
            <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-2 pt-2">
            {total > SEARCH_THRESHOLD && (
              <div className="relative">
                <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={`Search ${total} concepts…`}
                  className="pl-8 h-8 text-xs"
                  aria-label="Search concepts"
                />
              </div>
            )}

            <div className="max-h-80 space-y-3 overflow-y-auto pr-1" data-testid="concept-details">
              {matches ? (
                matches.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No concept matches "{query}".</p>
                ) : (
                  // Remount per query so the paging starts again from the first rows.
                  <ConceptGroup key={query} title="Matches" concepts={matches} />
                )
              ) : (
                <>
                  {engaged === 0 && (
                    <p className="text-sm text-muted-foreground">
                      The transcript did not touch any concept in this rubric.
                    </p>
                  )}
                  <ConceptGroup title={GROUP_LABELS.incorrect} concepts={groups.incorrect} />
                  <ConceptGroup title={GROUP_LABELS.covered} concepts={groups.covered} />
                  <ConceptGroup title={GROUP_LABELS.missed} concepts={groups.missed} />
                </>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
