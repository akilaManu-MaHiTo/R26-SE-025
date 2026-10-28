import { expect, it } from "vitest";
import { placeQuestion, type PlacementSource } from "./examStructure";
import type { PaperQuestion, Part } from "../api/examCreatorApi";

const part: Part = { part: "a", question: "Explain joins", max_marks: 10, question_id: "join",
  model_answer: "Combine rows", marking_scheme: [{ criterion: "Explanation", marks: 10 }],
  review_status: "approved", sources: [{ source_id: "lecture1", kind: "lecture", text: "Evidence" }] };
const questions: PaperQuestion[] = [
  { question_number: 1, topic: "SQL", parts: [part, { part: "b", question: "Keys", max_marks: 5 }] },
  { question_number: 2, topic: "SQL", parts: [{ part: "a", question: "Select", max_marks: 5 }] },
  { question_number: 3, topic: "ER", parts: [{ part: "a", question: "Entities", max_marks: 5 }] },
];

it("inserts a candidate at the chosen position and renumbers without mutating the paper", () => {
  const result = placeQuestion(questions, { kind: "candidate", topic: "ER", part: { ...part, question_id: "new" } }, { question: 1 });
  expect(result.map(q => q.question_number)).toEqual([1, 2, 3, 4]);
  expect(result[1].parts[0].question_id).toBe("new");
  expect(questions).toHaveLength(3);
});

it("moves a whole question down and preserves all review evidence", () => {
  const result = placeQuestion(questions, { kind: "question", question: 0 }, { question: 3 });
  expect(result[2].parts[0]).toEqual(part);
  expect(result.map(q => q.question_number)).toEqual([1, 2, 3]);
});

it("moves parts within and between matching topics with correct labels", () => {
  const result = placeQuestion(questions, { kind: "part", question: 0, part: 0 }, { question: 1, part: 1 });
  expect(result[0].parts[0].part).toBe("a");
  expect(result[1].parts[1]).toEqual({ ...part, part: "b" });
  const reordered = placeQuestion(questions, { kind: "part", question: 0, part: 0 }, { question: 0, part: 2 });
  expect(reordered[0].parts.map(p => p.question)).toEqual(["Keys", "Explain joins"]);
});

it("removes an empty parent when moving its last part", () => {
  const result = placeQuestion(questions, { kind: "part", question: 1, part: 0 }, { question: 0, part: 2 });
  expect(result).toHaveLength(2);
  expect(result[0].parts[2].question).toBe("Select");
  expect(result[1].question_number).toBe(2);
});

it("rejects mismatched topics, duplicates, invalid marks and stale destinations", () => {
  expect(() => placeQuestion(questions, { kind: "part", question: 0, part: 0 }, { question: 2, part: 0 })).toThrow(/topic/i);
  expect(() => placeQuestion(questions, { kind: "candidate", topic: "SQL", part }, { question: 3 })).toThrow(/already/i);
  expect(() => placeQuestion(questions, { kind: "candidate", topic: "SQL", part: { ...part, question_id: "new", max_marks: 0 } }, { question: 3 })).toThrow(/marks/i);
  expect(() => placeQuestion(questions, { kind: "question", question: 0 }, { question: 8 })).toThrow();
});

it.each<PlacementSource>([
  { kind: "question", question: 0 },
  { kind: "part", question: 0, part: 0 },
])("keeps a drop on its current position unchanged", source => {
  expect(placeQuestion(questions, source, source.kind === "part" ? { question: 0, part: 0 } : { question: 0 })).toEqual(questions);
});
