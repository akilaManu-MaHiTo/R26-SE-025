import { useMemo, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Badge } from "../ui/badge";
import { Input } from "../ui/input";
import { Progress } from "../ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../ui/collapsible";
import { TechnicalAccuracyAI, TechnicalAccuracyConcept } from "./types";

interface TechnicalAccuracyPanelProps {
  evaluation?: TechnicalAccuracyAI;
}

/**
 * Advisory panel showing the AI's suggested technical-accuracy score and its
 * per-concept evidence, computed against a lecturer-uploaded subject rubric
 * (see /api/subject-content). This never publishes anything itself — it is
 * shown next to the examiner's own "Technical Knowledge" slider in
 * EvaluationPanel.tsx, which pre-fills from overall_score but stays editable.
 *
 * A rubric can hold hundreds of concepts, so this deliberately does NOT render
 * one row per concept. What an examiner needs is the coverage summary and the
 * concepts the student actually engaged with; everything untouched is a long
 * tail that is counted, summarised, and collapsed behind a disclosure.
 */

/** Rows worth showing without being asked: anything the student engaged with. */
const PREVIEW_LIMIT = 25;

type Bucket = "incorrect" | "covered" | "missed";

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

export function TechnicalAccuracyPanel({ evaluation }: TechnicalAccuracyPanelProps) {
  const [query, setQuery] = useState("");

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

      {evaluation.overall_score != null && (
        <div className="text-sm font-semibold text-foreground">
          {evaluation.overall_score.toFixed(1)}
          <span className="text-xs font-normal text-muted-foreground">
            {" "}
            / 10 — suggestion only, review before publishing
          </span>
        </div>
      )}
      {evaluation.error && (
        <p className="text-xs text-amber-700 dark:text-amber-400">{evaluation.error}</p>
      )}

      {/* Coverage summary: the part that stays readable at any rubric size. */}
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

      {/* Search: the only practical way through a very large rubric. */}
      {total > PREVIEW_LIMIT && (
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

      {matches ? (
        <div className="space-y-2">
          {matches.length === 0 ? (
            <p className="text-sm text-muted-foreground">No concept matches "{query}".</p>
          ) : (
            matches
              .slice(0, PREVIEW_LIMIT)
              .map((concept) => <ConceptRow key={concept.concept_id} concept={concept} />)
          )}
          {matches.length > PREVIEW_LIMIT && (
            <p className="text-xs text-muted-foreground">
              Showing {PREVIEW_LIMIT} of {matches.length} matches — refine the search to narrow it.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {groups.incorrect.length > 0 && (
            <>
              <div className="text-xs font-medium text-foreground pt-1">
                Answered incorrectly ({groups.incorrect.length})
              </div>
              {groups.incorrect.map((concept) => (
                <ConceptRow key={concept.concept_id} concept={concept} />
              ))}
            </>
          )}

          {groups.covered.length > 0 && (
            <>
              <div className="text-xs font-medium text-foreground pt-1">
                Covered correctly ({groups.covered.length})
              </div>
              {groups.covered.map((concept) => (
                <ConceptRow key={concept.concept_id} concept={concept} />
              ))}
            </>
          )}

          {engaged === 0 && (
            <p className="text-sm text-muted-foreground">
              The transcript did not touch any concept in this rubric.
            </p>
          )}

          {/* The long tail. Counted and weighted, but never worth scrolling. */}
          {groups.missed.length > 0 && (
            <Collapsible>
              <CollapsibleTrigger className="group flex w-full items-center justify-between rounded-lg border border-border px-3 py-2 text-left transition-colors hover:bg-muted/50">
                <span className="text-xs font-medium text-foreground">
                  Not covered ({groups.missed.length})
                </span>
                <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {groups.missed.slice(0, PREVIEW_LIMIT).map((concept) => (
                  <ConceptRow key={concept.concept_id} concept={concept} />
                ))}
                {groups.missed.length > PREVIEW_LIMIT && (
                  <p className="text-xs text-muted-foreground">
                    Showing the {PREVIEW_LIMIT} heaviest of {groups.missed.length} — search above to
                    find a specific concept.
                  </p>
                )}
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      )}
    </div>
  );
}
