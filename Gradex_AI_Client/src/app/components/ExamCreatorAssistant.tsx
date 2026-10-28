import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { BrandOrb } from "./BrandOrb";
import { toast } from "sonner";
import { ChevronDown, ClipboardCheck, Settings2, Sparkles, Wand2 } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { BLOOM_LEVELS, defaultBlueprint, generateExamQuestions, reviewExamPaper,
  type Blueprint, type CreatorReview, type Generation, type Paper, type Part,
  type MaterialSource, type GenerationRetrieval, type CreatorApiError } from "../api/examCreatorApi";

import { CandidateActions, type StructureActions } from "./ExamStructureControls";

type Props = { structureActions?: StructureActions; courseCode: string; paper: Paper; setPaper: Dispatch<SetStateAction<Paper>> };
const selectClass = "mt-1.5 h-9 w-full rounded-md border border-input bg-background px-2.5 text-sm";
const summaryClass = "flex cursor-pointer list-none items-center gap-3 p-4 [&::-webkit-details-marker]:hidden";
const nestedDetails = "rounded-xl border border-border/70 bg-muted/20 p-3";
const nestedSummary = "cursor-pointer text-xs font-medium";
const sourceLabel = (source: MaterialSource) => {
  const kind = ({ lecture: "Lecture notes", tutorial: "Tutorial", exam: "Past exam", lecture_objective: "Lecture objective" } as Record<string, string>)[source.kind] ?? "Lecturer notes";
  return `${kind}: ${source.filename ?? source.source_id}${source.page_number ? ` · page ${source.page_number}` : ""}`;
};

export function ExamCreatorAssistant({ courseCode, paper, setPaper, structureActions }: Props) {
  const blueprint = paper.blueprint ?? defaultBlueprint();
  const [review, setReview] = useState<CreatorReview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [retrieval, setRetrieval] = useState<GenerationRetrieval | undefined>();
  const [topic, setTopic] = useState("");
  const [bloom, setBloom] = useState("Apply");
  const [marks, setMarks] = useState(10);
  const [allocationTopic, setAllocationTopic] = useState("");
  const [candidateMarks, setCandidateMarks] = useState<Record<string, number>>({});
  const generationAbort = useRef<AbortController | null>(null);
  const version = useRef(0);

  const clearGeneration = () => {
    version.current += 1;
    generationAbort.current?.abort();
    setGeneration(null);
    setGenerating(false);
    setGenerationError("");
    setRetrieval(undefined);
  };

  useEffect(() => {
    const controller = new AbortController();
    let ignore = false;
    version.current += 1;
    generationAbort.current?.abort();
    setGeneration(null);
    setRetrieval(undefined);
    setGenerationError("");
    setGenerating(false);
    setLoading(true);
    setError("");
    setReview(null);
    const timer = setTimeout(() => {
      reviewExamPaper(courseCode, paper, controller.signal).then(data => {
        if (!ignore) setReview(data);
      }).catch(err => {
        if (!ignore && err.name !== "AbortError") setError(err.message);
      }).finally(() => { if (!ignore) setLoading(false); });
    }, 450);
    return () => { ignore = true; clearTimeout(timer); controller.abort(); generationAbort.current?.abort(); };
  }, [courseCode, paper]);

  const updateBlueprint = (change: Partial<Blueprint>) => setPaper(prev => ({
    ...prev, blueprint: { ...(prev.blueprint ?? defaultBlueprint()), ...change },
  }));
  const addPart = (newTopic: string, part: Part) => {
    setPaper(prev => {
      if (prev.questions.some(q => q.parts.some(p => p.question_id && p.question_id === part.question_id))) return prev;
      return { ...prev, questions: [...prev.questions, {
        question_number: prev.questions.length + 1, topic: newTopic, parts: [part],
      }] };
    });
    toast.success("Added to the paper for lecturer review");
  };
  const generate = async () => {
    const controller = new AbortController();
    generationAbort.current?.abort();
    generationAbort.current = controller;
    const currentVersion = version.current;
    setGenerating(true); setGenerationError(""); setGeneration(null); setRetrieval(undefined);
    try {
      const data = await generateExamQuestions(courseCode, paper, topic, bloom, marks, controller.signal);
      if (version.current === currentVersion && !controller.signal.aborted) {
        setGeneration(data);
        setRetrieval(data.retrieval);
      }
    } catch (err) {
      if (!controller.signal.aborted && version.current === currentVersion) {
        setGenerationError(err instanceof Error ? err.message : "Generation failed");
        setRetrieval((err as CreatorApiError)?.retrieval);
      }
    } finally {
      if (version.current === currentVersion && !controller.signal.aborted) setGenerating(false);
    }
  };

  return <div className="space-y-4">
    <details className="group rounded-2xl border border-border/80 bg-card shadow-sm">
      <summary className={summaryClass}>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
          <Settings2 className="size-4" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">Paper setup</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">
            {blueprint.total_marks} marks · {blueprint.duration_minutes} min · {blueprint.purpose === "final" ? "Final examination" : "Revision assessment"}
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>

      <div className="space-y-4 border-t border-border/70 p-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-medium text-muted-foreground">Target marks<Input className="mt-1.5 h-9" type="number" min={1} max={1000} value={blueprint.total_marks} onChange={e => updateBlueprint({ total_marks: Number(e.target.value) })} /></label>
          <label className="text-xs font-medium text-muted-foreground">Duration (minutes)<Input className="mt-1.5 h-9" type="number" min={1} max={1440} value={blueprint.duration_minutes} onChange={e => updateBlueprint({ duration_minutes: Number(e.target.value) })} /></label>
          <label className="text-xs font-medium text-muted-foreground">Paper year<Input className="mt-1.5 h-9" type="number" min={1900} max={2200} value={paper.year} onChange={e => setPaper(prev => ({ ...prev, year: Number(e.target.value) }))} /></label>
          <label className="text-xs font-medium text-muted-foreground">Purpose<select className={selectClass} value={blueprint.purpose} onChange={e => updateBlueprint({ purpose: e.target.value as Blueprint["purpose"] })}><option value="final">Final examination</option><option value="revision">Revision assessment</option></select></label>
        </div>
        <p className="text-xs leading-5 text-muted-foreground">Final exams prioritize coverage. Revision assessments also prioritize measured student weaknesses.</p>

        <label className="block text-xs font-medium text-muted-foreground">Learning outcomes<Textarea className="mt-1.5 text-sm" maxLength={5000} value={blueprint.learning_outcomes} placeholder="What should students demonstrate?" onChange={e => updateBlueprint({ learning_outcomes: e.target.value })} /></label>

        <details className={nestedDetails}>
          <summary className={nestedSummary}>Topic mark allocation</summary>
          <p className="my-2 text-xs leading-5 text-muted-foreground">Allocate all marks for a fixed syllabus blueprint, or leave some unallocated.</p>
          {Object.entries(blueprint.topic_marks).map(([name, target]) => (
            <div key={name} className="my-2 flex items-end gap-2">
              <label className="flex-1 text-xs text-muted-foreground">{name}<Input className="mt-1 h-8" aria-label={`Target marks for ${name}`} type="number" min={0} value={target} onChange={e => updateBlueprint({ topic_marks: { ...blueprint.topic_marks, [name]: Number(e.target.value) } })} /></label>
              <Button size="sm" variant="ghost" aria-label={`Remove ${name} allocation`} onClick={() => { const next = { ...blueprint.topic_marks }; delete next[name]; updateBlueprint({ topic_marks: next }); }}>Remove</Button>
            </div>
          ))}
          <div className="mt-2 flex gap-2">
            <Input className="h-8" aria-label="Topic to allocate" list="creator-topics" placeholder="Topic name" value={allocationTopic} onChange={e => setAllocationTopic(e.target.value)} />
            <Button size="sm" disabled={!allocationTopic.trim()} onClick={() => { updateBlueprint({ topic_marks: { ...blueprint.topic_marks, [allocationTopic.trim()]: 0 } }); setAllocationTopic(""); }}>Add</Button>
          </div>
        </details>

        <details className={nestedDetails}>
          <summary className={nestedSummary}>Bloom percentages</summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {BLOOM_LEVELS.map(level => <label key={level} className="text-xs text-muted-foreground">{level} %<Input className="mt-1 h-8" type="number" min={0} max={100} value={blueprint.bloom_percentages[level] ?? 0} onChange={e => updateBlueprint({ bloom_percentages: { ...blueprint.bloom_percentages, [level]: Number(e.target.value) } })} /></label>)}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Total: {Object.values(blueprint.bloom_percentages).reduce((s, n) => s + n, 0)}% (must equal 100%)</p>
        </details>

        <details className={nestedDetails}>
          <summary className={nestedSummary}>Lecture notes for generation</summary>
          <label className="mt-2 block text-xs text-muted-foreground">Relevant course material<Textarea className="mt-1.5" maxLength={20000} rows={6} value={blueprint.lecture_notes} placeholder="Paste relevant lecture passages, definitions, examples and schemas." onChange={e => updateBlueprint({ lecture_notes: e.target.value })} /></label>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Saved with this draft. Generation also searches indexed course lectures. Lecture objectives are used when no matching passages are available.</p>
        </details>

        <datalist id="creator-topics">{Array.from(new Set([...(review?.topics ?? []), ...Object.keys(blueprint.topic_marks)])).map(t => <option key={t} value={t} />)}</datalist>
      </div>
    </details>

    <section className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="size-4 text-muted-foreground" aria-hidden="true" />
            Recommended questions
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Matched to remaining marks and cognitive gaps</p>
        </div>
        {review && <Badge variant="secondary" className="rounded-full font-normal">{review.recommendations.length}</Badge>}
      </div>

      {loading && (
        <div className="space-y-2" aria-hidden="true">
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
        </div>
      )}

      {review && !review.recommendations.length && (
        <div className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center">
          <p className="text-sm font-medium">No matching questions</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">No bank questions fit the remaining allocation. Adjust the blueprint or generate an alternative.</p>
        </div>
      )}

      {review?.recommendations.map(rec => (
        <Card key={rec.question_id} className="gap-0 space-y-2.5 rounded-xl border-border/80 bg-card p-3.5 shadow-none">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="rounded-full text-[10px] font-normal">{rec.canonical_topic}</Badge>
            <Badge variant="secondary" className="rounded-full text-[10px] font-normal">{rec.bloom_level}</Badge>
            <Badge variant="outline" className="rounded-full text-[10px] font-normal">{rec.requires_marks ? "Marks unassigned" : `${rec.marks} marks`}</Badge>
          </div>
          <p className="max-h-48 overflow-auto whitespace-pre-wrap text-xs leading-5">{rec.text}</p>
          <p className="text-[11px] leading-4 text-muted-foreground">{rec.blueprint_reason}</p>
          {rec.requires_marks && (
            <label className="block text-xs font-medium text-muted-foreground">Assign marks (up to {rec.max_available_marks})<Input className="mt-1.5 h-8" aria-label={`Marks for ${rec.question_id}`} type="number" min={1} max={rec.max_available_marks} value={candidateMarks[rec.question_id] ?? ""} onChange={e => setCandidateMarks(prev => ({ ...prev, [rec.question_id]: Number(e.target.value) }))} /></label>
          )}
          <div className="flex flex-wrap gap-2 pt-0.5">
            <CandidateActions topic={rec.canonical_topic}
              part={{ part: "a", question: rec.text, max_marks: rec.requires_marks ? candidateMarks[rec.question_id] : rec.marks, question_id: rec.question_id, bloom_level: rec.bloom_level, review_status: "needs_review" }}
              actions={structureActions} disabled={rec.requires_marks && (!(candidateMarks[rec.question_id] > 0) || candidateMarks[rec.question_id] > rec.max_available_marks)}
              fallback={() => addPart(rec.canonical_topic, { part: "a", question: rec.text, max_marks: rec.requires_marks ? candidateMarks[rec.question_id] : rec.marks, question_id: rec.question_id, bloom_level: rec.bloom_level, review_status: "needs_review" })} />
            <Button size="sm" variant="ghost" onClick={() => {
              const reason = window.prompt("Why is this question unsuitable? (optional)", "");
              if (reason !== null) setPaper(prev => ({ ...prev, rejected_questions: [...(prev.rejected_questions ?? []), { question_id: rec.question_id, reason: reason.slice(0, 1000) }] }));
            }}>Reject</Button>
          </div>
        </Card>
      ))}

      {!!paper.rejected_questions?.length && (
        <Button variant="ghost" size="sm" onClick={() => setPaper(prev => ({ ...prev, rejected_questions: [] }))}>
          Reset {paper.rejected_questions.length} rejected suggestions
        </Button>
      )}
    </section>

    <Card className="gap-0 rounded-2xl border-border/80 bg-card p-4 shadow-sm" aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <ClipboardCheck className="size-4 text-muted-foreground" aria-hidden="true" />
            Paper checks
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Structure, marks and Bloom coverage</p>
        </div>
        {review && (
          <Badge
            variant="outline"
            className={`rounded-full text-[10px] font-normal ${review.review.issues.length ? "border-amber-300/70 text-amber-700 dark:text-amber-400" : "border-emerald-300/70 text-emerald-700 dark:text-emerald-400"}`}
          >
            {review.review.issues.length ? "Needs review" : "On track"}
          </Badge>
        )}
      </div>

      {loading && (
        <p className="mt-3 flex items-center gap-2 rounded-xl bg-muted/50 px-3 py-2.5 text-xs text-muted-foreground">
          <BrandOrb state="solving" size={20} aria-hidden="true" />
          Checking draft…
        </p>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}

      {review && <>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-muted/50 p-2.5">
            <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Marks</p>
            <p className="mt-1 text-sm font-semibold tabular-nums">{review.review.total_marks}/{blueprint.total_marks}</p>
          </div>
          <div className="rounded-xl bg-muted/50 p-2.5">
            <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Remaining</p>
            <p className="mt-1 text-sm font-semibold tabular-nums">{review.review.remaining_marks}</p>
          </div>
          <div className="rounded-xl bg-muted/50 p-2.5">
            <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Time</p>
            <p className="mt-1 text-sm font-semibold tabular-nums">{review.review.estimated_minutes} min</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Estimated time covers {review.review.estimated_parts}/{review.review.part_count} parts.</p>
        {!review.analytics_available && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">No saved analytics for this source exam. Recommendations use the blueprint and course bank.</p>}

        <details className={`${nestedDetails} mt-3`}>
          <summary className={nestedSummary}>Coverage details</summary>
          <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
            {Object.entries(review.review.bloom_coverage).map(([name, c]) => (
              <span key={name} className="rounded-md bg-card px-2 py-1 text-muted-foreground">{name}: <span className="font-medium text-foreground">{c.actual}/{c.target}</span> marks</span>
            ))}
          </div>
        </details>

        {review.review.issues.length ? (
          <details className={`${nestedDetails} mt-2`} open>
            <summary className={nestedSummary}>{review.review.issues.length} items to review</summary>
            <ul className="mt-2 max-h-48 space-y-1 overflow-auto pl-4 text-xs leading-5 text-muted-foreground">
              {review.review.issues.map((i, n) => <li key={n} className="list-disc">{i.message}</li>)}
            </ul>
          </details>
        ) : (
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-emerald-500" />
            Structural checks passed. Verify academic correctness before publishing.
          </p>
        )}
      </>}
    </Card>

    <details className="group rounded-2xl border border-border/80 bg-card shadow-sm">
      <summary className={summaryClass}>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
          <Wand2 className="size-4" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">Generate alternatives</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">Draft a fresh question from lecture material</span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>

      <div className="space-y-3 border-t border-border/70 p-4">
        <label className="block text-xs font-medium text-muted-foreground">Topic<Input className="mt-1.5 h-9" list="creator-topics" value={topic} onChange={e => { setTopic(e.target.value); clearGeneration(); }} placeholder="Select or enter a course topic" /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-medium text-muted-foreground">Bloom level<select className={selectClass} value={bloom} onChange={e => { setBloom(e.target.value); clearGeneration(); }}>{BLOOM_LEVELS.map(l => <option key={l}>{l}</option>)}</select></label>
          <label className="text-xs font-medium text-muted-foreground">Marks per alternative<Input className="mt-1.5 h-9" type="number" min={1} value={marks} onChange={e => { setMarks(Number(e.target.value)); clearGeneration(); }} /></label>
        </div>
        <Button className="w-full" disabled={generating || loading || !!error || !topic.trim() || marks <= 0} onClick={generate}>
          {generating ? <><BrandOrb state="composing" size={20} aria-hidden="true" />Generating questions…</> : "Generate 2 alternatives"}
        </Button>
        <p className="text-[11px] leading-5 text-muted-foreground">Review the answer, rubric, sources and Bloom level before approving a question.</p>

        {generationError && <p role="alert" className="text-sm text-destructive">{generationError}</p>}

        {retrieval && (
          <div className="space-y-2 rounded-xl bg-muted/40 p-3 text-xs" aria-live="polite">
            <p className="leading-5">Retrieved {retrieval.lectures.sources.length} lecture passages and {retrieval.assessment_examples.sources.length} assessment examples.
              {retrieval.lectures.status === "ok" && ` Search: ${retrieval.lectures.mode === "hybrid" ? "semantic + keywords" : "keywords"}.`}</p>
            {Array.from(new Set([...retrieval.lectures.warnings, ...retrieval.assessment_examples.warnings])).map(warning =>
              <p key={warning} className="text-amber-700 dark:text-amber-400">{warning}</p>)}
            {!!retrieval.assessment_examples.sources.length && <details>
              <summary className="cursor-pointer text-xs font-medium">Assessment examples</summary>
              <p className="mt-2 text-muted-foreground">Used for question style and originality review.</p>
              {retrieval.assessment_examples.sources.map(source => <div key={source.source_id} className="mt-2">
                <strong>{sourceLabel(source)}</strong><p className="whitespace-pre-wrap">{source.text}</p>
              </div>)}
            </details>}
          </div>
        )}

        {generation && <>
          {!generation.similarity_available && <p className="text-xs text-amber-700 dark:text-amber-400">Semantic similarity check unavailable. Text similarity was checked; inspect for reused ideas.</p>}
          {generation.similarity_checks.some(c => c.flagged) && <p className="text-xs text-amber-700 dark:text-amber-400">One or more alternatives closely resemble existing questions. Review originality.</p>}
          {generation.candidates.map(candidate => (
            <div key={candidate.question_id} className="space-y-2 rounded-xl border border-border/70 bg-background p-3">
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="outline" className="rounded-full text-[10px] font-normal">{candidate.bloom_level}</Badge>
                <Badge variant="outline" className="rounded-full text-[10px] font-normal">{candidate.marks} marks</Badge>
                <Badge variant="outline" className="rounded-full text-[10px] font-normal">~{candidate.estimated_minutes} min</Badge>
              </div>
              <p className="whitespace-pre-wrap text-xs leading-5">{candidate.text}</p>
              <details>
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Answer, rubric and source evidence</summary>
                <p className="my-2 whitespace-pre-wrap text-xs leading-5">{candidate.model_answer}</p>
                <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">{candidate.marking_scheme.map((c, i) => <li key={i}>{c.criterion} ({c.marks} marks)</li>)}</ul>
                {candidate.sources.map(s => <p key={s.source_id} className="mt-2 whitespace-pre-wrap text-xs text-muted-foreground"><strong className="text-foreground">{sourceLabel(s)}</strong><br />{s.text}</p>)}
              </details>
              <div className="flex flex-wrap gap-2">
                <CandidateActions topic={candidate.topic} part={{ ...candidate, part: "a", question: candidate.text, max_marks: candidate.marks }} actions={structureActions} fallback={() => addPart(candidate.topic, { ...candidate, part: "a", question: candidate.text, max_marks: candidate.marks })} />
                <Button size="sm" variant="ghost" onClick={() => setPaper(prev => ({ ...prev, rejected_questions: [...(prev.rejected_questions ?? []), { question_id: candidate.question_id, reason: "Generated alternative rejected" }] }))}>Reject</Button>
              </div>
            </div>
          ))}
        </>}
      </div>
    </details>
  </div>;
}

export function PartReviewEditor({ part, onChange }: { part: Part; onChange: (changes: Partial<Part>) => void }) {
  const scheme = part.marking_scheme ?? [];
  const ready = !!part.model_answer?.trim() && !!part.bloom_level && scheme.length > 0 && scheme.every(c => c.criterion.trim() && c.marks > 0)
    && Math.abs(scheme.reduce((sum, c) => sum + c.marks, 0) - part.max_marks) < 0.01;
  const edit = (changes: Partial<Part>) => onChange({ ...changes, review_status: "needs_review" });
  const approved = part.review_status === "approved";
  return <details className="rounded-xl border border-border/70 bg-muted/20 p-2.5 text-xs">
    <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 [&::-webkit-details-marker]:hidden">
      <span className={`size-1.5 shrink-0 rounded-full ${approved ? "bg-emerald-500" : "bg-amber-500"}`} />
      <span className="font-medium">Part {part.part}: answer &amp; marking scheme</span>
      <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-normal ${approved ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400" : "bg-card text-muted-foreground"}`}>
        {approved ? "Approved" : "Needs review"}
      </span>
    </summary>
    <div className="mt-3 space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <label className="text-muted-foreground">Bloom level<select className={selectClass} value={part.bloom_level ?? ""} onChange={e => edit({ bloom_level: e.target.value })}><option value="">Select level</option>{BLOOM_LEVELS.map(l => <option key={l}>{l}</option>)}</select></label>
        <label className="text-muted-foreground">Estimated minutes<Input className="mt-1.5 h-8" type="number" min={1} value={part.estimated_minutes ?? ""} onChange={e => edit({ estimated_minutes: Number(e.target.value) || undefined })} /></label>
      </div>
      <label className="block text-muted-foreground">Model answer (lecturer only)<Textarea className="mt-1.5" value={part.model_answer ?? ""} onChange={e => edit({ model_answer: e.target.value })} /></label>
      {scheme.map((criterion, index) => (
        <div key={index} className="flex gap-2">
          <Input aria-label={`Criterion ${index + 1}`} value={criterion.criterion} onChange={e => edit({ marking_scheme: scheme.map((c, i) => i === index ? { ...c, criterion: e.target.value } : c) })} />
          <Input className="w-20" aria-label={`Criterion ${index + 1} marks`} type="number" min={0.5} step={0.5} value={criterion.marks} onChange={e => edit({ marking_scheme: scheme.map((c, i) => i === index ? { ...c, marks: Number(e.target.value) } : c) })} />
          <Button variant="ghost" size="sm" aria-label={`Remove criterion ${index + 1}`} onClick={() => edit({ marking_scheme: scheme.filter((_, i) => i !== index) })}>Remove</Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => edit({ marking_scheme: [...scheme, { criterion: "", marks: 1 }] })}>Add criterion</Button>
      <p className="text-muted-foreground">Rubric: <span className="font-medium text-foreground">{scheme.reduce((sum, c) => sum + c.marks, 0)}/{part.max_marks}</span> marks</p>
      {part.sources?.map(s => <details key={s.source_id} className={nestedDetails}>
        <summary className={nestedSummary}>{sourceLabel(s)}</summary>
        <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{s.text}</p>
      </details>)}
      <Button size="sm" disabled={!ready || approved} onClick={() => onChange({ review_status: "approved" })}>Approve question and answer</Button>
    </div>
  </details>;
}
