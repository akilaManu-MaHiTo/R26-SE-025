import { useEffect, useRef, useState } from "react";
import { BrandOrb } from "./BrandOrb";
import { BLOOM_LEVELS, generateExamQuestions, type GeneratedCandidate, type Paper, type PaperQuestion, type Part } from "../api/examCreatorApi";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import generatorIcon from "./animations/bloub-cercle-surpris-turquoise-anime.svg";
import excitedGeneratorIcon from "./animations/bloub-galet-excite-turquoise-anime.svg";

type Props = {
  courseCode: string; paper: Paper; question: PaperQuestion; part: Part;
  onGenerated: (candidate: GeneratedCandidate) => void;
};

export function CustomQuestionGenerator({ courseCode, paper, question, part, onGenerated }: Props) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState(question.topic);
  const [bloom, setBloom] = useState(part.bloom_level || "Apply");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    setGenerating(false);
    return () => { request.current?.abort(); };
  }, [paper, courseCode]);

  const changeOpen = (next: boolean) => {
    request.current?.abort();
    setGenerating(false);
    setError("");
    if (next) { setTopic(question.topic); setBloom(part.bloom_level || "Apply"); }
    setOpen(next);
  };

  const generate = async () => {
    if (!topic.trim() || !Number.isFinite(part.max_marks) || part.max_marks <= 0 || generating) return;
    if (question.parts.length > 1 && topic.trim() !== question.topic) {
      setError("Make this part a separate question before changing its topic.");
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setGenerating(true);
    setOpen(false);
    setError("");
    // This replaces a part, so release its allocation before checking remaining marks.
    const context = { ...paper, questions: paper.questions.map(q => q === question
      ? { ...q, parts: q.parts.filter(p => p !== part) } : q).filter(q => q.parts.length) };
    try {
      const result = await generateExamQuestions(courseCode, context, topic.trim(), bloom, part.max_marks, controller.signal, 1);
      if (controller.signal.aborted) return;
      const candidate = result.candidates[0];
      if (!candidate) throw new Error("No question was generated. Please try again.");
      onGenerated(candidate);
      setOpen(false);
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "Generation failed. Please try again.");
        setOpen(true);
      }
    } finally {
      if (!controller.signal.aborted) setGenerating(false);
    }
  };

  return <Popover open={open} onOpenChange={changeOpen}>
    <PopoverTrigger asChild>
      <Button type="button" variant="ghost" size="icon" className="group absolute right-1 bottom-1 size-11 rounded-full hover:bg-primary/10"
        disabled={generating}
        aria-label={`Generate Q${question.question_number} part ${part.part} with AI`} title="Generate a question with AI">
        {generating ? <BrandOrb state="solving" size={32} aria-hidden="true" /> : <>
        <img src={generatorIcon} alt="" className="size-10 transition-opacity duration-150 group-hover:opacity-0 group-focus-visible:opacity-0 motion-reduce:transition-none" />
        <img src={excitedGeneratorIcon} alt="" className="absolute size-10 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100 motion-reduce:transition-none" />
        </>}
      </Button>
    </PopoverTrigger>
    <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] space-y-3" aria-label="Generate a question">
      <div><h3 className="font-semibold">Generate a question</h3>
        <p className="text-xs text-muted-foreground">Choose a lecture topic and Bloom level · {part.max_marks} marks</p></div>
      <label className="block text-sm">Lecture topic
        <Input list="creator-topics" value={topic} maxLength={200} disabled={generating} placeholder="Select or enter a course topic" onChange={e => setTopic(e.target.value)} />
      </label>
      <label className="block text-sm">Bloom level
        <select className="mt-1 w-full rounded-md border bg-background p-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
          value={bloom} disabled={generating} onChange={e => setBloom(e.target.value)}>
          {BLOOM_LEVELS.map(level => <option key={level}>{level}</option>)}
        </select>
      </label>
      <p className="text-xs text-muted-foreground">{part.question.trim() ? "This replaces the current question text. " : ""}Review and edit the result before approving it.</p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="button" className="w-full" disabled={generating || !topic.trim() || !Number.isFinite(part.max_marks) || part.max_marks <= 0} onClick={generate}>
        {generating ? "Generating question…" : "Generate question"}
      </Button>
    </PopoverContent>
    <span role="status" className="sr-only">{generating ? "Generating question. Please wait." : ""}</span>
  </Popover>;
}
