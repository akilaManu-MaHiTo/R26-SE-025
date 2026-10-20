import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { ThinkingOrb } from "thinking-orbs";
import { toast } from "sonner";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { BLOOM_LEVELS, defaultBlueprint, generateExamQuestions, reviewExamPaper,
  type Blueprint, type CreatorReview, type Generation, type Paper, type Part,
  type MaterialSource, type GenerationRetrieval, type CreatorApiError } from "../api/examCreatorApi";

import { CandidateActions, type StructureActions } from "./ExamStructureControls";

type Props = { structureActions?: StructureActions; courseCode: string; paper: Paper; setPaper: Dispatch<SetStateAction<Paper>> };
const selectClass = "w-full rounded border bg-background p-2 text-sm";
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
    <details className="rounded-xl border bg-card p-4 space-y-3">
      <summary className="font-semibold cursor-pointer">Exam settings · {blueprint.total_marks} marks · {blueprint.duration_minutes} min</summary>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs">Target marks<Input type="number" min={1} max={1000} value={blueprint.total_marks} onChange={e => updateBlueprint({ total_marks: Number(e.target.value) })} /></label>
        <label className="text-xs">Duration (minutes)<Input type="number" min={1} max={1440} value={blueprint.duration_minutes} onChange={e => updateBlueprint({ duration_minutes: Number(e.target.value) })} /></label>
        <label className="text-xs">Paper year<Input type="number" min={1900} max={2200} value={paper.year} onChange={e => setPaper(prev => ({ ...prev, year: Number(e.target.value) }))} /></label>
        <label className="text-xs">Purpose<select className={selectClass} value={blueprint.purpose} onChange={e => updateBlueprint({ purpose: e.target.value as Blueprint["purpose"] })}><option value="final">Final examination</option><option value="revision">Revision assessment</option></select></label>
      </div>
      <p className="text-xs text-muted-foreground">Final exams prioritize coverage. Revision assessments also prioritize measured student weaknesses.</p>
      <label className="block text-xs">Learning outcomes<Textarea maxLength={5000} value={blueprint.learning_outcomes} placeholder="What should students demonstrate?" onChange={e => updateBlueprint({ learning_outcomes: e.target.value })} /></label>
      <details><summary className="cursor-pointer text-sm">Topic mark allocation</summary>
        <p className="text-xs text-muted-foreground my-2">Allocate all marks for a fixed syllabus blueprint, or leave some unallocated.</p>
        {Object.entries(blueprint.topic_marks).map(([name, target]) => <div key={name} className="flex items-center gap-2 my-2">
          <label className="text-xs flex-1">{name}<Input aria-label={`Target marks for ${name}`} type="number" min={0} value={target} onChange={e => updateBlueprint({ topic_marks: { ...blueprint.topic_marks, [name]: Number(e.target.value) } })} /></label>
          <Button size="sm" variant="ghost" aria-label={`Remove ${name} allocation`} onClick={() => { const next = { ...blueprint.topic_marks }; delete next[name]; updateBlueprint({ topic_marks: next }); }}>Remove</Button>
        </div>)}
        <div className="flex gap-2"><Input aria-label="Topic to allocate" list="creator-topics" placeholder="Topic name" value={allocationTopic} onChange={e => setAllocationTopic(e.target.value)} /><Button size="sm" disabled={!allocationTopic.trim()} onClick={() => { updateBlueprint({ topic_marks: { ...blueprint.topic_marks, [allocationTopic.trim()]: 0 } }); setAllocationTopic(""); }}>Add</Button></div>
      </details>
      <details><summary className="cursor-pointer text-sm">Bloom percentages</summary><div className="grid grid-cols-2 gap-2 mt-2">
        {BLOOM_LEVELS.map(level => <label key={level} className="text-xs">{level} %<Input type="number" min={0} max={100} value={blueprint.bloom_percentages[level] ?? 0} onChange={e => updateBlueprint({ bloom_percentages: { ...blueprint.bloom_percentages, [level]: Number(e.target.value) } })} /></label>)}
      </div><p className="text-xs mt-2">Total: {Object.values(blueprint.bloom_percentages).reduce((s, n) => s + n, 0)}% (must equal 100%)</p></details>
      <details><summary className="cursor-pointer text-sm">Lecture notes for generation</summary>
        <label className="block text-xs mt-2">Relevant course material<Textarea maxLength={20000} rows={6} value={blueprint.lecture_notes} placeholder="Paste relevant lecture passages, definitions, examples and schemas." onChange={e => updateBlueprint({ lecture_notes: e.target.value })} /></label>
        <p className="text-xs text-muted-foreground">Saved with this draft. Generation also searches indexed course lectures. Lecture objectives are used when no matching passages are available.</p>
      </details>
      <datalist id="creator-topics">{Array.from(new Set([...(review?.topics ?? []), ...Object.keys(blueprint.topic_marks)])).map(t => <option key={t} value={t} />)}</datalist>
    </details>

    <div className="space-y-2"><h3 className="font-semibold text-sm">Recommended questions</h3>
      {review && !review.recommendations.length && <p className="text-xs text-muted-foreground">No bank questions fit the remaining allocation. Adjust the blueprint or generate a new alternative.</p>}
      {review?.recommendations.map(rec => <Card key={rec.question_id} className="p-3 space-y-2">
        <p className="text-xs font-medium">{rec.canonical_topic} · {rec.bloom_level} · {rec.requires_marks ? "Marks not assigned" : `${rec.marks} marks`}</p>
        <p className="text-xs whitespace-pre-wrap max-h-48 overflow-auto">{rec.text}</p>
        <p className="text-xs text-muted-foreground">{rec.blueprint_reason}</p>
        {rec.requires_marks && <label className="block text-xs">Assign marks (up to {rec.max_available_marks})<Input aria-label={`Marks for ${rec.question_id}`} type="number" min={1} max={rec.max_available_marks} value={candidateMarks[rec.question_id] ?? ""} onChange={e => setCandidateMarks(prev => ({ ...prev, [rec.question_id]: Number(e.target.value) }))} /></label>}
        <div className="flex gap-2"><CandidateActions topic={rec.canonical_topic}
          part={{ part: "a", question: rec.text, max_marks: rec.requires_marks ? candidateMarks[rec.question_id] : rec.marks, question_id: rec.question_id, bloom_level: rec.bloom_level, review_status: "needs_review" }}
          actions={structureActions} disabled={rec.requires_marks && (!(candidateMarks[rec.question_id] > 0) || candidateMarks[rec.question_id] > rec.max_available_marks)}
          fallback={() => addPart(rec.canonical_topic, { part: "a", question: rec.text, max_marks: rec.requires_marks ? candidateMarks[rec.question_id] : rec.marks, question_id: rec.question_id, bloom_level: rec.bloom_level, review_status: "needs_review" })} />
          <Button size="sm" variant="ghost" onClick={() => {
            const reason = window.prompt("Why is this question unsuitable? (optional)", "");
            if (reason !== null) setPaper(prev => ({ ...prev, rejected_questions: [...(prev.rejected_questions ?? []), { question_id: rec.question_id, reason: reason.slice(0, 1000) }] }));
          }}>Reject</Button></div>
      </Card>)}
      {!!paper.rejected_questions?.length && <Button variant="ghost" size="sm" onClick={() => setPaper(prev => ({ ...prev, rejected_questions: [] }))}>Reset {paper.rejected_questions.length} rejected suggestions</Button>}
    </div>

    <Card className="p-4 space-y-2" aria-live="polite">
      <h3 className="font-semibold">Paper checks</h3>
      {loading && <p className="flex items-center gap-2 text-sm"><ThinkingOrb state="solving" size={20} aria-hidden="true" />Checking draft…</p>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {review && <>
        <p className="text-sm">{review.review.total_marks}/{blueprint.total_marks} marks · {review.review.remaining_marks} remaining</p>
        <p className="text-xs">Estimated time: {review.review.estimated_minutes} minutes ({review.review.estimated_parts}/{review.review.part_count} parts estimated).</p>
        {!review.analytics_available && <p className="text-xs text-amber-700">No saved analytics for this source exam. Recommendations use the blueprint and course bank.</p>}
        <details><summary className="cursor-pointer text-sm">Coverage details</summary><div className="grid grid-cols-2 gap-1 text-xs">{Object.entries(review.review.bloom_coverage).map(([name, c]) => <span key={name}>{name}: {c.actual}/{c.target} marks</span>)}</div></details>
        {review.review.issues.length ? <details open><summary className="text-sm cursor-pointer">{review.review.issues.length} items to review</summary><ul className="list-disc pl-4 text-xs space-y-1 max-h-48 overflow-auto mt-2">{review.review.issues.map((i, n) => <li key={n}>{i.message}</li>)}</ul></details> : <p className="text-sm text-green-700">Structural checks passed. Verify academic correctness before publishing.</p>}
      </>}
    </Card>

    <details className="rounded-xl border bg-card p-4 space-y-3">
      <summary className="font-semibold cursor-pointer">Generate alternatives with AI</summary>
      <label className="block text-xs">Topic<Input list="creator-topics" value={topic} onChange={e => { setTopic(e.target.value); clearGeneration(); }} placeholder="Select or enter a course topic" /></label>
      <div className="grid grid-cols-2 gap-2"><label className="text-xs">Bloom level<select className={selectClass} value={bloom} onChange={e => { setBloom(e.target.value); clearGeneration(); }}>{BLOOM_LEVELS.map(l => <option key={l}>{l}</option>)}</select></label>
        <label className="text-xs">Marks per alternative<Input type="number" min={1} value={marks} onChange={e => { setMarks(Number(e.target.value)); clearGeneration(); }} /></label></div>
      <Button className="w-full" disabled={generating || loading || !!error || !topic.trim() || marks <= 0} onClick={generate}>{generating ? <><ThinkingOrb state="composing" size={20} aria-hidden="true" />Generating questions…</> : "Generate 2 alternatives"}</Button>
      <p className="text-xs text-muted-foreground">Review the answer, rubric, sources and Bloom level before approving a question.</p>
      {generationError && <p role="alert" className="text-sm text-red-600">{generationError}</p>}
      {retrieval && <div className="space-y-2 text-xs" aria-live="polite">
        <p>Retrieved {retrieval.lectures.sources.length} lecture passages and {retrieval.assessment_examples.sources.length} assessment examples.
          {retrieval.lectures.status === "ok" && ` Search: ${retrieval.lectures.mode === "hybrid" ? "semantic + keywords" : "keywords"}.`}</p>
        {Array.from(new Set([...retrieval.lectures.warnings, ...retrieval.assessment_examples.warnings])).map(warning =>
          <p key={warning} className="text-amber-700">{warning}</p>)}
        {!!retrieval.assessment_examples.sources.length && <details>
          <summary className="cursor-pointer">Assessment examples</summary>
          <p className="mt-2 text-muted-foreground">Used for question style and originality review.</p>
          {retrieval.assessment_examples.sources.map(source => <div key={source.source_id} className="mt-2">
            <strong>{sourceLabel(source)}</strong><p className="whitespace-pre-wrap">{source.text}</p>
          </div>)}
        </details>}
      </div>}
      {generation && <>
        {!generation.similarity_available && <p className="text-xs text-amber-700">Semantic similarity check unavailable. Text similarity was checked; inspect for reused ideas.</p>}
        {generation.similarity_checks.some(c => c.flagged) && <p className="text-xs text-amber-700">One or more alternatives closely resemble existing questions. Review originality.</p>}
        {generation.candidates.map(candidate => <div key={candidate.question_id} className="border rounded p-3 space-y-2">
          <p className="text-sm whitespace-pre-wrap">{candidate.text}</p>
          <p className="text-xs">{candidate.marks} marks · {candidate.bloom_level} · estimated {candidate.estimated_minutes} min</p>
          <details><summary className="text-xs cursor-pointer">Answer, rubric and source evidence</summary>
            <p className="text-xs whitespace-pre-wrap my-2">{candidate.model_answer}</p>
            <ul className="text-xs list-disc pl-4">{candidate.marking_scheme.map((c, i) => <li key={i}>{c.criterion} ({c.marks} marks)</li>)}</ul>
            {candidate.sources.map(s => <p key={s.source_id} className="text-xs whitespace-pre-wrap mt-2"><strong>{sourceLabel(s)}</strong><br />{s.text}</p>)}
          </details>
          <div className="flex gap-2"><CandidateActions topic={candidate.topic} part={{ ...candidate, part: "a", question: candidate.text, max_marks: candidate.marks }} actions={structureActions} fallback={() => addPart(candidate.topic, { ...candidate, part: "a", question: candidate.text, max_marks: candidate.marks })} />
          <Button size="sm" variant="ghost" onClick={() => setPaper(prev => ({ ...prev, rejected_questions: [...(prev.rejected_questions ?? []), { question_id: candidate.question_id, reason: "Generated alternative rejected" }] }))}>Reject</Button></div>
        </div>)}
      </>}
    </details>


  </div>;
}

export function PartReviewEditor({ part, onChange }: { part: Part; onChange: (changes: Partial<Part>) => void }) {
  const scheme = part.marking_scheme ?? [];
  const ready = !!part.model_answer?.trim() && !!part.bloom_level && scheme.length > 0 && scheme.every(c => c.criterion.trim() && c.marks > 0)
    && Math.abs(scheme.reduce((sum, c) => sum + c.marks, 0) - part.max_marks) < 0.01;
  const edit = (changes: Partial<Part>) => onChange({ ...changes, review_status: "needs_review" });
  return <details className="text-xs border rounded p-2">
    <summary className="cursor-pointer">Part {part.part}: answer and marking scheme · {part.review_status === "approved" ? "Approved" : "Needs review"}</summary>
    <div className="space-y-2 mt-3">
      <div className="grid grid-cols-2 gap-2"><label>Bloom level<select className={selectClass} value={part.bloom_level ?? ""} onChange={e => edit({ bloom_level: e.target.value })}><option value="">Select level</option>{BLOOM_LEVELS.map(l => <option key={l}>{l}</option>)}</select></label>
        <label>Estimated minutes<Input type="number" min={1} value={part.estimated_minutes ?? ""} onChange={e => edit({ estimated_minutes: Number(e.target.value) || undefined })} /></label></div>
      <label className="block">Model answer (lecturer only)<Textarea value={part.model_answer ?? ""} onChange={e => edit({ model_answer: e.target.value })} /></label>
      {scheme.map((criterion, index) => <div key={index} className="flex gap-2"><Input aria-label={`Criterion ${index + 1}`} value={criterion.criterion} onChange={e => edit({ marking_scheme: scheme.map((c, i) => i === index ? { ...c, criterion: e.target.value } : c) })} />
        <Input className="w-20" aria-label={`Criterion ${index + 1} marks`} type="number" min={0.5} step={0.5} value={criterion.marks} onChange={e => edit({ marking_scheme: scheme.map((c, i) => i === index ? { ...c, marks: Number(e.target.value) } : c) })} />
        <Button variant="ghost" size="sm" aria-label={`Remove criterion ${index + 1}`} onClick={() => edit({ marking_scheme: scheme.filter((_, i) => i !== index) })}>Remove</Button></div>)}
      <Button variant="outline" size="sm" onClick={() => edit({ marking_scheme: [...scheme, { criterion: "", marks: 1 }] })}>Add criterion</Button>
      <p>Rubric: {scheme.reduce((sum, c) => sum + c.marks, 0)}/{part.max_marks} marks</p>
      {part.sources?.map(s => <details key={s.source_id}><summary className="cursor-pointer">{sourceLabel(s)}</summary><p className="whitespace-pre-wrap">{s.text}</p></details>)}
      <Button size="sm" disabled={!ready || part.review_status === "approved"} onClick={() => onChange({ review_status: "approved" })}>Approve question and answer</Button>
    </div>
  </details>;
}
