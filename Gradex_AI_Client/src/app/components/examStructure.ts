import type { PaperQuestion, Part } from "../api/examCreatorApi";

export type PlacementSource =
  | { kind: "candidate"; topic: string; part: Part }
  | { kind: "question"; question: number }
  | { kind: "part"; question: number; part: number };
export type PlacementTarget = { question: number; part?: number };

export function renumberQuestions(questions: PaperQuestion[]): PaperQuestion[] {
  return questions.map((q, i) => ({
    ...q, question_number: i + 1,
    parts: q.parts.map((p, j) => ({ ...p, part: String.fromCharCode(97 + j) })),
  }));
}

export function placeQuestion(questions: PaperQuestion[], source: PlacementSource, target: PlacementTarget): PaperQuestion[] {
  const next = questions.map(q => ({ ...q, parts: [...q.parts] }));
  const destination = next[target.question];
  if (!Number.isInteger(target.question) || target.question < 0 || target.question > next.length ||
    (target.part !== undefined && (!destination || !Number.isInteger(target.part) || target.part < 0 || target.part > destination.parts.length))) {
    throw new Error("This destination is no longer available.");
  }
  if (source.kind === "candidate") {
    if (!Number.isFinite(source.part.max_marks) || source.part.max_marks <= 0) throw new Error("Assign positive marks before adding this question.");
    if (source.part.question_id && questions.some(q => q.parts.some(p => p.question_id === source.part.question_id))) {
      throw new Error("This question is already in the draft.");
    }
  }
  const parent = source.kind === "candidate" ? undefined : next[source.question];
  if (source.kind !== "candidate" && (!parent || (source.kind === "part" && !parent.parts[source.part]))) {
    throw new Error("This question is no longer available.");
  }
  const topic = source.kind === "candidate" ? source.topic : parent!.topic;
  if (target.part !== undefined && (source.kind === "question" || destination.topic !== topic)) {
    throw new Error("Add this topic as a separate question so blueprint coverage stays accurate.");
  }
  let questionIndex = target.question;
  let partIndex = target.part;
  let moving: PaperQuestion;
  if (source.kind === "question") {
    moving = next.splice(source.question, 1)[0];
    if (source.question < questionIndex) questionIndex--;
  } else {
    const part = source.kind === "candidate" ? { ...source.part, review_status: "needs_review" as const } : parent!.parts.splice(source.part, 1)[0];
    if (source.kind === "part" && source.question === target.question && partIndex !== undefined && source.part < partIndex) partIndex--;
    moving = { question_number: 0, topic, parts: [part] };
  }
  if (partIndex !== undefined) destination.parts.splice(partIndex, 0, ...moving.parts);
  else next.splice(questionIndex, 0, moving);
  return renumberQuestions(next.filter(q => q.parts.length));
}
